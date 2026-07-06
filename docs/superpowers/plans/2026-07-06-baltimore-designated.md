# Baltimore County Designation + Structured Provenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include Baltimore County cooling sites (all BCPL library branches + county senior centers) via the county's designation model, with a structured `source_type` field distinguishing "designated" from "listed" records, honest two-part citation, and a user-facing caveat.

**Architecture:** A `source_type` field (validated in schema, defaulted in the runner, auto-carried to GeoJSON by the existing `to_feature`), a new Baltimore adapter with two sub-sources, finder display of the distinction, and a known-limitations rewrite.

**Tech Stack:** Existing (Python/uv/pytest; vanilla JS; Playwright).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-06-baltimore-designated-design.md`.
- `source_type ∈ {"listed","designated"}`; optional in schema; runner stamps `"listed"` default; Baltimore sets `"designated"`.
- Baltimore records: `source_url` = county hot-weather designation page; `url` = facility directory; `notes` = designation caveat (senior centers add "Primarily serves older adults."); jurisdiction `md`; ids `md-baltimore-lib-{slug}` / `md-baltimore-senior-{slug}`.
- **Verify the designation on the county's own hot-weather page before trusting it** (secondary-source claim); capture HTML fixtures for parser tests.
- Provenance/quarantine/fail-loud rules unchanged. `uv run pytest tests/ -v` + `npm run test:e2e` green before push.

---

### Task 1: `source_type` plumbing (schema + runner default)

**Files:** Modify `pipeline/schema.py`, `pipeline/acquire/cooling/runner.py`; Test `tests/test_schema.py`, `tests/test_cooling_runner.py`.

**Interfaces:** Produces validated `source_type`; every collected record carries one (Task 2 sets "designated", everything else defaults "listed"); `publish.to_feature` already passes it through unchanged (verify, no code change).

- [ ] **Step 1: Failing tests.** Append to `tests/test_schema.py`:

```python
def test_source_type_valid_values():
    assert validate_record({**GOOD, "source_type": "designated"}) == []
    assert validate_record({**GOOD, "source_type": "listed"}) == []


def test_source_type_invalid_rejected():
    errs = validate_record({**GOOD, "source_type": "made-up"})
    assert any("source_type" in e for e in errs)
```

Append to `tests/test_cooling_runner.py`:

```python
def test_collect_stamps_default_source_type():
    fetchers = {"dc": lambda cfg, t, d: [GOOD]}  # GOOD has no source_type
    recs = runner.collect({}, 10, "2026-07-05", fetchers=fetchers)
    assert recs[0]["source_type"] == "listed"


def test_collect_preserves_explicit_source_type():
    designated = {**GOOD, "id": "md-baltimore-lib-x", "source_type": "designated"}
    recs = runner.collect({}, 10, "2026-07-05", fetchers={"md": lambda cfg, t, d: [designated]})
    assert recs[0]["source_type"] == "designated"
```

- [ ] **Step 2: Verify failure** — `uv run pytest tests/test_schema.py tests/test_cooling_runner.py -v` → 4 FAIL.

- [ ] **Step 3: Implement.** In `pipeline/schema.py`, add a constant near `VALID_STATES` and a check in `validate_record` (before `return errs`):

```python
VALID_SOURCE_TYPES = {"listed", "designated"}
```
```python
    st = rec.get("source_type")
    if st is not None and st not in VALID_SOURCE_TYPES:
        errs.append(f"source_type not in {sorted(VALID_SOURCE_TYPES)}: {st}")
```

In `pipeline/acquire/cooling/runner.py` `collect`, stamp the default as each fetcher's records come in (replace the `records.extend(got)` line):

```python
        for rec in got:
            rec.setdefault("source_type", "listed")  # designation adapters set "designated" themselves
        records.extend(got)
