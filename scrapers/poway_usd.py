"""
Poway USD — Current Bids.

Each bid renders in its own 2-row table. The cells contain run-together
text like:
  Cell A: "Bid 2027-02 VES EXTERIOR PAINTING AND STUCCO Bid Submittal..."
  Cell B: "Bid 2027-02 VES Exterior Painting and Stucco - Bid Document..."

Parse strategy:
  - The bid number is always the first token (Bid #### or RFP ####)
  - The title is the rest, up to "Bid Submittal" / "Bidders must" / a date
  - PDF link in the row is the lead URL
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://powayusd.edlioschool.com/apps/pages/current-bids"

# "Bid 2027-02", "RFP 2026-23", "RFQ 25-12", etc.
BID_NUM_RE = re.compile(
    r"\b(Bid|RFP|RFQ|RFQual|IFB)\s+([\w\d\-]+)\b",
    re.IGNORECASE,
)
# Truncation markers — title text usually stops here
TITLE_END = re.compile(
    r"(Bid Submittal|Bidders must|Pre[- ]Bid|Submittal Packets|Sealed bids)",
    re.IGNORECASE,
)
# Due date marker
DUE_DATE_RE = re.compile(
    r"(?:no later than|due (?:on|by)?|deadline:?)\s*"
    r"([A-Z][a-z]+\.?\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)


class PowayUSDScraper(BaseScraper):
    name = "Poway USD"
    region = "SoCal"
    agency = "Poway USD"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        leads: List[Lead] = []
        seen_ids: set[str] = set()

        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True)
            if not text:
                continue

            # Match a bid identifier at the start (or near it)
            m = BID_NUM_RE.search(text)
            if not m:
                continue
            rfp_type = m.group(1).upper()
            if rfp_type == "BID":
                rfp_type = "Bid"
            rfp_id_num = m.group(2)
            full_id = f"{rfp_type} {rfp_id_num}"

            # Title: after the bid id, before the "Bid Submittal..." marker
            tail = text[m.end():].strip()
            end_match = TITLE_END.search(tail)
            title = (tail[:end_match.start()] if end_match else tail).strip()
            title = re.sub(r"\s+", " ", title)
            if not title:
                continue

            # Dedupe: same bid often appears in multiple table rows
            if full_id in seen_ids:
                continue
            seen_ids.add(full_id)

            # Due date — search the rest of the table text
            due_match = DUE_DATE_RE.search(text)
            due = parse_date_loose(due_match.group(1)) if due_match else None

            # Lead URL — first href in the table
            a = table.find("a", href=True)
            lead_url = urljoin(URL, a["href"]) if a else URL

            leads.append(Lead(
                title=title.title()[:140],  # title-case the all-caps
                agency=self.agency,
                rfp_id=full_id,
                rfp_type=rfp_type,
                posted=None,
                due=due,
                url=lead_url,
                region=self.region,
                description="",
                category="",
                stage="open",
            ))
        return leads
