"""
Main program (PDF sections 4.3, 4.4, 6):
  OnlineThread   -> puts online sales on the counter at 80/s or 10/s
  PeriodicThread -> every simulated hour, releases one store group
  MeshJoinThread -> MESHJOIN + load shedding + loading into the DW
"""
import argparse
import csv
import getpass
import threading
import time
from collections import deque
from datetime import datetime

import mysql.connector

from meshjoin import MeshJoin, CHUNK_SIZE
from loader import DWLoader, reset_dw

# ---------- Settings (PDF section 12) ----------
BUFFER_LIMIT = 1000      # counter (stream buffer) holds max 1000 sales
STORE_MAX = 500          # store sales may use at most half -> online always has room
PEAK_SPEED = 80          # online sales per second in peak time
NONPEAK_SPEED = 10       # online sales per second in non-peak time
HOUR_SECONDS = 60        # one simulated hour = 60 real seconds
N_GROUPS = 48            # periodic groups, one per hour

# ---------- Shared things (all threads use these) ----------
online_lane = deque()                # online sales on the counter
store_lane = deque()                 # store sales on the counter
lock = threading.Lock()              # only one hand on the counter at a time
settings = {"peak": True, "speed": PEAK_SPEED, "mode": "both"}
stats = {"hour": -1, "shed_to_disk": 0, "shed_back": 0, "loaded": 0, "in_H": 0}
stop_event = threading.Event()


def counter_size():                  # call only while holding the lock
    return len(online_lane) + len(store_lane)


def connect(db):
    return mysql.connector.connect(**db)


# ---------- Waiter 1: OnlineThread ----------
def online_thread(csv_path):
    next_time = time.perf_counter()
    with open(csv_path) as f:
        for sale in csv.DictReader(f):
            # wait while paused ("periodic" mode) or while the counter is full
            while not stop_event.is_set():
                if settings["mode"] != "periodic":
                    with lock:
                        if counter_size() < BUFFER_LIMIT:
                            online_lane.append(sale)
                            break
                time.sleep(0.01)
            if stop_event.is_set():
                return
            next_time = max(next_time + 1 / settings["speed"], time.perf_counter() - 1)
            wait = next_time - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
    print("[Online] the whole online file has been streamed")


# ---------- Load shedding: write store sales to disk ----------
def shed(cur, conn, sales):
    now = datetime.now()
    cur.executemany(
        "INSERT INTO shed_table (transaction_id, customer_id, product_id, quantity, "
        "unit_price, event_time, sales_mode, shed_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        [(s["transaction_id"], s["customer_id"], s["product_id"], s["quantity"],
          s["unit_price"], s["event_time"], s["sales_mode"], now) for s in sales])
    conn.commit()
    stats["shed_to_disk"] += len(sales)


def place_group(group, cur, conn):
    """Put a store group on the counter. What doesn't fit: peak -> shed, non-peak -> wait."""
    to_shed = []
    for sale in group:
        while not stop_event.is_set():
            with lock:
                if counter_size() < BUFFER_LIMIT and len(store_lane) < STORE_MAX:
                    store_lane.append(sale)
                    break
            if settings["peak"]:                 # can't cope -> shed to disk
                to_shed.append(sale)
                break
            time.sleep(0.01)                     # quiet time -> just wait for room
    if to_shed:
        shed(cur, conn, to_shed)
        print(f"[Shed] {len(to_shed)} store sales moved to shed_table (peak)")


# ---------- Waiter 2: PeriodicThread ----------
def periodic_thread(db, hour_seconds):
    conn = connect(db)
    cur = conn.cursor(dictionary=True)
    start = time.perf_counter()
    tick = 0                                       # simulated hours passed
    hour = 0                                       # next group to release
    while hour < N_GROUPS and not stop_event.is_set():
        if tick > 0:                               # group 0 goes out right away
            wait = start + tick * hour_seconds - time.perf_counter()
            if wait > 0 and stop_event.wait(wait):
                break
        tick += 1
        if settings["mode"] == "online":           # online only: no extraction
            continue
        cur.execute(
            "SELECT transaction_id, customer_id, product_id, quantity, unit_price, "
            "event_time, sales_mode FROM periodic_sales_data "
            "WHERE release_hour = %s AND released = 0", (hour,))
        group = cur.fetchall()
        cur.execute("UPDATE periodic_sales_data SET released = 1 WHERE release_hour = %s", (hour,))
        conn.commit()
        stats["hour"] = hour
        print(f"[Periodic] hour {hour}: released {len(group)} store sales")
        hour += 1
        place_group(group, cur, conn)
    if hour == N_GROUPS:
        print(f"[Periodic] all {N_GROUPS} groups released")
    conn.close()


# ---------- Bring shed sales back (only when quiet) ----------
def read_back_shed(cur, conn, n):
    cur.execute("SELECT id, transaction_id, customer_id, product_id, quantity, unit_price, "
                "event_time, sales_mode FROM shed_table ORDER BY id LIMIT %s", (n,))
    rows = cur.fetchall()
    if rows:
        ids = [r.pop("id") for r in rows]
        cur.execute(f"DELETE FROM shed_table WHERE id IN ({','.join(['%s'] * len(ids))})", ids)
        conn.commit()
        for r in rows:
            r["processing_mode"] = "SHED"
        stats["shed_back"] += len(rows)
    return rows


