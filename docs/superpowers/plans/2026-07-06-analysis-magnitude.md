# Analysis Round 2 Implementation Plan — Magnitude, Underserved Tracts, Navigation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a percent⇄count toggle to the analysis choropleth (real ACS numerators), redefine "gap tracts" as need+access ("underserved"), add ⓘ help disclosures and a segmented finder/analysis nav, applying strict no-chartjunk display rules.

**Architecture:** Small pipeline addition (2 new tract properties + 1 config value, regenerated payloads) plus a rework of `site/js/analysis.js`'s LAYERS structure so each layer carries a `pct` and optional `count` form. No new files except tests; no new dependencies.

**Tech Stack:** Existing — Python/uv/pytest pipeline, vanilla-JS + Leaflet site, Playwright e2e.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-06-analysis-magnitude-design.md`. Its "no chartjunk" section is BINDING: round-number thresholds/stops only; counts rendered with thousands separators and no decimals; percentages as whole numbers; tract-panel distances as whole km with "<1 km" under 1.
- Never derive a count as `% × population` — publish real ACS numerators (B17001_002E, S1810_C02_001E).
- `gap_min_affected: 1500`, `gap_distance_km: 8` (existing) — both flow config → `site_config.json` → client. No thresholds hardcoded in JS.
- Checkbox copy: **"Highlight underserved tracts"**. Underserved = `nearest_cc_km ≥ gap_distance_km AND pred3_e ≥ gap_min_affected`.
- Default display mode is **Percent**. Distance layer dims/disables the mode toggle.
- All existing tests must stay green; `uv run pytest tests/ -v` and `npm run test:e2e` before pushing.
- Count legend stops (data-verified against real distributions 2026-07-06, all round):
  heat `[250, 500, 1000, 1500, 2500]` people · no-AC `[10, 25, 50, 100, 250]` households ·
  65+ `[250, 500, 750, 1000, 1500]` people · poverty `[100, 250, 500, 1000, 2000]` people ·
  disability `[250, 500, 750, 1000, 1500]` people. 65+ percent stops `[5, 10, 15, 20, 30]`.

---

### Task 1: Pipeline — publish poverty/disability counts + gap_min_affected

**Files:**
- Modify: `pipeline/acquire/census.py` (acs_attrs), `pipeline/publish.py` (site_config block), `config/pipeline.yaml` (publish section)
- Test: `tests/test_acs.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: existing `_acs_int` sentinel helper; existing config plumbing.
- Produces: tract properties `pov_below_e: int|None`, `disability_e: int|None` on every published tract; `site_config.json` key `gap_min_affected: 1500`. Task 2's JS reads exactly these names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_acs.py` (fixtures `DETAILED`/`SUBJECT` already exist at top of file):

```python
def test_acs_attrs_includes_count_numerators():
    det = acs_rows_to_dict(DETAILED)["24033802405"]
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    a = acs_attrs(det, sub)
    assert a["pov_below_e"] == 480       # B17001_002E raw numerator
    assert a["disability_e"] == 520      # S1810_C02_001E raw numerator


def test_count_numerator_sentinel_gives_none():
    det = {**acs_rows_to_dict(DETAILED)["24033802405"], "B17001_002E": "-666666666"}
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    assert acs_attrs(det, sub)["pov_below_e"] is None
```

Append to `tests/test_publish.py`:

```python
def test_site_config_includes_gap_min_affected():
    from pipeline.config import load_config
    cfg = load_config()
    assert cfg["publish"]["gap_min_affected"] == 1500
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_acs.py tests/test_publish.py -v` → the two acs tests FAIL (KeyError), the config test FAILS (KeyError).

- [ ] **Step 3: Implement**

In `pipeline/acquire/census.py`, `acs_attrs` gains two entries (keep existing keys unchanged):

```python
        "pov_below_e": _acs_int(detailed, "B17001_002E"),
        "disability_e": _acs_int(subject, "S1810_C02_001E"),
```

In `config/pipeline.yaml` under `publish:`, next to `gap_distance_km: 8`:

```yaml
  gap_min_affected: 1500   # underserved = >=gap_distance_km AND >=this many people with 3+ heat factors (round number; 4% of tracts)
```

In `pipeline/publish.py` site_config block, after `"gap_distance_km": ...`:

