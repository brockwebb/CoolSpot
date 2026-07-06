# Finder Round 4: Place-Name Search — Design Spec

**Date:** 2026-07-06
**Status:** Approved via conversation (inline pick-one for ambiguity).
**Scope:** Finder view + one pipeline addition. Analysis view untouched.

## Problem

"Suitland MD" returns "couldn't find that address": the Census Geocoder's onelineaddress
endpoint matches street addresses only. Users reasonably enter a city/town/CDP/county for a
general location; the area-picker fallback is a poor answer when the user already named a
place. Full street address remains the most precise input.

## Design

### Data: `site/data/places.json` (pipeline-published)

- Sources (cached downloads like other raw inputs, verified live 2026-07-06):
  - `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip`
  - `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip`
- Tab-delimited; filter `USPS ∈ {DC, MD, VA}` (~1,225 places + ~160 counties).
- Published entry: `{"q": "suitland", "display": "Suitland, MD", "state": "MD", "lat": .., "lon": ..}`
  - `q` = lowercase match key: gazetteer NAME with the LSAD suffix stripped
    (trailing " CDP", " city", " town", " village", " borough", " municipality", " comunidad",
    " zona urbana"), punctuation (apostrophes/periods) removed, whitespace collapsed.
  - `display` = human name without suffix + ", ST" for places; counties keep their suffix
    ("Prince George's County, MD") and ALSO get a suffix-stripped `q` ("prince georges").
  - Duplicate `q` within the same state (e.g., a "X city" and "X CDP" both present): keep the
    larger-ALAND entry; collisions across states are kept (that's the ambiguity case).
- Coordinates: INTPTLAT/INTPTLONG rounded to 4 decimals (place centers; no chartjunk precision).
- Size budget: ~1,400 entries ≈ 120 KB pretty / ~80 KB minified — fine; loaded with the other
  boot fetches.

### Finder resolution order

1. Input contains a digit → Census geocoder (street address, most precise) first;
   on null match, place lookup as fallback.
2. No digit → place lookup FIRST (instant, local, no network); geocoder as fallback
   (covers named buildings the geocoder happens to know).
3. Both miss → existing area picker (last resort, unchanged).

### Place matching (client, `matchPlaces(input, places)`)

- Normalize input like `q` (lowercase, strip punctuation, collapse spaces).
- Detect and strip a trailing state token: `dc|md|va|maryland|virginia|district of columbia`
  (with or without a comma) → constrains matches to that state.
- Match ladder: exact `q` match → prefix match → returns [] (no fuzzy/contains; keeps
  results predictable).
- One match → use it. Multiple matches (max shown: 5) → inline pick-one list under the
  search box: buttons labeled with `display`, click → results for that place.

### Result messaging

- Place hit: status line "Showing results near {display} (place center — enter a street
  address for precise distances)."
- Street hit: unchanged ("Results near {matched address}").

### Accessibility / UI

- The pick-one list reuses the fallback-picker container pattern: a `<ul id="place-choices">`
  of real `<button>`s inside the search panel, cleared on the next search; `#search-status`
  (aria-live) announces "Multiple places match — choose one."

## Error handling

- `places.json` fetch failure → finder still boots; place lookup silently unavailable,
  geocoder + area picker unaffected (place search is progressive enhancement). This is the
  ONE deliberate exception to fail-loud, justified: a missing enhancement must not take down
  the emergency-relevant address search. A console.warn records it.
- Gazetteer download/parse failure in the pipeline → fails loudly (standard).
- Zero DC/MD/VA rows after filter → pipeline RuntimeError (dead-source canary, standard).

## Testing

- pytest: gazetteer parse + suffix-strip + dedupe rules on a fixture excerpt; places.json
  published with expected entry shape; "Suitland" present with MD coords.
- Playwright: "suitland md" → results render with "place center" status (no geocoder needed —
  works offline-deterministic); ambiguous bare name → pick-one buttons → click → results;
  gibberish still reaches the area picker; a street address still resolves via geocoder
  (existing test unchanged).

## Out of scope

- Autocomplete/typeahead while typing (would be the natural next step; not requested).
- ZIP-code centroids (different dataset; add later if users ask).
