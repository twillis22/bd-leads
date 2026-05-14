"""
Construction-relevance filtering.

Most public-agency portals list ALL solicitations — janitorial, IT, vehicles,
food service, etc. — and construction is a fraction. We need to filter
heavily.

Two filters run in parallel, EITHER qualifies a lead:

  1. Category-based — when the source exposes a category like 'Public Works'
     or 'Construction' or 'Capital Projects', trust it. Most reliable.

  2. Keyword-based — fallback for portals without category info. Match the
     title against a tunable keyword list.

Tyler explicitly asked for the keyword list to be exposed as a constant so
he can tune it. It lives below as CONSTRUCTION_KEYWORDS.
"""
from __future__ import annotations

import re
from typing import Iterable, List

from scrapers.base import Lead


# ----------------------------------------------------------------------------
# Tunable: keyword list. Liberal on first pass — prune false positives later.
# ----------------------------------------------------------------------------

CONSTRUCTION_KEYWORDS: List[str] = [
    # Generic build terms
    "construction", "renovation", "remodel", "modernization", "building",
    "facility", "facilities", "addition", "expansion", "improvement",
    "improvements", "infrastructure", "capital", "public works",
    # Tenant improvement
    "tenant improvement", "ti project", "interior",
    # Trades
    "plumbing", "electrical", "hvac", "mechanical", "roofing", "paving",
    "demolition", "demo ", "concrete", "asphalt", "framing", "drywall",
    "painting", "flooring", "windows", "doors", "fire protection",
    "sprinkler", "fire alarm",
    # Site / civil
    "site work", "sitework", "grading", "excavation", "utilities",
    "water main", "sewer", "storm drain", "trenching", "trenchless", "trail",
    "pavement", "paving", "sidewalk", "curb", "gutter", "slurry seal",
    "seal coat", "chip seal", "overlay", "rehabilitation", "striping",
    "guard rail", "guardrail", "bridge", "culvert", "signal", "lighting",
    # Project types
    "school", "library", "park", "community center", "fire station",
    "police station", "city hall", "courthouse", "parking structure",
    "parking lot", "garage",
    # Design-related (catch design-build)
    "design-build", "design build", "designbuild",
    "architect", "architectural",
    # General signals
    "build", "rebuild", "rehab", "rehabilitation", "restoration",
    "upgrade", "retrofit", "seismic",
]


# Categories that, when matched, qualify the lead instantly.
CONSTRUCTION_CATEGORY_HINTS: List[str] = [
    "public works", "construction", "capital project", "capital projects",
    "capital improvement", "facility", "facilities", "engineering",
    "architecture", "tenant improvement",
]


# Strong anti-signals — title contains one of these AND no construction
# keyword, we exclude. Helps reduce false positives.
EXCLUDE_HINTS: List[str] = [
    "janitorial", "janitor service", "uniform rental", "vehicle",
    "fleet", "software", "saas", "subscription", "consulting only",
    "audit services", "audit only", "legal services", "translation",
    "food service", "catering", "armored car", "armored transport",
    "towing", "uniform purchase",
]


# ----------------------------------------------------------------------------
# Filter
# ----------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).lower().strip()


def is_construction_relevant(lead: Lead) -> bool:
    """
    Return True if this lead looks like construction work.

    1. If the source-provided category matches a construction hint → True.
    2. Else if the title/description contains a construction keyword → True.
    3. Else False.

    Excludes (#2 only): if the title clearly signals a non-construction
    procurement (janitorial, IT, fleet, etc.) AND no construction keyword
    is present, exclude.
    """
    title = _norm(lead.title)
    desc = _norm(lead.description)
    category = _norm(lead.category)

    # Rule 1: trust source categories
    for hint in CONSTRUCTION_CATEGORY_HINTS:
        if hint in category:
            return True

    # Rule 2: keyword match in title or description
    haystack = f"{title} {desc}"
    has_keyword = any(kw in haystack for kw in CONSTRUCTION_KEYWORDS)

    # Rule 3: exclude false positives (only if no keyword matched)
    if not has_keyword:
        for ex in EXCLUDE_HINTS:
            if ex in haystack:
                return False

    return has_keyword


def filter_construction(leads: Iterable[Lead]) -> List[Lead]:
    """Return only the construction-relevant leads."""
    return [l for l in leads if is_construction_relevant(l)]
