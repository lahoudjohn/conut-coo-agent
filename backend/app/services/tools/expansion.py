from __future__ import annotations

import pandas as pd

from app.core.config import settings
from app.schemas.tools import ExpansionRequest, ToolResponse


MONTHLY_SALES_PATH = settings.processed_data_dir / "REP_S_00334_1_SMRY_cleaned.csv"
TAX_SUMMARY_PATH = settings.processed_data_dir / "REP_S_00194_SMRY_cleaned.csv"


def _normalize_branch(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _normalize_series(series: pd.Series) -> pd.Series:
    return series.astype(str).map(_normalize_branch)


def _normalize_score(series: pd.Series, inverse: bool = False) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=float)
    min_val = float(series.min())
    max_val = float(series.max())
    if max_val == min_val:
        base = pd.Series([1.0] * len(series), index=series.index)
    else:
        base = (series - min_val) / (max_val - min_val)
    return 1 - base if inverse else base


def _load_monthly_sales() -> pd.DataFrame:
    if not MONTHLY_SALES_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(MONTHLY_SALES_PATH).copy()
    df["total_sales"] = pd.to_numeric(df.get("total_sales"), errors="coerce")
    df["period_key"] = df.get("period_key")
    df = df.dropna(subset=["branch_name", "total_sales"]).copy()
    if "period_key" in df.columns:
        df["period_date"] = pd.to_datetime(df["period_key"].astype(str) + "-01", errors="coerce")
    else:
        df["period_date"] = pd.NaT
    return df


def _load_tax_summary() -> pd.DataFrame:
    if not TAX_SUMMARY_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(TAX_SUMMARY_PATH).copy()
    if "total" in df.columns:
        df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0.0)
    return df


def score_expansion_feasibility(payload: ExpansionRequest) -> ToolResponse:
    monthly_df = _load_monthly_sales()
    if monthly_df.empty:
        return ToolResponse(
            tool_name="expansion_feasibility",
            result={
                "candidate_location": payload.candidate_location,
                "target_region": payload.target_region,
                "feasibility_score": 0,
                "recommendation": "hold",
                "benchmark_branches": [],
            },
            key_evidence_metrics={"branches_analyzed": 0, "median_monthly_sales": 0},
            assumptions=[
                "Expansion scoring requires monthly branch sales history.",
            ],
            data_coverage_notes=[f"{MONTHLY_SALES_PATH.name} was not found in backend/data/processed."],
        )

    tax_df = _load_tax_summary()
    branch_summary = (
        monthly_df.groupby("branch_name", as_index=False)
        .agg(
            avg_monthly_sales=("total_sales", "mean"),
            sales_volatility=("total_sales", lambda s: float(s.std(ddof=0)) if len(s) > 1 else 0.0),
            last_month_sales=("total_sales", "last"),
            months_observed=("period_key", "nunique"),
        )
    )

    sorted_monthly = monthly_df.sort_values(["branch_name", "period_date"]).copy()
    sorted_monthly["mom_growth"] = sorted_monthly.groupby("branch_name")["total_sales"].pct_change()
    trend = (
        sorted_monthly.groupby("branch_name", as_index=False)["mom_growth"]
        .mean()
        .rename(columns={"mom_growth": "avg_mom_growth"})
    )
    trend["avg_mom_growth"] = trend["avg_mom_growth"].fillna(0.0)
    branch_summary = branch_summary.merge(trend, on="branch_name", how="left")

    if not tax_df.empty and {"branch_name", "total"}.issubset(tax_df.columns):
        tax_profile = tax_df.groupby("branch_name", as_index=False).agg(tax_index=("total", "mean"))
        branch_summary = branch_summary.merge(tax_profile, on="branch_name", how="left")
    else:
        branch_summary["tax_index"] = branch_summary["avg_monthly_sales"] * 0
    branch_summary["tax_index"] = branch_summary["tax_index"].fillna(0.0)

    branch_summary["growth_score"] = _normalize_score(branch_summary["avg_mom_growth"].fillna(0.0))
    branch_summary["stability_score"] = _normalize_score(branch_summary["sales_volatility"].fillna(0.0), inverse=True)
    branch_summary["scale_score"] = _normalize_score(branch_summary["avg_monthly_sales"].fillna(0.0))
    branch_summary["tax_score"] = _normalize_score(branch_summary["tax_index"].fillna(0.0))

    branch_summary["composite_score"] = (
        branch_summary["growth_score"] * 0.30
        + branch_summary["stability_score"] * 0.25
        + branch_summary["scale_score"] * 0.30
        + branch_summary["tax_score"] * 0.15
    )

    top_benchmarks = branch_summary.sort_values("composite_score", ascending=False).head(3).copy()
    feasibility = float(top_benchmarks["composite_score"].mean() * 100) if not top_benchmarks.empty else 0.0
    recommendation = "go" if feasibility >= 75 else "conditional_go" if feasibility >= 55 else "hold"

    return ToolResponse(
        tool_name="expansion_feasibility",
        result={
            "candidate_location": payload.candidate_location,
            "target_region": payload.target_region,
            "feasibility_score": round(feasibility, 2),
            "recommendation": recommendation,
            "benchmark_branches": top_benchmarks[
                [
                    "branch_name",
                    "avg_monthly_sales",
                    "avg_mom_growth",
                    "sales_volatility",
                    "composite_score",
                ]
            ].round(
                {
                    "avg_monthly_sales": 2,
                    "avg_mom_growth": 4,
                    "sales_volatility": 2,
                    "composite_score": 4,
                }
            ).to_dict(orient="records"),
        },
        key_evidence_metrics={
            "branches_analyzed": int(len(branch_summary)),
            "median_monthly_sales": round(float(branch_summary["avg_monthly_sales"].median()), 2),
            "top_branch_score": round(float(top_benchmarks["composite_score"].max() * 100), 2) if not top_benchmarks.empty else 0,
        },
        assumptions=[
            "Without external geo data, expansion feasibility is inferred by benchmarking existing branch growth, scale, and stability.",
            "Tax summary is used only as an internal density proxy when available.",
            "The recommendation is directional and should be paired with footfall, rent, and competitor checks before opening a new branch.",
        ],
        data_coverage_notes=[
            f"Loaded {len(monthly_df):,} monthly sales rows from {MONTHLY_SALES_PATH.name}.",
            f"Loaded {len(tax_df):,} tax summary rows from {TAX_SUMMARY_PATH.name}." if not tax_df.empty else f"{TAX_SUMMARY_PATH.name} was unavailable; tax proxy was omitted.",
            f"Computed branch benchmarks across {len(branch_summary):,} branches.",
        ],
    )