```python
        "gap_min_affected": cfg["publish"]["gap_min_affected"],
```

- [ ] **Step 4: Tests pass** — `uv run pytest tests/ -v` → all green (66 expected).

- [ ] **Step 5: Regenerate payloads** — `uv run coolspot publish` (uses cached raw data; no network needed beyond boundary cache). Verify:

```bash
python3 - <<'EOF'
import json
p = json.load(open("site/data/tracts_dc.geojson"))["features"][0]["properties"]
assert "pov_below_e" in p and "disability_e" in p, p.keys()
sc = json.load(open("site/data/site_config.json"))
assert sc["gap_min_affected"] == 1500
print("payloads OK")
EOF
```

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: publish poverty/disability count numerators + gap_min_affected (regenerated payloads)"`

---

### Task 2: Analysis UI — mode toggle, underserved, help, segmented nav, display cleanup

**Files:**
- Modify: `site/js/analysis.js` (LAYERS restructure + mode state + underserved + tract panel), `site/analysis.html` (toggle control, checkbox rename, help disclosures, nav), `site/index.html` (nav), `site/css/style.css` (seg-nav, help, show-as styles)
- Test: existing `tests-e2e/smoke.spec.mjs` selectors updated here (they reference old radio values/labels and would break); NEW e2e tests come in Task 3.

**Interfaces:**
- Consumes: tract props from Task 1 (`pov_below_e`, `disability_e`), `site_config.json` `gap_min_affected`/`gap_distance_km`.
- Produces: radio group `name="layer"` values become semantic keys `heat|no_ac|poverty|age65|disability|distance`; mode radio group `name="show-as"` values `pct|count` (id-less, container `#show-as`); checkbox id stays `only-gaps`; help disclosures `#underserved-help` and `#layers-help`; nav class `seg-nav`. Task 3 tests target exactly these.

- [ ] **Step 1: Rewrite `site/js/analysis.js` LAYERS + rendering** (full replacement of lines 1–68 region; boot() edits shown after):

