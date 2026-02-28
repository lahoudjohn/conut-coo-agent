from typing import Any

from fastapi import APIRouter, Query, Request

from app.core.tool_activity import list_tool_activity, record_tool_activity
from app.objectives.objective1_combo.service import recommend_combos
from app.objectives.objective2_forecast.service import forecast_branch_demand
from app.objectives.objective3_expansion.service import score_expansion_feasibility
from app.objectives.objective4_staffing.service import (
    benchmark_staffing_pressure,
    estimate_shift_staffing,
    summarize_branch_shift_lengths,
)
from app.objectives.objective5_growth.service import build_growth_strategy
from app.schemas.staffing import (
    ShiftLengthSummaryRequest,
    ShiftLengthSummaryResponse,
    StaffingBenchmarkRequest,
    StaffingBenchmarkResponse,
    StaffingRequest,
    StaffingResponse,
)
from app.schemas.tools import (
    ComboRequest,
    ExpansionRequest,
    ForecastRequest,
    GrowthStrategyRequest,
    ToolResponse,
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _activity_source(request: Request) -> str:
    caller = request.headers.get("X-Conut-Caller", "").strip()
    return caller or "unknown"


def _activity_agent_tool(request: Request) -> str | None:
    tool_name = request.headers.get("X-Conut-Agent-Tool", "").strip()
    return tool_name or None


def _build_result_preview(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    elif isinstance(payload, dict):
        data = payload
    else:
        return {}

    preview: dict[str, Any] = {"keys": sorted(data.keys())[:8]}
    if "tool_name" in data:
        preview["tool_name"] = data["tool_name"]
    if "recommended_staff" in data:
        preview["recommended_staff"] = data["recommended_staff"]
    if "result" in data and isinstance(data["result"], dict):
        preview["result_keys"] = sorted(data["result"].keys())[:8]
    return preview


def _log_activity(request: Request, tool_name: str, path: str, payload: Any, response_payload: Any) -> None:
    record_tool_activity(
        tool_name=tool_name,
        path=path,
        source=_activity_source(request),
        agent_tool=_activity_agent_tool(request),
        payload=payload,
        result_preview=_build_result_preview(response_payload),
        raw_output=response_payload,
    )


def _primary_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "objective_id": 1,
            "name": "recommend_combos",
            "openclaw_name": "conut_combo_optimization",
            "method": "POST",
            "path": "/tools/recommend_combos",
            "description": "Find high-value item combinations from order-level purchase patterns.",
            "request_schema": ComboRequest.model_json_schema(),
            "primary_objective_tool": True,
        },
        {
            "objective_id": 2,
            "name": "forecast_demand",
            "openclaw_name": "conut_demand_forecast",
            "method": "POST",
            "path": "/tools/forecast_demand",
            "description": "Forecast branch demand using historical sales patterns.",
            "request_schema": ForecastRequest.model_json_schema(),
            "primary_objective_tool": True,
        },
        {
            "objective_id": 3,
            "name": "expansion_feasibility",
            "openclaw_name": "conut_expansion_feasibility",
            "method": "POST",
            "path": "/tools/expansion_feasibility",
            "description": "Score candidate branch feasibility using internal branch benchmarks.",
            "request_schema": ExpansionRequest.model_json_schema(),
            "primary_objective_tool": True,
        },
        {
            "objective_id": 4,
            "name": "estimate_staffing",
            "openclaw_name": "conut_shift_staffing",
            "method": "POST",
            "path": "/tools/estimate_staffing",
            "description": "Estimate required employees per shift using demand and attendance-based labor signals.",
            "request_schema": StaffingRequest.model_json_schema(),
            "primary_objective_tool": True,
        },
        {
            "objective_id": 5,
            "name": "growth_strategy",
            "openclaw_name": "conut_growth_strategy",
            "method": "POST",
            "path": "/tools/growth_strategy",
            "description": "Generate coffee/milkshake growth insights from category performance and attach patterns.",
            "request_schema": GrowthStrategyRequest.model_json_schema(),
            "primary_objective_tool": True,
        },
    ]


