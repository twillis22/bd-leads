"""
Aggregator: pulls leads from every registered scraper, applies the
construction filter, dedupes, trims closed bids to N-most-recent per source,
sorts by due date, and tags new items via SeenTracker.

This is the layer that lives between the scrapers and the HTML generator.
Scrapers just produce raw leads — this turns them into the curated view
Tyler actually wants to look at.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List

from scrapers.base import Lead
from scrapers.planetbids import PlanetBidsScraper
from scrapers.llnl import LLNLScraper
from scrapers.carlsbad_usd import CarlsbadUSDScraper
from scrapers.city_of_berkeley import CityOfBerkeleyScraper
from scrapers.uc_berkeley import UCBerkeleyScraper
from scrapers.uc_davis_health import UCDavisHealthScraper
from scrapers.mid_peninsula_water import MidPeninsulaWaterScraper
from scrapers.poway_usd import PowayUSDScraper
from scrapers.slac import SLACScraper
from filters import filter_construction
from seen_tracker import SeenTracker


# ----------------------------------------------------------------------------
# Tunable knobs
# ----------------------------------------------------------------------------

# How many recently-closed bids to surface PER SOURCE. Tyler asked for this
# to be configurable so he can disable the closed-bids feature entirely
# without code surgery. Set to 0 to hide closed bids entirely.
CLOSED_BIDS_TO_KEEP_PER_SOURCE: int = 3


# ----------------------------------------------------------------------------
# Aggregator
# ----------------------------------------------------------------------------

def collect_all_leads() -> List[Lead]:
    """
    Run every registered scraper and concatenate their leads.
    Per-scraper failures are caught in BaseScraper subclasses (they return [])
    so one bad source can never kill the whole run.
    """
    leads: List[Lead] = []

    print("Running PlanetBids scraper...")
    leads.extend(PlanetBidsScraper.fetch_all())

    # Custom municipal scrapers (Tier-1 from the Pass 2 probe report).
    # Each is HTTP-based, no Playwright. New ones get added here.
    custom_scrapers = [
        LLNLScraper(),
        CarlsbadUSDScraper(),
        CityOfBerkeleyScraper(),
        UCBerkeleyScraper(),
        UCDavisHealthScraper(),
        MidPeninsulaWaterScraper(),
        PowayUSDScraper(),
        SLACScraper(),
    ]
    print(f"\nRunning {len(custom_scrapers)} custom scrapers...")
    for s in custom_scrapers:
        try:
            batch = s.fetch()
            print(f"  ✓ {s.name}: {len(batch)} leads")
            leads.extend(batch)
        except Exception as e:
            print(f"  ✗ {s.name}: FAILED — {e}")

    # v2 candidates (need Playwright or further investigation):
    #   SFPUC, Judicial Council, City of Gilroy, City of Orinda,
    #   County of Placer, County of Sonoma, San Marcos USD, SF DPW

    return leads


def aggregate(
    leads: Iterable[Lead],
    closed_per_source: int = CLOSED_BIDS_TO_KEEP_PER_SOURCE,
) -> List[Lead]:
    """
    Curate the raw lead stream into the final list for display.

    Steps (in order):
      1. Apply construction-relevance filter
      2. Dedupe by stable_id (same bid scraped twice? keep one)
      3. Split into open vs closed
      4. Trim closed list to top-N most recently-closed per source
      5. Sort: open by due-date ASC, closed by due-date DESC
      6. Concat (open first)
    """
    # 1. Construction filter
    leads = list(filter_construction(leads))

    # 2. Dedupe
    seen_ids: set[str] = set()
    deduped: List[Lead] = []
    for lead in leads:
        sid = lead.stable_id()
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        deduped.append(lead)

    # 3. Split open / closed
    open_leads = [l for l in deduped if not l.is_past_due and l.stage != "closed"]
    closed_leads = [l for l in deduped if l.is_past_due or l.stage == "closed"]

    # 4. Trim closed per agency (most recent first)
    closed_leads.sort(key=lambda l: l.due or datetime.min, reverse=True)
    trimmed_closed: List[Lead] = []
    per_agency_count: dict[str, int] = {}
    if closed_per_source > 0:
        for lead in closed_leads:
            n = per_agency_count.get(lead.agency, 0)
            if n < closed_per_source:
                trimmed_closed.append(lead)
                per_agency_count[lead.agency] = n + 1

    # 5. Sort open by due date ASC (closest deadlines first); leads with no
    # due date go to the end.
    def open_sort_key(l: Lead):
        return (l.due is None, l.due or datetime.max)

    open_leads.sort(key=open_sort_key)

    # 6. Concat
    return open_leads + trimmed_closed


def stamp_new(leads: List[Lead], tracker: SeenTracker | None = None) -> List[Lead]:
    """
    Tag each lead with is_new + first_seen using the persistent tracker.
    Saves the tracker file on success.
    """
    tracker = tracker or SeenTracker()
    tracker.load()
    stamped = tracker.stamp(leads)
    tracker.save()
    return stamped


# ----------------------------------------------------------------------------
# Bucketing helpers used by the HTML generator
# ----------------------------------------------------------------------------

BUCKET_THIS_WEEK = "This Week"
BUCKET_NEXT_2_WEEKS = "Next 2 Weeks"
BUCKET_THIS_MONTH = "This Month"
BUCKET_LATER = "Later"
BUCKET_NO_DUE = "No Due Date"
BUCKET_CLOSED = "Recently Closed"


def bucket_for(lead: Lead) -> str:
    """Bucket a lead by due-date proximity. Used to group the HTML page."""
    if lead.stage == "closed" or lead.is_past_due:
        return BUCKET_CLOSED
    days = lead.days_remaining
    if days is None:
        return BUCKET_NO_DUE
    if days <= 7:
        return BUCKET_THIS_WEEK
    if days <= 14:
        return BUCKET_NEXT_2_WEEKS
    if days <= 30:
        return BUCKET_THIS_MONTH
    return BUCKET_LATER


BUCKET_ORDER = [
    BUCKET_THIS_WEEK,
    BUCKET_NEXT_2_WEEKS,
    BUCKET_THIS_MONTH,
    BUCKET_LATER,
    BUCKET_NO_DUE,
    BUCKET_CLOSED,
]
