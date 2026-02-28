# COOnut: Conut COO Agent

AI-driven Chief of Operations system built for the Conut AI Engineering Hackathon.
This repository delivers a reproducible decision-support stack for Conut's five required business objectives, with:

- a Dockerized FastAPI backend
- a Dockerized React frontend
- a host-side OpenClaw integration layer
- a custom branded chat UI (`COOnut`)
- a live control-room dashboard that shows which OpenClaw tools were used

## What This Project Does

COOnut turns cleaned Conut operational data into structured, explainable business decisions across:

1. Combo Optimization
2. Demand Forecasting by Branch
3. Expansion Feasibility
4. Shift Staffing Estimation
5. Coffee and Milkshake Growth Strategy

The backend is the source of truth.
The frontend is the executive-facing interface.
OpenClaw is the agent layer that decides which tool to call.

## Current Architecture

High-level flow:

`cleaned CSVs -> objective services -> FastAPI tool endpoints -> OpenClaw tool/plugin -> COOnut frontend + OpenClaw chat`

Current runtime split:

- Docker runs the `backend` (FastAPI) and `frontend` (Vite/React)
- The host machine runs the `OpenClaw gateway` and the local `OpenClaw plugin`

This is intentional. It keeps the app itself Dockerized while using OpenClaw as the external agent runtime.

## Repository Structure

- `backend/`
- `backend/app/objectives/`
- `backend/app/api/routes/tools.py`
- `backend/app/api/routes/agent.py`
- `backend/app/core/tool_activity.py`
- `frontend/`
- `openclaw/conut-coo-agent/`
- `docs/`
- `demo/`

What these do:

- `backend/` contains the FastAPI app, objective logic, processed data, and tests
- `backend/app/objectives/` contains one folder per hackathon objective
- `backend/app/api/routes/tools.py` exposes the primary business tools
- `backend/app/api/routes/agent.py` exposes the backend proxy route for the frontend chat (`/agent/chat`)
- `backend/app/core/tool_activity.py` records recent tool calls for the Control Room
- `frontend/` contains the React + TypeScript + Tailwind product UI
- `openclaw/conut-coo-agent/` contains the local OpenClaw plugin that exposes the five main tools

## Data Layout

Raw CSVs belong in:

- `backend/data/raw/`

Cleaned and processed files used by the current system live in:

- `backend/data/processed/`

Key files used by the current objectives:

- `REP_S_00502_obj1.csv`
- `REP_S_00334_1_SMRY_cleaned.csv`
- `REP_S_00461_cleaned.csv`
- `REP_S_00194_SMRY_cleaned.csv`

## Business Objective Implementation

### 1. Combo Optimization

Primary files:

- `backend/app/objectives/objective1_combo/service.py`

Main data:

- `backend/data/processed/REP_S_00502_obj1.csv`

What it does:

- builds order baskets from netted line-item sales
- mines co-purchase relationships
- ranks strategic combos
- supports item-specific and branch-specific combo questions

Primary endpoint:

- `POST /tools/recommend_combos`

OpenClaw tool:

- `conut_combo_optimization`

### 2. Demand Forecasting by Branch

Primary files:

- `backend/app/objectives/objective2_forecast/demand_forecast.py`
- `backend/app/objectives/objective2_forecast/service.py`

Main data:

- `backend/data/processed/REP_S_00334_1_SMRY_cleaned.csv`

What it does:

- uses a 3-period weighted moving average
- projects branch demand from cleaned monthly sales history
- returns daily forecast rows for the requested horizon

Primary endpoint:

- `POST /tools/forecast_demand`

OpenClaw tool:

- `conut_demand_forecast`

### 3. Expansion Feasibility

Primary files:

- `backend/app/objectives/objective3_expansion/service.py`

Main data:

- `backend/data/processed/REP_S_00334_1_SMRY_cleaned.csv`
- `backend/data/processed/REP_S_00194_SMRY_cleaned.csv`

What it does:

- benchmarks candidate locations against internal branch performance
- scores feasibility using internal branch analogs
- returns a directional recommendation

Primary endpoint:

- `POST /tools/expansion_feasibility`

OpenClaw tool:

- `conut_expansion_feasibility`

### 4. Shift Staffing Estimation

Primary files:

- `backend/app/objectives/objective4_staffing/service.py`
- `backend/app/tools/staffing.py`

Main data:

- `backend/data/processed/REP_S_00461_cleaned.csv`
- `backend/data/processed/REP_S_00334_1_SMRY_cleaned.csv`

What it does:

- converts attendance logs into shift buckets
- builds branch labor-hour and headcount features
- calculates branch productivity from labor vs sales
- estimates required staffing per shift

Primary endpoint:

- `POST /tools/estimate_staffing`

Related helper endpoints:

- `POST /tools/understaffed_branches`
- `POST /tools/average_shift_length`

OpenClaw tool:

- `conut_shift_staffing`

### 5. Coffee and Milkshake Growth Strategy

Primary files:

- `backend/app/objectives/objective5_growth/service.py`
- `backend/app/services/tools/strategy.py`

Main data:

- `backend/data/processed/REP_S_00502_obj1.csv`

What it does:

- measures category share and attach opportunities
- uses coffee and milkshake keyword matching
- returns actionable growth suggestions grounded in actual category activity

Primary endpoint:

- `POST /tools/growth_strategy`

OpenClaw tool:

- `conut_growth_strategy`

## API Surface

### System

- `GET /health`

### Tool Discovery

- `GET /tools/schema`
- `GET /tools/openclaw_manifest`
- `GET /tools/activity`

### Primary Business Tools

- `POST /tools/recommend_combos`
- `POST /tools/forecast_demand`
- `POST /tools/expansion_feasibility`
- `POST /tools/estimate_staffing`
- `POST /tools/growth_strategy`

