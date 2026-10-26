"""
HW4 Part C: cleaning program for the Wildcat Capital tables.

Reads the 8 raw files (never modified) and writes 8 clean files with the
same names and columns, plus clearly named 0/1 flag columns.
Every transformation follows decision_log.md, runs one at a time, prints
rows affected + a before/after check, and ASSERTS the after-state, so the
script stops if a fix did not do what the log claims.

Order (defended in decision_log.md):
  dimensions -> facts | remove rows -> fix values -> add flags

Run from the hw04 folder:   python scripts/02_clean.py
Outputs:
  data/clean/<8 tables>.csv
  data/audit/cleaning_log.csv, value_changes.csv, quarantine_*.csv
"""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
CLEAN_DIR = BASE / "data" / "clean"
AUDIT_DIR = BASE / "data" / "audit"

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

CLEANING_LOG = []      # table, issue, action, rows_affected, note
VALUE_CHANGES = []     # DataFrames: table, key_column, key, column, old_value, new_value
QUARANTINE = {}        # name -> (source table, DataFrame)


# ---------- helpers -------------------------------------------------------
def load_raw(table):
    return pd.read_csv(RAW_DIR / f"{table}.csv", dtype=str,
                       keep_default_na=False, encoding="utf-8-sig")


def num(s):
    return pd.to_numeric(s, errors="coerce")


def step(title):
    print(f"\n--- {title} " + "-" * max(0, 66 - len(title)))


def log(table, issue, action, rows, note=""):
    CLEANING_LOG.append({"table": table, "issue": issue, "action": action,
                         "rows_affected": int(rows), "note": note})
    print(f"    rows affected: {rows:,}")


def record_changes(table, df, mask, column, new_values):
    """Log old -> new for every changed cell, then apply the change."""
    key = PK[table]
    old = df.loc[mask, column]
    new = pd.Series(new_values, index=old.index) if not isinstance(new_values, pd.Series) \
        else new_values.loc[old.index]
    VALUE_CHANGES.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key],
        "column": column, "old_value": old, "new_value": new,
    }))
    df.loc[mask, column] = new
    return int(mask.sum())


def quarantine(name, table, df, mask, reason, extra=None):
    """Move rows to a quarantine set (never silently deleted)."""
    q = df.loc[mask].copy()
    if extra is not None:
        for col, values in extra.items():
            q[col] = values.loc[q.index]
    q["quarantine_reason"] = reason
    QUARANTINE[name] = (table, q)
    return df.loc[~mask].copy()


# ---------- dim_client ----------------------------------------------------
def clean_dim_client(c, facts):
    t = "dim_client"

    step("A1 dim_client: quarantine duplicate clients")
    match_on = ["first_name", "age", "city", "zip_code", "client_since", "initial_aum"]
    c["_id"] = c.client_id.astype(int)
    c = c.sort_values("_id")
    dup = c.duplicated(match_on, keep="first")           # keep the lowest (original) id
    first_id = c.groupby(match_on)["client_id"].transform("first")
    dup_ids = set(c.loc[dup, "client_id"])
    print(f"    before: {len(c):,} rows, {c.client_id.nunique():,} ids, "
          f"{dup.sum()} duplicates of an earlier client")
    # verify the decision log's evidence before acting on it
    assert dup.sum() == 25, "expected 25 duplicate clients"
    assert c.loc[dup, "_id"].between(2501, 2525).all(), "duplicates should be ids 2501-2525"
    assert (first_id[dup].astype(int) <= 2500).all(), "every duplicate must match an original"
    trunc = [o.startswith(d) or d.startswith(o) for d, o in
             zip(c.loc[dup, "last_name"], c.loc[dup].index.map(
                 lambda i: c.loc[c.client_id == first_id[i], "last_name"].iloc[0]))]
    print(f"    last_name is a truncated prefix of the original in {sum(trunc)} of 25")
    for name, f in facts.items():
        assert not f.client_id.isin(dup_ids).any(), f"{name} references a duplicate id"
    c = quarantine("dim_client_duplicates", t, c, dup,
                   "duplicate of an earlier client_id (all fields match except last_name)",
                   extra={"duplicate_of_client_id": first_id})
    c = c.drop(columns="_id")
    log(t, "duplicate clients under new ids", "quarantine", 25,
        "ids 2501-2525; originals kept; no fact rows referenced them")
    print(f"    after:  {len(c):,} rows, ids unique = {c.client_id.is_unique}")
    assert len(c) == 2500 and c.client_id.is_unique

    step("A2 dim_client.state: full names -> 2-letter codes")
    state_map = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
                 "California": "CA", "Illinois": "IL", "Texas": "TX"}
    before_counts = c.state.replace(state_map).value_counts()
    mask = c.state.isin(state_map)
    print(f"    before: {mask.sum()} full names, {c.state.nunique()} distinct values")
    n = record_changes(t, c, mask, "state", c.loc[mask, "state"].map(state_map))
    log(t, "state stored as full name", "standardize", n, "7-entry USPS mapping")
    print(f"    after:  {c.state.nunique()} distinct values, PA = {(c.state == 'PA').sum()}")
    assert c.state.str.fullmatch(r"[A-Z]{2}").all()
    assert c.state.value_counts().equals(before_counts), "per-state totals must be preserved"

    step("B1 dim_client: flag blank risk_profile (value left blank)")
    c["is_risk_profile_missing"] = (c.risk_profile.str.strip() == "").astype(int).astype(str)
    n = int((c.is_risk_profile_missing == "1").sum())
    log(t, "blank risk_profile", "flag", n, "not filled: benchmark 3 may be the system default")
    assert n == 75, "expected 75 blanks after removing duplicates"
    assert (c.loc[c.is_risk_profile_missing == "1", "risk_profile"] == "").all()
    return c


