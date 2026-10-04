"""Step 6 - Linear regression: which factors drive the review score?"""
import numpy as np
import pandas as pd
from scipy import stats

from config import OUTPUTS, PROCESSED, make_dirs

FEATURES = ["delivery_days", "is_late", "order_value", "freight_value", "items"]


def fit_regression(orders):
    """OLS with NumPy: coefficients, p-values and R-squared."""
    df = orders[orders["delivery_status"] != "Not Delivered"].copy()
    df["is_late"] = (df["delivery_status"] == "Late").astype(int)
    df = df.dropna(subset=["review_score"] + FEATURES)
    X = np.column_stack([np.ones(len(df)), df[FEATURES].to_numpy(float)])
    y = df["review_score"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    se = np.sqrt(np.diag(resid @ resid / dof * np.linalg.inv(X.T @ X)))
    p = 2 * stats.t.sf(np.abs(beta / se), dof)
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    coef = pd.DataFrame({"coef": beta, "std_err": se, "p_value": p}, index=["intercept"] + FEATURES).round(4)
    return coef, r2, len(y)


def main():
    make_dirs()
    orders = pd.read_csv(PROCESSED / "orders_master.csv")
    coef, r2, n_obs = fit_regression(orders)
    text = "\n".join([
        "REGRESSION: what drives review score (OLS)",
        "=" * 60,
        f"Observations : {n_obs:,}",
        f"R-squared    : {r2:.3f}",
        coef.to_string(),
    ])
    (OUTPUTS / "regression_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
