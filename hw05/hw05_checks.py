"""
HW05 - Wildcat Capital star schema checks
MIS3060 Business Intelligence with AI

Proves in code what star_design.md claims:
  Part A  - every primary key is unique and non-blank,
            every foreign key matches a row in the table it points to (no orphans)
  Part B  - each fact table's grain is unique
  Part C  - the arithmetic behind the additive / non-additive classifications

Run from VS Code:   python hw05_checks.py
or point it at the data folder:   python hw05_checks.py "path/to/Wildcat Capital Clean"
"""

import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 0. Load the eight clean tables
# ---------------------------------------------------------------------------
DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent

EXPECTED_SHAPES = {
    "dim_advisor": (25, 7),
    "dim_benchmark": (8, 4),
    "dim_client": (2_500, 14),
    "dim_date": (1_827, 12),
    "dim_security": (500, 8),
    "fact_fees": (122_197, 8),
    "fact_portfolio_snapshot": (129_547, 14),
    "fact_transactions": (298_572, 10),
}

tables = {name: pd.read_csv(DATA_DIR / f"{name}.csv") for name in EXPECTED_SHAPES}

failures = []


def check(label, passed, detail=""):
    """Print one PASS/FAIL line and remember failures."""
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not passed:
        failures.append(label)


print(f"Data folder: {DATA_DIR}\n")

# ---------------------------------------------------------------------------
# 1. Row and column counts match the handout
# ---------------------------------------------------------------------------
print("1. Row and column counts, column names")
for name, expected in EXPECTED_SHAPES.items():
    actual = tables[name].shape
    check(f"{name} is {expected[0]:,} rows x {expected[1]} cols", actual == expected, f"found {actual}")

# Every column the checks below use must exist, so a renamed column gives a FAIL line, not a crash
REQUIRED_COLUMNS = {
    "dim_advisor": ["advisor_id"],
    "dim_benchmark": ["benchmark_id"],
    "dim_client": ["client_id", "advisor_id"],
    "dim_date": ["date_id", "date"],
    "dim_security": ["security_id", "benchmark_id"],
    "fact_fees": ["fee_id", "client_id", "advisor_id", "fee_date", "aum_basis", "bps_charged", "amount"],
    "fact_portfolio_snapshot": ["snapshot_id", "client_id", "advisor_id", "benchmark_id", "snapshot_date",
                                "aum", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd"],
    "fact_transactions": ["txn_id", "client_id", "advisor_id", "security_id", "txn_date", "txn_type",
                          "shares", "price", "amount"],
}
columns_ok = True
for name, cols in REQUIRED_COLUMNS.items():
    missing = [c for c in cols if c not in tables[name].columns]
    check(f"{name} has the columns these checks need", not missing, f"missing: {missing}" if missing else "")
    columns_ok = columns_ok and not missing

if not columns_ok:
    print("\nStopping: fix the files above before the remaining checks can run.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Part A - primary keys are unique and never blank
# ---------------------------------------------------------------------------
print("\n2. Primary keys (Part A)")
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id",
    "dim_benchmark": "benchmark_id",
    "dim_client": "client_id",
    "dim_date": "date_id",
    "dim_security": "security_id",
    "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id",
    "fact_transactions": "txn_id",
}
for name, pk in PRIMARY_KEYS.items():
    col = tables[name][pk]
    # whole-number type guards against keys stored as text (e.g. a cell holding just a space)
    check(f"{name}[{pk}] unique, non-blank, whole numbers",
          col.is_unique and col.notna().all() and pd.api.types.is_integer_dtype(col),
          f"{col.duplicated().sum()} duplicates, {col.isna().sum()} blanks, type {col.dtype}")

# dim_date[date] is the column the facts join to, so it must be unique too
d = tables["dim_date"]["date"]
check("dim_date[date] unique and non-blank (join column for facts)", d.is_unique and d.notna().all())

# ---------------------------------------------------------------------------
# 3. Part A - foreign keys: no orphans
# ---------------------------------------------------------------------------
print("\n3. Foreign keys (Part A)")
# (table, fk column, dimension table, dimension column, blanks allowed?)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_fees", "client_id", "dim_client", "client_id", False),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_fees", "fee_date", "dim_date", "date", False),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", False),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", False),
    ("fact_transactions", "client_id", "dim_client", "client_id", False),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_transactions", "security_id", "dim_security", "security_id", True),
    ("fact_transactions", "txn_date", "dim_date", "date", False),
]
for tbl, fk, dim, dim_col, blanks_ok in FOREIGN_KEYS:
    values = tables[tbl][fk]
    blanks = values.isna().sum()
    orphans = (~values.dropna().isin(tables[dim][dim_col])).sum()
    ok = orphans == 0 and (blanks_ok or blanks == 0)
    check(f"{tbl}[{fk}] -> {dim}[{dim_col}]", ok, f"{orphans} orphans, {blanks:,} blanks")

# Note: the three date FK checks above already prove the fact dates are calendar dates that
# match dim_date[date] (the join column), so no separate date check is needed.

