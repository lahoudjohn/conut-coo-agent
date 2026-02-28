from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.schemas.tools import ForecastRequest, ToolResponse
from app.services.features import summarize_branch_daily


def forecast_branch_demand(payload: ForecastRequest) -> ToolResponse:
    ctx = summarize_branch_daily()
    df = ctx.raw.copy()

    if not df.empty:
        df = df[df["branch_name"].astype(str).str.lower() == payload.branch.lower()]

    if df.empty:
        placeholder = []
        start = pd.Timestamp.today().normalize()
        for i in range(payload.horizon_days):
            placeholder.append(
                {"date": str((start + timedelta(days=i)).date()), "predicted_demand_units": 100 + (i % 3) * 8, "placeholder": True}
            )
        return ToolResponse(
            tool_name="forecast_demand",
            result={"branch": payload.branch, "forecast": placeholder},
            key_evidence_metrics={"history_days_used": 0, "recent_avg_daily_units": 0},
            assumptions=[
                "No branch history was available; placeholder trend is returned for demo behavior.",
                "Production should ingest raw CSVs first using `python -m app.cli ingest`.",
            ],
            data_coverage_notes=ctx.coverage_notes,
        )

    df["event_date"] = pd.to_datetime(df["event_date"])
    df = df.sort_values("event_date")

    recent = df.tail(min(len(df), 28)).copy()
    recent_avg = float(recent["demand_units"].mean())
    recent["dow"] = recent["event_date"].dt.dayofweek
    dow_factors = (recent.groupby("dow")["demand_units"].mean() / max(recent_avg, 1)).to_dict()

    last_date = recent["event_date"].max()
    trailing_mean = recent.tail(min(len(recent), 7))["demand_units"].mean()

    out = []
    for i in range(1, payload.horizon_days + 1):
        forecast_date = last_date + timedelta(days=i)
        factor = float(dow_factors.get(forecast_date.dayofweek, 1.0))
        predicted = max(1.0, trailing_mean * factor)
        out.append(
            {
                "date": str(forecast_date.date()),
                "predicted_demand_units": round(predicted, 2),
                "predicted_revenue_proxy": round(predicted * max(recent["revenue_proxy"].mean() / max(recent_avg, 1), 1), 2),
            }
        )

    start_avg = recent.head(min(len(recent), 7))["demand_units"].mean()
    end_avg = recent.tail(min(len(recent), 7))["demand_units"].mean()
    trend_pct = ((end_avg - start_avg) / start_avg * 100) if start_avg else 0.0

    return ToolResponse(
        tool_name="forecast_demand",
        result={"branch": payload.branch, "forecast": out},
        key_evidence_metrics={
            "history_days_used": int(len(recent)),
            "recent_avg_daily_units": round(recent_avg, 2),
            "recent_7_day_trend_pct": round(trend_pct, 2),
        },
        assumptions=[
            "Forecast uses a simple rolling mean with day-of-week seasonality for hackathon speed and explainability.",
            "Use this as a baseline; replace with Prophet/XGBoost later if validation supports it.",
        ],
        data_coverage_notes=ctx.coverage_notes,
    )
