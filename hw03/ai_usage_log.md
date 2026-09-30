# HW3 AI Usage Log

## Prompt 1 — Specification A (Earnings Pipeline)

Sent to a new Claude session. Generated `hw03/hw03_earnings.py`.

> Write a Python script using `requests` and `beautifulsoup4` that builds a
> quarterly earnings dataset from SEC 8-K filings.
>
> **HTTP setup**
> - Every single `requests.get()` call must send the header
>   `User-Agent: MIS3060 Villanova dlim02@villanova.edu`.
> - Pause 0.2 seconds between requests to respect SEC rate limits.
>
> **Companies** (use these CIKs exactly):
> Apple (AAPL, 0000320193), Microsoft (MSFT, 0000789019),
> NVIDIA (NVDA, 0001045810), JPMorgan Chase (JPM, 0000019617),
> Walmart (WMT, 0000104169).
>
> **Steps for each company**
> 1. Request `https://data.sec.gov/submissions/CIK{cik}.json`. The filings
>    are stored as parallel lists under `filings.recent` (form, filingDate,
>    accessionNumber, items).
> 2. Keep only filings where form is "8-K" and the `items` string contains
>    "2.02". Take the four most recent (one per quarter).
> 3. For each filing, build the filing folder URL:
>    `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession number without dashes}/index.json`.
>    From the list of files, pick the earnings press release: the .htm file
>    whose name contains "ex99" or "ex-99" (Exhibit 99.1).
> 4. Download the press release and convert it to plain text with BeautifulSoup.
> 5. Use regular expressions to extract quarterly revenue (keep the units:
>    millions or billions), diluted EPS, net income, and the reporting
>    period (e.g., "fourth quarter fiscal 2024").
> 6. Print each row as it is processed:
>    `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
>
> **Error handling**
> - If any field can't be extracted, store the string "NOT_FOUND" (never
>   None or blank).
> - If a press release exhibit can't be found or a request fails, print a
>   warning naming the ticker and filing date, and continue to the next
>   filing. The script must never crash because of one bad filing.
>
> **Output**
> Save all rows to `hw03/earnings_history.csv` with columns: company,
> ticker, cik, filing_date, period, revenue_reported, eps_diluted,
> net_income. Print a confirmation with the number of rows saved.

**Follow-up prompt (same session):**

> The script ran and produced 20 rows, but there are two extraction errors:
> (1) For NVDA and WMT, some period labels are wrong. NVDA shows 'first
> quarter fiscal 2027' twice, and WMT shows 'third quarter fiscal 2027'
> before that quarter has been reported. The period regex seems to be
> matching a phrase other than the one describing the current quarter's
> results. (2) WMT net income shows '$6,366 billion' when it should be
> '$6,366 million'; the unit is being taken from the wrong line. Please fix
> both, and prefer the period phrase that appears in the headline or first
> paragraph of the release.

## Prompt 2 — Specification B (Executive Events Pipeline)

Sent to a separate new Claude session. Generated `hw03/hw03_executives.py`.

> Write a Python script using `requests` and `beautifulsoup4` that builds a
> dataset of executive departures and appointments from SEC 8-K filings.
>
> **HTTP setup**
> - Every `requests.get()` call must send the header
>   `User-Agent: MIS3060 Villanova dlim02@villanova.edu`.
> - Pause 0.2 seconds between requests.
>
> **Companies**: same five as Specification A (AAPL 0000320193, MSFT
> 0000789019, NVDA 0001045810, JPM 0000019617, WMT 0000104169).
>
> **Steps for each company**
> 1. Request `https://data.sec.gov/submissions/CIK{cik}.json` and read the
>    parallel lists under `filings.recent`.
> 2. Keep filings where form is "8-K", the `items` string contains "5.02",
>    and `filingDate` is within the past 12 months of the day the script runs.
> 3. For each filing, download the main 8-K document at
>    `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession without dashes}/{primaryDocument}`
>    and strip the HTML to plain text.
> 4. Narrow the text to the Item 5.02 section: from "Item 5.02" up to the
>    next "Item" heading or "Signature(s)".
> 5. From that section, extract each event:
>    - event_type: "departure" (resign, retire, step down, terminate, leave),
>      "appointment" (appoint, elect, name, promote, hire), or "both" when
>      one person leaves one role and takes another in the same sentence
>    - person_name: the person's full name
>    - title: their role (e.g., "Chief Financial Officer", "director")
>    - effective_date: the date the change takes effect; if none is stated,
>      use "NOT_FOUND"
> 6. If a filing reports multiple events, create a separate row for each person.
> 7. If a filing's Item 5.02 section has no departure or appointment (e.g.,
>    compensation changes only), print
>    `[Ticker] | [Date] | No departure/appointment found (likely compensation-only)`
>    and skip it without crashing.
> 8. Print each event as it is processed:
>    `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
> 9. If a company has no Item 5.02 filings in the past 12 months, print
>    `[Ticker]: No executive events in past 12 months`. This is valid data,
>    not an error.
>
> **Error handling**
> - Any field that can't be extracted is stored as "NOT_FOUND", never blank.
> - If a request fails or a document can't be parsed, print a warning and
>   continue to the next filing.
>
> **Output**
> Save all events to `hw03/executive_events.csv` with columns: company,
> ticker, cik, filing_date, event_type, person_name, title, effective_date.
> Print a confirmation with the number of events saved.

## Prompt 3 — Timeline Join

Sent to a separate new Claude session. Generated `hw03/hw03_timeline.py`.
I used the assignment's prompt and added the final sentence to resolve the
overlap between "same week" and "before/after."

> Write a Python script that reads `hw03/earnings_history.csv` and
> `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of
>    days between the executive event's `filing_date` and the nearest
>    earnings filing date for the same company in the earnings table. Call
>    this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as:
>    `'before earnings'` if the event came before the nearest earnings
>    filing, `'after earnings'` if it came after, or `'same week'` if within
>    7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with
>    all columns from both source tables plus `days_to_nearest_earnings` and
>    `event_timing`.
> 4. Print a summary: for each company, list any executive events and
>    whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an
>    earnings announcement across all five companies.
>
> If an event is within 7 days of an earnings filing, label it 'same week'
> even if it is technically before or after.

