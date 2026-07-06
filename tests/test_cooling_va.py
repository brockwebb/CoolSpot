from pipeline.acquire.cooling.va import dedupe, parse

VA_JSON = [
    {"id": "1289", "store": "Richmond Public Library - Main", "address": "101 E Franklin St", "address2": "",
     "city": "Richmond", "state": "VA", "zip": "23219", "lat": "37.5407", "lng": "-77.4419",
     "phone": "(804) 646-9255", "hours": "", "url": "https://rvalibrary.org"},
    {"id": "1289", "store": "Richmond Public Library - Main", "address": "101 E Franklin St", "address2": "",
     "city": "Richmond", "state": "VA", "zip": "23219", "lat": "37.5407", "lng": "-77.4419",
     "phone": "", "hours": "", "url": ""},
]


def test_parse_va_maps_fields():
    source_url = "https://example.gov/va-source"
    r = parse([VA_JSON[0]], "2026-07-05", source_url)[0]
    assert r["id"] == "va-1289"
    assert r["name"] == "Richmond Public Library - Main"
    assert r["lat"] == 37.5407 and r["lon"] == -77.4419
    assert r["state"] == "VA" and r["jurisdiction"] == "va"
    assert r["source_url"] == source_url
    assert r["hours"] == ""  # empty passthrough; UI says "call ahead"


def test_dedupe_on_source_id():
    assert len(dedupe(VA_JSON)) == 1


def test_parse_va_guards_malformed_coordinates():
    """Row with empty lat/lng should yield record without lat/lon keys."""
    malformed_row = {
        "id": "9999", "store": "Test Center", "address": "123 Test St", "address2": "",
        "city": "TestCity", "state": "VA", "zip": "12345", "lat": "", "lng": "",
        "phone": "555-1234", "hours": "9-5", "url": "https://test.org"
    }
    good_row = VA_JSON[0]

    recs = parse([malformed_row, good_row], "2026-07-05", "https://example.gov/va-source")
    assert len(recs) == 2

    # Malformed row: has no lat/lon keys
    assert "lat" not in recs[0] and "lon" not in recs[0]
    assert recs[0]["id"] == "va-9999" and recs[0]["name"] == "Test Center"

    # Good row: has lat/lon
    assert recs[1]["lat"] == 37.5407 and recs[1]["lon"] == -77.4419
