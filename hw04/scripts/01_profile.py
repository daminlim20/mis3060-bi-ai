"""
HW4 Part A: audit of the Wildcat Capital tables.

Part 1 - profile_table(df, table_name) works on ANY DataFrame; nothing in it
names a table or column. For every column it reports blanks, null-like tokens,
distinct values, value shapes, inferred type + parse failures, whitespace,
case variants, mixed formats, id-like columns and numeric/date min/max.

Part 2 - four groups of rule checks (column, single-table, referential,
cross-table). These are driven by the SPEC / RELATIONSHIPS config below,
which is the only table-specific part of the script.

Run from the hw04 folder:   python scripts/01_profile.py
Outputs:  reports/profile_raw.csv, reports/dq_summary_raw.csv

Revised after Claude Code review (see README.md for the list of findings).
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
REPORTS = BASE / "reports"

# Kept as an explicit list (not a glob of *.csv) on purpose: the assignment
# says to use ONLY these eight files and ignore anything else in the folder.
TABLES = [
    "dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]

# Null-like tokens are a guess about meaning ("None" can be a real value),
# so they are reported separately, never silently treated as missing.
NULL_TOKENS = {"none", "null", "nan", "n/a", "na", "-", "--", "?", "missing", "nil"}
BOOL_TOKENS = {"true", "false", "yes", "no"}      # no single letters (review #11)

INT_RE = r"[+-]?\d+"
FLOAT_RE = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"   # no inf / nan (review #5)
SCI_RE = r".*[eE][+-]?\d+"
DATE_RE = r"\d{4}-\d{2}-\d{2}"                    # strict: 2024-1-5 fails (review #2)
TYPED_THRESHOLD = 0.80                              # >= 80% parse -> that type
PARTLY_TYPED = 0.50                                 # 50-80% -> flagged, not hidden (review #3)


# ---------- loading -------------------------------------------------------
def load_raw(table: str) -> pd.DataFrame:
    """Read every column as text so nothing is silently converted.
    utf-8-sig strips a byte-order mark if one is present (review #15).
    A malformed row (wrong number of fields) is allowed to stop the run:
    an audit should fail loudly, not skip data."""
    path = RAW_DIR / f"{table}.csv"
    with open(path, encoding="utf-8-sig") as fh:
        header = next(__import__("csv").reader(fh), [])
    dupes = {h for h in header if header.count(h) > 1}
    assert not dupes, f"{table}: duplicate column headers {dupes}"
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


# ---------- helpers -------------------------------------------------------
def shapes_of(values: pd.Series, collapse_digits: bool = False) -> pd.Series:
    """Vectorised value shapes (review #9): digits->9, upper->A, lower->a.
    Letter runs become A* / a* - the '*' cannot be confused with data
    (review #13). Shapes are computed once per UNIQUE value, then mapped back.
    collapse_digits=True gives the 'format' (45.10 and 4510.25 -> 9.9)."""
    uniq = pd.Series(values.unique())
    s = (uniq.str.replace(r"[A-Z]", "A", regex=True)
             .str.replace(r"[a-z]", "a", regex=True)
             .str.replace(r"[0-9]", "9", regex=True)
             .str.replace(r"A{2,}", "A*", regex=True)
             .str.replace(r"a{2,}", "a*", regex=True))
    if collapse_digits:
        s = s.str.replace(r"^[+-]", "", regex=True).str.replace(r"9+", "9", regex=True)
    else:
        s = s.str.replace(r"9{7,}", "9*", regex=True)
    return values.map(dict(zip(uniq, s)))


def parses_as(values: pd.Series, kind: str) -> pd.Series:
    """Boolean Series: True where the (stripped) value is a valid `kind`."""
    if kind == "int":
        return values.str.fullmatch(INT_RE)
    if kind == "float":
        return values.str.fullmatch(FLOAT_RE)
    if kind == "date":
        return values.str.fullmatch(DATE_RE) & \
            pd.to_datetime(values, format="%Y-%m-%d", errors="coerce").notna()
    if kind == "bool":
        return values.str.lower().isin(BOOL_TOKENS)
    return pd.Series(True, index=values.index)


def infer_type(values: pd.Series):
    """Return (inferred_type, best_non_text_type, best_rate).
    int vs float (review #4): if every float-valid value is also an int it
    is int; if some have decimals it is float."""
    if values.empty:
        return "empty", "", 0.0
    rates = {k: parses_as(values, k).mean() for k in ["bool", "int", "float", "date"]}
    if rates["float"] > rates["int"]:
        rates.pop("int")            # decimals present -> int is the wrong idea
    else:
        rates.pop("float")
    best = max(rates, key=rates.get)
    rate = float(rates[best])
    return (best if rate >= TYPED_THRESHOLD else "text"), best, rate


# ---------- the generic profiler -----------------------------------------
def profile_column(table: str, col: str, s: pd.Series) -> dict:
    n = len(s)
    stripped = s.str.strip()
    is_blank = stripped == ""
    is_null_token = stripped.str.lower().isin(NULL_TOKENS)
    vals = stripped[~is_blank & ~is_null_token]          # real, stripped values

    kind, best_type, best_rate = infer_type(vals)
    check_kind = kind if kind != "text" else (best_type if best_rate >= PARTLY_TYPED else "text")
    ok = parses_as(vals, check_kind)
    bad = vals[~ok]
    good = vals[ok]

    shapes = shapes_of(vals).value_counts()
    formats = shapes_of(good, collapse_digits=True).value_counts()   # review #6

    numeric = check_kind in ("int", "float")
    x = pd.to_numeric(good, errors="coerce") if numeric else pd.Series(dtype=float)
    d = pd.to_datetime(good, format="%Y-%m-%d", errors="coerce") if check_kind == "date" \
        else pd.Series(dtype="datetime64[ns]")                        # review #1

    leading_zero = int(vals.str.fullmatch(r"0\d+").sum())
    id_like = bool(numeric and (col.lower().endswith("_id") or leading_zero > 0
                                or (len(vals) and vals.nunique() == len(vals) and check_kind == "int")))

    pct = lambda k, base: round(100 * k / base, 2) if base else 0.0   # review #16
    return {
        "table": table,
        "column": col,
        "rows": n,
        "blank": int(is_blank.sum()),
        "null_tokens": int(is_null_token.sum()),
        "null_token_values": ", ".join(sorted(set(stripped[is_null_token])))[:60],
        "pct_blank_or_null": pct((is_blank | is_null_token).sum(), n),
        "distinct": int(vals.nunique()),                               # review #7
        "pct_distinct": pct(vals.nunique(), len(vals)),
        "inferred_type": kind,
        "best_type": best_type,
        "best_type_pct": round(100 * best_rate, 2),
        "partly_typed": bool(kind == "text" and best_rate >= PARTLY_TYPED),
        "parse_fail": int(len(bad)),
        "pct_parse_fail": pct(len(bad), len(vals)),
        "sample_bad_values": " | ".join(bad.drop_duplicates().head(5)),
        "n_shapes": int(len(shapes)),
        "top_shapes": " | ".join(f"{k} ({v})" for k, v in shapes.head(4).items()),
        "formats": " | ".join(f"{k} ({v})" for k, v in formats.head(4).items()),
        "mixed_format": bool(check_kind != "text" and len(formats) > 1),
        # money/percent text like '$1,000' or '9.28%' hides numbers (review #3)
        "symbol_numeric_values": int((vals.str.fullmatch(r"[-+$(]*[\d,.]+%?\)?")
                                      & vals.str.contains(r"[$%,]")).sum()),
        "scientific_notation": int(good.str.fullmatch(SCI_RE).sum()) if numeric else 0,
        "lead_trail_space": int((s != stripped).sum()),
        "internal_double_space": int(stripped.str.contains(r"\s{2,}", regex=True).sum()),  # review #8
        "case_variants": int(vals.nunique() - vals.str.lower().nunique()),
        "leading_zero_values": leading_zero,
        "id_like": id_like,                                            # review #12
        "min": x.min() if numeric and not x.empty else "",
        "max": x.max() if numeric and not x.empty else "",
        "date_min": d.min().date().isoformat() if not d.dropna().empty else "",
        "date_max": d.max().date().isoformat() if not d.dropna().empty else "",
        "top_values": " | ".join(f"{k} ({v})" for k, v in s.value_counts().head(5).items()),
    }


def profile_table(df: pd.DataFrame, table: str) -> pd.DataFrame:
    return pd.DataFrame([profile_column(table, c, df[c]) for c in df.columns])


# =========================================================================
# STEP 2: the four check groups
# =========================================================================
# Every check produces one row in dq_summary_raw.csv. A check that finds
# nothing is recorded as PASS, so the summary also proves what was tested.
#
# Severity guide
#   ERROR - wrong, or will break a join / calculation
#   WARN  - probably wrong; investigate before trusting it
#   INFO  - worth knowing; often a legitimate structure, not a defect

FINDINGS = []


def record(group, table, column, check, severity, fail_mask, df, key, note=""):
    """Log one check. fail_mask is a boolean Series (True = row fails)."""
    fail_mask = fail_mask.fillna(False).astype(bool)
    n_fail = int(fail_mask.sum())
    show_cols = [key] + [c for c in column.split("+") if c in df.columns and c != key]
    examples = (
        df.loc[fail_mask, show_cols].head(3).astype(str)
        .apply(lambda r: "; ".join(f"{c}={r[c]}" for c in show_cols), axis=1)
    )
    FINDINGS.append({
        "group": group,
        "table": table,
        "column": column,
        "check": check,
        "severity": severity if n_fail else "PASS",
        "rows_failed": n_fail,
        "pct_failed": round(100 * n_fail / len(df), 3) if len(df) else 0,
        "examples": " || ".join(examples),
        "note": note,
    })


def num(s):
    """Text -> number; anything that does not parse becomes NaN (and is caught
    separately by the type checks)."""
    return pd.to_numeric(s.str.strip(), errors="coerce")


def pct_to_decimal(s):
    """'9.28%' -> 0.0928, '0.0928' -> 0.0928. Used only to TEST a hypothesis
    here; Part C decides whether to apply it."""
    is_pct = s.str.strip().str.endswith("%")
    out = num(s.str.replace("%", "", regex=False))
    return out.where(~is_pct, out / 100)


# ---------- table specs: the only table-specific part of the audit --------
# The check functions below are generic; this dictionary tells them what
# "correct" means for each table.
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}
SPEC = {
    "dim_advisor": {
        "pk": "advisor_id",
        "int": ["advisor_id", "years_experience", "aum_target_mm"],
        "allowed": {"region": {"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"}},
        "range": {"years_experience": (0, 50), "aum_target_mm": (1, 1000)},
        "required": ["first_name", "last_name", "region"],
    },
    "dim_benchmark": {
        "pk": "benchmark_id",
        "int": ["benchmark_id"],
        "required": ["name", "asset_class", "ticker_proxy"],
    },
    "dim_client": {
        "pk": "client_id",
        "int": ["client_id", "age", "advisor_id"],
        "float": ["initial_aum"],
        "date": ["client_since"],
        "bool": ["is_active"],
        "allowed": {
            "state": US_STATES,
            "risk_profile": {"Conservative", "Moderately Conservative", "Balanced",
                             "Moderately Aggressive", "Aggressive"},
            "client_tier": {"Retail", "HNW", "UHNW"},
            "primary_account_type": {"Taxable", "IRA", "Roth IRA", "Trust", "529"},
        },
        "range": {"age": (18, 110), "initial_aum": (0.01, 1e9)},
        "pattern": {"zip_code": r"\d{5}"},
        "required": ["first_name", "last_name", "state", "zip_code", "risk_profile",
                     "client_tier", "advisor_id"],
    },
    "dim_date": {
        "pk": "date_id",
        "int": ["date_id", "year", "quarter", "month", "week_of_year",
                "is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"],
        "date": ["date"],
        "range": {"year": (2020, 2024), "quarter": (1, 4), "month": (1, 12),
                  "week_of_year": (1, 53)},
        "allowed": {c: {"0", "1"} for c in
                    ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]},
        "unique": ["date"],
    },
    "dim_security": {
        "pk": "security_id",
        "int": ["security_id", "benchmark_id"],
        "float": ["expense_ratio_bps"],
        "bool": ["is_etf"],
        "allowed": {"asset_class": {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}},
        "range": {"expense_ratio_bps": (0, 300)},
        "unique": ["ticker"],
        "required": ["ticker", "name", "asset_class", "benchmark_id"],
        # blanks that are expected to be structural (verified in row rules)
        "optional": ["sector", "expense_ratio_bps"],
    },
    "fact_fees": {
        "pk": "fee_id",
        "int": ["fee_id", "client_id", "advisor_id"],
        "float": ["aum_basis", "bps_charged", "amount"],
        "date": ["fee_date"],
        "allowed": {"fee_type": {"Management", "Advisory", "Custodial", "Performance"}},
        "range": {"aum_basis": (0, 1e10), "bps_charged": (0, 100), "amount": (0.01, 1e8)},
    },
    "fact_portfolio_snapshot": {
        "pk": "snapshot_id",
        "int": ["snapshot_id", "client_id", "advisor_id", "benchmark_id", "year", "month"],
        "float": ["aum", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd", "cash_pct"],
        "date": ["snapshot_date"],
        "allowed": {"account_type": {"Taxable", "IRA", "Roth IRA", "Trust", "529"}},
        "range": {"aum": (0, 1e10), "cash_pct": (0, 1), "month": (1, 12),
                  "year": (2020, 2024), "return_ytd": (-1, 1e6)},
    },
    "fact_transactions": {
        "pk": "txn_id",
        "int": ["txn_id", "client_id", "advisor_id", "security_id"],
        "float": ["shares", "price", "amount"],
        "date": ["txn_date"],
        "allowed": {"txn_type": {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal",
                                 "Advisory Fee"}},
        "range": {"price": (0.01, 1e6), "amount": (0.01, 1e9)},
        "optional": ["security_id", "shares", "price"],
    },
}

# foreign key -> primary key. 10 ID-based + 3 date joins.
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


# ---------- group 1: column level (generic, driven by SPEC) ---------------
def column_checks(t, df, spec):
    pk = spec["pk"]
    g = "1 column"
    blank = lambda c: df[c].str.strip() == ""

    record(g, t, pk, "primary key unique", "ERROR", df[pk].duplicated(keep=False), df, pk)
    record(g, t, pk, "primary key not blank", "ERROR", blank(pk), df, pk)
    for c in spec.get("unique", []):
        record(g, t, c, "natural key unique", "ERROR", df[c].duplicated(keep=False), df, pk)

    for c in spec.get("int", []):
        v = df[c].str.strip()
        bad = (v != "") & ~v.str.fullmatch(r"[+-]?\d+")
        float_like = v.str.fullmatch(r"[+-]?\d+\.0+")
        sev = "WARN" if bad.sum() and (float_like | ~bad).all() else "ERROR"
        record(g, t, c, "type: integer", sev, bad, df, pk,
               "integer stored as float text (e.g. 45.0)" if sev == "WARN" else "")
    for c in spec.get("float", []):
        v = df[c].str.strip()
        record(g, t, c, "type: number", "ERROR", (v != "") & num(df[c]).isna(), df, pk)
    for c in spec.get("date", []):
        v = df[c].str.strip()
        bad = (v != "") & pd.to_datetime(v, format="%Y-%m-%d", errors="coerce").isna()
        record(g, t, c, "type: date YYYY-MM-DD", "ERROR", bad, df, pk)
    for c in spec.get("bool", []):
        record(g, t, c, "type: True/False", "ERROR", ~df[c].isin({"True", "False"}), df, pk)

    for c, allowed in spec.get("allowed", {}).items():
        v = df[c].str.strip()
        record(g, t, c, "allowed values", "ERROR", (v != "") & ~v.isin(allowed), df, pk,
               "allowed: " + ", ".join(sorted(allowed))[:120])
    for c, (lo, hi) in spec.get("range", {}).items():
        x = num(df[c]) if c != "return_ytd" else pct_to_decimal(df[c])
        record(g, t, c, f"range {lo}..{hi}", "WARN", (x < lo) | (x > hi), df, pk)
    for c, pat in spec.get("pattern", {}).items():
        record(g, t, c, f"pattern {pat}", "ERROR", ~df[c].str.fullmatch(pat), df, pk)

    for c in spec.get("required", []):
        record(g, t, c, "required (not blank)", "WARN", blank(c), df, pk)
    for c in spec.get("optional", []):
        record(g, t, c, "blank (expected structural?)", "INFO", blank(c), df, pk,
               "verified against other columns in group 2")
    for c in df.columns:
        record(g, t, c, "leading/trailing whitespace", "WARN",
               df[c] != df[c].str.strip(), df, pk)
        nt = df[c].str.strip().str.lower().isin(NULL_TOKENS)
        record(g, t, c, "null-like text token (None/NULL/N/A)", "INFO", nt, df, pk)


# ---------- group 2: single-table rules -----------------------------------
def single_table_checks(T):
    g = "2 single-table"

    # exact duplicates ignoring the surrogate key
    for t, df in T.items():
        pk = SPEC[t]["pk"]
        record(g, t, "all except " + pk, "exact duplicate row (ignoring id)", "ERROR",
               df.drop(columns=pk).duplicated(keep=False), df, pk)

    c = T["dim_client"]
    near = ["first_name", "age", "city", "zip_code", "client_since", "initial_aum"]
    record(g, "dim_client", "+".join(near + ["last_name"]),
           "near-duplicate client (same person, new id)", "ERROR",
           c.duplicated(near, keep=False), c, "client_id",
           "matched on every field except id and last_name")
    aum = num(c.initial_aum)
    bands = {"Retail": (0, 500_000), "HNW": (500_000, 5_000_000), "UHNW": (5_000_000, 1e12)}
    lo = c.client_tier.map(lambda x: bands.get(x, (None, None))[0])
    hi = c.client_tier.map(lambda x: bands.get(x, (None, None))[1])
    record(g, "dim_client", "client_tier+initial_aum", "tier agrees with initial AUM band",
           "WARN", (aum < lo) | (aum >= hi), c, "client_id")

    s = T["dim_security"]
    etf = s.is_etf == "True"
    record(g, "dim_security", "sector+is_etf", "sector blank only for ETFs", "ERROR",
           (s.sector == "") & ~etf, s, "security_id")
    record(g, "dim_security", "expense_ratio_bps+is_etf", "expense ratio blank only for non-ETFs",
           "ERROR", (s.expense_ratio_bps == "") & etf, s, "security_id")

    d = T["dim_date"]
    dt = pd.to_datetime(d.date, errors="coerce")
    for col, truth in {
        "year": dt.dt.year, "quarter": dt.dt.quarter, "month": dt.dt.month,
        "month_name": dt.dt.month_name(), "day_of_week": dt.dt.day_name(),
        "is_month_end": dt.dt.is_month_end.astype(int),
        "is_quarter_end": dt.dt.is_quarter_end.astype(int),
        "is_year_end": dt.dt.is_year_end.astype(int),
    }.items():
        record(g, "dim_date", f"{col}+date", f"{col} agrees with date", "ERROR",
               d[col] != truth.astype(str), d, "date_id")
    record(g, "dim_date", "is_trading_day+date", "weekend marked as trading day", "ERROR",
           (dt.dt.dayofweek >= 5) & (d.is_trading_day == "1"), d, "date_id")
    record(g, "dim_date", "is_trading_day+date", "weekday marked non-trading (holidays)", "INFO",
           (dt.dt.dayofweek < 5) & (d.is_trading_day == "0"), d, "date_id",
           "0 means market holidays (e.g. Jan 1) are treated as trading days")

    f = T["fact_fees"]
    calc = num(f.aum_basis) * num(f.bps_charged) / 10000 / 12
    record(g, "fact_fees", "amount+aum_basis+bps_charged",
           "amount = aum_basis x bps / 10000 / 12", "ERROR",
           (num(f.amount) - calc).abs() > 0.01, f, "fee_id")
    record(g, "fact_fees", "client_id+fee_date+fee_type", "one fee per client-month", "WARN",
           f.duplicated(["client_id", "fee_date"], keep=False), f, "fee_id")
    record(g, "fact_fees", "aum_basis", "aum_basis at 1,000 floor", "INFO",
           num(f.aum_basis) == 1000, f, "fee_id")

    p = T["fact_portfolio_snapshot"]
    pdt = pd.to_datetime(p.snapshot_date, errors="coerce")
    record(g, "fact_portfolio_snapshot", "year+snapshot_date", "year agrees with date", "ERROR",
           p.year != pdt.dt.year.astype(str), p, "snapshot_id")
    record(g, "fact_portfolio_snapshot", "month+snapshot_date", "month agrees with date", "ERROR",
           p.month != pdt.dt.month.astype(str), p, "snapshot_id")
    record(g, "fact_portfolio_snapshot", "client_id+snapshot_date", "one snapshot per client-month",
           "ERROR", p.duplicated(["client_id", "snapshot_date"], keep=False), p, "snapshot_id")
    record(g, "fact_portfolio_snapshot", "return_ytd", "return stored as % string", "ERROR",
           p.return_ytd.str.strip().str.endswith("%"), p, "snapshot_id")
    rt = pct_to_decimal(p.return_ytd)
    alpha_gap = (rt - num(p.benchmark_return_ytd) - num(p.active_alpha_ytd)).abs()
    record(g, "fact_portfolio_snapshot", "active_alpha_ytd+return_ytd+benchmark_return_ytd",
           "alpha = return - benchmark (with % read as /100)", "ERROR",
           alpha_gap > 1e-4, p, "snapshot_id",
           "if this passes, '9.28%' really means 0.0928")
    record(g, "fact_portfolio_snapshot", "return_ytd", "implausible YTD return (>100% or < -90%)",
           "WARN", (rt > 1) | (rt < -0.9), p, "snapshot_id",
           "look at aum around these rows: deposits/withdrawals inside the return?")
    record(g, "fact_portfolio_snapshot", "aum", "aum at 1,000 floor", "INFO",
           num(p.aum) == 1000, p, "snapshot_id")

    x = T["fact_transactions"]
    sec_types = {"Buy", "Sell", "Dividend"}
    needs_sec = x.txn_type.isin(sec_types)
    has_sec = x.security_id.str.strip() != ""
    record(g, "fact_transactions", "security_id+txn_type",
           "Buy/Sell/Dividend must have a security", "ERROR", needs_sec & ~has_sec, x, "txn_id")
    record(g, "fact_transactions", "security_id+txn_type",
           "cash flows / fee debits must NOT have a security", "ERROR",
           ~needs_sec & (has_sec | (x.shares != "") | (x.price != "")), x, "txn_id")
    sh, pr, am = num(x.shares), num(x.price), num(x.amount)
    record(g, "fact_transactions", "shares+txn_type", "shares must be positive", "ERROR",
           sh <= 0, x, "txn_id")
    record(g, "fact_transactions", "amount+shares+price", "amount = |shares| x price", "ERROR",
           needs_sec & ((am - sh.abs() * pr).abs() > 0.01), x, "txn_id",
           "if this passes, the sign of shares is the only thing wrong")
    record(g, "fact_transactions", "amount", "amount must be positive", "ERROR", am <= 0, x, "txn_id")
    record(g, "fact_transactions", "all business fields", "duplicate transaction (ignoring id)",
           "ERROR", x.drop(columns="txn_id").duplicated(keep=False), x, "txn_id")


# ---------- group 3: referential integrity --------------------------------
def ri_checks(T):
    g = "3 referential"
    for ft, fk, dt_, dk in RELATIONSHIPS:
        f, d = T[ft], T[dt_]
        key = f[fk].str.strip()
        key = key.str.replace(r"\.0+$", "", regex=True)       # '45.0' -> '45'
        null = key == ""
        orphan = ~null & ~key.isin(set(d[dk].str.strip()))
        pk = SPEC[ft]["pk"]
        record(g, ft, fk, f"FK -> {dt_}.{dk}: orphan keys", "ERROR", orphan, f, pk,
               f"{key[orphan].nunique()} distinct orphan keys")
        if null.any():
            record(g, ft, fk, f"FK -> {dt_}.{dk}: blank key", "INFO", null, f, pk,
                   "blank FK: check if structural (group 2)")


# ---------- group 4: cross-table business rules ---------------------------
def cross_table_checks(T):
    g = "4 cross-table"
    c = T["dim_client"].set_index("client_id")

    for ft in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        f = T[ft]
        cli_adv = f.client_id.map(c.advisor_id)
        record(g, ft, "advisor_id+client_id", "fact advisor = client's advisor in dim_client",
               "WARN", cli_adv.notna() & (f.advisor_id != cli_adv), f, SPEC[ft]["pk"])

    p = T["fact_portfolio_snapshot"]
    record(g, "fact_portfolio_snapshot", "account_type+client_id",
           "account_type = client's primary_account_type", "WARN",
           p.account_type != p.client_id.map(c.primary_account_type), p, "snapshot_id")
    record(g, "fact_portfolio_snapshot", "snapshot_date+client_id",
           "snapshot before client_since month", "ERROR",
           p.snapshot_date < p.client_id.map(c.client_since).str[:7] + "-01", p, "snapshot_id")
    bench_map = {"Aggressive": "1", "Moderately Aggressive": "1", "Balanced": "3",
                 "Moderately Conservative": "8", "Conservative": "8"}
    rp = p.client_id.map(c.risk_profile)
    record(g, "fact_portfolio_snapshot", "benchmark_id+client_id",
           "benchmark agrees with client's risk_profile", "WARN",
           rp.isin(bench_map) & (p.benchmark_id != rp.map(bench_map)), p, "snapshot_id")
    record(g, "fact_portfolio_snapshot", "benchmark_id+client_id",
           "snapshot for client with BLANK risk_profile (which benchmark?)", "INFO",
           rp == "", p, "snapshot_id", "could this reveal the missing risk_profile?")
    g2 = p.groupby(["benchmark_id", "snapshot_date"]).benchmark_return_ytd.transform("nunique")
    record(g, "fact_portfolio_snapshot", "benchmark_return_ytd",
           "one benchmark return per benchmark-month", "ERROR", g2 > 1, p, "snapshot_id")

    f = T["fact_fees"]
    snap = p.set_index(p.client_id + "|" + p.snapshot_date).aum
    fkey = f.client_id + "|" + f.fee_date
    record(g, "fact_fees", "aum_basis+client_id+fee_date",
           "fee aum_basis = snapshot aum for same client-month", "ERROR",
           fkey.isin(snap.index) & (f.aum_basis != fkey.map(snap)), f, "fee_id")
    record(g, "fact_fees", "client_id+fee_date", "fee with no snapshot that month", "WARN",
           ~fkey.isin(snap.index), f, "fee_id")

    x = T["fact_transactions"]
    last = p.groupby("client_id").snapshot_date.max()
    txn_month = x.txn_date.str[:7] + "-01"
    record(g, "fact_transactions", "txn_date+client_id",
           "transaction after client's last snapshot (departed client?)", "WARN",
           txn_month > x.client_id.map(last), x, "txn_id",
           "check is_active for these clients")
    record(g, "fact_transactions", "txn_date+client_id", "transaction before client_since",
           "ERROR", x.txn_date < x.client_id.map(c.client_since), x, "txn_id")
    trading = T["dim_date"].set_index("date").is_trading_day
    record(g, "fact_transactions", "txn_date+txn_type", "Buy/Sell on a non-trading day", "WARN",
           x.txn_type.isin({"Buy", "Sell"}) & (x.txn_date.map(trading) == "0"), x, "txn_id")
    fee_month = f.groupby(["client_id", "fee_date"]).amount.apply(lambda a: num(a).sum())
    fee_month.index = [a + "|" + b for a, b in fee_month.index]
    adv = x.txn_type == "Advisory Fee"
    fee_amt = (x.client_id + "|" + txn_month).map(fee_month)
    record(g, "fact_transactions", "amount+txn_type",
           "Advisory Fee debit = fact_fees total for that client-month", "WARN",
           adv & ((num(x.amount) - fee_amt).abs() > 0.01), x, "txn_id",
           "two systems describing the same money: do they agree?")


# ---------- main ----------------------------------------------------------
def main():
    REPORTS.mkdir(exist_ok=True)
    T, frames = {}, []
    for t in TABLES:
        T[t] = load_raw(t)
        print(f"{t:26} {len(T[t]):>8,} rows x {T[t].shape[1]:>2} cols")
        frames.append(profile_table(T[t], t))
    profile = pd.concat(frames, ignore_index=True)
    profile.to_csv(REPORTS / "profile_raw.csv", index=False)
    print(f"\nSaved reports/profile_raw.csv  ({len(profile)} column profiles)")

    for t in TABLES:
        column_checks(t, T[t], SPEC[t])
    single_table_checks(T)
    ri_checks(T)
    cross_table_checks(T)

    dq = pd.DataFrame(FINDINGS)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    dq = dq.sort_values(["severity", "group", "table"], key=lambda s: s.map(order)
                        if s.name == "severity" else s)
    dq.to_csv(REPORTS / "dq_summary_raw.csv", index=False)
    print(f"Saved reports/dq_summary_raw.csv  ({len(dq)} checks)\n")
    print(dq.severity.value_counts().to_string())
    print("\nFindings (non-PASS):")
    show = dq[dq.severity != "PASS"]
    for _, r in show.iterrows():
        print(f"  {r.severity:5} {r.table:24} {r.column[:38]:38} {r.check[:55]:55} {r.rows_failed:>7,}")


if __name__ == "__main__":
    main()
