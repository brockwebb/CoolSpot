from pipeline.acquire.hospitals import hospital_features

ROWS = [
    {"hospital_pk": "090001", "hospital_name": "HOWARD UNIVERSITY HOSPITAL", "address": "2041 GEORGIA AVE NW",
     "city": "WASHINGTON", "state": "DC", "zip": "20060", "hospital_subtype": "Short Term",
     "geocoded_hospital_address": {"type": "Point", "coordinates": [-77.02, 38.917]}},
    {"hospital_pk": "210001", "hospital_name": "NO GEOCODE HOSPITAL", "address": "1 MAIN ST",
     "city": "BALTIMORE", "state": "MD", "zip": "21201", "hospital_subtype": "Short Term",
     "geocoded_hospital_address": None},
]
CMS = {"090001": {"hospital_type": "Acute Care Hospitals", "emergency_services": "Yes"}}


def test_hospital_features_geometry_and_enrichment():
    feats, skipped = hospital_features(ROWS, CMS, "2026-07-05")
    assert len(feats) == 1 and len(skipped) == 1
    f = feats[0]
    assert f["geometry"]["coordinates"] == [-77.02, 38.917]
    assert f["properties"]["emergency_services"] is True
    assert f["properties"]["hospital_type"] == "Acute Care Hospitals"
    assert f["properties"]["retrieved_date"] == "2026-07-05"


def test_unmatched_ccn_gets_none_enrichment():
    feats, _ = hospital_features([ROWS[0]], {}, "2026-07-05")
    assert feats[0]["properties"]["emergency_services"] is None
