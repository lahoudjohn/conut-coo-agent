# OpenClaw Integration

This project now includes a local OpenClaw plugin starter under:

`openclaw/conut-coo-agent/`

Its purpose is to expose the 5 primary business objectives as 5 OpenClaw tools:

1. `conut_combo_optimization`
2. `conut_demand_forecast`
3. `conut_expansion_feasibility`
4. `conut_shift_staffing`
5. `conut_growth_strategy`

## How It Works

- OpenClaw calls the local plugin tool.
- The plugin forwards the request to the FastAPI backend.
- The backend runs the objective logic and returns JSON.
- The plugin returns that JSON back to OpenClaw as structured text content.

This keeps the integration thin. The source of truth remains the FastAPI backend.

## Install Flow

1. Start the backend:

```bash
docker compose up --build
```

2. Confirm the backend manifest is available:

- `GET /tools/openclaw_manifest`
- `GET /tools/schema`

3. Link the local plugin into OpenClaw:

```bash
openclaw plugins install -l ./openclaw/conut-coo-agent/conut-coo-agent.ts
```

4. Restart OpenClaw if needed.

## Backend Manifest

The backend now exposes:

- `GET /tools/openclaw_manifest`

This returns exactly the 5 primary objective tools, separate from extra helper endpoints such as:

- `understaffed_branches`
- `average_shift_length`

Use this manifest when you want a clean 5-tool demo.

## Environment Variables

The plugin uses these optional variables:

- `CONUT_API_URL`
  - default: `http://127.0.0.1:8000`
- `CONUT_API_TIMEOUT_MS`
  - default: `20000`
- `CONUT_API_TOKEN`
  - optional bearer token passthrough if you later add backend auth

## Limitations

- The plugin assumes the backend is reachable over HTTP.
- It returns backend JSON as text content for maximum compatibility.
- Tool schemas are mirrored in the plugin and should be updated if the FastAPI request models change.

## Recommended Next Step

After all 5 objectives are validated individually, use this plugin as the single OpenClaw bridge for the final demo.
