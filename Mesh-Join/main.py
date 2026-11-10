
import csv
import getpass
import threading
import time
from collections import deque

import mysql.connector


BUFFER_LIMIT = 1000      # max sales waiting on the counter (stream buffer)
PEAK_SPEED = 80          # sales per second in peak time
NONPEAK_SPEED = 10       # sales per second in non-peak time
HOUR_SECONDS = 60        # one simulated hour = 60 real seconds
N_GROUPS = 48            # periodic groups, one released per hour


stream_buffer = deque()              # the counter
periodic_lane = deque()              # store sales brought in by the PeriodicThread
buffer_lock = threading.Lock()       # only one hand on the counter at a time
settings = {"speed": PEAK_SPEED}     # can be changed while running
stop_event = threading.Event()       # when set -> every thread stops


# Online Thread
def online_thread(csv_path):
    next_time = time.perf_counter()          # the timetable: when the next sale is due
    with open(csv_path) as f:
        for sale in csv.DictReader(f):
            # wait here while the counter is full
            while not stop_event.is_set():
                with buffer_lock:                       # take the lock
                    if len(stream_buffer) < BUFFER_LIMIT:
                        stream_buffer.append(sale)      # put sale on counter
                        break                           # done, next sale
                time.sleep(0.01)                        # full: wait a moment
            if stop_event.is_set():
                return
            # timetable: next sale is due 1/speed seconds after this one
            next_time = max(next_time + 1 / settings["speed"], time.perf_counter() - 1)
            wait = next_time - time.perf_counter()
            if wait > 0:                                # ahead of schedule -> rest
                time.sleep(wait)                        # behind -> no rest, catch up


# ---------- Waiter 2: PeriodicThread ----------
def periodic_thread(db, hour_seconds):
    conn = mysql.connector.connect(**db)          # this waiter's own phone
    cur = conn.cursor(dictionary=True)            # rows come back as {column: value}
    for hour in range(N_GROUPS):
        if stop_event.is_set():
            break
        # 1. take this hour's group (only if not released before)
        cur.execute(
            "SELECT transaction_id, customer_id, product_id, quantity, unit_price, "
            "event_time, sales_mode FROM periodic_sales_data "
            "WHERE release_hour = %s AND released = 0", (hour,))
        group = cur.fetchall()
        # 2. mark it released so it is never taken twice
        cur.execute("UPDATE periodic_sales_data SET released = 1 "
                    "WHERE release_hour = %s", (hour,))
        conn.commit()
        # 3. bring the tray to the kitchen
        with buffer_lock:
            periodic_lane.extend(group)
        print(f"[Periodic] hour {hour}: released {len(group)} store sales")
        stop_event.wait(hour_seconds)             # sleep until the next hour
    conn.close()


def ask_db():
    """Ask for the connection details at startup (PDF section 6)."""
    return {
        "host": input("Host [localhost]: ") or "localhost",
        "port": int(input("Port [3306]: ") or 3306),
        "database": input("Database [retail_dw]: ") or "retail_dw",
        "user": input("User [haziq]: ") or "haziq",
        "password": getpass.getpass("Password: "),
    }


# ---------- Test: both waiters for 10 seconds, 1 hour = 3 seconds ----------
if __name__ == "__main__":
    db = ask_db()

    # fresh run: mark every group as not released yet
    conn = mysql.connector.connect(**db)
    conn.cursor().execute("UPDATE periodic_sales_data SET released = 0")
    conn.commit()
    conn.close()

    TEST_HOUR = 3
    print("Peak:", PEAK_SPEED, "/s | Non-peak:", NONPEAK_SPEED, "/s | 1 hour =", TEST_HOUR, "s (test)")
    threading.Thread(target=online_thread, args=("Data/online_sales_stream.csv",), daemon=True).start()
    threading.Thread(target=periodic_thread, args=(db, TEST_HOUR), daemon=True).start()

    for second in range(1, 11):
        time.sleep(1)
        print(f"After {second:2}s: online on counter = {len(stream_buffer):4} | "
              f"store sales waiting = {len(periodic_lane)}")
    stop_event.set()
    print("Stopped.")
