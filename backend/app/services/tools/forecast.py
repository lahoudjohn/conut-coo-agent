from __future__ import annotations

import calendar
from datetime import timedelta

import pandas as pd

from app.core.config import settings
from app.schemas.tools import ForecastRequest, ToolResponse


MONTHLY_SALES_PATH = settings.processed_data_dir / "REP_S_00334_1_SMRY_cleaned.csv"


def _normalize_branch(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _load_monthly_sales() -> pd.DataFrame:
    if not MONTHLY_SALES_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(MONTHLY_SALES_PATH).copy()
    df["month"] = pd.to_numeric(df.get("month"), errors="coerce")
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["total_sales"] = pd.to_numeric(df.get("total_sales"), errors="coerce")

    if "period_key" not in df.columns:
        df["period_key"] = df.apply(
            lambda row: (
                f"{int(row['year']):04d}-{int(row['month']):02d}"
                if pd.notna(row["year"]) and pd.notna(row["month"])
                else None
            ),
            axis=1,
        )

    df["period_date"] = pd.to_datetime(df["period_key"].astype(str) + "-01", errors="coerce")
    df = df.dropna(subset=["branch_name", "period_date", "total_sales"]).copy()
    return df.sort_values("period_date")


def _average_monthly_step(series: pd.Series) -> float:
    if len(series) < 2:
        return 0.0
    diffs = series.diff().dropna()
    if diffs.empty:
        return 0.0
    return float(diffs.tail(min(len(diffs), 3)).mean())


def forecast_branch_demand(payload: ForecastRequest) -> ToolResponse:
    monthly_df = _load_monthly_sales()
    if monthly_df.empty:
        start = pd.Timestamp.today().normalize()
        forecast = [
            {
                "date": str((start + timedelta(days=i)).date()),
                "predicted_demand_units": 100 + (i % 3) * 8,
                "placeholder": True,
            }
            for i in range(payload.horizon_days)
        ]
        return ToolResponse(
            tool_name="forecast_demand",
            result={"branch": payload.branch, "forecast": forecast},
            key_evidence_metrics={"history_months_used": 0, "recent_avg_daily_units": 0},
            assumptions=[
                "Monthly sales history was unavailable, so a placeholder trend was returned.",
                "Objective 2 expects REP_S_00334_1_SMRY_cleaned.csv in backend/data/processed.",
            ],
            data_coverage_notes=["REP_S_00334_1_SMRY_cleaned.csv was not found in backend/data/processed."],
        )

    branch_df = monthly_df[
        monthly_df["branch_name"].astype(str).map(_normalize_branch) == _normalize_branch(payload.branch)
    ].copy()

    if branch_df.empty:
        available = sorted(monthly_df["branch_name"].astype(str).unique().tolist())
        return ToolResponse(
            tool_name="forecast_demand",
            result={"branch": payload.branch, "forecast": []},
            key_evidence_metrics={"history_months_used": 0, "recent_avg_daily_units": 0},
            assumptions=[
                "Branch-specific forecasting requires a branch that exists in the monthly sales summary.",
            ],
            data_coverage_notes=[f"Branch '{payload.branch}' was not found. Available branches: {', '.join(available)}."],
        )

    branch_df = branch_df.sort_values("period_date").reset_index(drop=True)
    latest = branch_df.iloc[-1]
    latest_sales = float(latest["total_sales"])
    latest_period = pd.Timestamp(latest["period_date"])
    days_in_latest_month = calendar.monthrange(latest_period.year, latest_period.month)[1]
    recent_avg_daily_units = latest_sales / max(days_in_latest_month, 1)

    monthly_step = _average_monthly_step(branch_df["total_sales"])
    base_sales = max(0.0, latest_sales + monthly_step)

    start_date = pd.Timestamp.today().normalize()
    forecast_rows = []
    for i in range(payload.horizon_days):
        forecast_date = start_date + timedelta(days=i)
        target_month_start = pd.Timestamp(year=forecast_date.year, month=forecast_date.month, day=1)
        months_ahead = max(
            0,
            (target_month_start.year - latest_period.year) * 12 + (target_month_start.month - latest_period.month),
        )
        projected_month_sales = max(0.0, latest_sales + (monthly_step * months_ahead))
        days_in_target_month = calendar.monthrange(forecast_date.year, forecast_date.month)[1]
        predicted_daily_units = projected_month_sales / max(days_in_target_month, 1)
        forecast_rows.append(
            {
                "date": str(forecast_date.date()),
                "predicted_demand_units": round(predicted_daily_units, 2),
                "predicted_revenue_proxy": round(projected_month_sales, 2),
            }
        )

    prior_sales = float(branch_df["total_sales"].iloc[0]) if len(branch_df) > 1 else latest_sales
    trend_pct = ((latest_sales - prior_sales) / prior_sales * 100) if prior_sales else 0.0

    return ToolResponse(
        tool_name="forecast_demand",
        result={"branch": str(latest["branch_name"]), "forecast": forecast_rows},
        key_evidence_metrics={
            "history_months_used": int(len(branch_df)),
            "recent_avg_daily_units": round(recent_avg_daily_units, 2),
            "average_monthly_step": round(monthly_step, 2),
            "recent_period_used": str(latest["period_key"]),
            "recent_trend_pct": round(trend_pct, 2),
        },
        assumptions=[
            "Forecast is derived from branch monthly sales because the available cleaned data for Objective 2 is monthly, not daily.",
            "Daily demand is estimated as projected monthly sales divided by the days in the target month.",
            "This is a lightweight deterministic baseline, not a trained time-series model.",
        ],
        data_coverage_notes=[
            f"Loaded {len(monthly_df):,} monthly rows from {MONTHLY_SALES_PATH.name}.",
            f"Used {len(branch_df):,} monthly observations for branch '{latest['branch_name']}'.",
            f"Latest observed month: {latest['period_key']} with scaled sales {latest_sales:,.2f}.",
        ],
    )
