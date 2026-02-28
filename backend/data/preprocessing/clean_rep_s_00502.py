from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "raw" / "REP_S_00502.csv"
OUTPUT_PATH = BASE_DIR / "processed" / "REP_S_00502_cleaned.csv"
UPDATED_OUTPUT_PATH = BASE_DIR / "processed" / "REP_S_00502_cleaned_updated.csv"


def normalize_cell(value: str) -> str:
    return " ".join(value.strip().split())


def parse_numeric(raw_value: str) -> float:
    cleaned = raw_value.replace(",", "").replace('"', "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def parse_report_date(raw_value: str) -> str:
    return normalize_cell(raw_value)


def parse_range_value(raw_value: str, prefix: str) -> str:
    value = normalize_cell(raw_value)
    if value.startswith(prefix):
        return value.replace(prefix, "", 1).strip()
    return ""


def is_page_header(row: list[str]) -> bool:
    if len(row) < 5:
        return False
    first = normalize_cell(row[0])
    second = normalize_cell(row[1])
    third = normalize_cell(row[2])
    fourth = normalize_cell(row[3]).lower()
    return bool(first and second.startswith("From Date:") and third.startswith("To Date:") and "page" in fourth)


def parse_page_marker(page_cell: str, total_cell: str) -> str:
    page_value = normalize_cell(page_cell).replace("Page", "", 1).replace("of", "", 1).strip()
    total_value = normalize_cell(total_cell)
    if page_value and total_value:
        return f"{page_value}/{total_value}"
    return page_value or total_value


def is_item_row(row: list[str]) -> bool:
    if len(row) < 4:
        return False
    first = normalize_cell(row[0])
    qty_value = normalize_cell(row[1])
    desc_value = normalize_cell(row[2])
    price_value = normalize_cell(row[3])
    if first:
        return False
    if not qty_value or not desc_value:
        return False
    try:
        parse_numeric(qty_value)
        parse_numeric(price_value)
        return True
    except ValueError:
        return False


def is_customer_total_row(row: list[str]) -> bool:
    if len(row) < 4:
        return False
    return normalize_cell(row[0]) == "Total :"


def load_rows(path: Path) -> list[list[str]]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="latin-1")
    return list(csv.reader(raw_text.splitlines()))


def clean_sales_by_customer_report(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> tuple[int, Path]:
    rows = load_rows(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_rows: list[dict[str, object]] = []
    order_sequence = 0
    current_branch = ""
    current_customer = ""
    current_customer_rows: list[dict[str, object]] = []
    report_generated_date = ""
    from_date = ""
    to_date = ""
    page_number = ""

    for raw_row in rows:
        row = raw_row + [""] * (5 - len(raw_row))
        row = [normalize_cell(value) for value in row[:5]]

        first = row[0]
        second = row[1]
        third = row[2]
        fourth = row[3]
        fifth = row[4]

        if is_page_header(row):
            report_generated_date = parse_report_date(first)
            from_date = parse_range_value(second, "From Date:")
            to_date = parse_range_value(third, "To Date:")
            page_number = parse_page_marker(fourth, fifth)
            continue

        if first == "Full Name":
            continue

        if first.startswith("Branch :"):
            current_branch = first.replace("Branch :", "", 1).strip()
            continue

        if first.startswith("REP_S_00502"):
            continue

        if is_customer_total_row(row):
            customer_total_qty = parse_numeric(second)
            customer_total_amount = parse_numeric(fourth)
            order_sequence += 1
            order_id = f"ORD-{order_sequence:06d}"
            for line_index, pending_row in enumerate(current_customer_rows, start=1):
                pending_row["order_id"] = order_id
                pending_row["order_sequence"] = order_sequence
                pending_row["line_index_in_order"] = line_index
                pending_row["customer_total_qty"] = customer_total_qty
                pending_row["customer_total_amount"] = customer_total_amount
            cleaned_rows.extend(current_customer_rows)
            current_customer_rows = []
            current_customer = ""
            continue

        if is_item_row(row):
            line_qty = parse_numeric(second)
            line_amount = parse_numeric(fourth)
            current_customer_rows.append(
                {
                    "branch": current_branch,
                    "customer_name": current_customer,
                    "line_qty": line_qty,
                    "item_description": third,
                    "line_amount": line_amount,
                    "customer_total_qty": "",
                    "customer_total_amount": "",
                    "order_id": "",
                    "order_sequence": "",
                    "line_index_in_order": "",
                    "report_generated_date": report_generated_date,
                    "from_date": from_date,
                    "to_date": to_date,
                    "page_marker": page_number,
                    "source_file": input_path.name,
                }
            )
            continue

        if first and not second and not third and not fourth:
            current_customer = first
            current_customer_rows = []
            continue

    fieldnames = [
        "branch",
        "customer_name",
        "line_qty",
        "item_description",
        "line_amount",
        "customer_total_qty",
        "customer_total_amount",
        "order_id",
        "order_sequence",
        "line_index_in_order",
        "report_generated_date",
        "from_date",
        "to_date",
        "page_marker",
        "source_file",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return len(cleaned_rows), output_path


def write_positive_order_subset(
    source_path: Path = OUTPUT_PATH,
    output_path: Path = UPDATED_OUTPUT_PATH,
) -> tuple[int, Path]:
    with source_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    positive_rows = [
        row
        for row in rows
        if parse_numeric(str(row.get("customer_total_amount", "0"))) > 0
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(positive_rows)

    return len(positive_rows), output_path


if __name__ == "__main__":
    row_count, written_path = clean_sales_by_customer_report()
    updated_row_count, updated_path = write_positive_order_subset()
    print(f"Cleaned {row_count} sales detail rows -> {written_path}")
    print(f"Wrote {updated_row_count} positive-order rows -> {updated_path}")
