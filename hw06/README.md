# HW6 — DAX Measure Library: AUM & Performance

## Structure
```
hw06/
├── README.md
├── powerbi/
│   ├── hw06.pbix              # posted star model + _Measures table + "Measures" report page
│   ├── measures.md            # Part A documentation + Part C answers
│   └── export_values.dax      # DAX query view: exports every measure/slice to powerbi_values.csv
├── scripts/
│   └── 01_reconcile_measures.py
├── reports/
│   ├── powerbi_values.csv         # exported from Power BI (measure, slice, value)
│   ├── pandas_values.csv          # pandas side only
│   └── measure_reconciliation.csv # measure, slice, powerbi_value, pandas_value, abs_diff, match
└── claude/
    ├── model_metadata.md
    ├── dax_session.md
    └── verification.md
```

## How to run
1. In Power BI DAX query view, run `powerbi/export_values.dax`; save the result grid as `reports/powerbi_values.csv` (headers `measure,slice,value`).
2. From `hw06/`:
   ```
   python scripts/01_reconcile_measures.py --data "../../../HW05"
   ```
   `--data` points at the Wildcat Capital Clean CSVs. The script recomputes every measure in pandas without reading Power BI, then joins to the Power BI export. Tolerance: 0.01 for currency and bps, 0.0001 for ratios, exact for counts and text. It also prints the Part C evidence.

## Coverage
89 rows: every measure at the grand total; measures 0, 1, 4, 6–10 by year (2020–2024); measures 1, 3, 4, 7–11 by client tier for 2024; measure 5 for December 2024. `AUM (naive SUM)` is included to show pandas and DAX make the same mistake (Total = $566.7B vs real Ending AUM of $12.7B).

## Results
**42 of 42 Power BI values match** (`reports/measure_reconciliation.csv`). The 42 values were read from the cards and tables on the **Measures** page (all grand-total cards; Ending AUM, AUM YoY %, Avg Monthly AUM, Fee Yield, Organic Growth by year; Ending AUM, Avg AUM per Client, AUM YoY % by tier 2024). Percentages were transcribed at the displayed precision (2 dp), which is inside the 0.0001 tolerance. The DAX query-view export of all 89 slices (`powerbi/export_values.dax`) was not run before the deadline; `reports/pandas_values.csv` holds the pandas side for all 89.

## Mismatches and fixes
- The `Wildcat Capital` CSV folder is an older export without `is_return_suspect`; the script failed on it. Fixed by pointing `--data` to the clean CSVs in `HW05`.
- Grand-total time intelligence: `SAMEPERIODLASTYEAR` over the full calendar maps to 2020–2023, so Ending AUM LY at Total = Dec 2023 balance; `DATEADD -1 month` at Total ends Nov 2024. The pandas side reproduces both explicitly.

## Claude Code review
Claude Code (VS Code) reviewed `scripts/01_reconcile_measures.py`, ran it on a scratch copy against `C:\MIS3060\HW05` (no repo files changed), and reproduced "42 rows, 42 match". Findings:

1. **High — about half the measures are never reconciled.** The script computes 89 rows but `powerbi_values.csv` has 42; the inner join (line ~182) silently drops the other 47. Never checked against Power BI: AUM (naive SUM), AUM MoM %, AUM-Weighted Alpha, Alpha Signal; missing slices: 2024-12 (measure 5) and Fee Yield, Organic Growth Rate, Top 10 Client Share by tier. The inner join would also hide a misspelled measure name. Fix: outer join with `indicator=True` and treat `left_only`/`right_only` as failures.
   - **Action:** not fixed before the deadline. The 42/42 result is reported as partial coverage, not full reconciliation.
2. **High — `powerbi_values.csv` did not come from `export_values.dax`.** The query outputs 10-decimal values for ~89 rows; the CSV was transcribed from the report page at display precision.
   - **Action:** documented above. Next step: run `export_values.dax` in DAX query view, replace the CSV, switch to the outer join, and re-run.
3. Still checking at commit time: null `active_alpha_ytd` in earlier years, and Top-10 ranking for the Total slice.
