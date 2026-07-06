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
