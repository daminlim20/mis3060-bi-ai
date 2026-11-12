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
Claude Code reviewed `scripts/01_reconcile_measures.py` before the final commit. Findings and actions:

| # | Claude Code flagged | What I did |
|---|---|---|
| 1 | Running against the `Wildcat Capital` folder crashed (`no attribute 'is_return_suspect'`): that export predates the cleaning step | Pointed `--data` at the clean CSVs in `HW05`; documented the run command above |
| 2 | Default `--data` (`hw06/data`) doesn't exist in the repo, so running with no argument fails | Kept the argument required in practice; the run command in this README always passes it |
| 3 | The merge with `powerbi_values.csv` is an **inner** join, so a slice missing from the Power BI export is silently skipped rather than reported | Accepted for this submission (only 42 slices were exported); the README states 42 of 89 were compared. Next step: switch back to an outer join once the full DAX export is run, so missing rows show as `match = False` |
| 4 | Grand-total `Ending AUM LY` / `Ending AUM PM` encode an assumption about how SAMEPERIODLASTYEAR and DATEADD behave on the full calendar (→ Dec 2023 and Nov 2024) | Kept, and listed under Mismatches and fixes; verify with the Total rows of the full export |
| 5 | Percentages transcribed at 2 dp sit close to the 0.0001 ratio tolerance (max rounding error 0.00005) | Checked: every transcribed ratio is within tolerance; the full-precision DAX export removes this risk |
| 6 | pandas computes measures independently (no values read from Power BI) and slice filters mirror the model relationships (`dim_client` tier, `dim_date` year/month) | No change needed |

Fix made while running: Fee Yield (bps) was first formatted as a percentage (showed 4315.4%); changed to decimal (43.2).
