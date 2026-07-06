import pytest
from pipeline.config import ConfigError, load_config, require_env


def test_load_config_returns_all_sections():
    cfg = load_config()
    for section in ("states", "census", "geocoder", "hospitals", "cooling_sources", "publish"):
        assert section in cfg
    assert {s["abbr"] for s in cfg["states"]} == {"DC", "MD", "VA"}


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="pipeline.yaml"):
        load_config(tmp_path / "nope" / "pipeline.yaml")


def test_load_config_missing_section_raises(tmp_path):
    p = tmp_path / "pipeline.yaml"
    p.write_text("states: []\n")
    with pytest.raises(ConfigError, match="census"):
        load_config(p)


def test_require_env_missing_names_variable(monkeypatch):
    monkeypatch.delenv("COOLSPOT_TEST_VAR", raising=False)
    with pytest.raises(ConfigError, match="COOLSPOT_TEST_VAR"):
        require_env("COOLSPOT_TEST_VAR")


def test_require_env_present(monkeypatch):
    monkeypatch.setenv("COOLSPOT_TEST_VAR", "abc")
    assert require_env("COOLSPOT_TEST_VAR") == "abc"
