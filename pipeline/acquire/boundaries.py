"""Cartographic boundary shapefiles -> rounded GeoJSON features (pyshp, no GDAL)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests
import shapefile


def download_and_extract(url: str, dest_dir: Path, timeout: int) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = url.rsplit("/", 1)[-1].removesuffix(".zip")
    shp = dest_dir / f"{stem}.shp"
    if shp.exists():
        print(f"cached: {shp.name}")
        return shp
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(dest_dir)
    if not shp.exists():
        raise RuntimeError(f"Expected {shp} inside {url}, found: {[p.name for p in dest_dir.iterdir()]}")
    return shp


def _round_coords(obj: list | tuple | float | int, precision: int) -> list | float | int:
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(c), precision) for c in obj]
        return [_round_coords(x, precision) for x in obj]
    return obj


def shapefile_to_features(shp_path: Path, precision: int) -> list[dict]:
    reader = shapefile.Reader(str(shp_path))
    geoid_idx = [f[0] for f in reader.fields[1:]].index("GEOID")
    feats = []
    for sr in reader.iterShapeRecords():
        geom = sr.shape.__geo_interface__
        feats.append({
            "type": "Feature",
            "properties": {"GEOID": sr.record[geoid_idx]},
            "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"], precision)},
        })
    return feats
