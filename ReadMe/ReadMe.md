# ReadMe: Near-Real-Time and Periodic Data Warehouse for a Retail Chain

Haziq Mubashir, 23i-2579, DS-7B
DS3003 & DS3004 Data Warehousing & Business Intelligence, Fall 2026

## 1. Requirements

- MySQL 8 (Server and Workbench)
- Python 3.10 or later
- Python packages: `pip install pandas openpyxl mysql-connector-python`

## 2. Folders

| Folder | Contents |
|---|---|
| Create-DW | `retail_dw.sql`: creates the star schema and the working tables |
| Mesh-Join | `dataprep.py`, `meshjoin.py`, `loader.py`, `main.py` |
| Queries-DW | `Queries.sql`: the 20 OLAP queries and the view |
| Data | `online_sales_stream.csv`, `customer_master_data.csv`, `product_master_data.csv`, `data_note.txt` |
| Project-Report | the project report |
| ReadMe | this file |

Run every command below from the top project folder (the one that contains these folders).

## 3. Create the database

1. Open `Create-DW/retail_dw.sql` in MySQL Workbench.
2. Run the whole script.

The script creates the database `retail_dw`, drops the view `STORE_QUARTERLY_SALES` and any old tables, then creates the 6 star schema tables and the 4 working tables (`customer_md`, `product_md`, `periodic_sales_data`, `shed_table`).

## 4. Prepare the data

1. Download `Online Retail.xlsx` from https://archive.ics.uci.edu/dataset/352/online+retail and put it in the `Data` folder.
2. Run: `python Mesh-Join/dataprep.py`
3. Enter the host, port, database, user and password when asked. The password is never stored in the code.

This step cleans the file and prints the counts before and after, applies the MD5 sales_mode and store rules, writes the two Master Data CSV files and `online_sales_stream.csv` into `Data`, loads the Master Data into MySQL, and loads the periodic sales into `periodic_sales_data` in 48 groups.

## 5. Start the program

Run: `python Mesh-Join/main.py`

The program asks for the host, port, database name, user name, password, and the path of the online file. It then prints the stream arrival mode, both speeds, how many seconds make one hour, and the stream buffer limit, and starts the three threads (OnlineThread, PeriodicThread, MeshJoinThread).

Each start is a fresh run: the fact and dimension tables and `shed_table` are emptied, and every periodic group is marked as not released.

Optional settings at start:

| Option | Default | Meaning |
|---|---|---|
| `--peak-speed` | 80 | online transactions per second in peak time |
| `--nonpeak-speed` | 10 | online transactions per second in non-peak time |
| `--hour-seconds` | 60 | real seconds in one simulated hour |
| `--start` | peak | arrival mode at start (`peak` or `non-peak`) |

At the default speeds a full load takes a long time (278,740 online transactions at 80 per second is about 58 minutes). To load the whole DW quickly before running the queries:

`python Mesh-Join/main.py --start non-peak --nonpeak-speed 3000 --hour-seconds 2`

Wait for the lines `[Online] the whole online file has been streamed` and `[Periodic] all 48 groups released`, type `status` until it shows `in H=0` and `loaded into DW=397884`, then type `quit`.

## 6. Commands while the program is running

Type a command and press Enter. Every command prints a status line.

| Command | Effect |
|---|---|
| `online` | online form only, periodic groups are not extracted |
| `periodic` | periodic groups only, the stream reader is paused |
| `both` | both forms, online transactions are taken first |
| `peak` | fast speed, shedding periodic transactions to disk is allowed |
| `non-peak` | slow speed, shed transactions are read back and processed |
| `status` | mode, speed, stream buffer count, transactions in H, transactions on the shed disk, transactions loaded |
| `set-peak N` | change the peak speed to N per second |
| `set-nonpeak N` | change the non-peak speed to N per second |
| `quit` | stop the threads and close the program |

## 7. Run the queries

1. Make sure the DW is fully loaded (section 5).
2. Open `Queries-DW/Queries.sql` in MySQL Workbench and run it.

The loaded year used in the queries is 2011. The latest six months are July 2011 to December 2011. Q16 compares product pairs in every cart and can take longer than the others.

## 8. Which load was used

The bonus was not implemented. Online (Live) join results are inserted directly into the fact table. Periodic results are loaded after they have been joined.

## 9. Settings used

- Master Data partition: 500 tuples, read from the database on each iteration
- Stream chunk w: 500 transactions
- Stream buffer limit: 1,000 transactions (periodic transactions may use at most 500 of these, so online transactions always have room)
- Peak 80 per second, non-peak 10 per second
- One simulated hour: 60 seconds
- Periodic groups: 48
- Priority: online first, then periodic, then shed

## 10. Dataset citation

Chen, D., Sain, S. L., and Guo, K. Online Retail. UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/352/online+retail

Downloaded on 7 November 2026.