```

- [ ] **Step 4: Tests pass** — `uv run pytest tests/ -v` (all green).
- [ ] **Step 5: Commit** — `git commit -am "feat: source_type provenance field (schema validation + runner default)"`

---

### Task 2: Baltimore County adapter (libraries + senior centers)

**Files:** Create `pipeline/acquire/cooling/baltimore.py`, `tests/fixtures/md_baltimore_libraries.html`, `tests/fixtures/md_baltimore_seniors.html`; Modify `pipeline/acquire/cooling/runner.py` (`_fetch_md`), `config/pipeline.yaml`; Test `tests/test_cooling_baltimore.py`.

**Interfaces:** Consumes `schema` helpers. Produces `baltimore.fetch_libraries(cfg, timeout) -> raw`, `baltimore.parse_libraries(raw, retrieved) -> list[dict]`, `baltimore.fetch_seniors(cfg, timeout) -> raw`, `baltimore.parse_seniors(raw, retrieved) -> list[dict]` — all records `source_type="designated"`, jurisdiction `md`, no lat/lon (geocoded downstream). Wired into `runner._fetch_md`.

- [ ] **Step 1: Verify designation + capture fixtures FIRST.** Fetch the county hot-weather page and confirm it designates *all* libraries and *all* senior centers as cooling sites (use a browser-like UA — the page bot-blocks default agents):

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
curl -sL -A "$UA" "https://www.baltimorecountymd.gov/departments/health/hot-weather" | grep -iE "cooling|library|senior" | head
```
Record what the page actually says in the report. Then capture the two directory sources as fixtures (find the best source for BCPL branches — try the library site and any Baltimore County / Maryland GIS layer; prefer structured data with coordinates if available). Save `tests/fixtures/md_baltimore_libraries.html` and `tests/fixtures/md_baltimore_seniors.html` (each > 3 KB of real content). If a clean JSON/GIS source with coordinates exists, use it and store the JSON fixture instead — note the choice in the report.

- [ ] **Step 2: Failing tests** (invariants fixed; selector logic written against the captured fixtures):

```python
# tests/test_cooling_baltimore.py
from pathlib import Path
from pipeline.acquire.cooling import baltimore
from pipeline.schema import partition_records

FIX = Path(__file__).parent / "fixtures"


def test_parse_libraries_designated_records():
    recs = baltimore.parse_libraries((FIX / "md_baltimore_libraries.html").read_text(), "2026-07-06")
    assert len(recs) >= 5
    valid, invalid = partition_records(recs)
    assert invalid == [], [r["_errors"] for r in invalid]
    for r in valid:
        assert r["source_type"] == "designated"
        assert r["jurisdiction"] == "md" and r["state"] == "MD"
        assert r["notes"] and "call ahead" in r["notes"].lower()
        assert any(ch.isdigit() for ch in r["address"])
        assert r["source_url"].startswith("http")


def test_parse_seniors_designated_and_audience_note():
    recs = baltimore.parse_seniors((FIX / "md_baltimore_seniors.html").read_text(), "2026-07-06")
    assert len(recs) >= 3
    valid, invalid = partition_records(recs)
    assert invalid == []
    for r in valid:
        assert r["source_type"] == "designated"
        assert "older adult" in r["notes"].lower()
```

- [ ] **Step 3: Implement `baltimore.py`** — parsers written against the captured fixtures, using this shared record builder (adapt `fetch_*`/`parse_*` bodies to the real DOM/JSON):

