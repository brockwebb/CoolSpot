# AD-001: CoolSpot Architecture Decisions

Date: 2026-07-05. Status: accepted.

1. **Static site + offline pipeline, no server.** Vanilla JS + Leaflet (OSM tiles,
   no API key), GitHub Pages. Rejected: embedded Google Maps (key+billing
   liability), Vite/Observable (unneeded build step).
2. **Vulnerability layer = Census CRE-Heat 2022** (tract CSV; experimental —
   labeled in UI). Rejected: CDC SVI/HHI, custom index.
3. **AC layer = Census LACE 2023** (Local Air Conditioning Estimates, released
   2026-05-19, tract-level, modeled AHS→ACS). Adopt-before-create evaluation
   done 2026-07-05: geography=tract, universe=occupied housing units, CSV only.
4. **Browser geocoding via Census Geocoder JSONP.** The geocoder sends no CORS
   headers (verified 2026-07-05); fetch() is impossible. JSONP verified working.
   Rejected: Nominatim (usage policy risk), server proxy (no server).
5. **Hospitals = HealthData.gov anag-cw7u** geocoded roster (frozen 2024-05)
   enriched by CCN join to CMS xubh-q36u (`emergency_services`, current names).
   HIFLD is dead (public portal shut down 2025-08-26).
6. **Cooling centers scraped per jurisdiction with provenance** (source_url +
   retrieved_date on every record; schema validation; quarantine-don't-drop).
   DC: HSEMA ArcGIS. VA: VDH WP-Store-Locator JSON (211 VA data). MD: hub-page
   discovery + PG ArcGIS + per-county HTML adapters. DE deferred to v1.1
   (press-release-only publication).
7. **Directions = Google Maps deep links** (`maps/dir/?api=1`), not embedded API.
8. **Pipeline is a CLI** (`coolspot`), per cross-project AD-003 (CLI over MCP).
