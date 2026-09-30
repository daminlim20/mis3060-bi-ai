# HW3 Specifications

## Specification A — Earnings Pipeline (hw03/hw03_earnings.py)

Write a Python script using `requests` and `beautifulsoup4` that builds a
quarterly earnings dataset from SEC 8-K filings.

**HTTP setup**
- Every single `requests.get()` call must send the header
  `User-Agent: MIS3060 Villanova dlim02@villanova.edu`.
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


## Specification B — Executive Events Pipeline (hw03/hw03_executives.py)

Write a Python script using `requests` and `beautifulsoup4` that builds a
dataset of executive departures and appointments from SEC 8-K filings.

**HTTP setup**
- Every `requests.get()` call must send the header
  `User-Agent: MIS3060 Villanova @villanova.edu`.
- Pause 0.2 seconds between requests.

**Companies**: same five as Specification A
(AAPL 0000320193, MSFT 0000789019, NVDA 0001045810, JPM 0000019617,
WMT 0000104169).

**Steps for each company**
1. Request `https://data.sec.gov/submissions/CIK{cik}.json` and read the
   parallel lists under `filings.recent`.
2. Keep filings where form is "8-K", the `items` string contains "5.02",
   and `filingDate` is within the past 12 months of the day the script runs.
3. For each filing, download the main 8-K document at
   `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession without dashes}/{primaryDocument}`
   and strip the HTML to plain text.
4. Narrow the text to the Item 5.02 section: from "Item 5.02" up to the
   next "Item" heading or "Signature(s)".
5. From that section, extract each event:
   - event_type: "departure" (resign, retire, step down, terminate, leave),
     "appointment" (appoint, elect, name, promote, hire), or "both" when one
     person leaves one role and takes another in the same sentence
   - person_name: the person's full name
   - title: their role (e.g., "Chief Financial Officer", "director")
   - effective_date: the date the change takes effect; if none is stated,
     use "NOT_FOUND"
6. If a filing reports multiple events (for example, one person departs and
   another is appointed), create a separate row for each person.
7. If a filing's Item 5.02 section has no departure or appointment (for
   example, it only describes compensation changes), print
   `[Ticker] | [Date] | No departure/appointment found (likely compensation-only)`
   and skip it without crashing.
8. Print each event as it is processed:
   `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
9. If a company has no Item 5.02 filings in the past 12 months, print
   `[Ticker]: No executive events in past 12 months`. This is valid data,
   not an error.

**Error handling**
- Any field that can't be extracted is stored as "NOT_FOUND", never blank.
- If a request fails or a document can't be parsed, print a warning and
  continue to the next filing.

**Output**
Save all events to `hw03/executive_events.csv` with columns:
company, ticker, cik, filing_date, event_type, person_name, title,
effective_date.
Print a confirmation with the number of events saved.