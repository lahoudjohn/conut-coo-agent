from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StaffingRequest(BaseModel):
    branch: str = Field(..., description="Branch to estimate staffing for.")
    target_period: str | None = Field(
        default=None,
        description="Optional target month in YYYY-MM format.",
        pattern=r"^\d{4}-\d{2}$",
    )
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] | None = Field(
        default=None,
        description="Optional day-of-week filter for more specific staffing estimates.",
    )
    shift_name: Literal["morning", "afternoon", "evening", "night"] = Field(
        ...,
        description="Shift bucket based on punch-in time.",
    )
    shift_hours: float = Field(default=8.0, gt=0, le=24)
    buffer_pct: float = Field(default=0.15, ge=0, le=1)
    demand_override: float | None = Field(default=None, ge=0)


class StaffingResponse(BaseModel):
    branch: str
    shift_name: str
    recommended_staff: int
    required_labor_hours: float
    productivity_sales_per_labor_hour: float
    demand_used: float
    evidence: dict[str, Any]
    assumptions: list[str]
    data_coverage: dict[str, Any]


class StaffingBenchmarkRequest(BaseModel):
    target_period: str | None = Field(
        default=None,
        description="Optional target month in YYYY-MM format.",
        pattern=r"^\d{4}-\d{2}$",
    )
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] | None = Field(
        default=None,
        description="Optional day-of-week filter for more specific staffing comparisons.",
    )
    shift_name: Literal["morning", "afternoon", "evening", "night"] = Field(
        default="evening",
        description="Shift bucket used for cross-branch staffing comparisons.",
    )
    shift_hours: float = Field(default=8.0, gt=0, le=24)
    buffer_pct: float = Field(default=0.15, ge=0, le=1)
    demand_override: float | None = Field(default=None, ge=0)
    top_n: int = Field(default=5, ge=1, le=20)


class StaffingBenchmarkResponse(BaseModel):
    shift_name: str
    target_period: str | None = None
    branches_ranked: list[dict[str, Any]]
    evidence: dict[str, Any]
    assumptions: list[str]
    data_coverage: dict[str, Any]


class ShiftLengthSummaryRequest(BaseModel):
    branch: str | None = Field(default=None, description="Optional branch filter.")
    shift_name: Literal["morning", "afternoon", "evening", "night"] | None = Field(
        default=None,
        description="Optional shift filter.",
    )
    day_of_week: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] | None = Field(
        default=None,
        description="Optional day-of-week filter.",
    )


class ShiftLengthSummaryResponse(BaseModel):
    branch_filter: str | None = None
    shift_name: str | None = None
    average_shift_length_hours: float
    branch_stats: list[dict[str, Any]]
    evidence: dict[str, Any]
    assumptions: list[str]
    data_coverage: dict[str, Any]