```python
# pipeline/acquire/cooling/baltimore.py
"""Baltimore County: no published cooling-center list. The county DESIGNATES all public
library branches and senior centers as cooling sites during extreme-heat events
(baltimorecountymd.gov/departments/health/hot-weather). We assemble the list from the
facility directories; every record is source_type='designated' with that caveat. See
docs/superpowers/specs/2026-07-06-baltimore-designated-design.md."""
from __future__ import annotations

import re

import requests

DESIGNATION_URL = "https://www.baltimorecountymd.gov/departments/health/hot-weather"
UA = "Mozilla/5.0 (compatible; CoolSpot/0.1; +https://github.com/brockwebb/CoolSpot)"
LIB_CAVEAT = "Designated cooling site during Baltimore County extreme-heat events — hours vary, call ahead."
SENIOR_CAVEAT = LIB_CAVEAT + " Primarily serves older adults."


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _record(kind: str, name: str, street: str, city: str, zc: str, directory_url: str,
            retrieved: str, caveat: str) -> dict:
    return {
        "id": f"md-baltimore-{kind}-{_slug(name)}",
        "name": name.strip(), "address": street.strip(), "city": city.strip() or "Baltimore",
        "state": "MD", "zip": zc or "", "jurisdiction": "md",
        "source_type": "designated",
        "source_url": DESIGNATION_URL,      # the authority that designates it a cooling site
        "url": directory_url,               # where the address came from
        "notes": caveat,
        "retrieved_date": retrieved,
    }


def fetch_libraries(cfg: dict, timeout: int):
    url = cfg["cooling_sources"]["md"]["baltimore"]["libraries_url"]
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text  # or .json() if a structured source was chosen


def parse_libraries(raw, retrieved_date: str) -> list[dict]:
    # WRITE against tests/fixtures/md_baltimore_libraries.html: extract each branch's
    # name + address; build via _record("lib", name, street, city, zip, <directory url>,
    # retrieved_date, LIB_CAVEAT). Print a loud !! warning before any skip.
    raise NotImplementedError


def fetch_seniors(cfg: dict, timeout: int):
    url = cfg["cooling_sources"]["md"]["baltimore"]["seniors_url"]
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text


def parse_seniors(raw, retrieved_date: str) -> list[dict]:
    # WRITE against tests/fixtures/md_baltimore_seniors.html; _record("senior", ...,
    # SENIOR_CAVEAT). Loud warning on skip.
    raise NotImplementedError
```

If either directory lists no usable addresses (only PDFs/links), follow the Task-10 drop rule: document the gap in the report and the known-limitations text rather than fabricating records — but the spec's premise is that these directories DO carry addresses, so this is the unlikely branch.

Config under `cooling_sources.md` (add a `baltimore` block; exact URLs set to what Step 1 found):

```yaml
    baltimore:
      designation_url: "https://www.baltimorecountymd.gov/departments/health/hot-weather"
      libraries_url: "<resolved in Step 1>"
      seniors_url: "https://www.baltimorecountymd.gov/departments/aging/centers"
```

- [ ] **Step 4: Wire into `runner._fetch_md`** — after the county_pages loop, before `return recs`:

```python
    from pipeline.acquire.cooling import baltimore
    recs.extend(baltimore.parse_libraries(baltimore.fetch_libraries(cfg, timeout), retrieved))
    recs.extend(baltimore.parse_seniors(baltimore.fetch_seniors(cfg, timeout), retrieved))
```

(These records already carry `source_type="designated"`, so the runner's default won't override them.)

- [ ] **Step 5: Tests + live smoke** — `uv run pytest tests/ -v` green; then `uv run coolspot acquire-cooling` and confirm Baltimore library + senior records appear in `data/raw/cooling_centers_pending.json` with `source_type:"designated"`; report the counts.
- [ ] **Step 6: Commit** (fixtures included) — `git commit -am "feat: Baltimore County designated cooling sites (libraries + senior centers)"`

---

### Task 3: Finder display + known-limitations + regenerate + deploy

**Files:** Modify `site/js/finder.js`, `site/css/style.css`, `site/js/common.js` (KNOWN_LIMITATIONS), `tests-e2e/smoke.spec.mjs`; regenerate `site/data/*`.

- [ ] **Step 1: `finder.js` — designated badge + notes.** In `card()`, replace the badge line and add a notes line:

```javascript
  const badge = it.kind !== "center"
    ? (it.emergency_services ? '<span class="badge badge-er">ER</span>'
                             : '<span class="badge badge-hosp">Hospital</span>')
    : it.source_type === "designated"
      ? '<span class="badge badge-desig">Designated site</span>'
      : '<span class="badge badge-cc">Cooling center</span>';
```
Add after the `hours` line and include `${notes}` in the returned template before the actions `<p>`:

