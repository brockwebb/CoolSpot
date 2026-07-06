"""Fail-loud configuration loading. All tunables live in config/pipeline.yaml."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline.yaml"
REQUIRED_SECTIONS = ("states", "census", "geocoder", "hospitals", "cooling_sources", "publish")


class ConfigError(RuntimeError):
    pass


def load_config(path: Path | None = None) -> dict:
    path = path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path} (expected config/pipeline.yaml)")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ConfigError(f"Config {path} missing required section(s): {', '.join(missing)}")
    return cfg


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Required environment variable {name} is not set. See .env.example.")
    return value
