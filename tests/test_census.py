from pipeline.acquire.census import cre_heat_attrs, filter_state_rows, lace_attrs, tract_geoid

CRE_ROW = {
    "GEO_ID": "1400000US24033802405", "STATE": "24", "COUNTY": "033", "TRACT": "802405",
    "NAME": "Census Tract 8024.05", "POPUNI": "4123",
    "PRED0_E": "1000", "PRED0_PE": "24.3", "PRED12_E": "2100", "PRED12_PE": "50.9",
    "PRED3_E": "1023", "PRED3_PE": "24.8", "LONG_90_DAY": "9", "MAX_WBT": "82.1", "EXPOSED": "1",
}
LACE_ROW = {
    "GEO_ID": "1400000US24033802405", "STATE": "24", "COUNTY": "033", "TRACT": "802405",
    "NAME": "Census Tract 8024.05", "WATER_TRACT": "0",
    "HSE_OCC_E": "1500", "HSE_OCC_M": "120", "AC_E": "1400", "AC_PE": "93.3",
    "NO_AC_E": "100", "NO_AC_M": "40", "NO_AC_PE": "6.7", "NO_AC_PM": "2.5",
}


def test_tract_geoid_strips_prefix():
    assert tract_geoid(CRE_ROW) == "24033802405"


def test_cre_heat_attrs():
    a = cre_heat_attrs(CRE_ROW)
    assert a == {"pop": 4123, "pred3_e": 1023, "pred3_pe": 24.8, "exposed": 1}


def test_lace_attrs():
    a = lace_attrs(LACE_ROW)
    assert a == {"hse_occ_e": 1500, "no_ac_e": 100, "no_ac_pe": 6.7, "water_tract": 0}


def test_missing_values_become_none():
    a = cre_heat_attrs({**CRE_ROW, "PRED3_PE": "", "EXPOSED": "-999"})
    assert a["pred3_pe"] is None and a["exposed"] is None


def test_lace_attrs_handles_float_formatted_int_fields():
    """Real LACE rows format integer counts as floats (e.g. NO_AC_E='2.0')."""
    a = lace_attrs({**LACE_ROW, "HSE_OCC_E": "672", "NO_AC_E": "2.0"})
    assert a["hse_occ_e"] == 672 and a["no_ac_e"] == 2


def test_filter_state_rows(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("GEO_ID,STATE,POPUNI\n1400000US24033802405,24,100\n1400000US06001000100,06,200\n")
    rows = filter_state_rows(p, {"24", "51", "11"})
    assert len(rows) == 1 and rows[0]["STATE"] == "24"


def test_filter_state_rows_falls_back_to_cp1252(tmp_path):
    """CRE-Heat national CSV ships Windows-1252 (accented territory place
    names); a strict utf-8-sig decode raises UnicodeDecodeError."""
    p = tmp_path / "x.csv"
    header = "GEO_ID,STATE,POPUNI,NAME\n"
    row_24 = "1400000US24033802405,24,100,Some Tract\n"
    row_accented = "1400000US72001000100,72," + "200,Comunidad Ba\xf1os\n"
    p.write_bytes((header + row_24 + row_accented).encode("cp1252"))
    rows = filter_state_rows(p, {"24", "51", "11"})
    assert len(rows) == 1 and rows[0]["STATE"] == "24"
