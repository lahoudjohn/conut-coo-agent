from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from app.core.config import settings


HEADER_MARKERS = ("page", "printed", "generated", "report", "division")
PREFERRED_FILES = [
    "rep_s_00502",
    "rep_s_00191_smry",
    "rep_s_00334_1_smry",
    "rep_s_00150",
    "rep_s_00461",
]


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _normalize_column(name: str) -> str:
    cleaned = _normalize_text(name).lower()
    cleaned = cleaned.replace("%", "pct").replace("/", "_").replace("-", "_")
    cleaned = cleaned.replace("(", "").replace(")", "").replace(".", "")
    cleaned = "_".join(part for part in cleaned.split() if part)
    return cleaned or "unnamed"


def _is_marker_row(row: pd.Series) -> bool:
    joined = " ".join(_normalize_text(v).lower() for v in row.tolist() if _normalize_text(v))
    if not joined:
        return True
    return any(marker in joined for marker in HEADER_MARKERS)


def _is_repeated_header_row(row: pd.Series, columns: list[str]) -> bool:
    normalized_values = [_normalize_column(str(v)) for v in row.tolist()[: len(columns)]]
    return normalized_values == columns[: len(normalized_values)]


def _clean_frame(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_column(str(c)) for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]
    df = df.dropna(how="all")

    if df.empty:
        df["source_file"] = source_name
        return df

    keep_rows = []
    columns = list(df.columns)
    for _, row in df.iterrows():
        if _is_marker_row(row):
            continue
        if _is_repeated_header_row(row, columns):
            continue
        keep_rows.append(row)

    cleaned = pd.DataFrame(keep_rows, columns=columns) if keep_rows else pd.DataFrame(columns=columns)
    cleaned = cleaned.applymap(lambda v: _normalize_text(v) if pd.notna(v) else None)
    cleaned = cleaned.replace({"": None})
    cleaned = cleaned.dropna(how="all")
    cleaned["source_file"] = source_name
    return cleaned.reset_index(drop=True)


def read_report_csv(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(path, dtype=str, encoding="latin-1")
    return _clean_frame(df, path.stem.lower())


def ingest_all_raw_files(raw_dir: Path | None = None, processed_dir: Path | None = None) -> list[Path]:
    raw_dir = raw_dir or settings.raw_data_dir
    processed_dir = processed_dir or settings.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for csv_path in sorted(raw_dir.glob("*.csv")):
        cleaned = read_report_csv(csv_path)
        out_path = processed_dir / f"{csv_path.stem.lower()}.parquet"
        cleaned.to_parquet(out_path, index=False)
        written.append(out_path)

    return written


def list_processed_files(processed_dir: Path | None = None) -> list[Path]:
    processed_dir = processed_dir or settings.processed_data_dir
    return sorted(processed_dir.glob("*.parquet"))


def load_processed_frame(stem: str, processed_dir: Path | None = None) -> pd.DataFrame:
    processed_dir = processed_dir or settings.processed_data_dir
    path = processed_dir / f"{stem.lower()}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_best_available_frame(candidates: Iterable[str] | None = None) -> pd.DataFrame:
    candidates = list(candidates or PREFERRED_FILES)
    for stem in candidates:
        df = load_processed_frame(stem)
        if not df.empty:
            return df
    files = list_processed_files()
    if not files:
        return pd.DataFrame()
    return pd.read_parquet(files[0])