def _secondary_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "understaffed_branches",
            "method": "POST",
            "path": "/tools/understaffed_branches",
            "description": "Rank branches by staffing pressure relative to their sales-driven shift labor requirements.",
            "request_schema": StaffingBenchmarkRequest.model_json_schema(),
            "primary_objective_tool": False,
        },
        {
            "name": "average_shift_length",
            "method": "POST",
            "path": "/tools/average_shift_length",
            "description": "Summarize average shift length across branches or for a selected branch/shift.",
            "request_schema": ShiftLengthSummaryRequest.model_json_schema(),
            "primary_objective_tool": False,
        },
    ]


def _all_tool_specs() -> list[dict[str, Any]]:
    primary = _primary_tool_specs()
    secondary = _secondary_tool_specs()
    return [primary[0], primary[1], primary[3], secondary[0], secondary[1], primary[2], primary[4]]


@router.post("/recommend_combos", response_model=ToolResponse)
def recommend_combos_endpoint(payload: ComboRequest, request: Request) -> ToolResponse:
    response = recommend_combos(payload)
    _log_activity(request, "recommend_combos", "/tools/recommend_combos", payload, response)
    return response


@router.post("/forecast_demand", response_model=ToolResponse)
def forecast_demand_endpoint(payload: ForecastRequest, request: Request) -> ToolResponse:
    response = forecast_branch_demand(payload)
    _log_activity(request, "forecast_demand", "/tools/forecast_demand", payload, response)
    return response


@router.post("/estimate_staffing", response_model=StaffingResponse)
def estimate_staffing_endpoint(payload: StaffingRequest, request: Request) -> StaffingResponse:
    response = estimate_shift_staffing(payload)
    _log_activity(request, "estimate_staffing", "/tools/estimate_staffing", payload, response)
    return response


@router.post("/understaffed_branches", response_model=StaffingBenchmarkResponse)
def understaffed_branches_endpoint(payload: StaffingBenchmarkRequest, request: Request) -> StaffingBenchmarkResponse:
    response = benchmark_staffing_pressure(payload)
    _log_activity(request, "understaffed_branches", "/tools/understaffed_branches", payload, response)
    return response


@router.post("/average_shift_length", response_model=ShiftLengthSummaryResponse)
def average_shift_length_endpoint(payload: ShiftLengthSummaryRequest, request: Request) -> ShiftLengthSummaryResponse:
    response = summarize_branch_shift_lengths(payload)
    _log_activity(request, "average_shift_length", "/tools/average_shift_length", payload, response)
    return response


@router.post("/expansion_feasibility", response_model=ToolResponse)
def expansion_feasibility_endpoint(payload: ExpansionRequest, request: Request) -> ToolResponse:
    response = score_expansion_feasibility(payload)
    _log_activity(request, "expansion_feasibility", "/tools/expansion_feasibility", payload, response)
    return response


@router.post("/growth_strategy", response_model=ToolResponse)
def growth_strategy_endpoint(payload: GrowthStrategyRequest, request: Request) -> ToolResponse:
    response = build_growth_strategy(payload)
    _log_activity(request, "growth_strategy", "/tools/growth_strategy", payload, response)
    return response


@router.get("/schema", tags=["tools"])
def tool_schema() -> dict:
    return {
        "tools": _all_tool_specs(),
        "primary_objective_tools": _primary_tool_specs(),
    }


@router.get("/activity", tags=["tools"])
def tool_activity(limit: int = Query(default=25, ge=1, le=50)) -> dict:
    return {"events": list_tool_activity(limit=limit)}


@router.get("/openclaw_manifest", tags=["tools"])
def openclaw_manifest() -> dict:
    return {
        "plugin_id": "conut-coo-agent",
        "plugin_entrypoint": "./openclaw/conut-coo-agent/conut-coo-agent.ts",
        "tool_count": len(_primary_tool_specs()),
        "tools": _primary_tool_specs(),
        "notes": [
            "This manifest exposes only the 5 primary business objective tools for OpenClaw.",
            "Use /tools/schema if you also want helper analytics endpoints such as understaffed_branches.",
        ],
    }