## Additional Prompt — Yahoo Finance Cross-Validation (Part 5C)

Adapted from the assignment's suggested prompt to print all quarters,
because the quarter I validated (NVDA Q3 FY2026) was not the most recent one.

> Write Python using yfinance to get quarterly revenue and net income for
> NVDA. Print all available quarters (not just the most recent), showing
> the quarter-end date, Total Revenue, and Net Income for each, in raw dollars.

## Companies That Required Iteration

**Earnings pipeline — NVDA and WMT.** The first run produced 20 rows with
no NOT_FOUND values, but reviewing the output revealed errors that
NOT_FOUND checks alone would have missed:
- **NVDA:** Two filings were both labeled "first quarter fiscal 2027." The
  $68.1B row was actually the fourth quarter of fiscal 2026; the period
  regex was matching the wrong quarter phrase in the release.
- **WMT:** Period labels were shifted (it listed "third quarter fiscal
  2027," which Walmart had not yet reported, and skipped Q4 FY2026), and
  net income was labeled "billion" instead of "million" (e.g., "$6,366
  billion" instead of $6,366 million).

One follow-up prompt fixed both. After the rerun, all 20 rows had correct
periods and units, and yfinance later confirmed all four NVDA quarters.

**Executive events pipeline — no regex fixes needed.** It extracted 30
events on the first run and correctly skipped 3 compensation-only filings.
Known limitations I documented rather than fixed:
- John Furner's January 2026 Walmart event was classified as a
  "departure," but it was an internal move (Walmart U.S. CEO to Walmart
  Inc. CEO) and would be better labeled "both."
- The same person appears under two name formats ("John Furner" and
  "John R. Furner").
- The zero-events edge case exists in the code but was never triggered,
  because all five companies had at least one Item 5.02 filing.

**Timeline:** No fixes needed. I renamed the generated file to
`hw03_timeline.py` to match the required filename.

## Something the Script Did That I Didn't Specify

The executives script printed the exact date window before processing
any company ("Looking for Item 5.02 8-K filings from 2025-09-29 to
2026-09-29"). My specification only said "within the past 12 months."
This was correct and useful: it made the filter visible, so I could
confirm the window was calculated from the run date rather than
hard-coded, which also means the script will stay accurate if rerun later.

## Additional AI Assistance

Beyond the prompts above, I used Claude as a guide throughout the
assignment: to understand the instructions, draft and refine my
specifications, troubleshoot Git Bash path errors, review script output
for extraction errors, and draft my written sections.