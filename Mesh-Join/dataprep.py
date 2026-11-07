import pandas as pd
import hashlib


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