# ---------- fact_transactions --------------------------------------------
def clean_fact_transactions(x, clients, snapshots):
    t = "fact_transactions"

    step("A5 fact_transactions: quarantine rows with unknown client_id")
    orphan = ~x.client_id.isin(set(clients.client_id))
    print(f"    before: {len(x):,} rows, {orphan.sum()} orphan client rows, "
          f"{x.loc[orphan, 'client_id'].nunique()} distinct orphan ids")
    assert orphan.sum() == 200
    total = num(x.loc[orphan, "amount"]).sum()
    x = quarantine("fact_transactions_orphan_client", t, x, orphan,
                   "client_id not in dim_client")
    log(t, "client_id not in dim_client", "quarantine", 200,
        f"gross amount ${total:,.2f}; txn_id 298573-298772")
    print(f"    after:  {len(x):,} rows")
    assert x.client_id.isin(set(clients.client_id)).all()

    step("A6 fact_transactions.security_id: '45.0' -> '45'")
    has = x.security_id != ""
    print(f"    before: {has.sum():,} non-blank, all end in '.0' = "
          f"{x.loc[has, 'security_id'].str.fullmatch(r'\d+\.0').all()}")
    assert x.loc[has, "security_id"].str.fullmatch(r"\d+\.0").all(), \
        "a security_id has a real decimal part; do not strip"
    n = record_changes(t, x, has, "security_id",
                       x.loc[has, "security_id"].str.replace(r"\.0$", "", regex=True))
    log(t, "security_id stored as decimal text", "standardize", n, "blanks left blank (cash flows)")
    assert x.loc[has, "security_id"].str.fullmatch(r"\d+").all()
    assert (x.security_id == "").sum() == (~has).sum(), "blank count must not change"

    step("A4 fact_transactions.shares: fix negative Buy share counts")
    sh, pr, am = num(x.shares), num(x.price), num(x.amount)
    neg = sh < 0
    print(f"    before: {neg.sum()} negative shares, types = "
          f"{x.loc[neg, 'txn_type'].value_counts().to_dict()}")
    assert (x.loc[neg, "txn_type"] == "Buy").all()
    # reconcile: the amount proves the size is right, so only the sign is wrong
    assert ((am[neg] - sh[neg].abs() * pr[neg]).abs() <= 0.01).all(), \
        "amount does not reconcile to |shares| x price; sign fix not justified"
    n = record_changes(t, x, neg, "shares", x.loc[neg, "shares"].str.lstrip("-"))
    log(t, "negative shares on Buy", "convert (abs)", n,
        "amount = |shares| x price verified on all rows first")
    sh = num(x.shares)
    print(f"    after:  {(sh < 0).sum()} negative shares")
    assert (sh.dropna() > 0).all()
    trade = x.txn_type.isin(["Buy", "Sell", "Dividend"])
    assert ((num(x.amount)[trade] - sh[trade] * num(x.price)[trade]).abs() <= 0.01).all()

    step("B3 fact_transactions: flag transactions after client left")
    last = snapshots.groupby("client_id").snapshot_date.max()
    txn_month = x.txn_date.str[:7] + "-01"
    post = txn_month > x.client_id.map(last)
    active = x.client_id.map(clients.set_index("client_id").is_active)
    assert (active[post] == "False").all(), "a flagged client is still active"
    x["is_post_departure_txn"] = post.astype(int).astype(str)
    log(t, "transaction after client's last snapshot", "flag", post.sum(),
        f"{x.loc[post, 'client_id'].nunique()} clients, all is_active = False")
    assert post.sum() == 2410
    return x


