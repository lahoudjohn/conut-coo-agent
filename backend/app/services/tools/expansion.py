from __future__ import annotations

from app.schemas.tools import ExpansionRequest, ToolResponse
from app.services.features import load_monthly_branch_summary, summarize_branch_daily


def score_expansion_feasibility(payload: ExpansionRequest) -> ToolResponse:
    daily_ctx = summarize_branch_daily()
    daily = daily_ctx.raw.copy()
    monthly = load_monthly_branch_summary()

    if daily.empty:
        return ToolResponse(
            tool_name="expansion_feasibility",
            result={
                "candidate_location": payload.candidate_location,
                "feasibility_score": 62,
                "recommendation": "conditional_go",
                "benchmark_branches": [],
            },
            key_evidence_metrics={"branches_analyzed": 0, "median_revenue_proxy": 0},
            assumptions=[
                "No benchmark branch data was available; placeholder score is used.",
                "Score should be replaced with a real geo-demand model if external location data is later allowed.",
            ],
            data_coverage_notes=daily_ctx.coverage_notes,
        )

    branch_summary = (
        daily.groupby("branch_name", as_index=False)
        .agg(
            avg_daily_demand=("demand_units", "mean"),
            avg_daily_revenue=("revenue_proxy", "mean"),
            active_days=("event_date", "nunique"),
        )
    )

    if not monthly.empty:
        monthly_branch = monthly.groupby("branch_name", as_index=False).agg(monthly_sales=("sales_value", "mean"))
        branch_summary = branch_summary.merge(monthly_branch, how="left", on="branch_name")
        branch_summary["monthly_sales"] = branch_summary["monthly_sales"].fillna(branch_summary["avg_daily_revenue"] * 30)
    else:
        branch_summary["monthly_sales"] = branch_summary["avg_daily_revenue"] * 30

    for col in ["avg_daily_demand", "avg_daily_revenue", "monthly_sales"]:
        max_val = branch_summary[col].max() or 1
        branch_summary[f"{col}_score"] = branch_summary[col] / max_val

    branch_summary["composite_score"] = (
        branch_summary["avg_daily_demand_score"] * 0.4
        + branch_summary["avg_daily_revenue_score"] * 0.35
        + branch_summary["monthly_sales_score"] * 0.25
    )

    top_benchmarks = branch_summary.sort_values("composite_score", ascending=False).head(3)
    feasibility = float(top_benchmarks["composite_score"].mean() * 100)
    recommendation = "go" if feasibility >= 75 else "conditional_go" if feasibility >= 55 else "hold"

    return ToolResponse(
        tool_name="expansion_feasibility",
        result={
            "candidate_location": payload.candidate_location,
            "target_region": payload.target_region,
            "feasibility_score": round(feasibility, 2),
            "recommendation": recommendation,
            "benchmark_branches": top_benchmarks[
                ["branch_name", "avg_daily_demand", "avg_daily_revenue", "composite_score"]
            ].to_dict(orient="records"),
        },
        key_evidence_metrics={
            "branches_analyzed": int(len(branch_summary)),
            "median_revenue_proxy": round(float(branch_summary["avg_daily_revenue"].median()), 2),
        },
        assumptions=[
            "Without external geo data, feasibility is a benchmark score against strongest existing branches.",
            "Recommendation is directional and should be paired with rent/footfall checks outside this dataset.",
        ],
        data_coverage_notes=daily_ctx.coverage_notes,
    )
