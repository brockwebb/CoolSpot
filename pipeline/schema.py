"""Cooling-center record schema. Invalid records are quarantined, never dropped."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

REQUIRED_FIELDS = ("id", "name", "address", "city", "state", "jurisdiction", "source_url", "retrieved_date")
VALID_STATES = {"DC", "MD", "VA"}
VALID_SOURCE_TYPES = {"listed", "designated"}
# Continental-US sanity window; catches null-island and swapped coords.
LAT_RANGE, LON_RANGE = (17.0, 50.0), (-130.0, -60.0)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_record(rec: dict) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        v = rec.get(f)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"missing or empty required field: {f}")
    if rec.get("state") and rec["state"] not in VALID_STATES:
        errs.append(f"state not in {sorted(VALID_STATES)}: {rec['state']}")
    if not str(rec.get("source_url", "")).startswith("http"):
        errs.append("source_url must start with http")
    rd = rec.get("retrieved_date", "")
    if isinstance(rd, str) and rd and not DATE_RE.match(rd):
        errs.append(f"retrieved_date not ISO YYYY-MM-DD: {rd}")
    if ("lat" in rec) != ("lon" in rec):
        errs.append("lat/lon must be present together")
    if "lat" in rec and "lon" in rec:
        try:
            lat, lon = float(rec["lat"]), float(rec["lon"])
            if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1]) or not (LON_RANGE[0] <= lon <= LON_RANGE[1]):
                errs.append(f"lat/lon outside plausible range: {lat},{lon}")
        except (TypeError, ValueError):
            errs.append(f"lat/lon not numeric: {rec.get('lat')},{rec.get('lon')}")
    st = rec.get("source_type")
    if st is not None and st not in VALID_SOURCE_TYPES:
        errs.append(f"source_type not in {sorted(VALID_SOURCE_TYPES)}: {st}")
    return errs


def partition_records(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    valid, invalid = [], []
    for rec in recs:
        errs = validate_record(rec)
        if errs:
            invalid.append({**rec, "_errors": errs})
        else:
            valid.append(rec)
    return valid, invalid


def write_quarantine(invalid: list[dict], reason: str, out_dir: Path) -> Path | None:
    if not invalid:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{reason}_{date.today().isoformat()}.json"
    path.write_text(json.dumps(invalid, indent=2))
    print(f"!! QUARANTINE: {len(invalid)} record(s) failed validation -> {path}")
    return path