```javascript
  const notes = it.notes ? `<p class="card-note">${esc(it.notes)}</p>` : "";
```

- [ ] **Step 2: CSS** — add:

```css
.badge-desig { background: #a16207; }   /* amber-brown: cooling-related but conditional */

.result-card .card-note {
  margin: 0.2rem 0;
  font-size: 0.82rem;
  color: var(--color-gray);
}
```

- [ ] **Step 3: `common.js` KNOWN_LIMITATIONS** — replace the "Maryland coverage is partial" entry body with:

```javascript
    body: "Cooling sites are included for Prince George's, Anne Arundel, Howard, and Baltimore " +
      "counties. Baltimore County is included by designation — the county names all public " +
      "library branches and senior centers as cooling sites during extreme-heat events rather " +
      "than publishing a fixed list, so those entries are marked “Designated site”; " +
      "confirm hours by calling ahead, and note senior centers primarily serve older adults. " +
      "Maryland counties beyond these four are not yet covered.",
```

(The finder's `#known-limitations` e2e asserts the section contains "Baltimore County" — still true.)

- [ ] **Step 4: Regenerate payloads** — `set -a; source .env; set +a; uv run coolspot all` (full live run: re-scrape all jurisdictions incl. Baltimore, geocode, publish). Confirm `site/data/cooling_centers.geojson` contains features with `source_type:"designated"`:

```bash
python3 -c "
import json
fs = json.load(open('site/data/cooling_centers.geojson'))['features']
d = [f for f in fs if f['properties'].get('source_type') == 'designated']
print(len(fs), 'centers total;', len(d), 'designated (Baltimore)')
assert len(d) >= 8, 'expected Baltimore designated sites'
print('sample:', d[0]['properties']['name'], '—', d[0]['properties']['notes'][:40])"
```

- [ ] **Step 5: e2e** — append:

```javascript
test("designated Baltimore sites carry the badge and caveat", async ({ page }) => {
  // Data-driven: confirm the shipped payload has designated sites, then drive the UI to one.
  await page.goto("/");
  const near = await page.evaluate(async () => {
    const fs = (await (await fetch("data/cooling_centers.geojson")).json()).features;
    const d = fs.find((f) => f.properties.source_type === "designated");
    return d ? { lon: d.geometry.coordinates[0], lat: d.geometry.coordinates[1] } : null;
  });
  test.skip(near === null, "no designated sites in payload");
  await page.evaluate(({ lat, lon }) => window.__showNearestForTest?.(lat, lon), near);
  // Fallback if no test hook: search a Baltimore-area place instead.
});
```

If exposing a test hook is undesirable, instead assert via a place search near Baltimore County (e.g. "towson md") that at least one result card shows the "Designated site" badge and a `.card-note`. Choose whichever is robust against the real data during implementation; the assertion must prove a designated badge + caveat render.

- [ ] **Step 6: Full verify + deploy** — `uv run pytest tests/ -v` + `npm run test:e2e` green; commit (code + regenerated payloads, noted in body); merge to main; `gh workflow run pages.yml`; watch; live-verify a Baltimore-area search shows a "Designated site" result with its caveat, zero console errors.

## Self-review (inline)

- Spec coverage: source_type (T1), Baltimore adapter + two-part citation + caveats + verify-first (T2), finder badge/notes + known-limitations (T3), testing (all), regenerate/deploy (T3). Publish passthrough is automatic (`to_feature`), noted. No gaps.
- Placeholders: the two `parse_*` bodies and the exact directory URLs are resolved against captured fixtures in Task 2 (bounded, fixture-backed — same pattern as the shipped MD county adapters), not open TBDs.
- Consistency: `source_type` values, `md-baltimore-{lib,senior}-` id prefixes, `badge-desig`/`.card-note` classes consistent across T1–T3 and tests.
