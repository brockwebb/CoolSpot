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
