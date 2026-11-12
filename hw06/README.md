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
<!-- update after running -->
Reconciliation: __ of 89 rows match.

## Mismatches and fixes
- The `Wildcat Capital` CSV folder is an older export without `is_return_suspect`; the script failed on it. Fixed by pointing `--data` to the clean CSVs in `HW05`.
- Grand-total time intelligence: `SAMEPERIODLASTYEAR` over the full calendar maps to 2020–2023, so Ending AUM LY at Total = Dec 2023 balance; `DATEADD -1 month` at Total ends Nov 2024. The pandas side reproduces both explicitly.

## Claude Code review
<!-- fill in after running Claude Code on scripts/01_reconcile_measures.py -->
