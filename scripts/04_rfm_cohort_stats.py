"""Step 4 - RFM segmentation, cohort retention, hypothesis test and insights summary."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from config import FIGURES, OUTPUTS, PROCESSED, make_dirs


def build_rfm(orders):
    snapshot = orders["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
    rfm = orders.groupby("customer_unique_id").agg(
        last_purchase=("order_purchase_timestamp", "max"),
        frequency=("order_id", "nunique"),
        monetary=("order_value", "sum"),
    )
    rfm["recency_days"] = (snapshot - rfm["last_purchase"]).dt.days
    rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    # most customers order once, so quantiles are useless for frequency - use fixed bins
    rfm["f_score"] = pd.cut(rfm["frequency"], [0, 1, 2, 3, 5, np.inf], labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

    r, f, m = rfm["r_score"], rfm["f_score"], rfm["m_score"]
    rfm["segment"] = np.select(
        [
            (r >= 4) & (f >= 2) & (m >= 4),
            f >= 2,
            (r <= 2) & (m >= 4),
            (r >= 3) & (m >= 4),
            r >= 4,
            r <= 2,
        ],
        ["Champions", "Loyal", "At Risk (High Value)", "High Value New", "Recent", "Hibernating"],
        default="Need Attention",
    )
    return rfm.reset_index().drop(columns="last_purchase")


def build_cohorts(orders):
    df = orders[["customer_unique_id", "order_purchase_timestamp"]].copy()
    df["order_period"] = df["order_purchase_timestamp"].dt.to_period("M")
    df["cohort"] = df.groupby("customer_unique_id")["order_period"].transform("min")
    df["month_index"] = (df["order_period"] - df["cohort"]).apply(lambda d: d.n)
    counts = (df.groupby(["cohort", "month_index"])["customer_unique_id"].nunique()
              .rename("customers").reset_index())
    size = counts[counts["month_index"] == 0].set_index("cohort")["customers"]
    counts["cohort_size"] = counts["cohort"].map(size)
    counts["retention_pct"] = (100 * counts["customers"] / counts["cohort_size"]).round(2)
    counts["cohort_month"] = counts["cohort"].astype(str)
    return counts[["cohort_month", "month_index", "cohort_size", "customers", "retention_pct"]]


def cohort_heatmap(cohorts):
    pivot = cohorts[cohorts["month_index"].between(1, 12)].pivot(
        index="cohort_month", columns="month_index", values="retention_pct")
    plt.figure(figsize=(11, 7))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="Blues", cbar_kws={"label": "Retention %"})
    plt.title("Cohort retention % (months after first purchase)")
    plt.xlabel("Months since first purchase")
    plt.ylabel("First purchase month")
    plt.tight_layout()
    plt.savefig(FIGURES / "06_cohort_retention.png", dpi=150)
    plt.close()


def late_delivery_test(orders):
    done = orders[(orders["delivery_status"] != "Not Delivered") & orders["review_score"].notna()]
    late = done.loc[done["delivery_status"] == "Late", "review_score"]
    on_time = done.loc[done["delivery_status"] == "On Time", "review_score"]
    t_stat, t_p = stats.ttest_ind(on_time, late, equal_var=False)
    _, mw_p = stats.mannwhitneyu(on_time, late, alternative="two-sided")
    rho, rho_p = stats.spearmanr(done["delivery_days"], done["review_score"])
    return {
        "on_time_orders": len(on_time), "late_orders": len(late),
        "on_time_mean": on_time.mean(), "late_mean": late.mean(),
        "t_stat": t_stat, "t_p": t_p, "mw_p": mw_p, "rho": rho, "rho_p": rho_p,
    }


def main():
    path = PROCESSED / "orders_master.csv"
    if not path.exists():
        raise SystemExit("orders_master.csv not found. Run scripts/03_clean_eda.py first.")
    make_dirs()
    orders = pd.read_csv(path, parse_dates=["order_purchase_timestamp"])
    delivered = orders[(orders["order_status"] == "delivered") & orders["order_value"].notna()]

    rfm = build_rfm(delivered)
    rfm.to_csv(PROCESSED / "rfm_customers.csv", index=False)
    cohorts = build_cohorts(delivered)
    cohorts.to_csv(PROCESSED / "cohort_retention.csv", index=False)
    cohort_heatmap(cohorts)
    test = late_delivery_test(orders)

    revenue = delivered["order_value"].sum()
    n_orders = delivered["order_id"].nunique()
    n_customers = len(rfm)
    repeat_rate = 100 * (rfm["frequency"] > 1).mean()
    top20 = rfm["monetary"].nlargest(max(1, int(0.2 * n_customers))).sum()
    done = orders[orders["delivery_status"] != "Not Delivered"]
    late_pct = 100 * (done["delivery_status"] == "Late").mean()
    seg = rfm.groupby("segment").agg(customers=("customer_unique_id", "count"),
                                     revenue=("monetary", "sum")).sort_values("revenue", ascending=False)
    seg["revenue_share_pct"] = (100 * seg["revenue"] / revenue).round(1)
    items = pd.read_csv(PROCESSED / "order_items_master.csv", usecols=["order_status", "category", "price"])
    top_cat = items[items["order_status"] == "delivered"].groupby("category")["price"].sum().nlargest(5)
    top_state = delivered.groupby("customer_state")["order_value"].sum().nlargest(5)
    m1 = cohorts[cohorts["month_index"] == 1]
    month1_retention = 100 * m1["customers"].sum() / m1["cohort_size"].sum() if len(m1) else float("nan")

    lines = [
        "INSIGHTS SUMMARY (use these exact numbers in resume / README / interview)",
        "=" * 72,
        f"Period               : {orders['order_month'].min()} to {orders['order_month'].max()}",
        f"Total revenue (BRL)  : {revenue:,.0f}",
        f"Delivered orders     : {n_orders:,}",
        f"Unique customers     : {n_customers:,}",
        f"Average order value  : {revenue / n_orders:,.2f}",
        f"Repeat customer rate : {repeat_rate:.2f}%",
        f"Top 20% customers    : {100 * top20 / revenue:.1f}% of revenue",
        f"Month-1 retention    : {month1_retention:.2f}%",
        f"Late delivery rate   : {late_pct:.2f}%",
        "",
        "Late delivery vs review score",
        f"  On-time avg review : {test['on_time_mean']:.2f}  (n={test['on_time_orders']:,})",
        f"  Late avg review    : {test['late_mean']:.2f}  (n={test['late_orders']:,})",
        f"  Difference         : {test['on_time_mean'] - test['late_mean']:.2f} points",
        f"  Welch t-test       : t={test['t_stat']:.2f}, p={test['t_p']:.3g}",
        f"  Mann-Whitney U     : p={test['mw_p']:.3g}",
        f"  Spearman (delivery days vs review): rho={test['rho']:.3f}, p={test['rho_p']:.3g}",
        "",
        "Top 5 categories by revenue",
        *[f"  {k:35s} {v:>14,.0f}" for k, v in top_cat.items()],
        "",
        "Top 5 states by revenue",
        *[f"  {k:35s} {v:>14,.0f}" for k, v in top_state.items()],
        "",
        "RFM segments",
        seg.round(0).to_string(),
    ]
    text = "\n".join(lines)
    (OUTPUTS / "insights_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