```javascript
// analysis.js — tract choropleths + cooling-center overlay + underserved tracts.
import { loadJSON, initMap, esc, renderFreshness, renderKnownLimitations } from "./common.js";

// No-chartjunk formatting: whole percents, separator counts, whole km.
const fmtPct = (v) => `${Math.round(v)}%`;
const fmtCount = (v) => Math.round(v).toLocaleString("en-US");
const fmtKm = (v) => (v < 1 ? "<1 km" : `${Math.round(v)} km`);

// Each layer: pct form + optional count form. value(p) -> number|null.
const LAYERS = {
  heat: {
    pct:   { value: (p) => p.pred3_pe,  label: "% with 3+ heat-vulnerability factors (CRE-Heat 2022, experimental)", fmt: fmtPct, stops: [5, 10, 15, 25, 40] },
    count: { value: (p) => p.pred3_e,   label: "People with 3+ heat-vulnerability factors (CRE-Heat 2022, experimental)", fmt: fmtCount, stops: [250, 500, 1000, 1500, 2500] },
  },
  no_ac: {
    pct:   { value: (p) => p.no_ac_pe,  label: "% households without air conditioning (LACE 2023, experimental)", fmt: fmtPct, stops: [2, 5, 10, 20, 35] },
    count: { value: (p) => p.no_ac_e,   label: "Households without air conditioning (LACE 2023, experimental)", fmt: fmtCount, stops: [10, 25, 50, 100, 250] },
  },
  poverty: {
    pct:   { value: (p) => p.pct_poverty,  label: "% below poverty level (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 20, 30, 40] },
    count: { value: (p) => p.pov_below_e,  label: "People below poverty level (ACS 2020–2024)", fmt: fmtCount, stops: [100, 250, 500, 1000, 2000] },
  },
  age65: {
    pct:   { value: (p) => (p.pop_total && p.pop_65plus != null ? (100 * p.pop_65plus) / p.pop_total : null), label: "% residents age 65+ (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 15, 20, 30] },
    count: { value: (p) => p.pop_65plus,   label: "Residents age 65+ (ACS 2020–2024)", fmt: fmtCount, stops: [250, 500, 750, 1000, 1500] },
  },
  disability: {
    pct:   { value: (p) => p.pct_disability, label: "% with a disability (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 15, 22, 30] },
    count: { value: (p) => p.disability_e,   label: "People with a disability (ACS 2020–2024)", fmt: fmtCount, stops: [250, 500, 750, 1000, 1500] },
  },
  distance: {
    pct:   { value: (p) => p.nearest_cc_km, label: "Distance to nearest cooling center", fmt: fmtKm, stops: [2, 5, 10, 20, 35] },
    count: null, // no count form; the mode toggle is disabled on this layer
  },
};
const RAMP = ["#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#e34a33", "#b30000"];
const NO_DATA = "#d7d7d7";

const state = { map: null, cfg: null, tracts: null, layerKey: "heat", mode: "pct", tractLayer: null,
                centersLayer: null, hospitalsLayer: null, onlyGaps: false };

function activeForm() {
  const def = LAYERS[state.layerKey];
  return def.count && state.mode === "count" ? def.count : def.pct;
}

function colorFor(value, stops) {
  if (value == null) return NO_DATA;
  let i = 0;
  while (i < stops.length && value >= stops[i]) i++;
  return RAMP[i];
}

function isUnderserved(p) {
  return p.nearest_cc_km != null && p.nearest_cc_km >= state.cfg.gap_distance_km
    && (p.pred3_e ?? 0) >= state.cfg.gap_min_affected;
}

function styleFeature(f) {
  const p = f.properties;
  const form = activeForm();
  const gap = isUnderserved(p);
  if (state.onlyGaps && !gap) return { fillOpacity: 0.05, weight: 0.3, color: "#999", fillColor: NO_DATA };
  return {
    fillColor: p.water_tract === 1 ? NO_DATA : colorFor(form.value(p), form.stops),
    fillOpacity: 0.75, weight: state.onlyGaps && gap ? 2 : 0.4,
    color: state.onlyGaps && gap ? "#1d4ed8" : "#666",
  };
}

function fmtOrNA(v, fmt) {
  return v == null ? "n/a" : fmt(v);
}

function onEachTract(f, layer) {
  layer.on("click", () => {
    const p = f.properties;
    document.getElementById("tract-info").innerHTML = `
      <h3>Tract ${p.GEOID}</h3>
      <ul>
        <li>Population: ${fmtOrNA(p.pop_total, fmtCount)}</li>
        <li>3+ heat factors: ${fmtOrNA(p.pred3_e, fmtCount)} people (${fmtOrNA(p.pred3_pe, fmtPct)})</li>
        <li>No AC: ${fmtOrNA(p.no_ac_e, fmtCount)} households (${fmtOrNA(p.no_ac_pe, fmtPct)})</li>
        <li>Poverty: ${fmtOrNA(p.pov_below_e, fmtCount)} (${fmtOrNA(p.pct_poverty, fmtPct)}) ·
            65+: ${fmtOrNA(p.pop_65plus, fmtCount)} ·
            Disability: ${fmtOrNA(p.disability_e, fmtCount)} (${fmtOrNA(p.pct_disability, fmtPct)})</li>
        <li>Nearest cooling center: ${fmtOrNA(p.nearest_cc_km, fmtKm)}</li>
      </ul>`;
  });
}

function renderLegend() {
  const form = activeForm();
  const rows = RAMP.map((color, i) => {
    const lo = i === 0 ? "&lt; " + form.fmt(form.stops[0])
      : i === RAMP.length - 1 ? "&ge; " + form.fmt(form.stops[form.stops.length - 1])
      : `${form.fmt(form.stops[i - 1])}–${form.fmt(form.stops[i])}`;
    return `<div class="legend-row"><span class="swatch" style="background:${color}"></span>${lo}</div>`;
  }).join("");
  document.getElementById("legend").innerHTML =
    `<h3>${form.label}</h3>${rows}<div class="legend-row"><span class="swatch" style="background:${NO_DATA}"></span>no data / water</div>`;
}

function syncModeControl() {
  const disabled = !LAYERS[state.layerKey].count;
  document.querySelectorAll('#show-as input[name="show-as"]').forEach((el) => (el.disabled = disabled));
  document.getElementById("show-as").classList.toggle("dimmed", disabled);
}

function redraw() {
  state.tractLayer.setStyle(styleFeature);
  renderLegend();
  syncModeControl();
}
```

