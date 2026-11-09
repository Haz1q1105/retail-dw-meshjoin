import mysql.connector
import getpass

PAGE_SIZE = 500

def read_page(cur, table, key, page):
    # page starts at 0 in Python: page 0 = first page
    sql = f"SELECT * FROM {table} ORDER BY {key} LIMIT {PAGE_SIZE} OFFSET {((page+1) - 1) * PAGE_SIZE}"
    cur.execute(sql)
    return cur.fetchall()     # gives back the rows as a list

# ---------- test ----------
conn = mysql.connector.connect(host="localhost", database="retail_dw",
                               user="haziq", password=getpass.getpass("Password: "))
cur = conn.cursor()

for p in range(9):
    rows = read_page(cur, "customer_md", "customer_id", p)
    print("Customer page", p,"->", len(rows), "rows")