"""Maryland: no statewide dataset exists (verified 2026-07-05). Strategy:
1. PG County ArcGIS MapServer (structured, easy).
2. MDH hub page -> per-county registry (contact + links), committed for review.
3. Per-county HTML adapters for top counties (Task 10).
The MDH hub URL is year-stamped; update config each season."""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MD_ADDR_RE = re.compile(r"^(?P<street>.*?),\s*(?P<city>[^,]+),\s*MD\s*(?P<zip>\d{5})?", re.IGNORECASE)
PG_SOURCE = "https://princegeorges.maps.arcgis.com/apps/webappviewer/index.html?id=6c7090a859d54539976fcfcc4dc874bf"


def fetch_pg(cfg: dict, timeout: int) -> dict:
    r = requests.get(cfg["cooling_sources"]["md"]["pg_arcgis_query_url"],
                     params={"where": "1=1", "outFields": "*", "f": "json", "outSR": 4326}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"PG County ArcGIS error: {data['error']}")
    return data


def parse_pg(raw: dict, retrieved_date: str) -> list[dict]:
    recs = []
    for feat in raw.get("features", []):
        a, g = feat.get("attributes", {}), feat.get("geometry", {})
        full = (a.get("Address") or "").strip()
        m = MD_ADDR_RE.match(full)
        if m:
            street, city, zc = m.group("street"), m.group("city").strip(), m.group("zip") or ""
            notes = ""
        else:
            street, city, zc = full, "Prince George's County", ""
            notes = "city inferred; address not split"
        rec = {
            "id": f"md-pg-{a.get('OBJECTID')}",
            "name": (a.get("Name") or "").strip(),
            "address": street, "city": city, "state": "MD", "zip": zc,
            "jurisdiction": "md",
            "hours": (a.get("Hours") or "").strip(),
            "phone": (a.get("Phone") or "").strip(),
            "notes": notes,
            "source_url": PG_SOURCE,
            "retrieved_date": retrieved_date,
        }
        if g.get("x") is not None and g.get("y") is not None:
            rec["lon"], rec["lat"] = float(g["x"]), float(g["y"])
        recs.append(rec)
    return recs


def fetch_hub(cfg: dict, timeout: int) -> str:
    r = requests.get(cfg["cooling_sources"]["md"]["hub_url"], timeout=timeout,
                     headers={"User-Agent": "CoolSpot/0.1 (public heat-relief project)"})
    r.raise_for_status()
    return r.text


def parse_hub(html: str, retrieved_date: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for tr in soup.select("table tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        county = cells[0].get_text(strip=True)
        if not county:
            continue
        # Skip header row: "County / City" text or no links + "Main Phone number"
        links = [a["href"] for c in cells for a in c.find_all("a", href=True)]
        if "County / City" in county or (not links and "Main" in cells[1].get_text()):
            continue
        entries.append({
            "county": county,
            "phone": cells[1].get_text(strip=True),
            "links": links,
            "retrieved_date": retrieved_date,
        })
    if not entries:
        raise RuntimeError("MDH hub page parsed to 0 counties — page structure changed (year-stamped URL?)")
    return entries


def write_registry(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))
    print(f"wrote MD county registry: {path} ({len(entries)} counties)")
