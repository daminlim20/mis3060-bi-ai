# HW5 — Wildcat Capital Star Schema Design
MIS3060 Business Intelligence with AI

All claims below are verified by `hw05_checks.py` (55 checks, all passing).

---

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` (`date` is also unique) | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(can be blank)*<br>`txn_date` → dim_date[date] |

**Notes**
- All eight primary keys are unique and never blank.
- No foreign key has an orphan: every value exists in the table it points to.
- The fact dates are calendar dates (`2023-12-16`), so they match `dim_date[date]`, not `dim_date[date_id]`. Every fact date falls inside the date table's range (2020-01-01 to 2024-12-31).
- `fact_transactions[security_id]` is legitimately blank on 101,528 rows. All of them are cash rows (Deposit, Withdrawal, Advisory Fee), where no security changes hands. No other key is ever blank.
- Two foreign keys link one dimension to another: `dim_client[advisor_id]` → `dim_advisor` and `dim_security[benchmark_id]` → `dim_benchmark`.

---

## Part B — Grain

- **fact_fees:** One row represents one fee charged to one client in one month (dated the first of the month), with its fee type, the AUM it was charged on, and the rate.
- **fact_portfolio_snapshot:** One row represents the month-start state of one client's account: its AUM, year-to-date return versus its benchmark, and cash share on that date.
- **fact_transactions:** One row represents one individual transaction event (a buy, sell, dividend, deposit, withdrawal or advisory fee debit) for one client on one date, identified by `txn_id`.

**Evidence (`hw05_checks.py`, section 4)**
- `client_id` + `fee_date` and `client_id` + `snapshot_date` have no repeated combinations, and every monthly row is dated the 1st.
- In transactions, no row is an exact copy of another (apart from `txn_id`), so nothing was loaded twice. Even so, among trade rows (where `security_id` is always filled) `client_id` + `txn_date` + `txn_type` + `security_id` repeats 94 times: a client can make the same kind of trade in the same security more than once on a day. So there is no natural key, and only `txn_id` identifies a row. (Counting cash rows as well gives 622 repeats, but 528 of those depend on treating two blank `security_id` values as equal, which SQL and Power BI do not do.)
- 7,350 client-months have a snapshot but no fee, so the two monthly facts do not line up row for row.

The two monthly tables are **periodic snapshots**, and `fact_transactions` is a **transaction fact**. That difference drives the classifications in Part C.

---

## Part C — Measures

**Test used:** if I add this value across clients, across months, or across both, what does the total represent?

### Fact measures

| Fact table | Column | Type | What it means for summing or averaging |
|---|---|---|---|
| fact_fees | `amount` | **Additive** | The dollars charged can be summed across clients, advisors, fee types and months; the total is fee revenue. |
| fact_fees | `aum_basis` | **Semi-additive** | It's the account balance the fee was charged on, so it can be summed across clients within one month but not across months. Over time, use the last value or the average. |
| fact_fees | `bps_charged` | **Non-additive** | It's a rate, so summing is meaningless. The effective rate is total `amount` ÷ total `aum_basis` × 12 × 10,000, or an average weighted by `aum_basis`. |
| fact_portfolio_snapshot | `aum` | **Semi-additive** | A month-start balance, so it can be summed across clients and advisors for a single month (firm AUM). Summing across months counts the same money again each month. Over time, take the last month or the average. |
| fact_portfolio_snapshot | `return_ytd` | **Non-additive** | A cumulative percentage that resets each January. It can't be summed across clients or months. Average it weighted by `aum`, or use the latest month in each year. |
| fact_portfolio_snapshot | `benchmark_return_ytd` | **Non-additive** | Same as `return_ytd`: a cumulative percentage, so it can't be summed in any direction. |
| fact_portfolio_snapshot | `active_alpha_ytd` | **Non-additive** | The difference of two YTD returns, so it's a percentage-point spread. Average it weighted by `aum`, or recompute it as return minus benchmark. |
| fact_portfolio_snapshot | `cash_pct` | **Non-additive** | A share of the account. A sum can exceed 100%, which is meaningless. Average it weighted by `aum`. |
| fact_transactions | `amount` | **Additive, within `txn_type`** | Dollar flows add up across clients, securities and dates, but every value is positive and direction is only in `txn_type`. So always sum within a type (or flip the sign on Withdrawals, Sells and Fees). A grand total that mixes deposits and withdrawals means nothing. |
| fact_transactions | `shares` | **Additive, within one security** | Share counts add up over time and across clients for the same security and transaction type. Adding shares of different securities gives a meaningless number. Blank on cash rows. |
| fact_transactions | `price` | **Non-additive** | A per-share price. Summing is meaningless; the average trade price is Σ`amount` ÷ Σ`shares`. Blank on cash rows. |

**Evidence (`hw05_checks.py`, section 5)**
- `fact_fees[amount]` = `aum_basis` × `bps_charged` ÷ 10,000 ÷ 12 on every row.
- `fact_fees[aum_basis]` equals the client's snapshot `aum` for the same month on every row.
- `active_alpha_ytd` = `return_ytd` − `benchmark_return_ytd` on every row.
- In transactions, `amount` = `shares` × `price` on Buy, Sell and Dividend rows, and every amount is positive.

### Numeric columns that are not measures

| Table | Columns | Why |
|---|---|---|
| fact_fees | `fee_id`, `client_id`, `advisor_id` | Keys: summing an ID is meaningless. They're only for counting and joining. |
| fact_portfolio_snapshot | `snapshot_id`, `client_id`, `advisor_id`, `benchmark_id` | Keys |
| fact_portfolio_snapshot | `year`, `month` | Date parts, copied from `snapshot_date`. Filter and group by them using `dim_date`. |
| fact_portfolio_snapshot | `is_return_suspect` | A 0/1 flag for filtering out bad returns. Summing it only counts flagged rows. |
| fact_transactions | `txn_id`, `client_id`, `advisor_id`, `security_id` | Keys |
| fact_transactions | `is_post_departure_txn` | A 0/1 flag. Summing it only counts flagged rows. |

### Numeric attributes in dimension tables that should never be summed

| Table | Column | Why |
|---|---|---|
| dim_advisor | `years_experience` | A descriptive attribute. Average it or group by it. |
| dim_advisor | `aum_target_mm` | A target, not an actual amount. Compare it with real AUM; don't add targets together. |
| dim_client | `age` | A descriptive attribute. Average it or put it into bands. |
| dim_client | `zip_code` | A code that only looks like a number. It should be Text. |
| dim_client | `initial_aum` | The balance on the day the client joined. It's a fixed starting point, not a flow, and real AUM comes from the snapshot fact. |
| dim_date | `date_id`, `year`, `quarter`, `month`, `week_of_year`, `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day` | Key, calendar parts and flags: used for grouping and filtering. |
| dim_security | `benchmark_id` | Key |
| dim_security | `expense_ratio_bps` | A rate. Average it, weighted by holdings if possible. Blank for non-ETFs. |
| dim_advisor, dim_benchmark, dim_client, dim_security | the `*_id` primary keys | Keys |

---

## Part E — Relationships and design questions

### Model summary
The model has **12 active relationships and 1 inactive one**. All are many-to-one with single-direction filtering, from the dimension to the fact. `dim_date` is marked as the date table on its `date` column.

| # | From (many side) | To (one side) | Active |
|---|---|---|---|
| 1 | fact_fees[client_id] | dim_client[client_id] | Yes |
| 2 | fact_fees[advisor_id] | dim_advisor[advisor_id] | Yes |
| 3 | fact_fees[fee_date] | dim_date[date] | Yes |
| 4 | fact_portfolio_snapshot[client_id] | dim_client[client_id] | Yes |
| 5 | fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Yes |
| 6 | fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Yes |
| 7 | fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Yes |
| 8 | fact_transactions[client_id] | dim_client[client_id] | Yes |
| 9 | fact_transactions[advisor_id] | dim_advisor[advisor_id] | Yes |
| 10 | fact_transactions[security_id] | dim_security[security_id] | Yes |
| 11 | fact_transactions[txn_date] | dim_date[date] | Yes |
| 12 | dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Yes |
| 13 | dim_client[advisor_id] | dim_advisor[advisor_id] | **No (inactive)** |

**Conformed dimensions:** `dim_client`, `dim_advisor` and `dim_date` each connect to all three fact tables, so one slicer on any of them filters fees, snapshots and transactions together. `dim_benchmark` is shared by two facts: snapshots link to it directly, and transactions reach it through `dim_security`. `dim_security` is used only by `fact_transactions`.

**Model checks in Power BI:** the row counts of all eight tables match the handout. A `dim_security[ticker]` × `fact_transactions[amount]` table shows exactly one `(Blank)` row, which is the cash rows. A slicer on `dim_advisor` filters all three facts.

### (a) Why do some transactions have no `security_id`? Is that a defect?
101,528 transactions have no `security_id`. All of them are Deposits, Withdrawals or Advisory Fee debits, which move cash in or out of the account without buying or selling a security. The check script shows the rule holds in both directions: every cash row is blank, and every Buy, Sell and Dividend row has a security. So this is not a defect. Power BI shows these rows as a single `(Blank)` member of `dim_security`, which is the cash rows, not a broken key. An alternative design would add a "Cash" member to `dim_security`, but this assignment does not allow new rows.

### (b) Which `advisor_id` relationship(s) did you keep active, and why?
I kept the three direct relationships from each fact's `advisor_id` to `dim_advisor` active, and made `dim_client[advisor_id]` → `dim_advisor` inactive. Power BI allows only one active path between two tables. With both kept, `dim_advisor` could reach each fact directly and also through `dim_client`. I kept the direct links for three reasons:
- Each fact is one hop from the advisor, which keeps the model a clean star.
- The advisor is recorded on each event itself, so if a client is ever reassigned, past fees and trades stay with the advisor who had them at the time.
- The check script found 0 mismatches between each fact's advisor and the client's advisor in `dim_client`, so both paths give identical numbers today. This includes the 2,410 transactions flagged `is_post_departure_txn`.

The inactive relationship stays in the model, so a later DAX measure can use it with `USERELATIONSHIP` if a "current advisor" view is ever needed.

### (c) Which date column did you join on, and why?
I joined `fee_date`, `snapshot_date` and `txn_date` to `dim_date[date]`, not to `dim_date[date_id]`. The facts store calendar dates such as `2023-12-16`. `date_id` is just a row number from 1 to 1,827 that never appears in any fact, so joining on it would match nothing, and every fact row would show as `(Blank)`. Both sides are typed as Date (not Date/Time) so the values match exactly. `date` is also the column I marked as the date table, which time-intelligence functions in Assignment 6 require.

### (d) Star or snowflake? Did you keep the dimension-to-dimension links?
Two foreign keys connect one dimension to another: `dim_client` → `dim_advisor` and `dim_security` → `dim_benchmark`. I kept both but treated them differently:
- **`dim_client` → `dim_advisor` is inactive.** The facts already carry `advisor_id` directly, so the advisor part of the model stays a star.
- **`dim_security` → `dim_benchmark` is active.** `fact_transactions` has no `benchmark_id`, so this link is the only way to slice trades by benchmark or asset class. That makes it a small snowflake branch.

The result is mostly a star, with one snowflake arm. One caveat: `dim_benchmark` means two different things in this model. For snapshots it is the *portfolio's* benchmark; for transactions it is the *security's* benchmark. A benchmark slicer filters both, so a report should label which one it means.

---

## Part F — Reflection

| Fact table | Business question | One visual, no DAX? |
|---|---|---|
| fact_fees | *How much fee revenue did each advisor bring in during 2024, by fee type?* | **Yes** |
| fact_portfolio_snapshot | *What was total firm AUM at the end of each quarter, and how did each advisor's book grow?* | **No** |
| fact_transactions | *What were net client flows (deposits minus withdrawals) each month, by advisor?* | **No** |

**1. Fee revenue: answerable.** `fact_fees[amount]` is fully additive. A matrix with `dim_advisor[last_name]` on rows, `fee_type` on columns, Sum of `amount` as the value, and a `dim_date[year]` slicer set to 2024 gives the right answer. Every relationship it needs is a single active hop.

**2. Quarterly AUM: not answerable.** `aum` is semi-additive. If you put `dim_date[quarter]` on a visual, Power BI sums three monthly balances and shows roughly three times the real AUM. The fix is to filter to one month per quarter. But the snapshots are dated the 1st, and the date table's `is_quarter_end` flag marks the 31st, so the flag never matches a snapshot. I checked all 60 snapshot dates, and none of them has `is_month_end`, `is_quarter_end` or `is_year_end` set. Today this needs a DAX measure (for example `LASTDATE` or `CLOSINGBALANCEQUARTER`). The same applies to returns: `return_ytd` needs an AUM-weighted average, which also takes DAX.

*Schema fix:* date the snapshots at month-end, the moment the balance actually describes, or add an `is_snapshot_quarter_end` flag to `dim_date` (or to the fact). Then a simple filter picks the right month, and the sum across clients is correct.

**3. Net flows: not answerable.** Every `amount` in `fact_transactions` is positive, and direction lives only in `txn_type`. Summing Deposits and Withdrawals together *adds* them. You could show them as two side-by-side columns and subtract in your head, but a single "net flow" number needs a DAX measure.

*Schema fix:* store a signed amount (negative for Withdrawals, Sells and Fee debits), or add a small `dim_txn_type` table with a `sign` column (+1 or −1) and a `category` column (Trade, Cash flow, Fee).

**Honest assessment:** the model handles additive questions well: fee revenue, trade volume, counts by advisor, client or security. It handles balances, rates and signed flows poorly. Those questions need DAX in Assignment 6 or the schema changes above. A smaller issue is that `dim_benchmark` means two things: the portfolio's benchmark for snapshots and the security's benchmark for trades. A benchmark slicer filters both, so a report has to say which one it means.
