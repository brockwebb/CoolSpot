"""DC HSEMA cooling centers via ArcGIS feature service (layer 1 — layer 0 does not exist)."""
from __future__ import annotations

import re

import requests

QUERY_PARAMS = {"where": "1=1", "outFields": "*", "f": "geojson"}
ADDR_RE = re.compile(r"^(?P<street>.*?),\s*(?P<city>[^,]+),\s*DC\s*(?P<zip>\d{5})?", re.IGNORECASE)


def fetch(cfg: dict, timeout: int) -> dict:
    r = requests.get(cfg["cooling_sources"]["dc"]["arcgis_query_url"], params=QUERY_PARAMS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def parse(raw: dict, retrieved_date: str) -> list[dict]:
    recs = []
    for feat in raw.get("features", []):
        p = feat.get("properties", {})
        coords = (feat.get("geometry") or {}).get("coordinates")
        full_addr = (p.get("USER_Address") or "").strip()
        m = ADDR_RE.match(full_addr)
        if m:
            street, city, zc = m.group("street"), m.group("city").strip(), m.group("zip") or ""
        else:
            street, city, zc = full_addr, "Washington", ""
        rec = {
            "id": f"dc-{feat.get('id')}",
            "name": (p.get("USER_Name") or "").strip(),
            "address": street,
            "city": city,
            "state": "DC",
            "zip": zc,
            "jurisdiction": "dc",
            "hours": p.get("USER_Hours") or "",
            "phone": p.get("USER_Phone") or "",
            "url": p.get("USER_Url") or "",
            "status": p.get("USER_Status") or "",
            "notes": f"Open to: {p.get('USER_Open_To')}" if p.get("USER_Open_To") else "",
            "source_url": "https://opendata.dc.gov/datasets/9ee42555df88442fb357d77147bfdca3",
            "retrieved_date": retrieved_date,
        }
        if coords:
            rec["lon"], rec["lat"] = float(coords[0]), float(coords[1])
        recs.append(rec)
    return recs
