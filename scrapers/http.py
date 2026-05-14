"""
Shared HTTP helpers for custom scrapers.

The PlanetBids scraper uses Playwright because PlanetBids is a JS-rendered
SPA. Most custom municipal sites are plain server-rendered HTML, so they
work fine with `requests + BeautifulSoup` — much faster than spinning up
a browser.

This module wraps the boilerplate so individual scraper files stay focused
on parsing logic.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_TIMEOUT = 20  # seconds


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[BeautifulSoup]:
    """
    GET the URL and return a parsed BeautifulSoup tree. Returns None on
    any failure (network error, non-200 status, malformed body) — scrapers
    should treat None as "skip this source" rather than raising.
    """
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Date parsing — each custom site formats dates a little differently. This
# centralizes the heuristics so each scraper doesn't reinvent it.
# ----------------------------------------------------------------------------

# Patterns we've seen across custom sites:
#   "May 28, 2026"
#   "May 20, 2026 12:00PM PST"
#   "May 20, 202612:00PM PST"        ← UC Berkeley — no space before time
#   "2 p.m. Thursday, June 18, 2026" ← UC Davis Health
#   "05/28/2026"
#   "May 29, 20262:00pm"             ← Carlsbad USD — no space before time
_MONTH_PATTERN = re.compile(
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
    r"(\d{1,2}),?\s*(\d{4})",
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")


def parse_date_loose(s: str) -> Optional[datetime]:
    """
    Tolerant date parser. Tries multiple formats and falls back to regex
    extraction of (month name + day + year) or (numeric MM/DD/YYYY).
    Returns None if no date pattern matches.

    Examples that work:
      "May 28, 2026"                  → datetime(2026, 5, 28)
      "May 20, 202612:00PM PST"       → datetime(2026, 5, 20)
      "2 p.m. Thursday, June 18, 2026" → datetime(2026, 6, 18)
      "05/28/2026"                    → datetime(2026, 5, 28)
    """
    if not s:
        return None
    s = s.strip()

    # Try the BaseScraper formats first via explicit strptime attempts
    for fmt in (
        "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d",
        "%B %d, %Y", "%b %d, %Y",
        "%B %d %Y", "%b %d %Y",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    # Loose regex fallbacks — find a month name + day + year anywhere
    m = _MONTH_PATTERN.search(s)
    if m:
        month_name, day, year = m.group(1), m.group(2), m.group(3)
        try:
            return datetime.strptime(f"{month_name[:3]} {day} {year}", "%b %d %Y")
        except ValueError:
            pass

    # Numeric MM/DD/YYYY anywhere
    m = _NUMERIC_DATE.search(s)
    if m:
        mo, d, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        try:
            return datetime(y, mo, d)
        except ValueError:
            pass

    return None
