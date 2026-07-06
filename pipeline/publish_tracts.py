"""Join CRE-Heat + LACE + ACS attributes onto tract boundaries; fail loud on bad joins."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.acquire import boundaries
from pipeline.acquire.census import (RAW_DIR, acs_attrs, acs_rows_to_dict,
                                     cre_heat_attrs, filter_state_rows, lace_attrs, tract_geoid)
from pipeline.config import PROJECT_ROOT


def build_state_geojson(features: list[dict], cre_by_geoid: dict[str, dict], lace_by_geoid: dict[str, dict], acs_by_geoid: dict[str, dict], min_match_rate: float) -> dict:
    matched = 0
    for f in features:
        geoid = f["properties"]["GEOID"]
        cre, lace, acs = cre_by_geoid.get(geoid), lace_by_geoid.get(geoid), acs_by_geoid.get(geoid)
        if cre and lace and acs:
            matched += 1
        for attrs in (cre, lace, acs):
            if attrs:
                f["properties"].update(attrs)
    rate = matched / len(features) if features else 0.0
    if rate < min_match_rate:
        raise RuntimeError(
            f"Tract attribute join match rate {rate:.3f} < required {min_match_rate} "
            f"({matched}/{len(features)}). Boundary vintage (GENZ2024) may not align with "
            "CRE-Heat/LACE 2020 tracts — investigate before publishing."
        )
    print(f"join match rate {rate:.3f} ({matched}/{len(features)})")
    return {"type": "FeatureCollection", "features": features}


def run(cfg: dict) -> None:
    pub = cfg["publish"]
    out_dir = PROJECT_ROOT / pub["site_data_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    fips_set = {s["fips"] for s in cfg["states"]}
    cre_rows = filter_state_rows(RAW_DIR / "CRE22_Heat_Tract.csv", fips_set)
    lace_rows = filter_state_rows(RAW_DIR / "LACE_23_Tract.csv", fips_set)
    cre_all = {tract_geoid(r): cre_heat_attrs(r) for r in cre_rows}
    lace_all = {tract_geoid(r): lace_attrs(r) for r in lace_rows}
    for st in cfg["states"]:
        url = cfg["census"]["boundaries_url_template"].format(fips=st["fips"])
        shp = boundaries.download_and_extract(url, RAW_DIR / f"cb_tract_{st['fips']}", pub["request_timeout_s"])
        feats = boundaries.shapefile_to_features(shp, pub["coord_precision"])
        raw = json.loads((RAW_DIR / f"acs_{st['abbr'].lower()}.json").read_text())
        det, sub = acs_rows_to_dict(raw["detailed"]), acs_rows_to_dict(raw["subject"])
        acs_all = {g: acs_attrs(det[g], sub.get(g, {})) for g in det}
        fc = build_state_geojson(feats, cre_all, lace_all, acs_all, pub["min_geoid_match_rate"])
        out = out_dir / f"tracts_{st['abbr'].lower()}.geojson"
        out.write_text(json.dumps(fc, separators=(",", ":")))
        print(f"wrote {out} ({out.stat().st_size:,} bytes, {len(feats)} tracts)")
