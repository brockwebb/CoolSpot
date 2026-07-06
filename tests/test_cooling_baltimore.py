from pathlib import Path

from pipeline.acquire.cooling import baltimore
from pipeline.schema import partition_records

FIX = Path(__file__).parent / "fixtures"


def test_parse_libraries_designated_records():
    recs = baltimore.parse_libraries((FIX / "md_baltimore_libraries.html").read_text(), "2026-07-06")
    assert len(recs) >= 5
    valid, invalid = partition_records(recs)
    assert invalid == [], [r["_errors"] for r in invalid]
    for r in valid:
        assert r["source_type"] == "designated"
        assert r["jurisdiction"] == "md" and r["state"] == "MD"
        assert r["notes"] and "call ahead" in r["notes"].lower()
        assert any(ch.isdigit() for ch in r["address"])
        assert r["source_url"].startswith("http")


def test_parse_seniors_designated_and_audience_note():
    recs = baltimore.parse_seniors((FIX / "md_baltimore_seniors.html").read_text(), "2026-07-06")
    assert len(recs) >= 3
    valid, invalid = partition_records(recs)
    assert invalid == []
    for r in valid:
        assert r["source_type"] == "designated"
        assert "older adult" in r["notes"].lower()


def test_parse_libraries_excludes_closed_branch(capsys):
    # North Point's address block in the fixture reads "CLOSED FOR RENOVATION<br/>1716
    # Merritt Boulevard<br/>Dundalk, Maryland 21222" — publishing it as an active
    # cooling site during a heat emergency would be a safety hazard, not a data nit.
    recs = baltimore.parse_libraries((FIX / "md_baltimore_libraries.html").read_text(), "2026-07-06")
    assert len(recs) == 18
    assert all(r["name"] != "North Point" for r in recs)
    assert all(r["name"] != "North Point Library" for r in recs)
    assert all("closed" not in r["address"].lower() for r in recs)
    out = capsys.readouterr().out
    assert "skipping closed facility" in out
    assert "North Point" in out


def test_parse_libraries_names_disambiguated_with_library_suffix():
    recs = baltimore.parse_libraries((FIX / "md_baltimore_libraries.html").read_text(), "2026-07-06")
    assert recs, "expected at least one library record"
    for r in recs:
        assert r["name"].endswith(" Library")


def test_seniors_pagination_is_self_terminating():
    # The captured fixture is a concatenation of 3 live directory pages (10, 10, 3
    # rows), each carrying its own "Displaying 23 results" header. Split it back apart
    # to exercise the pure per-page helper the way fetch_seniors consumes it, without
    # hardcoding a page count in the test either.
    raw = (FIX / "md_baltimore_seniors.html").read_text()
    pages = [p for p in raw.split("<!DOCTYPE html>") if p.strip()]
    assert len(pages) == 3

    fetched_rows = 0
    total_expected = None
    stopped_after = None
    for i, html in enumerate(pages):
        row_count, page_total = baltimore._page_result_info(html)
        assert row_count > 0
        if total_expected is None:
            total_expected = page_total
        fetched_rows += row_count
        if row_count == 0 or (total_expected is not None and fetched_rows >= total_expected):
            stopped_after = i
            break

    assert total_expected == 23
    assert fetched_rows == 23
    assert stopped_after == 2  # terminates exactly at the last page, not before or after
