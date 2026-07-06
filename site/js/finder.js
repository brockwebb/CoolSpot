// finder.js — address search -> nearest cooling centers + hospitals.
import { loadJSON, initMap, haversineKm, fmtKmMiles, directionsUrl, geocodeAddress, esc, renderFreshness, renderKnownLimitations } from "./common.js";

const state = { map: null, cfg: null, centers: [], hospitals: [], places: [], markers: L.layerGroup(), youMarker: null };

function featureToItem(f, kind) {
  const [lon, lat] = f.geometry.coordinates;
  return { ...f.properties, lat, lon, kind };
}

async function boot() {
  const [cfg, centersFC, hospitalsFC, manifest, places] = await Promise.all([
    loadJSON("data/site_config.json"), loadJSON("data/cooling_centers.geojson"),
    loadJSON("data/hospitals.geojson"), loadJSON("data/manifest.json"),
    loadJSON("data/places.json").catch((err) => { console.warn(`places.json unavailable — place search disabled: ${err.message}`); return []; }),
  ]);
  state.cfg = cfg;
  state.centers = centersFC.features.map((f) => featureToItem(f, "center"));
  state.hospitals = hospitalsFC.features.map((f) => featureToItem(f, "hospital"));
  state.places = places;
  state.map = initMap("map", cfg);
  state.markers.addTo(state.map);
  renderFreshness(manifest);
  renderKnownLimitations();
  const sel = document.getElementById("area-select");
  sel.append(new Option("Choose an area…", ""));
  cfg.fallback_areas.forEach((a, i) => sel.append(new Option(a.label, String(i))));
  sel.addEventListener("change", () => {
    const a = cfg.fallback_areas[Number(sel.value)];
    if (a) showNearest(a.lat, a.lon, `Showing results near ${a.label}`);
  });
  document.getElementById("address-form").addEventListener("submit", onSearch);
}

const STATE_TOKENS = { "dc": "DC", "district of columbia": "DC", "md": "MD", "maryland": "MD", "va": "VA", "virginia": "VA" };

function normPlace(s) {
  // Apostrophes DELETE (george's -> georges, matching the pipeline's match_key);
  // periods/commas become spaces (st. -> st, "suitland, md" -> "suitland md").
  return String(s).toLowerCase().replace(/['’]/g, "").replace(/[.,]/g, " ").replace(/\s+/g, " ").trim();
}

function matchPlaces(input, places) {
  let q = normPlace(input);
  q = q.replace(/\s\d{5}(-\d{4})?$/, "").trim();      // tolerate a trailing ZIP/ZIP+4 the geocoder missed on
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
    console.warn(`geocoder unavailable: ${err.message}`);
    geocoderDown = true;
  }
  if (hasDigit && handlePlaceMatches(matchPlaces(q, state.places))) return;
  status.textContent = geocoderDown
    ? "Address lookup is unavailable right now. Try a city or county name, or pick an area below."
    : "";
  fallback.hidden = false;
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
  const hospitals = nearest(state.hospitals.filter((h) => h.emergency_services !== false), lat, lon, cfg.nearest_hospitals);
  state.markers.clearLayers();
  if (state.youMarker) state.youMarker.remove();
  state.youMarker = L.circleMarker([lat, lon], { radius: 8, color: "#1d4ed8", fillOpacity: 0.9 })
    .bindPopup("Your location").addTo(state.map);
  const all = [...centers, ...hospitals];
  all.forEach((it) => {
    const m = L.marker([it.lat, it.lon]).bindPopup(`<b>${esc(it.name)}</b><br>${esc(it.address)}, ${esc(it.city)}`);
    state.markers.addLayer(m);
  });
  if (all.length) {
    state.map.fitBounds(L.latLngBounds(all.map((i) => [i.lat, i.lon])).extend([lat, lon]), { padding: [30, 30] });
  } else {
    state.map.setView([lat, lon], 12);
  }
  renderResults(centers, hospitals);
}

function safeHttpUrl(u) {
  return /^https?:\/\//i.test(String(u ?? "")) ? esc(u) : null;
}

function card(it) {
  const badge = it.kind !== "center"
    ? (it.emergency_services ? '<span class="badge badge-er">ER</span>'
                             : '<span class="badge badge-hosp">Hospital</span>')
    : it.source_type === "designated"
      ? '<span class="badge badge-desig">Designated site</span>'
      : '<span class="badge badge-cc">Cooling center</span>';
  const hours = it.hours ? `<p class="hours">${esc(it.hours)}</p>`
    : it.kind === "center" ? '<p class="hours muted">Hours not listed — call ahead</p>' : "";
  const notes = it.notes ? `<p class="card-note">${esc(it.notes)}</p>` : "";
  const phone = it.phone ? `<a href="tel:${esc(it.phone.replace(/[^\d+]/g, ""))}">${esc(it.phone)}</a> · ` : "";
  const validSourceUrl = safeHttpUrl(it.source_url);
  const sourceLink = validSourceUrl ? ` · <a href="${validSourceUrl}" target="_blank" rel="noopener">source</a>` : "";
  return `<article class="result-card">
    <h3>${esc(it.name)} ${badge}</h3>
    <p>${esc(it.address)}, ${esc(it.city)}, ${esc(it.state)} — <b>${fmtKmMiles(it.km)}</b></p>
    ${hours}
    ${notes}
    <p>${phone}<a class="btn" target="_blank" rel="noopener"
        href="${directionsUrl(it.name, it.address, it.city, it.state)}">Directions</a>${sourceLink}</p>
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
