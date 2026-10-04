"""Step 1 - Load the 9 raw Olist CSVs into a SQLite database (data/olist.db)."""
import sqlite3

import pandas as pd

from config import DATE_COLS, DB_PATH, RAW, TABLES, ZIP_DTYPES, check_raw_files, make_dirs

INDEXES = [
    ("orders", "order_id"),
    ("orders", "customer_id"),
    ("order_items", "order_id"),
    ("order_items", "product_id"),
    ("order_items", "seller_id"),
    ("payments", "order_id"),
    ("reviews", "order_id"),
    ("customers", "customer_id"),
    ("customers", "customer_unique_id"),
    ("products", "product_id"),
    ("sellers", "seller_id"),
]


def main():
    check_raw_files()
    make_dirs()
    with sqlite3.connect(DB_PATH) as con:
        for table, fname in TABLES.items():
            df = pd.read_csv(RAW / fname, encoding="utf-8-sig", dtype=ZIP_DTYPES)
            # store dates as ISO text so SQLite date functions work on them
            for col in DATE_COLS.get(table, []):
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
            df.to_sql(table, con, if_exists="replace", index=False)
            print(f"{table:22s} {len(df):>9,} rows")
        for table, col in INDEXES:
            con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})")
    print(f"\nDatabase ready: {DB_PATH}")


if __name__ == "__main__":
    main()
