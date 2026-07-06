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

// Census Geocoder sends no CORS headers (verified 2026-07-05); JSONP is the
// only keyless in-browser path. See AD-001 #4.
export function geocodeAddress(oneline, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const cb = "coolspot_geo_" + Math.random().toString(36).slice(2);
    const script = document.createElement("script");
    const timer = setTimeout(() => { cleanup(); reject(new Error("Geocoder timed out")); }, timeoutMs);
    function cleanup() { delete window[cb]; script.remove(); clearTimeout(timer); }
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
