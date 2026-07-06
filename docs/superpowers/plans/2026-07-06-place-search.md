# Finder Round 4 Implementation Plan — Place-Name Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "suitland md" (any city/town/CDP/county, with or without state) resolves to results at the place center; street addresses stay the precise path; the area picker becomes a true last resort.

**Architecture:** Pipeline downloads the Census Gazetteer place+county files (cached like other raw sources), publishes a compact `site/data/places.json` match index; the finder resolves input digit-first-geocoder / no-digit-first-places, with an inline pick-one list for cross-state ambiguity.

**Tech Stack:** Existing (Python/uv/pytest; vanilla JS; Playwright). No new dependencies.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-06-place-search-design.md`.
- `places.json` entry shape (exact keys, Task 2 depends on them): `{"q", "display", "state", "lat", "lon"}`; coords 4 decimals.
- Resolution order: digit in input → geocoder then places; no digit → places then geocoder; then area picker.
- Place-hit status copy exactly: `Showing results near {display} (place center — enter a street address for precise distances).`
- places.json load failure must NOT break the finder (progressive enhancement; console.warn) — deliberate spec-documented exception to fail-loud. Pipeline side stays fail-loud (0-row canary).
- Match ladder: exact → prefix → nothing. Max 5 choices shown.
- Tunables (gazetteer URLs) in `config/pipeline.yaml`. All tests green before push.

---

### Task 1: Pipeline — gazetteer → places.json

**Files:**
- Create: `pipeline/acquire/gazetteer.py`
- Modify: `config/pipeline.yaml` (census section), `pipeline/publish.py` (one call in run())
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Produces: `site/data/places.json` = sorted list of `{"q","display","state","lat","lon"}`.
- `parse_gazetteer(text: str, states: set[str]) -> list[dict]` — header-keyed tab-delimited rows (values stripped; the files pad the last column with spaces), filtered to USPS ∈ states. Works for BOTH file schemas (places file has NAME+LSAD columns; counties file has NAME only, with "County"/"city" inside NAME).
- `match_key(name: str) -> str` — lowercase; strip apostrophes (' and ’) and periods; strip ONE trailing PLACE suffix of: cdp, city, town, village, borough, municipality, comunidad, zona urbana (NOT county); collapse whitespace. ("Suitland CDP" → "suitland"; "Prince George's County" → "prince georges county" — county kept).
- `display_name(name: str, state: str, is_county: bool) -> str` — places: suffix stripped + ", ST" ("Suitland, MD"); counties: NAME kept whole + ", ST" ("Prince George's County, MD").
- `build_places(place_rows, county_rows) -> list[dict]` — key (q, state); within places keep larger ALAND on collision. County rows whose NAME ends with " County": indexed under the county-keeping key ("prince georges county") AND setdefault an alias under the suffix-stripped key ("prince georges") so bare names work — but a place name wins the bare key when both exist (Franklin city VA keeps "franklin"; Franklin County VA remains reachable as "franklin county"). County-file rows NOT ending " County" (VA independent cities, "Baltimore city") are treated like places (suffix-stripped key, setdefault — the place file's twin entry wins). Sorted by (q, state); raises RuntimeError on empty result.
- `run(cfg)` — download both zips (cache in data/raw like boundaries), extract the .txt, parse, build, write `site/data/places.json`. Called from `publish.run(cfg)` right before the manifest block.

- [ ] **Step 1: Failing tests** — `tests/test_gazetteer.py`:

```python
from pipeline.acquire.gazetteer import build_places, display_name, match_key, parse_gazetteer

PLACE_TXT = (
    "USPS\tGEOID\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG            \n"
    "AL\t0100100\t02582661\tAbanda CDP\t57\tS\t7764032\t34284\t2.998\t0.013\t33.091627\t-85.527029      \n"
    "MD\t2475725\t02390487\tSuitland CDP\t57\tS\t11412303\t9601\t4.406\t0.004\t38.849085\t-76.923114     \n"
    "VA\t5129600\t01498558\tFranklin city\t25\tA\t21609865\t236601\t8.344\t0.091\t36.683197\t-76.939744    \n"
)
COUNTY_TXT = (
    "USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG            \n"
    "MD\t24033\t01714670\tPrince George's County\t1250633930\t42160988\t482.873\t16.279\t38.829996\t-76.847360   \n"
    "VA\t51620\t01498421\tFranklin city\t21609865\t236601\t8.344\t0.091\t36.683197\t-76.939744   \n"
)


