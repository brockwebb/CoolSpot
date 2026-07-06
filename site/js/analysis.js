// analysis.js — tract choropleths + cooling-center overlay + coverage gaps.
import { loadJSON, initMap } from "./common.js";

const LAYERS = {
  pred3_pe:      { label: "% with 3+ heat-vulnerability factors (CRE-Heat 2022, experimental)", fmt: (v) => `${v}%`, stops: [5, 10, 15, 25, 40] },
  no_ac_pe:      { label: "% households without air conditioning (LACE 2023, experimental)",    fmt: (v) => `${v}%`, stops: [2, 5, 10, 20, 35] },
  pct_poverty:   { label: "% below poverty level (ACS 2020–2024)",  fmt: (v) => `${v}%`, stops: [5, 10, 20, 30, 40] },
  pop_65plus:    { label: "Residents age 65+ (ACS 2020–2024)",      fmt: (v) => String(v), stops: [200, 400, 700, 1100, 1600] },
  pct_disability:{ label: "% with a disability (ACS 2020–2024)",    fmt: (v) => `${v}%`, stops: [5, 10, 15, 22, 30] },
  nearest_cc_km: { label: "Distance to nearest cooling center (km)", fmt: (v) => `${v} km`, stops: [2, 5, 10, 20, 35] },
};
// Sequential 6-step ramp (light -> dark).
const RAMP = ["#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#e34a33", "#b30000"];
const NO_DATA = "#d7d7d7";

const state = { map: null, cfg: null, tracts: null, layerKey: "pred3_pe", tractLayer: null,
                centersLayer: null, hospitalsLayer: null, onlyGaps: false };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function colorFor(value, stops) {
  if (value == null) return NO_DATA;
  let i = 0;
  while (i < stops.length && value >= stops[i]) i++;
  return RAMP[i];
}

function styleFeature(f) {
  const p = f.properties;
  const def = LAYERS[state.layerKey];
  const isGap = p.nearest_cc_km != null && p.nearest_cc_km >= state.cfg.gap_distance_km;
  if (state.onlyGaps && !isGap) return { fillOpacity: 0.05, weight: 0.3, color: "#999", fillColor: NO_DATA };
  return {
    fillColor: p.water_tract === 1 ? NO_DATA : colorFor(p[state.layerKey], def.stops),
    fillOpacity: 0.75, weight: state.onlyGaps && isGap ? 2 : 0.4,
    color: state.onlyGaps && isGap ? "#1d4ed8" : "#666",
  };
}

function onEachTract(f, layer) {
  layer.on("click", () => {
    const p = f.properties;
    document.getElementById("tract-info").innerHTML = `
      <h3>Tract ${p.GEOID}</h3>
      <ul>
        <li>Population: ${p.pop_total ?? "n/a"}</li>
        <li>CRE-Heat 3+ factors: ${p.pred3_pe ?? "n/a"}%</li>
        <li>No AC: ${p.no_ac_pe ?? "n/a"}%</li>
        <li>Poverty: ${p.pct_poverty ?? "n/a"}% · 65+: ${p.pop_65plus ?? "n/a"} · Disability: ${p.pct_disability ?? "n/a"}%</li>
        <li>Nearest cooling center: ${p.nearest_cc_km ?? "n/a"} km</li>
      </ul>`;
  });
}

function renderLegend() {
  const def = LAYERS[state.layerKey];
  const rows = RAMP.map((color, i) => {
    const lo = i === 0 ? "&lt; " + def.fmt(def.stops[0])
      : i === RAMP.length - 1 ? "&ge; " + def.fmt(def.stops[def.stops.length - 1])
      : `${def.fmt(def.stops[i - 1])}–${def.fmt(def.stops[i])}`;
    return `<div class="legend-row"><span class="swatch" style="background:${color}"></span>${lo}</div>`;
  }).join("");
  document.getElementById("legend").innerHTML =
    `<h3>${def.label}</h3>${rows}<div class="legend-row"><span class="swatch" style="background:${NO_DATA}"></span>no data / water</div>`;
}

function redraw() {
  state.tractLayer.setStyle(styleFeature);
  renderLegend();
}

async function boot() {
  const [cfg, dc, md, va, centersFC, hospitalsFC] = await Promise.all([
    loadJSON("data/site_config.json"),
    loadJSON("data/tracts_dc.geojson"), loadJSON("data/tracts_md.geojson"), loadJSON("data/tracts_va.geojson"),
    loadJSON("data/cooling_centers.geojson"), loadJSON("data/hospitals.geojson"),
  ]);
  state.cfg = cfg;
  state.map = initMap("map", cfg);
  state.tracts = { type: "FeatureCollection", features: [...dc.features, ...md.features, ...va.features] };
  state.tractLayer = L.geoJSON(state.tracts, { style: styleFeature, onEachFeature: onEachTract }).addTo(state.map);
  state.centersLayer = L.geoJSON(centersFC, {
    pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 5, color: "#0f766e", fillColor: "#14b8a6", fillOpacity: 0.9, weight: 1 })
      .bindPopup(`<b>${esc(f.properties.name)}</b><br>${esc(f.properties.address)}`),
  }).addTo(state.map);
  state.hospitalsLayer = L.geoJSON(hospitalsFC, {
    pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 4, color: "#7f1d1d", fillColor: "#dc2626", fillOpacity: 0.8, weight: 1 })
      .bindPopup(`<b>${esc(f.properties.name)}</b>`),
  });
  document.querySelectorAll('#layer-picker input[name="layer"]').forEach((el) =>
    el.addEventListener("change", () => { state.layerKey = el.value; redraw(); }));
  document.getElementById("show-centers").addEventListener("change", (e) =>
    e.target.checked ? state.centersLayer.addTo(state.map) : state.centersLayer.remove());
  document.getElementById("show-hospitals").addEventListener("change", (e) =>
    e.target.checked ? state.hospitalsLayer.addTo(state.map) : state.hospitalsLayer.remove());
  document.getElementById("only-gaps").addEventListener("change", (e) => { state.onlyGaps = e.target.checked; redraw(); });
  renderLegend();
}

boot().catch((err) => {
  document.getElementById("tract-info").textContent = `Failed to load data: ${err.message}`;
  throw err;
});
