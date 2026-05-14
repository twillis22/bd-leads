"""
Mid-Peninsula Water District — Bids/RFP/RFQ page.

No table here. Each open RFP renders as an H3 heading like:
  "Request for Proposals - Folger EOC+-"
  "Request for Proposals - Exbourne and West Belmont Water Tank Improvements+-"
The "+-" suffix is a collapsible-section toggle artifact.

Inside the section is at least one PDF link to the full RFP document. We
emit one Lead per H3 that starts with "Request for".
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://www.midpeninsulawater.org/bid"


class MidPeninsulaWaterScraper(BaseScraper):
    name = "Mid-Peninsula Water"
    region = "NorCal"
    agency = "Mid-Peninsula Water District"

    HEADING_PATTERN = re.compile(
        r"^\s*(request for|invitation for|notice of|advertisement for)",
        re.IGNORECASE,
    )

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        leads: List[Lead] = []
        seen_pdfs: set[str] = set()

        for h in soup.find_all(["h2", "h3", "h4"]):
            raw_title = h.get_text(" ", strip=True)
            if not self.HEADING_PATTERN.match(raw_title):
                continue

            # Strip trailing accordion-toggle artifacts ("+-", "+ -", " +", etc.)
            title = re.sub(r"[\s+\-]+$", "", raw_title).strip()

            # Find the PDF link associated with this section. Walk forward
            # through siblings until we hit another heading or a PDF anchor.
            pdf_href = None
            due_str = ""
            for sibling in h.find_all_next():
                if sibling.name in ("h2", "h3", "h4"):
                    break
                if sibling.name == "a" and sibling.get("href", "").lower().endswith(".pdf"):
                    pdf_href = sibling["href"]
                    break
                # Capture any date-looking text along the way
                if not due_str:
                    txt = sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling)
                    if "due" in txt.lower() or "deadline" in txt.lower():
                        due_str = txt

            if pdf_href:
                if pdf_href in seen_pdfs:
                    continue
                seen_pdfs.add(pdf_href)

            leads.append(Lead(
                title=title,
                agency=self.agency,
                rfp_id="",
                rfp_type=self._classify_type(title),
                posted=None,
                due=parse_date_loose(due_str) if due_str else None,
                url=urljoin(URL, pdf_href) if pdf_href else URL,
                region=self.region,
                description="",
                category="",
                stage="open",
            ))
        return leads

    @staticmethod
    def _classify_type(title: str) -> str:
        t = title.lower()
        if t.startswith("request for proposal"): return "RFP"
        if t.startswith("request for qual"):     return "RFQ"
        if t.startswith("invitation for bid"):   return "IFB"
        return ""
