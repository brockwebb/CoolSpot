"""CRE-Heat 2022 and LACE 2023 tract CSVs (download-only products, not on the API)."""
from __future__ import annotations

import csv
from pathlib import Path

import requests

from pipeline.config import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw"
GEOID_PREFIX = "1400000US"


def download_csv(url: str, dest: Path, timeout: int) -> Path:
    if dest.exists():
        print(f"cached: {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    print(f"downloaded: {dest.name} ({dest.stat().st_size:,} bytes)")
    return dest


def filter_state_rows(csv_path: Path, state_fips: set[str]) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.DictReader(f) if row.get("STATE") in state_fips]


def tract_geoid(row: dict) -> str:
    geo_id = row["GEO_ID"]
    if not geo_id.startswith(GEOID_PREFIX):
        raise ValueError(f"Unexpected GEO_ID format: {geo_id}")
    return geo_id[len(GEOID_PREFIX):]


def _num(value: str | None, cast=float):
    """Census suppression/missing markers ('', '-999') -> None."""
    if value is None or value.strip() in ("", "-999", "-999.0", "N"):
        return None
    return cast(value)


def cre_heat_attrs(row: dict) -> dict:
    return {
        "pop": _num(row.get("POPUNI"), int),
        "pred3_e": _num(row.get("PRED3_E"), int),
        "pred3_pe": _num(row.get("PRED3_PE")),
        "exposed": _num(row.get("EXPOSED"), int),
    }


def lace_attrs(row: dict) -> dict:
    return {
        "hse_occ_e": _num(row.get("HSE_OCC_E"), int),
        "no_ac_e": _num(row.get("NO_AC_E"), int),
        "no_ac_pe": _num(row.get("NO_AC_PE")),
        "water_tract": _num(row.get("WATER_TRACT"), int),
    }


def run(cfg: dict) -> None:
    timeout = cfg["publish"]["request_timeout_s"]
    download_csv(cfg["census"]["cre_heat_tract_url"], RAW_DIR / "CRE22_Heat_Tract.csv", timeout)
    download_csv(cfg["census"]["lace_tract_url"], RAW_DIR / "LACE_23_Tract.csv", timeout)
