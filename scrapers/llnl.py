"""
LLNL (Lawrence Livermore National Labs) — construction opportunities.

Page renders a big HTML table with columns:
  Acquisition Type | Execution Method | NAICS | Project Name |
  Estimated Value  | Estimated Start  | Special Instructions

We filter to rows where Acquisition Type = "Construction".

Dates are quarter-coded ("Apr-26", "Q3 FY26", etc.) — too vague for a real
due date, so we treat them as "no due date" and let the construction filter
+ NEW badge surface them.
"""
from __future__ import annotations

from typing import List

from .base import BaseScraper, Lead
from .http import fetch_html


URL = "https://procurement.llnl.gov/opportunities"


class LLNLScraper(BaseScraper):
    name = "LLNL"
    region = "NorCal"
    agency = "Lawrence Livermore National Labs (LLNL)"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        # The construction table has a tablefield class with known headers
        table = soup.find("table", class_="tablefield")
        if not table:
            return []

        # Map header text → cell index so we don't depend on column order
        header_row = table.find("tr")
        if not header_row:
            return []
        headers = [
            th.get_text(strip=True).lstrip("\ufeff").lower()
            for th in header_row.find_all(["th", "td"])
        ]

        def idx(name: str) -> int:
            for i, h in enumerate(headers):
                if name in h:
                    return i
            return -1

        i_type    = idx("acquisition type")
        i_project = idx("project name")
        i_value   = idx("estimated value")
        i_start   = idx("estimated start")
        i_naics   = idx("naics")

        if i_project < 0:
            return []

        leads: List[Lead] = []
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) <= i_project:
                continue

            acq_type = cells[i_type] if i_type >= 0 else ""
            title    = cells[i_project]
            value    = cells[i_value] if i_value >= 0 else ""
            start    = cells[i_start] if i_start >= 0 else ""
            naics    = cells[i_naics] if i_naics >= 0 else ""

            # Filter: construction work only (skip Services, IT, etc.)
            if "construction" not in acq_type.lower():
                continue
            if not title:
                continue

            description_parts = []
            if value: description_parts.append(f"Est. value: {value}")
            if start: description_parts.append(f"Est. start: {start}")
            if naics: description_parts.append(f"NAICS: {naics}")

            leads.append(Lead(
                title=title,
                agency=self.agency,
                rfp_id="",            # LLNL doesn't pre-publish solicitation numbers
                rfp_type="Construction",
                posted=None,
                due=None,             # quarter-coded only
                url=URL,
                region=self.region,
                description=" | ".join(description_parts),
                category="Construction",  # source-provided — gets auto-qualified
                stage="planning",     # forecast, not yet open
            ))
        return leads
