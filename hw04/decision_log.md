# HW4 Decision Log: Wildcat Capital Data Cleaning

Written **before** the cleaning code (Part C). Each entry is the spec for one transformation in `scripts/02_clean.py`.
Evidence comes from `reports/dq_summary_raw.csv` / `reports/profile_raw.csv` (run of `scripts/01_profile.py`) and the follow-up checks noted in each entry.

**Audit result on raw data:** 340 checks: 317 PASS · 6 ERROR · 7 WARN · 10 INFO.

## Order of operations (and why)

1. **Dimensions first, facts second.** Fact checks (foreign keys, advisor/benchmark agreement) depend on the dimensions being right.
2. **Remove rows before fixing values.** Quarantining duplicate clients and orphan transactions first means no effort goes into repairing rows that will be removed, and row-count proofs stay simple.
3. **Type/format fixes before rule fixes.** `security_id` must be a clean integer and `return_ytd` a clean decimal before range or reconciliation checks mean anything.
4. **Flags last.** Flags are computed on the cleaned values so they describe the final data.

Decisions are grouped: **A. defects fixed**, **B. suspicious rows flagged**, **C. legitimate structure left as is**.

---

## A. Defects: fix or quarantine

### A1. Duplicate clients under new IDs
| Field | Entry |
|---|---|
| **Table / column** | `dim_client`, whole row (`client_id` 2501–2525) |
| **Evidence** | 25 clients appear twice (50 rows). IDs 2501–2525 match an original client on `first_name, age, city, zip_code, client_since, initial_aum` and every other field; only `last_name` differs, and it is the original truncated (`Taylo` vs `Taylor`; 23 of 25 are clean prefixes). IDs 2501–2525 are used by **0** fact rows. |
| **Dimension violated** | Uniqueness, Accuracy (truncated name) |
| **Decision** | **Quarantine** the 25 rows with IDs 2501–2525 → `quarantine_dim_client_duplicates.csv`, with the matching original `client_id` added for traceability. |
| **Justification** | One real person must be one client, or client counts, AUM per advisor and tier mix are overstated by 25. The originals are the complete records (full last name) and are the ones the facts reference, so nothing is lost by dropping the copies. |
| **Risk** | If any of the 25 were truly different people (same first name, age, city, ZIP, start date and AUM to the cent), we would lose a client. The 7-field exact match makes this very unlikely. Verify after the fix: 2,500 clients, all `client_id` unique, no fact orphans created. |

### A2. Full state names instead of codes
| Field | Entry |
|---|---|
| **Table / column** | `dim_client.state` |
| **Evidence** | 78 rows fail the allowed-values check: `Pennsylvania` (25), `Florida` (15), `New York` (14), `New Jersey` (13), `California` (5), `Illinois` (4), `Texas` (2). The other 2,447 use 2-letter codes. |
| **Dimension violated** | Consistency, Validity |
| **Decision** | **Standardize** to USPS 2-letter codes with an explicit 7-entry mapping. |
| **Justification** | Clients by state would otherwise split PA into "PA" and "Pennsylvania". The mapping is unambiguous (a state name has exactly one code), so no data is invented. |
| **Risk** | Very low. Assert afterwards that 100% of values are in the US state list and that per-state counts equal old code + old full name (e.g. PA = 414 + 25 = 439). |

### A3. `return_ytd` stored as percent text
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | 300 values are strings like `9.28%` / `-3.18%`; the other 129,247 are decimals (`0.0928`). |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Convert**: strip `%` and divide by 100. |
| **Justification** | **Verified, not assumed:** in the same rows, `return_ytd − benchmark_return_ytd = active_alpha_ytd` holds for all 300 when `9.28%` is read as 0.0928, and fails if read as 9.28. So the % rows are the same unit, just formatted differently. |
| **Risk** | If they were meant as 9.28 (i.e. 928%), we would understate returns, but the alpha reconciliation rules that out. Assert after: column 100% numeric, alpha reconciliation passes on all 129,547 rows within 0.0001 (the % strings are rounded to 2 decimals). |

### A4. Buys with negative share counts
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.shares` (`txn_type = Buy`) |
| **Evidence** | 836 Buy rows have `shares < 0`. All Sells and Dividends are positive. For these 836 rows `amount = |shares| × price` reconciles exactly (0 rows off by more than $0.01), and `amount` is positive. |
| **Dimension violated** | Validity (sign rule), Consistency |
| **Decision** | **Convert**: `shares = abs(shares)` for those rows; log every change in `value_changes.csv`. |
| **Justification** | The table's convention is positive shares with direction carried by `txn_type`. The amount proves the size of the trade is right, so only the sign is wrong. Leaving it would make share-position sums wrong (a Buy would reduce holdings). |
| **Risk** | If the negative sign meant "this buy was reversed/cancelled", we would count trades that never happened. Nothing else in the row (type, amount sign) suggests a reversal. Note it as a limitation. |

### A5. Transactions for clients that do not exist
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.client_id` |
| **Evidence** | 200 rows (`txn_id` 298,573–298,772, the last 200 rows of the file) have `client_id` 2,702–3,192; `dim_client` stops at 2,525. 200 distinct orphan keys (one row each), spread across all six txn types. |
| **Dimension violated** | Referential Integrity |
| **Decision** | **Quarantine** → `quarantine_fact_transactions_orphan_client.csv` (all original columns plus a reason column). |
| **Justification** | A transaction with no client can't be attributed to an advisor's book, a tier or a state, and in Power BI it would land in a "(Blank)" client. The contiguous block at the end of the file suggests a separate load, not real clients. We cannot invent which client they belong to. |
| **Risk** | If these are real clients missing from `dim_client`, about $10.89M of transaction amount ($10,888,495.37 gross, all types) disappears from reports. Quarantine (not delete) keeps them recoverable. |

