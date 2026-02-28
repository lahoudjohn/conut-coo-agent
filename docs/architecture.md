# Architecture

## Diagram

Create `docs/architecture.png` using draw.io, Excalidraw, Figma, or Mermaid export.

Recommended blocks:

1. Raw Data Layer
2. Ingestion + Cleaning
3. Parquet Cache
4. Feature Layer
5. Tool Services
6. FastAPI API Layer
7. OpenClaw
8. React Demo UI

## Recommended Diagram Layout

```text
Conut CSV Reports
    ->
Ingest CLI (python -m app.cli ingest)
    ->
Cleaned Parquet Cache (backend/data/processed)
    ->
Feature Builders (transactions, branch daily, hourly, category mix)
    ->
Tool Services
  - combo
  - forecast
  - staffing
  - expansion
  - strategy
    ->
FastAPI Tool Endpoints
    -> OpenClaw
    -> Frontend Dashboard
```

## Service Contracts

### Ingestion
- Reads report-style CSVs from `backend/data/raw/`
- Removes repeated headers and page markers
- Writes cached parquet to `backend/data/processed/`

### Feature Engineering
- Builds normalized transaction frame
- Builds branch-day aggregates
- Builds hourly demand profile
- Builds category keyword summaries

### Inference / Reporting
Each tool returns structured JSON with:
- operational result
- evidence metrics
- assumptions
- coverage notes

This makes the system easy to demo and easy to justify to judges.

## Why This Architecture Fits The Hackathon

- Fast to stand up
- Easy to explain
- Reproducible
- OpenClaw-friendly
- Can be improved incrementally without breaking endpoints
