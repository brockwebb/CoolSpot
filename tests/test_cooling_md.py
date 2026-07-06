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
