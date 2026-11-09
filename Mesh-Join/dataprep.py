import pandas as pd
import hashlib
import mysql.connector
import getpass


## functions 
def stable(text, n):
    fingerprint = hashlib.md5(text.encode("utf-8")).hexdigest()
    firste = fingerprint[:8]
    number =  int(firste, 16)
    return number % n


RAW_PATH = "Data/Online Retail.xlsx"
df = pd.read_excel(RAW_PATH,dtype={"InvoiceNo": str, "StockCode":str})

print("Rows:", len(df))
print("Columns:", list(df.columns))
print(df.head(5))


## Data cleaning process

mask = ((df["Quantity"] > 0)& (df["UnitPrice"] > 0)& (df["CustomerID"].notna())& (~df["InvoiceNo"].str.startswith("C"))
)

clean = df[mask].copy()

print("After cleaning:", len(clean))

clean["CustomerID"] = clean["CustomerID"].astype(int).astype(str)

# using the md5 method function to divide online and brick and mortar sales 
def sales_mode(inv):
    return "Online" if stable(inv, 10) <= 6 else "Periodic"

def store_id(inv):
    return 1 if sales_mode(inv) == "Online" else 2 + stable(inv, 4)

clean["sales_mode"] = clean["InvoiceNo"].map(sales_mode)
clean["store_id"] = clean["InvoiceNo"].map(store_id)

print(clean["sales_mode"].value_counts(normalize=True))
print(clean["store_id"].value_counts().sort_index())


# master data for the customer 
GENDERS = ["Male", "Female"]
AGES    = ["0-17","18-25","26-35","36-45","46-50","51-55","55+"]
OCCS    = ["Student","Engineer","Teacher","Executive","Clerk","Healthcare","Retail","Homemaker","Artist","Other"]
CITY    = ["A", "B", "C"]
STAY    = ["0", "1", "2", "3", "4+"]
MARITAL = ["Single", "Married"]

# choosing customer's country from their cleaned transaction
first_country = (clean.sort_values("InvoiceDate", kind="stable").groupby("CustomerID")["Country"].first())

rows = []
for cid, country in first_country.items():
    rows.append({
        "customer_id": cid,
        "gender": GENDERS[stable(cid, 2)],          
        "age_group": AGES[stable(cid + "age",7)],       
        "occupation": OCCS[stable(cid + "occ", 10)],
        "city_category": CITY[stable(cid + country, 3)],
        "stay_in_current_city_years": STAY[stable(cid + "stay", 5)],
        "marital_status": MARITAL[stable(cid + "mar", 2)],
    })

cust = pd.DataFrame(rows)
cust.to_csv("Data/customer_master_data.csv", index=False)
print("Customers:", len(cust))
print(cust.head())

# master data for the products
CATEGORIES = ["Home Decor", "Kitchen", "Stationery", "Toys", "Seasonal Gifts","Bags", "Jewelry", "Garden", "Party", "Other"]
SUPPLIERS = [("SUP01", "Northwind Supplies"), ("SUP02", "Atlantic Gifts Ltd"),("SUP03", "Midlands Wholesale"), ("SUP04", "Celtic Craft Co"),("SUP05", "EuroPack Partners")]

# for each product keeping longest ID
names = clean.groupby("StockCode")["Description"].agg(
    lambda d: max(d.dropna(), key=len, default="UNKNOWN"))

rows = []
for pid, name in names.items():
    sup_id, sup_name = SUPPLIERS[stable(pid,5)]      
    rows.append({
        "product_id": pid,
        "product_name": name,
        "product_category": CATEGORIES[ stable(pid + "cat", 10) ],  
        "supplier_id": sup_id,
        "supplier_name": sup_name,
    })

prod = pd.DataFrame(rows)
prod.to_csv("Data/product_master_data.csv", index=False)
print("Products:", len(prod))
print(prod.head())


RENAME = {"InvoiceNo": "transaction_id", "CustomerID": "customer_id","StockCode": "product_id", "Quantity": "quantity","UnitPrice": "unit_price", "InvoiceDate": "event_time"}
COLS = ["transaction_id", "customer_id", "product_id", "quantity","unit_price", "event_time", "sales_mode"]

sales = clean.rename(columns=RENAME)

# ---------- Online stream file ----------
online = sales[sales["sales_mode"] == "Online"]                # only online rows
online = online.sort_values("event_time", kind="stable")       # oldest first
online = online[COLS]                                          # only the PDF columns

online.to_csv("Data/online_sales_stream.csv", index=False)
print("Online rows:", len(online))


# ---------- Connect to MySQL ---------

conn = mysql.connector.connect(
    host=input("Host [localhost]: ") or "localhost",
    port=int(input("Port [3306]: ") or 3306),
    database=input("Database [retail_dw]: ") or "retail_dw",
    user=input("User [root]: ") or "root",
    password=getpass.getpass("Password: "),   # typing is hidden
)
cur = conn.cursor()
print("Connected to MySQL")


# ---------- Load Master Data into MySQL ----------
# Empty the tables first, so running this file twice does not create duplicates
cur.execute("DELETE FROM customer_md")
cur.executemany(
    "INSERT INTO customer_md VALUES (%s, %s, %s, %s, %s, %s, %s)",
    cust.values.tolist())

cur.execute("DELETE FROM product_md")
cur.executemany(
    "INSERT INTO product_md VALUES (%s, %s, %s, %s, %s)",
    prod.values.tolist())

conn.commit()   # save -- without this MySQL throws the inserts away
print("Customers loaded:", len(cust), "| Products loaded:", len(prod))


# ---------- Load periodic (store) sales into the staging table ----------
# 1. keep only store rows, oldest first
periodic = sales[sales["sales_mode"] == "Periodic"]
periodic = periodic.sort_values("event_time", kind="stable")[COLS].copy()

# 2. cut the sorted list into 48 equal groups: 0, 1, 2 ... 47
n = len(periodic)
periodic["release_hour"] = [i * 48 // n for i in range(n)]

# 3. MySQL wants dates as text like "2010-12-01 08:26:00"
periodic["event_time"] = periodic["event_time"].dt.strftime("%Y-%m-%d %H:%M:%S")

# 4. insert in batches of 5000 rows (one huge insert can be too big for MySQL)
cur.execute("DELETE FROM periodic_sales_data")
sql = ("INSERT INTO periodic_sales_data "
       "(transaction_id, customer_id, product_id, quantity, unit_price, "
       "event_time, sales_mode, release_hour) "
       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
rows = periodic.values.tolist()
for start in range(0, n, 5000):
    cur.executemany(sql, rows[start:start + 5000])
conn.commit()

sizes = periodic["release_hour"].value_counts()
print("Periodic rows loaded:", n)
print("Smallest group:", sizes.min(), "| Largest group:", sizes.max())

cur.close()
conn.close()
print("All done ")
