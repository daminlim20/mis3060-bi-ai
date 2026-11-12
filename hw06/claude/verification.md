# Part D — Verification of Claude's AUM-Weighted Alpha

**Did it run as written?** No. The first draft (with `VAR LastDate`) gave "The syntax for 'LastDate' is incorrect" when pasted into Power BI. The logic was fine; the pasted VAR line carried hidden characters. I used Claude's one-line rewrite without VAR, which ran. The test query (`SUMMARIZECOLUMNS` by year) returned one value and signal per year, matching the year table on the Measures page.

**Rows of `measure_reconciliation.csv` that prove it** (pandas recomputed independently from the CSVs):

| slice | pandas value | signal |
|---|---:|---|
| Total | 0.014480 | In line |
| 2020 | -0.006802 | In line |
| 2021 | -0.001574 | In line |
| 2022 | 0.028494 | Outperforming |
| 2023 | 0.017689 | In line |
| 2024 | 0.014480 | In line |
| HNW 2024 | 0.013988 | In line |
| Retail 2024 | 0.024041 | Outperforming |
| UHNW 2024 | 0.014097 | In line |

**Edge cases checked**
1. **Grand total** — with no year filter, the last date is 2024-12-01, so Total must equal 2024 (both 0.01448). It does: the measure is not averaging across 60 months.
2. **2022** — the only year above +2%, so it tests the Alpha Signal "Outperforming" branch (0.0285).
3. **2024 tier table** — the tier filter flows through `dim_client` to the snapshot; Retail 2024 (0.0240) crosses the +2% threshold while the firm is "In line", so the filter context is respected rather than returning the firm value.
4. **Blank alpha** — checked in pandas: no `active_alpha_ytd` is blank, so dropping Claude's `NOT ISBLANK` filter changes nothing.

**What I changed and why:** removed `VAR` (paste error), switched `SUM(aum)` to `COUNTROWS` in the LASTNONBLANK test to match the existing `Ending AUM` (same last date), dropped the redundant `NOT ISBLANK`.

**One claim confirmed:** Claude said a few suspect rows would dominate the weighted value. Confirmed in pandas: at Dec 2024 there are 148 suspect rows with alpha up to 71.34, and including them moves the firm figure from **1.448% to 1.668%**.
