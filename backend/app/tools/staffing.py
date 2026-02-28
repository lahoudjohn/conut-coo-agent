from __future__ import annotations

import calendar
import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.schemas.staffing import (
    ShiftLengthSummaryRequest,
    StaffingBenchmarkRequest,
    StaffingRequest,
)


DEFAULT_ATTENDANCE_PATH = settings.processed_data_dir / "REP_S_00461_cleaned.csv"
DEFAULT_MONTHLY_SALES_PATH = settings.processed_data_dir / "REP_S_00334_1_SMRY_cleaned.csv"
DAY_OF_WEEK_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAME_TO_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
SHIFT_SHARE_FALLBACK = 0.25


def _normalize_branch(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _month_to_number(value: object) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        month_num = int(float(text))
    except ValueError:
        month_num = None
    if month_num is not None and 1 <= month_num <= 12:
        return month_num
    return MONTH_NAME_TO_NUM.get(text[:3].lower())


def _parse_period_to_date(period_key: str | None) -> pd.Timestamp | None:
    if not period_key:
        return None
    try:
        return pd.Timestamp(f"{period_key}-01")
    except ValueError:
        return None


def _days_in_period(period_key: str | None) -> tuple[int, bool]:
    if not period_key:
        return 30, True
    try:
        year_text, month_text = period_key.split("-", 1)
        return calendar.monthrange(int(year_text), int(month_text))[1], False
    except (ValueError, IndexError):
        return 30, True


def _shift_from_hour(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour <= 23:
        return "evening"
    return "night"


def _resolve_branch_name(branch: str, available_branches: pd.Series) -> str | None:
    if available_branches.empty:
        return None
    normalized_requested = _normalize_branch(branch)
    normalized_available = available_branches.astype(str).map(_normalize_branch)
    exact = available_branches[normalized_available == normalized_requested]
    if not exact.empty:
        return str(exact.iloc[0])

    contains_request = normalized_available.str.contains(normalized_requested, regex=False)
    contained_in_request = pd.Series(
        [normalized_requested in value for value in normalized_available.tolist()],
        index=available_branches.index,
    )
    partial = available_branches[contains_request | contained_in_request]
    if len(partial) == 1:
        return str(partial.iloc[0])
    return None


def _prepare_attendance_base(attendance_df: pd.DataFrame) -> pd.DataFrame:
    if attendance_df.empty:
        prepared = pd.DataFrame(
            columns=[
                "employee_id",
                "employee_name",
                "branch",
                "punch_in_timestamp",
                "punch_out_timestamp",
                "work_duration_hours",
                "date_in",
                "hour_in",
                "day_of_week",
                "shift_name",
                "period_key",
            ]
        )
        prepared.attrs["rows_loaded"] = 0
        prepared.attrs["invalid_timestamp_rows_dropped"] = 0
        prepared.attrs["date_min"] = None
        prepared.attrs["date_max"] = None
        return prepared

    prepared = attendance_df.copy()
    prepared["punch_in_timestamp"] = pd.to_datetime(prepared.get("punch_in_timestamp"), errors="coerce")
    prepared["punch_out_timestamp"] = pd.to_datetime(prepared.get("punch_out_timestamp"), errors="coerce")
    prepared["work_duration_hours"] = pd.to_numeric(prepared.get("work_duration_hours"), errors="coerce")

    computed_hours = (prepared["punch_out_timestamp"] - prepared["punch_in_timestamp"]).dt.total_seconds() / 3600.0
    prepared["work_duration_hours"] = prepared["work_duration_hours"].fillna(computed_hours)
    prepared.loc[prepared["work_duration_hours"] <= 0, "work_duration_hours"] = computed_hours

    invalid_mask = (
        prepared["punch_in_timestamp"].isna()
        | prepared["punch_out_timestamp"].isna()
        | prepared["work_duration_hours"].isna()
        | (prepared["work_duration_hours"] <= 0)
    )
    invalid_count = int(invalid_mask.sum())
    prepared = prepared.loc[~invalid_mask].copy()

    prepared["date_in"] = prepared["punch_in_timestamp"].dt.date.astype(str)
    prepared["hour_in"] = prepared["punch_in_timestamp"].dt.hour.astype(int)
    prepared["day_of_week"] = prepared["punch_in_timestamp"].dt.strftime("%a")
    prepared["shift_name"] = prepared["hour_in"].map(_shift_from_hour)
    prepared["period_key"] = prepared["punch_in_timestamp"].dt.strftime("%Y-%m")
    prepared.attrs["rows_loaded"] = int(len(attendance_df))
    prepared.attrs["invalid_timestamp_rows_dropped"] = invalid_count
    prepared.attrs["date_min"] = prepared["date_in"].min() if not prepared.empty else None
    prepared.attrs["date_max"] = prepared["date_in"].max() if not prepared.empty else None
    return prepared


def load_attendance(cleaned_path: str | Path = DEFAULT_ATTENDANCE_PATH) -> pd.DataFrame:
    path = Path(cleaned_path)
    if not path.exists():
        empty = pd.DataFrame(
            columns=[
                "employee_id",
                "employee_name",
                "branch",
                "punch_in_timestamp",
                "punch_out_timestamp",
                "work_duration_seconds",
                "work_duration_hours",
                "overnight_shift",
                "source_file",
            ]
        )
        empty.attrs["source_path"] = str(path)
        return empty

    attendance_df = pd.read_csv(path)
    for column in ("work_duration_seconds", "work_duration_hours", "overnight_shift"):
        if column in attendance_df.columns:
            attendance_df[column] = pd.to_numeric(attendance_df[column], errors="coerce").fillna(0.0)
    attendance_df.attrs["source_path"] = str(path)
    return attendance_df


def load_monthly_sales(cleaned_path: str | Path = DEFAULT_MONTHLY_SALES_PATH) -> pd.DataFrame:
    path = Path(cleaned_path)
    if not path.exists():
        empty = pd.DataFrame(columns=["branch_name", "period_key", "period_date", "monthly_sales", "source_file"])
        empty.attrs["source_path"] = str(path)
        return empty

    sales_df = pd.read_csv(path).copy()
    sales_df["year"] = pd.to_numeric(sales_df.get("year"), errors="coerce")
    sales_df["month_num"] = sales_df.get("month").map(_month_to_number)
    sales_df["monthly_sales"] = pd.to_numeric(
        sales_df.get("monthly_sales", sales_df.get("total_sales")),
        errors="coerce",
    ).fillna(0.0)

    if "period_key" not in sales_df.columns:
        sales_df["period_key"] = None
    missing_period = sales_df["period_key"].isna() | sales_df["period_key"].astype(str).str.strip().eq("")
    sales_df.loc[missing_period, "period_key"] = sales_df.loc[missing_period].apply(
        lambda row: (
            f"{int(row['year']):04d}-{int(row['month_num']):02d}"
            if pd.notna(row["year"]) and pd.notna(row["month_num"])
            else None
        ),
        axis=1,
    )
    sales_df["period_date"] = pd.to_datetime(sales_df["period_key"] + "-01", errors="coerce")

    aggregated = (
        sales_df.dropna(subset=["branch_name", "period_key"])
        .groupby(["branch_name", "period_key"], as_index=False)
        .agg(
            period_date=("period_date", "first"),
            monthly_sales=("monthly_sales", "sum"),
            source_file=("source_file", "first"),
        )
    )
    aggregated.attrs["source_path"] = str(path)
    return aggregated


def build_shift_features(attendance_df: pd.DataFrame) -> pd.DataFrame:
    base = _prepare_attendance_base(attendance_df)
    if base.empty:
        features = pd.DataFrame(
            columns=[
                "branch",
                "shift_name",
                "day_of_week",
                "avg_labor_hours_per_day_shift",
                "avg_headcount_per_day_shift",
                "p50_labor_hours_per_day_shift",
                "p90_labor_hours_per_day_shift",
                "observed_days",
            ]
        )
        features.attrs.update(base.attrs)
        return features

    daily = (
        base.groupby(["branch", "date_in", "day_of_week", "shift_name"], as_index=False)
        .agg(
            labor_hours_per_day_shift=("work_duration_hours", "sum"),
            headcount_per_day_shift=("employee_id", pd.Series.nunique),
        )
    )
    by_day = (
        daily.groupby(["branch", "shift_name", "day_of_week"], as_index=False)
        .agg(
            avg_labor_hours_per_day_shift=("labor_hours_per_day_shift", "mean"),
            avg_headcount_per_day_shift=("headcount_per_day_shift", "mean"),
            p50_labor_hours_per_day_shift=("labor_hours_per_day_shift", lambda s: float(s.quantile(0.5))),
            p90_labor_hours_per_day_shift=("labor_hours_per_day_shift", lambda s: float(s.quantile(0.9))),
            observed_days=("date_in", pd.Series.nunique),
        )
    )
    all_days = (
        daily.groupby(["branch", "shift_name"], as_index=False)
        .agg(
            avg_labor_hours_per_day_shift=("labor_hours_per_day_shift", "mean"),
            avg_headcount_per_day_shift=("headcount_per_day_shift", "mean"),
            p50_labor_hours_per_day_shift=("labor_hours_per_day_shift", lambda s: float(s.quantile(0.5))),
            p90_labor_hours_per_day_shift=("labor_hours_per_day_shift", lambda s: float(s.quantile(0.9))),
            observed_days=("date_in", pd.Series.nunique),
        )
    )
    all_days["day_of_week"] = "All"
    features = pd.concat([all_days, by_day], ignore_index=True, sort=False)
    features["day_of_week"] = features["day_of_week"].astype(str)
    features.attrs.update(base.attrs)
    features.attrs["daily_shift_rows"] = int(len(daily))
    return features


def build_branch_productivity(attendance_df: pd.DataFrame, monthly_sales_df: pd.DataFrame) -> pd.DataFrame:
    base = _prepare_attendance_base(attendance_df)
    if base.empty:
        productivity_df = pd.DataFrame(
            columns=[
                "branch",
                "labor_period_key",
                "labor_period_date",
                "total_labor_hours_month",
                "sales_period_key_used",
                "monthly_sales",
                "productivity_sales_per_labor_hour",
                "exact_period_match",
            ]
        )
        productivity_df.attrs["global_productivity"] = None
        return productivity_df

    labor_monthly = (
        base.groupby(["branch", "period_key"], as_index=False)
        .agg(total_labor_hours_month=("work_duration_hours", "sum"))
    )
    labor_monthly["labor_period_date"] = pd.to_datetime(labor_monthly["period_key"] + "-01", errors="coerce")

    rows: list[dict[str, Any]] = []
    for row in labor_monthly.itertuples(index=False):
        branch_sales = monthly_sales_df[
            monthly_sales_df["branch_name"].astype(str).map(_normalize_branch) == _normalize_branch(row.branch)
        ].copy()
        selected_sales = None
        if not branch_sales.empty:
            exact = branch_sales[branch_sales["period_key"] == row.period_key]
            if not exact.empty:
                selected_sales = exact.sort_values("period_date").iloc[-1]
            else:
                branch_sales["period_distance_days"] = (
                    branch_sales["period_date"] - row.labor_period_date
                ).abs().dt.days
                selected_sales = branch_sales.sort_values(["period_distance_days", "period_date"]).iloc[0]

        monthly_sales = float(selected_sales["monthly_sales"]) if selected_sales is not None else None
        productivity = (
            monthly_sales / float(row.total_labor_hours_month)
            if monthly_sales is not None and row.total_labor_hours_month > 0
            else None
        )
        rows.append(
            {
                "branch": row.branch,
                "labor_period_key": row.period_key,
                "labor_period_date": row.labor_period_date,
                "total_labor_hours_month": float(row.total_labor_hours_month),
                "sales_period_key_used": str(selected_sales["period_key"]) if selected_sales is not None else None,
                "sales_period_date_used": selected_sales["period_date"] if selected_sales is not None else None,
                "monthly_sales": monthly_sales,
                "productivity_sales_per_labor_hour": productivity,
                "exact_period_match": bool(selected_sales is not None and selected_sales["period_key"] == row.period_key),
            }
        )

    productivity_df = pd.DataFrame(rows)
    valid = productivity_df.dropna(subset=["productivity_sales_per_labor_hour"])
    if not valid.empty:
        total_sales = valid["monthly_sales"].sum()
        total_labor = valid["total_labor_hours_month"].sum()
        global_productivity = float(total_sales / total_labor) if total_labor > 0 else None
    else:
        global_productivity = None
    productivity_df.attrs["global_productivity"] = global_productivity
    productivity_df.attrs["period_min"] = productivity_df["labor_period_key"].min() if not productivity_df.empty else None
    productivity_df.attrs["period_max"] = productivity_df["labor_period_key"].max() if not productivity_df.empty else None
    return productivity_df


def _select_sales_row(branch_sales: pd.DataFrame, target_period: str | None) -> tuple[pd.Series | None, list[str]]:
    notes: list[str] = []
    if branch_sales.empty:
        return None, notes
    branch_sales = branch_sales.sort_values("period_date").reset_index(drop=True)
    if target_period:
        exact = branch_sales[branch_sales["period_key"] == target_period]
        if not exact.empty:
            return exact.iloc[-1], notes
        target_date = _parse_period_to_date(target_period)
        if target_date is not None:
            branch_sales = branch_sales.assign(
                period_distance_days=(branch_sales["period_date"] - target_date).abs().dt.days
            )
            chosen = branch_sales.sort_values(["period_distance_days", "period_date"]).iloc[0]
            notes.append(f"Requested target_period '{target_period}' was unavailable; used closest sales period '{chosen['period_key']}'.")
            return chosen, notes
    chosen = branch_sales.iloc[-1]
    if target_period:
        notes.append("Target period format was invalid, so the latest available branch sales period was used.")
    else:
        notes.append(f"No target_period provided; used latest branch sales period '{chosen['period_key']}'.")
    return chosen, notes


def _select_productivity_row(branch_productivity: pd.DataFrame, target_period: str | None) -> tuple[pd.Series | None, list[str]]:
    notes: list[str] = []
    valid = branch_productivity.dropna(subset=["productivity_sales_per_labor_hour"]).sort_values("labor_period_date")
    if valid.empty:
        return None, notes
    if target_period:
        exact = valid[valid["labor_period_key"] == target_period]
        if not exact.empty:
            return exact.iloc[-1], notes
        target_date = _parse_period_to_date(target_period)
        if target_date is not None:
            valid = valid.assign(
                period_distance_days=(valid["labor_period_date"] - target_date).abs().dt.days
            )
            chosen = valid.sort_values(["period_distance_days", "labor_period_date"]).iloc[0]
            notes.append(
                f"Requested target_period '{target_period}' had no exact productivity row; used closest labor period '{chosen['labor_period_key']}'."
            )
            return chosen, notes
    chosen = valid.iloc[-1]
    if target_period:
        notes.append("Target period format was invalid, so the latest available branch productivity row was used.")
    else:
        notes.append(f"No target_period provided; used latest productivity row '{chosen['labor_period_key']}'.")
    return chosen, notes


def estimate_staffing(
    request: StaffingRequest,
    attendance_df: pd.DataFrame,
    monthly_sales_df: pd.DataFrame,
    productivity_df: pd.DataFrame,
) -> dict[str, Any]:
    shift_features = build_shift_features(attendance_df)
    available_branches = attendance_df.get("branch", pd.Series(dtype=str)).dropna().astype(str).drop_duplicates()
    resolved_branch = _resolve_branch_name(request.branch, available_branches)
    if not resolved_branch:
        raise ValueError(f"Branch '{request.branch}' not found in attendance data.")

    assumptions = [
        "Values are scaled units, so staffing recommendations rely on relative productivity rather than absolute currency.",
        "Limited history and monthly sales granularity may reduce precision for shift-level staffing decisions.",
        "Shift definitions are based on punch-in time buckets: morning 06:00-12:00, afternoon 12:00-18:00, evening 18:00-23:59, night 00:00-06:00.",
    ]

    branch_sales = monthly_sales_df[
        monthly_sales_df["branch_name"].astype(str).map(_normalize_branch) == _normalize_branch(resolved_branch)
    ].copy()
    branch_productivity = productivity_df[
        productivity_df["branch"].astype(str).map(_normalize_branch) == _normalize_branch(resolved_branch)
    ].copy()
    branch_features = shift_features[
        shift_features["branch"].astype(str).map(_normalize_branch) == _normalize_branch(resolved_branch)
    ].copy()
    if branch_features.empty:
        raise ValueError(f"Branch '{request.branch}' has no valid attendance rows after timestamp cleaning.")

    fallback_notes: list[str] = []
    if request.demand_override is not None:
        demand_used = float(request.demand_override)
        sales_period_used = request.target_period or (branch_sales["period_key"].max() if not branch_sales.empty else None)
        fallback_notes.append("Demand override was provided, so monthly sales were not used to set demand.")
    else:
        sales_row, sales_notes = _select_sales_row(branch_sales, request.target_period)
        fallback_notes.extend(sales_notes)
        if sales_row is not None:
            demand_used = float(sales_row["monthly_sales"])
            sales_period_used = str(sales_row["period_key"])
        elif not monthly_sales_df.empty:
            global_sales = monthly_sales_df.sort_values("period_date").iloc[-1]
            demand_used = float(global_sales["monthly_sales"])
            sales_period_used = str(global_sales["period_key"])
            assumptions.append(
                f"No monthly sales were found for branch '{resolved_branch}', so the latest global sales period '{sales_period_used}' was used as the demand proxy."
            )
        else:
            raise ValueError("Monthly sales data is unavailable, so demand could not be estimated.")

    productivity_row, productivity_notes = _select_productivity_row(branch_productivity, request.target_period)
    fallback_notes.extend(productivity_notes)
    productivity_source = "branch"
    if productivity_row is not None:
        productivity_value = float(productivity_row["productivity_sales_per_labor_hour"])
        productivity_period_used = str(productivity_row["labor_period_key"])
    else:
        productivity_value = productivity_df.attrs.get("global_productivity")
        productivity_period_used = None
        productivity_source = "global_fallback"
        if productivity_value is None or productivity_value <= 0:
            raise ValueError("Productivity could not be computed from attendance and monthly sales.")
        assumptions.append(
            f"Branch-specific productivity was unavailable for '{resolved_branch}', so global productivity across all branches was used."
        )

    period_for_days = request.target_period or sales_period_used or productivity_period_used
    days_in_period, assumed_30_days = _days_in_period(period_for_days)
    if assumed_30_days:
        assumptions.append("A 30-day month was assumed because the requested or inferred period was unavailable or invalid.")

    day_scope = request.day_of_week or "All"
    if request.day_of_week:
        scoped_features = branch_features[branch_features["day_of_week"] == request.day_of_week].copy()
        if scoped_features.empty:
            scoped_features = branch_features[branch_features["day_of_week"] == "All"].copy()
            day_scope = "All"
            assumptions.append(
                f"No attendance history was available for day_of_week '{request.day_of_week}', so all-day shift averages were used."
            )
    else:
        scoped_features = branch_features[branch_features["day_of_week"] == "All"].copy()

    requested_shift = scoped_features[scoped_features["shift_name"] == request.shift_name].copy()
    if requested_shift.empty:
        shift_share = SHIFT_SHARE_FALLBACK
        avg_labor_hours = None
        avg_headcount = None
        p50_labor = None
        p90_labor = None
        observed_days = 0
        assumptions.append(
            f"No attendance history was available for branch '{resolved_branch}' and shift '{request.shift_name}', so an equal 25% shift split was used."
        )
    else:
        total_avg_labor = float(scoped_features["avg_labor_hours_per_day_shift"].sum())
        avg_labor_hours = float(requested_shift["avg_labor_hours_per_day_shift"].iloc[0])
        avg_headcount = float(requested_shift["avg_headcount_per_day_shift"].iloc[0])
        p50_labor = float(requested_shift["p50_labor_hours_per_day_shift"].iloc[0])
        p90_labor = float(requested_shift["p90_labor_hours_per_day_shift"].iloc[0])
        observed_days = int(requested_shift["observed_days"].iloc[0])
        shift_share = avg_labor_hours / total_avg_labor if total_avg_labor > 0 else SHIFT_SHARE_FALLBACK
        if total_avg_labor <= 0:
            assumptions.append("Historical shift labor totals were zero, so an equal 25% shift split was used.")

    required_labor_hours_month = float(demand_used / productivity_value)
    required_labor_hours_per_day_all = required_labor_hours_month / days_in_period
    required_labor_hours = required_labor_hours_per_day_all * shift_share
    required_staff_raw = required_labor_hours / max(request.shift_hours, 0.1)
    recommended_staff = max(1, math.ceil(required_staff_raw * (1.0 + request.buffer_pct)))

    branch_attendance_base = _prepare_attendance_base(attendance_df)
    branch_attendance_base = branch_attendance_base[
        branch_attendance_base["branch"].astype(str).map(_normalize_branch) == _normalize_branch(resolved_branch)
    ]

    return {
        "branch": resolved_branch,
        "shift_name": request.shift_name,
        "recommended_staff": recommended_staff,
        "required_labor_hours": round(required_labor_hours, 2),
        "productivity_sales_per_labor_hour": round(float(productivity_value), 4),
        "demand_used": round(demand_used, 2),
        "evidence": {
            "productivity_source": productivity_source,
            "productivity_period_used": productivity_period_used,
            "sales_period_used": sales_period_used,
            "historical_day_scope_used": day_scope,
            "historical_avg_labor_hours_per_day_shift": round(avg_labor_hours, 2) if avg_labor_hours is not None else None,
            "historical_avg_headcount_per_day_shift": round(avg_headcount, 2) if avg_headcount is not None else None,
            "historical_p50_labor_hours_per_day_shift": round(p50_labor, 2) if p50_labor is not None else None,
            "historical_p90_labor_hours_per_day_shift": round(p90_labor, 2) if p90_labor is not None else None,
            "historical_observed_days": observed_days,
            "shift_share_used": round(shift_share, 4),
            "days_in_period_used": days_in_period,
            "required_labor_hours_month": round(required_labor_hours_month, 2),
            "required_labor_hours_per_day_all_shifts": round(required_labor_hours_per_day_all, 2),
            "required_staff_raw": round(required_staff_raw, 2),
            "buffer_pct_used": request.buffer_pct,
            "recent_monthly_sales_used": round(demand_used, 2),
            "fallback_notes": fallback_notes,
        },
        "assumptions": assumptions,
        "data_coverage": {
            "attendance_source_path": attendance_df.attrs.get("source_path"),
            "attendance_rows_loaded": int(attendance_df.attrs.get("rows_loaded", len(attendance_df))),
            "attendance_rows_used_for_branch": int(len(branch_attendance_base)),
            "attendance_invalid_rows_dropped": int(shift_features.attrs.get("invalid_timestamp_rows_dropped", 0)),
            "attendance_date_min": shift_features.attrs.get("date_min"),
            "attendance_date_max": shift_features.attrs.get("date_max"),
            "shift_feature_rows_for_branch": int(len(branch_features)),
            "sales_source_path": monthly_sales_df.attrs.get("source_path"),
            "sales_rows_loaded": int(len(monthly_sales_df)),
            "sales_period_min": monthly_sales_df["period_key"].min() if not monthly_sales_df.empty else None,
            "sales_period_max": monthly_sales_df["period_key"].max() if not monthly_sales_df.empty else None,
            "productivity_rows_for_branch": int(len(branch_productivity)),
            "global_productivity_available": productivity_df.attrs.get("global_productivity") is not None,
        },
    }


def rank_understaffed_branches(
    request: StaffingBenchmarkRequest,
    attendance_df: pd.DataFrame,
    monthly_sales_df: pd.DataFrame,
    productivity_df: pd.DataFrame,
) -> dict[str, Any]:
    available_branches = sorted(attendance_df.get("branch", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    if not available_branches:
        raise ValueError("Attendance data is unavailable, so branches cannot be benchmarked.")

    ranked_rows: list[dict[str, Any]] = []
    fallback_count = 0
    for branch in available_branches:
        branch_request = StaffingRequest(
            branch=branch,
            target_period=request.target_period,
            day_of_week=request.day_of_week,
            shift_name=request.shift_name,
            shift_hours=request.shift_hours,
            buffer_pct=request.buffer_pct,
            demand_override=request.demand_override,
        )
        branch_result = estimate_staffing(branch_request, attendance_df, monthly_sales_df, productivity_df)
        evidence = branch_result["evidence"]
        historical_headcount = float(evidence["historical_avg_headcount_per_day_shift"] or 0.0)
        recommended_staff = int(branch_result["recommended_staff"])
        headcount_gap = round(recommended_staff - historical_headcount, 2)
        gap_ratio = round(headcount_gap / max(historical_headcount, 1.0), 4)
        if evidence.get("productivity_source") == "global_fallback":
            fallback_count += 1

        ranked_rows.append(
            {
                "branch": branch_result["branch"],
                "recommended_staff": recommended_staff,
                "historical_avg_headcount": round(historical_headcount, 2),
                "headcount_gap": headcount_gap,
                "headcount_gap_ratio": gap_ratio,
                "demand_used": branch_result["demand_used"],
                "productivity_sales_per_labor_hour": branch_result["productivity_sales_per_labor_hour"],
                "required_labor_hours": branch_result["required_labor_hours"],
                "sales_period_used": evidence.get("sales_period_used"),
                "productivity_period_used": evidence.get("productivity_period_used"),
            }
        )

    ranked_rows.sort(
        key=lambda row: (row["headcount_gap"], row["demand_used"], -row["productivity_sales_per_labor_hour"]),
        reverse=True,
    )
    top_rows = ranked_rows[: request.top_n]

    return {
        "shift_name": request.shift_name,
        "target_period": request.target_period,
        "branches_ranked": top_rows,
        "evidence": {
            "branches_evaluated": len(ranked_rows),
            "top_n": request.top_n,
            "day_of_week_used": request.day_of_week or "All",
            "buffer_pct_used": request.buffer_pct,
            "demand_override_used": request.demand_override is not None,
            "global_productivity_fallback_count": fallback_count,
        },
        "assumptions": [
            "Branches are ranked by the gap between recommended staff and historical average headcount for the requested shift.",
            "A positive headcount_gap indicates the branch is likely understaffed relative to its sales-driven labor requirement.",
            "Values are scaled units, so comparisons reflect relative staffing pressure rather than absolute labor cost.",
            "Shift definitions are based on punch-in time buckets.",
        ],
        "data_coverage": {
            "attendance_rows_loaded": int(attendance_df.attrs.get("rows_loaded", len(attendance_df))),
            "attendance_source_path": attendance_df.attrs.get("source_path"),
            "sales_rows_loaded": int(len(monthly_sales_df)),
            "sales_source_path": monthly_sales_df.attrs.get("source_path"),
            "branches_in_attendance": len(available_branches),
            "benchmark_period_requested": request.target_period,
        },
    }


def summarize_shift_lengths(
    request: ShiftLengthSummaryRequest,
    attendance_df: pd.DataFrame,
) -> dict[str, Any]:
    base = _prepare_attendance_base(attendance_df)
    if base.empty:
        raise ValueError("Attendance data is unavailable, so shift lengths cannot be summarized.")

    branch_filter = None
    if request.branch:
        resolved_branch = _resolve_branch_name(
            request.branch,
            base["branch"].dropna().astype(str).drop_duplicates(),
        )
        if not resolved_branch:
            raise ValueError(f"Branch '{request.branch}' not found in attendance data.")
        branch_filter = resolved_branch
        base = base[base["branch"].astype(str).map(_normalize_branch) == _normalize_branch(resolved_branch)].copy()

    if request.shift_name:
        base = base[base["shift_name"] == request.shift_name].copy()
    if request.day_of_week:
        base = base[base["day_of_week"] == request.day_of_week].copy()

    if base.empty:
        raise ValueError("No attendance rows matched the requested branch/shift filters.")

    branch_stats = (
        base.groupby("branch", as_index=False)
        .agg(
            average_shift_length_hours=("work_duration_hours", "mean"),
            median_shift_length_hours=("work_duration_hours", "median"),
            p90_shift_length_hours=("work_duration_hours", lambda s: float(s.quantile(0.9))),
            shift_count=("employee_id", "count"),
            unique_employees=("employee_id", pd.Series.nunique),
        )
        .sort_values("average_shift_length_hours", ascending=False)
    )
    branch_stats = branch_stats.round(
        {
            "average_shift_length_hours": 2,
            "median_shift_length_hours": 2,
            "p90_shift_length_hours": 2,
        }
    )

    return {
        "branch_filter": branch_filter,
        "shift_name": request.shift_name,
        "average_shift_length_hours": round(float(base["work_duration_hours"].mean()), 2),
        "branch_stats": branch_stats.to_dict(orient="records"),
        "evidence": {
            "median_shift_length_hours": round(float(base["work_duration_hours"].median()), 2),
            "p90_shift_length_hours": round(float(base["work_duration_hours"].quantile(0.9)), 2),
            "shift_count": int(len(base)),
            "unique_employees": int(base["employee_id"].nunique()),
            "day_of_week_used": request.day_of_week or "All",
        },
        "assumptions": [
            "Average shift length is measured from cleaned attendance work_duration_hours values.",
            "Shift bucket filters are based on punch-in time, not mid-shift overlap.",
            "This is descriptive summary logic, not a predictive model.",
        ],
        "data_coverage": {
            "attendance_rows_loaded": int(attendance_df.attrs.get("rows_loaded", len(attendance_df))),
            "attendance_invalid_rows_dropped": int(base.attrs.get("invalid_timestamp_rows_dropped", 0)),
            "attendance_source_path": attendance_df.attrs.get("source_path"),
            "attendance_date_min": base.attrs.get("date_min"),
            "attendance_date_max": base.attrs.get("date_max"),
            "branch_filter_applied": branch_filter,
        },
    }
