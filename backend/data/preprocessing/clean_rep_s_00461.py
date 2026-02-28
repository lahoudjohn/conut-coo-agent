from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "raw" / "REP_S_00461.csv"
OUTPUT_PATH = BASE_DIR / "processed" / "REP_S_00461_cleaned.csv"


def normalize_cell(value: str) -> str:
    return " ".join(value.strip().split())


def parse_employee_id(raw_value: str) -> int | None:
    if "EMP ID" not in raw_value:
        return None
    value = raw_value.split(":", 1)[-1].strip()
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_employee_name(raw_value: str) -> str:
    if "NAME" not in raw_value:
        return ""
    return raw_value.split(":", 1)[-1].strip()


def parse_shift_datetime(date_value: str, time_value: str) -> datetime:
    return datetime.strptime(f"{date_value} {time_value}", "%d-%b-%y %H.%M.%S")


def parse_duration_parts(duration_value: str) -> tuple[int, int, int]:
    parts = duration_value.replace(".", ":").split(":")
    hours, minutes, seconds = (int(part) for part in parts)
    return hours, minutes, seconds


def duration_to_seconds(duration_value: str) -> int:
    hours, minutes, seconds = parse_duration_parts(duration_value)
    return (hours * 3600) + (minutes * 60) + seconds


def is_shift_row(row: list[str]) -> bool:
    if len(row) < 6:
        return False
    first = normalize_cell(row[0])
    third = normalize_cell(row[2])
    fourth = normalize_cell(row[3])
    fifth = normalize_cell(row[4])
    sixth = normalize_cell(row[5])
    if not all([first, third, fourth, fifth, sixth]):
        return False
    try:
        parse_shift_datetime(first, third)
        parse_shift_datetime(fourth, fifth)
        duration_to_seconds(sixth)
        return True
    except ValueError:
        return False


def load_rows(path: Path) -> list[list[str]]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="latin-1")
    return list(csv.reader(raw_text.splitlines()))


def clean_attendance_report(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> tuple[int, Path]:
    rows = load_rows(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_rows: list[dict[str, object]] = []
    current_employee_id: int | None = None
    current_employee_name = ""
    current_branch = ""

    for row in rows:
        row = row + [""] * (6 - len(row))
        row = [normalize_cell(value) for value in row[:6]]

        second = row[1]
        third = row[2]

        if "EMP ID" in second and "NAME" in third:
            current_employee_id = parse_employee_id(second)
            current_employee_name = parse_employee_name(third)
            current_branch = ""
            continue

        if (
            current_employee_id is not None
            and not row[0]
            and second
            and not row[2]
            and not row[3]
            and not row[4]
            and not row[5]
            and "EMP ID" not in second
            and "From Date" not in third
            and "PUNCH IN" not in second
        ):
            current_branch = second
            continue

        if not is_shift_row(row):
            continue

        punch_in_dt = parse_shift_datetime(row[0], row[2])
        punch_out_dt = parse_shift_datetime(row[3], row[4])
        duration_seconds = duration_to_seconds(row[5])

        cleaned_rows.append(
            {
                "employee_id": current_employee_id,
                "employee_name": current_employee_name,
                "branch": current_branch,
                "punch_in_date": row[0],
                "punch_in_time": row[2].replace(".", ":"),
                "punch_out_date": row[3],
                "punch_out_time": row[4].replace(".", ":"),
                "punch_in_timestamp": punch_in_dt.isoformat(sep=" "),
                "punch_out_timestamp": punch_out_dt.isoformat(sep=" "),
                "work_duration": row[5].replace(".", ":"),
                "work_duration_seconds": duration_seconds,
                "work_duration_hours": round(duration_seconds / 3600, 4),
                "overnight_shift": int(punch_out_dt.date() > punch_in_dt.date()),
                "source_file": input_path.name,
            }
        )

    fieldnames = [
        "employee_id",
        "employee_name",
        "branch",
        "punch_in_date",
        "punch_in_time",
        "punch_out_date",
        "punch_out_time",
        "punch_in_timestamp",
        "punch_out_timestamp",
        "work_duration",
        "work_duration_seconds",
        "work_duration_hours",
        "overnight_shift",
        "source_file",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return len(cleaned_rows), output_path


if __name__ == "__main__":
    row_count, written_path = clean_attendance_report()
    print(f"Cleaned {row_count} attendance rows -> {written_path}")