def test_parse_filters_states_and_strips_padding():
    rows = parse_gazetteer(PLACE_TXT, {"MD", "VA", "DC"})
    assert [r["NAME"] for r in rows] == ["Suitland CDP", "Franklin city"]
    assert rows[0]["INTPTLONG"] == "-76.923114"  # padding stripped


def test_match_key_strips_place_suffixes_and_punct_keeps_county():
    assert match_key("Suitland CDP") == "suitland"
    assert match_key("Franklin city") == "franklin"
    assert match_key("Prince George's County") == "prince georges county"   # county KEPT
    assert match_key("St. Charles CDP") == "st charles"


def test_display_name():
    assert display_name("Suitland CDP", "MD", is_county=False) == "Suitland, MD"
    assert display_name("Prince George's County", "MD", is_county=True) == "Prince George's County, MD"


def test_build_places_county_alias_and_collision_rules():
    places = parse_gazetteer(PLACE_TXT, {"MD", "VA"})
    counties = parse_gazetteer(COUNTY_TXT, {"MD", "VA"})
    out = build_places(places, counties)
    qs = {(e["q"], e["state"]): e for e in out}
    assert qs[("franklin", "VA")]["display"] == "Franklin, VA"       # place holds the bare key
    assert qs[("prince georges county", "MD")]["display"] == "Prince George's County, MD"
    assert qs[("prince georges", "MD")]["display"] == "Prince George's County, MD"  # alias (no place collision)
    assert qs[("suitland", "MD")]["lat"] == 38.8491                   # 4 decimals


def test_county_bare_alias_loses_to_place():
    # A place and county sharing a bare name in the same state: county keeps only its "x county" key.
    places = parse_gazetteer(PLACE_TXT, {"VA"})
    counties = [{"USPS": "VA", "NAME": "Franklin County", "ALAND": "1", "INTPTLAT": "37.0", "INTPTLONG": "-79.9"}]
    out = build_places(places, counties)
    qs = {(e["q"], e["state"]): e for e in out}
    assert qs[("franklin", "VA")]["display"] == "Franklin, VA"              # city wins bare key
    assert qs[("franklin county", "VA")]["display"] == "Franklin County, VA"  # county reachable explicitly


def test_build_places_empty_raises():
    import pytest
    with pytest.raises(RuntimeError, match="0 places"):
        build_places([], [])
