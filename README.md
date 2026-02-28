# Conut COO Agent

Hackathon-ready AI-driven Chief of Operations agent for the Conut AI Engineering Hackathon.

## What This Repository Delivers

This repo provides a practical, reproducible template for:

- Ingesting report-style CSV exports with repeated headers and page markers
- Cleaning and caching them as parquet under `backend/data/processed/`
- Building lightweight feature tables for operational analytics
- Exposing 5 business tools as structured FastAPI endpoints for OpenClaw
- Optionally demoing the same endpoints in a minimal React UI

## Business Objectives Covered

1. Combo optimization
2. Demand forecasting by branch
3. Expansion feasibility scoring
4. Shift staffing estimation
5. Coffee and milkshake growth strategy

## Architecture

See `docs/architecture.md`.

High-level flow:

`raw CSVs -> ingest/clean -> parquet cache -> feature builders -> tool services -> FastAPI JSON endpoints -> OpenClaw / frontend`

## Project Structure

- `backend/`: FastAPI app, ingestion pipeline, feature logic, tests
- `backend/app/objectives/`: one folder per hackathon objective (combo, forecast, expansion, staffing, growth)
- `frontend/`: Vite + React + Tailwind demo UI
- `docs/`: architecture and executive brief template
- `demo/`: demo capture checklist

## Where To Put The CSV Files

Copy the provided scaled Conut CSV exports into:

`backend/data/raw/`

Examples:

- `backend/data/raw/REP_S_00502.csv`
- `backend/data/raw/rep_s_00334_1_SMRY.csv`

The ingest step will normalize filenames to lowercase parquet files in:

`backend/data/processed/`

## Quick Start

### One-command local dev

```bash
docker compose up --build
```

After startup:

- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Frontend demo: `http://localhost:5173`

### Ingest raw data

```bash
make ingest
```

or:

```bash
docker compose run --rm backend python -m app.cli ingest
```

### Run tests

```bash
make test
```

### Generate frontend API types

```bash
make generate-client
```

## API Endpoints

### System

- `GET /health`

### OpenClaw Tool Endpoints

- `GET /tools/schema`
- `POST /tools/recommend_combos`
- `POST /tools/forecast_demand`
- `POST /tools/estimate_staffing`
- `POST /tools/expansion_feasibility`
- `POST /tools/growth_strategy`

Each tool returns:

- `result`
- `key_evidence_metrics`
- `assumptions`
- `data_coverage_notes`

This is intentional so OpenClaw can both act and explain.

## Example Tool Call

```bash
curl -X POST http://localhost:8000/tools/forecast_demand \
  -H "Content-Type: application/json" \
  -d '{"branch":"Hamra","horizon_days":7}'
```

## OpenClaw Integration Notes

Use `GET /tools/schema` to register the tools dynamically.

Recommended OpenClaw flow:

1. Fetch `/tools/schema`
2. Map each returned tool spec into OpenClaw’s tool registry
3. Let the agent call the corresponding POST endpoint with JSON
4. Use `result` for direct answers and `key_evidence_metrics` / `assumptions` for justification

The payloads are intentionally simple, stable, and JSON-first.

## Data and Modeling Notes

This template is optimized for hackathon speed:

- Forecasting uses a rolling mean plus day-of-week factor
- Combo optimization uses order-level co-occurrence support
- Staffing uses demand-to-capacity heuristics
- Expansion uses internal benchmark scoring when no geo data exists
- Growth strategy uses keyword category matching and attach heuristics

This is enough to demonstrate an end-to-end operational AI system quickly. You can replace the internals later with more advanced models without changing the API contract.

## Reproducibility

- Dependencies are pinned in `backend/requirements.txt`
- Frontend uses pinned package versions in `frontend/package.json`
- Docker Compose runs both services locally
- Processed parquet cache prevents re-cleaning on every request

## Deliverable Placeholders

- `docs/executive-brief-template.md`
- `docs/architecture.md`
- `docs/architecture.png`
- `demo/README.md`

## Suggested Next Steps

1. Add a validation notebook comparing forecast accuracy across branches
2. Wire actual OpenClaw tool registration in your demo
3. Replace placeholder heuristics with stronger branch-specific models after ingestion is verified
