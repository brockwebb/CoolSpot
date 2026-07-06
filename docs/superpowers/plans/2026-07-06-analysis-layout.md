# Analysis Round 3 Implementation Plan — Compact Controls, Horizontal Legend, Full-Width Map

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compact one-row control bar (layer picker becomes a dropdown), legend as a horizontal strip above a full-width map, tract clicks open a popup AND update a slim bar — titled with human-readable tract + county names from the boundary shapefiles.

**Architecture:** Two-field passthrough in the boundaries converter (+payload regen), then a layout rework of `analysis.html`/`analysis.js`/`style.css`. No new data sources or dependencies.

**Tech Stack:** Existing (Python/uv/pytest; vanilla JS + Leaflet; Playwright).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-06-analysis-layout-design.md`. No-chartjunk rules from the round-2 spec remain binding (whole %, separator counts, whole km).
- Tract identity title: `"{tract_name} — {county}, {state_abbr}"`, fallback `"Tract {GEOID}"` if fields missing. Never a bare GEOID as the only identity.
- Layer select id `layer-select`, values `heat|no_ac|poverty|age65|disability|distance` (unchanged keys).
- Legend markup switches `<h3>` → `<span class="legend-title">`; all e2e references update.
- Finder page untouched except nothing (no shared-file regressions — common.js unchanged).
- `uv run pytest tests/ -v` and `npm run test:e2e` green before push.

---

### Task 1: Pipeline — tract identity passthrough

**Files:**
- Modify: `pipeline/acquire/boundaries.py` (shapefile_to_features)
- Test: `tests/test_boundaries.py`

**Interfaces:**
- Produces: every tract feature property dict gains `tract_name` (NAMELSAD, e.g. "Census Tract 5051.01"), `county` (NAMELSADCO, e.g. "Carroll County"), `state_abbr` (STUSPS, e.g. "MD"), alongside existing `GEOID`. `publish_tracts.build_state_geojson` needs NO change (it updates properties in place). Task 2's JS reads exactly these names.

- [ ] **Step 1: Failing test** — in `tests/test_boundaries.py`, extend `make_fixture_shp` to write the three fields and assert passthrough:

```python
def make_fixture_shp_named(tmp_path):
    w = shapefile.Writer(str(tmp_path / "fixn"), shapeType=shapefile.POLYGON)
    w.field("GEOID", "C", size=11)
    w.field("NAMELSAD", "C", size=40)
    w.field("NAMELSADCO", "C", size=40)
    w.field("STUSPS", "C", size=2)
    w.poly([[(-77.01, 38.90), (-77.01, 38.91), (-77.00, 38.90), (-77.01, 38.90)]])
    w.record("24013505101", "Census Tract 5051.01", "Carroll County", "MD")
    w.close()
    return tmp_path / "fixn.shp"


def test_shapefile_to_features_keeps_identity_fields(tmp_path):
    feats = shapefile_to_features(make_fixture_shp_named(tmp_path), precision=5)
    p = feats[0]["properties"]
    assert p["tract_name"] == "Census Tract 5051.01"
    assert p["county"] == "Carroll County"
    assert p["state_abbr"] == "MD"


def test_shapefile_missing_identity_fields_still_works(tmp_path):
    # the original minimal fixture (GEOID only) must not crash — fields become None
    feats = shapefile_to_features(make_fixture_shp(tmp_path), precision=5)
    p = feats[0]["properties"]
    assert p["GEOID"] == "11001000100"
    assert p["tract_name"] is None and p["county"] is None and p["state_abbr"] is None
```

- [ ] **Step 2: Verify failure** — `uv run pytest tests/test_boundaries.py -v` → 2 FAIL.

- [ ] **Step 3: Implement** — in `boundaries.shapefile_to_features`, replace the GEOID-only property build. Current code indexes `GEOID` positionally; generalize:

```python
def shapefile_to_features(shp_path: Path, precision: int) -> list[dict]:
    reader = shapefile.Reader(str(shp_path))
    field_names = [f[0] for f in reader.fields[1:]]

    def field(rec, name):
        return rec[field_names.index(name)] if name in field_names else None

    feats = []
    for sr in reader.iterShapeRecords():
        geom = sr.shape.__geo_interface__
        feats.append({
            "type": "Feature",
            "properties": {
                "GEOID": field(sr.record, "GEOID"),
                "tract_name": field(sr.record, "NAMELSAD"),
                "county": field(sr.record, "NAMELSADCO"),
                "state_abbr": field(sr.record, "STUSPS"),
            },
            "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"], precision)},
        })
    return feats
```

- [ ] **Step 4: All green** — `uv run pytest tests/ -v` (69 expected: 67 + 2).
- [ ] **Step 5: Regenerate + verify** — `uv run coolspot publish`; then:

```bash
python3 -c "
import json
p = json.load(open('site/data/tracts_md.geojson'))['features'][0]['properties']
assert p['tract_name'].startswith('Census Tract') and p['county'].endswith('County') and p['state_abbr'] == 'MD', p
print('identity fields OK:', p['tract_name'], '-', p['county'])"
```

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: tract identity fields (name/county/state) in published payloads"` (note regenerated payloads in body).

