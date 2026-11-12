# HW6 Measure Library — Wildcat Capital

All measures live in the `_Measures` table of `powerbi/hw06.pbix`.
"Last snapshot" = `LASTNONBLANK(dim_date[date], CALCULATE(COUNTROWS(fact_portfolio_snapshot)))`, the last date in the current filter that has snapshot rows.

## Part A — Measures

| # | Measure | DAX | Pattern | What it means for a Wildcat manager |
|---|---|---|---|---|
| 0 | AUM (naive SUM) | `SUM ( fact_portfolio_snapshot[aum] )` | **Wrong on purpose** (SUM of a balance) | Adds every month's balance together, so it counts the same money 12+ times. Never use on a report. |
| — | Total Fees | `SUM ( fact_fees[amount] )` | SUM | Fees billed in the period. |
| — | Net Flows | `CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" ) - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )` | SUM | Net new money clients brought in. |
| 1 | Ending AUM | `CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )` | Last balance | How much we manage at the end of the selected period. |
| 2 | Ending Clients | `CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) )` | Last balance | How many clients we have at the end of the period. |
| 3 | Avg AUM per Client | `DIVIDE ( [Ending AUM], [Ending Clients] )` | Recompute (ratio of two last balances) | The typical relationship size today. |
| 4 | Ending AUM LY | `CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )` | Last balance, shifted | Balance one year earlier. |
| 4 | AUM YoY % | `DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )` | Recompute | How fast the book grew over the year (markets + flows). |
| 5 | Ending AUM PM | `CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )` | Last balance, shifted | Balance one month earlier. |
| 5 | AUM MoM % | `DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )` | Recompute | Month-on-month growth. |
| 6 | Avg Monthly AUM | `DIVIDE ( SUM ( fact_portfolio_snapshot[aum] ), DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] ) )` | Recompute (Σ balance ÷ # snapshots) | Average balance we carried during the period — the right base for fee yield. |
| 7 | Fee Yield (bps) | `DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )` | Recompute across two fact tables | Annualized fees earned per dollar managed. |
| 8 | Organic Growth Rate | `DIVIDE ( [Net Flows], [Ending AUM LY] )` | Recompute (flow ÷ last balance) | Growth from net new money only, excluding markets. |
| 9 | AUM-Weighted Alpha | `CALCULATE ( DIVIDE ( SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ), SUM ( fact_portfolio_snapshot[aum] ) ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ), fact_portfolio_snapshot[is_return_suspect] <> 1 )` | Recompute-and-weight, at last balance | Dollar-weighted outperformance vs benchmark, year to date. |
| 10 | Alpha Signal | `SWITCH ( TRUE (), ISBLANK ( [AUM-Weighted Alpha] ), BLANK (), [AUM-Weighted Alpha] >= 0.02, "Outperforming", [AUM-Weighted Alpha] <= -0.02, "Lagging", "In line" )` | Label on a recomputed value | A one-word verdict a manager can scan. |
| 11 | Top 10 Client Share | `DIVIDE ( CALCULATE ( [Ending AUM], TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] ) ), [Ending AUM] )` | Recompute at last balance | Concentration risk: share of today's AUM held by the 10 biggest clients in the selection. |

Formats: currency for AUM measures; % (2 dp) for YoY, MoM, Organic Growth, Alpha, Top 10 share; 1 dp for bps; whole number for clients.

## Part C — Design questions

**(a) Ending AUM vs SUMX over clients.** With no filters, `Ending AUM` = **$12,729,572,078.86**. `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` = **$13,149,297,713.80**, which is **$419,725,634.94** larger. SUMX iterates clients, and for each client `[Ending AUM]` finds *that client's own* last snapshot. 175 clients left before December 2024, so SUMX adds their last balances (exactly $419,725,634.94) even though Wildcat no longer manages that money. `Ending AUM` answers "How much do we manage today?" because it uses one firm-wide last date (Dec 2024).

**(b) Fee Yield vs Effective Fee Rate (2024).** Fee Yield = **43.15 bps**; ICE 9 Effective Fee Rate = **45.53 bps**. Same fees in the numerator; the difference is the denominator. In pandas, every fee row's `aum_basis` equals that client-month's snapshot `aum` exactly ($128,385,303,527 on both sides). But **1,684 client-months in 2024 have a snapshot and no fee row**, so snapshot AUM ($135,459,843,784) includes about **$7.07B** of balance that was never billed. Data limitation: `fact_fees` does not have a fee record for every account every month (missing/unbilled fee records), so fees cannot be tied to all managed AUM; Effective Fee Rate only measures billed AUM.

**(c) Why last snapshot only, and why exclude suspects.** `active_alpha_ytd` is year-to-date: January holds one month of alpha, December the full year. Averaging across months mixes partial years — weighting all months gives **0.38%** vs **1.45%** at the last snapshot. `is_return_suspect = 1` rows are data errors: 148 rows at the last date, with alpha as high as **71.34 (7,134%)**, and because weighting is by AUM a few bad rows move the firm number. At the last snapshot (Dec 2024):
- AUM-weighted, suspects excluded: **1.448%**
- Simple mean, same rows: **0.879%** (big clients outperform small ones)
- AUM-weighted, suspects included: **1.668%**

**(d) Organic Growth by tier, 2024.**

| Tier | Ending AUM | AUM YoY % | Organic Growth |
|---|---:|---:|---:|
| UHNW | $9.65B | 19.59% | 0.10% |
| HNW | $2.55B | 19.64% | 1.18% |
| Retail | $0.53B | 19.13% | 9.87% |

All tiers grew ~19–20%, but almost none of that came from net new money: AUM YoY minus organic growth is ~18–19 points of market return in UHNW and HNW. Retail is the only tier where clients are adding real money (9.87%), but it is 4% of AUM. UHNW, 76% of AUM, is essentially flat on flows. What it does **not** tell you: whether clients moved between tiers, the dollar size of flows, fee profitability by tier, or *why* money came in or left. It also doesn't separate market return from other effects (e.g. dividends or fee deductions inside AUM).
