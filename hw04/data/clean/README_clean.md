# Wildcat Capital: Clean Data (HW4)

Produced by `scripts/02_clean.py` from the 8 raw files in `data/raw/` (raw files are never modified).
Every change is traceable in `data/audit/`: `cleaning_log.csv` (one row per step), `value_changes.csv` (198,256 cell-level old → new values) and two `quarantine_*.csv` files. The reasons for each decision are in `../../decision_log.md`.

## Row counts

| Table | Raw | Clean | Quarantined | Quarantine file |
|---|---:|---:|---:|---|
| dim_advisor | 25 | 25 | 0 | |
| dim_benchmark | 8 | 8 | 0 | |
| dim_client | 2,525 | 2,500 | 25 | `quarantine_dim_client_duplicates.csv` |
| dim_date | 1,827 | 1,827 | 0 | |
| dim_security | 500 | 500 | 0 | |
| fact_fees | 122,197 | 122,197 | 0 | |
| fact_portfolio_snapshot | 129,547 | 129,547 | 0 | |
| fact_transactions | 298,772 | 298,572 | 200 | `quarantine_fact_transactions_orphan_client.csv` |

`raw = clean + quarantined` is asserted for every table in the script.

## Relationships (star schema)

All are many-to-one, from fact (or snowflaked dimension) to dimension. Single-direction filtering from dimension to fact.

| From (many) | To (one) | Notes |
|---|---|---|
| `fact_fees.client_id` | `dim_client.client_id` | |
| `fact_fees.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_fees.fee_date` | `dim_date.date` | always the 1st of the month |
| `fact_portfolio_snapshot.client_id` | `dim_client.client_id` | one snapshot per client per month |
| `fact_portfolio_snapshot.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_portfolio_snapshot.benchmark_id` | `dim_benchmark.benchmark_id` | |
| `fact_portfolio_snapshot.snapshot_date` | `dim_date.date` | always the 1st of the month |
| `fact_transactions.client_id` | `dim_client.client_id` | |
| `fact_transactions.advisor_id` | `dim_advisor.advisor_id` | |
| `fact_transactions.security_id` | `dim_security.security_id` | **blank by design** for Deposit / Withdrawal / Advisory Fee (101,528 rows) |
| `fact_transactions.txn_date` | `dim_date.date` | any calendar day |
| `dim_client.advisor_id` | `dim_advisor.advisor_id` | snowflake; the fact tables also carry advisor_id directly |
| `dim_security.benchmark_id` | `dim_benchmark.benchmark_id` | snowflake |

Join `dim_date` on the **`date`** column, not `date_id`; no fact table stores `date_id`. In every fact table the `advisor_id` equals the client's `advisor_id` in `dim_client` (checked: 0 mismatches), so the two paths to `dim_advisor` agree. In Power BI, keep only one of them active to avoid ambiguous paths.

## Column types a BI tool needs

Files are plain CSV; set these types on import instead of trusting auto-detect.

| Type | Columns |
|---|---|
| **Text** (keep leading zeros / literal values) | `dim_client.zip_code` (232 ZIPs start with 0), `dim_advisor.certifications` (the value `None` means "no certification", not null), `dim_security.ticker`, `dim_benchmark.ticker_proxy`, all name/category columns, `primary_account_type` / `account_type` (`529` is a plan name, not a number) |
| **Whole number** | all `*_id` columns, `age`, `years_experience`, `aum_target_mm`, `year`, `quarter`, `month`, `week_of_year` |
| **Decimal** | `initial_aum`, `expense_ratio_bps`, `aum_basis`, `bps_charged`, `shares`, `price` |
| **Fixed decimal / currency** | `amount` (fees and transactions), `aum` |
| **Decimal (ratio, format as %)** | `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct`. These are stored as decimals (0.0928 = 9.28%); a few tiny values use scientific notation (`1.2e-05`), which parses correctly as Decimal |
| **Date** (ISO `YYYY-MM-DD`) | `dim_date.date`, `client_since`, `fee_date`, `snapshot_date`, `txn_date` |
| **True/False** | `dim_client.is_active`, `dim_security.is_etf` |
| **Whole number 0/1** (or True/False) | `dim_date.is_*`, and the flag columns below |

## Flag columns added (0/1)

| Table | Column | Rows = 1 | Meaning / how to use it |
|---|---|---:|---|
| dim_client | `is_risk_profile_missing` | 75 | `risk_profile` is blank and was **not** filled. Show as its own bucket; chase with advisors. |
| fact_portfolio_snapshot | `is_return_suspect` | 1,475 (178 clients) | YTD return > +100% or < −90%; caused by deposits/withdrawals on small Retail accounts being counted as performance. **Exclude from average-return measures.** |
| fact_transactions | `is_post_departure_txn` | 2,410 (131 clients) | Dated after the client's last monthly snapshot; all are `is_active = False` clients. Investigate before using in advisor activity metrics. |

## What was changed

| Step | Table.column | Rows | Change |
|---|---|---:|---|
| A1 | dim_client | 25 | Duplicate clients (ids 2501–2525, truncated last names) quarantined; originals kept |
| A2 | dim_client.state | 77 | Full state names → 2-letter codes |
| A3 | fact_portfolio_snapshot.return_ytd | 300 | `9.28%` → `0.0928` (verified against alpha) |
| A5 | fact_transactions | 200 | Rows with a client_id not in dim_client quarantined ($10,888,495.37 gross) |
| A6 | fact_transactions.security_id | 197,044 | `45.0` → `45` |
| A4 | fact_transactions.shares | 835 | Negative Buy shares → positive (verified: amount = \|shares\| × price) |

Counts are after quarantine. The raw audit showed 78 / 836 / 197,175 for A2 / A4 / A6. The difference is rows that were quarantined first (1 duplicate client had a full state name; 1 orphan transaction had negative shares; 131 orphan transactions had a security_id).

## Known limitations (chosen not to fix)

1. **Blank risk profiles (75 clients) were not filled.** All of them use benchmark 3, which only Balanced clients otherwise use. But that may be the system default for missing profiles, and suitability data should not be inferred.
2. **Extreme returns are flagged, not recomputed.** A true time-weighted return needs cash-flow timing we don't have.
3. **Advisory Fee transactions do not reconcile to `fact_fees`** at monthly, quarterly or annual grain. Treat `fact_fees` as the billing system of record; don't sum fee revenue from `fact_transactions`.
4. **28.4% of Buy/Sell trades fall on weekends,** about the same share as weekend days on the calendar (28.6%). Trade dates look like booking dates, not exchange dates, so day-of-week trading analysis is not meaningful.
5. **`dim_date.is_trading_day` marks market holidays (e.g. Jan 1) as trading days.** No holiday calendar is available in this data.
6. **AUM floor of $1,000** (420 snapshots, 386 fee rows) looks like a system minimum, not a real balance.
7. **One fee at 100.38 bps** (fee_id 68809) is slightly above every other fee; it reconciles to AUM × bps, and no documented cap exists.
8. **Negative-share Buys were assumed to be sign errors, not reversals.** Nothing in the rows indicates a cancellation.
9. **The 200 quarantined transactions may belong to real clients missing from `dim_client`.** They are kept in the quarantine file, so they can be restored if the client records turn up.
