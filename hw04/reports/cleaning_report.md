# Wildcat Capital Data Cleaning Report
**To:** Portfolio Committee · **Re:** Warehouse extract audit and cleaning (8 tables, 555,401 rows)

## Executive summary

The warehouse extract is **usable for reporting after cleaning, but it was not before.** We audited all eight tables with 340 automated checks, found 6 definite errors and 7 probable problems, and fixed or isolated every one without inventing data.

Three findings matter most to the committee:

1. **Security-level reporting would have shown nothing.** In the raw extract, 0% of the 197,175 trades and dividends joined to the securities table, because trade records stored the ID as `45.0` and the securities table as `45`. After cleaning, the match is 100%.
2. **The client list was overstated by 25 people.** Twenty-five clients appeared twice under new IDs (2501–2525), with truncated last names. The duplicates are removed; the client count is now 2,500.
3. **$10.89M of transaction activity belongs to no known client.** 200 transactions point to client IDs that do not exist. They are set aside, not deleted, pending a check with operations.

We also **flagged, but did not change,** 1,475 monthly return figures that are really balance swings on small accounts, not investment performance, and 2,410 transactions dated after a client left. These need the committee's attention before they appear in performance or advisor metrics.

## What we changed

| # | Issue | Table | Rows | Action | How we know the fix is right |
|---|---|---|---:|---|---|
| A1 | Duplicate clients under new IDs | dim_client | 25 | Removed to quarantine | All fields match the original except the truncated last name; no fees, snapshots or trades used the duplicate IDs |
| A2 | State spelled out (`Pennsylvania`) | dim_client | 77 | Standardized to `PA` etc. | One-to-one mapping; per-state totals unchanged |
| A3 | Return stored as `9.28%` text | fact_portfolio_snapshot | 300 | Converted to 0.0928 Return − benchmark = alpha holds on all 300 rows only when read this way; recomputing return from balances confirms it independently (246 raw failures → 0) |
| A4 | Buys with negative share counts | fact_transactions | 835 | Sign corrected | Amount = shares × price matched exactly before the change |
| A5 | Transactions for non-existent clients | fact_transactions | 200 | Removed to quarantine ($10,888,495.37) | Client IDs 2,702–3,192; the client table ends at 2,525 |
| A6 | Security ID stored as `45.0` | fact_transactions | 197,044 | Standardized to `45` | Every value ended in `.0`; join to securities now 100% |
| B1 | Blank risk profile | dim_client | 75 | **Flagged** (`is_risk_profile_missing`) | Not filled; see judgment call 1 |
| B2 | YTD return > +100% or < −90% | fact_portfolio_snapshot | 1,475 | **Flagged** (`is_return_suspect`) | See judgment call 2 |
| B3 | Transaction after client left | fact_transactions | 2,410 | **Flagged** (`is_post_departure_txn`) | All 131 clients are marked inactive |

Rows: **raw 555,401 = clean 555,176 + quarantined 225**, proven for every table. Every changed cell (198,256) is logged with its old and new value.

### Data quality scorecard (raw → clean, fact_transactions and dim_client)

| Table | Measure | Raw | Clean |
|---|---|---:|---:|
| fact_transactions | Referential match | 81.95% | 100.00% |
| fact_transactions | Type validity | 90.55% | 100.00% |
| fact_transactions | Rule pass | 99.94% | 100.00% |
| fact_portfolio_snapshot | Type validity | 99.98% | 100.00% |
| fact_portfolio_snapshot | Rule pass | 99.96% | 100.00% |
| dim_client | Key uniqueness (incl. duplicate people) | 98.02% | 100.00% |
| dim_client | Rule pass | 99.66% | 100.00% |
| dim_client | Completeness | 99.79% | 99.79% |

The other four tables scored 100% on every measure at both stages. dim_client completeness does not rise, because we chose not to fill the 75 blank risk profiles.

## Key judgment calls

**1. Blank risk profiles were flagged, not filled.** Every one of the 75 clients is tracked against benchmark 3, which is otherwise used only by Balanced clients, so "Balanced" looks like an easy fill. We declined. The benchmark may simply be the system default for clients with *no* profile, which would make it a consequence of the blank, not evidence of the answer. Risk profile drives suitability, and a guessed value is a compliance exposure.
*Risk:* risk-profile reports show a 75-client "missing" bucket until advisors supply the profiles.

**2. Extreme returns were flagged, not recomputed.** All 178 affected clients are Retail; the median balance on these rows is $40k, against $485k overall. We confirmed that `return_ytd` is exactly the account balance divided by the prior December's balance, minus one (100% of 104,823 testable rows), so it measures **balance change, not investment return**. On a small account any balance jump becomes a huge "return": client 29 went from $9.1k to $52.1k in July 2022 and its YTD return from −32% to +287%. That jump is not explained by the transaction ledger (that client *withdrew* $53.6k that month), and across all accounts, monthly balance changes show no relationship to recorded deposits and withdrawals (correlation 0.001). A correct return needs cash flows that reconcile to balances, which this extract does not have.
*Risk:* if these rows are not excluded, one 9,467% return distorts the average for the entire Retail tier. **Recommendation:** exclude `is_return_suspect = 1` from every average-return figure.

**3. Advisory fee transactions were not reconciled to the fee table, and we used the fee table.** The 35,766 fee debits in the transaction ledger do not match billed fees at monthly, quarterly or annual totals. We cannot tell which system is wrong, so we changed neither. `fact_fees` is internally consistent: every fee equals AUM × rate ÷ 12, and every fee's AUM equals that month's snapshot. We treat it as the system of record.
*Risk:* fee revenue differs depending on which table a report uses. **Recommendation:** report fees only from `fact_fees`, and ask operations to explain the ledger difference.

**4. Quarantine, not deletion.** The 200 orphan transactions and the 25 duplicates sit in audit files with every original column, so they can be restored if the missing client records turn up.

## Limitations

- **Weekend trading:** 28.4% of buys and sells are dated on weekends, about the same share as weekend days on the calendar (28.6%). Trade dates appear to be booking dates, so day-of-week trading analysis is not meaningful.
- **Holiday calendar:** the date table marks market holidays (e.g. January 1) as trading days.
- **$1,000 balance floor:** 420 snapshots and 386 fee rows sit at exactly $1,000. This looks like a system minimum, not a real balance.
- **One fee above 100 bps** (100.38 bps, $0.34 above a 100 bps rate). It is left as recorded, because we know of no documented cap. It is the only rule that still fails after cleaning.
- **Negative-share buys** were treated as sign errors. If any were reversals, those trades are overstated; nothing in the data indicates a reversal.
- **Balances and transactions don't tie out:** monthly AUM changes are unrelated to recorded deposits and withdrawals (correlation 0.001). Use snapshots for balances and transactions for activity; don't derive one from the other.
- **Departed-client activity** (2,410 transactions, including 689 buys) is flagged, not explained. It needs operations review before it counts toward advisor activity.

---
`AI-assisted report — reviewed for factual accuracy on 10/25/2026 by Damin Lim`
