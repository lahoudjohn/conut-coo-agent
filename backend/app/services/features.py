from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.services.ingest import list_processed_files, load_best_available_frame, load_processed_frame

PRIMARY_CSV_CANDIDATES = [
    "REP_S_00502_obj1.csv",
    "REP_S_00502_cleaned_updated.csv",
    "REP_S_00502_cleaned.csv",
]

CATEGORY_ALIASES: dict[str, list[str]] = {
    "coffee": [
        "coffee",
        "latte",
        "espresso",
        "macchiato",
        "cappuccino",
        "mocha",
        "americano",
        "flat white",
        "cortado",
        "frappe",
    ],
    "milkshake": ["milkshake"],
}


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _to_numeric(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
        .replace("", pd.NA)
        .astype(float)
    )


@dataclass
class DataContext:
    raw: pd.DataFrame
    coverage_notes: list[str]
    placeholder_used: bool
    processed_files: list[str]


def _load_primary_csv_frame() -> tuple[pd.DataFrame, str | None]:
    for filename in PRIMARY_CSV_CANDIDATES:
        path = settings.processed_data_dir / filename
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:
            continue
        if not df.empty:
            return df, filename
    return pd.DataFrame(), None


def get_primary_dataset() -> DataContext:
    processed = list_processed_files()
    processed_names = [p.name for p in processed]
    if processed:
        sales_df = load_best_available_frame()
        if not sales_df.empty:
            coverage = [
                f"Loaded {len(sales_df):,} rows from processed cache.",
                f"Processed files available: {', '.join(processed_names)}",
            ]
            return DataContext(
                raw=sales_df.copy(),
                coverage_notes=coverage,
                placeholder_used=False,
                processed_files=processed_names,
            )

    csv_df, csv_name = _load_primary_csv_frame()
    if not csv_df.empty and csv_name:
        csv_files = sorted(path.name for path in settings.processed_data_dir.glob("*.csv"))
        coverage = [f"Loaded {len(csv_df):,} rows from processed CSV {csv_name}."]
        if csv_files:
            coverage.append(f"Processed CSV files available: {', '.join(csv_files)}")
        return DataContext(
            raw=csv_df.copy(),
            coverage_notes=coverage,
            placeholder_used=False,
            processed_files=csv_files,
        )

    coverage_notes = ["No processed parquet or supported CSV files found in backend/data/processed."]
    if processed_names:
        coverage_notes.append("Processed parquet files exist but the selected dataset is empty.")

    return DataContext(
        raw=pd.DataFrame(),
        coverage_notes=coverage_notes,
        placeholder_used=True,
        processed_files=processed_names,
    )


def build_transaction_frame() -> DataContext:
    ctx = get_primary_dataset()
    df = ctx.raw.copy()
    if df.empty:
        return ctx

    sellable_col = _find_column(df, ["is_sellable_item"])
    if sellable_col:
        sellable_mask = df[sellable_col].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
        if sellable_mask.any():
            df = df.loc[sellable_mask].copy()

    order_col = _find_column(df, ["order_id", "order_no", "order_number", "invoice_no", "check_no", "receipt_no", "bill_no"])
    item_col = _find_column(df, ["item_name", "item_name_normalized", "menu_item", "product_name", "item", "description"])
    branch_col = _find_column(df, ["branch", "branch_name", "store", "location"])
    qty_col = _find_column(df, ["line_qty", "qty", "quantity", "sold_qty", "item_qty"])
    amount_col = _find_column(df, ["line_amount", "net_sales", "sales", "amount", "total", "line_total"])
    customer_col = _find_column(df, ["customer", "customer_name", "customer_code"])
    date_col = _find_column(df, ["business_date", "date", "order_date", "created_at", "datetime", "from_date", "report_generated_date"])
    time_col = _find_column(df, ["time", "order_time", "created_time"])

    if amount_col and amount_col in df:
        df["amount_value"] = _to_numeric(df[amount_col]).fillna(0)
    else:
        df["amount_value"] = 0.0

    if qty_col and qty_col in df:
        df["qty_value"] = _to_numeric(df[qty_col]).fillna(1)
    else:
        df["qty_value"] = 1.0

    if date_col:
        date_str = df[date_col].astype(str)
        if time_col:
            date_str = date_str + " " + df[time_col].astype(str)
        df["event_ts"] = pd.to_datetime(date_str, errors="coerce")
    else:
        df["event_ts"] = pd.NaT

    df["order_id"] = df[order_col] if order_col else df.index.astype(str)
    df["item_name"] = df[item_col] if item_col else "unknown_item"
    df["branch_name"] = df[branch_col] if branch_col else "all_branches"
    df["customer_name"] = df[customer_col] if customer_col else None
    df["event_date"] = df["event_ts"].dt.date

    tx = df[
        ["order_id", "item_name", "branch_name", "qty_value", "amount_value", "customer_name", "event_ts", "event_date", "source_file"]
    ].copy()
    tx = tx.dropna(subset=["item_name"])
    ctx.raw = tx
    return ctx


