"""
bd-leads — top-level entrypoint.

Runs daily via GitHub Action. End-to-end flow:
  1. Run every registered scraper to collect raw leads.
  2. Apply construction filter, dedupe, trim closed bids, sort.
  3. Tag new items via SeenTracker (and persist seen.json).
  4. Render the HTML page to docs/index.html.
  5. Print a summary.

Failures in any one scraper don't crash the run — they're logged but the
pipeline continues with whatever else succeeded.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from aggregate import collect_all_leads, aggregate, stamp_new
from generate_html import generate
from seen_tracker import SeenTracker


def main() -> int:
    print("=" * 60)
    print("bd-leads — daily refresh")
    print("=" * 60)

    # 1. Scrape
    try:
        raw = collect_all_leads()
    except Exception as e:
        print(f"\nFATAL: scraping pass failed entirely: {e}")
        traceback.print_exc()
        return 1
    print(f"\n→ Pulled {len(raw)} raw leads from all sources\n")

    # 2. Aggregate (filter + dedupe + trim + sort)
    curated = aggregate(raw)
    print(f"→ {len(curated)} leads after construction filter, dedupe, and closed-trim\n")

    # 3. Stamp seen-state
    tracker = SeenTracker(path=Path("data/seen.json"))
    curated = stamp_new(curated, tracker)
    new_count = sum(1 for l in curated if l.is_new)
    print(f"→ {new_count} flagged as NEW (first seen within last 7 days)\n")

    # 4. Render
    out = generate(curated, output_path=Path("docs/index.html"))
    size_kb = out.stat().st_size / 1024
    print(f"→ Wrote {out} ({size_kb:.1f} KB)\n")

    # 5. Summary
    print("Summary:")
    print(f"  • Total leads on page: {len(curated)}")
    print(f"  • New (last 7 days):   {new_count}")
    print(f"  • Output:              {out}")
    print(f"  • Seen tracker:        {tracker.path}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
