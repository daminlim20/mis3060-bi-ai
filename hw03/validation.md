# HW3 Validation

## 5A — Known-Answer Check: Earnings

Company/quarter checked: NVIDIA (NVDA), third quarter fiscal 2026
(quarter ended October 26, 2025; reported November 19, 2025)

Official source: [paste URL]

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| NVDA Q3 FY2026 Revenue | https://nvidianews.nvidia.com/_gallery/download_pdf/691e34d93d633290a88deeef/ | $57.0 billion | yes matched|
| NVDA Q3 FY2026 EPS Diluted | https://nvidianews.nvidia.com/_gallery/download_pdf/691e34d93d633290a88deeef/ | $1.30 | yes matched |


## 5B — Known-Answer Check: Executive Events

Event checked: Walmart, filed 2025-11-14 — C. Douglas McMillon departure

Source: [paste URL]

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | yes matched| CSV: "C. Douglas McMillon", "president and chief executive officer" |
| Event type (departure/appointment) | yes matched | CSV: departure (retirement) |
| Effective date | yes matched| CSV: [what your CSV says] / News: [what the article says] |
 Source:|https://www.cnbc.com/2025/11/14/walmart-ceo-doug-mcmillon-to-retire-in-january.html


| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $57.0 billion | $57,006,000,000 | yes matches |
| Net Income | $31,910 million | $31,910,000,000 | yes matches |

Notes: Yahoo Finance labels this quarter "2025-10-31" (month-end), while
NVIDIA's fiscal quarter actually ended October 26, 2025 — same period,
different date convention. The 8-K revenue is rounded to one decimal
($57.0B) because the script captured the headline figure; the underlying
value matches exactly. As an additional check, the other three NVDA
quarters in earnings_history.csv (Q4 FY26, Q1 FY27, Q2 FY27) also match
yfinance for both revenue and net income.


## 5D — Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 30 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes (30 rows) | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | Pass |