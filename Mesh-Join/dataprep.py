import pandas as pd

RAW_PATH = "Data/Online Retail.xlsx"
df = pd.read_excel(RAW_PATH,dtype={"InvoiceNo": str, "StockCode":str})

print("Rows:", len(df))
print("Columns:", list(df.columns))
print(df.head(5))

