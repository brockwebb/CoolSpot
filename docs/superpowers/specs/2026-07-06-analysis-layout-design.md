# Analysis View Round 3: Compact Controls, Horizontal Legend, Full-Width Map — Design Spec

**Date:** 2026-07-06
**Status:** Direct user directive (layout) + user-reported display bug (tract identity); approved via conversation.
**Scope:** `site/analysis.html`, `site/js/analysis.js`, `site/css/style.css`, small `pipeline/acquire/boundaries.py` / `publish_tracts` passthrough. Finder view untouched.

## Problems (user-reported)

1. The stacked 6-radio "Map layer" fieldset wastes vertical space and pushes the map down.
2. The legend sits in a right-hand column, stealing horizontal real estate the map needs
   for visual exploration.
3. The tract info box shows a bare GEOID ("Tract 11001001702") — meaningless to a human.
   It must show the tract number and county name.

## Design

### 1. Compact control bar (one wrapping row)

```
Show as: (•) Percent ( ) Number of people   Map layer: [Heat vulnerability (CRE-Heat) ▾] ⓘ
☐ Show cooling centers  ☐ Show hospitals  ☐ Highlight underserved tracts ⓘ
```

- The layer picker becomes a `<select id="layer-select">` with the same six options and
  values (`heat|no_ac|poverty|age65|disability|distance`), placed to the right of the
  "Number of people" radio, label "Map layer:".
- The two ⓘ disclosures keep their ids (`layers-help`, `underserved-help`) and content;
  the layers ⓘ sits after the select, opening as an overlay-style block that does not
  reflow the map (absolute-positioned within the control bar).
- Checkboxes become inline (one row, wrapping on mobile).

### 2. Horizontal legend above the map, full map width

- `#legend` moves above `#map`, same width, one wrapping row:
  `<layer label> [swatch <5%] [5–10%] [10–15%] [15–25%] [25–40%] [≥40%] [no data]`.
- Map becomes full-width (the `.finder-layout` two-column grid is dropped on this page);
  height stays 55vh mobile / 75vh desktop.

### 3. Tract identity + details: popup AND slim bar

- Clicking a tract shows a **Leaflet popup** at the click point AND updates a **slim
  horizontal bar** (`#tract-info`, keeps `aria-live="polite"`) directly below the map.
  Same content in both, single content-builder function.
- Title format: **"Census Tract 5051.01 — Carroll County, MD"** (never a bare GEOID;
  GEOID may appear small/muted as a secondary detail).
- Detail line stays no-chartjunk: counts with separators, whole percents, whole km.

### 4. Pipeline: tract identity passthrough

- The already-downloaded cartographic boundary shapefiles carry `NAMELSAD`
  ("Census Tract 5051.01"), `NAMELSADCO` ("Carroll County"), `STUSPS` ("MD") — verified
  2026-07-06. `boundaries.shapefile_to_features` keeps them as properties
  `tract_name`, `county`, `state_abbr` alongside `GEOID`; `publish_tracts` passes them
  through (it already updates properties in place). Regenerate payloads.
- No new fetches, no client-side FIPS lookup table.

## Error handling

- Missing `tract_name`/`county` on a feature (defensive): popup/bar title falls back to
  `Tract {GEOID}` — never blank, never crashes.

## Testing

- pytest: `shapefile_to_features` fixture test asserts the three new properties.
- Playwright: layer switching via the `<select>` updates the legend; legend renders above
  the map (assert DOM order); tract click opens a popup containing "County"; slim bar
  updates with the same title; existing toggle/underserved/nav tests updated for the
  select control.

## Out of scope

- Finder page layout; proportional symbols (PL-1) / value-by-alpha (PL-2) remain parked.
