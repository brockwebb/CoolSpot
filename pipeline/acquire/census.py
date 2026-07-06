"""CRE-Heat 2022 and LACE 2023 tract CSVs (download-only products, not on the API)."""
from __future__ import annotations

import csv
import json
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


ACS_SENTINEL_FLOOR = -222222222  # ACS uses large negative codes for N/A


def fetch_acs(endpoint: str, get_vars: list[str], state_fips: str, api_key: str, timeout: int) -> list[list[str]]:
    params = {
        "get": ",".join(["NAME"] + get_vars),
        "for": "tract:*",
        "in": [f"state:{state_fips}", "county:*"],
        "key": api_key,
    }
    r = requests.get(endpoint, params=params, timeout=timeout)
    r.raise_for_status()
    if not r.text.strip():
        raise RuntimeError(
            f"Empty ACS response from {endpoint} for state {state_fips} — "
            "usually an invalid/missing CENSUS_API_KEY (the API now requires one)."
        )
    return r.json()


def acs_rows_to_dict(rows: list[list[str]]) -> dict[str, dict[str, str]]:
    header, out = rows[0], {}
    for row in rows[1:]:
        d = dict(zip(header, row))
        out[d["state"] + d["county"] + d["tract"]] = d
    return out


def _acs_int(d: dict, var: str) -> int | None:
    v = d.get(var)
    if v is None or v == "":
        return None
    n = int(float(v))
    return None if n <= ACS_SENTINEL_FLOOR else n


def _pct(num: int | None, denom: int | None) -> float | None:
    if num is None or not denom:
        return None
    return round(100.0 * num / denom, 1)


def acs_attrs(detailed: dict, subject: dict) -> dict:
    return {
        "pop_total": _acs_int(detailed, "B01003_001E"),
        "pop_65plus": _acs_int(subject, "S0101_C01_030E"),
        "pop_65_alone": _acs_int(detailed, "B09021_023E"),
        "pct_poverty": _pct(_acs_int(detailed, "B17001_002E"), _acs_int(detailed, "B17001_001E")),
        "pct_no_vehicle": _pct(_acs_int(detailed, "B08201_002E"), _acs_int(detailed, "B08201_001E")),
        "pct_disability": _pct(_acs_int(subject, "S1810_C02_001E"), _acs_int(subject, "S1810_C01_001E")),
    }


def run(cfg: dict) -> None:
    from pipeline.config import require_env
    timeout = cfg["publish"]["request_timeout_s"]
    download_csv(cfg["census"]["cre_heat_tract_url"], RAW_DIR / "CRE22_Heat_Tract.csv", timeout)
    download_csv(cfg["census"]["lace_tract_url"], RAW_DIR / "LACE_23_Tract.csv", timeout)
    api_key = require_env("CENSUS_API_KEY")
    acs = cfg["census"]["acs"]
    for st in cfg["states"]:
        dest = RAW_DIR / f"acs_{st['abbr'].lower()}.json"
        if dest.exists():
            print(f"cached: {dest.name}")
            continue
        payload = {
            "detailed": fetch_acs(acs["detailed_endpoint"], acs["detailed_vars"], st["fips"], api_key, timeout),
            "subject": fetch_acs(acs["subject_endpoint"], acs["subject_vars"], st["fips"], api_key, timeout),
        }
        dest.write_text(json.dumps(payload))
        print(f"downloaded: {dest.name}")
