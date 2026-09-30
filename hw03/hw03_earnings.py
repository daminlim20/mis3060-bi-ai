"""
HW3 - Specification A: Earnings Pipeline

Builds a quarterly earnings dataset from SEC 8-K filings (Item 2.02,
"Results of Operations and Financial Condition") for five companies.

For each company:
  1. Pull the submissions JSON from data.sec.gov.
  2. Keep 8-K filings whose items include "2.02"; take the 4 most recent
     (one per quarter).
  3. Open each filing's index.json and pick the Exhibit 99.1 press release.
  4. Download the press release and convert it to plain text (BeautifulSoup).
  5. Extract revenue, diluted EPS, net income, and reporting period with regex.
  6. Print each row, then save everything to hw03/earnings_history.csv.

Requires: requests, beautifulsoup4
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEADERS = {"User-Agent": "MIS3060 Villanova dlim02@villanova.edu"}
PAUSE_SECONDS = 0.2
FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart", "ticker": "WMT", "cik": "0000104169"},
]

OUTPUT_FILE = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date", "period",
    "revenue_reported", "eps_diluted", "net_income",
]


# ---------------------------------------------------------------------------
# HTTP helper - every request goes through here
# ---------------------------------------------------------------------------

def sec_get(url):
    """GET a URL with the required User-Agent, then pause for the SEC rate limit.

    Raises requests.RequestException on network errors or non-2xx responses,
    so callers can catch it and move on.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
    finally:
        time.sleep(PAUSE_SECONDS)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Step 1-2: find the earnings 8-K filings
# ---------------------------------------------------------------------------

def get_earnings_filings(cik):
    """Return up to 4 recent 8-K / Item 2.02 filings as dicts, newest first."""
    data = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    recent = data["filings"]["recent"]

    forms = recent["form"]
    dates = recent["filingDate"]
    accessions = recent["accessionNumber"]
    items = recent["items"]

    filings = []
    quarters_seen = set()
    # The SEC lists filings newest first.
    for form, date, accession, item_str in zip(forms, dates, accessions, items):
        if form != "8-K" or "2.02" not in (item_str or ""):
            continue
        # One per quarter: skip a second 2.02 filing in the same calendar quarter.
        year, month = int(date[:4]), int(date[5:7])
        quarter_key = (year, (month - 1) // 3)
        if quarter_key in quarters_seen:
            continue
        quarters_seen.add(quarter_key)
        filings.append({"filing_date": date, "accession": accession})
        if len(filings) == FILINGS_PER_COMPANY:
            break
    return filings


# ---------------------------------------------------------------------------
# Step 3: locate the Exhibit 99.1 press release
# ---------------------------------------------------------------------------

EX99_NAME = re.compile(r"ex(?:hibit)?[-_]?99", re.IGNORECASE)
EX991_NAME = re.compile(r"ex(?:hibit)?[-_]?99[-_.]?0?1(?!\d)", re.IGNORECASE)


def find_press_release_url(cik, accession):
    """Return the URL of the Exhibit 99.1 .htm file, or None if not found."""
    cik_no_zeros = str(int(cik))
    acc_no_dashes = accession.replace("-", "")
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}"

    index = sec_get(f"{folder}/index.json").json()
    names = [item["name"] for item in index["directory"]["item"]]
    htm_files = [n for n in names if n.lower().endswith((".htm", ".html"))]

    # Spec rule: .htm file whose name contains "ex99" / "ex-99".
    # Prefer the one that is explicitly 99.1 over 99.2, 99.3, ...
    candidates = [n for n in htm_files if EX99_NAME.search(n)]
    if candidates:
        exact = [n for n in candidates if EX991_NAME.search(n)]
        return f"{folder}/{(exact or candidates)[0]}"

    # Fallback: some filers (e.g. NVIDIA) give the exhibit a name like
    # "q3fy25pr.htm". The human-readable filing index labels each document
    # with its type, so look for the row typed EX-99.1 there.
    index_page = sec_get(f"{folder}/{accession}-index.htm")
    soup = BeautifulSoup(index_page.content, "html.parser")
    for row in soup.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if any(c.upper().startswith("EX-99.1") for c in cells):
            link = row.find("a", href=True)
            if link and link["href"].lower().endswith((".htm", ".html")):
                return "https://www.sec.gov" + link["href"]
    return None


# ---------------------------------------------------------------------------
# Step 4: download and convert to text
# ---------------------------------------------------------------------------

def get_press_release_text(url):
    """Download an HTML press release and return clean, single-spaced text."""
    html = sec_get(url).content
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ").replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Step 5: regex extraction
# ---------------------------------------------------------------------------

NUM = r"\(?-?[\d,]+(?:\.\d+)?\)?"   # 94.9, 14,736, (0.12)
UNIT = r"(billion|million)"


def clean_number(raw):
    """'(0.12)' -> '-0.12', '14,736' stays '14,736'."""
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        return "-" + raw[1:-1]
    return raw.strip("()")


