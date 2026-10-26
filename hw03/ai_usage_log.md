# HW3 AI Usage Log

## Prompt 1 — Earnings Pipeline

I sent the following prompt to a new Claude session, which generated `hw03/hw03_earnings.py`.

> Write a Python script using `requests` and `beautifulsoup4` that builds a quarterly earnings dataset from SEC 8-K filings.
>
> **HTTP setup**
> - Every single `requests.get()` call must send the header `User-Agent: MIS3060 Villanova dlim02@villanova.edu`.
> - Pause 0.2 seconds between requests to respect SEC rate limits.
>
> **Companies** (use these CIKs exactly):
> Apple (AAPL, 0000320193), Microsoft (MSFT, 0000789019), NVIDIA (NVDA, 0001045810), JPMorgan Chase (JPM, 0000019617), Walmart (WMT, 0000104169).
>
> **Steps for each company**
> 1. Request `https://data.sec.gov/submissions/CIK{cik}.json`. The filings are stored as parallel lists under `filings.recent` (form, filingDate, accessionNumber, items).
> 2. Keep only filings where form is "8-K" and the `items` string contains "2.02". Take the four most recent (one per quarter).
> 3. For each filing, build the filing folder URL: `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession number without dashes}/index.json`. From the list of files, pick the earnings press release: the .htm file whose name contains "ex99" or "ex-99" (Exhibit 99.1).
> 4. Download the press release and convert it to plain text with BeautifulSoup.
> 5. Use regular expressions to extract quarterly revenue (keep the units: millions or billions), diluted EPS, net income, and the reporting period (e.g., "fourth quarter fiscal 2024").
> 6. Print each row as it is processed: `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
>
> **Error handling**
> - If any field can't be extracted, store the string "NOT_FOUND" (never None or blank).
> - If a press release exhibit can't be found or a request fails, print a warning naming the ticker and filing date, and continue to the next filing. The script must never crash because of one bad filing.
>
> **Output**
> Save all rows to `hw03/earnings_history.csv` with columns: company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income. Print a confirmation with the number of rows saved.

After running the script, I noticed that the output had 20 rows but still contained a few extraction errors. I used the following follow-up prompt in the same Claude session:

> The script ran and produced 20 rows, but there are two extraction errors:
> (1) For NVDA and WMT, some period labels are wrong. NVDA shows 'first quarter fiscal 2027' twice, and WMT shows 'third quarter fiscal 2027' before that quarter has been reported. The period regex seems to be matching a phrase other than the one describing the current quarter's results.
> (2) WMT net income shows '$6,366 billion' when it should be '$6,366 million'; the unit is being taken from the wrong line. Please fix both, and prefer the period phrase that appears in the headline or first paragraph of the release.

## Prompt 2 — Executive Events Pipeline

For the executive events portion, I opened a separate Claude session. This generated `hw03/hw03_executives.py`.

> Write a Python script using `requests` and `beautifulsoup4` that builds a dataset of executive departures and appointments from SEC 8-K filings.
>
> **HTTP setup**
> - Every `requests.get()` call must send the header `User-Agent: MIS3060 Villanova dlim02@villanova.edu`.
> - Pause 0.2 seconds between requests.
>
> **Companies**: same five as Specification A (AAPL 0000320193, MSFT 0000789019, NVDA 0001045810, JPM 0000019617, WMT 0000104169).
>
> **Steps for each company**
> 1. Request `https://data.sec.gov/submissions/CIK{cik}.json` and read the parallel lists under `filings.recent`.
> 2. Keep filings where form is "8-K", the `items` string contains "5.02", and `filingDate` is within the past 12 months of the day the script runs.
> 3. For each filing, download the main 8-K document at `https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession without dashes}/{primaryDocument}` and strip the HTML to plain text.
> 4. Narrow the text to the Item 5.02 section: from "Item 5.02" up to the next "Item" heading or "Signature(s)".
> 5. From that section, extract each event:
>    - event_type: "departure" (resign, retire, step down, terminate, leave), "appointment" (appoint, elect, name, promote, hire), or "both" when one person leaves one role and takes another in the same sentence
>    - person_name: the person's full name
>    - title: their role (e.g., "Chief Financial Officer", "director")
>    - effective_date: the date the change takes effect; if none is stated, use "NOT_FOUND"
> 6. If a filing reports multiple events, create a separate row for each person.
> 7. If a filing's Item 5.02 section has no departure or appointment (e.g., compensation changes only), print `[Ticker] | [Date] | No departure/appointment found (likely compensation-only)` and skip it without crashing.
> 8. Print each event as it is processed: `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
> 9. If a company has no Item 5.02 filings in the past 12 months, print `[Ticker]: No executive events in past 12 months`. This is valid data, not an error.
>
> **Error handling**
> - Any field that can't be extracted is stored as "NOT_FOUND", never blank.
> - If a request fails or a document can't be parsed, print a warning and continue to the next filing.
>
> **Output**
> Save all events to `hw03/executive_events.csv` with columns: company, ticker, cik, filing_date, event_type, person_name, title, effective_date. Print a confirmation with the number of events saved.

## Prompt 3 — Timeline Join

I used a third, separate Claude session for the timeline portion. This produced `hw03/hw03_timeline.py`. I mostly used the assignment's suggested prompt, but I added the final sentence to make it clear that "same week" should take priority over "before" or "after."

> Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.
> 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies.
>
> If an event is within 7 days of an earnings filing, label it 'same week' even if it is technically before or after.

## Additional Prompt — Yahoo Finance Cross-Validation

For Part 5C, I also used Claude to help with the Yahoo Finance cross-check. I adapted the suggested assignment prompt so that it would print all available quarters instead of only the latest one. I did this because the quarter I wanted to validate, NVDA Q3 FY2026, was not the most recent quarter.

> Write Python using yfinance to get quarterly revenue and net income for NVDA. Print all available quarters (not just the most recent), showing the quarter-end date, Total Revenue, and Net Income for each, in raw dollars.

## Where I Had to Make Changes

The earnings pipeline needed the most revision. On the first run, it produced all 20 expected rows and did not return any `NOT_FOUND` values. However, checking the actual output showed that some values were still wrong, which would not have been caught just by looking for missing data.

For NVDA, two different filings were both labeled "first quarter fiscal 2027." The row showing $68.1 billion in revenue was actually the fourth quarter of fiscal 2026. The regex had picked up a different quarter reference elsewhere in the release instead of the period being reported.

Walmart had a similar issue. Some of its quarter labels were shifted, including a "third quarter fiscal 2027" result even though that quarter had not yet been reported. The script also skipped Q4 FY2026. In addition, Walmart's net income unit was incorrect. For example, it showed "$6,366 billion" instead of "$6,366 million" because the regex was picking up the wrong unit from the surrounding text.

I used one follow-up prompt to fix both issues. After rerunning the script, all 20 rows had the correct period labels and units. I later used yfinance to confirm the four NVDA quarters as an additional check.

The executive events pipeline worked better on the first run. It extracted 30 events and correctly skipped three filings that only discussed compensation changes. I did notice a few limitations, but I documented them rather than continuing to revise the script.

One example was John Furner's January 2026 Walmart event. The script classified it as a "departure," even though it was really an internal move from Walmart U.S. CEO to Walmart Inc. CEO, so "both" would probably describe it more accurately. The same person also appeared under two different formats, "John Furner" and "John R. Furner." Finally, although the script includes logic for companies with zero executive events, that case never came up because all five companies had at least one Item 5.02 filing during the period.

The timeline script did not need any corrections after it ran. I only renamed the generated file to `hw03_timeline.py` so that it matched the required filename.

## Something Claude Added That I Did Not Ask For

One useful thing the executive script did on its own was print the exact date range it was searching before it started processing companies: "Looking for Item 5.02 8-K filings from 2025-09-29 to 2026-09-29."

My original prompt only said to look at filings from the past 12 months, so I had not specifically asked for this message. I found it helpful because it let me verify that the date range was being calculated from the day the script ran rather than being hard-coded. It also means the script should still use the correct 12-month window if it is run again later.

## Additional AI Assistance

In addition to generating the scripts, I used Claude as a guide throughout the assignment. I used it to help me understand parts of the instructions, draft and revise my specifications, troubleshoot Git Bash path errors, check the output for extraction problems, and help organize some of my written explanations.
