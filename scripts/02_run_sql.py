"""Step 2 - Run every query in sql/analysis_queries.sql and export results to CSV."""
import re
import sqlite3

import pandas as pd

from config import DB_PATH, SQL_FILE, SQL_RESULTS, make_dirs


def main():
    if not DB_PATH.exists():
        raise SystemExit("data/olist.db not found. Run scripts/01_load_to_sqlite.py first.")
    make_dirs()
    # the part before the first "-- name:" creates the views; each named block is one query
    setup, *blocks = re.split(r"^-- name:\s*", SQL_FILE.read_text(encoding="utf-8"), flags=re.M)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(setup)
        for block in blocks:
            name, query = block.split("\n", 1)
            df = pd.read_sql_query(query, con)
            df.to_csv(SQL_RESULTS / f"{name.strip()}.csv", index=False)
            print(f"\n=== {name.strip()} ({len(df)} rows) ===")
            print(df.head(8).to_string(index=False))
    print(f"\nAll results saved in {SQL_RESULTS}")


if __name__ == "__main__":
    main()
