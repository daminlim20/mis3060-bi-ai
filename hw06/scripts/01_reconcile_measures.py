"""HW6 Part B - reconcile Power BI measures to independent pandas calculations.

Usage (from the hw06/ folder):
    python scripts/01_reconcile_measures.py --data "path/to/Wildcat Capital Clean"

Reads:  <data>/fact_portfolio_snapshot.csv, fact_fees.csv, fact_transactions.csv, dim_client.csv
        reports/powerbi_values.csv            (measure, slice, value) exported from Power BI
Writes: reports/pandas_values.csv             (pandas side only, for reference)
        reports/measure_reconciliation.csv    (measure, slice, powerbi_value, pandas_value, abs_diff, match)
Also prints the Part C evidence.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# ---------- tolerance by measure type ----------
CURRENCY = {"AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "Ending AUM PM",
            "Avg AUM per Client", "Avg Monthly AUM"}
COUNT = {"Ending Clients"}
BPS = {"Fee Yield (bps)"}
TEXT = {"Alpha Signal"}


def tolerance(measure):
    if measure in CURRENCY:
        return 0.01
    if measure in BPS:
        return 0.01
    if measure in COUNT:
        return 0.0
    return 0.0001  # ratios / percentages


# ---------- load ----------
def load(data_dir):
    d = Path(data_dir)
    snap = pd.read_csv(d / "fact_portfolio_snapshot.csv", parse_dates=["snapshot_date"])
    fees = pd.read_csv(d / "fact_fees.csv", parse_dates=["fee_date"])
    txn = pd.read_csv(d / "fact_transactions.csv", parse_dates=["txn_date"])
    client = pd.read_csv(d / "dim_client.csv")[["client_id", "client_tier"]]
    # attach the dimension attribute we slice by (same as the dim_client relationship)
    snap = snap.merge(client, on="client_id", how="left")
    fees = fees.merge(client, on="client_id", how="left")
    txn = txn.merge(client, on="client_id", how="left")
    snap["yr"], snap["mo"] = snap.snapshot_date.dt.year, snap.snapshot_date.dt.month
    fees["yr"], fees["mo"] = fees.fee_date.dt.year, fees.fee_date.dt.month
    txn["yr"], txn["mo"] = txn.txn_date.dt.year, txn.txn_date.dt.month
    return snap, fees, txn


def filt(df, years=None, months=None, tier=None):
    """Apply the same filters a Power BI slice applies (dim_date year/month, dim_client tier)."""
    m = pd.Series(True, index=df.index)
    if years is not None:
        m &= df.yr.isin(years)
    if months is not None:
        m &= df.mo.isin(months)
    if tier is not None:
        m &= df.client_tier == tier
    return df[m]


# ---------- measures, written independently of DAX ----------
def at_last_snapshot(s):
    """Rows at the last snapshot date that has data in the filter (= LASTNONBLANK)."""
    if s.empty:
        return s
    return s[s.snapshot_date == s.snapshot_date.max()]


def ending_aum(s):
    last = at_last_snapshot(s)
    return last.aum.sum() if not last.empty else np.nan


def ending_clients(s):
    last = at_last_snapshot(s)
    return float(last.client_id.nunique()) if not last.empty else np.nan


def weighted_alpha(s):
    last = at_last_snapshot(s)
    ok = last[(last.is_return_suspect != 1) & last.active_alpha_ytd.notna()]
    return (ok.aum * ok.active_alpha_ytd).sum() / ok.aum.sum() if ok.aum.sum() else np.nan


def alpha_signal(a):
    if pd.isna(a):
        return ""
    if a >= 0.02:
        return "Outperforming"
    if a <= -0.02:
        return "Lagging"
    return "In line"


def top10_share(s):
    last = at_last_snapshot(s)
    by_client = last.groupby("client_id").aum.sum().sort_values(ascending=False)
    return by_client.head(10).sum() / by_client.sum() if by_client.sum() else np.nan


def div(a, b):
    return a / b if (b not in (0, None) and not pd.isna(b) and not pd.isna(a)) else np.nan


def all_measures(snap, fees, txn, years, months=None, tier=None, ly_years=None, pm=None):
    """Compute every measure for one slice.
    ly_years: the years SAMEPERIODLASTYEAR maps to; pm: (years, months) DATEADD -1 month maps to."""
    s = filt(snap, years, months, tier)
    f = filt(fees, years, months, tier)
    t = filt(txn, years, months, tier)
    out = {}
    out["AUM (naive SUM)"] = s.aum.sum()
    out["Ending AUM"] = ending_aum(s)
    out["Ending Clients"] = ending_clients(s)
    out["Avg AUM per Client"] = div(out["Ending AUM"], out["Ending Clients"])
    ly = ending_aum(filt(snap, ly_years, months, tier)) if ly_years else np.nan
    out["Ending AUM LY"] = ly
    out["AUM YoY %"] = div(out["Ending AUM"] - ly, ly)
    if pm:
        pm_val = ending_aum(filt(snap, pm[0], pm[1], tier))
        out["Ending AUM PM"] = pm_val
        out["AUM MoM %"] = div(out["Ending AUM"] - pm_val, pm_val)
    out["Avg Monthly AUM"] = div(s.aum.sum(), s.snapshot_date.nunique())
    out["Fee Yield (bps)"] = div(f.amount.sum() * 12 * 10000, s.aum.sum())
    net = t.loc[t.txn_type == "Deposit", "amount"].sum() - t.loc[t.txn_type == "Withdrawal", "amount"].sum()
    out["Organic Growth Rate"] = div(net, ly)
    out["AUM-Weighted Alpha"] = weighted_alpha(s)
    out["Alpha Signal"] = alpha_signal(out["AUM-Weighted Alpha"])
    out["Top 10 Client Share"] = top10_share(s)
    return out


def build_pandas_values(snap, fees, txn):
    years = sorted(snap.yr.unique())
    rows = []

    def add(slice_name, values, keep):
        for k in keep:
            rows.append({"measure": k, "slice": slice_name, "pandas_value": values[k]})

    # Grand total: no filter. SAMEPERIODLASTYEAR of the whole calendar keeps 2020-2023;
    # DATEADD(-1 month) of the whole calendar ends in Nov of the last year.
    last_y = years[-1]
    tot = all_measures(snap, fees, txn, years, ly_years=years[:-1],
                       pm=(years, None))
    # PM at grand total = everything through Nov of the last year
    pm_tot = snap[snap.snapshot_date < pd.Timestamp(last_y, 12, 1)]
    tot["Ending AUM PM"] = ending_aum(pm_tot)
    tot["AUM MoM %"] = div(tot["Ending AUM"] - tot["Ending AUM PM"], tot["Ending AUM PM"])
    add("Total", tot, list(tot.keys()))

    # By year: measures 0, 1, 4, 6-10
    by_year = ["AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
               "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal"]
    for y in years:
        add(str(y), all_measures(snap, fees, txn, [y], ly_years=[y - 1]), by_year)

    # By tier, 2024: measures 1, 3, 4, 7-11
    by_tier = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
               "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
    for tier in sorted(snap.client_tier.dropna().unique()):
        add(f"{tier} 2024", all_measures(snap, fees, txn, [2024], tier=tier, ly_years=[2023]), by_tier)

    # Measure 5, December 2024
    dec = all_measures(snap, fees, txn, [2024], months=[12], pm=([2024], [11]))
    add("2024-12", dec, ["Ending AUM", "Ending AUM PM", "AUM MoM %"])
    return pd.DataFrame(rows)


def reconcile(pandas_df, pbi_path):
    pbi = pd.read_csv(pbi_path, dtype={"slice": str})
    pbi.columns = [c.strip().lower().strip("[]") for c in pbi.columns]
    pbi = pbi.rename(columns={"value": "powerbi_value"})
    pbi["measure"], pbi["slice"] = pbi.measure.str.strip(), pbi["slice"].str.strip()
    df = pandas_df.merge(pbi[["measure", "slice", "powerbi_value"]], on=["measure", "slice"], how="inner")  # only rows exported from Power BI

    def compare(r):
        if r.measure in TEXT:
            pv = "" if pd.isna(r.powerbi_value) else str(r.powerbi_value).strip()
            return pd.Series({"abs_diff": np.nan, "match": pv == (r.pandas_value or "")})
        p, q = pd.to_numeric(r.powerbi_value, errors="coerce"), pd.to_numeric(r.pandas_value, errors="coerce")
        if pd.isna(p) and pd.isna(q):
            return pd.Series({"abs_diff": 0.0, "match": True})
        diff = abs(p - q)
        return pd.Series({"abs_diff": diff, "match": bool(diff <= tolerance(r.measure) + 1e-9)})

    df[["abs_diff", "match"]] = df.apply(compare, axis=1)
    return df[["measure", "slice", "powerbi_value", "pandas_value", "abs_diff", "match"]]


def part_c(snap, fees):
    print("\n===== Part C evidence =====")
    # (a) Ending AUM vs SUMX over clients of each client's own Ending AUM
    total = ending_aum(snap)
    per_client = snap.sort_values("snapshot_date").groupby("client_id").tail(1)
    sumx = per_client.aum.sum()
    gone = per_client[per_client.snapshot_date < snap.snapshot_date.max()]
    print(f"(a) Ending AUM = {total:,.2f} | SUMX by client = {sumx:,.2f} | diff = {sumx - total:,.2f}")
    print(f"    {len(gone)} clients whose last snapshot is before {snap.snapshot_date.max():%Y-%m}, "
          f"their last balances sum to {gone.aum.sum():,.2f}")
    # (b) Fee Yield vs Effective Fee Rate, 2024
    s24, f24 = snap[snap.yr == 2024], fees[fees.yr == 2024]
    fy = f24.amount.sum() * 12 * 1e4 / s24.aum.sum()
    efr = f24.amount.sum() * 12 * 1e4 / f24.aum_basis.sum()
    print(f"(b) 2024 Fee Yield = {fy:.2f} bps | Effective Fee Rate = {efr:.2f} bps")
    print(f"    sum snapshot aum = {s24.aum.sum():,.0f} | sum fee aum_basis = {f24.aum_basis.sum():,.0f}")
    # does aum_basis double count? compare per client-month
    fb = f24.groupby(["client_id", "mo"]).agg(basis=("aum_basis", "sum"), n=("fee_id", "count"),
                                                 basis_max=("aum_basis", "max")).reset_index()
    sb = s24.groupby(["client_id", "mo"]).aum.sum().rename("aum").reset_index()
    j = fb.merge(sb, on=["client_id", "mo"], how="outer", indicator=True)
    print(f"    fee rows per client-month: mean {fb.n.mean():.2f}, max {fb.n.max()}")
    print(f"    fee types 2024: {f24.fee_type.value_counts().to_dict()}")
    print(f"    client-months with fees but no snapshot: {(j._merge == 'left_only').sum()} "
          f"(basis {j.loc[j._merge == 'left_only', 'basis'].sum():,.0f}); "
          f"snapshot but no fees: {(j._merge == 'right_only').sum()}")
    both = j[j._merge == "both"]
    print(f"    where both exist: sum max(aum_basis) {both.basis_max.sum():,.0f} vs snapshot aum {both.aum.sum():,.0f}")
    # (c) alpha variants at last snapshot
    last = at_last_snapshot(snap)
    nn = last[last.active_alpha_ytd.notna()]
    clean = nn[nn.is_return_suspect != 1]
    print(f"(c) weighted, suspects excluded = {weighted_alpha(snap):.6f}")
    print(f"    simple mean, same rows      = {clean.active_alpha_ytd.mean():.6f}")
    print(f"    weighted, suspects included = {(nn.aum * nn.active_alpha_ytd).sum() / nn.aum.sum():.6f}")
    print(f"    suspect rows at last date: {(nn.is_return_suspect == 1).sum()}, "
          f"max suspect alpha {nn.loc[nn.is_return_suspect == 1, 'active_alpha_ytd'].max():.2f}")
    allyr = snap[snap.active_alpha_ytd.notna() & (snap.is_return_suspect != 1)]
    print(f"    (all months, not last only) weighted = {(allyr.aum * allyr.active_alpha_ytd).sum() / allyr.aum.sum():.6f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data"), help="folder with the Wildcat Capital Clean CSVs")
    args = ap.parse_args()
    snap, fees, txn = load(args.data)
    REPORTS.mkdir(exist_ok=True)
    pdv = build_pandas_values(snap, fees, txn)
    pdv.to_csv(REPORTS / "pandas_values.csv", index=False)
    pbi_path = REPORTS / "powerbi_values.csv"
    if pbi_path.exists():
        rec = reconcile(pdv, pbi_path)
        rec.to_csv(REPORTS / "measure_reconciliation.csv", index=False)
        print(f"{len(rec)} rows, {int(rec.match.sum())} match")
        bad = rec[~rec.match]
        if len(bad):
            print(bad.to_string(index=False))
    else:
        print(f"No {pbi_path} yet - wrote pandas_values.csv only ({len(pdv)} rows)")
    part_c(snap, fees)


if __name__ == "__main__":
    main()
