from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "raw" / "REP_S_00194_SMRY.csv"
OUTPUT_PATH = BASE_DIR / "processed" / "REP_S_00194_SMRY_cleaned.csv"


def normalize_cell(value: str) -> str:
    return " ".join(value.strip().split())


def parse_numeric(raw_value: str) -> float:
    cleaned = raw_value.replace(",", "").replace('"', "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def parse_branch_name(raw_value: str) -> str:
    return raw_value.split(":", 1)[-1].strip()


def load_rows(path: Path) -> list[list[str]]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="latin-1")
    return list(csv.reader(raw_text.splitlines()))


def clean_tax_report(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> tuple[int, Path]:
    rows = load_rows(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_rows: list[dict[str, object]] = []
    current_branch = ""
    report_period = ""

    for row in rows:
        row = row + [""] * (10 - len(row))
        row = [normalize_cell(value) for value in row[:10]]

        first = row[0]
        second = row[1]

        if second.startswith("Year:"):
            report_period = second
            continue

        if first.startswith("Branch Name:"):
            current_branch = parse_branch_name(first)
            continue

        if first != "Total By Branch" or not current_branch:
            continue

        cleaned_rows.append(
            {
                "branch_name": current_branch,
                "tax_description": first,
                "report_period": report_period,
                "vat_11_pct": parse_numeric(row[1]),
                "tax_2": parse_numeric(row[2]),
                "tax_3": parse_numeric(row[3]),
                "tax_4": parse_numeric(row[4]),
                "tax_5": parse_numeric(row[5]),
                "service": parse_numeric(row[7]),
                "total": parse_numeric(row[8]),
                "source_file": input_path.name,
            }
        )

    fieldnames = [
        "branch_name",
        "tax_description",
        "report_period",
        "vat_11_pct",
        "tax_2",
        "tax_3",
        "tax_4",
        "tax_5",
        "service",
        "total",
        "source_file",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return len(cleaned_rows), output_path


if __name__ == "__main__":
    row_count, written_path = clean_tax_report()
    print(f"Cleaned {row_count} tax summary rows -> {written_path}")
