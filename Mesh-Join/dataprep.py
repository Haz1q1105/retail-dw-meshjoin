import pandas as pd

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