def table_unit(text, position):
    """Unit for a table number found at `position` in the text.

    Releases often have several tables with different units (Walmart's summary
    table is "in billions", its income statement is "in millions"), so use the
    closest "in millions" / "in billions" note *before* the number, not the
    first one in the document.
    """
    notes = [m for m in re.finditer(r"in (millions|billions)", text, re.IGNORECASE)
             if m.start() < position]
    if notes:
        return notes[-1].group(1).lower().rstrip("s")
    later = re.search(r"in (millions|billions)", text[position:], re.IGNORECASE)
    return later.group(1).lower().rstrip("s") if later else ""


def format_table_value(match, text):
    """Format a number pulled from a financial table, with its table's unit."""
    value = clean_number(match.group(1))
    unit = table_unit(text, match.start(1))
    # Sanity check: no quarterly figure here is in the thousands of billions,
    # so a whole number >= 1,000 labelled "billion" must really be millions.
    if unit == "billion" and "." not in value and float(value.replace(",", "")) >= 1000:
        unit = "million"
    return f"${value}" + (f" {unit}" if unit else "")


def first_match(patterns, text):
    """Return the first regex match object from a list of patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match
    return None


def extract_revenue(text):
    # Sentences such as:
    #   "quarterly revenue of $94.9 billion"         (Apple)
    #   "Revenue was $65.6 billion"                   (Microsoft)
    #   "revenue for the third quarter ... of $35.1 billion"   (NVIDIA)
    #   "Consolidated revenue of $169.6 billion"      (Walmart)
    #   "revenue of $43.3 billion"                    (JPMorgan)
    match = first_match([
        rf"revenues?[^$]{{0,80}}?\$\s?({NUM})\s*{UNIT}",
        rf"net sales[^$]{{0,80}}?\$\s?({NUM})\s*{UNIT}",
    ], text)
    if match:
        return f"${clean_number(match.group(1))} {match.group(2).lower()}"

    # Fall back to the income statement table: "Total net sales $ 94,930"
    match = first_match([
        rf"total (?:net )?(?:revenues?|net sales|sales)\s*\$?\s?({NUM})",
    ], text)
    if match:
        return format_table_value(match, text)
    return NOT_FOUND


def extract_eps(text):
    # "diluted earnings per share of $0.97"               (Apple)
    # "Diluted earnings per share was $3.30"               (Microsoft)
    # "GAAP earnings per diluted share for the quarter were $0.78"  (NVIDIA)
    # "GAAP EPS of $0.57"                                  (Walmart)
    # "net income of $12.9 billion, or $4.37 per share"    (JPMorgan)
    match = first_match([
        rf"diluted (?:earnings|net income|EPS)(?: per (?:common )?share)?[^$]{{0,60}}?\$\s?({NUM})",
        rf"(?:earnings|net income) per diluted (?:common )?share[^$]{{0,60}}?\$\s?({NUM})",
        rf"EPS (?:of|was|were)\s+\$\s?({NUM})",
        rf"\$\s?({NUM}) per (?:diluted )?share",
    ], text)
    return f"${clean_number(match.group(1))}" if match else NOT_FOUND


def extract_net_income(text):
    # Narrative first: "Net income was $24.7 billion" / "net income of $12.9 billion"
    match = first_match([
        rf"net income(?! per)[^$]{{0,60}}?\$\s?({NUM})\s*{UNIT}",
    ], text)
    if match:
        return f"${clean_number(match.group(1))} {match.group(2).lower()}"

    # Otherwise the income statement table (values in millions):
    #   "Net income attributable to Walmart $ 4,579"  (skip noncontrolling interest)
    #   "Net income $ 14,736"
    match = first_match([
        rf"net income attributable to (?!non)[A-Z][\w.,&' ]{{1,40}}?\s\$\s?({NUM})",
        rf"net income(?! per)(?! attributable)\s*\$\s?({NUM})",
    ], text)
    if match:
        return format_table_value(match, text)
    return NOT_FOUND


ORDINALS = {"1": "first", "2": "second", "3": "third", "4": "fourth"}
Q = r"(first|second|third|fourth)"


def full_year(year):
    return year if len(year) == 4 else "20" + year


# Period patterns and how to label each match.
PERIOD_PATTERNS = [
    # "third quarter of fiscal 2025", "Third Quarter Fiscal Year 2025",
    # "Fourth Quarter and Fiscal 2026"                      (NVIDIA)
    (rf"\b{Q}[- ]quarter,? (?:and (?:full[- ])?|of )?fiscal (?:year )?(\d{{4}})",
     lambda m: f"{m.group(1).lower()} quarter fiscal {m.group(2)}"),
    # "fiscal 2024 fourth quarter"                          (Apple)
    (rf"\bfiscal (?:year )?(\d{{4}}) {Q}[- ]quarter",
     lambda m: f"{m.group(2).lower()} quarter fiscal {m.group(1)}"),
    # "Q3 FY25", "Q4 and FY26"                              (Walmart)
    (r"\bQ([1-4])(?: and(?: full[- ]year)?)? ?FY ?(\d{2,4})\b",
     lambda m: f"{ORDINALS[m.group(1)]} quarter fiscal {full_year(m.group(2))}"),
    (r"\bFY ?(\d{2,4}) Q([1-4])\b",
     lambda m: f"{ORDINALS[m.group(2)]} quarter fiscal {full_year(m.group(1))}"),
    # "third-quarter 2024" / "third quarter 2024"           (JPMorgan, calendar year)
    (rf"\b{Q}[- ]quarter,? (?:of )?(\d{{4}})",
     lambda m: f"{m.group(1).lower()} quarter {m.group(2)}"),
    # "3Q24"
    (r"\b([1-4])Q(\d{2})\b",
     lambda m: f"{ORDINALS[m.group(1)]} quarter {full_year(m.group(2))}"),
]
# Last resort only - less descriptive than a named quarter.   (Microsoft style)
QUARTER_ENDED = re.compile(r"quarter ended ([A-Z][a-z]+ \d{1,2}, \d{4})")

# Words shortly before a period phrase that mean it is NOT the quarter being
# reported: guidance/outlook for a future quarter, or a prior-year comparison.
FORWARD_OR_COMPARISON = re.compile(
    # keyword, then up to 8 words - but not across a period or semicolon
    r"\b(?:outlook|guidance|expects?|expected|anticipates?|forecasts?|projects?|"
    r"next|upcoming|compared (?:to|with)|versus|vs|prior[- ]year|last year|"
    r"a year ago)\.?[^\w.;]+(?:\w+[^\w.;]+){0,8}$",
    re.IGNORECASE,
)

LEAD_CHARS = 1500


def lead_section(text):
    """Headline + first paragraph: everything through the end of the first
    sentence saying the company 'today announced/reported/released' results,
    or the first LEAD_CHARS characters if there is no such sentence."""
    match = re.search(r"today (?:announced|reported|released)[^.]*\.", text[:4000],
                      re.IGNORECASE)
    return text[:match.end()] if match else text[:LEAD_CHARS]


def earliest_period(section):
    """Earliest period phrase in `section` that isn't guidance or a comparison."""
    candidates = []
    for pattern, fmt in PERIOD_PATTERNS:
        for match in re.finditer(pattern, section, re.IGNORECASE):
            preceding = section[max(0, match.start() - 80):match.start()]
            if FORWARD_OR_COMPARISON.search(preceding):
                continue
            candidates.append((match.start(), fmt(match)))
    return min(candidates)[1] if candidates else None


