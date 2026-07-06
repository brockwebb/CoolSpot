from pipeline.geocode import apply_geocodes, build_batch_csv, parse_batch_response

NEEDS = {"id": "md-howard-x", "name": "X", "address": "10 Main St", "city": "Columbia", "state": "MD",
         "zip": "21044", "jurisdiction": "md", "source_url": "https://e.gov", "retrieved_date": "2026-07-05"}
HAS = {**NEEDS, "id": "dc-1", "lat": 38.9, "lon": -77.0}

BATCH_RESPONSE = '''"md-howard-x","10 Main St, Columbia, MD, 21044","Match","Exact","10 MAIN ST, COLUMBIA, MD, 21044","-76.86051,39.20401","647368517","L"
"md-fail-y","1 Nowhere Rd, Xx, MD, 00000","No_Match"
'''


def test_build_batch_csv_only_uncoded():
    csv_text = build_batch_csv([NEEDS, HAS])
    assert "md-howard-x" in csv_text and "dc-1" not in csv_text
    assert csv_text.splitlines()[0] == "md-howard-x,10 Main St,Columbia,MD,21044"


def test_parse_batch_response():
    g = parse_batch_response(BATCH_RESPONSE)
    assert g["md-howard-x"]["lat"] == 39.20401
    assert g["md-howard-x"]["lon"] == -76.86051
    assert g["md-howard-x"]["geocode_quality"] == "Exact"
    assert "md-fail-y" not in g


def test_apply_geocodes_partitions():
    located, unlocated = apply_geocodes([NEEDS, HAS, {**NEEDS, "id": "md-fail-y"}],
                                        parse_batch_response(BATCH_RESPONSE))
    assert {r["id"] for r in located} == {"md-howard-x", "dc-1"}
    assert unlocated[0]["id"] == "md-fail-y"
