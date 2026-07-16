"""
AQSD Yahoo Legacy Organizer v1.0

Finds Python scripts that use Yahoo/yfinance and copies them into a separate
legacy folder without deleting or moving the working originals.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "Scripts"
LEGACY_DIR = BASE_DIR / "Legacy" / "Yahoo" / "Scripts"
MANIFEST = BASE_DIR / "Legacy" / "Yahoo" / "Yahoo_Files_Manifest.csv"

PATTERNS = (
    "import yfinance",
    "from yfinance",
    "yf.download",
    "yf.Ticker",
    "query1.finance.yahoo",
    "query2.finance.yahoo",
)


def find_yahoo_files() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        matches = [
            pattern
            for pattern in PATTERNS
            if pattern.lower() in text.lower()
        ]

        if matches:
            rows.append(
                {
                    "file_name": path.name,
                    "source_path": str(path),
                    "size_bytes": str(path.stat().st_size),
                    "matched_patterns": "; ".join(matches),
                    "scanned_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

    return rows


def write_manifest(
    rows: list[dict[str, str]],
) -> None:
    MANIFEST.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_name",
                "source_path",
                "size_bytes",
                "matched_patterns",
                "scanned_at",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def copy_files(
    rows: list[dict[str, str]],
) -> None:
    LEGACY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for row in rows:
        source = Path(row["source_path"])
        destination = LEGACY_DIR / source.name
        shutil.copy2(source, destination)


def show_rows(
    rows: list[dict[str, str]],
) -> None:
    print("\nAQSD YAHOO LEGACY ORGANIZER")
    print("=" * 88)

    if not rows:
        print("No Yahoo/yfinance scripts detected.")
    else:
        for index, row in enumerate(rows, start=1):
            print(
                f"{index:>3}. {row['file_name']:<40} "
                f"{row['size_bytes']:>10} bytes"
            )

    print("=" * 88)
    print(f"Files detected: {len(rows)}")
    print(f"Manifest:       {MANIFEST}")
    print(f"Archive folder: {LEGACY_DIR}")
    print("Original files deleted: NO")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Yahoo Legacy Organizer."
    )

    parser.add_argument(
        "--scan",
        action="store_true",
    )

    parser.add_argument(
        "--copy",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    rows = find_yahoo_files()
    write_manifest(rows)

    if args.copy:
        copy_files(rows)

    show_rows(rows)

    if args.copy:
        print(
            "\nYahoo scripts copied to the legacy folder. "
            "Working originals remain unchanged."
        )


if __name__ == "__main__":
    main()
