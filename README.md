# CoolSpot

A public heat-relief finder for the DC, Maryland, and Virginia region. CoolSpot locates cooling
centers and hospitals near an address, and provides a Census-tract-level map of heat vulnerability
and air-conditioning access, to help residents find cooling during extreme heat events.

It ships as a static site (vanilla JS + Leaflet, no server, no build step) fed by an offline Python
data pipeline. Live at: **https://brockwebb.github.io/CoolSpot/**

> **Screenshot:** TODO — capture a screenshot of the finder view once the site is live at the URL
> above and embed it here (e.g. `docs/design/screenshot-finder.png`).

## What it does

- **Finder** (`index.html`) — enter an address, get the nearest cooling centers and hospitals with
  directions, phone numbers, and hours (where known). Falls back to a picker of regional anchor
  towns if geocoding fails or an address can't be matched.
- **Heat vulnerability map** (`analysis.html`) — a Census-tract choropleth toggling between six
  layers: CRE-Heat vulnerability, LACE no-AC estimate, poverty rate, 65+ population, disability
  rate, and distance to the nearest cooling center. Includes a "highlight gap tracts" toggle for
  tracts that are both far from a cooling center and above a configurable distance threshold.

## Data sources

| Source | Purpose | Coverage | Vintage |
|---|---|---|---|
| Census CRE-Heat | Heat vulnerability index (% of population with 3+ risk factors) | Tract, DC/MD/VA | 2022, experimental |
| Census LACE | % of households without air conditioning | Tract, DC/MD/VA | 2023, experimental |
| Census ACS 5-year | Poverty rate, 65+ population, disability rate | Tract, DC/MD/VA | 2020–2024 |
| Census TIGER/Line | Tract boundaries | DC/MD/VA | 2024 vintage (2020 fallback where 2024 unavailable) |
| Census Geocoder | Address → lat/lon (finder + batch pipeline) | US-wide | live JSONP |
| HHS/CMS Hospital General Information | Hospital roster + emergency-services flag | US-wide | coordinates frozen May 2024; attributes refreshed via CMS |
| DC HSEMA (ArcGIS Open Data) | Cooling center registry | Washington, DC | retrieved 2026-07-06 |
| Virginia Dept. of Health / 211 Virginia | Cooling center registry | Virginia (statewide) | retrieved 2026-07-06 |
| Prince George's County (ArcGIS) | Cooling center registry | MD — Prince George's | retrieved 2026-07-06 |
| Anne Arundel County | Cooling center registry (HTML) | MD — Anne Arundel | retrieved 2026-07-06 |
| Howard County | Cooling center registry (HTML) | MD — Howard | retrieved 2026-07-06 |

**Retrieval strategy:** each jurisdiction has its own adapter (ArcGIS REST query, HTML scrape, or
static hub page) under `pipeline/acquire/cooling/`, normalized to a shared schema (`pipeline/schema.py`)
and geocoded in bulk via the Census batch geocoder. Records that fail geocoding are quarantined
(not silently dropped) to `data/quarantine/` with the reason, for manual follow-up.

**Freshness caveats:**
- Cooling center hours and open/closed status change with weather and staffing — the site's
  disclaimer banner and each result card say "call ahead." The footer freshness line shows the
  date each jurisdiction's list was last retrieved.
- **Baltimore County has no scrapeable cooling-center list** as of this writing — its county
  emergency-management page describes a program but does not publish an address-level registry.
  This is a documented coverage gap, not a bug; see the "Deferred / known gaps" section below.
- CRE-Heat and LACE are Census Bureau *experimental* data products (methodology and vintages can
  change year to year) — labeled as such in the map legend.
- Hospital coordinates are a frozen roster (May 2024); operational attributes (e.g., emergency
  services flag) are refreshed from CMS but the location list itself is not re-geocoded each run.

