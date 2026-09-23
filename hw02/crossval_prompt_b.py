"""
Cross-validation -- Prompt B
Count total rows, then subtract the count of rows where txn_type is
Sell, Deposit, Withdrawal, Dividend, or Advisory Fee. What remains
should be the Buy count, verified independently of Prompt A's direct filter.
"""

import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

total_rows = len(df)
other_types = ["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]
other_count = df["txn_type"].isin(other_types).sum()

buy_count_by_subtraction = total_rows - other_count

print(f"Total rows:                         {total_rows:,}")
print(f"Rows that are Sell/Deposit/Withdrawal/Dividend/Advisory Fee: {other_count:,}")
print(f"Prompt B result -- Buy count by subtraction: {buy_count_by_subtraction:,}")
