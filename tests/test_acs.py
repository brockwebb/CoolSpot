from pipeline.acquire.census import acs_attrs, acs_rows_to_dict

DETAILED = [
    ["NAME", "B01003_001E", "B09021_022E", "B09021_023E", "B17001_001E", "B17001_002E",
     "B08201_001E", "B08201_002E", "state", "county", "tract"],
    ["Census Tract 8024.05", "4123", "612", "180", "4000", "480", "1500", "90", "24", "033", "802405"],
]
SUBJECT = [
    ["NAME", "S1810_C01_001E", "S1810_C02_001E", "S0101_C01_030E", "state", "county", "tract"],
    ["Census Tract 8024.05", "4100", "520", "630", "24", "033", "802405"],
]


def test_rows_to_dict_builds_geoid():
    d = acs_rows_to_dict(DETAILED)
    assert "24033802405" in d
    assert d["24033802405"]["B01003_001E"] == "4123"


def test_acs_attrs_merges_and_computes():
    det = acs_rows_to_dict(DETAILED)["24033802405"]
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    a = acs_attrs(det, sub)
    assert a["pop_total"] == 4123
    assert a["pop_65plus"] == 630          # S0101_C01_030E
    assert a["pop_65_alone"] == 180        # B09021_023E
    assert a["pct_poverty"] == 12.0        # 480/4000
    assert a["pct_no_vehicle"] == 6.0      # 90/1500
    assert round(a["pct_disability"], 1) == 12.7  # 520/4100


def test_zero_denominator_gives_none():
    det = {**acs_rows_to_dict(DETAILED)["24033802405"], "B17001_001E": "0"}
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    assert acs_attrs(det, sub)["pct_poverty"] is None


def test_negative_sentinel_gives_none():
    det = {**acs_rows_to_dict(DETAILED)["24033802405"], "B17001_002E": "-666666666"}
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    assert acs_attrs(det, sub)["pct_poverty"] is None


def test_acs_attrs_includes_count_numerators():
    det = acs_rows_to_dict(DETAILED)["24033802405"]
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    a = acs_attrs(det, sub)
    assert a["pov_below_e"] == 480       # B17001_002E raw numerator
    assert a["disability_e"] == 520      # S1810_C02_001E raw numerator


def test_count_numerator_sentinel_gives_none():
    det = {**acs_rows_to_dict(DETAILED)["24033802405"], "B17001_002E": "-666666666"}
    sub = acs_rows_to_dict(SUBJECT)["24033802405"]
    assert acs_attrs(det, sub)["pov_below_e"] is None
