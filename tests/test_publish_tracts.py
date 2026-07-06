import pytest
from pipeline.publish_tracts import build_state_geojson

FEATURES = [
    {"type": "Feature", "properties": {"GEOID": "11001000100"},
     "geometry": {"type": "Polygon", "coordinates": [[[-77.0, 38.9], [-77.0, 38.91], [-76.99, 38.9], [-77.0, 38.9]]]}},
]
CRE = {"11001000100": {"pop": 4123, "pred3_e": 1023, "pred3_pe": 24.8, "exposed": 1}}
LACE = {"11001000100": {"hse_occ_e": 1500, "no_ac_e": 100, "no_ac_pe": 6.7, "water_tract": 0}}
ACS = {"11001000100": {"pop_total": 4123, "pop_65plus": 630, "pop_65_alone": 180,
                       "pct_poverty": 12.0, "pct_no_vehicle": 6.0, "pct_disability": 12.7}}


def test_attributes_merged_into_properties():
    fc = build_state_geojson(FEATURES, CRE, LACE, ACS, min_match_rate=0.99)
    props = fc["features"][0]["properties"]
    assert props["pred3_pe"] == 24.8 and props["no_ac_pe"] == 6.7 and props["pop_65plus"] == 630


def test_low_match_rate_fails_loud():
    with pytest.raises(RuntimeError, match="match rate"):
        build_state_geojson(FEATURES, {}, {}, {}, min_match_rate=0.99)
