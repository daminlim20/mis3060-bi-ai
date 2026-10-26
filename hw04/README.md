# HW4: Cleaning the Wildcat Capital Data

MIS3060 Business Intelligence with AI · Villanova University

Audit, clean and validate the 8-table Wildcat Capital warehouse extract **without inventing data**, and prove each fix worked.

## Results at a glance

- **340 audit checks** on raw data: 6 ERROR · 7 WARN · 10 INFO (`reports/dq_summary_raw.csv`)
- **20 decisions** logged before coding: 6 fixes, 3 flags, 11 leave-as-is (`decision_log.md`)
- **225 rows quarantined** (25 duplicate clients, 200 orphan transactions); **198,256 cell changes** logged; raw 555,401 = clean 555,176 + quarantined 225
- **fact_transactions referential match: 81.95% → 100%** (`reports/data_quality_scorecard.csv`)

## Structure

```
hw04/
├── README.md                      this file
├── decision_log.md                Part B: one entry per issue (written before 02_clean.py)
├── scripts/
│   ├── 01_profile.py              Part A: generic profiler + 4 check groups
│   ├── 02_clean.py                Part C: one asserted transformation at a time
│   └── 03_validate.py             Part D: RI function, rules, reconciliations, IQR, scorecard
├── data/
│   ├── raw/                       the 8 original CSVs (never modified)
│   ├── clean/                     8 clean CSVs + README_clean.md (relationships, BI types, flags, limitations)
│   └── audit/                     cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv            per-column profile (75 columns)
    ├── dq_summary_raw.csv         340 checks, tagged ERROR / WARN / INFO / PASS
    ├── data_quality_scorecard.csv one row per table per stage (raw / clean)
    ├── ri_results.csv · rule_results.csv · reconciliations.csv · outliers_iqr.csv
    └── cleaning_report.md         Part E: report for the portfolio committee
```

## How to run

Python 3.11+ with pandas (tested on pandas 3.0). From the `hw04` folder:

```bash
python scripts/01_profile.py    # ~1 min  -> reports/profile_raw.csv, dq_summary_raw.csv
python scripts/02_clean.py      # ~10 s   -> data/clean/, data/audit/   (stops on any failed assert)
python scripts/03_validate.py   # ~15 s   -> reports/data_quality_scorecard.csv + 4 detail reports
```

Run them in order: `03_validate.py` compares `data/raw` with the `data/clean` output of `02_clean.py`. All three read every file as text (`dtype=str, keep_default_na=False`) and convert columns deliberately.

## Process

Scripts were drafted with Claude, run and debugged in VS Code, and reviewed by Claude Code before each commit. One commit per part; the Part B decision log was drafted before the cleaning code but was accidentally committed together with Part C (`12fe7a1`). Its post-run addendum was committed separately as Part B (`8bc4e85`).

## Claude Code review findings

### `01_profile.py`

| # | Claude Code flagged | What I did |
|---|---|---|
| 1 | Date min/max computed alphabetically | Fixed: computed from parsed dates |
| 2 | `2024-1-5` accepted as a valid date | Fixed: strict `YYYY-MM-DD` regex |
| 3 | Columns >20% dirty labeled "text", hiding problems | Fixed: added `best_type`, `best_type_pct`, `partly_typed`, `symbol_numeric_values` |
| 4 | Mixed `10` / `10.5` labeled int | Fixed: any decimals → float |
| 5 | `inf` / `Infinity` accepted as numbers | Fixed: strict number regex; scientific notation still allowed but counted |
| 6 | `mixed_format` overlapped with parse failures | Fixed: formats built from valid values only |
| 7 | Blanks / null tokens counted as distinct values | Fixed |
| 8 | Double spaces double-counted with leading/trailing | Fixed: `internal_double_space` |
| 9 | Slow (regex per cell, twice) | Fixed: vectorised, once per unique value (2–3 min → <1 min) |
| 10 | Null tokens are guesses | Kept, reported separately with the actual values shown |
| 11 | `t/f/y/n` caught as booleans | Fixed: single letters removed |
| 12 | Leading-zero IDs/ZIPs treated as numbers | Fixed: `id_like`, `leading_zero_values` (232 ZIPs) |
| 13 | Ambiguous shape notation | Fixed: `A*` / `a*` |
| 15 | Hard-coded table list; BOM; duplicate headers | BOM + duplicate-header assert added; **list kept** because the assignment says to use only these 8 files |
| 16 | 0-row table gives NaN | Fixed |
| 17 | No table-level checks | Added in the 4 check groups (duplicates, keys, row rules) |

Claude Code confirmed with a read-only script that the outputs are correct: every changed cell is logged (77 + 300 + 197,879), all 25 duplicates differ only in a truncated last name, and every cleaned `security_id` exists in `dim_security`. Its findings were about **what the asserts prove**.

### `02_clean.py`

| # | Claude Code flagged | What I did |
|---|---|---|
| 1 | **A2 state assert was circular**: the "before" totals were computed with the same mapping as the fix, so it could never fail | Fixed. The mapping is now checked against an independent USPS name → code reference, and per-state totals are computed from the column *before* the fix. **Mutation-tested:** changing `Texas → TN` now stops the script; my first fix still passed that test, because it took codes from the mapping it was checking |
| 2 | Asserts checked the code ran, not that the fix was right | Added value-preserving asserts: A3 new = old ÷ 100; A4 only the sign changed; A6 numeric `security_id` unchanged; A1 truncation evidence and all-other-fields-equal are **asserted**, not just printed |
| 3 | Nothing proved that cells outside a fix stayed untouched | `record_changes()` now asserts rows outside the mask are unchanged; a final step asserts every raw ≠ clean cell is in `value_changes.csv` (0 unlogged) |
| 4 | `num()` didn't strip whitespace (03 did) | Fixed for consistency |

### `03_validate.py`

| # | Claude Code flagged | What I did |
|---|---|---|
| 1 | No asserts: reports are written whatever they say | Added `gate()`: clean stage must have 0 orphan FKs, unique dimension keys, 0 reconciliation failures, and 0 rule failures except the documented one (C5: 1 fee > 100 bps) |
| 2 | R5 double-counted the 200 orphans as advisor mismatches | Fixed: R5 checks only known clients (raw R5 for transactions 200 → 0; the orphans stay counted once, in RI) |
| 3 | `client_since` rule compared strings, so blank passed | Fixed: parsed as a date first |
| 4 | R3b crashed on a non-numeric year; scorecard divided by 0 if all FKs blank | Fixed: nullable int; guarded division |
| 5 | R6 compared benchmark returns as text (`0.05` ≠ `0.050`) | Fixed: compared as numbers |
| 6 | Redundant flag-exclusion lines; `dim_key_unique` unused | Removed the redundant lines; `dim_key_unique` is now used by the gate |

### Found during my own verification (Part E)

While checking the report's numbers, I tested the claim that extreme returns came from deposits. The transaction ledger disproved it (correlation 0.001 between AUM changes and net flows). I corrected `decision_log.md` (addendum), `README_clean.md` (limitation 10) and the cleaning-log note, and added reconciliation R3b to `03_validate.py` (`return_ytd` = AUM ÷ prior-Dec AUM − 1 on 100% of testable rows).
