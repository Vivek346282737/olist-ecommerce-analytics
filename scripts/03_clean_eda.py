"""Step 3 - Data cleaning, master tables for Tableau, and EDA charts (Pandas + Seaborn)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import (DATE_COLS, FIGURES, OUTPUTS, PROCESSED, RAW, STATE_NAMES, TABLES,
                    ZIP_DTYPES, check_raw_files, make_dirs)

sns.set_theme(style="whitegrid")


def read(table):
    df = pd.read_csv(RAW / TABLES[table], encoding="utf-8-sig", dtype=ZIP_DTYPES)
    for col in DATE_COLS.get(table, []):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def quality_report(tables):
    rows = []
    for name, df in tables.items():
        nulls = df.isna().sum()
        rows.append({
            "table": name,
            "rows": len(df),
            "columns": df.shape[1],
            "duplicate_rows": int(df.duplicated().sum()),
            "null_cells": int(nulls.sum()),
            "most_null_column": nulls.idxmax() if nulls.max() > 0 else "",
            "most_null_count": int(nulls.max()),
        })
    return pd.DataFrame(rows)


def build_masters(t):
    orders = t["orders"].copy()
    # a delivery date before the purchase date is a data error
    bad = orders["order_delivered_customer_date"] < orders["order_purchase_timestamp"]
    orders.loc[bad, "order_delivered_customer_date"] = pd.NaT

    delivered = orders["order_delivered_customer_date"]
    orders["delivery_days"] = (delivered - orders["order_purchase_timestamp"]).dt.days
    orders["delay_days"] = (delivered - orders["order_estimated_delivery_date"]).dt.days
    orders["delivery_status"] = "On Time"
    orders.loc[delivered > orders["order_estimated_delivery_date"], "delivery_status"] = "Late"
    orders.loc[delivered.isna(), "delivery_status"] = "Not Delivered"
    orders["order_date"] = orders["order_purchase_timestamp"].dt.date
    orders["order_month"] = orders["order_purchase_timestamp"].dt.strftime("%Y-%m")
    orders["order_year"] = orders["order_purchase_timestamp"].dt.year
    orders["order_weekday"] = orders["order_purchase_timestamp"].dt.day_name()

    customers = t["customers"].copy()
    customers["customer_state_name"] = customers["customer_state"].map(STATE_NAMES)

    # one row per order for reviews and payments (an order can have several of each)
    reviews = t["reviews"].groupby("order_id", as_index=False)["review_score"].mean()
    pay = t["payments"]
    main_pay = pay.sort_values("payment_value").groupby("order_id").tail(1)[["order_id", "payment_type"]]
    pay_agg = pay.groupby("order_id", as_index=False).agg(
        payment_value=("payment_value", "sum"),
        payment_installments=("payment_installments", "max"),
    ).merge(main_pay, on="order_id")

    products = t["products"].merge(t["category_translation"], on="product_category_name", how="left")
    products["category"] = (products["product_category_name_english"]
                            .fillna(products["product_category_name"]).fillna("unknown"))

    order_cols = ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_date",
                  "order_month", "order_year", "order_weekday", "order_delivered_customer_date",
                  "order_estimated_delivery_date", "delivery_days", "delay_days", "delivery_status"]
    cust_cols = ["customer_id", "customer_unique_id", "customer_city", "customer_state", "customer_state_name"]

    items = (t["order_items"]
             .merge(orders[order_cols], on="order_id", how="inner")
             .merge(customers[cust_cols], on="customer_id", how="left")
             .merge(products[["product_id", "category"]], on="product_id", how="left")
             .merge(t["sellers"][["seller_id", "seller_city", "seller_state"]], on="seller_id", how="left"))
    items["category"] = items["category"].fillna("unknown")
    items = items.drop(columns=["shipping_limit_date", "customer_id"])

    top_item = items.sort_values("price").groupby("order_id").tail(1)[["order_id", "category"]]
    item_agg = items.groupby("order_id", as_index=False).agg(
        items=("order_item_id", "count"),
        order_value=("price", "sum"),
        freight_value=("freight_value", "sum"),
    ).merge(top_item.rename(columns={"category": "main_category"}), on="order_id")

    order_master = (orders[order_cols]
                    .merge(customers[cust_cols], on="customer_id", how="left")
                    .merge(item_agg, on="order_id", how="left")
                    .merge(reviews, on="order_id", how="left")
                    .merge(pay_agg, on="order_id", how="left")
                    .drop(columns=["customer_id"]))
    return items, order_master


def save_fig(name):
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=150)
    plt.close()


def eda_charts(items, orders):
    delivered_items = items[items["order_status"] == "delivered"]

    monthly = delivered_items.groupby("order_month")["price"].sum()
    plt.figure(figsize=(11, 4.5))
    monthly.plot(marker="o")
    plt.title("Monthly revenue (delivered orders)")
    plt.xlabel("Month")
    plt.ylabel("Revenue (BRL)")
    save_fig("01_monthly_revenue.png")

    top_cat = delivered_items.groupby("category")["price"].sum().nlargest(10).sort_values()
    plt.figure(figsize=(9, 5))
    top_cat.plot(kind="barh")
    plt.title("Top 10 categories by revenue")
    plt.xlabel("Revenue (BRL)")
    plt.ylabel("")
    save_fig("02_top_categories.png")

    plt.figure(figsize=(7, 4.5))
    sns.countplot(x=orders["review_score"].dropna().round().astype(int))
    plt.title("Review score distribution")
    plt.xlabel("Review score")
    plt.ylabel("Orders")
    save_fig("03_review_scores.png")

    plt.figure(figsize=(9, 4.5))
    sns.histplot(orders["delivery_days"].dropna().clip(0, 60), bins=60)
    plt.title("Delivery time in days (capped at 60)")
    plt.xlabel("Days from purchase to delivery")
    save_fig("04_delivery_days.png")

    done = orders[orders["delivery_status"] != "Not Delivered"]
    plt.figure(figsize=(6, 4.5))
    sns.barplot(data=done, x="delivery_status", y="review_score", order=["On Time", "Late"])
    plt.title("Average review score: on time vs late")
    plt.xlabel("")
    plt.ylabel("Average review score")
    save_fig("05_review_by_delivery_status.png")


def main():
    check_raw_files()
    make_dirs()
    tables = {name: read(name) for name in TABLES if name != "geolocation"}

    report = quality_report(tables)
    report.to_csv(OUTPUTS / "data_quality_report.csv", index=False)
    print("Data quality report (before cleaning):")
    print(report.to_string(index=False))

    tables = {name: df.drop_duplicates() for name, df in tables.items()}
    items, orders = build_masters(tables)
    items.to_csv(PROCESSED / "order_items_master.csv", index=False)
    orders.to_csv(PROCESSED / "orders_master.csv", index=False)
    print(f"\norder_items_master.csv  {len(items):,} rows")
    print(f"orders_master.csv       {len(orders):,} rows")

    eda_charts(items, orders)
    print(f"Charts saved in {FIGURES}")


if __name__ == "__main__":
    main()
