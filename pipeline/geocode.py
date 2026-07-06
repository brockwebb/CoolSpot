"""Census batch geocoder for scraped records lacking coordinates.
Batch limit 10k rows (we are far below). Unmatched records are quarantined."""
from __future__ import annotations

import csv
import io
import json

import requests

from pipeline.config import PROJECT_ROOT
from pipeline.schema import write_quarantine

PENDING_PATH = PROJECT_ROOT / "data" / "raw" / "cooling_centers_pending.json"
GEOCODED_PATH = PROJECT_ROOT / "data" / "raw" / "cooling_centers_geocoded.json"
QUARANTINE_DIR = PROJECT_ROOT / "data" / "quarantine"


def build_batch_csv(records: list[dict]) -> str:
    """CSV rows `id,street,city,state,zip` for records lacking coordinates.
    Default csv quoting (only-when-needed) is accepted by the geocoder."""
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in records:
        if "lat" not in r:
            w.writerow([r["id"], r["address"], r["city"], r["state"], r.get("zip", "")])
    return buf.getvalue()


def parse_batch_response(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 6 and row[2] == "Match":
            lon_s, lat_s = row[5].split(",")
            out[row[0]] = {"lat": float(lat_s), "lon": float(lon_s), "geocode_quality": row[3]}
    return out


def apply_geocodes(records: list[dict], geocodes: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    located, unlocated = [], []
    for r in records:
        if "lat" in r:
            located.append(r)
        elif r["id"] in geocodes:
            located.append({**r, **geocodes[r["id"]]})
        else:
            unlocated.append(r)
    return located, unlocated


def run(cfg: dict) -> None:
    if not PENDING_PATH.is_file():
        raise RuntimeError(
            f"{PENDING_PATH} not found — run `coolspot acquire-cooling` before `coolspot geocode`."
        )
    pending = json.loads(PENDING_PATH.read_text())["records"]
    need = [r for r in pending if "lat" not in r]
    geocodes: dict[str, dict] = {}
    if need:
        csv_text = build_batch_csv(pending)
        resp = requests.post(
            cfg["geocoder"]["batch_url"],
            files={"addressFile": ("addresses.csv", csv_text, "text/csv")},
            data={"benchmark": cfg["geocoder"]["benchmark"]},
            timeout=cfg["publish"]["request_timeout_s"] * 3,
        )
        resp.raise_for_status()
        geocodes = parse_batch_response(resp.text)
    located, unlocated = apply_geocodes(pending, geocodes)
    write_quarantine(unlocated, "geocode_failed", QUARANTINE_DIR)
    GEOCODED_PATH.write_text(json.dumps({"records": located}, indent=2))
    print(f"geocoded: {len(located)} located ({len(need)} needed geocoding), {len(unlocated)} quarantined")
