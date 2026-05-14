"""
Carlsbad Unified School District — Current RFQ, RFB, RFP page.

Clean HTML table with headers:
  Bid / RFQP No. | Description | Type | Docs Available | Submission Deadline

Submission Deadline column has the format "May 29, 20262:00pm" (no space
before time) — handled by parse_date_loose.
"""
from __future__ import annotations

from typing import List

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://carlsbadusd.net/9293_3"


class CarlsbadUSDScraper(BaseScraper):
    name = "Carlsbad USD"
    region = "SoCal"
    agency = "Carlsbad USD"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        table = soup.find("table", class_="dataTable")
        if not table:
            return []

        leads: List[Lead] = []
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue

            rfp_id = cells[0].get_text(strip=True)
            description = cells[1].get_text(" ", strip=True)
            rfp_type = cells[2].get_text(strip=True)
            due_str = cells[4].get_text(" ", strip=True)

            if not (rfp_id or description):
                continue

            # Title is the description; rfp_id is the ID
            # First link in the row is usually the PDF for the bid
            link = cells[1].find("a", href=True) or tr.find("a", href=True)
            lead_url = link["href"] if link else URL

            leads.append(Lead(
                title=description or rfp_id,
                agency=self.agency,
                rfp_id=rfp_id,
                rfp_type=rfp_type.upper() if rfp_type else "",
                posted=None,
                due=parse_date_loose(due_str),
                url=lead_url,
                region=self.region,
                description="",
                category="",
                stage="open",
            ))
        return leads