# ---------- fact_portfolio_snapshot ---------------------------------------
def clean_fact_portfolio_snapshot(p):
    t = "fact_portfolio_snapshot"

    step("A3 fact_portfolio_snapshot.return_ytd: '9.28%' -> 0.0928")
    pct = p.return_ytd.str.strip().str.endswith("%")
    print(f"    before: {pct.sum()} percent strings, "
          f"{num(p.return_ytd).isna().sum()} non-numeric values")
    new = p.loc[pct, "return_ytd"].map(
        lambda v: format(round(float(v.strip().rstrip("%")) / 100, 6), ".6f").rstrip("0").rstrip("."))
    # reconcile BEFORE applying: alpha = return - benchmark must hold
    gap = (num(new) - num(p.loc[pct, "benchmark_return_ytd"])
           - num(p.loc[pct, "active_alpha_ytd"])).abs()
    assert (gap <= 1e-4).all(), "alpha does not reconcile with /100; conversion not justified"
    n = record_changes(t, p, pct, "return_ytd", new)
    log(t, "return_ytd stored as percent text", "convert", n,
        "verified: return - benchmark = alpha on all converted rows")
    rt = num(p.return_ytd)
    print(f"    after:  {rt.isna().sum()} non-numeric values")
    assert rt.notna().all()
    assert ((rt - num(p.benchmark_return_ytd) - num(p.active_alpha_ytd)).abs() <= 1e-4).all()

    step("B2 fact_portfolio_snapshot: flag implausible YTD returns")
    sus = (rt > 1) | (rt < -0.9)
    p["is_return_suspect"] = sus.astype(int).astype(str)
    log(t, "YTD return > +100% or < -90%", "flag", sus.sum(),
        f"{p.loc[sus, 'client_id'].nunique()} clients; deposits counted as performance")
    assert sus.sum() == 1475
    return p


# ---------- main ----------------------------------------------------------
def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    raw = {t: load_raw(t) for t in TABLES}
    clean = {t: df.copy() for t, df in raw.items()}
    print("Loaded raw:", ", ".join(f"{t} {len(df):,}" for t, df in raw.items()))

    facts = {t: clean[t] for t in TABLES if t.startswith("fact_")}
    clean["dim_client"] = clean_dim_client(clean["dim_client"], facts)
    clean["fact_portfolio_snapshot"] = clean_fact_portfolio_snapshot(clean["fact_portfolio_snapshot"])
    clean["fact_transactions"] = clean_fact_transactions(
        clean["fact_transactions"], clean["dim_client"], clean["fact_portfolio_snapshot"])

    for t in ["dim_advisor", "dim_benchmark", "dim_date", "dim_security", "fact_fees"]:
        CLEANING_LOG.append({"table": t, "issue": "none requiring change", "action": "leave as is",
                             "rows_affected": 0, "note": "see decision_log.md section C"})

    step("Proof: raw rows = clean rows + quarantined rows (every table)")
    for t in TABLES:
        q = sum(len(df) for (src, df) in QUARANTINE.values() if src == t)
        ok = len(raw[t]) == len(clean[t]) + q
        print(f"    {t:26} raw {len(raw[t]):>8,} = clean {len(clean[t]):>8,} "
              f"+ quarantined {q:>4}   {'OK' if ok else 'FAIL'}")
        assert ok, f"{t}: rows were lost"
        # same columns, in the same order; only new is_* flag columns appended
        added = [c for c in clean[t].columns if c not in raw[t].columns]
        assert list(clean[t].columns[:raw[t].shape[1]]) == list(raw[t].columns)
        assert all(c.startswith("is_") for c in added), f"{t}: unexpected new column"
        assert clean[t][PK[t]].is_unique, f"{t}: primary key not unique"

    for t, df in clean.items():
        df.to_csv(CLEAN_DIR / f"{t}.csv", index=False)
    pd.DataFrame(CLEANING_LOG).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False)
    pd.concat(VALUE_CHANGES, ignore_index=True).to_csv(AUDIT_DIR / "value_changes.csv", index=False)
    for name, (_, q) in QUARANTINE.items():
        q.to_csv(AUDIT_DIR / f"quarantine_{name}.csv", index=False)

    n_changes = sum(len(v) for v in VALUE_CHANGES)
    print(f"\nSaved 8 clean tables to data/clean/")
    print(f"Saved data/audit/cleaning_log.csv ({len(CLEANING_LOG)} rows), "
          f"value_changes.csv ({n_changes:,} cell changes), "
          f"{len(QUARANTINE)} quarantine files")


if __name__ == "__main__":
    main()
