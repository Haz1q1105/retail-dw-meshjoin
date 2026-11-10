"""
MESHJOIN: enrich sales with Customer and Product Master Data.
Master Data stays in MySQL and is read one page (partition) of 500 rows at a time.
"""
import csv
import getpass
from collections import deque

import mysql.connector

# ---------- Settings (PDF section 12) ----------
PAGE_SIZE = 500        # Master Data rows per page (disk buffer size)
CHUNK_SIZE = 500       # sales taken into H each round (w)
BUFFER_LIMIT = 1000    # max sales waiting in the stream buffer

CUST_COLS = ["customer_id", "gender", "age_group", "occupation",
             "city_category", "stay_in_current_city_years", "marital_status"]
PROD_COLS = ["product_id", "product_name", "product_category",
             "supplier_id", "supplier_name"]


# ---------- Disk: read one page of a Master Data table ----------
def read_page(cur, table, key, page):
    sql = f"SELECT * FROM {table} ORDER BY {key} LIMIT {PAGE_SIZE} OFFSET {page * PAGE_SIZE}"
    cur.execute(sql)
    return cur.fetchall()


def count_pages(cur, table):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    rows = cur.fetchone()[0]
    return (rows + PAGE_SIZE - 1) // PAGE_SIZE      # round UP


class MeshJoin:
    def __init__(self, cur):
        self.cur = cur
        self.stream_buffer = deque()   # waiting line of sales
        self.H_cust = {}               # trays by customer_id
        self.H_prod = {}               # trays by product_id
        self.queue = deque()           # bundles on the desk, oldest first

        self.n_cust_pages = count_pages(cur, "customer_md")
        self.n_prod_pages = count_pages(cur, "product_md")
        # a bundle stays until it has seen every page of BOTH books
        self.rounds_needed = max(self.n_cust_pages, self.n_prod_pages)
        self.cust_page = 0
        self.prod_page = 0

    # ----- Step 2 helpers -----
    def take_chunk(self):
        chunk = []
        while len(chunk) < CHUNK_SIZE and len(self.stream_buffer) > 0:
            chunk.append(self.stream_buffer.popleft())
        return chunk

    def add_chunk(self, chunk):
        for sale in chunk:
            self.H_cust.setdefault(sale["customer_id"], []).append(sale)
            self.H_prod.setdefault(sale["product_id"], []).append(sale)
        self.queue.append({"sales": chunk, "rounds": 0})

    # ----- Step 3 -----
    def probe(self, page_rows, H, cols):
        for row in page_rows:
            key = row[0]
            if key in H:
                for sale in H[key]:
                    for name, value in zip(cols[1:], row[1:]):
                        sale[name] = value

    # ----- Step 4 helper -----
    def remove_from_trays(self, chunk):
        for sale in chunk:
            for H, key in ((self.H_cust, sale["customer_id"]),
                           (self.H_prod, sale["product_id"])):
                H[key] = [s for s in H[key] if s is not sale]
                if not H[key]:
                    del H[key]          # throw away empty trays

    # ----- One full round (PDF section 4.2) -----
    def run_round(self, chunk=None):
        # 1. disk buffer: load the NEXT page of each book (loop back after the last)
        cust_disk = read_page(self.cur, "customer_md", "customer_id", self.cust_page)
        prod_disk = read_page(self.cur, "product_md", "product_id", self.prod_page)
        used_pages = (self.cust_page, self.prod_page)
        self.cust_page = (self.cust_page + 1) % self.n_cust_pages
        self.prod_page = (self.prod_page + 1) % self.n_prod_pages

        # 2. take a new bundle from the line onto the desk
        #    (main.py hands us the chunk; the small test takes it from our own line)
        if chunk is None:
            chunk = self.take_chunk()
        if chunk:
            self.add_chunk(chunk)

        # 3. match the pages against the trays
        self.probe(cust_disk, self.H_cust, CUST_COLS)
        self.probe(prod_disk, self.H_prod, PROD_COLS)

        # 4. bundles that have seen every page leave the desk
        for bundle in self.queue:
            bundle["rounds"] += 1
        finished = []
        while self.queue and self.queue[0]["rounds"] >= self.rounds_needed:
            bundle = self.queue.popleft()
            self.remove_from_trays(bundle["sales"])
            finished.extend(bundle["sales"])
        return finished, used_pages

    def sales_in_H(self):
        return sum(len(b["sales"]) for b in self.queue)


# ---------- Small test: 2,000 online sales, no threads yet ----------
if __name__ == "__main__":
    TEST_SALES = 2000

    conn = mysql.connector.connect(host="localhost", database="retail_dw",
                                   user="haziq", password=getpass.getpass("Password: "))
    mj = MeshJoin(conn.cursor())
    print(f"Customer pages: {mj.n_cust_pages} | Product pages: {mj.n_prod_pages} "
          f"| A bundle stays {mj.rounds_needed} rounds")

    f = open("Data/online_sales_stream.csv")
    reader = csv.DictReader(f)
    read_so_far = 0
    output = []
    r = 0
    while True:
        # top up the waiting line (max 1000), until 2000 test sales have arrived
        while len(mj.stream_buffer) < BUFFER_LIMIT and read_so_far < TEST_SALES:
            mj.stream_buffer.append(next(reader))
            read_so_far += 1

        if not mj.stream_buffer and not mj.queue:
            break                                   # nothing left anywhere

        r += 1
        finished, (cp, pp) = mj.run_round()
        output.extend(finished)
        print(f"Round {r:2}: customer page {cp}, product page {pp} | "
              f"bundles on desk {len(mj.queue)} | sales in H {mj.sales_in_H():4} | "
              f"finished this round {len(finished):3} | total finished {len(output)}")

    complete = [s for s in output if "gender" in s and "supplier_name" in s]
    print(f"\nSales in: {read_so_far} | Sales out: {len(output)} | Fully enriched: {len(complete)}")
    f.close()
    conn.close()