```

- [ ] **Step 2: Verify failure** → module missing.
- [ ] **Step 3: Implement `pipeline/acquire/gazetteer.py`**

```python
# pipeline/acquire/gazetteer.py
"""Census Gazetteer place/county centers -> site/data/places.json for the finder's
place-name search. Places win over counties on match-key collision within a state."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import requests

from pipeline.config import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw"
# Place suffixes only — "county" is deliberately NOT stripped by match_key: counties are
# indexed under their county-keeping key plus a bare alias (see build_places), so a county
# never silently overwrites a same-named city (Franklin city vs Franklin County, VA).
SUFFIXES = ("cdp", "city", "town", "village", "borough", "municipality", "comunidad", "zona urbana")
DISPLAY_SUFFIXES = (" CDP", " city", " town", " village", " borough", " municipality")


def download_and_extract_txt(url: str, dest_dir: Path, timeout: int) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = url.rsplit("/", 1)[-1].removesuffix(".zip")
    txt = dest_dir / f"{stem}.txt"
    if txt.exists():
        print(f"cached: {txt.name}")
        return txt
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(dest_dir)
    if not txt.exists():
        raise RuntimeError(f"Expected {txt.name} inside {url}")
    return txt


def parse_gazetteer(text: str, states: set[str]) -> list[dict]:
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = dict(zip(header, (v.strip() for v in line.split("\t"))))
        if vals.get("USPS") in states:
            rows.append(vals)
    return rows


def match_key(name: str) -> str:
    q = name.lower().replace("'", "").replace("’", "").replace(".", "")
    q = " ".join(q.split())
    for s in SUFFIXES:
        if q.endswith(" " + s):
            q = q[: -(len(s) + 1)]
            break
    return q.strip()


def display_name(name: str, state: str, is_county: bool) -> str:
    if not is_county:
        for s in DISPLAY_SUFFIXES:
            if name.endswith(s):
                name = name[: -len(s)]
                break
    return f"{name}, {state}"


def _entry(row: dict, is_county: bool) -> dict:
    return {
        "q": match_key(row["NAME"]),
        "display": display_name(row["NAME"], row["USPS"], is_county),
        "state": row["USPS"],
        "lat": round(float(row["INTPTLAT"]), 4),
        "lon": round(float(row["INTPTLONG"]), 4),
        "_aland": int(row["ALAND"]),
    }


def build_places(place_rows: list[dict], county_rows: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for row in place_rows:
        e = _entry(row, is_county=False)
        key = (e["q"], e["state"])
        if key not in best or e["_aland"] > best[key]["_aland"]:
            best[key] = e
    for row in county_rows:
        e = _entry(row, is_county=True)
        best.setdefault((e["q"], e["state"]), e)  # county-keeping key ("x county") or city twin
        if e["q"].endswith(" county"):
            alias = {**e, "q": e["q"][: -len(" county")].strip()}
            best.setdefault((alias["q"], alias["state"]), alias)  # bare alias; a place name wins
    out = sorted(({k: v for k, v in e.items() if k != "_aland"} for e in best.values()),
                 key=lambda e: (e["q"], e["state"]))
    if not out:
        raise RuntimeError("Gazetteer produced 0 places for the configured states — source format changed?")
    return out


def run(cfg: dict) -> None:
    timeout = cfg["publish"]["request_timeout_s"]
    states = {s["abbr"] for s in cfg["states"]}
    place_txt = download_and_extract_txt(cfg["census"]["gazetteer_place_url"], RAW_DIR / "gazetteer", timeout)
    county_txt = download_and_extract_txt(cfg["census"]["gazetteer_county_url"], RAW_DIR / "gazetteer", timeout)
    # Gazetteer files are latin-1-safe; utf-8 first, cp1252 fallback matches census.py's pattern.
    def read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            print(f"note: {p.name} decoded as cp1252 (not UTF-8)")
            return p.read_text(encoding="cp1252")
    places = build_places(parse_gazetteer(read(place_txt), states), parse_gazetteer(read(county_txt), states))
    out = PROJECT_ROOT / cfg["publish"]["site_data_dir"] / "places.json"
    out.write_text(json.dumps(places, separators=(",", ":")))
    print(f"wrote {out} ({len(places)} places)")
```

Config additions under `census:`:

```yaml
  gazetteer_place_url: "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip"
  gazetteer_county_url: "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
```

`pipeline/publish.py` `run()` — after the tract-gap annotation block, before the manifest block:

```python
    from pipeline.acquire import gazetteer
    gazetteer.run(cfg)
```

(Import at top of file with the other imports, not inline — shown here for placement only.)

- [ ] **Step 4: All green** — `uv run pytest tests/ -v` (74 expected: 69 + 5).
- [ ] **Step 5: Publish + verify** — `uv run coolspot publish`; then:

```bash
python3 -c "
import json
pl = json.load(open('site/data/places.json'))
idx = {(e['q'], e['state']): e for e in pl}
assert ('suitland','MD') in idx and abs(idx[('suitland','MD')]['lat'] - 38.85) < 0.01
assert ('prince georges','MD') in idx
assert all(set(e) == {'q','display','state','lat','lon'} for e in pl)
print(len(pl), 'places OK; suitland ->', idx[('suitland','MD')])"
```

- [ ] **Step 6: Commit** (payload included, noted in body).

---

### Task 2: Finder resolution + pick-one UI + e2e + deploy

**Files:**
- Modify: `site/js/finder.js`, `site/index.html` (one `<ul>`), `site/css/style.css` (choices list), `site/js/common.js` (KNOWN_LIMITATIONS address-search entry), `tests-e2e/smoke.spec.mjs`

**Interfaces:**
- Consumes: `site/data/places.json` (Task 1 shape).
- Produces: `matchPlaces(input, places) -> list` (exported for nothing — module-local), `#place-choices` list.

- [ ] **Step 1: `site/index.html`** — inside the search panel, after `#fallback-picker`:

```html
    <ul id="place-choices" hidden aria-label="Matching places"></ul>
```

- [ ] **Step 2: `site/js/finder.js`** — (a) boot loads places (progressive):

```javascript
  // in boot()'s Promise.all, append:
    loadJSON("data/places.json").catch((err) => { console.warn(`places.json unavailable — place search disabled: ${err.message}`); return []; }),
  // and destructure as `places`; then:
  state.places = places;
```

(b) add module-local helpers + replace `onSearch`:

```javascript
const STATE_TOKENS = { "dc": "DC", "district of columbia": "DC", "md": "MD", "maryland": "MD", "va": "VA", "virginia": "VA" };

function normPlace(s) {
  // Apostrophes DELETE (george's -> georges, matching the pipeline's match_key);
  // periods/commas become spaces (st. -> st, "suitland, md" -> "suitland md").
  return String(s).toLowerCase().replace(/['’]/g, "").replace(/[.,]/g, " ").replace(/\s+/g, " ").trim();
}

function matchPlaces(input, places) {
  let q = normPlace(input);
  let stateFilter = null;
  for (const [tok, st] of Object.entries(STATE_TOKENS).sort((a, b) => b[0].length - a[0].length)) {
    if (q === tok) return [];                       // a bare state is not a place query
    if (q.endsWith(" " + tok)) { stateFilter = st; q = q.slice(0, -(tok.length + 1)).trim(); break; }
  }
  if (!q) return [];
  const pool = stateFilter ? places.filter((p) => p.state === stateFilter) : places;
  const exact = pool.filter((p) => p.q === q);
  if (exact.length) return exact.slice(0, 5);
  return pool.filter((p) => p.q.startsWith(q)).slice(0, 5);
}

function showPlace(m) {
  showNearest(m.lat, m.lon,
    `Showing results near ${m.display} (place center — enter a street address for precise distances).`);
}

function handlePlaceMatches(matches) {
  const status = document.getElementById("search-status");
  const choices = document.getElementById("place-choices");
  if (!matches.length) return false;
  if (matches.length === 1) { showPlace(matches[0]); return true; }
  status.textContent = "Multiple places match — choose one:";
  choices.innerHTML = matches.map((m, i) =>
    `<li><button type="button" data-i="${i}">${esc(m.display)}</button></li>`).join("");
  choices.hidden = false;
  choices.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => { choices.hidden = true; showPlace(matches[Number(b.dataset.i)]); }));
  return true;
}

async function onSearch(ev) {
  ev.preventDefault();
  const status = document.getElementById("search-status");
  const fallback = document.getElementById("fallback-picker");
  const choices = document.getElementById("place-choices");
  fallback.hidden = true;
  choices.hidden = true;
  choices.innerHTML = "";
  const q = document.getElementById("address-input").value.trim();
  const hasDigit = /\d/.test(q);
  status.textContent = "Searching…";
  if (!hasDigit && handlePlaceMatches(matchPlaces(q, state.places))) return;
  let geocoderDown = false;
  try {
    const hit = await geocodeAddress(q);
    if (hit) { showNearest(hit.lat, hit.lon, `Results near ${hit.matched}`); return; }
  } catch (err) {
    geocoderDown = true;
  }
  if (hasDigit && handlePlaceMatches(matchPlaces(q, state.places))) return;
  status.textContent = geocoderDown
    ? "Address lookup is unavailable right now. Try a city or county name, or pick an area below."
    : "";
  fallback.hidden = false;
}
```

(`state` object gains `places: []` in its initializer.)

- [ ] **Step 3: CSS** — after the fallback-picker-adjacent styles:

```css
#place-choices {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

#place-choices button {
  padding: 0.35rem 0.8rem;
  border: 1px solid var(--color-teal);
  background: #fff;
  color: var(--color-teal);
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
}

#place-choices button:hover {
  background: var(--color-teal);
  color: #fff;
}
```

- [ ] **Step 4: `common.js` KNOWN_LIMITATIONS** — update the "Address search covers standard U.S. addresses" entry body to add: "You can also enter a city, town, or county name (e.g. 'Suitland, MD') for results around its center — a street address gives the most precise distances."

- [ ] **Step 5: e2e** — append to `tests-e2e/smoke.spec.mjs`:

```javascript
test("place-name search: suitland md resolves locally", async ({ page }) => {
  await page.goto("/");
  await page.fill("#address-input", "suitland md");
  await page.click('#address-form button[type="submit"]');
  await expect(page.locator("#search-status")).toContainText("Suitland, MD");
  await expect(page.locator("#search-status")).toContainText("place center");
  await expect(page.locator(".result-card").first()).toBeVisible();
});

test("ambiguous place shows pick-one buttons", async ({ page }) => {
  await page.goto("/");
  // discover a genuinely ambiguous q from the shipped index (data-driven, not hardcoded)
  const amb = await page.evaluate(async () => {
    const places = await (await fetch("data/places.json")).json();
    const byQ = {};
    for (const p of places) (byQ[p.q] ??= []).push(p);
    return Object.keys(byQ).find((q) => new Set(byQ[q].map((p) => p.state)).size >= 2) ?? null;
  });
  test.skip(amb === null, "no cross-state ambiguous place in index");
  await page.fill("#address-input", amb);
  await page.click('#address-form button[type="submit"]');
  await expect(page.locator("#place-choices button").first()).toBeVisible();
  await page.locator("#place-choices button").first().click();
  await expect(page.locator("#search-status")).toContainText("place center");
  await expect(page.locator(".result-card").first()).toBeVisible();
});

test("gibberish still reaches the area picker", async ({ page }) => {
  await page.goto("/");
  await page.fill("#address-input", "zzqx nowhere");
  await page.click('#address-form button[type="submit"]');
  await expect(page.locator("#fallback-picker")).toBeVisible({ timeout: 15000 });
});
```

(The gibberish test hits the live geocoder from CI/local — acceptable, existing tests already tolerate network; keep its generous timeout.)

- [ ] **Step 6: Verify** — `node --check` all touched JS; full pytest + e2e (15 expected); local screenshot of the pick-one state.
- [ ] **Step 7: Merge to main, push, watch Pages deploy, live-verify** — real-browser: "suitland md" on the live site → status contains "Suitland, MD (place center", results render; zero pageerrors.

## Self-review (inline)

- Spec coverage: data (T1), resolution order + copy + pick-one + progressive enhancement (T2), limitations text (T2 step 4), testing (T1 pytest / T2 e2e). No gaps.
- Placeholders: none. Ambiguity e2e is data-driven by design, with an explicit skip guard.
- Consistency: entry keys q/display/state/lat/lon identical T1↔T2; `#place-choices` id consistent HTML/JS/CSS/e2e; status copy string identical in JS and e2e assertions ("place center").
- Normalization parity (fixed during self-review): both sides DELETE apostrophes and space-collapse, so "prince george's county" → "prince georges county" on the client exactly matches the index's county-keeping key; "st. charles" → "st charles" both sides. The client deliberately does NOT strip "county"/place suffixes — county entries are indexed under both "x county" and (when no place collides) bare "x", so user phrasing either way resolves, and a suffix a user *typed* is treated as meaningful (typing "franklin county va" must NOT match Franklin city).
- Collision correctness (fixed during self-review): counties never overwrite same-named cities; Franklin County VA reachable as "franklin county", Franklin city VA holds "franklin".
