# Visitor Counter — Design Spec

**Date:** 2026-07-06
**Status:** Approved direction from brainstorming (GoatCounter, "both"). Blocked on one input
from the owner: the GoatCounter site code (subdomain).
**Scope:** `site/index.html`, `site/analysis.html`, `site/css/style.css`, one AD entry,
e2e. No pipeline change, no new site data.

## Problem

The owner wants to know how many people actually use CoolSpot, and to show a "visitor
number" at the bottom of the page. A static GitHub Pages site cannot count its own
visitors — there is no backend to hold a running total, and writing to the repo from the
browser would require embedding a write token in public JavaScript (forbidden). So a counter
necessarily adds a third-party call on page load.

## Constraint context

On load today the browser talks to exactly two hosts: **GitHub Pages** (the files) and
**OpenStreetMap** (tiles). The Census geocoder fires only on a search; Google only on a
"Directions" click (a plain link). This tool serves elderly, low-income, and disabled
people during heat emergencies, so adding a load-time third party is a deliberate decision,
recorded as **AD-009** — a documented reversal of the "load-time only touches GitHub + OSM"
posture, justified by (a) a privacy-first, cookieless, no-PII service and (b) a fail-silent
design that can never break or block the emergency-relevant map.

## Design

Two independent pieces under one GoatCounter site. `{{SITE_CODE}}` is the owner-chosen
subdomain (default intent: `coolspot`), the **single** value to substitute; it appears in
exactly two URLs.

### 1. Tracking (owner's private dashboard)

One async script tag before `</body>` on **both** pages:

```html
<script data-goatcounter="https://{{SITE_CODE}}.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
```

- Cookieless; no persistent identifier; no personal data stored; GDPR-clean (verified
  against goatcounter.com 2026-07-06). Powers the owner-only dashboard (unique visits,
  pages, referrers, over time) — the accurate answer to "how many people use it."
- `async` + failure-inert: if `gc.zgo.at` is unreachable the script simply doesn't run;
  nothing on the page depends on it.

### 2. Visible number (footer badge) — image embed, NOT a JS fetch

```html
<p class="visitor-line">
  Visitors:
  <img class="visitor-count" alt=""
       src="https://{{SITE_CODE}}.goatcounter.com/counter/TOTAL.svg?no_branding=1" />
  · Anonymous, cookieless visit counts via
  <a href="https://www.goatcounter.com/" target="_blank" rel="noopener">GoatCounter</a>.
</p>
```

- **Why an `<img>`, not `fetch()`:** GoatCounter's `/counter/*.json` endpoint does not reliably
  send CORS headers from a third-party origin (GitHub issue arp242/goatcounter#782), so a
  browser `fetch()` from `brockwebb.github.io` would fail. An `<img>`/SVG embed is not a
  cross-origin fetch and **bypasses CORS entirely** — no JavaScript, no CORS, and it
  **fails silent by construction**: a broken/blocked image renders nothing (empty `alt`),
  leaving the page and map untouched. This is the load-bearing choice.
- **`TOTAL`** = site-wide count across both pages (per GoatCounter docs); server-cached ~4h,
  so the number is "approximately N," which also means it cannot be gamed by refreshing.
- Label is "Visitors" (GoatCounter counts visits, which approximate unique visitors).

### 3. Owner-side setup (one-time, by the owner)

In GoatCounter settings, enable the **visitor-counter / public count** display option (this
exposes only the aggregate count via `/counter/*`, NOT the full dashboard). The exact setting
name is verified at build time; if enabling the count requires "public statistics," that is
called out to the owner before shipping so it is a conscious choice.

## Cosmetic tradeoff (accepted)

The number is an SVG image, so it renders in GoatCounter's styling, not the site font — it
reads as "Visitors: 1,234" but is not pixel-matched to the footer typography. Accepted for a
footer badge. A JS-fetch version in exact site font (with the image as fallback) is parked
(PL-1) — not built, to keep the fail-silent guarantee simple.

## Error handling

- Counter image unreachable/blocked → renders nothing; no error, no layout break (empty alt,
  fixed height reserves no jarring space). Verified by the fail-silent e2e test.
- Tracking script unreachable → inert (`async`, nothing depends on it).
- The feature is entirely inert until `{{SITE_CODE}}.goatcounter.com` exists; wiring can ship
  before signup with no user-visible breakage.

## Testing

- **Playwright (no dependency on the live service):**
  1. **Fail-silent:** intercept and abort all requests to `*.goatcounter.com` and `gc.zgo.at`;
     load both pages; assert the map/legend/finder still render and there is no uncaught
     page error. This is the safety-critical test.
  2. **Presence:** footer contains `img.visitor-count` whose `src` ends with
     `/counter/TOTAL.svg?no_branding=1`, and the GoatCounter privacy link; the tracking
     `<script src*="gc.zgo.at/count.js"]` is present on both pages.
- No unit tests (no Python change).

## Out of scope / parking lot

- **PL-1:** JS-fetch counter in exact site typography with image fallback.
- Per-page counts, self-hosting GoatCounter, historical charts embedded on the page.

## The one open input

Owner provides the confirmed GoatCounter site code (subdomain). Until then the two URLs carry
`{{SITE_CODE}}`; substituting it is the first implementation step.
