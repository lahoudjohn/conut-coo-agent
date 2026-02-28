from fastapi import HTTPException

from app.schemas.staffing import (
    ShiftLengthSummaryRequest,
    ShiftLengthSummaryResponse,
    StaffingBenchmarkRequest,
    StaffingBenchmarkResponse,
    StaffingRequest,
    StaffingResponse,
)
from app.tools.staffing import (
    build_branch_productivity,
    estimate_staffing,
    load_attendance,
    load_monthly_sales,
    rank_understaffed_branches,
    summarize_shift_lengths,
)


def estimate_shift_staffing(payload: StaffingRequest) -> StaffingResponse:
    attendance_df = load_attendance()
    monthly_sales_df = load_monthly_sales()
    productivity_df = build_branch_productivity(attendance_df, monthly_sales_df)

    try:
        result = estimate_staffing(payload, attendance_df, monthly_sales_df, productivity_df)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    return StaffingResponse(**result)


def benchmark_staffing_pressure(payload: StaffingBenchmarkRequest) -> StaffingBenchmarkResponse:
    attendance_df = load_attendance()
    monthly_sales_df = load_monthly_sales()
    productivity_df = build_branch_productivity(attendance_df, monthly_sales_df)

    try:
        result = rank_understaffed_branches(payload, attendance_df, monthly_sales_df, productivity_df)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    return StaffingBenchmarkResponse(**result)


def summarize_branch_shift_lengths(payload: ShiftLengthSummaryRequest) -> ShiftLengthSummaryResponse:
    attendance_df = load_attendance()

    try:
        result = summarize_shift_lengths(payload, attendance_df)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    return ShiftLengthSummaryResponse(**result)
