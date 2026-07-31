"""
AQSD
Participant Database Engine

Module : APD-004 Daily Participant Import Manager
Version: 1.0.0

Description
-----------
Finds the official NSE participant Open Interest and Trading Volume
reports for one trading date, parses both files, inserts the records
into APD, prevents duplicates, and returns one consolidated summary.

Raw files are never modified.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_database.parsers import (
    ParticipantParseResult,
    parse_participant_report,
)
from Scripts.aqsd_database.repositories import (
    ParticipantRepository,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

RAW_PARTICIPANT_DIR: Final[Path] = (
    BASE_DIR
    / "Data"
    / "Raw"
    / "NSE"
    / "Participant"
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-004"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantImportResult:
    """
    Consolidated result for one daily participant import.
    """

    trade_date: date
    source_directory: Path
    reports_expected: int
    reports_found: int
    reports_successful: int
    reports_failed: int
    records_created: int
    records_inserted: int
    records_skipped: int
    database_total_records: int
    latest_database_date: date | None
    overall_status: str
    report_results: tuple[ParticipantParseResult, ...]


# ==========================================================
# PATH HELPERS
# ==========================================================

def build_source_directory(
    trade_date: date,
) -> Path:
    """
    Build the raw participant folder for one trading date.

    Example:
        Data/Raw/NSE/Participant/2026/07/30
    """

    return (
        RAW_PARTICIPANT_DIR
        / trade_date.strftime("%Y")
        / trade_date.strftime("%m")
        / trade_date.strftime("%d")
    )


def build_expected_files(
    trade_date: date,
) -> tuple[Path, Path]:
    """
    Return the expected OI and Volume report paths.
    """

    source_directory = build_source_directory(
        trade_date
    )

    date_code = trade_date.strftime("%d%m%Y")

    oi_file = (
        source_directory
        / f"fao_participant_oi_{date_code}.csv"
    )

    volume_file = (
        source_directory
        / f"fao_participant_vol_{date_code}.csv"
    )

    return oi_file, volume_file


# ==========================================================
# STATUS LOGIC
# ==========================================================

def determine_status(
    *,
    reports_expected: int,
    reports_found: int,
    reports_successful: int,
    reports_failed: int,
) -> str:
    """
    Determine the overall import status.
    """

    if (
        reports_found == reports_expected
        and reports_successful == reports_expected
        and reports_failed == 0
    ):
        return "SUCCESS"

    if reports_successful > 0:
        return "PARTIAL_SUCCESS"

    return "FAILED"


# ==========================================================
# IMPORT MANAGER
# ==========================================================

def run_participant_import(
    trade_date: date,
) -> ParticipantImportResult:
    """
    Import both NSE participant reports for one trading date.
    """

    source_directory = build_source_directory(
        trade_date
    )

    expected_files = build_expected_files(
        trade_date
    )

    print("=" * 72)
    print("AQSD PARTICIPANT IMPORT MANAGER")
    print("=" * 72)
    print(f"Module           : {MODULE_ID}")
    print(f"Version          : {MODULE_VERSION}")
    print(f"Trade Date       : {trade_date.isoformat()}")
    print(f"Source Directory : {source_directory}")
    print("-" * 72)

    report_results: list[ParticipantParseResult] = []

    reports_found = 0

    with ParticipantRepository() as repository:
        for source_file in expected_files:
            print(f"Checking: {source_file.name}")

            if not source_file.exists():
                result = ParticipantParseResult(
                    source_file=source_file,
                    trade_date=trade_date,
                    report_type="UNKNOWN",
                    participants_found=(),
                    records_created=0,
                    records_inserted=0,
                    records_skipped=0,
                    status="FAILED",
                    message="Expected participant report not found.",
                )

                report_results.append(result)

                print("FAILED: File not found.")
                print("-" * 72)
                continue

            reports_found += 1

            result = parse_participant_report(
                source_file=source_file,
                trade_date=trade_date,
                repository=repository,
            )

            report_results.append(result)

            print(f"Status           : {result.status}")
            print(f"Report Type      : {result.report_type}")
            print(
                "Participants     : "
                + ", ".join(result.participants_found)
            )
            print(f"Records Created  : {result.records_created}")
            print(f"Records Inserted : {result.records_inserted}")
            print(f"Records Skipped  : {result.records_skipped}")

            if result.status != "SUCCESS":
                print(f"Reason           : {result.message}")

            print("-" * 72)

        database_total_records = repository.count_records()
        latest_database_date = repository.get_latest_trade_date()

    reports_successful = sum(
        result.status == "SUCCESS"
        for result in report_results
    )

    reports_failed = (
        len(report_results)
        - reports_successful
    )

    records_created = sum(
        result.records_created
        for result in report_results
    )

    records_inserted = sum(
        result.records_inserted
        for result in report_results
    )

    records_skipped = sum(
        result.records_skipped
        for result in report_results
    )

    overall_status = determine_status(
        reports_expected=len(expected_files),
        reports_found=reports_found,
        reports_successful=reports_successful,
        reports_failed=reports_failed,
    )

    print("IMPORT SUMMARY")
    print("-" * 72)
    print(f"Reports Expected : {len(expected_files)}")
    print(f"Reports Found    : {reports_found}")
    print(f"Successful       : {reports_successful}")
    print(f"Failed           : {reports_failed}")
    print(f"Records Created  : {records_created}")
    print(f"Records Inserted : {records_inserted}")
    print(f"Records Skipped  : {records_skipped}")
    print(f"Database Records : {database_total_records}")
    print(f"Latest APD Date  : {latest_database_date}")
    print(f"Overall Status   : {overall_status}")
    print("=" * 72)

    return ParticipantImportResult(
        trade_date=trade_date,
        source_directory=source_directory,
        reports_expected=len(expected_files),
        reports_found=reports_found,
        reports_successful=reports_successful,
        reports_failed=reports_failed,
        records_created=records_created,
        records_inserted=records_inserted,
        records_skipped=records_skipped,
        database_total_records=database_total_records,
        latest_database_date=latest_database_date,
        overall_status=overall_status,
        report_results=tuple(report_results),
    )


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read the required --date argument.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Import NSE participant OI and Volume reports "
            "into the AQSD Participant Database."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Trading date in YYYY-MM-DD format.",
    )

    return parser.parse_args()


def parse_trade_date(
    value: str,
) -> date:
    """
    Convert YYYY-MM-DD text into a Python date.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    selected_date = parse_trade_date(
        arguments.date
    )

    result = run_participant_import(
        selected_date
    )

    if result.overall_status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()