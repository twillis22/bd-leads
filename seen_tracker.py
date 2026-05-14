"""
Persistent first-seen tracking for leads.

Same pattern as bd-events: a JSON file at data/seen.json holds the first-seen
ISO date for every lead stable_id we've ever encountered. The GitHub Action
commits this file each run so state survives across cron invocations.

Why this matters:
  - "NEW" badge logic — items first seen in the last N days are flagged
  - Lets the HTML page distinguish "freshly posted yesterday" from
    "been sitting on the board for a month"
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from scrapers.base import Lead


class SeenTracker:
    """Loads/saves first-seen state and stamps leads with is_new + first_seen."""

    NEW_WINDOW_DAYS = 7  # how long the NEW badge sticks around

    def __init__(self, path: Path | str = "data/seen.json"):
        self.path = Path(path)
        self._data: Dict[str, str] = {}

    # --- persistence -------------------------------------------------------

    def load(self) -> "SeenTracker":
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except Exception:
                # Corrupt file shouldn't crash the run — start fresh
                self._data = {}
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    # --- core logic --------------------------------------------------------

    def stamp(self, leads: Iterable[Lead]) -> List[Lead]:
        """
        For each lead:
          - If never seen, record today as first_seen.
          - Set is_new=True if first_seen is within NEW_WINDOW_DAYS.
          - Set first_seen on the Lead object.

        Returns the same list of leads (mutated).
        """
        today = datetime.now(timezone.utc).date()
        cutoff = today - timedelta(days=self.NEW_WINDOW_DAYS)

        out: List[Lead] = []
        for lead in leads:
            sid = lead.stable_id()
            if sid not in self._data:
                self._data[sid] = today.isoformat()

            first_seen_str = self._data[sid]
            try:
                first_seen_date = datetime.fromisoformat(first_seen_str).date()
            except Exception:
                first_seen_date = today

            lead.first_seen = first_seen_str
            lead.is_new = first_seen_date >= cutoff
            out.append(lead)

        return out

    def prune(self, current_ids: Iterable[str], max_age_days: int = 365) -> int:
        """
        Remove seen-entries that are (a) not in the current set AND
        (b) older than max_age_days. Keeps the file from growing forever.
        Returns the number of entries removed.
        """
        current = set(current_ids)
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=max_age_days)).isoformat()
        to_remove = [
            sid for sid, first_seen in self._data.items()
            if sid not in current and first_seen < cutoff
        ]
        for sid in to_remove:
            del self._data[sid]
        return len(to_remove)
