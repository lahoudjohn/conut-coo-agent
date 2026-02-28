# Demo Evidence Checklist

Capture the following and add files to this folder:

## Screenshots

1. Swagger `/docs` showing the 5 tool endpoints
2. Frontend dashboard with at least one successful tool result
3. OpenClaw invoking `GET /tools/schema`
4. OpenClaw invoking at least two POST tool endpoints
5. Ingest command output showing parquet files written

## Short Video

Recommended 60 to 120 second demo flow:

1. Show raw CSVs in `backend/data/raw/`
2. Run `python -m app.cli ingest`
3. Open `http://localhost:8000/docs`
4. Trigger a tool endpoint
5. Open the frontend demo and run a second tool
6. Show OpenClaw calling the same backend endpoint
7. Close with one business recommendation from the outputs

## File Naming

Use clean, predictable names:

- `01-swagger-tools.png`
- `02-frontend-dashboard.png`
- `03-openclaw-schema.png`
- `04-openclaw-forecast.png`
- `05-ingest-output.png`
- `demo.mp4`
