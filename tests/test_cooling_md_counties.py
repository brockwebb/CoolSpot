# tests/test_cooling_md_counties.py
"""Baltimore County is intentionally absent from CASES: its cooling-locations
page (tests/fixtures/md_baltimore_county.html) lists only category links
(library system, senior centers) and phone numbers to "check locations" —
no scrapeable per-center addresses. Per the task-10 drop rule, its parser was
deleted rather than faking records. See .superpowers/sdd/task-10-report.md."""
from pathlib import Path

import pytest
from pipeline.acquire.cooling.md_counties import COUNTY_PARSERS, parse_county
from pipeline.schema import partition_records

FIXTURES = Path(__file__).parent / "fixtures"
CASES = ["anne_arundel", "howard"]


@pytest.mark.parametrize("county", CASES)
def test_county_parser_yields_valid_records(county):
    html = (FIXTURES / f"md_{county}.html").read_text()
    recs = parse_county(county, html, "2026-07-05", f"https://example.gov/{county}")
    assert len(recs) >= 1, f"{county}: parser found no cooling centers in real fixture"
    valid, invalid = partition_records(recs)
    assert invalid == [], f"{county}: schema violations: {[r['_errors'] for r in invalid]}"
    for r in valid:
        assert r["jurisdiction"] == "md"
        assert r["source_url"] == f"https://example.gov/{county}"
        assert any(ch.isdigit() for ch in r["address"]), f"address looks wrong: {r['address']}"


def test_unknown_county_raises():
    with pytest.raises(KeyError):
        parse_county("narnia", "<html></html>", "2026-07-05", "https://example.gov/x")


def test_all_configured_counties_have_parsers():
    assert set(COUNTY_PARSERS) >= set(CASES)