def summarize_branch_daily() -> DataContext:
    ctx = build_transaction_frame()
    df = ctx.raw.copy()
    if df.empty:
        return ctx

    if df["event_date"].isna().all():
        synthetic_dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=min(len(df), 30))
        df = df.head(len(synthetic_dates)).copy()
        df["event_date"] = synthetic_dates.date
        ctx.coverage_notes.append("No reliable date column found; synthetic dates used for placeholder trending.")
        ctx.placeholder_used = True

    daily = (
        df.dropna(subset=["event_date"])
        .groupby(["branch_name", "event_date"], as_index=False)
        .agg(
            demand_units=("qty_value", "sum"),
            revenue_proxy=("amount_value", "sum"),
            line_count=("order_id", "count"),
            order_count=("order_id", pd.Series.nunique),
        )
    )
    ctx.raw = daily
    return ctx


def build_branch_hourly_profile() -> DataContext:
    ctx = build_transaction_frame()
    df = ctx.raw.copy()
    if df.empty:
        return ctx

    if df["event_ts"].isna().all():
        ctx.coverage_notes.append("No timestamps found; staffing will use shift heuristics instead of hourly evidence.")
        ctx.placeholder_used = True
        ctx.raw = pd.DataFrame()
        return ctx

    df["hour"] = df["event_ts"].dt.hour
    hourly = (
        df.dropna(subset=["hour"])
        .groupby(["branch_name", "hour"], as_index=False)
        .agg(order_count=("order_id", pd.Series.nunique), qty_units=("qty_value", "sum"))
    )
    ctx.raw = hourly
    return ctx


def load_monthly_branch_summary() -> pd.DataFrame:
    df = load_processed_frame("rep_s_00334_1_smry")
    if df.empty:
        csv_path = settings.processed_data_dir / "REP_S_00334_1_SMRY_cleaned.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, dtype=str)
    if df.empty:
        return pd.DataFrame()

    branch_col = _find_column(df, ["branch", "branch_name", "store", "location"])
    sales_col = _find_column(df, ["sales", "net_sales", "amount", "total"])
    month_col = _find_column(df, ["month", "period"])

    if not branch_col:
        return pd.DataFrame()

    out = pd.DataFrame({"branch_name": df[branch_col].fillna("unknown_branch")})
    out["period"] = df[month_col] if month_col else "unknown_period"
    out["sales_value"] = _to_numeric(df[sales_col]).fillna(0) if sales_col else 0
    return out


def category_keyword_share(categories: list[str]) -> tuple[pd.DataFrame, DataContext]:
    ctx = build_transaction_frame()
    df = ctx.raw.copy()
    if df.empty:
        return pd.DataFrame(), ctx

    lowered = df["item_name"].astype(str).str.lower()
    rows = []
    for category in categories:
        keywords = CATEGORY_ALIASES.get(category.lower(), [category.lower()])
        pattern = "|".join(pd.Series(keywords).map(lambda value: rf"\b{value}\b"))
        mask = lowered.str.contains(pattern, na=False, regex=True)
        rows.append(
            {
                "category": category,
                "lines": int(mask.sum()),
                "qty_units": float(df.loc[mask, "qty_value"].sum()),
                "revenue_proxy": float(df.loc[mask, "amount_value"].sum()),
            }
        )
    summary = pd.DataFrame(rows)
    return summary, ctx


def processed_data_path() -> Path:
    return settings.processed_data_dir
