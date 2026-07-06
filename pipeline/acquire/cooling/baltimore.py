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

# A branch/center taken offline (e.g. "CLOSED FOR RENOVATION") must never be published
# as an available cooling site — publishing a closed location during a heat emergency
# is a safety hazard, not a data-quality nit. Case-insensitive so it also catches
# "Closed", "Temporarily closed", etc. Re-checked on every run, so a branch reappears
# automatically once the source drops the notice.
CLOSED_RE = re.compile(r"\bclosed\b", re.IGNORECASE)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _is_closed(name: str, lines: list[str]) -> bool:
    return bool(CLOSED_RE.search(name)) or any(CLOSED_RE.search(l) for l in lines)


def _record(kind: str, name: str, street: str, city: str, zc: str, directory_url: str,
            retrieved: str, caveat: str, phone: str = "") -> dict:
    return {
        "id": f"md-baltimore-{kind}-{_slug(name)}",
        "name": name.strip(), "address": street.strip(), "city": city.strip() or "Baltimore",
        "state": "MD", "zip": zc or "", "jurisdiction": "md",
        "source_type": "designated",
        "source_url": DESIGNATION_URL,      # the authority that designates it a cooling site
        "url": directory_url,               # where the address came from
        "phone": phone.strip(),
        "notes": caveat,
        "retrieved_date": retrieved,
    }


def _extract_phone(container) -> str:
    """Best-effort phone extraction from a facility card's tel: link. Returns "" (not
    fabricated) if the source card carries no phone — some facilities genuinely omit one."""
    tel = container.select_one('a[href^="tel:"]')
    if tel is None:
        return ""
    return tel.get_text(strip=True)


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
        if _is_closed(name, lines):
            print(f"!! baltimore: skipping closed facility: {name!r}")
            continue
        if len(lines) < 2:
            print(f"!! baltimore[libraries]: skipped unparseable address for {name!r}: {lines!r}")
            continue
        street = ", ".join(lines[:-1])
        m = CITY_STATE_ZIP_RE.match(lines[-1])
        if not m:
            print(f"!! baltimore[libraries]: skipped unparseable city/zip line for {name!r}: {lines[-1]!r}")
            continue
        # The source never disambiguates branches from same-named senior centers, and a
        # bare branch name ("Arbutus") is unclear on a public finder — append "Library".
        # The id slug is derived from this same enriched name (e.g. md-baltimore-lib-
        # arbutus-library); that's a one-time, cosmetic slug change, not worth threading
        # a separate id-vs-display-name parameter through _record for.
        phone = _extract_phone(art)
        recs.append(_record("lib", f"{name} Library", street, m.group("city"), m.group("zip") or "",
                             directory_url, retrieved_date, LIB_CAVEAT, phone))
    if not recs:
        raise RuntimeError("baltimore[libraries]: 0 records parsed — source structure changed?")
    return recs


# Safety cap on how many senior-center directory pages we'll fetch before giving up.
# The directory currently reports ~23 results over 3 pages (10/page); this cap is
# generous headroom, not a tuned expectation — if the county's listing grows past this
# many pages, fetch_seniors raises RuntimeError rather than silently truncating.
SENIORS_MAX_PAGES = 10


def _page_result_info(html: str) -> tuple[int, int | None]:
    """Pure helper (testable against a fixture page) for one directory page: how many
    center/program cards it contains, and the "Displaying N results" total it reports
    (None if that header isn't present on the page)."""
    soup = BeautifulSoup(html, "html.parser")
    row_count = len(soup.select("article.c-teaser"))
    m = re.search(r"Displaying\s+(\d+)\s+results", html)
    total = int(m.group(1)) if m else None
    return row_count, total


def fetch_seniors(cfg: dict, timeout: int):
    url = cfg["cooling_sources"]["md"]["baltimore"]["seniors_url"]
    pages: list[str] = []
    fetched_rows = 0
    total_expected: int | None = None
    for page in range(SENIORS_MAX_PAGES):
        page_url = url if page == 0 else f"{url}?page={page}"
        r = requests.get(page_url, timeout=timeout, headers={"User-Agent": UA})
        r.raise_for_status()
        html = r.text
        pages.append(html)
        row_count, page_total = _page_result_info(html)
        if total_expected is None:
            total_expected = page_total
        fetched_rows += row_count
        # Stop once a page comes back with no rows (past the last real page), or once
        # we've collected at least as many rows as the directory's own "Displaying N
        # results" header claims exist. Self-terminating: it adapts if the county adds
        # or removes a page instead of silently truncating at a hardcoded page count.
        if row_count == 0 or (total_expected is not None and fetched_rows >= total_expected):
            break
    else:
        raise RuntimeError(
            f"baltimore[seniors]: hit the {SENIORS_MAX_PAGES}-page safety cap with only "
            f"{fetched_rows}/{total_expected!r} results fetched — directory may have grown; "
            "raise SENIORS_MAX_PAGES or investigate."
        )
    if total_expected is not None and fetched_rows < total_expected:
        raise RuntimeError(
            f"baltimore[seniors]: expected {total_expected} results per directory header but "
            f"only fetched {fetched_rows} across {len(pages)} page(s)."
        )
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
        if _is_closed(name, lines):
            print(f"!! baltimore: skipping closed facility: {name!r}")
            continue
        if len(lines) < 2:
            print(f"!! baltimore[seniors]: skipped unparseable address for {name!r}: {lines!r}")
            continue
        street = ", ".join(lines[:-1])
        m = CITY_STATE_ZIP_RE.match(lines[-1])
        if not m:
            print(f"!! baltimore[seniors]: skipped unparseable city/zip line for {name!r}: {lines[-1]!r}")
            continue
        phone = _extract_phone(art)
        recs.append(_record("senior", name, street, m.group("city"), m.group("zip") or "",
                             directory_url, retrieved_date, SENIOR_CAVEAT, phone))
    if not recs:
        raise RuntimeError("baltimore[seniors]: 0 records parsed — source structure changed?")
    return recs
