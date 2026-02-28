from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "raw" / "rep_s_00334_1_SMRY.csv"
OUTPUT_PATH = BASE_DIR / "processed" / "REP_S_00334_1_SMRY_cleaned.csv"

MONTH_NAMES = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


def normalize_cell(value: str) -> str:
    return " ".join(value.strip().split())


def parse_branch_name(raw_value: str) -> str:
    return raw_value.split(":", 1)[-1].strip()


def parse_numeric(raw_value: str) -> float:
    cleaned = raw_value.replace(",", "").replace('"', "").strip()
    return float(cleaned)


def is_month_row(row: list[str]) -> bool:
    if len(row) < 4:
        return False
    month_value = normalize_cell(row[0]).lower()
    year_value = normalize_cell(row[2])
    total_value = normalize_cell(row[3])
    if month_value not in MONTH_NAMES:
        return False
    if not year_value.isdigit():
        return False
    if not total_value:
        return False
    try:
        parse_numeric(total_value)
        return True
    except ValueError:
        return False


def load_rows(path: Path) -> list[list[str]]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="latin-1")
    return list(csv.reader(raw_text.splitlines()))


def clean_monthly_sales_report(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> tuple[int, Path]:
    rows = load_rows(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_rows: list[dict[str, object]] = []
    current_branch = ""

    for row in rows:
        row = row + [""] * (5 - len(row))
        row = [normalize_cell(value) for value in row[:5]]

        first = row[0]

        if first.startswith("Branch Name:"):
            current_branch = parse_branch_name(first)
            continue

        if not current_branch:
            continue

        if not is_month_row(row):
            continue

        month_name = row[0]
        year_value = int(row[2])
        total_sales = parse_numeric(row[3])

        cleaned_rows.append(
            {
                "branch_name": current_branch,
                "month": month_name,
                "year": year_value,
                "period_key": f"{year_value}-{month_name[:3].title()}",
                "total_sales": total_sales,
                "source_file": input_path.name,
            }
        )

    fieldnames = [
        "branch_name",
        "month",
        "year",
        "period_key",
        "total_sales",
        "source_file",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return len(cleaned_rows), output_path


if __name__ == "__main__":
    row_count, written_path = clean_monthly_sales_report()
    print(f"Cleaned {row_count} monthly sales rows -> {written_path}")
