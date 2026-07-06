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
    r = parse([VA_JSON[0]], "2026-07-05")[0]
    assert r["id"] == "va-1289"
    assert r["name"] == "Richmond Public Library - Main"
    assert r["lat"] == 37.5407 and r["lon"] == -77.4419
    assert r["state"] == "VA" and r["jurisdiction"] == "va"
    assert r["hours"] == ""  # empty passthrough; UI says "call ahead"


def test_dedupe_on_source_id():
    assert len(dedupe(VA_JSON)) == 1
