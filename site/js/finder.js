// finder.js — address search -> nearest cooling centers + hospitals.
import { loadJSON, initMap, haversineKm, fmtKmMiles, directionsUrl, geocodeAddress } from "./common.js";

const state = { map: null, cfg: null, centers: [], hospitals: [], markers: L.layerGroup(), youMarker: null };

function featureToItem(f, kind) {
  const [lon, lat] = f.geometry.coordinates;
  return { ...f.properties, lat, lon, kind };
}

async function boot() {
  const [cfg, centersFC, hospitalsFC, manifest] = await Promise.all([
    loadJSON("data/site_config.json"), loadJSON("data/cooling_centers.geojson"),
    loadJSON("data/hospitals.geojson"), loadJSON("data/manifest.json"),
  ]);
  state.cfg = cfg;
  state.centers = centersFC.features.map((f) => featureToItem(f, "center"));
  state.hospitals = hospitalsFC.features.map((f) => featureToItem(f, "hospital"));
  state.map = initMap("map", cfg);
  state.markers.addTo(state.map);
  renderFreshness(manifest);
  const sel = document.getElementById("area-select");
  sel.append(new Option("Choose an area…", ""));
  cfg.fallback_areas.forEach((a, i) => sel.append(new Option(a.label, String(i))));
  sel.addEventListener("change", () => {
    const a = cfg.fallback_areas[Number(sel.value)];
    if (a) showNearest(a.lat, a.lon, `Showing results near ${a.label}`);
  });
  document.getElementById("address-form").addEventListener("submit", onSearch);
}

function renderFreshness(manifest) {
  const parts = Object.entries(manifest.jurisdictions)
    .map(([j, m]) => `${j.toUpperCase()}: ${m.count} centers (verified ${m.retrieved_date})`);
  document.getElementById("freshness").textContent =
    `Data updated ${manifest.generated} — ${parts.join(" · ")} · ${manifest.hospitals.count} hospitals`;
}

async function onSearch(ev) {
  ev.preventDefault();
  const status = document.getElementById("search-status");
  const fallback = document.getElementById("fallback-picker");
  status.textContent = "Looking up address…";
  fallback.hidden = true;
  try {
    const q = document.getElementById("address-input").value.trim();
    const hit = await geocodeAddress(q);
    if (!hit) {
      status.textContent = "";
      fallback.hidden = false;
      return;
    }
    showNearest(hit.lat, hit.lon, `Results near ${hit.matched}`);
  } catch (err) {
    status.textContent = `Address lookup is unavailable (${err.message}). Pick an area below instead.`;
    fallback.hidden = false;
  }
}

function nearest(items, lat, lon, n) {
  return items
    .map((it) => ({ ...it, km: haversineKm(lat, lon, it.lat, it.lon) }))
    .sort((a, b) => a.km - b.km)
    .slice(0, n);
}

function showNearest(lat, lon, label) {
  const { cfg } = state;
  document.getElementById("search-status").textContent = label;
  const centers = nearest(state.centers, lat, lon, cfg.nearest_n);
  const hospitals = nearest(state.hospitals.filter((h) => h.emergency_services !== false), lat, lon, 3);
  state.markers.clearLayers();
  if (state.youMarker) state.youMarker.remove();
  state.youMarker = L.circleMarker([lat, lon], { radius: 8, color: "#1d4ed8", fillOpacity: 0.9 })
    .bindPopup("Your location").addTo(state.map);
  const all = [...centers, ...hospitals];
  all.forEach((it) => {
    const m = L.marker([it.lat, it.lon]).bindPopup(`<b>${esc(it.name)}</b><br>${esc(it.address)}, ${esc(it.city)}`);
    state.markers.addLayer(m);
  });
  state.map.fitBounds(L.latLngBounds(all.map((i) => [i.lat, i.lon])).extend([lat, lon]), { padding: [30, 30] });
  renderResults(centers, hospitals);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function card(it) {
  const badge = it.kind === "center" ? '<span class="badge badge-cc">Cooling center</span>'
    : it.emergency_services ? '<span class="badge badge-er">ER</span>'
    : '<span class="badge badge-hosp">Hospital</span>';
  const hours = it.hours ? `<p class="hours">${esc(it.hours)}</p>`
    : it.kind === "center" ? '<p class="hours muted">Hours not listed — call ahead</p>' : "";
  const phone = it.phone ? `<a href="tel:${esc(it.phone.replace(/[^\d+]/g, ""))}">${esc(it.phone)}</a> · ` : "";
  return `<article class="result-card">
    <h3>${esc(it.name)} ${badge}</h3>
    <p>${esc(it.address)}, ${esc(it.city)}, ${esc(it.state)} — <b>${fmtKmMiles(it.km)}</b></p>
    ${hours}
    <p>${phone}<a class="btn" target="_blank" rel="noopener"
        href="${directionsUrl(it.name, it.address, it.city, it.state)}">Directions</a>
       · <a href="${esc(it.source_url)}" target="_blank" rel="noopener">source</a></p>
  </article>`;
}

function renderResults(centers, hospitals) {
  document.getElementById("results").innerHTML =
    `<h2>Nearest cooling centers</h2>${centers.map(card).join("")}
     <h2>Nearest hospitals</h2>${hospitals.map(card).join("")}`;
}

boot().catch((err) => {
  document.getElementById("search-status").textContent = `Failed to load data: ${err.message}`;
  throw err;
});