**Current counts** (as published, 2026-07-06 run): 369 cooling centers total — DC 145, Virginia
164, Maryland 60 (Prince George's + Anne Arundel + Howard only); 152 hospitals; 3,856 Census tracts
across DC/MD/VA with CRE-Heat, LACE, and ACS attributes joined at 100% match rate. 2 cooling-center
records failed geocoding and were quarantined (address ambiguity), out of 371 scraped.

## Updating the data

The whole pipeline is idempotent and re-runnable end-to-end:

```bash
uv run coolspot all
```

Recommended cadence:
- **Each season** (or before a heat event): re-run `uv run coolspot all` to refresh cooling-center
  registries and hospital attributes, and re-publish `site/data/*`.
- **Yearly**: check the Maryland Department of Health cooling-center hub URL in
  `config/pipeline.yaml` — county sites reorganize their pages more often than DC/VA sources do —
  and update county adapter URLs there if a source moves.
- Census CRE-Heat/LACE/ACS/TIGER vintages are pinned in `config/pipeline.yaml`; bump them when the
  Bureau publishes a new year and re-run `coolspot all`.
  **Known limitation:** downloads are cached to disk under fixed filenames, so changing a vintage
  URL in `config/pipeline.yaml` alone will not fetch new data — the pipeline finds the cached file
  and re-publishes stale data. Delete `data/raw/` before re-running `coolspot all` whenever you bump
  a vintage. Tracked as a follow-up for the next data season (fixed caching, or cache keyed by URL).

All tunables (source URLs, vintages, distance thresholds, geocoder batch size) live in
`config/pipeline.yaml` — there are no hardcoded values to hunt down in `pipeline/`.

## Architecture

```
config/pipeline.yaml           -- all tunables (URLs, vintages, thresholds)
pipeline/                      -- offline Python pipeline (uv run coolspot <stage>)
  acquire/
    census.py                 -- CRE-Heat/LACE/ACS acquisition
    boundaries.py              -- TIGER/Line tract shapefiles -> attributed GeoJSON
    hospitals.py                -- HealthData.gov/CMS hospital roster acquisition
    cooling/
      dc.py                    -- DC HSEMA ArcGIS adapter
      va.py                    -- Virginia Dept. of Health / 211 Virginia adapter
      md.py                    -- Prince George's County ArcGIS adapter
      md_counties.py            -- Anne Arundel / Howard HTML adapters
      runner.py                -- fan-out across jurisdiction adapters -> shared schema
  geocode.py                   -- Census batch geocoder client + quarantine
  publish.py                   -- writes site/data/cooling_centers.geojson + manifest.json + site_config.json
  publish_tracts.py            -- writes site/data/tracts_{dc,md,va}.geojson
site/                          -- static site (no build step, no server)
  index.html                   -- finder view
  analysis.html                -- heat vulnerability map
  js/                          -- vanilla JS + ES modules (common.js, finder.js, analysis.js)
  data/                        -- pipeline output, consumed directly by the browser
tests/                         -- pytest suite (pipeline)
tests-e2e/                     -- Playwright smoke tests (real-browser, against site/)
```

Data flows one direction: pipeline stages read raw sources -> normalize -> geocode -> publish
static GeoJSON/JSON into `site/data/`. The browser never talks to the pipeline; it only fetches
those static files plus the live Census JSONP geocoder for address lookup.

See `docs/design/AD-001-architecture.md` for the full set of architectural decisions (why static +
offline pipeline, why vanilla JS, why JSONP for geocoding, why LACE was chosen as the AC-evaluation
data product, etc.), `docs/superpowers/specs/2026-07-05-coolspot-design.md` for the full spec, and
`docs/superpowers/plans/2026-07-05-coolspot.md` for the implementation plan.

## Disclaimer

CoolSpot is informational only and is **not an emergency service**. Cooling center hours and
availability change — call ahead before visiting. In a life-threatening heat emergency, call 911.

## Deferred / known gaps

- Delaware is out of scope for v1 (spec covers DC/MD/VA).
- Maryland counties beyond Prince George's, Anne Arundel, and Howard are not yet covered; several
  publish only PDFs (no structured data) and Baltimore County has no published address-level list
  at all.
- Virginia cooling-center hours are inconsistently published upstream; hours enrichment (e.g.
  cross-referencing 211 Virginia call center data) is a candidate follow-up.
- Seasonal re-run procedure is documented above under "Updating the data"; it is not yet automated
  via a scheduled workflow.

## Contributing

This is a personal civic-data project. Issues and PRs are welcome, especially: additional Maryland
county adapters, hours enrichment, or accessibility fixes to the finder/map views. Please run
`uv run pytest tests/ -v` and `npm run test:e2e` before opening a PR — both suites must pass.

## License

MIT. See `LICENSE`.
