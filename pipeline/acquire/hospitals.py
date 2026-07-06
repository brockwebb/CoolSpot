"""Hospitals: HealthData.gov geocoded roster (anag-cw7u) + CMS (xubh-q36u) CCN enrichment.
Roster geocodes frozen 2024-05 (reporting mandate ended); CMS join supplies currency."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import requests

from pipeline.config import PROJECT_ROOT

SOURCE_URL = "https://healthdata.gov/Hospital/COVID-19-Reported-Patient-Impact-and-Hospital-Capa/anag-cw7u"
SELECT_FIELDS = ("hospital_pk,hospital_name,address,city,state,zip,"
                 "fips_code,hospital_subtype,geocoded_hospital_address")


def fetch_healthdata(url: str, states: list[str], timeout: int) -> list[dict]:
    quoted = ",".join(f"'{s}'" for s in states)
    params = {"$select": f"distinct {SELECT_FIELDS}", "$where": f"state in({quoted})", "$limit": 5000}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f"HealthData.gov returned 0 hospitals for {states} — endpoint changed?")
    return rows


def fetch_cms_index(url: str, page_size: int, timeout: int) -> dict[str, dict]:
    index, offset = {}, 0
    while True:
        r = requests.get(url, params={"limit": page_size, "offset": offset}, timeout=timeout)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            break
        for row in results:
            index[row["facility_id"]] = {
                "hospital_type": row.get("hospital_type"),
                "emergency_services": row.get("emergency_services"),
            }
        offset += page_size
    if not index:
        raise RuntimeError("CMS hospital index came back empty — check cms_url/pagination.")
    return index


def hospital_features(rows: list[dict], cms: dict[str, dict], retrieved: str) -> tuple[list[dict], list[dict]]:
    feats, skipped = [], []
    for row in rows:
        point = row.get("geocoded_hospital_address")
        if not point or "coordinates" not in point:
            skipped.append(row)
            continue
        ccn = row.get("hospital_pk", "")
        enrich = cms.get(ccn, {})
        es = enrich.get("emergency_services")
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": point["coordinates"]},
            "properties": {
                "name": row.get("hospital_name", "").title(),
                "address": row.get("address", "").title(),
                "city": row.get("city", "").title(),
                "state": row.get("state"),
                "zip": row.get("zip"),
                "subtype": row.get("hospital_subtype"),
                "ccn": ccn,
                "hospital_type": enrich.get("hospital_type"),
                "emergency_services": None if es is None else es.strip().lower() == "yes",
                "source_url": SOURCE_URL,
                "retrieved_date": retrieved,
            },
        })
    return feats, skipped


def run(cfg: dict) -> None:
    timeout = cfg["publish"]["request_timeout_s"]
    states = [s["abbr"] for s in cfg["states"]]
    rows = fetch_healthdata(cfg["hospitals"]["healthdata_url"], states, timeout)
    cms = fetch_cms_index(cfg["hospitals"]["cms_url"], cfg["hospitals"]["cms_page_size"], timeout)
    feats, skipped = hospital_features(rows, cms, date.today().isoformat())
    if skipped:
        print(f"!! {len(skipped)} hospital rows lacked geocodes and were skipped (names: "
              f"{[r.get('hospital_name') for r in skipped]})")
    out = PROJECT_ROOT / cfg["publish"]["site_data_dir"] / "hospitals.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    print(f"wrote {out} ({len(feats)} hospitals)")
