# Baltimore County via Designation + Structured Provenance — Design Spec

**Date:** 2026-07-06
**Status:** Approved via conversation (add data + structured `source_type`).
**Scope:** pipeline (schema, a new Baltimore adapter, runner, publish), finder display, and the
known-limitations text. No change to DC/VA/PG/AA/Howard data behavior.

## Problem

The live site claims Baltimore County "publishes no address-level cooling-center list, so it
cannot be included." That overstates the gap. Baltimore County uses a **designation model**:
rather than publishing an ad-hoc list, it declares that **all Baltimore County Public Library
branches** and **all county senior centers** are cooling sites during extreme-heat events
(source: baltimorecountymd.gov/departments/health/hot-weather). The addresses are obtainable
from those directories.

These records carry a materially different provenance than the rest of our data — DC/VA/PG/AA/
Howard come from *published cooling-center registries* (the jurisdiction asserts specific sites
are cooling centers); Baltimore is a *categorical designation* whose site list **we** assemble.
That distinction must be captured honestly, not flattened.

## Design

### 1. Structured provenance: `source_type`

Add a field distinguishing the two provenance shapes, machine-readable so it can generalize
later and drive UI:

- `source_type: "listed"` — from a published cooling-center registry (all existing records).
- `source_type: "designated"` — a facility designated as a cooling site by category; list
  assembled by CoolSpot from a facility directory (Baltimore County).

Implementation: `schema.validate_record` accepts `source_type ∈ {listed, designated}` when
present (optional, not required, so existing adapters/tests are untouched). The cooling-center
runner stamps `source_type: "listed"` on any record lacking one (one documented default), and
the Baltimore adapter sets `"designated"` explicitly. `publish.to_feature` carries it through
to `cooling_centers.geojson`.

### 2. Baltimore County adapter

New module `pipeline/acquire/cooling/baltimore.py`, two sub-sources, jurisdiction `md`:

- **Libraries:** all BCPL branches (name, address; ~19–20). Prefer a structured source (a GIS
  layer or the library's location data) over HTML scrape; fall back to scraping bcpl.info/
  locations. Records have no coordinates unless the source provides them → the existing geocode
  stage fills them.
- **Senior centers:** all county senior centers (baltimorecountymd.gov/departments/aging/
  centers; the page bot-blocks default UAs — use a browser-like User-Agent, as the round-1
  Baltimore fetch already found).

Every Baltimore record:
- `source_type: "designated"`.
- `source_url` = the county hot-weather designation page (the authority that makes it a cooling
  site — the civic citation).
- `url` = the facility directory page the address came from (BCPL locations / senior centers).
- `notes` = the caveat, e.g. *"Designated cooling site during Baltimore County extreme-heat
  events — hours vary, call ahead."* Senior centers append: *"Primarily serves older adults."*
- `id` = `md-baltimore-lib-{slug}` / `md-baltimore-senior-{slug}`.

**Build-time verification (mandatory first step):** confirm the "all libraries + all senior
centers" designation against the county's own hot-weather page before trusting it — the earlier
claim was corroborated only by secondary news sources. If the county scopes it more narrowly,
match that and record what was found. Captured HTML fixtures back the parser tests, as with the
other MD county adapters.

### 3. Finder display

- The result card shows `notes` when present (currently it does not) — this is how the
  designation caveat reaches the user.
- Designated records get a distinct badge: **"Designated site"** (neutral gray) instead of the
  teal "Cooling center", so the different confidence level reads at a glance.
- The `source` link continues to point at `source_url` (the county designation page); scheme-
  validated as today.

### 4. Known-limitations rewrite

Replace the Baltimore sentence. New text (values not hardcoded thresholds, just prose):
"Baltimore County is included by **designation** — the county names all public library
branches and senior centers as cooling sites during extreme-heat events rather than publishing
a fixed list, so those entries are marked *designated sites*; confirm hours by calling ahead,
and note senior centers primarily serve older adults. Maryland counties beyond Prince George's,
Anne Arundel, Howard, and Baltimore are not yet covered."

## Error handling

- Unknown `source_type` value → schema validation error → quarantined (fail-loud, standard).
- A Baltimore sub-source that fails to fetch → the runner's fail-loud contract applies (the
  stage fails, naming the jurisdiction) — a designation source going dark must not silently
  drop Baltimore.
- Records that fail geocoding → quarantined, as today (not force-placed).

## Testing

- pytest: `source_type` validation (listed/designated/invalid); runner stamps "listed" default;
  publish carries `source_type`; Baltimore parsers yield schema-valid designated records from
  captured fixtures (≥1 each, addresses contain digits, source_type == "designated", notes
  non-empty, senior-center notes mention older adults).
- Playwright: a designated result renders the "Designated site" badge and its caveat note.
  (A DC/VA search won't surface Baltimore; use an MD area/address near Baltimore County, or
  assert against the shipped `cooling_centers.geojson` that ≥1 `source_type:"designated"`
  feature exists and drives the badge.)

## Out of scope / parking lot

- Generalizing the designation model to DC/VA (their lists already include libraries; leave
  as-is) or to other MD counties / DE — parked (PL: designation-model generalization).
- Per-branch hours (BCPL branch hours vary; "call ahead" covers it for v1).
