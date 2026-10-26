"""
HW4 Part D: referential integrity, rule checks, reconciliations, outliers,
and a raw-vs-clean data quality scorecard.

Everything runs twice, on data/raw and on data/clean, so every number has a
before and an after.

Run from the hw04 folder:   python scripts/03_validate.py
Outputs (reports/):
  data_quality_scorecard.csv   one row per table per stage   <- required
  ri_results.csv               13 relationships x 2 stages
  rule_results.csv             every business rule x 2 stages
  reconciliations.csv          cross-table / recomputed checks x 2 stages
  outliers_iqr.csv             IQR flags x 2 stages
"""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
STAGES = {"raw": BASE / "data" / "raw", "clean": BASE / "data" / "clean"}
TABLES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]
PK = {
    "dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id",
    "dim_client": "client_id", "dim_date": "date_id", "dim_security": "security_id",
    "fact_fees": "fee_id", "fact_portfolio_snapshot": "snapshot_id",
    "fact_transactions": "txn_id",
}


def load(stage, table):
    return pd.read_csv(STAGES[stage] / f"{table}.csv", dtype=str,
                       keep_default_na=False, encoding="utf-8-sig")


def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


# =========================================================================
# 1. Referential integrity: ONE reusable function (kept for Assignment 5)
# =========================================================================
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every value of fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared exactly as stored (text, whitespace-stripped), the way a
    BI tool would join them, so '45.0' does NOT match '45'.
    Blank keys are counted separately: they are not orphans, and whether a
    blank is allowed is a business rule, not an RI question.

    Returns a dict:
      rows, null_keys, null_key_rate  - blank foreign keys
      match_rate                      - share of NON-blank keys found in the dim
      orphan_rows                     - non-blank keys not found in the dim
      distinct_orphan_keys            - how many different missing keys
      sample_orphan_keys              - up to 5 examples
      dim_key_unique                  - the "one" side must be unique
    """
    fk = fact_df[fact_key].astype(str).str.strip()
    pk = dim_df[dim_key].astype(str).str.strip()
    is_null = fk == ""
    present = fk[~is_null]
    found = present.isin(set(pk))
    orphans = present[~found]
    n = len(fk)
    return {
        "rows": n,
        "null_keys": int(is_null.sum()),
        "null_key_rate": round(100 * is_null.mean(), 3) if n else 0.0,
        "match_rate": round(100 * found.mean(), 3) if len(present) else 100.0,
        "orphan_rows": int(len(orphans)),
        "distinct_orphan_keys": int(orphans.nunique()),
        "sample_orphan_keys": ", ".join(orphans.drop_duplicates().head(5)),
        "dim_key_unique": bool(pk.is_unique),
    }


# 10 ID-based relationships + 3 joins to the date table
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


def run_ri(T, stage):
    rows = []
    for ft, fk, dt, dk in RELATIONSHIPS:
        r = check_referential_integrity(T[ft], fk, T[dt], dk)
        rows.append({"stage": stage, "fact_table": ft, "fact_key": fk,
                     "dim_table": dt, "dim_key": dk, **r})
    return pd.DataFrame(rows)


# =========================================================================
# 2. Rule-based checks: every column with a natural business bound
# =========================================================================
US_STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN
MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
TRADES = {"Buy", "Sell", "Dividend"}


def between(lo, hi):
    return lambda s: num(s).between(lo, hi)


def one_of(values):
    return lambda s: s.str.strip().isin(values)


# (table, column, rule name, test(column) -> pass Series, optional row filter(df) -> mask)
RULES = [
    ("dim_advisor", "years_experience", "range 0-50", between(0, 50), None),
    ("dim_advisor", "aum_target_mm", "positive", lambda s: num(s) > 0, None),
    ("dim_advisor", "region", "allowed list",
     one_of({"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"}), None),
    ("dim_client", "age", "range 18-110", between(18, 110), None),
    ("dim_client", "initial_aum", "positive", lambda s: num(s) > 0, None),
    ("dim_client", "state", "USPS 2-letter code", one_of(US_STATES), None),
    ("dim_client", "zip_code", "5 digits", lambda s: s.str.fullmatch(r"\d{5}"), None),
    ("dim_client", "risk_profile", "allowed list (if present)",
     one_of({"Conservative", "Moderately Conservative", "Balanced",
             "Moderately Aggressive", "Aggressive"}), lambda d: d.risk_profile != ""),
    ("dim_client", "client_tier", "allowed list", one_of({"Retail", "HNW", "UHNW"}), None),
    ("dim_client", "primary_account_type", "allowed list", one_of(ACCOUNT_TYPES), None),
    ("dim_client", "is_active", "True/False", one_of({"True", "False"}), None),
    ("dim_client", "client_since", "not after 2024-12-31", lambda s: s <= "2024-12-31", None),
    ("dim_date", "month", "range 1-12", between(1, 12), None),
    ("dim_date", "quarter", "range 1-4", between(1, 4), None),
    ("dim_date", "week_of_year", "range 1-53", between(1, 53), None),
    ("dim_date", "is_trading_day", "0/1", one_of({"0", "1"}), None),
    ("dim_security", "asset_class", "allowed list",
     one_of({"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}), None),
    ("dim_security", "expense_ratio_bps", "range 0-300 (if present)", between(0, 300),
     lambda d: d.expense_ratio_bps != ""),
    ("dim_security", "is_etf", "True/False", one_of({"True", "False"}), None),
    ("fact_fees", "amount", "positive", lambda s: num(s) > 0, None),
    ("fact_fees", "bps_charged", "range 0-100", between(0, 100), None),
    ("fact_fees", "aum_basis", "non-negative", lambda s: num(s) >= 0, None),
    ("fact_fees", "fee_type", "allowed list",
     one_of({"Management", "Advisory", "Custodial", "Performance"}), None),
    ("fact_fees", "fee_date", "first of month", lambda s: s.str.endswith("-01"), None),
    ("fact_portfolio_snapshot", "aum", "non-negative", lambda s: num(s) >= 0, None),
    ("fact_portfolio_snapshot", "cash_pct", "range 0-1", between(0, 1), None),
    ("fact_portfolio_snapshot", "return_ytd", "numeric and >= -100%",
     lambda s: num(s) >= -1, None),
    ("fact_portfolio_snapshot", "benchmark_return_ytd", "numeric and >= -100%",
     lambda s: num(s) >= -1, None),
    ("fact_portfolio_snapshot", "month", "range 1-12", between(1, 12), None),
    ("fact_portfolio_snapshot", "account_type", "allowed list", one_of(ACCOUNT_TYPES), None),
    ("fact_transactions", "txn_type", "allowed list",
     one_of(TRADES | {"Deposit", "Withdrawal", "Advisory Fee"}), None),
    ("fact_transactions", "amount", "positive (sign carried by txn_type)",
     lambda s: num(s) > 0, None),
    ("fact_transactions", "shares", "positive for trades", lambda s: num(s) > 0,
     lambda d: d.txn_type.isin(TRADES)),
    ("fact_transactions", "price", "positive for trades", lambda s: num(s) > 0,
     lambda d: d.txn_type.isin(TRADES)),
    ("fact_transactions", "security_id", "present for trades",
     lambda s: s.str.strip() != "", lambda d: d.txn_type.isin(TRADES)),
    ("fact_transactions", "security_id", "blank for cash flows / fee debits",
     lambda s: s.str.strip() == "", lambda d: ~d.txn_type.isin(TRADES)),
]


def run_rules(T, stage):
    rows = []
    for t, col, name, test, where in RULES:
        df = T[t]
        scope = where(df) if where else pd.Series(True, index=df.index)
        passed = test(df.loc[scope, col]).fillna(False).astype(bool)
        rows.append({"stage": stage, "table": t, "column": col, "rule": name,
                     "rows_checked": int(scope.sum()), "rows_failed": int((~passed).sum()),
                     "pass_rate": round(100 * passed.mean(), 3) if len(passed) else 100.0})
    return pd.DataFrame(rows)


# =========================================================================
# 3. Cross-table reconciliations (recomputed vs stored)
# =========================================================================
def run_reconciliations(T, stage):
    f, p, x = T["fact_fees"], T["fact_portfolio_snapshot"], T["fact_transactions"]
    out = []

    def add(name, detail, ok):
        ok = ok.fillna(False).astype(bool)
        out.append({"stage": stage, "reconciliation": name, "detail": detail,
                    "rows_checked": len(ok), "rows_failed": int((~ok).sum()),
                    "pass_rate": round(100 * ok.mean(), 3)})

    # R1: fee amount recomputed from its own inputs
    calc = num(f.aum_basis) * num(f.bps_charged) / 10000 / 12
    add("R1 fee amount = aum_basis x bps / 10000 / 12", "fact_fees, tolerance $0.01",
        (num(f.amount) - calc).abs() <= 0.01)

    # R2: two tables describing the same fact: fee basis vs snapshot AUM
    snap = dict(zip(p.client_id + "|" + p.snapshot_date, p.aum))
    basis = (f.client_id + "|" + f.fee_date).map(snap)
    add("R2 fee aum_basis = snapshot aum (same client-month)",
        "fact_fees vs fact_portfolio_snapshot", num(f.aum_basis) == num(basis))

    # R3: alpha recomputed from return and benchmark
    gap = num(p.return_ytd) - num(p.benchmark_return_ytd) - num(p.active_alpha_ytd)
    add("R3 active_alpha = return_ytd - benchmark_return_ytd",
        "fact_portfolio_snapshot, tolerance 0.0001", gap.abs() <= 1e-4)

    # R4: trade amount recomputed from shares x price (sign must agree too)
    tr = x[x.txn_type.isin(TRADES)]
    add("R4 trade amount = shares x price", "fact_transactions trades, tolerance $0.01",
        (num(tr.amount) - num(tr.shares) * num(tr.price)).abs() <= 0.01)

    # R5: advisor on each fact row = client's advisor in dim_client
    adv = T["dim_client"].drop_duplicates("client_id").set_index("client_id").advisor_id
    for name, df in [("fees", f), ("snapshots", p), ("transactions", x)]:
        add(f"R5 {name}: advisor_id = dim_client.advisor_id", "fact vs dim_client",
            df.advisor_id == df.client_id.map(adv))

    # R6: benchmark return identical for every client on the same benchmark-month
    n = p.groupby(["benchmark_id", "snapshot_date"]).benchmark_return_ytd.transform("nunique")
    add("R6 one benchmark return per benchmark-month", "fact_portfolio_snapshot", n == 1)
    return pd.DataFrame(out)


# =========================================================================
# 4. IQR outliers: numeric columns with no natural upper bound
# =========================================================================
IQR_COLUMNS = [
    ("fact_fees", "amount"),
    ("fact_transactions", "amount"),
    ("fact_portfolio_snapshot", "aum"),
    ("dim_client", "initial_aum"),
]


def run_iqr(T, stage, k=1.5):
    rows = []
    for t, col in IQR_COLUMNS:
        x = num(T[t][col]).dropna()
        q1, q3 = x.quantile(0.25), x.quantile(0.75)
        lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
        flagged = (x < lo) | (x > hi)
        rows.append({"stage": stage, "table": t, "column": col, "q1": round(q1, 2),
                     "q3": round(q3, 2), "lower_fence": round(lo, 2), "upper_fence": round(hi, 2),
                     "rows": len(x), "flagged": int(flagged.sum()),
                     "pct_flagged": round(100 * flagged.mean(), 2), "max": round(x.max(), 2)})
    return pd.DataFrame(rows)


IQR_NOTE = ("Flagged does not mean wrong: AUM and amounts are right-skewed by client tier "
            "(a UHNW client's normal balance is far above the Retail-heavy upper fence), so the "
            "IQR flags mostly mark large-but-legitimate accounts that need a look, not errors.")


# =========================================================================
# 5. Scorecard: one row per table per stage
# =========================================================================
# Blanks that are correct by design (decision_log.md section C) are excluded
# from completeness, so the score measures defects, not structure.
STRUCTURAL_BLANKS = {
    "dim_security": {"sector", "expense_ratio_bps"},
    "fact_transactions": {"security_id", "shares", "price"},
}
TYPES = {   # column -> expected type; everything else is free text
    "int": {"advisor_id", "years_experience", "aum_target_mm", "benchmark_id", "client_id",
            "age", "date_id", "year", "quarter", "month", "week_of_year", "security_id",
            "fee_id", "snapshot_id", "txn_id", "is_month_end", "is_quarter_end",
            "is_year_end", "is_trading_day"},
    "float": {"initial_aum", "expense_ratio_bps", "aum_basis", "bps_charged", "amount", "aum",
              "return_ytd", "benchmark_return_ytd", "active_alpha_ytd", "cash_pct",
              "shares", "price"},
    "date": {"client_since", "date", "fee_date", "snapshot_date", "txn_date"},
    "bool": {"is_active", "is_etf"},
}
DUP_CLIENT_KEY = ["first_name", "age", "city", "zip_code", "client_since", "initial_aum"]


def type_valid(s, kind):
    v = s.str.strip()
    if kind == "int":
        ok = v.str.fullmatch(r"[+-]?\d+")
    elif kind == "float":
        ok = v.str.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
    elif kind == "date":
        ok = pd.to_datetime(v, format="%Y-%m-%d", errors="coerce").notna()
    else:
        ok = v.isin({"True", "False"})
    return ok[v != ""]          # blanks are a completeness question, not a type one


def scorecard(T, stage, ri, rules):
    rows = []
    for t in TABLES:
        df = T[t]
        cols = [c for c in df.columns if not c.startswith("is_") or c in TYPES["int"] | TYPES["bool"]]
        cols = [c for c in cols if c not in {"is_risk_profile_missing", "is_return_suspect",
                                              "is_post_departure_txn"}]   # added flags
        req = [c for c in cols if c not in STRUCTURAL_BLANKS.get(t, set())]
        completeness = (df[req].apply(lambda s: s.str.strip() != "")).to_numpy().mean()

        unique = ~df[PK[t]].duplicated(keep=False)
        if t == "dim_client":    # business key: the same person must not appear twice
            unique &= ~df.duplicated(DUP_CLIENT_KEY, keep=False)

        checks = [type_valid(df[c], k) for k in TYPES for c in cols if c in TYPES[k]]
        typed = pd.concat(checks) if checks else pd.Series(dtype=bool)

        rr = rules[rules.table == t]
        rule_pass = 1 - rr.rows_failed.sum() / rr.rows_checked.sum() if len(rr) else float("nan")

        r = ri[ri.fact_table == t]
        nonnull = (r.rows - r.null_keys).sum()
        ri_match = 1 - r.orphan_rows.sum() / nonnull if len(r) else float("nan")

        rows.append({
            "table": t, "stage": stage, "rows": len(df),
            "pct_completeness": round(100 * completeness, 3),
            "pct_key_uniqueness": round(100 * unique.mean(), 3),
            "pct_type_validity": round(100 * typed.mean(), 3) if len(typed) else 100.0,
            "pct_rule_pass": round(100 * rule_pass, 3) if rule_pass == rule_pass else "n/a",
            "pct_referential_match": round(100 * ri_match, 3) if ri_match == ri_match else "n/a",
        })
    return pd.DataFrame(rows)


# =========================================================================
def main():
    REPORTS.mkdir(exist_ok=True)
    out = {k: [] for k in ["ri", "rules", "recon", "iqr", "score"]}
    for stage in STAGES:
        T = {t: load(stage, t) for t in TABLES}
        ri, rules = run_ri(T, stage), run_rules(T, stage)
        out["ri"].append(ri)
        out["rules"].append(rules)
        out["recon"].append(run_reconciliations(T, stage))
        out["iqr"].append(run_iqr(T, stage))
        out["score"].append(scorecard(T, stage, ri, rules))
    R = {k: pd.concat(v, ignore_index=True) for k, v in out.items()}

    score = R["score"].sort_values(["table", "stage"], key=lambda s: s.map(
        {"raw": 0, "clean": 1}) if s.name == "stage" else s)
    score.to_csv(REPORTS / "data_quality_scorecard.csv", index=False)
    R["ri"].to_csv(REPORTS / "ri_results.csv", index=False)
    R["rules"].to_csv(REPORTS / "rule_results.csv", index=False)
    R["recon"].to_csv(REPORTS / "reconciliations.csv", index=False)
    iqr = R["iqr"].assign(note=IQR_NOTE)
    iqr.to_csv(REPORTS / "outliers_iqr.csv", index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("\n=== Referential integrity (match % of non-blank keys) ===")
    piv = R["ri"].pivot_table(index=["fact_table", "fact_key", "dim_table"], columns="stage",
                              values=["match_rate", "orphan_rows", "null_key_rate"], sort=False)
    print(piv[[("match_rate", "raw"), ("match_rate", "clean"), ("orphan_rows", "raw"),
               ("orphan_rows", "clean"), ("null_key_rate", "clean")]].to_string())

    print("\n=== Rules that fail at either stage ===")
    rp = R["rules"].pivot_table(index=["table", "column", "rule"], columns="stage",
                                values="rows_failed", sort=False)[["raw", "clean"]]
    print(rp[(rp.raw > 0) | (rp.clean > 0)].to_string())
    print(f"({len(RULES)} rules in total; the rest pass at both stages)")

    print("\n=== Reconciliations (rows failed) ===")
    print(R["recon"].pivot_table(index="reconciliation", columns="stage", values="rows_failed",
                                 sort=False)[["raw", "clean"]].to_string())

    print("\n=== IQR outliers (clean) ===")
    print(R["iqr"][R["iqr"].stage == "clean"][["table", "column", "upper_fence", "flagged",
                                                "pct_flagged", "max"]].to_string(index=False))
    print(IQR_NOTE)

    print("\n=== Data quality scorecard ===")
    print(score.to_string(index=False))
    print("\nSaved reports/data_quality_scorecard.csv, ri_results.csv, rule_results.csv, "
          "reconciliations.csv, outliers_iqr.csv")


if __name__ == "__main__":
    main()
