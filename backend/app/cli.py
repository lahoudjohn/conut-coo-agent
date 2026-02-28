import sys

from app.services.ingest import ingest_all_raw_files


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else None

    if command == "ingest":
        written = ingest_all_raw_files()
        print(f"Ingested {len(written)} file(s).")
        for path in written:
            print(path)
        return

    print("Usage: python -m app.cli ingest")


if __name__ == "__main__":
    main()