def extract_period(text):
    # 1. Headline / first paragraph - this describes the quarter being reported.
    # 2. Rest of the release, skipping guidance and prior-year comparisons.
    # 3. "quarter ended <date>" as a last resort.
    # Within each step the phrase that appears FIRST wins, so a pattern that
    # matches deep in an Outlook/Guidance section can't beat the headline.
    for section in (lead_section(text), text):
        period = earliest_period(section)
        if period:
            return period
    match = QUARTER_ENDED.search(text)
    return f"quarter ended {match.group(1)}" if match else NOT_FOUND


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_filing(company, filing):
    """Build one output row. Returns None (after a warning) if it can't."""
    ticker = company["ticker"]
    date = filing["filing_date"]

    url = find_press_release_url(company["cik"], filing["accession"])
    if url is None:
        print(f"WARNING: {ticker} {date} - no Exhibit 99.1 press release found, skipping")
        return None

    text = get_press_release_text(url)
    row = {
        "company": company["company"],
        "ticker": ticker,
        "cik": company["cik"],
        "filing_date": date,
        "period": extract_period(text),
        "revenue_reported": extract_revenue(text),
        "eps_diluted": extract_eps(text),
        "net_income": extract_net_income(text),
    }
    # Never store None or blanks.
    for key, value in row.items():
        if value is None or str(value).strip() == "":
            row[key] = NOT_FOUND
    return row


def main():
    rows = []

    for company in COMPANIES:
        ticker = company["ticker"]
        try:
            filings = get_earnings_filings(company["cik"])
        except Exception as exc:  # network error, bad JSON, missing keys ...
            print(f"WARNING: {ticker} - could not load filing list ({exc}), skipping company")
            continue

        if not filings:
            print(f"WARNING: {ticker} - no 8-K Item 2.02 filings found")
            continue

        for filing in filings:
            try:
                row = process_filing(company, filing)
            except Exception as exc:
                print(f"WARNING: {ticker} {filing['filing_date']} - {type(exc).__name__}: {exc}; skipping")
                continue
            if row is None:
                continue
            rows.append(row)
            print(f"{row['ticker']} | {row['period']} | "
                  f"Revenue: {row['revenue_reported']} | "
                  f"EPS: {row['eps_diluted']} | "
                  f"Net Income: {row['net_income']}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