### Objective 4 Helper Endpoints

- `POST /tools/understaffed_branches`
- `POST /tools/average_shift_length`

### Frontend Chat Proxy

- `POST /agent/chat`

This endpoint allows the custom frontend chat UI to talk to OpenClaw through the backend.

## How The Code Works End To End

### Backend flow

1. Cleaned CSVs are loaded from `backend/data/processed/`.
2. Objective-specific service code computes the analysis.
3. FastAPI returns structured JSON from `/tools/...`.
4. Every tool call is recorded in `tool_activity.py`.
5. `/tools/activity` exposes the recent tool log for the frontend dashboard.

### OpenClaw flow

1. OpenClaw loads the local plugin from `openclaw/conut-coo-agent/conut-coo-agent.ts`.
2. The plugin exposes the five main objectives as tools.
3. When OpenClaw chooses a tool, the plugin calls the matching FastAPI endpoint.
4. The backend returns structured JSON.
5. OpenClaw turns that into a natural-language answer.

### Frontend flow

1. The user types into the `COOnut` chat UI.
2. The frontend sends the message to `POST /agent/chat`.
3. The backend proxies that message to the OpenClaw gateway.
4. OpenClaw may call one of the five tools.
5. The assistant response comes back to the frontend chat.
6. The `Control Room` shows the last five tool calls made by OpenClaw.

## Running The Project

## Option A: Recommended Full Run (Dockerized App + Host OpenClaw)

This is the intended grading and demo setup.

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd conut-coo-agent
```

### 2. Create the Docker environment file

Copy:

```bash
cp .env.example .env
```

Set values in `.env` as needed:

- `CONUT_OPENCLAW_GATEWAY_URL`
- `CONUT_OPENCLAW_GATEWAY_TOKEN`
- `CONUT_OPENCLAW_AGENT_ID`

Notes:

- `CONUT_OPENCLAW_GATEWAY_URL` is already set for Docker + host OpenClaw in `.env.example`
- `CONUT_OPENCLAW_GATEWAY_TOKEN` is needed if you want the custom frontend chat (`/agent/chat`) to work while the backend runs inside Docker
- `CONUT_OPENCLAW_AGENT_ID` defaults to `main`

### 3. Start the Dockerized app

```bash
docker compose up --build
```

After startup:

- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### 4. Start OpenClaw on the host machine

OpenClaw is not containerized in this repo. It runs on the host and connects to the Dockerized backend.

Link the plugin:

```bash
openclaw plugins install -l ./openclaw/conut-coo-agent/conut-coo-agent.ts
```

Then run OpenClaw with host-side environment variables:

```bash
OPENAI_API_KEY=your_openai_key
CONUT_API_URL=http://127.0.0.1:8000
openclaw gateway run
```

If you want the stock OpenClaw dashboard too:

```bash
openclaw dashboard
```

### 5. Open the product UI

Go to:

- `http://localhost:5173`

Use:

- `Agent Lounge` for the branded COOnut chat UI
- `Control Room` for the last five OpenClaw-triggered tool calls

## Option B: Local Development Without Docker

### Backend

```powershell
cd c:\Users\JL\Desktop\Hackathon\conut-coo-agent
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```powershell
cd c:\Users\JL\Desktop\Hackathon\conut-coo-agent\frontend
npm install
npm run dev
```

### OpenClaw

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:CONUT_API_URL="http://127.0.0.1:8000"
openclaw plugins install -l .\openclaw\conut-coo-agent\conut-coo-agent.ts
openclaw gateway run
```

## Professor Validation Flow

The simplest reviewer flow:

1. Run `docker compose up --build`
2. Open `http://localhost:8000/docs`
3. Manually test the five primary `/tools/...` endpoints
4. Start OpenClaw on the host machine with a valid API key
5. Open `http://localhost:5173`
6. Ask operational questions in the COOnut chat
7. Verify the `Control Room` shows which tool was used

This covers:

- reproducibility
- end-to-end pipeline execution
- operational AI tool use
- practical OpenClaw integration

## Example Questions

Use these in the frontend chat or OpenClaw:

1. `What are the top 5 product combos to promote?`
2. `Forecast demand for Conut Jnah for the next 7 days.`
3. `Is North District a good candidate for a new branch in Beirut?`
4. `How many staff do we need at Main Street Coffee for the evening shift in 2025-12?`
5. `How can we increase coffee and milkshake sales across all branches?`

## Testing

Backend smoke tests:

```bash
cd backend
pytest -q
```

Or from the repo root:

```bash
make test
```

Other useful commands:

- `make ingest`
- `make generate-client`

## OpenClaw Notes

The local OpenClaw plugin lives in:

- `openclaw/conut-coo-agent/`

The backend manifest endpoint:

- `GET /tools/openclaw_manifest`

returns the clean five-tool handoff aligned to the hackathon objectives.

The frontend chat uses:

- `POST /agent/chat`

and relies on the backend being able to reach the OpenClaw gateway.
That is why the Docker setup includes:

- `CONUT_OPENCLAW_GATEWAY_URL`
- `CONUT_OPENCLAW_GATEWAY_TOKEN`

## Limitations

- OpenClaw itself is not containerized in this repo.
- Tool activity is stored in backend memory, so restarting the backend clears the live in-memory feed.
- The `Control Room` only records real tool calls. If the model answers directly without invoking a tool, no new tool event appears.
- Most analytics are lightweight deterministic baselines designed for hackathon speed, not heavyweight production ML pipelines.

## Deliverables Included

- Public GitHub-ready repository structure
- Dockerized backend and frontend
- Objective-based backend implementation
- OpenClaw integration plugin
- Custom branded frontend (`COOnut`)
- README run instructions
- docs placeholders and demo checklist
