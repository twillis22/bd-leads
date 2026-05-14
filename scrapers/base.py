"""
Base classes for the bd-leads scrapers.

Mirrors the pattern from bd-events: a single dataclass for the unit of output
(Lead), and a small abstract base class every scraper extends.

Lead.normalize() is the pivot point — every scraper produces Leads in a
consistent shape regardless of source quirks. The aggregator never cares
where a Lead came from.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional


# ----------------------------------------------------------------------------
# Lead data model
# ----------------------------------------------------------------------------

@dataclass
class Lead:
    """A single bid / RFP / RFQ opportunity from a public agency portal."""

    title: str                    # project title
    agency: str                   # source agency (e.g. "City of Sunnyvale")
    rfp_id: str                   # invitation #, e.g. "IFB PW26-19"
    rfp_type: str                 # "RFP" / "RFQ" / "IFB" / "Bid" etc.
    posted: Optional[datetime]    # when it was published
    due: Optional[datetime]       # close / due date (None if not parseable)
    url: str                      # direct link to the bid detail page
    region: str = "NorCal"        # "NorCal" / "SoCal" / "Other"
    description: str = ""         # if scrapeable
    category: str = ""            # source-provided category if any
    stage: str = "open"           # "open" / "closed" / "pending"
    is_new: bool = False          # first seen in last N days
    first_seen: str = ""          # ISO date string

    # --- helpers -----------------------------------------------------------

    @property
    def days_remaining(self) -> Optional[int]:
        """Days until the bid closes. Negative if past due. None if no due date."""
        if not self.due:
            return None
        now = datetime.now(timezone.utc)
        due = self.due if self.due.tzinfo else self.due.replace(tzinfo=timezone.utc)
        return (due - now).days

    @property
    def is_past_due(self) -> bool:
        d = self.days_remaining
        return d is not None and d < 0

    def to_dict(self) -> dict:
        """JSON-safe representation for persistence and the HTML page."""
        d = asdict(self)
        d["posted"] = self.posted.isoformat() if self.posted else None
        d["due"] = self.due.isoformat() if self.due else None
        d["days_remaining"] = self.days_remaining
        return d

    def stable_id(self) -> str:
        """
        Stable identifier for dedupe + seen-tracking.

        Prefer (agency, rfp_id). Fall back to (agency, title) if rfp_id is missing.
        These two combos rarely collide in practice — RFP numbers are agency-unique.
        """
        key = self.rfp_id or self.title
        return f"{self.agency}::{key}".lower().strip()


# ----------------------------------------------------------------------------
# Base scraper
# ----------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    Every scraper extends this. The contract is simple:
        scraper.fetch() -> List[Lead]

    Scrapers should swallow per-portal errors and return what they got rather
    than blowing up the whole aggregator. Log the failure, move on.
    """

    name: str = "unnamed"        # display name for logs, e.g. "PlanetBids"
    region: str = "NorCal"       # default region for emitted leads

    @abstractmethod
    def fetch(self) -> List[Lead]:
        """Fetch and parse leads from this source. Always returns a list."""
        ...

    # Helpful for subclasses
    def _safe_parse_date(self, s: str) -> Optional[datetime]:
        """
        Best-effort date parser for the formats we see in PlanetBids and friends.
        Returns None on failure rather than raising — never let one bad date
        kill an entire scrape.
        """
        if not s:
            return None
        s = s.strip()
        formats = [
            "%m/%d/%Y %I:%M%p",     # 05/27/2026 03:00pm
            "%m/%d/%Y %I:%M %p",    # 05/27/2026 3:00 PM
            "%m/%d/%Y",             # 05/27/2026
            "%Y-%m-%d %H:%M:%S",    # 2026-05-08 07:00:47
            "%Y-%m-%d %H:%M:%S.%f", # 2026-05-08 07:00:47.580
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None
