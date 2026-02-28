from __future__ import annotations

from app.core.config import settings
from app.objectives.objective2_forecast.demand_forecast import forecast_branch_demand_wma
from app.schemas.tools import ForecastRequest, ToolResponse


def forecast_branch_demand(payload: ForecastRequest) -> ToolResponse:
    result = forecast_branch_demand_wma(
        branch=payload.branch,
        forecast_horizon=payload.horizon_days,
        processed_data_path=settings.processed_data_dir,
    )

    if result is None:
        return ToolResponse(
            tool_name="forecast_demand",
            result={"branch": payload.branch, "forecast": []},
            key_evidence_metrics={"history_months_used": 0, "recent_avg_daily_units": 0},
            assumptions=[
                "Monthly sales history was unavailable, so the WMA forecast could not run.",
                "Objective 2 expects REP_S_00334_1_SMRY_cleaned.csv in backend/data/processed.",
            ],
            data_coverage_notes=["REP_S_00334_1_SMRY_cleaned.csv was not found in backend/data/processed."],
        )

    recent_avg_daily_units = 0.0
    if result.forecast_rows:
        recent_avg_daily_units = float(result.forecast_rows[0]["predicted_demand_units"])

    return ToolResponse(
        tool_name="forecast_demand",
        result={
            "branch": result.branch,
            "forecast": result.forecast_rows,
            "model": "3-period weighted moving average",
        },
        key_evidence_metrics={
            "history_months_used": result.history_months_used,
            "recent_avg_daily_units": round(recent_avg_daily_units, 2),
            "recent_period_used": result.latest_period_used,
            "latest_sales_used": round(result.latest_sales, 2),
            "wma_weights": result.weights,
        },
        assumptions=result.assumptions,
        data_coverage_notes=result.data_coverage_notes,
    )
