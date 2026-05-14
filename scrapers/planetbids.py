"""
PlanetBids generic scraper.

Every PlanetBids portal uses the same UI structure — same table shape,
same selectors, same stage dropdown. The only difference between portals
is the numeric `portal_id` in the URL. So one scraper class handles all 34
of Tyler's PlanetBids sources, parameterized on (portal_id, agency_name, region).

URL pattern verified:
    https://vendors.planetbids.com/portal/{portal_id}/bo/bo-search

Table columns (verified across multiple portals):
    Posted | Project Title | Invitation # | Due Date | Remaining | Stage | Format

Bid detail page URL pattern:
    https://vendors.planetbids.com/portal/{portal_id}/bo/bo-detail/{bid_id}
    (bid_id is the `rowattribute` attr on each <tr>)

A second pass with Stage=Closed pulls recently-closed bids for the
"who's bidding in our market" awareness feature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .base import BaseScraper, Lead
from .browser import BrowserSession


PLANETBIDS_BASE = "https://vendors.planetbids.com/portal"


# ----------------------------------------------------------------------------
# Portal config — Tyler's list lives in his spreadsheet; this is the starter
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class PortalConfig:
    portal_id: str
    agency: str
    region: str = "NorCal"  # NorCal / SoCal / Other


# Full Bay Area + SoCal PlanetBids portal list, extracted from Tyler's
# Lead_Lookup_sites.xlsx spreadsheet.
#
# Note: two portal IDs are shared between agencies and have been collapsed
# to one entry each:
#   - 15331: CSU Maritime + CSU Chancellor's Office (same system portal)
#   - 68007: SamTrans + Caltrain + San Mateo County Transit District
#
# Portals that have migrated off PlanetBids (e.g., Palo Alto → OpenGov) are
# detected and skipped automatically at fetch time, so stale entries fail
# soft without blowing up the run.
PORTALS: List[PortalConfig] = [
    PortalConfig("14590", "City of Richmond",                                        "NorCal"),
    PortalConfig("14599", "County of Stanislaus",                                    "NorCal"),
    PortalConfig("15331", "CSU Maritime / Chancellor's Office",                      "NorCal"),
    PortalConfig("15739", "Sacramento State",                                        "NorCal"),
    PortalConfig("16128", "CSU San Marcos",                                          "SoCal"),
    PortalConfig("17950", "City of San Diego",                                       "SoCal"),
    PortalConfig("18057", "Ohlone CCD",                                              "NorCal"),
    PortalConfig("20507", "San Mateo County CCD",                                    "NorCal"),
    PortalConfig("24809", "Foothill DeAnza CCD",                                     "NorCal"),
    PortalConfig("25796", "San Diego State University (SDSU)",                       "SoCal"),
    PortalConfig("26036", "CSU Monterey Bay",                                        "NorCal"),
    PortalConfig("27970", "City of Carlsbad",                                        "SoCal"),
    PortalConfig("39476", "West Valley Mission CCD",                                 "NorCal"),
    PortalConfig("39481", "City of San Marcos",                                      "SoCal"),
    PortalConfig("43669", "Los Rios CCD",                                            "NorCal"),
    PortalConfig("43764", "San Diego Unified School District (SDUSD)",               "SoCal"),
    PortalConfig("46142", "City of Elk Grove",                                       "NorCal"),
    PortalConfig("47167", "MiraCosta CCD",                                           "SoCal"),
    PortalConfig("47527", "City of Mountain View",                                   "NorCal"),
    PortalConfig("47827", "UC College of the Law San Francisco",                     "NorCal"),
    PortalConfig("53850", "Monterey Peninsula CCD",                                  "NorCal"),
    PortalConfig("57150", "Palomar CCD",                                             "SoCal"),
    PortalConfig("57760", "San Diego CCD (SDCCD)",                                   "SoCal"),
    PortalConfig("60397", "The Pasha Group",                                         "Other"),
    PortalConfig("62973", "Oceanside USD",                                           "SoCal"),
    PortalConfig("64254", "City of Walnut Creek Public Works Projects",              "NorCal"),
    PortalConfig("66280", "Santa Clara Housing Authority",                           "NorCal"),
    PortalConfig("67229", "Contra Costa CCD",                                        "NorCal"),
    PortalConfig("68007", "SamTrans / Caltrain / SMCTD",                             "NorCal"),
    PortalConfig("71685", "City of Los Altos",                                       "NorCal"),
    PortalConfig("73033", "City of Seaside",                                         "NorCal"),
    PortalConfig("75302", "City of Sunnyvale",                                       "NorCal"),
]


# ----------------------------------------------------------------------------
# Scraper
# ----------------------------------------------------------------------------

class PlanetBidsScraper(BaseScraper):
    """
    Scrape one PlanetBids portal. Use PlanetBidsScraper.fetch_all() to run
    across the full portal list with a shared browser session.
    """

    name = "PlanetBids"

    # How many recently-closed bids to also pull, per portal. The aggregator's
    # CLOSED_BIDS_TO_KEEP_PER_SOURCE will further filter this down — pulling
    # a small N here keeps the closed-pass cheap.
    CLOSED_FETCH_LIMIT = 10

    def __init__(self, config: PortalConfig, session: Optional[BrowserSession] = None):
        self.config = config
        self.region = config.region
        self._session = session

    # --- public API --------------------------------------------------------

    def fetch(self) -> List[Lead]:
        """Fetch open + recently-closed leads for this portal."""
        if self._session is None:
            with BrowserSession() as session:
                return self._fetch_with_session(session)
        return self._fetch_with_session(self._session)

    @classmethod
    def fetch_all(cls, portals: Optional[List[PortalConfig]] = None) -> List[Lead]:
        """
        Fetch leads from every configured portal using ONE browser session.
        This is the entry point the aggregator calls.
        """
        portals = portals or PORTALS
        results: List[Lead] = []
        with BrowserSession() as session:
            for cfg in portals:
                scraper = cls(cfg, session=session)
                try:
                    leads = scraper._fetch_with_session(session)
                    results.extend(leads)
                    print(f"  ✓ {cfg.agency} (portal {cfg.portal_id}): {len(leads)} leads")
                except Exception as e:
                    # Per the BaseScraper contract: don't kill the run for one portal.
                    print(f"  ✗ {cfg.agency} (portal {cfg.portal_id}): FAILED — {e}")
        return results

    # --- internals ---------------------------------------------------------

    def _fetch_with_session(self, session: BrowserSession) -> List[Lead]:
        """Run open-bid pass + closed-bid pass for this portal."""
        leads: List[Lead] = []
        page = session.new_page()
        try:
            # Quick guard: detect "not a valid portal" pages (agencies that
            # migrated off PlanetBids) so we don't waste two retries on them.
            url = f"{PLANETBIDS_BASE}/{self.config.portal_id}/bo/bo-search"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                body_snippet = page.evaluate(
                    "() => document.body.innerText.slice(0, 200)"
                )
                if "not a valid PlanetBids agency portal" in (body_snippet or ""):
                    print(f"    (portal {self.config.portal_id} is no longer a valid PlanetBids portal — skipping)")
                    return []
            except Exception:
                pass  # fall through to normal fetch attempts

            # Open / current bids — explicitly filter to "Bidding" so we don't
            # double-count closed/canceled bids that show in the default view.
            leads.extend(self._fetch_stage(page, stage_label="Bidding", stage_value="open"))
            # Recently-closed bids (small batch for the awareness feature)
            closed = self._fetch_stage(page, stage_label="Closed", stage_value="closed")
            leads.extend(closed[: self.CLOSED_FETCH_LIMIT])
        finally:
            page.close()
        return leads

    def _fetch_stage(self, page, stage_label: Optional[str], stage_value: str) -> List[Lead]:
        """
        Load the search page (optionally filtered by stage) and parse rows.

        stage_label: text in the Stage dropdown ("Closed", "Bidding", etc.)
                     or None for the default (all open) view.
        stage_value: the value we tag the resulting Lead.stage with.
        """
        url = f"{PLANETBIDS_BASE}/{self.config.portal_id}/bo/bo-search"
        session = self._session
        if not session.goto_with_retry(page, url):
            return []

        if stage_label:
            # Use the stage filter dropdown and re-search.
            # Notes:
            #   - <select>s have ID attrs but empty name attrs.
            #   - The filter is fully client-side, so networkidle returns
            #     instantly. We poll for the table to actually re-render to
            #     reflect our chosen stage before reading rows.
            try:
                page.select_option('select#stageId-field', label=stage_label)
                page.click('button:has-text("Search")')
                # Poll: every visible row's stage cell must equal stage_label,
                # OR the table goes empty (no bids in that stage).
                try:
                    page.wait_for_function(
                        """(target) => {
                            const rows = [...document.querySelectorAll('tbody tr')];
                            if (rows.length === 0) return true;  // empty result is valid
                            return rows.every(r => {
                                const cells = r.querySelectorAll('td');
                                return cells.length > 5 &&
                                       cells[5].textContent.trim() === target;
                            });
                        }""",
                        arg=stage_label,
                        timeout=8000,
                    )
                except Exception:
                    # Filter didn't apply cleanly — return empty rather than
                    # poisoning results with the wrong stage.
                    return []
            except Exception:
                return []

        # Extract rows in one round-trip
        rows = page.evaluate("""() => {
            const out = [];
            for (const tr of document.querySelectorAll('tbody tr')) {
                const cells = [...tr.querySelectorAll('td')].map(c => c.textContent.trim());
                out.push({
                    bid_id: tr.getAttribute('rowattribute'),
                    cells: cells,
                });
            }
            return out;
        }""")

        return [self._row_to_lead(r, stage_value) for r in rows if r.get("bid_id")]

    def _row_to_lead(self, row: dict, stage_value: str) -> Lead:
        """Map a PlanetBids row dict to a Lead."""
        cells = row.get("cells") or []
        # Cells: [Posted, Project Title, Invitation #, Due Date, Remaining, Stage, Format]
        posted_str = cells[0] if len(cells) > 0 else ""
        title      = cells[1] if len(cells) > 1 else ""
        rfp_id     = cells[2] if len(cells) > 2 else ""
        due_str    = cells[3] if len(cells) > 3 else ""
        # 'Remaining' (cells[4]) — skipped, recomputed from due date
        stage_text = cells[5] if len(cells) > 5 else ""

        return Lead(
            title=title,
            agency=self.config.agency,
            rfp_id=rfp_id,
            rfp_type=self._infer_rfp_type(rfp_id),
            posted=self._safe_parse_date(posted_str),
            due=self._safe_parse_date(due_str),
            url=f"{PLANETBIDS_BASE}/{self.config.portal_id}/bo/bo-detail/{row['bid_id']}",
            region=self.config.region,
            description="",                 # detail-page scrape is v2
            category="",                    # detail-page scrape is v2
            stage=stage_value if stage_value != "open" else (stage_text.lower() or "open"),
        )

    @staticmethod
    def _infer_rfp_type(rfp_id: str) -> str:
        """Pull the RFP type prefix off the invitation number, e.g. 'IFB PW26-19' -> 'IFB'."""
        if not rfp_id:
            return ""
        head = rfp_id.strip().split()[0].upper()
        for token in ("IFB", "RFP", "RFQ", "RFQUAL", "RFI", "IPWB", "BID"):
            if head.startswith(token):
                return token if token != "RFQUAL" else "RFQual"
        return ""