- [ ] **Step 2: Update `boot()`** — three edits: (a) after `renderKnownLimitations();` add the underserved help text interpolation; (b) add the show-as listener; (c) final call sequence.

```javascript
  // (a) interpolate config values into the underserved definition — never hardcode thresholds in prose
  document.getElementById("underserved-help-text").textContent =
    `Highlighted tracts are ${state.cfg.gap_distance_km} km or more from every listed cooling center ` +
    `AND are home to at least ${state.cfg.gap_min_affected.toLocaleString("en-US")} people with 3 or more ` +
    `heat-vulnerability risk factors (Census CRE-Heat estimate). These are the areas where a new cooling ` +
    `center would reach the most vulnerable people.`;

  // (b) with the other listeners
  document.querySelectorAll('#show-as input[name="show-as"]').forEach((el) =>
    el.addEventListener("change", () => { state.mode = el.value; redraw(); }));

  // (c) replace the trailing `renderLegend();` with:
  renderLegend();
  syncModeControl();
```

- [ ] **Step 3: Update `site/analysis.html`** — replace the `analysis-panel` section content and nav:

Nav (BOTH pages — same markup, `aria-current` on the active side):

```html
  <nav class="seg-nav" aria-label="View switcher">
    <a href="index.html">Find cooling centers</a><a href="analysis.html" aria-current="page">Heat vulnerability map</a>
  </nav>
```

(index.html: `aria-current="page"` moves to the first anchor.)

Analysis panel:

```html
  <section class="analysis-panel" aria-label="Map layer controls">
    <div id="show-as" role="radiogroup" aria-label="Show values as">
      <span class="control-label">Show as:</span>
      <label><input type="radio" name="show-as" value="pct" checked /> Percent of tract</label>
      <label><input type="radio" name="show-as" value="count" /> Number of people</label>
    </div>
    <fieldset id="layer-picker">
      <legend>Map layer
        <details id="layers-help" class="help"><summary aria-label="About these layers">ⓘ</summary>
          <p>CRE-Heat and LACE are U.S. Census Bureau <em>experimental</em> data products — modeled
          estimates, not direct counts. "Percent of tract" shows how concentrated a condition is;
          "Number of people" shows how many residents it affects. Note: the map colors whole tracts,
          so geographically large tracts draw more attention than their population justifies.</p>
        </details>
      </legend>
      <label><input type="radio" name="layer" value="heat" checked /> Heat vulnerability (CRE-Heat)</label>
      <label><input type="radio" name="layer" value="no_ac" /> No air conditioning (LACE)</label>
      <label><input type="radio" name="layer" value="poverty" /> Below poverty level</label>
      <label><input type="radio" name="layer" value="age65" /> Age 65 and over</label>
      <label><input type="radio" name="layer" value="disability" /> With a disability</label>
      <label><input type="radio" name="layer" value="distance" /> Distance to nearest cooling center</label>
    </fieldset>
    <div class="analysis-toggles">
      <label><input type="checkbox" id="show-centers" checked /> Show cooling centers</label>
      <label><input type="checkbox" id="show-hospitals" /> Show hospitals</label>
      <label><input type="checkbox" id="only-gaps" /> Highlight underserved tracts</label>
      <details id="underserved-help" class="help"><summary aria-label="What does underserved mean?">ⓘ</summary>
        <p id="underserved-help-text"></p>
      </details>
    </div>
  </section>
```

- [ ] **Step 4: CSS additions** to `site/css/style.css` (after `.jump-btn` block; remove the old `.site-header nav a` underline rule only if it conflicts — keep it, `.seg-nav a` overrides):

```css
.seg-nav {
  display: inline-flex;
  border: 1px solid var(--color-teal);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.seg-nav a {
  padding: 0.4rem 0.9rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-teal);
  text-decoration: none;
}

.seg-nav a + a {
  border-left: 1px solid var(--color-teal);
}

.seg-nav a[aria-current="page"] {
  background: var(--color-teal);
  color: #fff;
}

#show-as {
  margin-bottom: 0.5rem;
}

#show-as label {
  margin-right: 0.9rem;
}

#show-as .control-label {
  font-weight: 600;
  margin-right: 0.5rem;
}

#show-as.dimmed {
  opacity: 0.45;
}

details.help {
  display: inline-block;
  font-size: 0.85rem;
}

details.help summary {
  cursor: pointer;
  list-style: none;
  color: var(--color-teal);
  font-weight: 700;
  padding: 0 0.25rem;
}

details.help[open] {
  display: block;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  margin-top: 0.3rem;
  background: #fafafa;
  max-width: 40rem;
}
```

