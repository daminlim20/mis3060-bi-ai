# HW3 Specifications

## Specification A — Earnings Pipeline (hw03/hw03_earnings.py)

Write a Python script using `requests` and `beautifulsoup4` that builds a
quarterly earnings dataset from SEC 8-K filings.

**HTTP setup**
- Every single `requests.get()` call must send the header
  `User-Agent: dlim02@villanova.edu`.
- Pause 0.2 seconds between requests to respect SEC rate limits.

**Companies** (use these CIKs exactly):
Apple (AAPL, 0000320193), Microsoft (MSFT, 0000789019),
NVIDIA (NVDA, 0001045810), JPMorgan Chase (JPM, 0000019617),
Walmart (WMT, 0000104169).

**Steps for each company**
1. Request `https://data.sec.gov/submissions/CIK{cik}.json`. The filings are
   stored as parallel lists under `filings.recent` (form, filingDate,
   accessionNumber, items).
2. Keep only filings where form is "8-K" and the `items` string contains
   "2.02". Take the four most recent (one per quarter).
3. For each filing, build the filing folder URL:
   `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession number without dashes}/index.json`.
   From the list of files, pick the earnings press release: the .htm file
   whose name contains "ex99" or "ex-99" (Exhibit 99.1).
4. Download the press release and convert it to plain text with BeautifulSoup.
5. Use regular expressions to extract:
   - quarterly revenue (keep the units: millions or billions)
   - diluted EPS
   - net income
   - reporting period (e.g., "fourth quarter fiscal 2024")
6. Print each row as it is processed:
   `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`

**Error handling**
- If any field can't be extracted, store the string "NOT_FOUND" (never None
  or blank).
- If a press release exhibit can't be found or a request fails, print a
  warning naming the ticker and filing date, and continue to the next filing.
  The script must never crash because of one bad filing.

**Output**
Save all rows to `hw03/earnings_history.csv` with columns:
company, ticker, cik, filing_date, period, revenue_reported, eps_diluted,
net_income.
Print a confirmation with the number of rows saved.