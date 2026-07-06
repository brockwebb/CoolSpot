"""Baltimore County: no published cooling-center list. The county DESIGNATES all public
library branches and senior centers as cooling sites during extreme-heat events
(baltimorecountymd.gov/departments/health/hot-weather). We assemble the list from the
facility directories; every record is source_type='designated' with that caveat. See
docs/superpowers/specs/2026-07-06-baltimore-designated-design.md.

Verification (2026-07-06, captured live): the hot-weather page's "public Cooling
locations" table has a "Baltimore County Public Library" row whose
Contact/Visiting Information column reads "All locations are open to the public"
(linking to bcpl.info/locations) — an unconditional designation of every branch.
The "Senior Centers" row links to the same aging/centers directory used here and
reads "Call <phone> to check locations are open to the public before you visit.
Visitors must register once at the center." — every center is in scope, but with a
narrower call-ahead/registration caveat than the library row, which SENIOR_CAVEAT
reflects.

Sources:
- Libraries: https://www.bcpl.info/locations — a single, fully server-rendered page
  (Drupal "teaser" cards, one per branch: name, street address, phone). No GIS/JSON
  layer with coordinates was found for BCPL branches, so records carry no lat/lon
  (geocoded downstream per pipeline/geocode.py), matching the other MD adapters.
- Senior centers: https://www.baltimorecountymd.gov/departments/aging/centers — a
  paginated Drupal view (10 results/page, 3 pages, "Displaying 23 results"). Of the
  23 rows, 3 are administrative/program listings sharing the Dept. of Aging HQ
  address (Cycling Seniors of Baltimore County, Online Programs for Adult Learning
  (OPAL), Senior Craft Gallery) rather than physical drop-in senior centers; these
  are filtered out (name must end in "Senior Center") rather than counted as
  cooling sites they are not."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

DESIGNATION_URL = "https://www.baltimorecountymd.gov/departments/health/hot-weather"
UA = "Mozilla/5.0 (compatible; CoolSpot/0.1; +https://github.com/brockwebb/CoolSpot)"
LIB_CAVEAT = "Designated cooling site during Baltimore County extreme-heat events — hours vary, call ahead."
SENIOR_CAVEAT = LIB_CAVEAT + " Primarily serves older adults."

# "<City>, Maryland <zip>" — the last stripped-string line in each directory's address block.
CITY_STATE_ZIP_RE = re.compile(r"^(?P<city>[^,]+),\s*Maryland\s*(?P<zip>\d{5})?", re.IGNORECASE)

# Senior-center rows include a handful of administrative/program listings (Cycling
# Seniors of Baltimore County, OPAL, Senior Craft Gallery) that share the Dept. of
# Aging HQ address rather than being physical drop-in centers; only true centers
# are in scope for a "designated cooling site" record.
SENIOR_CENTER_NAME_RE = re.compile(r"senior center$", re.IGNORECASE)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _record(kind: str, name: str, street: str, city: str, zc: str, directory_url: str,
            retrieved: str, caveat: str) -> dict:
    return {
        "id": f"md-baltimore-{kind}-{_slug(name)}",
        "name": name.strip(), "address": street.strip(), "city": city.strip() or "Baltimore",
        "state": "MD", "zip": zc or "", "jurisdiction": "md",
        "source_type": "designated",
        "source_url": DESIGNATION_URL,      # the authority that designates it a cooling site
        "url": directory_url,               # where the address came from
        "notes": caveat,
        "retrieved_date": retrieved,
    }


def _address_lines(container, label_keyword: str) -> list[str] | None:
    """Find the <p>/<address> block whose first strong/label mentions label_keyword
    and return its stripped text lines (label line included, dropped by caller)."""
    for el in container.find_all(["p", "address"]):
        label = el.find("strong") or el.find("h3")
        label_text = label.get_text(strip=True) if label else el.get_text(strip=True)
        if label_keyword.lower() in label_text.lower():
            return list(el.stripped_strings)
    return None


def fetch_libraries(cfg: dict, timeout: int):
    url = cfg["cooling_sources"]["md"]["baltimore"]["libraries_url"]
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text


def parse_libraries(raw, retrieved_date: str) -> list[dict]:
    # tests/fixtures/md_baltimore_libraries.html: one <article class="c-teaser
    # c-teaser--location"> per branch, with an <h2.c-teaser__title> name and an
    # <address.c-teaser__address> block of "Address" / "<street>" / "<city>,
    # Maryland <zip>" lines (occasionally an extra suite/floor line in between).
    soup = BeautifulSoup(raw, "html.parser")
    directory_url = "https://www.bcpl.info/locations"
    recs: list[dict] = []
    articles = soup.select("article.c-teaser--location")
    if not articles:
        print("!! baltimore[libraries]: no branch cards found — page structure may have changed")
        return recs
    for art in articles:
        title_el = art.select_one("h2.c-teaser__title")
        name = title_el.get_text(strip=True) if title_el else ""
        addr_el = art.select_one("address.c-teaser__address")
        if not name or addr_el is None:
            print(f"!! baltimore[libraries]: skipped card with missing name/address: {art.get_text(' ', strip=True)[:80]!r}")
            continue
        lines = [l for l in addr_el.stripped_strings if l.lower() != "address"]
        if len(lines) < 2:
            print(f"!! baltimore[libraries]: skipped unparseable address for {name!r}: {lines!r}")
            continue
        street = ", ".join(lines[:-1])
        m = CITY_STATE_ZIP_RE.match(lines[-1])
        if not m:
            print(f"!! baltimore[libraries]: skipped unparseable city/zip line for {name!r}: {lines[-1]!r}")
            continue
        recs.append(_record("lib", name, street, m.group("city"), m.group("zip") or "",
                             directory_url, retrieved_date, LIB_CAVEAT))
    return recs


def fetch_seniors(cfg: dict, timeout: int):
    url = cfg["cooling_sources"]["md"]["baltimore"]["seniors_url"]
    pages = []
    # Drupal view is paginated 10/page; the directory reports "Displaying 23
    # results" across 3 pages (?page=0 implicit, ?page=1, ?page=2).
    for page in range(3):
        page_url = url if page == 0 else f"{url}?page={page}"
        r = requests.get(page_url, timeout=timeout, headers={"User-Agent": UA})
        r.raise_for_status()
        pages.append(r.text)
    return "\n".join(pages)


def parse_seniors(raw, retrieved_date: str) -> list[dict]:
    # tests/fixtures/md_baltimore_seniors.html: concatenation of the directory's
    # paginated pages, each <article class="c-teaser"> (name in h2.c-teaser__title,
    # address in a <p><strong>Address:</strong> ...</p> block). Non-center program
    # rows (name doesn't end in "Senior Center") are intentionally filtered, not
    # a parse failure.
    soup = BeautifulSoup(raw, "html.parser")
    directory_url = "https://www.baltimorecountymd.gov/departments/aging/centers"
    recs: list[dict] = []
    articles = soup.select("article.c-teaser")
    if not articles:
        print("!! baltimore[seniors]: no center cards found — page structure may have changed")
        return recs
    for art in articles:
        title_el = art.select_one("h2.c-teaser__title")
        name = title_el.get_text(strip=True) if title_el else ""
        if not name:
            print(f"!! baltimore[seniors]: skipped card with no name: {art.get_text(' ', strip=True)[:80]!r}")
            continue
        if not SENIOR_CENTER_NAME_RE.search(name):
            print(f"-- baltimore[seniors]: filtering non-center program listing: {name!r}")
            continue
        lines = _address_lines(art, "address")
        if not lines:
            print(f"!! baltimore[seniors]: skipped unparseable address for {name!r}")
            continue
        lines = [l for l in lines if "address" not in l.lower()]
        if len(lines) < 2:
            print(f"!! baltimore[seniors]: skipped unparseable address for {name!r}: {lines!r}")
            continue
        street = ", ".join(lines[:-1])
        m = CITY_STATE_ZIP_RE.match(lines[-1])
        if not m:
            print(f"!! baltimore[seniors]: skipped unparseable city/zip line for {name!r}: {lines[-1]!r}")
            continue
        recs.append(_record("senior", name, street, m.group("city"), m.group("zip") or "",
                             directory_url, retrieved_date, SENIOR_CAVEAT))
    return recs
