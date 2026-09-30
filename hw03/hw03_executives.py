"""
hw03_executives.py - Specification B: Executive Events Pipeline

Builds a dataset of executive departures and appointments from SEC 8-K
filings (Item 5.02) for five companies over the past 12 months, and saves
it to hw03/executive_events.csv.

Requires: requests, beautifulsoup4
"""

import csv
import re
import time
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# The SEC rejects document downloads (403) unless the User-Agent contains a
# real email address, so put your Villanova username in front of the @.
HEADERS = {"User-Agent": "MIS3060 Villanova YOUR_USERNAME@villanova.edu"}
PAUSE_SECONDS = 0.2
OUTPUT_FILE = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "event_type",
               "person_name", "title", "effective_date"]
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"ticker": "AAPL", "cik": "0000320193", "name": "Apple Inc."},
    {"ticker": "MSFT", "cik": "0000789019", "name": "Microsoft Corporation"},
    {"ticker": "NVDA", "cik": "0001045810", "name": "NVIDIA Corporation"},
    {"ticker": "JPM", "cik": "0000019617", "name": "JPMorgan Chase & Co."},
    {"ticker": "WMT", "cik": "0000104169", "name": "Walmart Inc."},
]

# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_PATTERN = rf"\b(?:{MONTH_PATTERN})\.?\s+\d{{1,2}},?\s+\d{{4}}\b"
DATE_RE = re.compile(
    rf"\b({MONTH_PATTERN})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE)
EFFECTIVE_DATE_RE = re.compile(
    rf"\beffective\b[^;]{{0,100}}?{DATE_PATTERN}", re.IGNORECASE)
# e.g. effective on the Transition Date
EFFECTIVE_TERM_RE = re.compile(
    r"\b(?:effective\s+(?:on\s+|as\s+of\s+|upon\s+)?|on\s+|as\s+of\s+)"
    r"the\s+((?:[A-Z][a-z]+\s+)?Date)\b")
# e.g. September 1, 2026 (the "Transition Date")
DEFINED_DATE_RE = re.compile(
    rf"({DATE_PATTERN})[^()]{{0,30}}\(\s*(?:the\s+)?[\"']([^\"']+)[\"']\s*\)",
    re.IGNORECASE)

# ---------------------------------------------------------------------------
# Event keywords
# ---------------------------------------------------------------------------
# Departure words: resign, retire, step down, terminate, leave (+ close variants)
DEPART_RE = re.compile(
    r"\b(?:resign(?:s|ed|ing|ation)?|retir(?:e|es|ed|ing|ement)"
    r"|step(?:s|ped|ping)?\s+down|terminat(?:e|es|ed|ing|ion)"
    r"|leav(?:e|es|ing)|left|depart(?:s|ed|ing|ure)?"
    r"|not\s+(?:to\s+)?(?:stand|seek|run)\s+for\s+re-?election"
    r"|transition(?:s|ed|ing)?\s+(?:out\s+of|from))\b",
    re.IGNORECASE)
# Appointment words: appoint, elect, name, promote, hire (+ close variants)
APPOINT_RE = re.compile(
    r"\b(?:appoint(?:s|ed|ing|ment)?|elect(?:s|ed|ing|ion)?"
    r"|nam(?:e|es|ed|ing)|promot(?:e|es|ed|ing|ion)s?|hir(?:e|es|ed|ing)"
    r"|join(?:s|ed|ing)?|becom(?:e|es|ing))\b",
    re.IGNORECASE)
# "... transition from his role as CEO to Executive Chair": the "to" is the new role
TRANSITION_TO_RE = re.compile(
    r"\btransition\w*\s+from\b[^.;]*?\b(to)\s+(?=(?:the\s+)?(?:role\s+of\s+)?[A-Z])"
    r"|\btransition\w*\s+(to)\s+(?:the\s+|a\s+)?(?:role|position)\s+of\b",
    re.IGNORECASE)
# "Y will succeed / replace X": Y is appointed and X is the predecessor
SUCCEED_RE = re.compile(r"\b(?:succeed(?:s|ed|ing)?|replac(?:e|es|ed|ing))\b",
                        re.IGNORECASE)

# Wording that contains an event keyword but does not report a new event
NOT_AN_EVENT_RE = re.compile(
    r"\bnamed\s+executive\s+officers?\b"
    r"|\b(?:elected|decided|chose|chosen)\s+to\s+(?=retire|resign|step|leave|depart)"
    r"|\bretirement\s+(?:plan|savings|benefits?|accounts?|eligib\w*)\b"
    r"|\bpreviously\s+announced\b"
    r"|\bwhose\b[^;]{0,150}?\b(?:was|were|has\s+been)\s+(?:previously\s+)?announced\b[^,;]*"
    r"|\b(?:before|prior\s+to)\s+(?:joining|becoming)\b"
    r"|\bjoin(?:ed|ing)\b[^.;]{0,60}?\bin\s+(?:[A-Z][a-z]+\s+)?(?:19|20)\d{2}\b",
    re.IGNORECASE)
# "terminate" inside hypothetical severance language is not an actual departure
CONDITIONAL_RE = re.compile(
    r"\bin\s+the\s+event\b|\bif\b|\bwould\b|\bseverance\b|\bwithout\s+cause\b"
    r"|\bfor\s+cause\b|\bgood\s+reason\b|\bqualifying\b|\bfor\s+any\s+reason\b"
    r"|\bfollowing\s+(?:his\s+|her\s+|their\s+|the\s+)?termination\b"
    r"|\btermination\s+of\s+(?:his\s+|her\s+|their\s+)?employment\b",
    re.IGNORECASE)

# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------
CAP = r"[A-Z][A-Za-z&'\-.]*"
DEPT = rf"(?:\s*(?:,|\bof\b)\s*(?:the\s+)?{CAP}(?:\s+(?:and\s+|&\s+|of\s+)?{CAP})*)"
PREFIX = r"(?:(?i:interim|acting|lead\s+independent|independent|non-executive)\s+)?"
CORE = (
    r"(?:"
    rf"(?i:chief\s+(?:[a-z]+\s+){{1,3}}officer)s?{DEPT}{{0,2}}"
    rf"|(?i:(?:executive\s+|senior\s+|corporate\s+|group\s+)?(?:vice\s+president|VP))s?{DEPT}{{0,3}}"
    rf"|(?i:(?:co-)?(?:president|CEO|CFO|COO|CAO|CTO|CIO|CLO))s?{DEPT}{{0,2}}"
    r"|(?i:principal\s+(?:executive|financial|accounting|operating)\s+officer)"
    r"|(?i:(?:executive\s+)?chair(?:man|woman|person)?"
    r"(?:\s+of\s+(?:the\s+)?(?:[a-z]+'s\s+)?board(?:\s+of\s+directors)?)?)"
    r"|(?i:general\s+counsel|chief\s+audit\s+executive|corporate\s+secretary"
    r"|secretary|treasurer|controller|(?:senior\s+|special\s+)?advisor)"
    r"|(?i:member\s+of\s+the\s+(?:company's\s+)?board(?:\s+of\s+directors)?)"
    r"|(?i:director)"
    r")"
)
TITLE_RE = re.compile(
    rf"\b{PREFIX}{CORE}(?:\s*,?\s+and\s+(?:an?\s+)?{PREFIX}{CORE})?(?![A-Za-z])")
# the words right before a title that mark it as the role being taken or left
AS_BEFORE_TITLE_RE = re.compile(
    r"(?:\bas|\bin\s+the\s+role\s+of|\bto)\s+"
    r"(?:(?:the|its|our|an?|his|her|their|sole|current|new)\s+|[A-Z][\w.&]*'s\s+)*$",
    re.IGNORECASE)
BOARD_SEAT_RE = re.compile(
    r"^[^.;]{0,40}?\b(?:to|from)\s+(?:the\s+|its\s+|our\s+)?(?:Company's\s+)?Board\b"
    r"(?!\s*'s)(?!(?:\s+of\s+Directors)?\s+(?:Committee|Chair))")

# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------
STOP_WORDS = set("""
mr ms mrs dr messrs the a an and or of on in as at to for by with from upon
following prior during after before effective additionally also further however
today pursuant under such this these that there his her he she their its our we
departure departures election elections appointment appointments certain
officers officer's arrangements compensatory directors' principal
company company's corporation corp inc co llc ltd plc group holdings firm
apple microsoft nvidia jpmorgan walmart sam's club
board directors director committee compensation management development human
resources nominating governance audit risk finance financial chief officer
executive senior vice president chair chairman chairwoman chairperson
lead independent interim acting general counsel secretary treasurer controller
accounting operating technology information legal marketing people
operations global international retail commercial consumer banking bank
asset wealth investment corporate services business sales worldwide cloud
americas u.s us united states america north south east west
item form section exhibit agreement agreements covenant covenants plan award
awards annual meeting shareholders stockholders securities exchange act
regulation release press report non-competition non-solicitation competition
retention continuity restricted stock units performance vesting policy incentive
equity grant grants letter offer employment transition consulting separation
bonus salary target standard poor's composite index
january february march april may june july august september october november
december jan feb mar apr jun jul aug sep sept oct nov dec
monday tuesday wednesday thursday friday saturday sunday
since while when although because until beginning starting now then
hardware engineering software product products design field supply chain
ecommerce merchandising community communications affairs strategy innovation
automation planning analysis solutions partner partners industry research
manufacturing platform platforms network networks data center gaming
fiscal year quarter new york delaware washington california arkansas
""".split())
ROMAN_SUFFIXES = {"II", "III", "IV"}

NAME_TOKEN = r"(?:(?:[A-Z]\.){2,}|[A-Z][a-zA-Z'\-]*\.?)"   # "U.S." is one token
NAME_TOKEN_RE = re.compile(NAME_TOKEN)
CAP_RUN_RE = re.compile(rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN})*")
HONORIFIC_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+([A-Z][a-zA-Z'\-]+)")
MESSRS_RE = re.compile(r"\bMessrs\.\s+([A-Z][a-zA-Z'\-]+)\s+and\s+([A-Z][a-zA-Z'\-]+)")
ABBREVIATION_RE = re.compile(
    r"\b(Mr|Ms|Mrs|Dr|Messrs|Jr|Sr|Inc|Corp|Co|Ltd|No|St|Jan|Feb|Mar|Apr|Jun|Jul"
    r"|Aug|Sep|Sept|Oct|Nov|Dec|[A-Z])\.")
UNIT_CONTEXT_RE = re.compile(
    r"(?<!resignation )(?<!appointment )(?<!election )(?<!retirement )"
    r"(?<!departure )(?<!promotion )(?<!hiring )"
    r"\b(?:of|at|in|for|from)\s+(?:the\s+|its\s+|[A-Z][\w.&]*'s\s+)?$")
HONORIFIC_ONLY = r"(?:(?:Mr|Ms|Mrs|Dr|Messrs)\.\s*)?"
DIRECT_OBJECT_RE = re.compile(rf"^\s*(?:of\s+)?{HONORIFIC_ONLY}$")
DIRECT_AFTER_SUCCEED_RE = re.compile(rf"^\s*{HONORIFIC_ONLY}$")
COORDINATED_RE = re.compile(
    rf"^\s*(?:,\s*(?:age\s+)?\d{{1,3}}\s*)?,?\s*(?:and|&)\s*{HONORIFIC_ONLY}$")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def fetch(url):
    """GET a URL with the required header. Returns the response or None."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response
    except requests.RequestException as err:
        print(f"  WARNING: request failed for {url} ({err})")
        return None
    finally:
        time.sleep(PAUSE_SECONDS)


# ---------------------------------------------------------------------------
# Steps 1-2: choose the filings
# ---------------------------------------------------------------------------
def one_year_before(day):
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # Feb 29 -> Feb 28
        return day.replace(year=day.year - 1, day=28)


def select_filings(submissions, start_date, end_date):
    """Return 8-K filings with Item 5.02 filed between start_date and end_date."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    items = recent.get("items", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])

    selected = []
    for form, filed, item_str, accession, document in zip(
            forms, dates, items, accessions, documents):
        if form != "8-K" or "5.02" not in (item_str or ""):
            continue
        try:
            filed_on = datetime.strptime(filed, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if start_date <= filed_on <= end_date:
            selected.append({"filing_date": filed, "accession": accession,
                             "document": document})
    return selected


# ---------------------------------------------------------------------------
# Steps 3-4: HTML -> text -> Item 5.02 section
# ---------------------------------------------------------------------------
def html_to_text(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "head", "title", "ix:header"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ").replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def extract_item_502(text):
    """Text from 'Item 5.02' up to the next Item heading or 'Signature(s)'.

    If 'Item 5.02' appears more than once (e.g., a cover-page list), the
    longest candidate section is used, since that is the actual disclosure.
    """
    end_re = re.compile(r"\bItem\s*(\d{1,2}\.\d{2})|\bSignatures?\b", re.I)
    best = ""
    for start in re.finditer(r"\bItem\s*5\.02\b", text, re.I):
        end = len(text)
        for match in end_re.finditer(text, start.end()):
            if match.group(1) != "5.02":
                end = match.start()
                break
        section = text[start.start():end].strip()
        if len(section) > len(best):
            best = section
    return best or None


# ---------------------------------------------------------------------------
# Step 5: text helpers
# ---------------------------------------------------------------------------
def split_sentences(text):
    protected = ABBREVIATION_RE.sub(lambda m: m.group(1) + "<DOT>", text)
    protected = re.sub(
        r"(U<DOT>S)<DOT>(\s+)(?=(?:Since|In|On|The|He|She|They|From|As|During|Prior"
        r"|Before|After|Mr|Ms|Mrs|Dr|This|There|Additionally)\b)",
        r"\1.\2", protected)
    parts = re.split(r"(?<=[.!?])\d{0,2}\s+(?=[A-Z\"(])", protected)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def clean_token(token):
    token = token.rstrip(",")
    if token.endswith("'s"):
        token = token[:-2]
    return token.rstrip("'")


def is_name_word(word):
    bare = word.rstrip(".")
    if len(bare) == 1 and word.endswith("."):
        return True                      # a middle initial such as "A."
    if bare.lower() in STOP_WORDS:
        return False
    # all-caps words are acronyms (PSUs, CIB), not names
    if len(bare) > 1 and bare.upper() == bare and bare not in ROMAN_SUFFIXES:
        return False
    if len(bare) > 1 and not re.search(r"[a-z]", bare):
        return False
    return True


def full_names_in(sentence):
    """Return (start, end, name) for each 2-4 word capitalized name."""
    names = []
    for run in CAP_RUN_RE.finditer(sentence):
        group = []
        for tok in NAME_TOKEN_RE.finditer(run.group()):
            word = clean_token(tok.group())
            if is_name_word(word):
                group.append((tok.start(), tok.end(), word))
            else:
                names.extend(_finish_name(group, run.start()))
                group = []
        names.extend(_finish_name(group, run.start()))
    return names


def _finish_name(group, offset):
    while group and len(group[-1][2].rstrip(".")) == 1:   # trailing initial
        group.pop()
    if not 2 <= len(group) <= 4:
        return []
    words = [g[2] for g in group]
    last = words[-1].rstrip(".")
    words[-1] = last + "." if last in ("Jr", "Sr") else last
    return [(offset + group[0][0], offset + group[-1][1], " ".join(words))]


def surname_of(full_name):
    words = [w for w in full_name.split()
             if w.rstrip(".") not in ("Jr", "Sr") and w not in ROMAN_SUFFIXES]
    return words[-1] if words else full_name


def build_name_map(sentences):
    """Surname -> the longest full name used for that person in the filing."""
    name_map = {}
    for sentence in sentences:
        for _, _, full in full_names_in(sentence):
            surname = surname_of(full)
            if len(full.split()) > len(name_map.get(surname, "").split()):
                name_map[surname] = full
    return name_map


def canonical(name, name_map):
    longest = name_map.get(surname_of(name))
    if longest and set(name.split()) <= set(longest.split()):
        return longest
    return name


def person_mentions(sentence, name_map):
    """All mentions of people in a sentence as (start, end, full name)."""
    mentions = [(s, e, canonical(n, name_map)) for s, e, n in full_names_in(sentence)
                if not UNIT_CONTEXT_RE.search(sentence[max(0, s - 40):s])]

    def overlaps(s, e):
        return any(ms < e and s < me for ms, me, _ in mentions)

    for match in MESSRS_RE.finditer(sentence):
        for group in (1, 2):
            s, e = match.span(group)
            if not overlaps(s, e):
                surname = clean_token(match.group(group))
                start = match.start() if group == 1 else s
                mentions.append((start, e, name_map.get(surname, surname)))
    for match in HONORIFIC_RE.finditer(sentence):
        s, e = match.span(1)
        if not overlaps(s, e):
            surname = clean_token(match.group(1))
            mentions.append((match.start(), e, name_map.get(surname, surname)))
    return sorted(mentions)


def to_iso(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS[m.group(1).lower()],
                    int(m.group(2))).isoformat()
    except (ValueError, KeyError):
        return None


def clean_title(title):
    title = re.sub(r"\s+", " ", title).strip(" ,;")
    title = re.sub(r"\s+of\s+(?:the\s+)?(?:Company|Firm|Corporation)\.?$", "",
                   title, flags=re.I)
    title = re.sub(r"\s+of\s+(?:[A-Z][\w.&'\-]*\s+){0,4}"
                   r"(?:Corporation|Inc|Co|Company|Incorporated)\.?$", "", title)
    if title.endswith(".") and not re.search(r"[A-Z]\.[A-Z]\.$", title):
        title = title[:-1]
    return title.strip(" ,;")


# ---------------------------------------------------------------------------
# Steps 5-6: find events in a sentence
# ---------------------------------------------------------------------------
def keyword_hits(sentence):
    """Return (start, end, event_type, mode) for each event keyword."""
    blanked = NOT_AN_EVENT_RE.sub(lambda m: " " * len(m.group()), sentence)
    hypothetical = bool(CONDITIONAL_RE.search(sentence))
    hits = []
    for m in DEPART_RE.finditer(blanked):
        if hypothetical and m.group().lower().startswith("terminat"):
            continue
        hits.append((m.start(), m.end(), "departure", "normal"))
    for m in TRANSITION_TO_RE.finditer(blanked):
        group = 1 if m.group(1) else 2
        hits.append((m.start(group), m.end(group), "appointment", "subject"))
    # hide departure phrases so "re-election" is not read as "election"
    for s, e, kind, _ in list(hits):
        if kind != "departure":
            continue
        blanked = blanked[:s] + " " * (e - s) + blanked[e:]
    for m in APPOINT_RE.finditer(blanked):
        hits.append((m.start(), m.end(), "appointment", "normal"))
    for m in SUCCEED_RE.finditer(blanked):
        hits.append((m.start(), m.end(), "appointment", "succeed"))
    return hits


def coordinated_group(sentence, mentions, idx, direction):
    """'Doug Petno, 61, and Troy Rohrbaugh ...' -> both mentions."""
    group = [idx]
    i = idx
    while True:
        j = i - 1 if direction == "back" else i + 1
        if not 0 <= j < len(mentions):
            break
        left, right = (mentions[j], mentions[i]) if direction == "back" else (mentions[i], mentions[j])
        if not COORDINATED_RE.match(sentence[left[1]:right[0]]):
            break
        group.append(j)
        i = j
    return sorted(group)


def people_for_hit(sentence, mentions, hit):
    """Indices of the people a keyword refers to (and a predecessor, if any)."""
    k_start, k_end, _, mode = hit
    before = [i for i, m in enumerate(mentions) if m[1] <= k_start]
    after = [i for i, m in enumerate(mentions) if m[0] >= k_end]

    if mode == "succeed":
        if not before:            # "He succeeds X": subject is a pronoun
            return [], None
        predecessor = None
        if after and DIRECT_AFTER_SUCCEED_RE.match(sentence[k_end:mentions[after[0]][0]]):
            predecessor = after[0]
        return coordinated_group(sentence, mentions, before[-1], "back"), predecessor

    # "the Board appointed Jane Doe", "the resignation of Mr. Smith"
    if mode == "normal" and after and DIRECT_OBJECT_RE.match(
            sentence[k_end:mentions[after[0]][0]]):
        return coordinated_group(sentence, mentions, after[0], "forward"), None
    # otherwise the subject of the verb: the closest person named before it
    if before:
        return coordinated_group(sentence, mentions, before[-1], "back"), None
    if after and mode == "normal":
        return coordinated_group(sentence, mentions, after[0], "forward"), None
    return [], None


def region_end(sentence, mentions, last_idx, own_names):
    """Where the text about this person stops: at the next other person."""
    for j in range(last_idx + 1, len(mentions)):
        start, _, name = mentions[j]
        if name in own_names:
            continue
        if re.search(r"\b(?:succeed\w*|replac\w*)\s*" + HONORIFIC_ONLY + r"$",
                     sentence[:start], re.I):
            continue          # predecessor named after "succeeds"
        return start
    return len(sentence)


def titles_between(sentence, start, end):
    return [m for m in TITLE_RE.finditer(sentence, start, end) if m.end() <= end]


def is_as_title(sentence, match):
    return bool(AS_BEFORE_TITLE_RE.search(sentence[max(0, match.start() - 60):match.start()]))


def title_for(sentence, mentions, group, event_type, hit):
    """Pick the title for an appointment (new role) or a departure (old role)."""
    k_start, k_end = hit[0], hit[1]
    names = {mentions[i][2] for i in group}
    first, last = mentions[group[0]], mentions[group[-1]]
    end = region_end(sentence, mentions, group[-1], names)
    after_start = max(last[1], k_end)
    after = titles_between(sentence, after_start, end)

    if event_type == "appointment":
        for m in after:
            if is_as_title(sentence, m):
                return clean_title(m.group())
        if after:
            return clean_title(after[0].group())
        if BOARD_SEAT_RE.search(sentence[after_start:end]):
            return "director"
    else:
        for m in after:
            if is_as_title(sentence, m):
                return clean_title(m.group())
        if BOARD_SEAT_RE.search(sentence[k_end:end]):
            return "director"
        # appositive: "Donald Robertson, Vice President, ... notified ... retire"
        between = titles_between(sentence, last[1], k_start) if k_start > last[1] else []
        if between:
            return clean_title(between[0].group())
        if after:
            return clean_title(after[0].group())

    back_start = max((m[1] for i, m in enumerate(mentions)
                      if i < group[0] and m[2] not in names), default=0)
    backward = titles_between(sentence, back_start, first[0])
    return clean_title(backward[-1].group()) if backward else None


def effective_date(sentence, k_start, defined_dates):
    m = EFFECTIVE_DATE_RE.search(sentence)
    if m:
        return to_iso(m.group())
    term = EFFECTIVE_TERM_RE.search(sentence)
    if term and term.group(1).lower() in defined_dates:
        return defined_dates[term.group(1).lower()]
    if re.search(r"\beffective\s+immediately\b", sentence, re.I):
        return to_iso(sentence)        # the date the event happened
    if re.search(r"\beffective\b", sentence, re.I):
        return None                    # effective upon something that isn't a date
    return to_iso(sentence[k_start:]) or to_iso(sentence)


def extract_events(section):
    """Return a list of event dicts found in an Item 5.02 section."""
    sentences = split_sentences(section)
    name_map = build_name_map(sentences)
    defined_dates = {term.lower(): to_iso(d) for d, term in DEFINED_DATE_RE.findall(section)}

    events = {}      # (name, event_type) -> event
    order = []
    successor_of = {}   # predecessor name -> successor name

    def record(name, event_type, title, eff):
        key = (name, event_type)
        if key not in events:
            events[key] = {"person_name": name, "event_type": event_type,
                           "title": title, "effective_date": eff}
            order.append(key)
        else:
            events[key]["title"] = events[key]["title"] or title
            events[key]["effective_date"] = events[key]["effective_date"] or eff

    for sentence in sentences:
        mentions = person_mentions(sentence, name_map)
        hits = keyword_hits(sentence)
        if not mentions or not hits:
            continue

        found = {}   # name -> {event_type: (title, date)}
        for hit in hits:
            group, predecessor = people_for_hit(sentence, mentions, hit)
            for i in group:
                name = mentions[i][2]
                slot = found.setdefault(name, {})
                if hit[2] not in slot or slot[hit[2]][0] is None:
                    slot[hit[2]] = (title_for(sentence, mentions, group, hit[2], hit),
                                    effective_date(sentence, hit[0], defined_dates))
            if predecessor is not None and group:
                pred_name = mentions[predecessor][2]
                pred_hit = (mentions[predecessor][0], mentions[predecessor][1], "departure", "normal")
                own = title_for(sentence, mentions, [predecessor], "departure", pred_hit)
                successor_title = found[mentions[group[0]][2]]["appointment"][0]
                successor_of[pred_name] = mentions[group[0]][2]
                slot = found.setdefault(pred_name, {})
                slot.setdefault("departure", (own or successor_title,
                                              effective_date(sentence, hit[0], defined_dates)))

        for name, by_type in found.items():
            if "departure" in by_type and "appointment" in by_type:
                old, new = by_type["departure"][0], by_type["appointment"][0]
                title = f"{old} -> {new}" if old and new and old != new else (new or old)
                eff = by_type["appointment"][1] or by_type["departure"][1]
                record(name, "both", title, eff)
            else:
                event_type, (title, eff) = next(iter(by_type.items()))
                record(name, event_type, title, eff)

    # One row per person: departure + appointment in one filing becomes "both"
    merged = []
    by_person = {}
    for key in order:
        by_person.setdefault(key[0], []).append(events[key])
    for name, evs in by_person.items():
        types = {e["event_type"] for e in evs}
        if len(evs) == 1:
            merged.append(evs[0])
            continue
        dep = next((e for e in evs if e["event_type"] == "departure"), None)
        app = next((e for e in evs if e["event_type"] == "appointment"), None)
        both = next((e for e in evs if e["event_type"] == "both"), None)
        if both is None and dep and app:
            old, new = dep["title"], app["title"]
            title = f"{old} -> {new}" if old and new and old != new else (new or old)
            both = {"person_name": name, "event_type": "both", "title": title,
                    "effective_date": app["effective_date"] or dep["effective_date"]}
        if both is not None:
            for e in evs:
                both["title"] = both["title"] or e["title"]
                both["effective_date"] = both["effective_date"] or e["effective_date"]
            merged.append(both)
        else:
            merged.extend(evs)
        del types

    # Fill missing titles/dates from other sentences about the same person
    for ev in merged:
        surname = surname_of(ev["person_name"])
        related = [s for s in sentences if surname in s]
        if not ev["effective_date"]:
            for s in related:
                m = EFFECTIVE_DATE_RE.search(s)
                if m:
                    ev["effective_date"] = to_iso(m.group())
                    break
        if not ev["title"]:
            for s in related:
                pos = s.index(surname) + len(surname)
                for m in TITLE_RE.finditer(s, pos):
                    if is_as_title(s, m):
                        ev["title"] = clean_title(m.group())
                        break
                if ev["title"]:
                    break

    final = {ev["person_name"]: ev for ev in merged}
    for pred, succ in successor_of.items():
        if pred in final and succ in final and not final[pred]["effective_date"]:
            final[pred]["effective_date"] = final[succ]["effective_date"]

    return [{
        "event_type": ev["event_type"],
        "person_name": ev["person_name"] or NOT_FOUND,
        "title": ev["title"] or NOT_FOUND,
        "effective_date": ev["effective_date"] or NOT_FOUND,
    } for ev in merged]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_company(company, start_date, end_date):
    ticker, cik = company["ticker"], company["cik"]
    rows = []

    response = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if response is None:
        print(f"  WARNING: skipping {ticker}; submissions data unavailable")
        return rows
    try:
        submissions = response.json()
    except ValueError:
        print(f"  WARNING: skipping {ticker}; submissions data was not valid JSON")
        return rows

    company_name = company.get("name") or submissions.get("name") or NOT_FOUND
    filings = select_filings(submissions, start_date, end_date)
    if not filings:
        print(f"{ticker}: No executive events in past 12 months")
        return rows

    for filing in filings:
        filing_date = filing["filing_date"]
        url = ("https://www.sec.gov/Archives/edgar/data/"
               f"{int(cik)}/{filing['accession'].replace('-', '')}/"
               f"{filing['document']}")
        doc = fetch(url)
        if doc is None:
            continue
        try:
            section = extract_item_502(html_to_text(doc.content))
            if not section:
                print(f"  WARNING: {ticker} | {filing_date} | "
                      "could not locate the Item 5.02 section")
                continue
            events = extract_events(section)
        except Exception as err:  # keep going on any parsing problem
            print(f"  WARNING: {ticker} | {filing_date} | could not parse document ({err})")
            continue

        if not events:
            print(f"{ticker} | {filing_date} | No departure/appointment found "
                  "(likely compensation-only)")
            continue

        for ev in events:
            print(f"{ticker} | {filing_date} | {ev['event_type']} | "
                  f"{ev['person_name']} | {ev['title']}")
            rows.append({
                "company": company_name,
                "ticker": ticker,
                "cik": cik,
                "filing_date": filing_date,
                **ev,
            })
    return rows


def main():
    today = date.today()
    start_date = one_year_before(today)
    print(f"Looking for Item 5.02 8-K filings from {start_date} to {today}\n")

    all_rows = []
    for company in COMPANIES:
        print(f"--- {company['ticker']} ---")
        all_rows.extend(process_company(company, start_date, today))
        print()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({col: (row.get(col) or NOT_FOUND) for col in CSV_COLUMNS})

    print(f"Saved {len(all_rows)} events to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
