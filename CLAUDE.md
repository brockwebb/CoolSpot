# CoolSpot: Project Context for Claude Code

**Project purpose:** CoolSpot is a public heat-relief finder for the DC, Maryland, and Virginia region. It provides a static site (built via GitHub Pages) that locates cooling centers, hospitals, and air-conditioned facilities alongside Census heat vulnerability and air-conditioning estimates to help residents find cooling during extreme heat events.

## Architecture & Decisions

See `docs/design/AD-001-architecture.md` for approved architectural decisions. Key constraints:
- Static site + offline Python pipeline (no server)
- Vanilla JS + Leaflet, GitHub Pages deployment
- Data sources: Census (CRE-Heat 2022, LACE 2023, ACS), HealthData.gov, state/county cooling center registries

## Specification & Planning

- Full specification: `docs/specification.md`
- Implementation plan: `docs/plan.md`

## Before You Push

Run the full test suite:
```bash
uv run pytest tests/ -v
```

All tests must pass. No exceptions.

## Pipeline CLI

The pipeline is exposed as the `coolspot` command:
```bash
coolspot --help
```

Configuration is centralized in `config/pipeline.yaml` — all tunables live there. No magic numbers in source code.

## Environment Setup

Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Then add your Census API key from https://api.census.gov/data/key_signup.html:
```bash
CENSUS_API_KEY=<your-key>
```

The pipeline will fail loudly if required env vars are missing.

## End-to-end tests

Real-browser smoke tests live in `tests-e2e/` (Playwright, served against `site/` via
`python3 -m http.server`, no dev server or build step needed):

```bash
npm install && npx playwright install chromium
npm run test:e2e
```

## Implementation learnings (from the v1 pipeline run, 2026-07-06)

- **Cooling centers:** 369 published across DC (145), VA (164), and MD (60 — Prince George's,
  Anne Arundel, Howard only). 2 of 371 scraped MD records failed Census batch geocoding on
  address ambiguity and were quarantined to `data/quarantine/` rather than dropped or force-fit.
  Baltimore County publishes no address-level cooling-center list — documented as a coverage gap,
  not a bug.
- **Hospitals:** 152, roster coordinates frozen at May 2024 vintage; only attributes (e.g.
  emergency-services flag) refresh from CMS on re-run.
- **Tracts / joins:** 3,856 Census tracts across DC/MD/VA. CRE-Heat, LACE, and ACS 2020–2024 all
  joined at a 100% match rate against the TIGER/Line tract boundary set — no fallback-vintage
  joins were needed in the 2026-07-06 run, but the GENZ2024→GENZ2020 fallback path (Task 6) is
  still live in case a future vintage is unavailable.
- **Payload sizes** (as published to `site/data/`): `tracts_va.geojson` ~3.9 MB, `tracts_md.geojson`
  ~1.9 MB, `tracts_dc.geojson` ~142 KB, `cooling_centers.geojson` ~205 KB, `hospitals.geojson`
  ~71 KB. All fetched directly by the browser — no pagination or tiling needed at this scale, and
  local Playwright runs saw load-to-legend times of ~200ms (well under the 15s CI-safe bound), so
  no Leaflet rendering mitigation (e.g. `smoothFactor`) was needed for the analysis view.
- **Geocoding:** the Census geocoder sends no CORS headers, so the finder's address search uses
  JSONP client-side (see `site/js/common.js`) rather than a fetch — this is a deliberate choice
  documented in AD-001, not an oversight.