- [ ] **Step 5: Fix existing e2e selectors broken by the radio-value rename** in `tests-e2e/smoke.spec.mjs`: `input[value="no_ac_pe"]` → `input[value="no_ac"]`; legend text expectation `"without air conditioning"` unchanged (count-form label also contains it — the perf test clicks while in pct mode, still fine); `#legend h3` "CRE-Heat" expectation unchanged (heat pct label still contains it).

- [ ] **Step 6: Verify** — `node --check site/js/analysis.js`; serve locally (`python3 -m http.server 8199 -d site`), screenshot both pages, confirm: seg-nav renders, toggle switches legend to counts with separators, distance layer dims toggle, underserved highlight + ⓘ works; `npm run test:e2e` all green.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat: percent/count toggle, underserved tracts, help disclosures, segmented nav"`

---

### Task 3: New e2e coverage + deploy + live verification

**Files:**
- Modify: `tests-e2e/smoke.spec.mjs` (append new tests)

- [ ] **Step 1: Append e2e tests**

```javascript
test("percent/count toggle flips legend to separator counts", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend h3")).toContainText("% with 3+", { timeout: 15000 });
  await page.locator('#show-as input[value="count"]').click();
  await expect(page.locator("#legend h3")).toContainText("People with 3+");
  await expect(page.locator("#legend .legend-row").nth(3)).toContainText("1,000"); // separator, round stop
});

test("distance layer disables the mode toggle", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  await page.locator('#layer-picker input[value="distance"]').click();
  await expect(page.locator('#show-as input[value="count"]')).toBeDisabled();
  await expect(page.locator("#show-as")).toHaveClass(/dimmed/);
  await page.locator('#layer-picker input[value="heat"]').click();
  await expect(page.locator('#show-as input[value="count"]')).toBeEnabled();
});

test("underserved highlight and help disclosure", async ({ page }) => {
  await page.goto("/analysis.html");
  await expect(page.locator("#legend .legend-row").first()).toBeVisible({ timeout: 15000 });
  await page.locator("#underserved-help summary").click();
  await expect(page.locator("#underserved-help-text")).toContainText("8 km");
  await expect(page.locator("#underserved-help-text")).toContainText("1,500 people");
  await page.locator("#only-gaps").click();
  // at 8km + 1500 affected, 155 tracts qualify; blue outline weight=2 stroke color #1d4ed8
  await expect(page.locator('#map path[stroke="#1d4ed8"]').first()).toBeAttached();
});

test("segmented nav on both pages with correct active side", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('.seg-nav a[aria-current="page"]')).toHaveText("Find cooling centers");
  await page.goto("/analysis.html");
  await expect(page.locator('.seg-nav a[aria-current="page"]')).toHaveText("Heat vulnerability map");
});
```

- [ ] **Step 2: Full verification** — `uv run pytest tests/ -v` (66) and `npm run test:e2e` (12) all green.
- [ ] **Step 3: Commit tests, push, deploy** — `git add -A && git commit -m "test: e2e coverage for mode toggle, underserved tracts, seg nav" && git push`. Watch the Pages run (`gh run watch`), then live-verify: toggle + underserved + nav function at https://brockwebb.github.io/CoolSpot/analysis.html with a real browser check, zero console errors.

---

## Self-review (done inline)

- Spec coverage: §1 nav → T2; §2 toggle+numerators → T1+T2; §3 underserved → T1 (config) + T2 (logic/copy); §4 help → T2; §5 display cleanup → T2 (fmt helpers used in legend + tract panel); pipeline → T1; testing → T1 (pytest) + T3 (Playwright). No gaps.
- Placeholders: none.
- Type consistency: property names `pov_below_e`/`disability_e` and config key `gap_min_affected` identical across T1 code, T2 JS, T3 test strings; radio values `heat|no_ac|poverty|age65|disability|distance` consistent between T2 HTML/JS and T3 selectors.
