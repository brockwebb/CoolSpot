import json
from pipeline.schema import partition_records, validate_record, write_quarantine

GOOD = {
    "id": "dc-001", "name": "MLK Library", "address": "901 G St NW", "city": "Washington",
    "state": "DC", "jurisdiction": "dc", "source_url": "https://example.gov/x",
    "retrieved_date": "2026-07-05", "lat": 38.898, "lon": -77.025,
}


def test_valid_record_passes():
    assert validate_record(GOOD) == []


def test_missing_required_field_named():
    rec = {k: v for k, v in GOOD.items() if k != "source_url"}
    errs = validate_record(rec)
    assert any("source_url" in e for e in errs)


def test_bad_coordinates_rejected():
    errs = validate_record({**GOOD, "lat": 0.0, "lon": 0.0})
    assert any("lat" in e or "lon" in e for e in errs)


def test_bad_date_rejected():
    assert validate_record({**GOOD, "retrieved_date": "July 5"}) != []


def test_partition_and_quarantine(tmp_path, capsys):
    bad = {**GOOD, "name": ""}
    valid, invalid = partition_records([GOOD, bad])
    assert len(valid) == 1 and len(invalid) == 1
    assert "_errors" in invalid[0]
    path = write_quarantine(invalid, "unit_test", tmp_path)
    assert path.exists()
    assert len(json.loads(path.read_text())) == 1
    assert "QUARANTINE" in capsys.readouterr().out


def test_quarantine_empty_returns_none(tmp_path):
    assert write_quarantine([], "unit_test", tmp_path) is None


def test_source_type_valid_values():
    assert validate_record({**GOOD, "source_type": "designated"}) == []
    assert validate_record({**GOOD, "source_type": "listed"}) == []


def test_source_type_invalid_rejected():
    errs = validate_record({**GOOD, "source_type": "made-up"})
    assert any("source_type" in e for e in errs)
