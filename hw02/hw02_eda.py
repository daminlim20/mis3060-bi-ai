"""
Script:   hw02_eda.py
Dataset:  data/raw/fact_transactions.csv (Wildcat Capital transaction portfolio)
Author:   Damin Lim
Generated: 2026-09-22

Description:
Exploratory data analysis of Wildcat Capital's fact_transactions dataset.
Validates the dataset's structure, checks for missing values and duplicates,
profiles the amount distribution, groups activity by transaction type, and
examines relationships between shares, price, and amount -- before any of
this data is used in downstream analysis.

Run from the repository root with:
    python hw02/hw02_eda.py
"""

import os

import pandas as pd

DATA_PATH = "data/raw/fact_transactions.csv"
CHARTS_DIR = "hw02/charts"
PROFILE_PATH = "hw02/hw02_profile.txt"
EXPECTED_SHAPE = (298772, 9)


def section(title):
    line = "=" * 70
    return f"\n{line}\n{title}\n{line}"


def main():
    profile_lines = []  # collects the text for items 2-13 -> hw02_profile.txt

    def emit(text=""):
        print(text)
        profile_lines.append(text)

    # ---- 1. Load the dataset --------------------------------------------
    df = pd.read_csv(DATA_PATH)

    # ---- 2. Shape ---------------------------------------------------------
    emit(section("2. DATASET SHAPE"))
    emit(f"Rows: {df.shape[0]:,}  |  Columns: {df.shape[1]}")
    emit(f"Shape: {df.shape}")

    # ---- 3. Column names and data types -----------------------------------
    emit(section("3. COLUMN NAMES AND DATA TYPES"))
    for col, dtype in df.dtypes.items():
        emit(f"{col:<15} {dtype}")

    # ---- 4. Missing values per column --------------------------------------
    emit(section("4. MISSING VALUES PER COLUMN"))
    nulls = df.isnull().sum()
    for col, cnt in nulls.items():
        emit(f"{col:<15} {cnt:,}")

    # ---- 5. Descriptive statistics for numeric columns ---------------------
    emit(section("5. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)"))
    emit(df.describe().to_string())

    # ---- 6. txn_type value counts and percentages ---------------------------
    emit(section("6. TXN_TYPE VALUE COUNTS AND PERCENTAGES"))
    vc = df["txn_type"].value_counts(ascending=False)
    pct = (vc / len(df) * 100).round(2)
    for txn_type in vc.index:
        emit(f"{txn_type:<15} count={vc[txn_type]:>7,}   pct={pct[txn_type]:>6.2f}%")

    # ---- 7. Unique clients, advisors, securities ---------------------------
    emit(section("7. UNIQUE ENTITY COUNTS"))
    emit(f"Unique clients:    {df['client_id'].nunique():,}")
    emit(f"Unique advisors:   {df['advisor_id'].nunique():,}")
    emit(f"Unique securities: {df['security_id'].nunique():,}")

    # ---- 8. txn_date range ---------------------------------------------------
    emit(section("8. TXN_DATE RANGE"))
    emit(f"Earliest txn_date: {df['txn_date'].min()}")
    emit(f"Latest txn_date:   {df['txn_date'].max()}")

    # ---- 9. Duplicate txn_id check --------------------------------------------
    emit(section("9. DUPLICATE TXN_ID CHECK"))
    dup_count = df["txn_id"].duplicated().sum()
    emit(f"Duplicate txn_id count: {dup_count:,}")

    # ---- 10. amount: mean, median, skewness -------------------------------------
    emit(section("10. AMOUNT: MEAN, MEDIAN, SKEWNESS"))
    amount_mean = df["amount"].mean()
    amount_median = df["amount"].median()
    amount_skew = df["amount"].skew()
    emit(f"Mean amount:   ${amount_mean:,.2f}")
    emit(f"Median amount: ${amount_median:,.2f}")
    emit(f"Skewness:      {amount_skew:.2f}")

    # ---- 11. Group by txn_type: count, mean, median amount ----------------------
    emit(section("11. AMOUNT BY TXN_TYPE (sorted by mean amount, descending)"))
    grouped = df.groupby("txn_type")["amount"].agg(count="count", mean="mean", median="median")
    grouped["mean"] = grouped["mean"].round(2)
    grouped["median"] = grouped["median"].round(2)
    grouped = grouped.sort_values("mean", ascending=False)
    grouped_display = grouped.copy()
    grouped_display["mean"] = grouped_display["mean"].map(lambda x: f"{x:,.2f}")
    grouped_display["median"] = grouped_display["median"].map(lambda x: f"{x:,.2f}")
    emit(grouped_display.to_string())

    # ---- 12. Correlation matrix: shares, price, amount ---------------------------
    emit(section("12. CORRELATION MATRIX (shares, price, amount)"))
    corr = df[["shares", "price", "amount"]].corr().round(2)
    emit(corr.map(lambda x: f"{x:.2f}").to_string())

    pairs = []
    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append((cols[i], cols[j], corr.iloc[i, j]))
    pairs_sorted = sorted(pairs, key=lambda p: abs(p[2]), reverse=True)
    emit("\nThree strongest correlations (excluding self-correlation, no repeated pairs):")
    for a, b, val in pairs_sorted[:3]:
        emit(f"  {a} <-> {b}: {val:.2f}")

    # ---- 13. Negative shares by txn_type -------------------------------------------
    emit(section("13. SHARES: MIN, MAX, NEGATIVE COUNT BY TXN_TYPE"))
    shares_stats = df.groupby("txn_type")["shares"].agg(
        min_shares="min",
        max_shares="max",
        negative_count=lambda s: (s < 0).sum(),
    )
    emit(shares_stats.to_string())

    # ---- 14. Shape validation warning -----------------------------------------------
    if df.shape != EXPECTED_SHAPE:
        print(f"\nWARNING: dataset shape {df.shape} does not match the expected shape {EXPECTED_SHAPE}!")
    else:
        print(f"\nShape check passed: dataset matches the expected shape {EXPECTED_SHAPE}.")

    # ---- 15. Charts -------------------------------------------------------------------
    os.makedirs(CHARTS_DIR, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Histogram of amount, with mean/median lines
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["amount"], bins=60, color="#4C72B0", edgecolor="white")
    ax.axvline(amount_mean, color="#C44E52", linestyle="--", linewidth=2,
               label=f"Mean: ${amount_mean:,.2f}")
    ax.axvline(amount_median, color="#55A868", linestyle="--", linewidth=2,
               label=f"Median: ${amount_median:,.2f}")
    ax.set_title("Distribution of Transaction Amount")
    ax.set_xlabel("Amount ($)")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "hist_amount.png"), dpi=150)
    plt.close(fig)

    # Horizontal box plot of amount by txn_type
    fig, ax = plt.subplots(figsize=(10, 6))
    txn_order = df.groupby("txn_type")["amount"].median().sort_values().index
    data_by_type = [df.loc[df["txn_type"] == t, "amount"].dropna() for t in txn_order]
    ax.boxplot(data_by_type, vert=False, tick_labels=list(txn_order))
    ax.set_title("Transaction Amount by Type")
    ax.set_xlabel("Amount ($)")
    ax.set_ylabel("Transaction Type")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "box_amount_by_type.png"), dpi=150)
    plt.close(fig)

    # Scatter of shares vs. amount, colored by txn_type
    fig, ax = plt.subplots(figsize=(10, 6))
    cmap = plt.get_cmap("tab10")
    for i, t in enumerate(sorted(df["txn_type"].dropna().unique())):
        subset = df[df["txn_type"] == t]
        ax.scatter(subset["shares"], subset["amount"], s=8, alpha=0.5,
                   label=t, color=cmap(i % 10))
    ax.set_title("Shares vs. Amount by Transaction Type")
    ax.set_xlabel("Shares")
    ax.set_ylabel("Amount ($)")
    ax.legend(markerscale=2, fontsize=8, title="txn_type")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "scatter_shares_amount.png"), dpi=150)
    plt.close(fig)

    print(f"\nCharts saved to {CHARTS_DIR}/")

    # ---- 16. Save plain-text profile summary (items 2-13) -----------------------------
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(profile_lines))
    print(f"Profile summary saved to {PROFILE_PATH}")


if __name__ == "__main__":
    main()
