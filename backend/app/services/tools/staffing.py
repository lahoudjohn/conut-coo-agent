from __future__ import annotations

import math
from datetime import date

from app.core.config import settings
from app.schemas.tools import StaffingRequest, ToolResponse
from app.services.features import build_branch_hourly_profile, summarize_branch_daily


SHIFT_WINDOWS = {
    "morning": (6, 11),
    "afternoon": (12, 16),
    "evening": (17, 22),
    "night": (23, 5),
}

SHIFT_SHARE_FALLBACK = {
    "morning": 0.28,
    "afternoon": 0.32,
    "evening": 0.30,
    "night": 0.10,
}


def _hour_in_shift(hour: int, shift: str) -> bool:
    start, end = SHIFT_WINDOWS[shift]
    if start <= end:
        return start <= hour <= end
    return hour >= start or hour <= end


def estimate_shift_staffing(payload: StaffingRequest) -> ToolResponse:
    daily_ctx = summarize_branch_daily()
    daily = daily_ctx.raw.copy()
    hourly_ctx = build_branch_hourly_profile()
    hourly = hourly_ctx.raw.copy()

    if not daily.empty:
        daily = daily[daily["branch_name"].astype(str).str.lower() == payload.branch.lower()]
    if not hourly.empty:
        hourly = hourly[hourly["branch_name"].astype(str).str.lower() == payload.branch.lower()]

    target_date = payload.target_date or date.today()

    if daily.empty:
        est_orders = 36
        employees = 2
        return ToolResponse(
            tool_name="estimate_staffing",
            result={
                "branch": payload.branch,
                "shift": payload.shift,
                "target_date": str(target_date),
                "estimated_orders": est_orders,
                "recommended_employees": employees,
                "staffing_band": {"min": employees, "max": employees + 1},
                "placeholder": True,
            },
            key_evidence_metrics={"avg_daily_orders": 0, "shift_share": SHIFT_SHARE_FALLBACK[payload.shift]},
            assumptions=[
                "No branch demand history found; placeholder staffing is returned.",
                "Orders per employee per shift default is configured in settings.",
            ],
            data_coverage_notes=daily_ctx.coverage_notes + hourly_ctx.coverage_notes,
        )

    avg_daily_orders = float(daily["order_count"].mean())
    shift_share = SHIFT_SHARE_FALLBACK[payload.shift]

    if not hourly.empty:
        total_orders = float(hourly["order_count"].sum()) or 1.0
        shift_orders = float(hourly[hourly["hour"].apply(lambda h: _hour_in_shift(int(h), payload.shift))]["order_count"].sum())
        shift_share = shift_orders / total_orders if shift_orders else shift_share

    est_orders = max(1, round(avg_daily_orders * shift_share))
    employees = max(2, math.ceil(est_orders / settings.default_orders_per_employee_per_shift))

    return ToolResponse(
        tool_name="estimate_staffing",
        result={
            "branch": payload.branch,
            "shift": payload.shift,
            "target_date": str(target_date),
            "estimated_orders": est_orders,
            "recommended_employees": employees,
            "staffing_band": {"min": max(2, employees - 1), "max": employees + 1},
        },
        key_evidence_metrics={
            "avg_daily_orders": round(avg_daily_orders, 2),
            "shift_share": round(shift_share, 3),
            "orders_per_employee_capacity": settings.default_orders_per_employee_per_shift,
        },
        assumptions=[
            "Staffing is sized from order volume, not labor-law scheduling constraints.",
            "Refine this with prep-time and attendance correlations using REP_S_00461 later.",
        ],
        data_coverage_notes=daily_ctx.coverage_notes + hourly_ctx.coverage_notes,
    )