### A6. `security_id` stored as decimal text
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.security_id` |
| **Evidence** | All 197,175 non-blank values look like `45.0`; `dim_security.security_id` is `45`. Every value ends in `.0` (the profiler shows a single format, `9.9`). The pattern means the file was saved by a tool that turned the column into decimals because of its blanks. |
| **Dimension violated** | Validity, Consistency (key format differs across tables) |
| **Decision** | **Standardize**: strip the trailing `.0` → whole-number text. Blanks stay blank (see C3). |
| **Justification** | Text `45.0` will not join to `45` in Power BI or a text merge, so all trades would look like orphans. |
| **Risk** | None if every value really ends in `.0`; assert that before stripping, so a value like `45.5` would stop the script. Assert after: FK match to `dim_security` = 100% of non-blank keys. |

---

## B. Suspicious: keep the row, add a 0/1 flag

### B1. Blank `risk_profile`
| Field | Entry |
|---|---|
| **Table / column** | `dim_client.risk_profile` |
| **Evidence** | 76 blanks (75 after A1 removes one duplicate). Every snapshot for these clients uses `benchmark_id = 3` (3,942 rows), and benchmark 3 is otherwise used **only** by Balanced clients. |
| **Dimension violated** | Completeness |
| **Decision** | **Flag** `is_risk_profile_missing = 1`; **leave the value blank** (do not fill). |
| **Justification** | **Judgment call.** Filling "Balanced" is tempting, but benchmark 3 may simply be the system's *default* for clients with no profile, so the benchmark could be a consequence of the blank, not evidence of the true value. Risk profile is suitability data, and inventing it is a compliance problem. The flag lets the committee count and chase the 75 clients. |
| **Risk** | Risk-profile reports show a "(Blank)" bucket of 75 clients. Alternative considered: fill as Balanced with a flag, which is rejected because it can't be verified from an independent source. |

### B2. Implausible YTD returns
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (and `active_alpha_ytd`) |
| **Evidence** | 1,475 rows (178 clients) have YTD return > +100% or < −90% (max 9,467%). **All 178 are Retail**; median AUM of these rows is $40k vs $485k overall. In the examples, return jumps exactly when AUM jumps from a deposit (e.g. client 29: AUM $9k → $52k, return −32% → +287%). Alpha still reconciles on these rows (1,473 of 1,475 rows). |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag** `is_return_suspect = 1`; leave the value. |
| **Justification** | The numbers are arithmetically consistent, so the defect is in *how* return was calculated upstream (deposits counted as performance on small balances), not in the stored digits. We cannot recompute a true time-weighted return without daily cash-flow timing, so we don't change it. The flag lets the committee exclude these from average-return figures. |
| **Risk** | If not excluded, one client's 9,467% return distorts average returns for the whole Retail tier. If some are real (unlikely above 100% in a year), the flag only warns; it removes nothing. |

### B3. Transactions after a client left
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.txn_date` vs the client's last snapshot |
| **Evidence** | 2,410 transactions for 131 clients are dated after that client's last monthly snapshot (28–390 days later, median 116). **All 131 clients have `is_active = False`**, and every inactive client's snapshots stop before Dec 2024 while every active client's run through Dec 2024. They include Buys (689) and Dividends (439), not just closing withdrawals. |
| **Dimension violated** | Consistency (cross-table), Accuracy |
| **Decision** | **Flag** `is_post_departure_txn = 1`; keep the rows. |
| **Justification** | A departed client buying securities months later is a red flag (late postings, mis-keyed client, or an account that wasn't really closed). It needs investigation, not deletion, because the money may be real. |
| **Risk** | If left unflagged, activity and fees for "inactive" clients inflate advisor metrics. If we quarantined them and they were real late postings, cash reports would be wrong. |

---

## C. Legitimate structure / accepted: leave as is (documented)

| # | Table.column | Evidence | Dimension | Decision | Justification | Risk |
|---|---|---|---|---|---|---|
| C1 | `dim_security.sector` | 219 blanks, **all** ETFs (is_etf = True) | Completeness | Leave as is | An ETF holds many sectors; blank is correct. Row rule "sector blank only for ETFs" passes 100%. | BI shows "(Blank)" sector; label it "Multi-sector / ETF" in the report layer. |
| C2 | `dim_security.expense_ratio_bps` | 281 blanks, **all** individual stocks | Completeness | Leave as is | Stocks have no expense ratio; filling 0 would be invented. Rule passes 100%. | Averages must ignore blanks, not count them as 0. |
| C3 | `fact_transactions.security_id/shares/price` | 101,597 blanks in **exactly the same rows**, all Deposit / Withdrawal / Advisory Fee | Completeness | Leave as is | Cash flows and fee debits have no security. Rule "cash flows must not have a security" passes 100%. | The FK null rate is 34%, by design; the RI check must treat blank ≠ orphan. |
| C4 | `dim_advisor.certifications` | 6 advisors = literal `None` | Validity | Leave as is | Means "holds no certification", a real category, not missing data. | If a BI tool reads "None" as null, these advisors vanish from a certification filter. Set column type = Text. |
| C5 | `fact_fees.bps_charged` | 1 row = 100.38 bps (fee_id 68809, client 1402; that client's next-highest is 94.14 bps) | Plausibility | Leave as is | No documented 100 bps cap; amount reconciles to AUM × bps ÷ 12 exactly. | If a 100 bps cap exists, the client was overcharged ~$0.34. Document as known limitation. |
| C6 | `aum` / `aum_basis` = 1,000.00 | 420 snapshot / 386 fee rows exactly $1,000 | Plausibility | Leave as is | Looks like a system minimum-balance floor; fees reconcile to it. | Low-balance accounts slightly overstated; contributes to B2's extreme returns. |
| C7 | Buy/Sell on non-trading days | 40,649 trades (28.4%) on weekends; weekends are 28.6% of calendar days | Plausibility | Leave as is | Trades are spread evenly over **all** calendar days, so this is how the source system dates them (likely booking date), not isolated bad rows. Flagging 28% of trades has no investigative value. | Day-of-week analysis is meaningless; documented as limitation. |
| C8 | Advisory Fee txns vs `fact_fees` | 33,469 of 35,766 fee debits don't equal that month's fee total; no match at monthly, quarterly (only 1% of client-quarters within 1%) or annual (5% within 5%) grain | Consistency | Leave as is | Two systems with different timing/aggregation; we cannot tell which is right, so we don't "fix" either. `fact_fees` is the billing system of record. | Fee revenue differs by source: report fees **only** from `fact_fees`. |
| C9 | `dim_date.is_trading_day` | Every weekday = 1, including market holidays (e.g. Jan 1) | Accuracy | Leave as is | Calendar logic is otherwise 100% correct; a holiday calendar is outside this data. | Trading-day counts slightly overstated. |
| C10 | `active_alpha_ytd`, `return_ytd` scientific notation | ~900 values like `1.2e-05` | Validity (format only) | Leave as is | Valid numbers; every BI tool parses them once the type = Decimal. | None after type conversion. |
| C11 | `dim_client.zip_code` | 232 ZIPs start with 0 (e.g. `03897`) | Validity (type) | Leave as text | ZIP is an identifier, not a number. | Must be set to Text in Power BI or leading zeros vanish. |

---

## Post-run reconciliation (added after running `02_clean.py`)

The entries above were written before the cleaning code and are left unchanged. Running the code in the order defended at the top changed three counts, because rows quarantined first no longer need fixing:

| Entry | Count in raw audit | Rows changed in `cleaning_log.csv` | Difference explained by |
|---|---:|---:|---|
| A2 state names | 78 | 77 | 1 duplicate client (A1) had a full state name |
| A4 negative shares | 836 | 835 | 1 orphan transaction (A5) had negative shares |
| A6 `security_id` `45.0` | 197,175 | 197,044 | 131 orphan transactions (A5) had a security_id |

The A2 check "PA = 414 + 25 = 439" becomes **PA = 434** after A1 removes 5 duplicate PA clients; the script asserts that per-state totals are preserved by the mapping itself. Every other count (25, 75, 300, 1,475, 200, 2,410) matched the log exactly.

### Correction to B2 evidence (found while writing the Part E report)

B2 originally said the extreme returns come from "deposits counted as performance". Checking that against the transaction ledger **disproved it**: client 29's balance jump (July 2022) happened in a month with a $53.6k *withdrawal*, and across all accounts monthly AUM changes have a correlation of **0.001** with that month's deposits − withdrawals. What *is* verified: `return_ytd` = AUM ÷ prior-December AUM − 1 on **100% of 104,823** rows that have a prior December (now reconciliation R3b in `03_validate.py`). So `return_ytd` measures balance change, not investment return, and balances do not reconcile to recorded flows. **The decision (flag, don't recompute) is unchanged and better supported**: without flows that tie to balances, a true return can't be computed. Added as limitation 10 in `README_clean.md`.
