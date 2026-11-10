
import hashlib
from datetime import datetime
from decimal import Decimal

# Store list, kept in memory (PDF section 5.4.2)
STORES = {1: ("Online", "Web"),
          2: ("London Bridge", "London"),
          3: ("Manchester Arndale", "Manchester"),
          4: ("Birmingham Bullring", "Birmingham"),
          5: ("Edinburgh Princes", "Edinburgh")}


def stable(text, n):
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16) % n


def store_id_for(sale):
    """Store enrichment, done outside MESHJOIN (PDF section 5.4.3)."""
    if sale["sales_mode"] == "Online":
        return 1
    return 2 + stable(sale["transaction_id"], 4)


def time_parts(dt):
    """Split one timestamp into the dim_time columns (PDF section 8)."""
    m = dt.month
    if m in (12, 1, 2):
        season = "Winter"
    elif m in (3, 4, 5):
        season = "Spring"
    elif m in (6, 7, 8):
        season = "Summer"
    else:
        season = "Fall"
    return (dt, dt.date(), dt.hour, dt.day, m, (m - 1) // 3 + 1, dt.year,
            dt.strftime("%A"),
            "Weekend" if dt.weekday() >= 5 else "Weekday",
            season,
            "H1" if m <= 6 else "H2")


def reset_dw(conn):
    """Empty the fact and dimension tables for a fresh run."""
    cur = conn.cursor()
    cur.execute("DELETE FROM fact_sales")
    for t in ("dim_customer", "dim_product", "dim_supplier", "dim_store", "dim_time"):
        cur.execute(f"DELETE FROM {t}")
    conn.commit()


class DWLoader:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        self.cache = {}            # (table, id) -> key we already know

    def get_key(self, table, key_col, id_col, id_value, insert_sql, values):
        """Find the card number; make the card first if it doesn't exist."""
        if (table, id_value) in self.cache:
            return self.cache[(table, id_value)]
        self.cur.execute(f"SELECT {key_col} FROM {table} WHERE {id_col} = %s", (id_value,))
        row = self.cur.fetchone()
        if row:
            key = row[0]
        else:
            self.cur.execute(insert_sql, values)        # new card
            key = self.cur.lastrowid
        self.cache[(table, id_value)] = key
        return key

    def load(self, sales):
        facts = []
        for s in sales:
            # 1. card numbers from the 5 cabinets
            c = self.get_key("dim_customer", "customer_key", "customer_id", s["customer_id"],
                             "INSERT INTO dim_customer (customer_id, gender, age_group, occupation, "
                             "city_category, stay_in_current_city_years, marital_status) "
                             "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                             (s["customer_id"], s["gender"], s["age_group"], s["occupation"],
                              s["city_category"], s["stay_in_current_city_years"], s["marital_status"]))
            p = self.get_key("dim_product", "product_key", "product_id", s["product_id"],
                             "INSERT INTO dim_product (product_id, product_name, product_category) "
                             "VALUES (%s,%s,%s)",
                             (s["product_id"], s["product_name"], s["product_category"]))
            sp = self.get_key("dim_supplier", "supplier_key", "supplier_id", s["supplier_id"],
                              "INSERT INTO dim_supplier (supplier_id, supplier_name) VALUES (%s,%s)",
                              (s["supplier_id"], s["supplier_name"]))
            sid = store_id_for(s)
            st = self.get_key("dim_store", "store_key", "store_id", sid,
                              "INSERT INTO dim_store (store_id, store_name, city) VALUES (%s,%s,%s)",
                              (sid,) + STORES[sid])
            dt = s["event_time"]
            if isinstance(dt, str):
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            t = self.get_key("dim_time", "time_key", "full_datetime", dt,
                             "INSERT INTO dim_time (full_datetime, full_date, hour_of_day, day_of_month, "
                             "month_num, quarter_num, year_num, day_name, day_type, season, half_year) "
                             "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                             time_parts(dt))

            # 2. revenue = quantity x price (computed here, PDF section 6.2)
            qty = int(s["quantity"])
            revenue = Decimal(str(s["unit_price"])) * qty

            # 3. one receipt line
            facts.append((s["transaction_id"], c, p, sp, st, t, qty, revenue,
                           s["sales_mode"], s.get("processing_mode", "DIRECT")))

        self.cur.executemany(
            "INSERT INTO fact_sales (transaction_id, customer_key, product_key, supplier_key, "
            "store_key, time_key, quantity, revenue, sales_mode, processing_mode) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", facts)
        self.conn.commit()
        return len(facts)


if __name__ == "__main__":
    import csv
    import getpass
    import mysql.connector
    from meshjoin import MeshJoin

    conn = mysql.connector.connect(host="localhost", database="retail_dw",
                                   user="haziq", password=getpass.getpass("Password: "))
    reset_dw(conn)
    mj = MeshJoin(conn.cursor())
    loader = DWLoader(conn)

    reader = csv.DictReader(open("Data/online_sales_stream.csv"))
    for _ in range(2000):
        mj.stream_buffer.append(next(reader))

    loaded = 0
    while mj.stream_buffer or mj.queue:
        finished, _ = mj.run_round()
        loaded += loader.load(finished)
    print("Loaded into fact_sales:", loaded)
    conn.close()
