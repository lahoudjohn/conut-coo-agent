from __future__ import annotations

import calendar
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


WMA_WEIGHTS = np.array([0.2, 0.3, 0.5], dtype=float)
SOURCE_FILE = "REP_S_00334_1_SMRY_cleaned.csv"


@dataclass
class WmaForecastResult:
    branch: str
    forecast_rows: list[dict[str, float | str]]
    history_months_used: int
    latest_period_used: str
    latest_sales: float
    weights: list[float]
    data_coverage_notes: list[str]
    assumptions: list[str]


def _normalize_branch(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _load_monthly_sales(processed_data_path: str | Path) -> pd.DataFrame:
    file_path = Path(processed_data_path) / SOURCE_FILE
    if not file_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(file_path).copy()
    df["month"] = pd.to_numeric(df.get("month"), errors="coerce")
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["total_sales"] = pd.to_numeric(df.get("total_sales"), errors="coerce")
    df = df.dropna(subset=["branch_name", "month", "year", "total_sales"]).copy()

    df["month"] = df["month"].astype(int)
    df["year"] = df["year"].astype(int)
    df["period_key"] = df.apply(lambda row: f"{row['year']:04d}-{row['month']:02d}", axis=1)
    df["period_date"] = pd.to_datetime(df["period_key"] + "-01", errors="coerce")

    grouped = (
        df.dropna(subset=["period_date"])
        .groupby(["branch_name", "year", "month", "period_key", "period_date"], as_index=False)
        .agg(total_sales=("total_sales", "sum"))
        .sort_values(["branch_name", "period_date"])
    )
    return grouped


def _project_monthly_sales(history: list[float], months_ahead: int) -> list[float]:
    if len(history) < len(WMA_WEIGHTS):
        raise ValueError(f"At least {len(WMA_WEIGHTS)} historical months are required for WMA forecasting.")

    if months_ahead <= 0:
        return []

    window = list(history[-len(WMA_WEIGHTS) :])
    projections: list[float] = []
    for _ in range(months_ahead):
        next_val = float(np.dot(window, WMA_WEIGHTS))
        next_val = max(next_val, 0.0)
        projections.append(next_val)
        window.pop(0)
        window.append(next_val)
    return projections


def forecast_branch_demand_wma(
    branch: str,
    forecast_horizon: int,
    processed_data_path: str | Path,
) -> WmaForecastResult | None:
    monthly_df = _load_monthly_sales(processed_data_path)
    file_path = Path(processed_data_path) / SOURCE_FILE

    if monthly_df.empty:
        return None

    branch_df = monthly_df[
        monthly_df["branch_name"].astype(str).map(_normalize_branch) == _normalize_branch(branch)
    ].copy()

    if branch_df.empty:
        available = sorted(monthly_df["branch_name"].astype(str).unique().tolist())
        return WmaForecastResult(
            branch=branch,
            forecast_rows=[],
            history_months_used=0,
            latest_period_used="",
            latest_sales=0.0,
            weights=WMA_WEIGHTS.tolist(),
            data_coverage_notes=[
                f"Branch '{branch}' was not found in {SOURCE_FILE}.",
                f"Available branches: {', '.join(available)}.",
            ],
            assumptions=[
                "Branch-specific WMA forecasting requires a branch that exists in the cleaned monthly sales file.",
            ],
        )

    branch_df = branch_df.sort_values("period_date").reset_index(drop=True)
    if len(branch_df) < len(WMA_WEIGHTS):
        latest_period_used = str(branch_df.iloc[-1]["period_key"]) if not branch_df.empty else ""
        return WmaForecastResult(
            branch=str(branch_df.iloc[-1]["branch_name"]),
            forecast_rows=[],
            history_months_used=int(len(branch_df)),
            latest_period_used=latest_period_used,
            latest_sales=float(branch_df.iloc[-1]["total_sales"]) if not branch_df.empty else 0.0,
            weights=WMA_WEIGHTS.tolist(),
            data_coverage_notes=[
                f"Only {len(branch_df)} month(s) available for branch '{branch_df.iloc[-1]['branch_name']}'.",
                f"WMA requires at least {len(WMA_WEIGHTS)} months of history.",
            ],
            assumptions=[
                "The 3-period weighted moving average cannot run without at least 3 historical months.",
            ],
        )

    latest = branch_df.iloc[-1]
    latest_period = pd.Timestamp(latest["period_date"])
    latest_sales = float(latest["total_sales"])

    start_date = pd.Timestamp.today().normalize()
    target_month_starts = sorted(
        {
            pd.Timestamp(year=(start_date + pd.Timedelta(days=i)).year, month=(start_date + pd.Timedelta(days=i)).month, day=1)
            for i in range(forecast_horizon)
        }
    )
    max_months_ahead = max(
        0,
        max(
            (
                (month_start.year - latest_period.year) * 12 + (month_start.month - latest_period.month)
                for month_start in target_month_starts
            ),
            default=0,
        ),
    )
    monthly_projections = _project_monthly_sales(branch_df["total_sales"].tolist(), max_months_ahead)

    forecast_rows: list[dict[str, float | str]] = []
    for i in range(forecast_horizon):
        forecast_date = start_date + pd.Timedelta(days=i)
        target_month_start = pd.Timestamp(year=forecast_date.year, month=forecast_date.month, day=1)
        months_ahead = (target_month_start.year - latest_period.year) * 12 + (target_month_start.month - latest_period.month)

        if months_ahead <= 0:
            projected_month_sales = latest_sales
        else:
            projected_month_sales = monthly_projections[months_ahead - 1]

        days_in_target_month = calendar.monthrange(forecast_date.year, forecast_date.month)[1]
        predicted_daily_units = projected_month_sales / max(days_in_target_month, 1)
        forecast_rows.append(
            {
                "date": str(forecast_date.date()),
                "predicted_demand_units": round(float(predicted_daily_units), 2),
                "predicted_revenue_proxy": round(float(projected_month_sales), 2),
            }
        )

    return WmaForecastResult(
        branch=str(latest["branch_name"]),
        forecast_rows=forecast_rows,
        history_months_used=int(len(branch_df)),
        latest_period_used=str(latest["period_key"]),
        latest_sales=latest_sales,
        weights=WMA_WEIGHTS.tolist(),
        data_coverage_notes=[
            f"Loaded {len(monthly_df):,} monthly rows from {file_path.name}.",
            f"Used {len(branch_df):,} monthly observations for branch '{latest['branch_name']}'.",
            f"Latest observed month: {latest['period_key']} with scaled sales {latest_sales:,.2f}.",
        ],
        assumptions=[
            "Forecast uses a 3-period weighted moving average with weights 20%, 30%, and 50% from oldest to newest.",
            "Daily demand is estimated by dividing projected monthly sales by the number of days in each target month.",
            "This is a lightweight deterministic baseline built from the cleaned monthly sales summary.",
        ],
    )


def forecast_future_demand_wma(processed_data_path: str | Path = "data/processed", forecast_horizon: int = 3) -> tuple[str, dict | None]:
    """
    Legacy report-style interface preserved for notebook or script usage.
    """
    monthly_df = _load_monthly_sales(processed_data_path)
    if monthly_df.empty:
        report = "\n" + "=" * 80 + "\n"
        report += "CHIEF OF OPERATIONS: 3-MONTH WMA FORECAST\n"
        report += "=" * 80 + "\n"
        report += f"ERROR: Could not find {SOURCE_FILE} in {processed_data_path}.\n"
        return report, None

    report = "\n" + "=" * 80 + "\n"
    report += "CHIEF OF OPERATIONS: 3-MONTH WMA FORECAST\n"
    report += "=" * 80 + "\n"
    report += "MODEL ARCHITECTURE: 3-Period Weighted Moving Average (Iterative)\n"
    report += "WEIGHT DISTRIBUTION: 50% Recent | 30% Previous | 20% Oldest\n\n"
    report += "PER-BRANCH PROJECTIONS:\n"

    plot_data: dict[str, dict[str, list[float] | list[int] | int]] = {}
    for branch_name in monthly_df["branch_name"].astype(str).unique():
        branch_df = monthly_df[monthly_df["branch_name"] == branch_name].sort_values("period_date").reset_index(drop=True)
        if len(branch_df) < len(WMA_WEIGHTS):
            report += f"   * {branch_name.upper()}: Insufficient data (needs at least {len(WMA_WEIGHTS)} months).\n"
            continue

        history = branch_df["total_sales"].tolist()
        predictions = _project_monthly_sales(history, forecast_horizon)
        history_steps = list(range(1, len(history) + 1))
        future_steps = list(range(len(history) + 1, len(history) + forecast_horizon + 1))

        report += f"   * {branch_name.upper()}:\n"
        for step, value in zip(future_steps, predictions, strict=True):
            report += f"       - Month {step}: ~{value:,.2f} projected units\n"

        plot_data[branch_name] = {
            "X_train": history_steps,
            "y_train": history,
            "X_future": future_steps,
            "predictions": predictions,
            "max_historical_month": len(history),
        }

    report += "\n" + "=" * 80 + "\n"
    report += "AGENT VERDICT: RESOURCE ALLOCATION\n"
    report += "Forecast utilizes a Weighted Moving Average to establish a stable, conservative operational baseline.\n"
    report += "=" * 80 + "\n"
    return report, plot_data


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    processed_path = Path("backend") / "data" / "processed"
    final_report, plotting_data = forecast_future_demand_wma(processed_path)
    print(final_report)

    if plotting_data:
        plt.figure(figsize=(12, 7))
        for branch_name, data in plotting_data.items():
            x_train = data["X_train"]
            y_train = data["y_train"]
            x_future = data["X_future"]
            predictions = data["predictions"]
            max_historical_month = data["max_historical_month"]

            plt.plot(x_train, y_train, marker="o", alpha=0.6, label=f"History ({branch_name})")
            plt.plot(x_future, predictions, marker="x", linestyle="--", linewidth=2.0, label=f"WMA ({branch_name})")
            plt.plot([x_train[-1], x_future[0]], [y_train[-1], predictions[0]], linestyle="--", linewidth=1.5, alpha=0.5)
            plt.axvline(x=max_historical_month + 0.5, color="red", linestyle=":", linewidth=1.5)

        plt.title("3-Month WMA Operational Demand Forecast")
        plt.xlabel("Time (Months)")
        plt.ylabel("Total Sales / Output")
        plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.tight_layout()
        plt.show()
