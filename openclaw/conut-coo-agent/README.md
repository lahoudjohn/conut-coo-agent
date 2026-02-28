# Conut COO Agent OpenClaw Plugin

This local plugin registers the 5 primary Conut COO objective tools in OpenClaw:

- `conut_combo_optimization`
- `conut_demand_forecast`
- `conut_expansion_feasibility`
- `conut_shift_staffing`
- `conut_growth_strategy`

It forwards all tool calls to the FastAPI backend.

## Default Backend URL

If you do nothing, the plugin calls:

`http://127.0.0.1:8000`

You can override that before starting OpenClaw:

```powershell
$env:CONUT_API_URL="http://127.0.0.1:8000"
```

Optional bearer token passthrough:

```powershell
$env:CONUT_API_TOKEN="your-token-here"
```

## Install In OpenClaw

Link the plugin by pointing OpenClaw at the entry file:

```bash
openclaw plugins install -l ./openclaw/conut-coo-agent/conut-coo-agent.ts
```

After installation, restart the OpenClaw gateway/app if needed.

## Backend Dependency

The FastAPI backend must already be running:

```bash
docker compose up --build
```

Or the plugin will fail when it tries to call the tool endpoints.
