from fastapi import APIRouter

from app.objectives.objective1_combo.service import recommend_combos
from app.objectives.objective2_forecast.service import forecast_branch_demand
from app.objectives.objective3_expansion.service import score_expansion_feasibility
from app.objectives.objective4_staffing.service import estimate_shift_staffing
from app.objectives.objective5_growth.service import build_growth_strategy
from app.schemas.tools import (
    ComboRequest,
    ExpansionRequest,
    ForecastRequest,
    GrowthStrategyRequest,
    StaffingRequest,
    ToolResponse,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/recommend_combos", response_model=ToolResponse)
def recommend_combos_endpoint(payload: ComboRequest) -> ToolResponse:
    return recommend_combos(payload)


@router.post("/forecast_demand", response_model=ToolResponse)
def forecast_demand_endpoint(payload: ForecastRequest) -> ToolResponse:
    return forecast_branch_demand(payload)


@router.post("/estimate_staffing", response_model=ToolResponse)
def estimate_staffing_endpoint(payload: StaffingRequest) -> ToolResponse:
    return estimate_shift_staffing(payload)


@router.post("/expansion_feasibility", response_model=ToolResponse)
def expansion_feasibility_endpoint(payload: ExpansionRequest) -> ToolResponse:
    return score_expansion_feasibility(payload)


@router.post("/growth_strategy", response_model=ToolResponse)
def growth_strategy_endpoint(payload: GrowthStrategyRequest) -> ToolResponse:
    return build_growth_strategy(payload)


@router.get("/schema", tags=["tools"])
def tool_schema() -> dict:
    specs = [
        {
            "name": "recommend_combos",
            "method": "POST",
            "path": "/tools/recommend_combos",
            "description": "Find high-value item combinations from order-level purchase patterns.",
            "request_schema": ComboRequest.model_json_schema(),
        },
        {
            "name": "forecast_demand",
            "method": "POST",
            "path": "/tools/forecast_demand",
            "description": "Forecast branch demand using historical sales patterns.",
            "request_schema": ForecastRequest.model_json_schema(),
        },
        {
            "name": "estimate_staffing",
            "method": "POST",
            "path": "/tools/estimate_staffing",
            "description": "Estimate required staffing by branch, date, and shift.",
            "request_schema": StaffingRequest.model_json_schema(),
        },
        {
            "name": "expansion_feasibility",
            "method": "POST",
            "path": "/tools/expansion_feasibility",
            "description": "Score candidate branch feasibility using internal branch benchmarks.",
            "request_schema": ExpansionRequest.model_json_schema(),
        },
        {
            "name": "growth_strategy",
            "method": "POST",
            "path": "/tools/growth_strategy",
            "description": "Generate coffee/milkshake growth insights from category performance and attach patterns.",
            "request_schema": GrowthStrategyRequest.model_json_schema(),
        },
    ]
    return {"tools": specs}
