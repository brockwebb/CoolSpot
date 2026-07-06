"""coolspot CLI. Each subcommand is a function(config) registered in COMMANDS."""
from __future__ import annotations

import argparse
import sys
from typing import Callable

from pipeline.config import load_config
from pipeline.acquire import census as acquire_census_mod
from pipeline.acquire import hospitals as acquire_hospitals_mod
from pipeline.acquire.cooling import runner as acquire_cooling_mod
from pipeline import geocode as geocode_mod


def _not_implemented(name: str) -> Callable[[dict], None]:
    def _run(cfg: dict) -> None:
        raise SystemExit(f"{name}: not implemented yet (see plan task list)")
    return _run


COMMANDS: dict[str, Callable[[dict], None]] = {
    "acquire-census": acquire_census_mod.run,
    "acquire-hospitals": acquire_hospitals_mod.run,
    "acquire-cooling": acquire_cooling_mod.run,
    "geocode": geocode_mod.run,
    "publish": _not_implemented("publish"),
}


def _run_all(cfg: dict) -> None:
    for name in ("acquire-census", "acquire-hospitals", "acquire-cooling", "geocode", "publish"):
        print(f"==> {name}")
        COMMANDS[name](cfg)


COMMANDS["all"] = _run_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coolspot", description="CoolSpot data pipeline")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    COMMANDS[args.command](load_config())
    return 0
