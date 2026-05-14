# bd-leads

Daily aggregator for open RFPs / construction solicitations across Bay Area public agency portals.
Companion project to `bd-events`; same architecture, different data model.

The output is a single bookmarkable HTML page at `docs/index.html`, refreshed daily by a GitHub Action and served via GitHub Pages.

---

## What this does

1. Scrapes open RFPs from every PlanetBids portal in `PORTALS` (currently 2 starter portals; add yours from the spreadsheet)
2. Pulls the most recent N closed bids per portal for awareness (default N=3, set to 0 to disable)
3. Filters down to construction-relevant work via keyword/category match
4. Dedupes, sorts by due-date ascending, tags new items
5. Renders an HTML page with filter pills (region, agency, due-this-week) and groupings (This Week / Next 2 Weeks / This Month / Later / Recently Closed)

---

## Project layout

```
bd-leads/
├── main.py                 # entrypoint
├── aggregate.py            # filter + dedupe + sort + closed-trim
├── filters.py              # construction-relevance keyword + category filter
├── generate_html.py        # renders docs/index.html
├── seen_tracker.py         # persistent first-seen state (data/seen.json)
├── smoke_test.py           # quick scraper-only sanity check
├── requirements.txt
├── scrapers/
│   ├── __init__.py
│   ├── base.py             # Lead dataclass + BaseScraper
│   ├── browser.py          # shared Playwright session
│   └── planetbids.py       # generic PlanetBids scraper (handles all portals)
├── data/
│   └── seen.json           # auto-committed by the GitHub Action
├── docs/
│   └── index.html          # auto-generated bookmarkable page
└── .github/workflows/
    └── update.yml          # daily cron at 13:00 UTC (06:00 PT)
```

---

## Local quickstart

```bash
pip install -r requirements.txt
playwright install chromium

# Just the scrapers:
python smoke_test.py

# Full pipeline (scrape → filter → render):
python main.py
# → writes docs/index.html
```

Open `docs/index.html` in a browser to see what the page looks like.

---

## Adding more portals

Open `scrapers/planetbids.py`, find the `PORTALS` list, add a line per portal:

```python
PORTALS: List[PortalConfig] = [
    PortalConfig("75302", "City of Sunnyvale",          "NorCal"),
    PortalConfig("29905", "City of Pomona",             "SoCal"),
    PortalConfig("<id>",  "<Agency name>",              "NorCal"),  # add yours
    ...
]
```

The portal ID is the number between `/portal/` and `/bo/` in the vendor URL.
e.g. `https://vendors.planetbids.com/portal/75302/bo/bo-search` → `75302`.

Portals that have migrated off PlanetBids (Palo Alto → OpenGov, for example) are detected automatically and skipped without erroring.

---

## Step 2 (next session): custom municipal sites

The handoff doc identified ~34 custom municipal portals that need one-off scrapers. The 8–10 highest-value candidates are:

- San Francisco DPW (non-login pages)
- Oakland
- UC Berkeley / UC Davis
- SamTrans
- SFPUC
- SLAC
- LLNL
- Judicial Council
- San Diego County

Add new scrapers as `scrapers/<source>.py`, extend `BaseScraper`, and register them in `aggregate.collect_all_leads()`.

OpenGov (Cloudflare-protected), login-walled portals, and plan rooms are all parked for v2.

---

## Tunable knobs

| Where | What | Default |
|---|---|---|
| `aggregate.py` | `CLOSED_BIDS_TO_KEEP_PER_SOURCE` — recently-closed bids surfaced per portal | `3` |
| `filters.py` | `CONSTRUCTION_KEYWORDS` — keyword list driving the relevance filter | (liberal v1 list) |
| `filters.py` | `CONSTRUCTION_CATEGORY_HINTS` — source-provided categories that auto-qualify | (Public Works etc.) |
| `filters.py` | `EXCLUDE_HINTS` — anti-signals (janitorial, IT, etc.) | (conservative list) |
| `seen_tracker.py` | `NEW_WINDOW_DAYS` — how long the NEW badge sticks | `7` |
| `scrapers/planetbids.py` | `CLOSED_FETCH_LIMIT` — max closed bids fetched per portal | `10` |
| `.github/workflows/update.yml` | cron schedule | daily 13:00 UTC |

---

## Project conventions

Inherited from `bd-events`:

- Regions: **NorCal / SoCal / Other**
- HTML brand: warm grey `#262626` bg, brand orange `#ff671f` accent, Inter font, all-caps section labels
- Persistent state in `data/seen.json`, committed by the GitHub Action
- "NEW" badge for leads first seen in the last 7 days
- Lead bid detail URLs link straight to the source portal so Ty can review and respond from one click
