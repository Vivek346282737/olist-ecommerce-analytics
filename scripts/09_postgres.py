"""Step 9 - Load the dataset into PostgreSQL and run the analysis queries there.

Uses the PostgreSQL command-line tools (initdb, pg_ctl, psql). Set PG_BIN to the folder that holds them.
The SQLite queries are translated to PostgreSQL syntax and saved as sql/analysis_queries_postgres.sql,
then the PostgreSQL results are compared with the SQLite results.
"""
import os
import re
import subprocess
from pathlib import Path

import pandas as pd

from config import OUTPUTS, RAW, ROOT, SQL_FILE, SQL_RESULTS, TABLES, check_raw_files

PG_HOME = Path(os.environ.get("PG_HOME", Path.home() / "pgsql-portable"))
PG_BIN = Path(os.environ.get("PG_BIN", PG_HOME / "pgsql" / "bin"))
PG_DATA = PG_HOME / "data"
PORT, DB, USER = "5433", "olist", "postgres"
SCHEMA = ROOT / "sql" / "postgres_schema.sql"
PG_SQL = ROOT / "sql" / "analysis_queries_postgres.sql"
PG_RESULTS = OUTPUTS / "postgres_results"
LOAD_ORDER = ["customers", "sellers", "products", "category_translation", "orders", "order_items", "payments", "reviews"]

# SQLite expression -> PostgreSQL expression
TRANSLATIONS = [
    ("-- Written for SQLite. In MySQL replace strftime('%Y-%m', x) with DATE_FORMAT(x, '%Y-%m')\n"
     "-- and julianday(a) - julianday(b) with DATEDIFF(a, b).",
     "-- PostgreSQL version (generated from analysis_queries.sql by scripts/09_postgres.py)."),
    ("strftime('%Y-%m', o.order_purchase_timestamp)", "to_char(o.order_purchase_timestamp, 'YYYY-MM')"),
    ("ROUND(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp), 1)",
     "ROUND(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400, 1)"),
    ("CAST(julianday((SELECT max_ts FROM last_date)) - julianday(MAX(order_purchase_timestamp)) AS INTEGER)",
     "((SELECT max_ts FROM last_date)::date - MAX(order_purchase_timestamp)::date)"),
]


def run(tool, *args, check=True):
    return subprocess.run([str(PG_BIN / f"{tool}.exe"), *args], capture_output=True, text=True, check=check)


def psql(*args):
    result = run("psql", "-p", PORT, "-U", USER, "-d", DB, "-v", "ON_ERROR_STOP=1", "-q", *args, check=False)
    if result.returncode != 0:
        raise SystemExit(f"psql failed:\n{result.stderr}")
    return result.stdout


def start_server():
    if not PG_DATA.exists():
        run("initdb", "-D", str(PG_DATA), "-U", USER, "-A", "trust", "-E", "UTF8", "--locale=C")
    if run("pg_ctl", "-D", str(PG_DATA), "status", check=False).returncode != 0:
        subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(PG_DATA), "-o", f"-p {PORT}", "-l", str(PG_HOME / "server.log"),
                        "-w", "start"], check=True, stdout=subprocess.DEVNULL)
    run("createdb", "-p", PORT, "-U", USER, DB, check=False)  # fails harmlessly if it already exists


def translate_queries():
    sql = SQL_FILE.read_text(encoding="utf-8")
    for old, new in TRANSLATIONS:
        if old not in sql:
            raise SystemExit(f"Expected SQLite expression not found: {old[:50]}")
        sql = sql.replace(old, new)
    PG_SQL.write_text(sql, encoding="utf-8")
    return sql


def main():
    check_raw_files()
    PG_RESULTS.mkdir(parents=True, exist_ok=True)
    start_server()
    try:
        psql("-f", str(SCHEMA))
        for table in LOAD_ORDER:
            csv_path = (RAW / TABLES[table]).as_posix()
            psql("-c", f"\\copy {table} FROM '{csv_path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')")
            print(f"{table:22s} {psql('-At', '-c', f'SELECT COUNT(*) FROM {table}').strip():>9} rows")

        setup, *blocks = re.split(r"^-- name:\s*", translate_queries(), flags=re.M)
        psql("-c", setup)
        print()
        for block in blocks:
            name, query = block.split("\n", 1)
            name = name.strip()
            query = " ".join(line for line in query.splitlines() if not line.strip().startswith("--")).strip().rstrip(";")
            out = (PG_RESULTS / f"{name}.csv").as_posix()
            psql("-c", f"\\copy ({query}) TO '{out}' WITH (FORMAT csv, HEADER true)")
            pg, lite = pd.read_csv(PG_RESULTS / f"{name}.csv"), pd.read_csv(SQL_RESULTS / f"{name}.csv")
            a, b = pg.select_dtypes("number").sum().sum(), lite.select_dtypes("number").sum().sum()
            same = pg.shape == lite.shape and abs(a - b) <= 0.01 * abs(b)  # NTILE breaks ties differently per engine
            print(f"{name:32s} {len(pg):>3} rows   matches SQLite: {'yes' if same else 'NO'}")
        print(f"\nPostgreSQL version: {psql('-At', '-c', 'SHOW server_version').strip()}")
    finally:
        run("pg_ctl", "-D", str(PG_DATA), "-m", "fast", "stop", check=False)


if __name__ == "__main__":
    main()
