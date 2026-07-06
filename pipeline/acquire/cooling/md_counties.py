"""Per-county MD HTML adapters. Each parser is written against a captured fixture
(tests/fixtures/md_{county}.html); when a county redesigns its page the fixture
test fails rather than publishing garbage. Records here have no lat/lon —
they are geocoded by pipeline/geocode.py.

Baltimore County was captured (tests/fixtures/md_baltimore_county.html) and
inspected but has NO parser here: its hot-weather page lists only category
descriptions (public library system, recreation centers, senior centers)
with a "check locations" link or phone number for each — no scrapeable
per-center addresses on the page itself. This county was dropped rather than
faking records; see data/sources/md_county_registry.json (review_note) and
the README "Deferred / known gaps" section for the gap note."""
from __future__ import annotations

import re
from typing import Callable

from bs4 import BeautifulSoup

ADDR_LINE_RE = re.compile(
    r"(?P<street>\d[\w\s.\-#/]*?),?\s+(?P<city>[A-Z][A-Za-z .'-]+),?\s+(?:MD|Maryland)\.?\s*(?P<zip>\d{5})?")

# Anne Arundel's location links read "Name: Street, City" with no state/zip.
# Splits on the LAST ": <digit>" boundary so names containing a colon of
# their own (e.g. "Discoveries: The Library at the Mall: 2550 ...") still
# separate correctly (greedy .* backtracks to the rightmost match).
AA_NAME_ADDR_RE = re.compile(r"^(?P<name>.*):\s*(?P<addr>\d.+)$")

# Howard's addresses are "<street>[,] <city>[,] MD <zip>" with inconsistent
# (sometimes missing) commas before the city. A generic street/city split is
# ambiguous without the comma, so we anchor on Howard's known city names
# (all six appear verbatim in the fixture) rather than guessing where the
# street ends.
HOWARD_ADDR_RE = re.compile(
    r"^(?P<street>.+?),?\s+(?P<city>Ellicott City|Cooksville|Laurel|Columbia|Elkridge|Jessup)"
    r"\s*,?\s*(?:MD|Maryland)\.?\s*(?P<zip>\d{5})?",
    re.IGNORECASE)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def make_record(county_key: str, name: str, street: str, city: str, zc: str,
                hours: str, phone: str, source_url: str, retrieved_date: str) -> dict:
    return {
        "id": f"md-{county_key}-{slugify(name)}",
        "name": name.strip(), "address": street.strip(), "city": city.strip(),
        "state": "MD", "zip": zc or "", "jurisdiction": "md",
        "hours": hours.strip(), "phone": phone.strip(),
        "source_url": source_url, "retrieved_date": retrieved_date,
    }


def _parse_anne_arundel(soup: BeautifulSoup, retrieved_date: str, source_url: str) -> list[dict]:
    # The page is organized as repeating "heading" sections (Police Station
    # Lobbies, Senior Activity Center Community Rooms, Public Libraries),
    # each a <div class="paragraph paragraph--type--heading" id="...">
    # followed by two sibling <div class="paragraph--type--text-editor">:
    # the first holds "Operating Days & Hours" prose, the second an
    # <a class="icon-link-location"> per location reading "Name: Street, City".
    recs: list[dict] = []
    for heading in soup.select('div[class*="paragraph--type--heading"]'):
        heading_text = heading.get_text(strip=True)
        hours_div = heading.find_next_sibling("div", class_="paragraph--type--text-editor")
        locs_div = hours_div.find_next_sibling("div", class_="paragraph--type--text-editor") if hours_div else None
        if locs_div is None:
            print(f"!! md_counties[anne_arundel]: skipped section with no location div: {heading_text[:80]!r}")
            continue
        hours_text = hours_div.get_text(" ", strip=True) if hours_div else ""
        hours_text = re.sub(r"^Operating Days & Hours\s*", "", hours_text)
        for a in locs_div.select("a.icon-link-location"):
            text = a.get_text(strip=True)
            m = AA_NAME_ADDR_RE.match(text)
            if not m:
                print(f"!! md_counties[anne_arundel]: skipped unparseable candidate: {text[:80]!r}")
                continue
            name, addr = m.group("name").strip(), m.group("addr").strip()
            # append the state literal ADDR_LINE_RE expects; AA's own page
            # text omits "MD" since it's implied by the county context.
            am = ADDR_LINE_RE.search(addr + ", MD")
            if not am:
                print(f"!! md_counties[anne_arundel]: skipped unparseable candidate: {(text + ' → ' + addr)[:80]!r}")
                continue
            recs.append(make_record(
                "anne_arundel", name, am.group("street"), am.group("city"), am.group("zip") or "",
                hours_text, "", source_url, retrieved_date))
    return recs


def _parse_howard(soup: BeautifulSoup, retrieved_date: str, source_url: str) -> list[dict]:
    # All facilities (DRP community centers, HCLS library branches, DCRS
    # 50+ centers, the Housing Resource Center) are flat <li> entries of
    # <ul type="disc"> lists; each li's own nested (untyped) <ul> holds
    # Address / Phone Number / Hours of Operation sub-<li>s in that order.
    recs: list[dict] = []
    for li in soup.select('ul[type="disc"] > li'):
        strong = li.find("strong")
        if strong is None:
            li_text = li.get_text(" ", strip=True)
            print(f"!! md_counties[howard]: skipped li with no strong tag: {li_text[:80]!r}")
            continue
        name = re.sub(r"^\d+\s*-\s*", "", strong.get_text(strip=True)).strip()
        nested = li.find("ul")
        if nested is None:
            print(f"!! md_counties[howard]: skipped facility with no nested ul: {name[:80]!r}")
            continue
        sub_lis = nested.find_all("li", recursive=False)
        addr_text = phone = hours_text = ""
        for sub in sub_lis:
            label = sub.get_text(" ", strip=True)
            if label.lower().startswith("address"):
                addr_text = re.sub(r"^Address:?\s*", "", label, flags=re.IGNORECASE)
            elif label.lower().startswith("phone"):
                phone = re.sub(r"^Phone Numbers?:?\s*", "", label, flags=re.IGNORECASE)
            elif label.lower().startswith("hours"):
                hours_text = re.sub(r"^Hours of Operation:?\s*", "", label, flags=re.IGNORECASE)
        if not addr_text:
            print(f"!! md_counties[howard]: skipped unparseable candidate: {name[:80]!r} (no address found)")
            continue
        am = HOWARD_ADDR_RE.search(addr_text)
        if not am:
            print(f"!! md_counties[howard]: skipped unparseable candidate: {addr_text[:80]!r}")
            continue
        recs.append(make_record(
            "howard", name, am.group("street"), am.group("city"), am.group("zip") or "",
            hours_text, phone, source_url, retrieved_date))
    return recs


COUNTY_PARSERS: dict[str, Callable] = {
    "anne_arundel": _parse_anne_arundel,
    "howard": _parse_howard,
}


def parse_county(county_key: str, html: str, retrieved_date: str, source_url: str) -> list[dict]:
    return COUNTY_PARSERS[county_key](BeautifulSoup(html, "html.parser"), retrieved_date, source_url)
