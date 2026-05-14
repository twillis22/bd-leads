"""
UC Berkeley Capital Strategies — Open RFQ's.

The page has multiple tables; the one we want has headers:
  Project Name | Number | Due | Awardee

Awardee == "To Be Announced" means the RFQ is still open. Anything else
(awarded, etc.) we treat as closed.

Due column format: "May 20, 202612:00PM PST" — no space before time, handled
by parse_date_loose.
"""
from __future__ import annotations

from typing import List

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://capitalstrategies.berkeley.edu/rfq"


class UCBerkeleyScraper(BaseScraper):
    name = "UC Berkeley"
    region = "NorCal"
    agency = "UC Berkeley"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        # Find the table whose first row has "Project Name" — there are multiple
        # tables on the page (decorative, headers, etc.).
        target_table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if not rows:
                continue
            first = [c.get_text(strip=True).lower() for c in rows[0].find_all(["td", "th"])]
            if any("project name" in c for c in first):
                target_table = t
                break
        if not target_table:
            return []

        leads: List[Lead] = []
        for tr in target_table.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(cells) < 4:
                continue
            title, number, due_str, awardee = cells[0], cells[1], cells[2], cells[3]
            if not title:
                continue

            is_open = "announce" in awardee.lower() or "tba" in awardee.lower() or "tbd" in awardee.lower()
            stage = "open" if is_open else "awarded"

            leads.append(Lead(
                title=title,
                agency=self.agency,
                rfp_id=number,
                rfp_type="RFQ",
                posted=None,
                due=parse_date_loose(due_str),
                url=URL,
                region=self.region,
                description=f"Awardee: {awardee}" if awardee else "",
                category="",
                stage=stage,
            ))
        return leads
