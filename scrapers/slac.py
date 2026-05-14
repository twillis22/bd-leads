"""
SLAC (Stanford Linear Accelerator) — CRMF Project Opportunity.

Unlike most agency pages, SLAC's supplier page describes a SINGLE
opportunity (the Cryogenic Module Repair Facility project) with detailed
milestone/timeline tables. There's no list of multiple bids.

We emit it as one Lead — Tyler still wants it on the dashboard for
awareness, and if other SLAC opportunities appear in future, we'll need a
different parse strategy. For now this is a deliberate one-Lead emit.
"""
from __future__ import annotations

import re
from typing import List

from .base import BaseScraper, Lead
from .http import fetch_html, parse_date_loose


URL = "https://suppliers.slac.stanford.edu/find-opportunities/crmf-project-opportunity"


class SLACScraper(BaseScraper):
    name = "SLAC"
    region = "NorCal"
    agency = "SLAC (Stanford)"

    def fetch(self) -> List[Lead]:
        soup = fetch_html(URL)
        if not soup:
            return []

        # The page title or main heading tells us the project name
        h = soup.find(["h1", "h2"], string=re.compile(r"CRMF", re.IGNORECASE))
        title = h.get_text(strip=True) if h else "CRMF Project Opportunity"

        # Look for a "Proposals Due" or "Bid" date in the activity/milestone tables
        due = None
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            label = cells[0].lower()
            if "proposals due" in label or "bids due" in label or "rfp release" in label:
                for c in cells[1:]:
                    d = parse_date_loose(c)
                    if d:
                        due = d
                        break
            if due:
                break

        return [Lead(
            title=title,
            agency=self.agency,
            rfp_id="CRMF",
            rfp_type="RFP",
            posted=None,
            due=due,
            url=URL,
            region=self.region,
            description="Cryogenic Module Repair Facility — multi-phase construction opportunity",
            category="Construction",
            stage="planning",
        )]
