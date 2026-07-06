import pytest
from pipeline.acquire.cooling import runner

GOOD = {"id": "dc-1", "name": "X", "address": "1 Main St", "city": "Washington", "state": "DC",
        "jurisdiction": "dc", "source_url": "https://e.gov", "retrieved_date": "2026-07-05",
        "lat": 38.9, "lon": -77.0}


def test_collect_merges_and_validates(tmp_path):
    fetchers = {"dc": lambda cfg, t, d: [GOOD], "va": lambda cfg, t, d: [{**GOOD, "id": "va-1", "state": "VA", "jurisdiction": "va"}]}
    recs = runner.collect({}, 10, "2026-07-05", fetchers=fetchers)
    assert len(recs) == 2


def test_failed_source_reraises():
    def boom(cfg, t, d):
        raise RuntimeError("site down")
    with pytest.raises(RuntimeError, match="site down"):
        runner.collect({}, 10, "2026-07-05", fetchers={"dc": boom})


def test_collect_stamps_default_source_type():
    fetchers = {"dc": lambda cfg, t, d: [GOOD]}  # GOOD has no source_type
    recs = runner.collect({}, 10, "2026-07-05", fetchers=fetchers)
    assert recs[0]["source_type"] == "listed"


def test_collect_preserves_explicit_source_type():
    designated = {**GOOD, "id": "md-baltimore-lib-x", "source_type": "designated"}
    recs = runner.collect({}, 10, "2026-07-05", fetchers={"md": lambda cfg, t, d: [designated]})
    assert recs[0]["source_type"] == "designated"
