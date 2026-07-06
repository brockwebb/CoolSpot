"""Collect cooling-center records from all jurisdiction adapters.
A failing source fails the whole stage (fail loud) — a heat-relief site
silently missing a jurisdiction is worse than a visibly broken build."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pipeline.acquire.cooling import baltimore, dc, md, md_counties, va
from pipeline.config import PROJECT_ROOT
from pipeline.schema import partition_records, write_quarantine

PENDING_PATH = PROJECT_ROOT / "data" / "raw" / "cooling_centers_pending.json"
QUARANTINE_DIR = PROJECT_ROOT / "data" / "quarantine"


def _fetch_dc(cfg: dict, timeout: int, retrieved: str) -> list[dict]:
    return dc.parse(dc.fetch(cfg, timeout), retrieved, cfg["cooling_sources"]["dc"]["source_page"])


def _fetch_va(cfg: dict, timeout: int, retrieved: str) -> list[dict]:
    return va.parse(va.fetch(cfg, timeout), retrieved, cfg["cooling_sources"]["va"]["source_page"])


def _fetch_md(cfg: dict, timeout: int, retrieved: str) -> list[dict]:
    recs = md.parse_pg(md.fetch_pg(cfg, timeout), retrieved)
    registry = md.parse_hub(md.fetch_hub(cfg, timeout), retrieved)
    md.write_registry(registry, PROJECT_ROOT / "data" / "sources" / "md_county_registry.json")
    import requests
    for county_key, url in cfg["cooling_sources"]["md"]["county_pages"].items():
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "CoolSpot/0.1 (public heat-relief project)"})
        r.raise_for_status()
        recs.extend(md_counties.parse_county(county_key, r.text, retrieved, url))
    recs.extend(baltimore.parse_libraries(baltimore.fetch_libraries(cfg, timeout), retrieved))
    recs.extend(baltimore.parse_seniors(baltimore.fetch_seniors(cfg, timeout), retrieved))
    return recs


DEFAULT_FETCHERS = {"dc": _fetch_dc, "va": _fetch_va, "md": _fetch_md}


def collect(cfg: dict, timeout: int, retrieved: str, fetchers=None) -> list[dict]:
    records: list[dict] = []
    for name, fn in (fetchers or DEFAULT_FETCHERS).items():
        print(f"--> cooling centers: {name}")
        try:
            got = fn(cfg, timeout, retrieved)
        except Exception:
            print(f"!! FAILED jurisdiction '{name}' — pipeline stops (fail loud).")
            raise
        print(f"    {len(got)} records")
        for rec in got:
            rec.setdefault("source_type", "listed")  # designation adapters set "designated" themselves
        records.extend(got)
    return records


def run(cfg: dict) -> None:
    timeout = cfg["publish"]["request_timeout_s"]
    records = collect(cfg, timeout, date.today().isoformat())
    valid, invalid = partition_records(records)
    write_quarantine(invalid, "cooling_scrape", QUARANTINE_DIR)
    counts: dict[str, int] = {}
    for r in valid:
        counts[r["jurisdiction"]] = counts.get(r["jurisdiction"], 0) + 1
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps({"records": valid, "by_jurisdiction_counts": counts}, indent=2))
    print(f"pending: {len(valid)} valid records {counts}; {len(invalid)} quarantined")
