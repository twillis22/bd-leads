"""
HTML generator for bd-leads.

Produces a single self-contained index.html file:
  - Level 10 brand styling (warm grey bg, brand orange accent, Inter)
  - Cards grouped by due-date bucket (This Week / Next 2 Weeks / etc)
  - Filter pills (region, agency, "due this week", "construction only")
  - NEW badge for items first seen in the last 7 days
  - "Recently closed" section collapsed by default

Data is embedded inline as a JSON blob; filter pills operate on it via
vanilla JS — no fetch calls, no server, just a static page that works
when bookmarked.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
from typing import List

from scrapers.base import Lead
from aggregate import bucket_for, BUCKET_ORDER, BUCKET_CLOSED


# ----------------------------------------------------------------------------
# Top-level entry point
# ----------------------------------------------------------------------------

def generate(leads: List[Lead], output_path: Path | str = "docs/index.html") -> Path:
    """Write the HTML page to output_path and return that path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _build_payload(leads)
    html = _render(payload)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ----------------------------------------------------------------------------
# Build the JSON payload the page consumes
# ----------------------------------------------------------------------------

def _build_payload(leads: List[Lead]) -> dict:
    """Shape the data the embedded JS needs to render and filter."""
    now = datetime.now(timezone.utc)

    # Lead dicts in display order
    items = []
    for l in leads:
        items.append({
            "title": l.title,
            "agency": l.agency,
            "rfp_id": l.rfp_id,
            "rfp_type": l.rfp_type or "",
            "due": l.due.isoformat() if l.due else None,
            "due_label": _format_due(l),
            "posted": l.posted.isoformat() if l.posted else None,
            "days_remaining": l.days_remaining,
            "url": l.url,
            "region": l.region,
            "stage": l.stage,
            "bucket": bucket_for(l),
            "is_new": l.is_new,
            "first_seen": l.first_seen,
        })

    # Agency counts (top 10 for filter pills)
    agency_counts = Counter(i["agency"] for i in items if i["bucket"] != BUCKET_CLOSED)
    top_agencies = [a for a, _ in agency_counts.most_common(10)]

    # Region counts (for filter pills)
    region_counts = Counter(i["region"] for i in items if i["bucket"] != BUCKET_CLOSED)

    # Quick stats for the header strip
    open_count = sum(1 for i in items if i["bucket"] != BUCKET_CLOSED)
    closed_count = sum(1 for i in items if i["bucket"] == BUCKET_CLOSED)
    new_count = sum(1 for i in items if i["is_new"] and i["bucket"] != BUCKET_CLOSED)
    due_this_week = sum(
        1 for i in items
        if i["days_remaining"] is not None and 0 <= i["days_remaining"] <= 7
    )

    return {
        "items": items,
        "buckets": BUCKET_ORDER,
        "top_agencies": top_agencies,
        "regions": list(region_counts.keys()),
        "stats": {
            "open": open_count,
            "closed": closed_count,
            "new": new_count,
            "due_this_week": due_this_week,
            "updated": now.strftime("%a %b %d, %Y %I:%M %p UTC"),
            "agency_total": len(agency_counts),
        },
    }


def _format_due(lead: Lead) -> str:
    """Human-friendly 'due' label shown on each card."""
    if not lead.due:
        return "—"
    days = lead.days_remaining
    if days is None:
        return lead.due.strftime("%b %d")
    if days < 0:
        return f"closed {lead.due.strftime('%b %d')}"
    if days == 0:
        return f"due today ({lead.due.strftime('%b %d')})"
    if days == 1:
        return "due tomorrow"
    if days <= 7:
        return f"due in {days}d ({lead.due.strftime('%b %d')})"
    return f"due {lead.due.strftime('%b %d')}"


# ----------------------------------------------------------------------------
# HTML template
# ----------------------------------------------------------------------------

