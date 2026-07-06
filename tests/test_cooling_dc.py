from pipeline.acquire.cooling.dc import parse

DC_GEOJSON = {"type": "FeatureCollection", "features": [{
    "type": "Feature", "id": 7,
    "geometry": {"type": "Point", "coordinates": [-77.0219, 38.8993]},
    "properties": {"USER_Name": "MLK Jr Memorial Library", "USER_Address": "901 G St NW, Washington, DC 20001",
                   "USER_Ward": "Ward 2", "USER_Open_To": "Public", "USER_Hours": "Mon-Fri: 9AM-5PM",
                   "USER_Phone": "(202) 727-0321", "USER_Type": "Library",
                   "USER_Url": "https://www.dclibrary.org/mlk", "USER_Status": "Open. See hours below."},
}]}


def test_parse_dc_maps_fields():
    source_url = "https://example.gov/dc-source"
    recs = parse(DC_GEOJSON, "2026-07-05", source_url)
    assert len(recs) == 1
    r = recs[0]
    assert r["id"] == "dc-7"
    assert r["name"] == "MLK Jr Memorial Library"
    assert r["address"] == "901 G St NW"
    assert r["city"] == "Washington" and r["state"] == "DC" and r["zip"] == "20001"
    assert r["lat"] == 38.8993 and r["lon"] == -77.0219
    assert r["hours"] == "Mon-Fri: 9AM-5PM" and r["jurisdiction"] == "dc"
    assert r["source_url"] == source_url
    assert r["retrieved_date"] == "2026-07-05"


def test_parse_dc_handles_unsplittable_address():
    feats = dict(DC_GEOJSON)
    feats["features"][0]["properties"]["USER_Address"] = "901 G St NW"
    r = parse(feats, "2026-07-05", "https://example.gov/dc-source")[0]
    assert r["address"] == "901 G St NW" and r["city"] == "Washington" and r["state"] == "DC"
