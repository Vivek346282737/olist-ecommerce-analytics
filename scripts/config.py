"""Shared paths and file names for the whole project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
SQL_RESULTS = OUTPUTS / "sql_results"
DB_PATH = ROOT / "data" / "olist.db"
SQL_FILE = ROOT / "sql" / "analysis_queries.sql"
EXCEL_FILE = ROOT / "excel" / "olist_excel_analysis.xlsx"

# table name -> Kaggle CSV file name
TABLES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

DATE_COLS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}

# zip prefixes have leading zeros, so they must stay text
ZIP_DTYPES = {
    "customer_zip_code_prefix": str,
    "seller_zip_code_prefix": str,
    "geolocation_zip_code_prefix": str,
}

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapa", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceara", "DF": "Distrito Federal", "ES": "Espirito Santo", "GO": "Goias",
    "MA": "Maranhao", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Para", "PB": "Paraiba", "PR": "Parana",
    "PE": "Pernambuco", "PI": "Piaui", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondonia",
    "RR": "Roraima", "SC": "Santa Catarina", "SP": "Sao Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}


def check_raw_files():
    """Stop early with a clear message if the Kaggle CSVs are not in data/raw."""
    missing = [f for f in TABLES.values() if not (RAW / f).exists()]
    if missing:
        raise SystemExit(
            f"Missing files in {RAW}:\n  " + "\n  ".join(missing)
            + "\nDownload the Olist dataset from Kaggle and unzip all CSVs into data/raw."
        )


def make_dirs():
    for d in (PROCESSED, OUTPUTS, FIGURES, SQL_RESULTS, EXCEL_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
