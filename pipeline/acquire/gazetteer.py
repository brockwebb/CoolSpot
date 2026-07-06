"""Census Gazetteer place/county centers -> site/data/places.json for the finder's
place-name search. Places win over counties on match-key collision within a state."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import requests

from pipeline.config import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw"
# Place suffixes only — "county" is deliberately NOT stripped by match_key: counties are
# indexed under their county-keeping key plus a bare alias (see build_places), so a county
# never silently overwrites a same-named city (Franklin city vs Franklin County, VA).
SUFFIXES = ("cdp", "city", "town", "village", "borough", "municipality", "comunidad", "zona urbana")
DISPLAY_SUFFIXES = (" CDP", " city", " town", " village", " borough", " municipality")


def download_and_extract_txt(url: str, dest_dir: Path, timeout: int) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = url.rsplit("/", 1)[-1].removesuffix(".zip")
    txt = dest_dir / f"{stem}.txt"
    if txt.exists():
        print(f"cached: {txt.name}")
        return txt
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(dest_dir)
    if not txt.exists():
        raise RuntimeError(f"Expected {txt.name} inside {url}")
    return txt


def parse_gazetteer(text: str, states: set[str]) -> list[dict]:
    lines = text.splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = dict(zip(header, (v.strip() for v in line.split("\t"))))
        if vals.get("USPS") in states:
            rows.append(vals)
    return rows


def match_key(name: str) -> str:
    q = name.lower().replace("'", "").replace("'", "").replace(".", "")
    q = " ".join(q.split())
    for s in SUFFIXES:
        if q.endswith(" " + s):
            q = q[: -(len(s) + 1)]
            break
    return q.strip()


def display_name(name: str, state: str, is_county: bool) -> str:
    if not is_county:
        for s in DISPLAY_SUFFIXES:
            if name.endswith(s):
                name = name[: -len(s)]
                break
    return f"{name}, {state}"


def _entry(row: dict, is_county: bool) -> dict:
    return {
        "q": match_key(row["NAME"]),
        "display": display_name(row["NAME"], row["USPS"], is_county),
        "state": row["USPS"],
        "lat": round(float(row["INTPTLAT"]), 4),
        "lon": round(float(row["INTPTLONG"]), 4),
        "_aland": int(row["ALAND"]),
    }


def build_places(place_rows: list[dict], county_rows: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for row in place_rows:
        e = _entry(row, is_county=False)
        key = (e["q"], e["state"])
        if key not in best or e["_aland"] > best[key]["_aland"]:
            best[key] = e
    for row in county_rows:
        e = _entry(row, is_county=True)
        best.setdefault((e["q"], e["state"]), e)  # county-keeping key ("x county") or city twin
        if e["q"].endswith(" county"):
            alias = {**e, "q": e["q"][: -len(" county")].strip()}
            best.setdefault((alias["q"], alias["state"]), alias)  # bare alias; a place name wins
    out = sorted(({k: v for k, v in e.items() if k != "_aland"} for e in best.values()),
                 key=lambda e: (e["q"], e["state"]))
    if not out:
        raise RuntimeError("Gazetteer produced 0 places for the configured states — source format changed?")
    return out


def run(cfg: dict) -> None:
    timeout = cfg["publish"]["request_timeout_s"]
    states = {s["abbr"] for s in cfg["states"]}
    place_txt = download_and_extract_txt(cfg["census"]["gazetteer_place_url"], RAW_DIR / "gazetteer", timeout)
    county_txt = download_and_extract_txt(cfg["census"]["gazetteer_county_url"], RAW_DIR / "gazetteer", timeout)
    # Gazetteer files are latin-1-safe; utf-8 first, cp1252 fallback matches census.py's pattern.
    def read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            print(f"note: {p.name} decoded as cp1252 (not UTF-8)")
            return p.read_text(encoding="cp1252")
    places = build_places(parse_gazetteer(read(place_txt), states), parse_gazetteer(read(county_txt), states))
    out = PROJECT_ROOT / cfg["publish"]["site_data_dir"] / "places.json"
    out.write_text(json.dumps(places, separators=(",", ":")))
    print(f"wrote {out} ({len(places)} places)")