---

### Task 2: Layout rework + e2e + deploy

**Files:**
- Modify: `site/analysis.html` (main restructure), `site/js/analysis.js`, `site/css/style.css`, `tests-e2e/smoke.spec.mjs`

**Interfaces:**
- Consumes: `tract_name`/`county`/`state_abbr` from Task 1.
- Produces: `#layer-select` dropdown; `#legend` with `.legend-title` span; `#tract-info` slim bar below map; popup on tract click.

- [ ] **Step 1: `site/analysis.html` — replace `<main>` content** (header/footer/known-limitations untouched):

```html
<main>
  <section class="control-bar" aria-label="Map controls">
    <div id="show-as" role="radiogroup" aria-label="Show values as">
      <span class="control-label">Show as:</span>
      <label><input type="radio" name="show-as" value="pct" checked /> Percent of tract</label>
      <label><input type="radio" name="show-as" value="count" /> Number of people</label>
    </div>
    <div class="layer-control">
      <label class="control-label" for="layer-select">Map layer:</label>
      <select id="layer-select">
        <option value="heat" selected>Heat vulnerability (CRE-Heat)</option>
        <option value="no_ac">No air conditioning (LACE)</option>
        <option value="poverty">Below poverty level</option>
        <option value="age65">Age 65 and over</option>
        <option value="disability">With a disability</option>
        <option value="distance">Distance to nearest cooling center</option>
      </select>
      <details id="layers-help" class="help"><summary aria-label="About these layers">ⓘ</summary>
        <p>CRE-Heat and LACE are U.S. Census Bureau <em>experimental</em> data products — modeled
        estimates, not direct counts. "Percent of tract" shows how concentrated a condition is;
        "Number of people" shows how many residents it affects. Note: the map colors whole tracts,
        so geographically large tracts draw more attention than their population justifies.</p>
      </details>
    </div>
    <div class="analysis-toggles">
      <label><input type="checkbox" id="show-centers" checked /> Show cooling centers</label>
      <label><input type="checkbox" id="show-hospitals" /> Show hospitals</label>
      <label><input type="checkbox" id="only-gaps" /> Highlight underserved tracts</label>
      <details id="underserved-help" class="help"><summary aria-label="What does underserved mean?">ⓘ</summary>
        <p id="underserved-help-text"></p>
      </details>
    </div>
  </section>
  <div id="legend" class="legend-bar" aria-label="Map legend"></div>
  <div id="map" class="map map-tall" role="application" aria-label="Map of heat vulnerability by Census tract"></div>
  <div id="tract-info" class="tract-bar" aria-live="polite">Click a tract for details.</div>
</main>
```

- [ ] **Step 2: `site/js/analysis.js` edits** (four spots):

(a) Layer listener — replace the `#layer-picker` radio loop in `boot()`:

```javascript
  document.getElementById("layer-select").addEventListener("change", (e) => {
    state.layerKey = e.target.value; redraw();
  });
```

(b) `renderLegend` — title becomes an inline span (horizontal bar):

```javascript
function renderLegend() {
  const form = activeForm();
  const rows = RAMP.map((color, i) => {
    const lo = i === 0 ? "&lt; " + form.fmt(form.stops[0])
      : i === RAMP.length - 1 ? "&ge; " + form.fmt(form.stops[form.stops.length - 1])
      : `${form.fmt(form.stops[i - 1])}–${form.fmt(form.stops[i])}`;
    return `<span class="legend-row"><span class="swatch" style="background:${color}"></span>${lo}</span>`;
  }).join("");
  document.getElementById("legend").innerHTML =
    `<span class="legend-title">${form.label}</span>${rows}<span class="legend-row"><span class="swatch" style="background:${NO_DATA}"></span>no data / water</span>`;
}
```

(c) Tract identity + shared content builder; popup AND bar on click — replace `onEachTract`:

