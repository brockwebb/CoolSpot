"""Publish cooling centers, coverage-gap annotations, manifest, and site config."""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from pipeline import publish_tracts
from pipeline.config import PROJECT_ROOT
from pipeline.geocode import GEOCODED_PATH


def to_feature(rec: dict) -> dict:
    props = {k: v for k, v in rec.items() if k not in ("lat", "lon")}
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]},
            "properties": props}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _rings(geom: dict):
    if geom["type"] == "Polygon":
        yield geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly[0]


def centroid(feature: dict) -> tuple[float, float]:
    xs, ys, n = 0.0, 0.0, 0
    for ring in _rings(feature["geometry"]):
        for lon, lat in ring:
            xs, ys, n = xs + lon, ys + lat, n + 1
    return ys / n, xs / n


def add_gap_distances(tract_fc: dict, center_points: list[tuple[float, float]]) -> None:
    for f in tract_fc["features"]:
        lat, lon = centroid(f)
        best = min((haversine_km(lat, lon, clat, clon) for clat, clon in center_points), default=None)
        f["properties"]["nearest_cc_km"] = round(best, 1) if best is not None else None


def jurisdiction_summary(records: list[dict]) -> dict[str, dict]:
    """Aggregate records by jurisdiction, collecting all unique source URLs."""
    juris: dict[str, dict] = {}
    for r in records:
        j = juris.setdefault(r["jurisdiction"], {"count": 0, "retrieved_date": r["retrieved_date"],
                                                 "source_urls": []})
        j["count"] += 1
        if r["source_url"] not in j["source_urls"]:
            j["source_urls"].append(r["source_url"])
    return juris


def run(cfg: dict) -> None:
    out_dir = PROJECT_ROOT / cfg["publish"]["site_data_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    publish_tracts.run(cfg)

    records = json.loads(GEOCODED_PATH.read_text())["records"]
    feats = [to_feature(r) for r in records]
    (out_dir / "cooling_centers.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    print(f"wrote cooling_centers.geojson ({len(feats)} centers)")

    center_points = [(r["lat"], r["lon"]) for r in records]
    for st in cfg["states"]:
        p = out_dir / f"tracts_{st['abbr'].lower()}.geojson"
        fc = json.loads(p.read_text())
        add_gap_distances(fc, center_points)
        p.write_text(json.dumps(fc, separators=(",", ":")))
    print("annotated tract files with nearest_cc_km")

    juris = jurisdiction_summary(records)
    hosp_count = len(json.loads((out_dir / "hospitals.geojson").read_text())["features"])
    (out_dir / "manifest.json").write_text(json.dumps({
        "generated": date.today().isoformat(),
        "jurisdictions": juris,
        "hospitals": {"count": hosp_count,
                      "roster_note": "coordinate roster frozen May 2024; attributes current via CMS"},
    }, indent=2))

    (out_dir / "site_config.json").write_text(json.dumps({
        "nearest_n": cfg["publish"]["nearest_n"],
        "gap_distance_km": cfg["publish"]["gap_distance_km"],
        "map_center": cfg["publish"]["map_center"],
        "map_zoom": cfg["publish"]["map_zoom"],
        "fallback_areas": cfg["publish"]["fallback_areas"],
    }, indent=2))
    print("wrote manifest.json and site_config.json")
