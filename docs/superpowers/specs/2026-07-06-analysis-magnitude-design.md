# Analysis View Round 2: Magnitude, Gaps, Navigation — Design Spec

**Date:** 2026-07-06
**Status:** Approved direction from brainstorming (rate⇄count toggle + redefined gaps + segmented nav); this document is the written spec for review.
**Scope:** Analysis view (`site/analysis.html` / `site/js/analysis.js`), shared header on both pages, small pipeline addition. No new pages, no new data sources.

## Problem

1. **Rates hide magnitude.** The choropleth shows "% with 3+ heat factors" — but 40% of 150
   people and 40% of 6,000 people paint the same red. The map answers "how concentrated?"
   but never "how many people?", and the counts already exist in the published data
   (`pred3_e`, `no_ac_e`, `pop_65plus`) or in ACS tables the pipeline fetches and discards.
2. **"Highlight gap tracts" is distance-blind.** A gap today = nearest cooling center ≥ 8 km,
   regardless of who lives there. An empty rural tract highlights identically to a populous,
   vulnerable one. The label is also unexplained in the UI.
3. **Finder ↔ analysis navigation is a text link** users overlook; the two views read as
   separate pages rather than two modes of one tool.

## Design principle: no chartjunk

The interface is for **visual exploration, not decimal-precision reporting**. Binding rules:

- All thresholds, legend stops, and config values are **round numbers**. No data-derived
  thresholds (a median-derived cutoff like 517 is chartjunk in config form).
- Counts display with thousands separators and **no decimals** ("1,500 people", never "1523.4").
- Percentages display as **whole numbers** in legends and the tract panel ("32%", not "32.15%").
- Distances in the tract panel: whole km, with "<1 km" below 1. (Finder result cards keep
  their existing mi/km format — that view is navigational, not statistical.)
- No new gridlines, borders, icons, or emphasis beyond what each element needs to be read.

## Features

### 1. Segmented navigation toggle (both pages)

Replace the header text-link nav with a two-button segmented control:

```
[ Find cooling centers ] [ Heat vulnerability map ]
```

Active segment filled (teal background, white text), inactive outlined. Plain anchors styled
as a group — no JS. `aria-current="page"` retained on the active segment.

### 2. Rate ⇄ count toggle

One control above the layer picker, applying to whichever layer is active:

```
Show as:  (•) Percent of tract   ( ) Number of people
```

| Layer | Percent form | Count form | Count source |
|---|---|---|---|
| Heat vulnerability (CRE-Heat) | `pred3_pe` | `pred3_e` | already published |
| No air conditioning (LACE) | `no_ac_pe` | `no_ac_e` (households) | already published |
| Age 65+ | computed `pop_65plus / pop_total` | `pop_65plus` | already published |
| Below poverty | `pct_poverty` | `pov_below_e` | **new: publish ACS B17001_002E** |
| With a disability | `pct_disability` | `disability_e` | **new: publish ACS S1810_C02_001E** |
| Distance to nearest cooling center | — | — | exempt: toggle disabled (dimmed) with no mode change |

Rules:

- **Real numerators only.** Poverty and disability counts come from the ACS variables the
  pipeline already fetches (currently used only to compute the percent, then discarded).
  Never derive a count as `% × population` — denominators differ (poverty universe ≠ total
  population; disability universe = civilian noninstitutionalized) and the rounding compounds.
- Each layer defines two label strings and two sets of **round-number** legend stops
  (percent stops stay as-is; count stops in round people/household units, e.g.
  `[100, 250, 500, 1000, 2000]` — final values tuned per layer at implementation against the
  real distributions, but always round).
- Count-form labels name the unit: "People with 3+ heat-vulnerability factors",
  "Households without air conditioning".
- Legend re-renders on toggle; the map recolors via the existing `setStyle` path.
- Default remains **Percent** (matches current behavior).
- **Stated limitation** (in the layer help, not over-claimed anywhere): count view still colors
  tracts, so geographically large tracts still carry more visual weight than their population
  justifies. The fix for that (proportional symbols) is explicitly deferred, recorded in the
  parking lot below.

### 3. Redefined "gap tracts": need + access

A gap tract = **far from cooling AND many affected people**:

```
nearest_cc_km ≥ gap_distance_km   AND   pred3_e ≥ gap_min_affected
```

- `gap_distance_km: 8` (existing) and `gap_min_affected: 1500` (new; data-verified — 500 would highlight 37% of tracts, 1500 highlights a selective 4%) — both in
  `config/pipeline.yaml` under `publish:`, surfaced to the client through `site_config.json`.
  Round numbers per the no-chartjunk rule.
- Checkbox label becomes **"Highlight underserved tracts"** — plain words for what it now means.
- Highlight styling unchanged (blue outline, others receded).

### 4. ⓘ help disclosures

A reusable, dependency-free pattern: native `<details class="help"><summary>ⓘ</summary>…</details>`
inline next to a control. Keyboard/screen-reader accessible by default. Two instances:

1. **Underserved tracts** — exact definition in plain words: "Highlighted tracts are more than
   8 km from any listed cooling center AND are home to at least 1,500 people with 3 or more
   heat-vulnerability risk factors (Census CRE-Heat estimate). These are the areas where a new
   cooling center would reach the most vulnerable people." (Values interpolated from
   `site_config.json`, not hardcoded in the string.)
2. **Layer picker** — one disclosure covering: CRE-Heat and LACE are Census experimental
   modeled estimates; percent vs count explained in one sentence each; the tract-area caveat
   from §2.

### 5. Display cleanup (applies the no-chartjunk rules to what exists)

- Tract detail panel: percentages as whole numbers, counts with thousands separators,
  distance as whole km / "<1 km".
- Legend labels use the layer's `fmt` — counts get separators ("1,000–2,000"), percents whole.

## Pipeline change (small)

`pipeline/acquire/census.py` `acs_attrs()` additionally returns `pov_below_e` (B17001_002E)
and `disability_e` (S1810_C02_001E) as integers (existing `_acs_int` sentinel handling), and
`publish_tracts` carries them into tract properties. Regenerate `site/data/tracts_*.geojson`.
`site_config.json` gains `gap_min_affected`. No new fetches — the variables are already in
every `data/raw/acs_*.json`.

## Error handling

- Missing count value (`null` from ACS suppression) → tract renders as no-data gray in count
  mode, exactly as percent mode does today.
- `gap_min_affected` missing from config → pipeline fails loudly at publish (existing
  fail-loud config pattern).
- Toggle state is view-local (no persistence); switching layers preserves the current mode
  except the distance layer, which dims the toggle and ignores it.

## Testing

- **pytest:** `acs_attrs` returns the two new counts (fixture-verified, sentinel → None);
  published tract properties include them; `site_config.json` includes `gap_min_affected`.
- **Playwright:** toggle flips legend from `%` labels to people-count labels with separators;
  distance layer dims the toggle; "Highlight underserved tracts" produces at least one
  highlighted tract and the ⓘ disclosure opens and contains the definition; segmented nav
  present on both pages with correct active state.

## Out of scope / parking lot

- **PL-1: Proportional-symbol "affected people" view** (circle area = count, color = rate) —
  the full fix for tract-area distortion; deferred by explicit user choice.
- **PL-2: Value-by-alpha population fading** — deferred by explicit user choice.
- Any change to the finder view beyond the shared header nav.
