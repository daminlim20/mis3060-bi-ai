"""
Build a timeline linking executive events to the nearest earnings filing.

Reads:
    hw03/earnings_history.csv
    hw03/executive_events.csv
Writes:
    hw03/corporate_events_timeline.csv

Run from the folder that contains hw03/ (or from inside hw03/ itself):
    python corporate_events_timeline.py
Add --overwrite to replace an existing output file.
"""

import sys
from pathlib import Path

import pandas as pd

SAME_WEEK_DAYS = 7  # events within this many days of an earnings filing are 'same week'

# Column used to match companies across the two tables. Leave as None to detect
# automatically, or set it (e.g. "ticker") if detection picks the wrong column.
COMPANY_COL = None
COMPANY_CANDIDATES = ["ticker", "symbol", "company", "company_name", "cik", "name"]
DATE_COL = "filing_date"


def find_data_dir() -> Path:
    """Locate the hw03 folder whether the script runs from its parent or inside it."""
    for candidate in (Path("hw03"), Path("."), Path(__file__).resolve().parent):
        if (candidate / "earnings_history.csv").exists() and (
            candidate / "executive_events.csv"
        ).exists():
            return candidate
    sys.exit("Could not find earnings_history.csv and executive_events.csv in hw03/.")


def pick_company_col(earnings: pd.DataFrame, events: pd.DataFrame) -> str:
    if COMPANY_COL:
        return COMPANY_COL
    shared = {c.lower(): c for c in earnings.columns if c in events.columns}
    for name in COMPANY_CANDIDATES:
        if name in shared:
            return shared[name]
    sys.exit(
        "Could not tell which column identifies the company. "
        f"Shared columns: {sorted(shared.values())}. Set COMPANY_COL at the top of the script."
    )


def classify(signed_days) -> str:
    """signed_days = event date minus nearest earnings date."""
    if pd.isna(signed_days):
        return "no earnings data"
    if abs(signed_days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if signed_days < 0 else "after earnings"


def main() -> None:
    data_dir = find_data_dir()
    out_path = data_dir / "corporate_events_timeline.csv"
    if out_path.exists() and "--overwrite" not in sys.argv:
        sys.exit(f"{out_path} already exists. Re-run with --overwrite to replace it.")

    earnings = pd.read_csv(data_dir / "earnings_history.csv")
    events = pd.read_csv(data_dir / "executive_events.csv")
    for df, name in ((earnings, "earnings_history"), (events, "executive_events")):
        if DATE_COL not in df.columns:
            sys.exit(f"{name}.csv has no '{DATE_COL}' column. Columns: {list(df.columns)}")
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    company = pick_company_col(earnings, events)

    # --- 1. Find the nearest earnings filing for each event --------------------
    nearest_idx, signed = [], []
    for _, ev in events.iterrows():
        same_co = earnings[
            (earnings[company] == ev[company]) & earnings[DATE_COL].notna()
        ]
        if same_co.empty or pd.isna(ev[DATE_COL]):
            nearest_idx.append(None)
            signed.append(float("nan"))
            continue
        diffs = (ev[DATE_COL] - same_co[DATE_COL]).dt.days  # + means event is after
        best = diffs.abs().idxmin()  # ties go to the earlier-listed earnings row
        nearest_idx.append(best)
        signed.append(diffs[best])

    # --- 2/3. Combine: every event row + its matched earnings row ---------------
    events_out = events.add_suffix("_event")
    earnings_out = earnings.add_suffix("_earnings")
    matched = pd.DataFrame(
        [earnings_out.loc[i] if i is not None else pd.Series(dtype=object) for i in nearest_idx],
        columns=earnings_out.columns,
    ).reset_index(drop=True)

    combined = pd.concat([events_out.reset_index(drop=True), matched], axis=1)
    # Keep one plain company column up front instead of two duplicated copies.
    combined.insert(0, company, events[company].values)
    combined = combined.drop(columns=[f"{company}_event", f"{company}_earnings"])

    signed = pd.Series(signed, dtype="float")
    combined["days_to_nearest_earnings"] = signed.abs().astype("Int64")
    combined["event_timing"] = signed.apply(classify)

    combined = combined.sort_values([company, f"{DATE_COL}_event"]).reset_index(drop=True)
    for col in (f"{DATE_COL}_event", f"{DATE_COL}_earnings"):
        combined[col] = combined[col].dt.strftime("%Y-%m-%d")
    combined.to_csv(out_path, index=False)
    print(f"Saved {len(combined)} rows to {out_path}\n")

    # --- 4. Per-company summary -------------------------------------------------
    # Pick a descriptive column from the events table to show what each event was.
    desc_col = next(
        (c for c in events.columns
         if c.lower() in ("event_type", "event", "description", "event_description", "title")),
        None,
    )
    all_companies = sorted(set(earnings[company].dropna()) | set(events[company].dropna()))
    print("=" * 70)
    print("EXECUTIVE EVENTS BY COMPANY")
    print("=" * 70)
    for co in all_companies:
        rows = combined[combined[company] == co]
        print(f"\n{co}")
        if rows.empty:
            print("  (no executive events)")
            continue
        for _, r in rows.iterrows():
            what = f" | {r[desc_col + '_event']}" if desc_col else ""
            days = r["days_to_nearest_earnings"]
            near = r[f"{DATE_COL}_earnings"]
            if r["event_timing"] == "no earnings data":
                print(f"  {r[DATE_COL + '_event']}{what}: no earnings filings for this company")
            else:
                print(f"  {r[DATE_COL + '_event']}{what}: {r['event_timing']} "
                      f"(nearest earnings {near}, {days} days apart)")

    # --- 5. Overall counts ------------------------------------------------------
    counts = combined["event_timing"].value_counts()
    print("\n" + "=" * 70)
    print(f"TOTALS ACROSS ALL {len(all_companies)} COMPANIES")
    print("=" * 70)
    print(f"  Before earnings: {counts.get('before earnings', 0)}")
    print(f"  After earnings:  {counts.get('after earnings', 0)}")
    print(f"  Same week (within {SAME_WEEK_DAYS} days, counted separately): "
          f"{counts.get('same week', 0)}")
    if counts.get("no earnings data", 0):
        print(f"  No earnings data to compare: {counts['no earnings data']}")


if __name__ == "__main__":
    main()
