from pipeline.acquire.gazetteer import build_places, display_name, match_key, parse_gazetteer

PLACE_TXT = (
    "USPS\tGEOID\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG            \n"
    "AL\t0100100\t02582661\tAbanda CDP\t57\tS\t7764032\t34284\t2.998\t0.013\t33.091627\t-85.527029      \n"
    "MD\t2475725\t02390487\tSuitland CDP\t57\tS\t11412303\t9601\t4.406\t0.004\t38.849085\t-76.923114     \n"
    "VA\t5129600\t01498558\tFranklin city\t25\tA\t21609865\t236601\t8.344\t0.091\t36.683197\t-76.939744    \n"
)
COUNTY_TXT = (
    "USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG            \n"
    "MD\t24033\t01714670\tPrince George's County\t1250633930\t42160988\t482.873\t16.279\t38.829996\t-76.847360   \n"
    "VA\t51620\t01498421\tFranklin city\t21609865\t236601\t8.344\t0.091\t36.683197\t-76.939744   \n"
)


def test_parse_filters_states_and_strips_padding():
    rows = parse_gazetteer(PLACE_TXT, {"MD", "VA", "DC"})
    assert [r["NAME"] for r in rows] == ["Suitland CDP", "Franklin city"]
    assert rows[0]["INTPTLONG"] == "-76.923114"  # padding stripped


def test_match_key_strips_place_suffixes_and_punct_keeps_county():
    assert match_key("Suitland CDP") == "suitland"
    assert match_key("Franklin city") == "franklin"
    assert match_key("Prince George's County") == "prince georges county"   # county KEPT
    assert match_key("St. Charles CDP") == "st charles"


def test_match_key_strips_typographic_apostrophe():
    assert match_key("O’Brien CDP") == "obrien"


def test_display_name():
    assert display_name("Suitland CDP", "MD", is_county=False) == "Suitland, MD"
    assert display_name("Prince George's County", "MD", is_county=True) == "Prince George's County, MD"


def test_build_places_county_alias_and_collision_rules():
    places = parse_gazetteer(PLACE_TXT, {"MD", "VA"})
    counties = parse_gazetteer(COUNTY_TXT, {"MD", "VA"})
    out = build_places(places, counties)
    qs = {(e["q"], e["state"]): e for e in out}
    assert qs[("franklin", "VA")]["display"] == "Franklin, VA"       # place holds the bare key
    assert qs[("prince georges county", "MD")]["display"] == "Prince George's County, MD"
    assert qs[("prince georges", "MD")]["display"] == "Prince George's County, MD"  # alias (no place collision)
    assert qs[("suitland", "MD")]["lat"] == 38.8491                   # 4 decimals


def test_county_bare_alias_loses_to_place():
    # A place and county sharing a bare name in the same state: county keeps only its "x county" key.
    places = parse_gazetteer(PLACE_TXT, {"VA"})
    counties = [{"USPS": "VA", "NAME": "Franklin County", "ALAND": "1", "INTPTLAT": "37.0", "INTPTLONG": "-79.9"}]
    out = build_places(places, counties)
    qs = {(e["q"], e["state"]): e for e in out}
    assert qs[("franklin", "VA")]["display"] == "Franklin, VA"              # city wins bare key
    assert qs[("franklin county", "VA")]["display"] == "Franklin County, VA"  # county reachable explicitly


def test_build_places_empty_raises():
    import pytest
    with pytest.raises(RuntimeError, match="0 places"):
        build_places([], [])


def test_published_places_json_normalization_parity():
    # Invariant: every "q" in the committed site/data/places.json must live in the charset
    # {a-z, 0-9, space, hyphen} — the charset on which the pipeline's match_key (Python) and
    # the client's normPlace (JS) provably agree. If a future gazetteer entry produces a "q"
    # outside this charset, the two normalizers could silently diverge and break place search.
    import json
    import re

    from pipeline.config import PROJECT_ROOT

    path = PROJECT_ROOT / "site" / "data" / "places.json"
    places = json.loads(path.read_text())
    assert places, "places.json is empty"
    charset = re.compile(r"^[a-z0-9 -]+$")
    expected_keys = {"q", "display", "state", "lat", "lon"}
    for entry in places:
        assert charset.match(entry["q"]), f"q outside normalization-parity charset: {entry['q']!r}"
        assert set(entry.keys()) == expected_keys, f"unexpected keys: {entry.keys()!r}"
