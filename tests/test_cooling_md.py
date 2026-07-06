from pipeline.acquire.cooling.md import clean_text, parse_hub, parse_pg

PG_JSON = {"features": [{
    "attributes": {"Name": "Bowie Community Center", "Address": "3209 Stonybrook Dr, Bowie, MD 20716",
                   "Phone": "301-464-1737", "Hours": "M-F 9-5", "OBJECTID": 3},
    "geometry": {"x": -76.7276, "y": 38.9433},
}]}

HUB_HTML = """
<table><tbody>
<tr><td>Allegany</td><td>301-759-5000</td><td><a href="https://alleganyhealthdept.com/cooling">Cooling info</a></td></tr>
<tr><td>Baltimore City</td><td>311</td><td><a href="https://health.maryland.gov/preparedness/Documents/BC%20Cooling.pdf">PDF</a></td></tr>
</tbody></table>
"""


def test_parse_pg_maps_fields():
    recs = parse_pg(PG_JSON, "2026-07-05")
    assert len(recs) == 1
    r = recs[0]
    assert r["id"] == "md-pg-3"
    assert r["name"] == "Bowie Community Center"
    assert r["address"] == "3209 Stonybrook Dr"
    assert r["city"] == "Bowie" and r["state"] == "MD" and r["zip"] == "20716"
    assert r["lat"] == 38.9433 and r["lon"] == -76.7276
    assert r["jurisdiction"] == "md"
    assert r["qc_note"] == ""


def test_parse_pg_unsplit_address_sets_qc_note_not_notes():
    # A record whose Address string doesn't match "<street>, <city>, MD <zip>" falls
    # back to the whole string as street + county-level city. That fallback is an
    # internal QC annotation — it must land in `qc_note`, which the finder does not
    # render, never in the public-facing `notes` field.
    raw = {"features": [{
        "attributes": {"Name": "Unsplittable Center", "Address": "Somewhere weird with no commas",
                       "Phone": "", "Hours": "", "OBJECTID": 99},
        "geometry": {},
    }]}
    recs = parse_pg(raw, "2026-07-05")
    assert len(recs) == 1
    r = recs[0]
    assert r["qc_note"] == "city inferred; address not split"
    assert "notes" not in r, "PG records must not carry a public-facing `notes` field"


def test_parse_hub_builds_registry():
    entries = parse_hub(HUB_HTML, "2026-07-05")
    assert len(entries) == 2
    assert entries[0]["county"] == "Allegany"
    assert entries[0]["links"] == ["https://alleganyhealthdept.com/cooling"]
    assert entries[1]["links"][0].endswith(".pdf")


def test_parse_hub_fixture_county_count():
    """Canary test: MDH hub page county count. Fails when page redesigns."""
    from pathlib import Path
    fixture_path = Path(__file__).parent / "fixtures" / "md_hub_2026.html"
    if not fixture_path.exists():
        import pytest
        pytest.skip("md_hub_2026.html fixture not present")
    hub_html = fixture_path.read_text()
    entries = parse_hub(hub_html, "2026-07-05")
    # If this fails, the MDH hub page structure changed — update fixture and count
    assert len(entries) == 24, f"Expected 24 counties in MDH hub, got {len(entries)}"
    assert all("County / City" not in e["county"] for e in entries)
    garrett = [e for e in entries if e["county"] == "Garrett County"]
    assert len(garrett) == 1
    assert garrett[0]["county"] == "Garrett County"


def test_clean_text_strips_zero_width_and_nbsp():
    assert clean_text("​​Garrett\xa0County​") == "Garrett County"


def test_write_registry_preserves_review_notes(tmp_path):
    """Test that write_registry preserves review_note fields from existing entries."""
    from pipeline.acquire.cooling.md import write_registry
    import json

    reg_path = tmp_path / "registry.json"

    # Write initial registry with a review_note on Baltimore County.
    initial_entries = [
        {
            "county": "Baltimore County",
            "phone": "410-887-2243",
            "links": ["https://example.gov/baltimore"],
            "retrieved_date": "2026-07-05",
            "review_note": "test review note"
        },
        {
            "county": "Anne Arundel County",
            "phone": "410-768-5522",
            "links": ["https://example.gov/aa"],
            "retrieved_date": "2026-07-05"
        }
    ]
    write_registry(initial_entries, reg_path)

    # Verify the note was written.
    data = json.loads(reg_path.read_text())
    assert data[0]["review_note"] == "test review note"

    # Regenerate registry with fresh data (no review_note in new entries).
    fresh_entries = [
        {
            "county": "Baltimore County",
            "phone": "410-887-2243",
            "links": ["https://example.gov/baltimore-new"],
            "retrieved_date": "2026-07-06"
        },
        {
            "county": "Anne Arundel County",
            "phone": "410-768-5522",
            "links": ["https://example.gov/aa-new"],
            "retrieved_date": "2026-07-06"
        },
        {
            "county": "Caroline County",
            "phone": "410-479-2222",
            "links": ["https://example.gov/caroline"],
            "retrieved_date": "2026-07-06"
        }
    ]
    write_registry(fresh_entries, reg_path)

    # Verify the review_note on Baltimore County survived the regeneration.
    data = json.loads(reg_path.read_text())
    baltimore = [e for e in data if e["county"] == "Baltimore County"]
    assert len(baltimore) == 1
    assert baltimore[0]["review_note"] == "test review note"
    assert baltimore[0]["links"][0] == "https://example.gov/baltimore-new"

    # Anne Arundel should still have no review_note.
    aa = [e for e in data if e["county"] == "Anne Arundel County"]
    assert len(aa) == 1
    assert "review_note" not in aa[0]
