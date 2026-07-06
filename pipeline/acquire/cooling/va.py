"""VA cooling centers via VDH WP Store Locator JSON (data maintained by 211 Virginia).
WPSL caps results per query, so we sweep regional center points and dedupe on id."""
from __future__ import annotations

import requests


def fetch(cfg: dict, timeout: int) -> list[dict]:
    va = cfg["cooling_sources"]["va"]
    rows: list[dict] = []
    for lat, lng in va["sweep_points"]:
        r = requests.get(va["wpsl_url"], params={
            "action": "store_search", "lat": lat, "lng": lng,
            "max_results": va["max_results"], "search_radius": va["search_radius_miles"], "autoload": 1,
        }, timeout=timeout)
        r.raise_for_status()
        rows.extend(r.json())
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for row in rows:
        seen.setdefault(str(row.get("id")), row)
    return list(seen.values())


def parse(rows: list[dict], retrieved_date: str, source_url: str) -> list[dict]:
    recs = []
    for row in dedupe(rows):
        rec = {
            "id": f"va-{row.get('id')}",
            "name": (row.get("store") or "").strip(),
            "address": " ".join(x for x in [(row.get("address") or "").strip(), (row.get("address2") or "").strip()] if x),
            "city": (row.get("city") or "").strip(),
            "state": "VA",
            "zip": (row.get("zip") or "").strip(),
            "jurisdiction": "va",
            "hours": (row.get("hours") or "").strip(),
            "phone": (row.get("phone") or "").strip(),
            "url": (row.get("url") or "").strip(),
            "source_url": source_url,
            "retrieved_date": retrieved_date,
        }
        try:
            rec["lat"] = float(row.get("lat"))
            rec["lon"] = float(row.get("lng"))
        except (TypeError, ValueError):
            pass
        recs.append(rec)
    return recs
