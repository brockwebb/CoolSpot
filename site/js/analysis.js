// analysis.js — tract choropleths + cooling-center overlay + underserved tracts.
import { loadJSON, initMap, esc, renderFreshness, renderKnownLimitations } from "./common.js";

// No-chartjunk formatting: whole percents, separator counts, whole km.
const fmtPct = (v) => `${Math.round(v)}%`;
const fmtCount = (v) => Math.round(v).toLocaleString("en-US");
const fmtKm = (v) => (v < 1 ? "<1 km" : `${Math.round(v)} km`);

// Each layer: pct form + optional count form. value(p) -> number|null.
const LAYERS = {
  heat: {
    pct:   { value: (p) => p.pred3_pe,  label: "% with 3+ heat-vulnerability factors (CRE-Heat 2022, experimental)", fmt: fmtPct, stops: [5, 10, 15, 25, 40] },
    count: { value: (p) => p.pred3_e,   label: "People with 3+ heat-vulnerability factors (CRE-Heat 2022, experimental)", fmt: fmtCount, stops: [250, 500, 1000, 1500, 2500] },
  },
  no_ac: {
    pct:   { value: (p) => p.no_ac_pe,  label: "% households without air conditioning (LACE 2023, experimental)", fmt: fmtPct, stops: [2, 5, 10, 20, 35] },
    count: { value: (p) => p.no_ac_e,   label: "Households without air conditioning (LACE 2023, experimental)", fmt: fmtCount, stops: [10, 25, 50, 100, 250] },
  },
  poverty: {
    pct:   { value: (p) => p.pct_poverty,  label: "% below poverty level (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 20, 30, 40] },
    count: { value: (p) => p.pov_below_e,  label: "People below poverty level (ACS 2020–2024)", fmt: fmtCount, stops: [100, 250, 500, 1000, 2000] },
  },
  age65: {
    pct:   { value: (p) => (p.pop_total && p.pop_65plus != null ? (100 * p.pop_65plus) / p.pop_total : null), label: "% residents age 65+ (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 15, 20, 30] },
    count: { value: (p) => p.pop_65plus,   label: "Residents age 65+ (ACS 2020–2024)", fmt: fmtCount, stops: [250, 500, 750, 1000, 1500] },
  },
  disability: {
    pct:   { value: (p) => p.pct_disability, label: "% with a disability (ACS 2020–2024)", fmt: fmtPct, stops: [5, 10, 15, 22, 30] },
    count: { value: (p) => p.disability_e,   label: "People with a disability (ACS 2020–2024)", fmt: fmtCount, stops: [250, 500, 750, 1000, 1500] },
  },
  distance: {
    // 'pct' slot holds the only form (km); no count form exists — activeForm() falls back here.
    pct:   { value: (p) => p.nearest_cc_km, label: "Distance to nearest cooling center", fmt: fmtKm, stops: [2, 5, 10, 20, 35] },
    count: null, // no count form; the mode toggle is disabled on this layer
  },
};
const RAMP = ["#fee8c8", "#fdd49e", "#fdbb84", "#fc8d59", "#e34a33", "#b30000"];
const NO_DATA = "#d7d7d7";

const state = { map: null, cfg: null, tracts: null, layerKey: "heat", mode: "pct", tractLayer: null,
                centersLayer: null, hospitalsLayer: null, onlyGaps: false };

function activeForm() {
  const def = LAYERS[state.layerKey];
  return def.count && state.mode === "count" ? def.count : def.pct;
}

function colorFor(value, stops) {
  if (value == null) return NO_DATA;
  let i = 0;
  while (i < stops.length && value >= stops[i]) i++;
  return RAMP[i];
}

function isUnderserved(p) {
  return p.nearest_cc_km != null && p.nearest_cc_km >= state.cfg.gap_distance_km
    && (p.pred3_e ?? 0) >= state.cfg.gap_min_affected;
}

function styleFeature(f) {
  const p = f.properties;
  const form = activeForm();
  const gap = isUnderserved(p);
  if (state.onlyGaps && !gap) return { fillOpacity: 0.05, weight: 0.3, color: "#999", fillColor: NO_DATA };
  return {
    fillColor: p.water_tract === 1 ? NO_DATA : colorFor(form.value(p), form.stops),
    fillOpacity: 0.75, weight: state.onlyGaps && gap ? 2 : 0.4,
    color: state.onlyGaps && gap ? "#1d4ed8" : "#666",
  };
}

function fmtOrNA(v, fmt) {
  return v == null ? "n/a" : fmt(v);
}

function tractTitle(p) {
  return p.tract_name && p.county && p.state_abbr ? `${p.tract_name} — ${p.county}, ${p.state_abbr}` : `Tract ${p.GEOID}`;
}

function tractDetailsHTML(p) {
  return `
    <h3>${esc(tractTitle(p))}</h3>
    <ul>
      <li>Population: ${fmtOrNA(p.pop_total, fmtCount)}</li>
      <li>3+ heat factors: ${fmtOrNA(p.pred3_e, fmtCount)} people (${fmtOrNA(p.pred3_pe, fmtPct)})</li>
      <li>No AC: ${fmtOrNA(p.no_ac_e, fmtCount)} households (${fmtOrNA(p.no_ac_pe, fmtPct)})</li>
      <li>Poverty: ${fmtOrNA(p.pov_below_e, fmtCount)} (${fmtOrNA(p.pct_poverty, fmtPct)}) ·
          65+: ${fmtOrNA(p.pop_65plus, fmtCount)} ·
          Disability: ${fmtOrNA(p.disability_e, fmtCount)} (${fmtOrNA(p.pct_disability, fmtPct)})</li>
      <li>Nearest cooling center: ${fmtOrNA(p.nearest_cc_km, fmtKm)} <span class="muted">· GEOID ${esc(p.GEOID)}</span></li>
    </ul>`;
}

function onEachTract(f, layer) {
  layer.on("click", (e) => {
    const html = tractDetailsHTML(f.properties);
    document.getElementById("tract-info").innerHTML = html;
    L.popup({ maxWidth: 320 }).setLatLng(e.latlng).setContent(html).openOn(state.map);
  });
}

function renderLegend() {
  const form = activeForm();
  const rows = RAMP.map((color, i) => {
    const lo = i === 0 ? "&lt; " + form.fmt(form.stops[0])
      : i === RAMP.length - 1 ? "&ge; " + form.fmt(form.stops[form.stops.length - 1])
      : `${form.fmt(form.stops[i - 1])}–${form.fmt(form.stops[i])}`;
    return `<span class="legend-row"><span class="swatch" style="background:${color}"></span>${lo}</span>`;
  }).join("");
  document.getElementById("legend").innerHTML =
    `<span class="legend-title">${form.label}</span>${rows}<span class="legend-row"><span class="swatch" style="background:${NO_DATA}"></span>no data / water</span>`;
}

function syncModeControl() {
  const disabled = !LAYERS[state.layerKey].count;
  document.querySelectorAll('#show-as input[name="show-as"]').forEach((el) => (el.disabled = disabled));
  document.getElementById("show-as").classList.toggle("dimmed", disabled);
}

function redraw() {
  state.tractLayer.setStyle(styleFeature);
  renderLegend();
  syncModeControl();
}

async function boot() {
  const [cfg, dc, md, va, centersFC, hospitalsFC, manifest] = await Promise.all([
    loadJSON("data/site_config.json"),
    loadJSON("data/tracts_dc.geojson"), loadJSON("data/tracts_md.geojson"), loadJSON("data/tracts_va.geojson"),
    loadJSON("data/cooling_centers.geojson"), loadJSON("data/hospitals.geojson"),
    loadJSON("data/manifest.json"),
  ]);
  state.cfg = cfg;
  renderFreshness(manifest);
  renderKnownLimitations();

  // Interpolate config values into the underserved definition — never hardcode thresholds in prose.
  document.getElementById("underserved-help-text").textContent =
    `Highlighted tracts are ${state.cfg.gap_distance_km} km or more from every listed cooling center ` +
    `AND are home to at least ${state.cfg.gap_min_affected.toLocaleString("en-US")} people with 3 or more ` +
    `heat-vulnerability risk factors (Census CRE-Heat estimate). These are the areas where a new cooling ` +
    `center would reach the most vulnerable people.`;

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
  document.getElementById("layer-select").addEventListener("change", (e) => {
    state.layerKey = e.target.value; redraw();
  });
  document.querySelectorAll('#show-as input[name="show-as"]').forEach((el) =>
    el.addEventListener("change", () => { state.mode = el.value; redraw(); }));
  document.getElementById("show-centers").addEventListener("change", (e) =>
    e.target.checked ? state.centersLayer.addTo(state.map) : state.centersLayer.remove());
  document.getElementById("show-hospitals").addEventListener("change", (e) =>
    e.target.checked ? state.hospitalsLayer.addTo(state.map) : state.hospitalsLayer.remove());
  document.getElementById("only-gaps").addEventListener("change", (e) => { state.onlyGaps = e.target.checked; redraw(); });
  renderLegend();
  syncModeControl();
}

boot().catch((err) => {
  document.getElementById("tract-info").textContent = `Failed to load data: ${err.message}`;
  throw err;
});
