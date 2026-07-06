# CoolSpot: Project Context for Claude Code

**Project purpose:** CoolSpot is a public heat-relief finder for the DC, Maryland, and Virginia region. It provides a static site (built via GitHub Pages) that locates cooling centers, hospitals, and air-conditioned facilities alongside Census heat vulnerability and air-conditioning estimates to help residents find cooling during extreme heat events.

## Architecture & Decisions

See `docs/design/AD-001-architecture.md` for approved architectural decisions. Key constraints:
- Static site + offline Python pipeline (no server)
- Vanilla JS + Leaflet, GitHub Pages deployment
- Data sources: Census (CRE-Heat 2022, LACE 2023, ACS), HealthData.gov, state/county cooling center registries

## Specification & Planning

- Full specification: `docs/specification.md`
- Implementation plan: `docs/plan.md`

## Before You Push

Run the full test suite:
```bash
uv run pytest tests/ -v
```

All tests must pass. No exceptions.

## Pipeline CLI

The pipeline is exposed as the `coolspot` command:
```bash
coolspot --help
```

Configuration is centralized in `config/pipeline.yaml` — all tunables live there. No magic numbers in source code.

## Environment Setup

Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Then add your Census API key from https://api.census.gov/data/key_signup.html:
```bash
CENSUS_API_KEY=<your-key>
```

The pipeline will fail loudly if required env vars are missing.
