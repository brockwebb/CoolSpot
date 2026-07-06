# CoolSpot — Design Spec

**Date:** 2026-07-05
**Status:** Approved by Brock (2026-07-05 brainstorming session)
**Repo:** public, GitHub Pages at `brockwebb.github.io/CoolSpot`

## Purpose

A public, resident-first web tool for finding heat relief in the Mid-Atlantic:
enter an address, see the nearest cooling centers and hospitals with hours and
one-tap directions. Beneath the finder, an analysis view for planners and
researchers: tract-level heat-vulnerability choropleths with cooling-center
locations overlaid, making coverage gaps visible.

Nothing like this exists today. Maryland's official resource is a
click-a-county-get-a-list page; Virginia and Delaware are scattered across
locality sites; only DC publishes structured open data. CoolSpot unifies them.

**Coverage:** MD, VA, DC required; DE if its sources are tractable.

## Audience

1. **Residents / caregivers (primary):** "It's 102°F, where can Mom cool off
   near her house?" Mobile-first — heat emergencies happen on phones.
2. **Planners / researchers (secondary):** "Which high-vulnerability tracts
   have no cooling center within reach?"

## Architecture

Two clean halves. No server, ever.

### Half 1: Python data pipeline (offline, produces static files)

CLI-invokable per AD-003 (CLI over MCP for internal tools). Stages:

1. **Acquire**
   - **Census API:** CRE-Heat (Community Resilience Estimates for Heat,
     tract-level heat-vulnerability estimates,
     census.gov/data/experimental-data-products/cre-heat.html) — the headline
     vulnerability layer; ACS tract variables (65+, living alone, poverty,
     disability, no vehicle); and the recently released Census air-conditioning
     data product.
   - **Hospitals:** HHS/CMS hospital location data or HIFLD hospitals layer.
   - **Cooling centers:** scraped from state/county web pages (crawl4ai for
     hard pages, requests + BeautifulSoup where simple). No unified public
     dataset exists; this is original data assembly.
2. **Normalize & geocode**
   - Every cooling-center record carries `source_url`, `retrieved_date`, and
     geocode match quality.
   - Geocoding via the free Census Geocoder batch API.
   - Records failing schema validation or geocoding are quarantined loudly —
     never silently dropped.
3. **Publish** — static payloads into the site directory:
   - `tracts.geojson` — simplified cartographic boundaries with CRE-Heat, ACS,
     and AC attributes
   - `cooling_centers.geojson`
   - `hospitals.geojson`
   - per-state `last_verified` manifest

### Half 2: Static site (vanilla HTML/CSS/JS + Leaflet)

TickBiteRisk pattern: zero build step, GitHub Pages serves the static
directory directly. Leaflet with OpenStreetMap tiles — no API key, no billing.

- **Finder view (landing):**
  - Address box → Census Geocoder onelineaddress endpoint (client-side fetch,
    free, keyless) → map recenters.
  - Nearest N cooling centers and hospitals listed with haversine distances,
    hours, source link, and a Google Maps directions deep-link
    (`google.com/maps/dir/?api=1&destination=…`) — Google routing UX without
    embedding Google or holding an API key.
  - Geocoder failure → friendly message + "pick your county" fallback.
  - Synchronized list view mirrors the map (accessibility; screen readers).
- **Analysis view:**
  - Toggleable tract choropleths: CRE-Heat (headline), 65+, living alone,
    poverty, no-AC.
  - Cooling centers and hospitals overlaid.
  - Coverage-gap rendering: high-vulnerability tracts beyond a configurable
    distance from any cooling center.
- **Site-wide:** per-state data-freshness banner (last-verified dates);
  "informational only, not an emergency service" disclaimer; CRE-Heat labeled
  as experimental data.

## Configuration

All tunables in YAML config, never in source (per engineering standards):
Census API endpoints and variable lists, state source URLs, nearest-N count,
coverage-gap distance threshold, map defaults.

## Repo layout

Standard project conventions:

```
CoolSpot/
├── CLAUDE.md              # project context
├── README.md
├── docs/
│   ├── design/            # ADs (AD-001, ...)
│   └── superpowers/specs/ # this document
├── cc_tasks/              # gitignored
├── handoffs/              # gitignored
├── pipeline/              # Python package: acquire / process / publish
├── config/                # YAML
├── data/
│   ├── raw/               # gitignored large pulls
│   └── quarantine/        # records that failed validation, for review
├── site/                  # static site served by GitHub Pages
│   └── data/              # published GeoJSON payloads
├── tests/
└── pyproject.toml
```

## Error handling

- Pipeline fails at startup on missing config/env, naming the exact variable.
- Scraper output is schema-validated before publishing; a state redesigning
  its page fails the pipeline instead of publishing garbage.
- Client-side geocode failures degrade gracefully to county selection.
- No silent failures anywhere (engineering standards §4).

## Testing

- pytest: payload schema validation, geocode match-quality thresholds,
  fixture-based scraper tests (saved HTML fixtures per state source).
- Playwright smoke test for the site (pattern already in use in TickBiteRisk).
- Full suite green before push.

## Known risks

1. **Cooling-center scraping is the long pole.** Inconsistent HTML, seasonal
   churn (lists change every summer). Mitigations: provenance on every record,
   per-state freshness display, quarantine-don't-drop, fixture tests.
2. **The new Census AC product is unevaluated.** Its geography may not be
   tract-level. First data-phase task: an evaluation memo (adopt-before-create
   applied to data) covering geography, vintage, and join strategy.
3. **CRE-Heat is an experimental Census product.** Labeled as such in the UI.

## Decisions made (with alternatives rejected)

- **Leaflet + Google deep-links** over embedded Google Maps (API key + billing
  liability on a free public site) and over static SVG (weak for point-finding).
- **Static vanilla JS** over Vite or Observable Framework (lean stack; zero
  build step; matches TickBiteRisk pattern that already works).
- **CRE-Heat** over CDC SVI/HHI or a custom composite index (heat-specific,
  tract-level, authoritative; no index methodology to defend ourselves).
- **Scrape with provenance** over curated-manual-only or proxy datasets
  (OSM/HIFLD stand-ins rejected as knowingly wrong).

## Out of scope (v1)

- Real-time weather/heat-alert integration
- User accounts, saved locations, notifications
- States beyond MD/VA/DC/DE
- Automated scheduled re-scraping (pipeline is run manually per season for now)
