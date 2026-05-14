"""
City of Berkeley — Bid & Proposal Opportunities.

Clean HTML table with headers:
  Name | Spec # | Due | Posted

The Name cell usually contains a link directly to the bid PDF/page on the
city's procurement system.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://berkeleyca.gov/doing-business/working-city/bid-proposal-opportunities"


class CityOfBerkeleyScraper(BaseScraper):
    name = "City of Berkeley"
    region = "NorCal"
    agency = "City of Berkeley"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        # Headers are: Name | Spec # | Due | Posted
        table = soup.find("table")
        if not table:
            return []
        # Identify column indices from the header row
        header_row = table.find("tr")
        if not header_row:
            return []
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

        def idx(name: str) -> int:
            for i, h in enumerate(headers):
                if name in h:
                    return i
            return -1

        i_name   = idx("name")
        i_spec   = idx("spec")
        i_due    = idx("due")
        i_posted = idx("posted")

        if i_name < 0:
            return []

        leads: List[Lead] = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) <= i_name:
                continue

            name_cell = cells[i_name]
            title = name_cell.get_text(" ", strip=True)
            if not title:
                continue

            link = name_cell.find("a", href=True)
            lead_url = urljoin(URL, link["href"]) if link else URL

            rfp_id   = cells[i_spec].get_text(strip=True) if i_spec >= 0 and len(cells) > i_spec else ""
            due_str  = cells[i_due].get_text(strip=True)  if i_due  >= 0 and len(cells) > i_due else ""
            posted_s = cells[i_posted].get_text(strip=True) if i_posted >= 0 and len(cells) > i_posted else ""

            leads.append(Lead(
                title=title,
                agency=self.agency,
                rfp_id=rfp_id,
                rfp_type=self._infer_type_from_title(title),
                posted=parse_date_loose(posted_s),
                due=parse_date_loose(due_str),
                url=lead_url,
                region=self.region,
                description="",
                category="",
                stage="open",
            ))
        return leads

    @staticmethod
    def _infer_type_from_title(title: str) -> str:
        t = title.lower()
        for token in ("rfp", "rfq", "ifb", "bid"):
            if token in t:
                return token.upper()
        return ""