```javascript
function tractTitle(p) {
  return p.tract_name && p.county ? `${p.tract_name} — ${p.county}, ${p.state_abbr}` : `Tract ${p.GEOID}`;
}

function tractDetailsHTML(p) {
  return `
    <h3>${esc(tractTitle(p))}</h3>
    <ul>
      <li>Population: ${fmtOrNA(p.pop_total, fmtCount)}</li>
      <li>3+ heat factors: ${fmtOrNA(p.pred3_e, fmtCount)} people (${fmtOrNA(p.pred3_pe, fmtPct)})</li>
      <li>No AC: ${fmtOrNA(p.no_ac_e, fmtCount)} households (${fmtOrNA(p.no_ac_pe, fmtPct)})</li>
      <li>Poverty: ${fmtOrNA(p.pov_below_e, fmtCount)} (${fmtOrNA(p.pct_poverty, fmtPct)}) ·
          65+: ${fmtOrNA(p.pop_65plus, fmtCount)} ·
          Disability: ${fmtOrNA(p.disability_e, fmtCount)} (${fmtOrNA(p.pct_disability, fmtPct)})</li>
      <li>Nearest cooling center: ${fmtOrNA(p.nearest_cc_km, fmtKm)} <span class="muted">· GEOID ${esc(p.GEOID)}</span></li>
    </ul>`;
}

function onEachTract(f, layer) {
  layer.on("click", (e) => {
    const html = tractDetailsHTML(f.properties);
    document.getElementById("tract-info").innerHTML = html;
    L.popup({ maxWidth: 320 }).setLatLng(e.latlng).setContent(html).openOn(state.map);
  });
}
```

(`tract_name`/`county` are first-party Census strings but go through `esc()` anyway — consistent with the esc-everything posture.)

- [ ] **Step 3: `site/css/style.css`** — add after the `#show-as` blocks; also DELETE the now-dead `#layer-picker` rules and change `.analysis-toggles label` from block to inline:

```css
.control-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 1.5rem;
  margin-bottom: 0.6rem;
}

.layer-control {
  position: relative;
}

.layer-control select {
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.9rem;
}

.analysis-toggles {
  position: relative;
  margin-top: 0;
}

.analysis-toggles label {
  display: inline-block;
  margin: 0 0.9rem 0 0;
}

.control-bar details.help[open] {
  position: absolute;
  z-index: 1100;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-width: 26rem;
}

.legend-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem 0.9rem;
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.4rem 0.8rem;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
}

.legend-bar .legend-title {
  font-weight: 600;
  margin-right: 0.5rem;
}

.legend-bar .legend-row {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.tract-bar {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem 0.8rem;
  margin-top: 0.5rem;
  font-size: 0.9rem;
}

.tract-bar h3 {
  margin: 0 0 0.25rem;
  font-size: 1rem;
}

.tract-bar ul {
  margin: 0;
  padding-left: 1.1rem;
}

.muted {
  color: var(--color-gray);
  font-size: 0.8rem;
}
```

Also remove `#legend { border... }` old block-column rules if they conflict (the `.legend-bar` class governs now; old `#legend` selector block and `#legend .swatch-row` may be deleted — `#legend .swatch` sizing rule is still used, keep it).

- [ ] **Step 4: e2e updates** in `tests-e2e/smoke.spec.mjs`:
  - All `#legend h3` → `#legend .legend-title` (3 occurrences).
  - `#layer-picker input[value="no_ac"]` → `page.selectOption("#layer-select", "no_ac")` (perf test; the click timing wrap stays).
  - Distance-toggle test: `input[value="distance"]`/`input[value="heat"]` clicks → `selectOption("#layer-select", "distance")` / `("#layer-select", "heat")`.
  - Append:

```javascript
test("legend renders as a horizontal bar above the map", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-title")).toBeVisible({ timeout: 15000 });
  const order = await page.evaluate(() => {
    const legend = document.getElementById("legend");
    const map = document.getElementById("map");
    return !!(legend.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(order).toBe(true); // legend precedes map in DOM
});

test("tract click opens popup and fills slim bar with county name", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-title")).toBeVisible({ timeout: 15000 });
  await page.locator("#map path.leaflet-interactive").first().click({ force: true });
  await expect(page.locator(".leaflet-popup-content h3").first()).toContainText(/Census Tract|Tract/);
  await expect(page.locator("#tract-info h3")).toContainText(/County|Washington/);
});
```

  (County regex allows DC, whose NAMELSADCO for DC is "District of Columbia" — verify against real payload during implementation and adjust the assertion to match actual data, keeping it meaningful: it must prove a human-readable name, not a bare GEOID.)

- [ ] **Step 5: Verify** — `node --check site/js/analysis.js`; local server + screenshots (control bar single row on desktop, legend strip above full-width map, popup + bar on click, ⓘ overlay not reflowing); `uv run pytest tests/ -q` + `npm run test:e2e` all green.
- [ ] **Step 6: Commit, push (direct on main per established flow), watch Pages deploy, live-verify** with a real-browser script: select a layer via dropdown, click a tract, assert popup title contains "County" (or "District of Columbia"), zero pageerrors.

## Self-review (inline)

- Spec coverage: §1 control bar → T2; §2 legend/full-width → T2; §3 popup+bar+identity → T1 (data) + T2 (UI); §4 pipeline → T1; error handling (fallback title) → T2 code; testing → both. No gaps.
- Placeholders: none. The county-assertion regex is explicitly resolved during implementation against real data (bounded instruction, not TBD).
- Consistency: property names `tract_name|county|state_abbr` identical in T1 code, T2 JS, spec; `layer-select` id consistent HTML/JS/e2e.
