// common.js — shared map/data/geocode helpers. ES module.
export async function loadJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`Failed to load ${path}: HTTP ${r.status}`);
  return r.json();
}

export function initMap(elementId, siteConfig) {
  const map = L.map(elementId).setView(siteConfig.map_center, siteConfig.map_zoom);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  return map;
}

export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371, toR = (d) => (d * Math.PI) / 180;
  const dp = toR(lat2 - lat1), dl = toR(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(toR(lat1)) * Math.cos(toR(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function fmtKmMiles(km) {
  return `${(km * 0.621371).toFixed(1)} mi (${km.toFixed(1)} km)`;
}

export function directionsUrl(name, address, city, state) {
  const dest = encodeURIComponent(`${name}, ${address}, ${city}, ${state}`);
  return `https://www.google.com/maps/dir/?api=1&destination=${dest}`;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function renderFreshness(manifest) {
  const parts = Object.entries(manifest.jurisdictions)
    .map(([j, m]) => `${j.toUpperCase()}: ${m.count} centers (verified ${m.retrieved_date})`);
  document.getElementById("freshness").textContent =
    `Data updated ${manifest.generated} — ${parts.join(" · ")} · ${manifest.hospitals.count} hospitals`;
}

// Single source of truth for the on-page caveats, shared by both views so the
// finder and analysis pages never drift. Rendered into #known-limitations-list.
export const KNOWN_LIMITATIONS = [
  {
    title: "Cooling center hours change without notice",
    body: "Listings show a center's usual schedule where it is published, but hours and " +
      "open/closed status shift with weather, staffing, and heat-emergency activations. Always " +
      "call ahead before traveling. The footer shows the date each jurisdiction's list was last checked.",
  },
  {
    title: "Maryland coverage is partial",
    body: "Cooling centers are included for Prince George's, Anne Arundel, and Howard counties only; " +
      "other Maryland counties are not yet covered. Baltimore County publishes no address-level " +
      "cooling-center list, so it cannot be included — check the county's emergency-management page directly.",
  },
  {
    title: "Delaware is not yet included",
    body: "This release covers Washington, DC, Maryland, and Virginia only.",
  },
  {
    title: "A few addresses could not be mapped",
    body: "A small number of cooling-center addresses could not be matched to coordinates by the Census " +
      "geocoder. They are held back rather than shown at a wrong location, and are flagged for manual " +
      "review rather than dropped.",
  },
  {
    title: "Heat-vulnerability and AC layers are experimental estimates",
    body: "The CRE-Heat and LACE map layers are U.S. Census Bureau experimental data products — modeled " +
      "estimates, not direct counts — and their methodology and vintage can change year to year. Treat " +
      "them as indicators, not precise measurements.",
  },
  {
    title: "Hospital locations are a fixed roster",
    body: "Hospital points come from a national roster whose coordinates were last set in May 2024. " +
      "Attributes such as the emergency-services flag are refreshed, but the location list itself is not " +
      "re-verified on each update, so a very recently opened or closed facility may be missing or stale.",
  },
  {
    title: "Address search covers standard U.S. addresses",
    body: "The finder uses the U.S. Census geocoder; very new construction or non-standard addresses may " +
      "not match. If your address isn't found, pick the nearest listed area instead.",
  },
];

export function renderKnownLimitations(listElementId = "known-limitations-list") {
  const el = document.getElementById(listElementId);
  if (!el) return;
  el.innerHTML = KNOWN_LIMITATIONS
    .map((k) => `<li><strong>${esc(k.title)}.</strong> ${esc(k.body)}</li>`)
    .join("");
}

// Census Geocoder sends no CORS headers (verified 2026-07-05); JSONP is the
// only keyless in-browser path. See AD-001 #4.
export function geocodeAddress(oneline, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const cb = "coolspot_geo_" + Math.random().toString(36).slice(2);
    const script = document.createElement("script");
    const timer = setTimeout(() => { cleanup(); reject(new Error("Geocoder timed out")); }, timeoutMs);
    function cleanup() {
      // Reassign to a no-op instead of `delete window[cb]`: if the JSONP
      // response arrives after the timeout has already fired and cleaned up,
      // the callback script tag may still invoke window[cb] once it loads —
      // deleting the property would make that a ReferenceError instead of a
      // harmless call into a function that does nothing.
      window[cb] = () => {};
      script.remove();
      clearTimeout(timer);
    }
    window[cb] = (data) => {
      cleanup();
      const m = data?.result?.addressMatches?.[0];
      if (!m) { resolve(null); return; }
      resolve({ lat: m.coordinates.y, lon: m.coordinates.x, matched: m.matchedAddress });
    };
    script.onerror = () => { cleanup(); reject(new Error("Geocoder unreachable")); };
    const params = new URLSearchParams({
      address: oneline, benchmark: "Public_AR_Current", format: "jsonp", callback: cb,
    });
    script.src = `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?${params}`;
    document.head.appendChild(script);
  });
}