def _render(payload: dict) -> str:
    """Inline the JSON payload into the static HTML shell."""
    data_json = json.dumps(payload, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__DATA_JSON__", data_json)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BD Leads — Open RFPs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #262626;
  --card: rgba(255, 255, 255, 0.04);
  --card-hover: rgba(255, 255, 255, 0.07);
  --border: rgba(255, 255, 255, 0.08);
  --text: #f6f6f6;
  --muted: #a8a8a8;
  --dim: #6c6c6c;
  --brand: #ff671f;
  --brand-deep: #934727;
  --norcal: #7eaee0;
  --socal: #e095b1;
  --other: #9ec9b3;
  --new: #ff671f;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
body { padding: 32px 24px 80px; }

.container { max-width: 1200px; margin: 0 auto; }

/* HEADER ---------------------------------------------------------------- */
header { margin-bottom: 32px; }
.brand-row { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; flex-wrap: wrap; margin-bottom: 6px; }
h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.01em; }
h1 .brand-mark { color: var(--brand); }
.updated { color: var(--dim); font-size: 12px; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; }
.tagline { color: var(--muted); font-size: 14px; }

/* STATS STRIP ----------------------------------------------------------- */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin: 24px 0 28px; }
.stat { background: var(--card); border: 1px solid var(--border); padding: 14px 16px; border-radius: 10px; }
.stat-num { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1; }
.stat-num.brand { color: var(--brand); }
.stat-label { font-size: 11px; font-weight: 600; color: var(--muted); letter-spacing: 0.06em; text-transform: uppercase; margin-top: 6px; }

/* FILTER ROW ------------------------------------------------------------ */
.filter-section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; margin-bottom: 24px; }
.filter-label { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--dim); margin: 8px 0 8px; }
.filter-label:first-child { margin-top: 0; }
.pill-row { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.12s; font-family: inherit; }
.pill:hover { color: var(--text); border-color: var(--muted); }
.pill.active { background: var(--brand); border-color: var(--brand); color: #1a1a1a; font-weight: 600; }
.pill .count { opacity: 0.55; margin-left: 4px; font-weight: 400; }
.pill.active .count { opacity: 0.7; }

/* BUCKETS --------------------------------------------------------------- */
.bucket { margin-bottom: 32px; }
.bucket-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.bucket-title { font-size: 11px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text); }
.bucket-count { font-size: 11px; font-weight: 500; color: var(--dim); }

/* CARDS ----------------------------------------------------------------- */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
.card { background: var(--card); border: 1px solid var(--border); border-left: 3px solid var(--region-color, var(--dim)); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; transition: background 0.12s, border-color 0.12s; }
.card:hover { background: var(--card-hover); }
.card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.card-agency { font-size: 11px; font-weight: 600; color: var(--muted); letter-spacing: 0.02em; text-transform: uppercase; }
.card-badges { display: flex; gap: 5px; flex-shrink: 0; align-items: center; }
.badge { font-size: 9px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; padding: 2px 7px; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); }
.badge.type { color: var(--text); }
.badge.new { background: var(--brand); border-color: var(--brand); color: #1a1a1a; }
.card-title { font-size: 14.5px; font-weight: 600; color: var(--text); line-height: 1.35; }
.card-title a { color: inherit; text-decoration: none; }
.card-title a:hover { color: var(--brand); }
.card-meta { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; font-size: 12px; color: var(--muted); margin-top: 2px; }
.card-rfp { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 11.5px; color: var(--dim); }
.card-due { font-weight: 500; }
.card-due.urgent { color: var(--brand); font-weight: 600; }
.card-due.past { color: var(--dim); }

/* Region tints (left border) */
.card[data-region="NorCal"] { --region-color: var(--norcal); }
.card[data-region="SoCal"]  { --region-color: var(--socal); }
.card[data-region="Other"]  { --region-color: var(--other); }

/* RECENTLY CLOSED ------------------------------------------------------- */
details.closed-section { margin-top: 32px; }
details.closed-section > summary { cursor: pointer; list-style: none; padding: 14px 18px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; align-items: center; }
details.closed-section > summary::-webkit-details-marker { display: none; }
details.closed-section > summary::after { content: "+ show"; color: var(--brand); font-size: 11px; font-weight: 700; }
details.closed-section[open] > summary::after { content: "− hide"; }
details.closed-section[open] > summary { margin-bottom: 16px; }
details.closed-section .cards { opacity: 0.72; }

/* EMPTY STATE ----------------------------------------------------------- */
.empty { color: var(--dim); font-size: 13px; padding: 24px; text-align: center; background: var(--card); border: 1px dashed var(--border); border-radius: 10px; }

/* FOOTER ---------------------------------------------------------------- */
footer { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--border); color: var(--dim); font-size: 11px; letter-spacing: 0.04em; }
footer a { color: var(--muted); text-decoration: none; }
footer a:hover { color: var(--brand); }

