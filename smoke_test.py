"""
Smoke test for the PlanetBids scraper.

Runs against the configured portals, prints a summary, then applies the
construction filter and shows what survives.
"""
from __future__ import annotations

import sys
from collections import Counter

from scrapers import PlanetBidsScraper, PORTALS
from filters import filter_construction, is_construction_relevant


def main():
    print(f"Fetching {len(PORTALS)} PlanetBids portal(s)...\n")
    leads = PlanetBidsScraper.fetch_all()

    print(f"\n→ {len(leads)} total leads pulled\n")
    if not leads:
        print("No leads. Bailing.")
        sys.exit(1)

    # Stage breakdown
    stages = Counter(l.stage for l in leads)
    print(f"Stage breakdown: {dict(stages)}")

    # Type breakdown
    types = Counter(l.rfp_type or "(unknown)" for l in leads)
    print(f"RFP-type breakdown: {dict(types)}\n")

    # Apply construction filter
    construction = filter_construction(leads)
    print(f"After construction filter: {len(construction)} of {len(leads)} kept\n")

    # Show a sample of each
    print("=" * 70)
    print("SAMPLE: 5 construction-relevant leads")
    print("=" * 70)
    for lead in construction[:5]:
        days = lead.days_remaining
        days_str = f"{days}d remaining" if days is not None and days >= 0 else (
            "past due" if days is not None else "no due date"
        )
        print(f"\n  [{lead.agency}] {lead.rfp_id}")
        print(f"    {lead.title}")
        print(f"    {lead.rfp_type} | stage={lead.stage} | {days_str}")
        print(f"    {lead.url}")

    print("\n" + "=" * 70)
    print("SAMPLE: 3 leads that were FILTERED OUT (sanity check)")
    print("=" * 70)
    filtered_out = [l for l in leads if not is_construction_relevant(l)]
    for lead in filtered_out[:3]:
        print(f"\n  [{lead.agency}] {lead.rfp_id}")
        print(f"    {lead.title}")

    print()


if __name__ == "__main__":
    main()