# ---------- The chef: MeshJoinThread ----------
def meshjoin_thread(db):
    conn = connect(db)
    mj = MeshJoin(conn.cursor())
    loader = DWLoader(conn)
    shed_cur = conn.cursor(dictionary=True)
    while not stop_event.is_set():
        # priority: 1st online, 2nd store, 3rd shed (shed only in non-peak)
        chunk = []
        with lock:
            while len(chunk) < CHUNK_SIZE and online_lane:
                chunk.append(online_lane.popleft())
            while len(chunk) < CHUNK_SIZE and store_lane:
                chunk.append(store_lane.popleft())
        if not settings["peak"] and len(chunk) < CHUNK_SIZE:
            chunk += read_back_shed(shed_cur, conn, CHUNK_SIZE - len(chunk))

        if not chunk and not mj.queue:             # nothing to do -> rest a moment
            time.sleep(0.1)
            continue

        finished, _ = mj.run_round(chunk)
        if finished:
            stats["loaded"] += loader.load(finished)
        stats["in_H"] = mj.sales_in_H()
    conn.close()


def ask_db():
    """Connection details are asked at startup, never written in the code (PDF section 6)."""
    return {
        "host": input("Host [localhost]: ") or "localhost",
        "port": int(input("Port [3306]: ") or 3306),
        "database": input("Database [retail_dw]: ") or "retail_dw",
        "user": input("User [haziq]: ") or "haziq",
        "password": getpass.getpass("Password: "),
    }


def print_status():
    with lock:
        on, st = len(online_lane), len(store_lane)
    print(f"[Status] mode={settings['mode']} | {'peak' if settings['peak'] else 'non-peak'} "
          f"{settings['speed']}/s | counter={on + st} (online {on}, store {st}) | "
          f"in H={stats['in_H']} | on shed disk={stats['shed_to_disk'] - stats['shed_back']} | "
          f"loaded into DW={stats['loaded']}")


def set_peak(on):
    settings["peak"] = on
    settings["speed"] = PEAK_SPEED if on else NONPEAK_SPEED


HELP = ("Commands: online | periodic | both | peak | non-peak | status | "
        "set-peak N | set-nonpeak N | quit")


# ---------- Start the program ----------
if __name__ == "__main__":
    # settings the user can choose when starting (PDF sections 5.2 and 12)
    ap = argparse.ArgumentParser(description="MESHJOIN near-real-time DW loader")
    ap.add_argument("--peak-speed", type=int, default=80, help="online sales/s in peak time")
    ap.add_argument("--nonpeak-speed", type=int, default=10, help="online sales/s in non-peak time")
    ap.add_argument("--hour-seconds", type=float, default=60, help="real seconds in one simulated hour")
    ap.add_argument("--start", choices=["peak", "non-peak"], default="peak", help="arrival mode at start")
    args = ap.parse_args()
    PEAK_SPEED, NONPEAK_SPEED = args.peak_speed, args.nonpeak_speed
    set_peak(args.start == "peak")

    # connection details + online file, asked at execution time (PDF section 6)
    db = ask_db()
    csv_path = input("Online file [Data/online_sales_stream.csv]: ") or "Data/online_sales_stream.csv"

    # fresh run: empty the DW and the shed table, mark every group as not released
    conn = connect(db)
    reset_dw(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM shed_table")
    cur.execute("UPDATE periodic_sales_data SET released = 0")
    conn.commit()
    conn.close()

    # printed before the threads start (PDF section 6)
    print(f"Stream arrival mode: {args.start} | peak = {PEAK_SPEED}/s, non-peak = {NONPEAK_SPEED}/s")
    print(f"One hour = {args.hour_seconds} seconds | stream buffer limit = {BUFFER_LIMIT}")
    print(HELP)

    threads = [threading.Thread(target=online_thread, args=(csv_path,), daemon=True),
               threading.Thread(target=periodic_thread, args=(db, args.hour_seconds), daemon=True),
               threading.Thread(target=meshjoin_thread, args=(db,), daemon=True)]
    for t in threads:
        t.start()

    # the remote control: keep accepting commands until quit (PDF section 6.1)
    while True:
        cmd = input().strip().lower()
        if cmd in ("online", "periodic", "both"):
            settings["mode"] = cmd
        elif cmd == "peak":
            set_peak(True)
        elif cmd == "non-peak":
            set_peak(False)
        elif cmd.startswith("set-peak ") or cmd.startswith("set-nonpeak "):
            name, value = cmd.split()
            if name == "set-peak":
                PEAK_SPEED = int(value)
            else:
                NONPEAK_SPEED = int(value)
            set_peak(settings["peak"])           # apply the new speed now
        elif cmd == "quit":
            break
        elif cmd != "status":
            print(HELP)
            continue
        print_status()                            # every command shows the result

    stop_event.set()
    for t in threads:
        t.join(timeout=5)
    print(f"Stopped. Shed to disk in peak: {stats['shed_to_disk']} | "
          f"shed processed back in non-peak: {stats['shed_back']} | "
          f"loaded into DW: {stats['loaded']}")