/* MOBILE TWEAKS --------------------------------------------------------- */
@media (max-width: 640px) {
  body { padding: 24px 14px 60px; }
  h1 { font-size: 22px; }
  .cards { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="container">

<header>
  <div class="brand-row">
    <h1><span class="brand-mark">BD Leads</span></h1>
    <span class="updated" id="updated"></span>
  </div>
  <p class="tagline">Open RFPs and recent solicitations across Bay Area public agencies. Construction-relevant only.</p>
</header>

<section class="stats" id="stats"></section>

<section class="filter-section">
  <div class="filter-label">Filters</div>
  <div class="pill-row" id="quick-filters"></div>
  <div class="filter-label">Region</div>
  <div class="pill-row" id="region-filters"></div>
  <div class="filter-label">Agency</div>
  <div class="pill-row" id="agency-filters"></div>
</section>

<main id="results"></main>

<footer>
  Auto-generated daily • Level 10 Construction Business Development
</footer>

</div>

<script>
const DATA = __DATA_JSON__;

// ---------- State ----------
const state = {
  region: "all",                // "all" | "NorCal" | "SoCal" | "Other"
  agency: "all",                // "all" | <agency name>
  dueThisWeek: false,           // toggle
};

// ---------- Render: stats ----------
function renderStats() {
  const s = DATA.stats;
  const el = document.getElementById("stats");
  el.innerHTML = "";
  const cards = [
    { num: s.open, label: "Open Leads", brand: true },
    { num: s.due_this_week, label: "Due This Week" },
    { num: s.new, label: "New This Week" },
    { num: s.agency_total, label: "Agencies" },
    { num: s.closed, label: "Recently Closed" },
  ];
  for (const c of cards) {
    const div = document.createElement("div");
    div.className = "stat";
    div.innerHTML = `<div class="stat-num ${c.brand ? "brand" : ""}">${c.num}</div><div class="stat-label">${c.label}</div>`;
    el.appendChild(div);
  }
  document.getElementById("updated").textContent = "Updated " + s.updated;
}

// ---------- Render: filter pills ----------
function renderFilters() {
  // Quick filters
  const quick = document.getElementById("quick-filters");
  quick.innerHTML = "";
  quick.appendChild(makePill("Due This Week", null, state.dueThisWeek, () => {
    state.dueThisWeek = !state.dueThisWeek;
    renderFilters(); renderResults();
  }));

  // Region pills
  const regionEl = document.getElementById("region-filters");
  regionEl.innerHTML = "";
  regionEl.appendChild(makePill("All Regions", null, state.region === "all", () => {
    state.region = "all"; renderFilters(); renderResults();
  }));
  for (const r of DATA.regions) {
    const count = DATA.items.filter(i => i.region === r && i.bucket !== "Recently Closed").length;
    regionEl.appendChild(makePill(r, count, state.region === r, () => {
      state.region = r; renderFilters(); renderResults();
    }));
  }

  // Agency pills (top 10)
  const agencyEl = document.getElementById("agency-filters");
  agencyEl.innerHTML = "";
  agencyEl.appendChild(makePill("All Agencies", null, state.agency === "all", () => {
    state.agency = "all"; renderFilters(); renderResults();
  }));
  for (const a of DATA.top_agencies) {
    const count = DATA.items.filter(i => i.agency === a && i.bucket !== "Recently Closed").length;
    agencyEl.appendChild(makePill(a, count, state.agency === a, () => {
      state.agency = a; renderFilters(); renderResults();
    }));
  }
}

function makePill(label, count, active, onClick) {
  const b = document.createElement("button");
  b.className = "pill" + (active ? " active" : "");
  b.innerHTML = label + (count != null ? `<span class="count">${count}</span>` : "");
  b.onclick = onClick;
  return b;
}

// ---------- Render: results ----------
function renderResults() {
  const root = document.getElementById("results");
  root.innerHTML = "";

  const filtered = DATA.items.filter(matchesFilters);
  const open = filtered.filter(i => i.bucket !== "Recently Closed");
  const closed = filtered.filter(i => i.bucket === "Recently Closed");

  // Group open by bucket
  const byBucket = {};
  for (const i of open) {
    (byBucket[i.bucket] = byBucket[i.bucket] || []).push(i);
  }

  // Render each bucket in order
  let totalRendered = 0;
  for (const b of DATA.buckets) {
    if (b === "Recently Closed") continue;
    const items = byBucket[b] || [];
    if (!items.length) continue;
    root.appendChild(renderBucket(b, items));
    totalRendered += items.length;
  }

  // Empty state
  if (totalRendered === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No leads match the current filters.";
    root.appendChild(empty);
  }

  // Closed section (only if closed bids exist after filters)
  if (closed.length) {
    const details = document.createElement("details");
    details.className = "closed-section";
    const summary = document.createElement("summary");
    summary.innerHTML = `<span>Recently Closed <span style="color:var(--dim);font-weight:500;margin-left:6px;">${closed.length}</span></span>`;
    details.appendChild(summary);
    const grid = document.createElement("div");
    grid.className = "cards";
    for (const i of closed) grid.appendChild(renderCard(i));
    details.appendChild(grid);
    root.appendChild(details);
  }
}

function renderBucket(title, items) {
  const section = document.createElement("section");
  section.className = "bucket";
  const header = document.createElement("div");
  header.className = "bucket-header";
  header.innerHTML = `<span class="bucket-title">${title}</span><span class="bucket-count">${items.length} ${items.length === 1 ? "lead" : "leads"}</span>`;
  section.appendChild(header);
  const grid = document.createElement("div");
  grid.className = "cards";
  for (const i of items) grid.appendChild(renderCard(i));
  section.appendChild(grid);
  return section;
}

function renderCard(item) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.region = item.region;

  const dueClass = item.days_remaining != null && item.days_remaining < 0 ? "past"
                 : item.days_remaining != null && item.days_remaining <= 7 ? "urgent" : "";

  const badges = [];
  if (item.is_new) badges.push(`<span class="badge new">New</span>`);
  if (item.rfp_type) badges.push(`<span class="badge type">${escapeHTML(item.rfp_type)}</span>`);

  card.innerHTML = `
    <div class="card-top">
      <span class="card-agency">${escapeHTML(item.agency)}</span>
      <span class="card-badges">${badges.join("")}</span>
    </div>
    <div class="card-title"><a href="${escapeHTML(item.url)}" target="_blank" rel="noopener">${escapeHTML(item.title)}</a></div>
    <div class="card-meta">
      <span class="card-rfp">${escapeHTML(item.rfp_id || "")}</span>
      <span class="card-due ${dueClass}">${escapeHTML(item.due_label)}</span>
    </div>
  `;
  return card;
}

function matchesFilters(item) {
  if (state.region !== "all" && item.region !== state.region) return false;
  if (state.agency !== "all" && item.agency !== state.agency) return false;
  if (state.dueThisWeek) {
    if (item.bucket === "Recently Closed") return false;
    if (item.days_remaining == null || item.days_remaining < 0 || item.days_remaining > 7) return false;
  }
  return true;
}

function escapeHTML(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// ---------- Boot ----------
renderStats();
renderFilters();
renderResults();
</script>
</body>
</html>
"""