# security_id is blank on exactly the cash rows: every cash row blank, every trade row filled
txn = tables["fact_transactions"]
CASH_TYPES = ["Deposit", "Withdrawal", "Advisory Fee"]
TRADE_TYPES = ["Buy", "Sell", "Dividend"]
is_cash = txn["txn_type"].isin(CASH_TYPES)
is_trade = txn["txn_type"].isin(TRADE_TYPES)
check("every txn_type is either a cash type or a trade type", (is_cash | is_trade).all(),
      f"other types: {sorted(set(txn.loc[~(is_cash | is_trade), 'txn_type']))}")
check("every cash row has a blank security_id", txn.loc[is_cash, "security_id"].isna().all(),
      f"{txn.loc[is_cash, 'security_id'].notna().sum()} cash rows with a security")
check("every trade row has a security_id", txn.loc[is_trade, "security_id"].notna().all(),
      f"{txn.loc[is_trade, 'security_id'].isna().sum()} trade rows without a security")

# Each fact's advisor_id equals the client's advisor in dim_client (Part E b)
client_adv = tables["dim_client"][["client_id", "advisor_id"]]
for tbl in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
    m = tables[tbl].merge(client_adv, on="client_id", suffixes=("", "_client"))
    mismatches = (m["advisor_id"] != m["advisor_id_client"]).sum()
    check(f"{tbl}[advisor_id] equals dim_client[advisor_id]", mismatches == 0, f"{mismatches} mismatches")

# ---------------------------------------------------------------------------
# 4. Part B - grain
# ---------------------------------------------------------------------------
print("\n4. Grain (Part B)")
fees = tables["fact_fees"]
snap = tables["fact_portfolio_snapshot"]

dups = fees.duplicated(["client_id", "fee_date"]).sum()
check("fact_fees: one row per client per month (client_id + fee_date unique)", dups == 0, f"{dups} duplicates")

dups = snap.duplicated(["client_id", "snapshot_date"]).sum()
check("fact_portfolio_snapshot: one row per client per month (client_id + snapshot_date unique)",
      dups == 0, f"{dups} duplicates")

first_of_month = (pd.to_datetime(fees["fee_date"]).dt.day.eq(1).all()
                  and pd.to_datetime(snap["snapshot_date"]).dt.day.eq(1).all())
check("monthly facts are dated the 1st of the month", first_of_month)

# First rule out double-loaded rows: no two rows may be identical apart from txn_id
exact = txn.drop(columns="txn_id").duplicated().sum()
check("fact_transactions: no row is an exact copy of another (apart from txn_id)", exact == 0,
      f"{exact} exact duplicates")

# Then show there is no natural key. Test only trade rows, where security_id is never blank:
# pandas treats two blanks as equal, but SQL and Power BI do not.
natural = ["client_id", "txn_date", "txn_type", "security_id"]
trade_repeats = txn.loc[is_trade].duplicated(natural).sum()
check("fact_transactions: no natural key, so the grain is one event per txn_id",
      trade_repeats > 0 and exact == 0 and txn["txn_id"].is_unique,
      f"{trade_repeats} trade rows repeat client+date+type+security; txn_id unique")

# ---------------------------------------------------------------------------
# 5. Part C - the arithmetic behind the measure classifications
# ---------------------------------------------------------------------------
print("\n5. Measure behaviour (Part C)")
expected_fee = fees["aum_basis"] * fees["bps_charged"] / 10_000 / 12
# Tolerance of 1 cent: the largest real gap is $0.005, i.e. rounding to the cent
check("fees: amount = aum_basis x bps_charged / 10,000 / 12 (amount additive, bps a rate)",
      (fees["amount"] - expected_fee).abs().le(0.01).all(),
      f"max gap ${(fees['amount'] - expected_fee).abs().max():.4f}")

# validate="one_to_one" raises an error if either side matches twice; indicator shows unmatched fees
try:
    m = fees.merge(snap, how="left", left_on=["client_id", "fee_date"],
                   right_on=["client_id", "snapshot_date"], validate="one_to_one", indicator=True)
    unmatched = (m["_merge"] != "both").sum()
    check("fees: aum_basis equals the snapshot aum for that month (a balance, semi-additive)",
          unmatched == 0 and (m["aum_basis"] - m["aum"]).abs().lt(0.01).all(),
          f"{unmatched} fees without a snapshot")
except pd.errors.MergeError as e:
    check("fees: aum_basis equals the snapshot aum for that month (a balance, semi-additive)", False, str(e))

alpha = snap["return_ytd"] - snap["benchmark_return_ytd"]
check("snapshot: active_alpha_ytd = return_ytd - benchmark_return_ytd",
      (alpha - snap["active_alpha_ytd"]).abs().lt(1e-5).all())

# Select trade rows by txn_type, not by "shares is filled", so a trade missing shares cannot be skipped
trades = txn.loc[is_trade]
check("transactions: shares and price are filled on every Buy / Sell / Dividend row",
      trades[["shares", "price"]].notna().all().all(),
      f"{trades['shares'].isna().sum()} blank shares, {trades['price'].isna().sum()} blank prices")
check("transactions: amount = shares x price on Buy / Sell / Dividend rows",
      (trades["amount"] - trades["shares"] * trades["price"]).abs().le(0.01).all(),
      f"max gap ${(trades['amount'] - trades['shares'] * trades['price']).abs().max():.4f}")

check("transactions: every amount is positive (direction lives in txn_type)", txn["amount"].gt(0).all())

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
if failures:
    print(f"{len(failures)} check(s) FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("All checks passed.")
