"""
UC Davis Health — Projects Out to Bid.

Each bid renders as its own small key-value table with rows like:
  Project:              | 9558130 - ACC Basement RAD Mammography Update
  Solicitation Type:    | General Contractor Prequalification
  Documents:            | Advertisement (pdf)
  Prequalifications Due:| 2 p.m. Thursday, June 18, 2026

The first cell ("Project:", "Solicitation Type:", etc.) is the field label;
the second cell is the value. We walk every table-striped table and pull
the values into a Lead.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://health.ucdavis.edu/facilities/work-with-us/contractors/out-to-bid"


class UCDavisHealthScraper(BaseScraper):
    name = "UC Davis Health"
    region = "NorCal"
    agency = "UC Davis Health"

    # Field-label heuristics — left-hand cell values to recognize
    DUE_LABELS = (
        "due", "deadline", "prequalifications due", "proposals due",
        "submittals due", "bids due", "proposal due",
    )

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        leads: List[Lead] = []
        for table in soup.find_all("table", class_="table-striped"):
            project = ""
            sol_type = ""
            docs = ""
            due_str = ""
            doc_url = None

            for tr in table.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                label = cells[0].get_text(" ", strip=True).rstrip(":").lower()
                value_cell = cells[1]
                value = value_cell.get_text(" ", strip=True)

                if "project" == label or "project name" == label:
                    project = value
                elif "solicitation type" in label or "type" == label:
                    sol_type = value
                elif "document" in label:
                    docs = value
                    # First PDF link in the documents cell
                    a = value_cell.find("a", href=True)
                    if a:
                        doc_url = urljoin(URL, a["href"])
                elif any(d in label for d in self.DUE_LABELS):
                    due_str = value

            if not project:
                continue

            # Try to split "9558130 - ACC Basement RAD Mammography Update" into id + title
            rfp_id = ""
            title = project
            m = re.match(r"^([\w\d-]+)\s*-\s*(.+)$", project)
            if m:
                rfp_id, title = m.group(1).strip(), m.group(2).strip()

            leads.append(Lead(
                title=title,
                agency=self.agency,
                rfp_id=rfp_id,
                rfp_type=self._classify_type(sol_type),
                posted=None,
                due=parse_date_loose(due_str),
                url=doc_url or URL,
                region=self.region,
                description=sol_type,
                category="Construction",  # this page is exclusively construction
                stage="open",
            ))
        return leads

    @staticmethod
    def _classify_type(sol_type: str) -> str:
        s = sol_type.lower()
        if "prequal" in s and "design-build" in s: return "RFQual"
        if "prequal" in s: return "RFQual"
        if "request for qualifications" in s: return "RFQ"
        if "request for proposal" in s: return "RFP"
        if "bid" in s: return "Bid"
        return ""
