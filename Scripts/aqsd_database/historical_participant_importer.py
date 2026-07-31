"""
AQSD
Historical Participant Workbook Importer

Module : APD-008
Version: 1.0.0
Author : AQSD

Description
-----------
Imports the historical 67-column AQSD Participant workbook into the
normalized APD SQLite database.

One workbook row represents one trading date.

Only gross Long and Short participant-position columns are imported.
Net columns are not imported because AQSD calculates:

    Net = Long - Short

Market-price columns such as Nifty_Spot and BankNifty_Spot are not
written into APD. They will later belong to the Market Price Database.

Supported participants
----------------------
- FII
- PRO
- DII
- CLIENT / CLNT / RTL

Supported position groups
-------------------------
- Index Futures
- Index Call Options
- Index Put Options
- Stock Futures
- Stock Call Options
- Stock Put Options

Important
---------
- The original workbook is never modified.
- Existing APD records are not duplicated.
- Invalid and duplicate dates are reported.
- Genuine Excel dates are preserved.
- Text dates are interpreted using Indian day-first format.
- Dates are never guessed or automatically swapped.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from Scripts.aqsd_database.repositories import (
    ParticipantPosition,
    ParticipantRepository,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-008"
MODULE_VERSION: Final[str] = "1.0.0"

DATE_COLUMN: Final[str] = "Trade_Date"

SUPPORTED_PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
    "CLIENT",
)

PARTICIPANT_ALIASES: Final[dict[str, str]] = {
    "FII": "FII",
    "FPI": "FII",
    "PRO": "PRO",
    "DII": "DII",
    "CLIENT": "CLIENT",
    "CLNT": "CLIENT",
    "RTL": "CLIENT",
}


# ==========================================================
# COLUMN MAPPING
# ==========================================================

POSITION_COLUMN_MAP: Final[dict[str, tuple[str, str]]] = {
    "INDEX_FUTURES_LONG_TTL": (
        "OPEN INTEREST - INDEX FUTURES",
        "LONG",
    ),
    "INDEX_FUTURES_SHORT_TTL": (
        "OPEN INTEREST - INDEX FUTURES",
        "SHORT",
    ),
    "INDEX_CALL_LONG_TTL": (
        "OPEN INTEREST - INDEX OPTIONS CALL",
        "LONG",
    ),
    "INDEX_CALL_SHORT_TTL": (
        "OPEN INTEREST - INDEX OPTIONS CALL",
        "SHORT",
    ),
    "INDEX_PUT_LONG_TTL": (
        "OPEN INTEREST - INDEX OPTIONS PUT",
        "LONG",
    ),
    "INDEX_PUT_SHORT_TTL": (
        "OPEN INTEREST - INDEX OPTIONS PUT",
        "SHORT",
    ),
    "STOCK_FUTURES_LONG_TTL": (
        "OPEN INTEREST - STOCK FUTURES",
        "LONG",
    ),
    "STOCK_FUTURES_SHORT_TTL": (
        "OPEN INTEREST - STOCK FUTURES",
        "SHORT",
    ),
    "STOCK_CALL_LONG_TTL": (
        "OPEN INTEREST - STOCK OPTIONS CALL",
        "LONG",
    ),
    "STOCK_CALL_SHORT_TTL": (
        "OPEN INTEREST - STOCK OPTIONS CALL",
        "SHORT",
    ),
    "STOCK_PUT_LONG_TTL": (
        "OPEN INTEREST - STOCK OPTIONS PUT",
        "LONG",
    ),
    "STOCK_PUT_SHORT_TTL": (
        "OPEN INTEREST - STOCK OPTIONS PUT",
        "SHORT",
    ),
}


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class DateIssue:
    """
    One date validation issue.
    """

    excel_row: int
    original_value: str
    issue_type: str
    message: str


@dataclass(frozen=True)
class HistoricalImportResult:
    """
    Consolidated result from APD-008.
    """

    source_file: Path
    sheet_name: str
    workbook_rows: int
    valid_date_rows: int
    invalid_date_rows: int
    duplicate_date_rows: int
    weekend_date_rows: int
    position_records_created: int
    records_inserted: int
    records_skipped: int
    database_total_records: int
    earliest_import_date: date | None
    latest_import_date: date | None
    status: str
    date_issues: tuple[DateIssue, ...]


# ==========================================================
# TEXT HELPERS
# ==========================================================

def normalize_header(value: str) -> str:
    """
    Normalize an Excel header while preserving underscore structure.
    """

    normalized = str(value).strip().upper()

    normalized = re.sub(
        r"[^A-Z0-9]+",
        "_",
        normalized,
    )

    normalized = re.sub(
        r"_+",
        "_",
        normalized,
    )

    return normalized.strip("_")


def standardize_participant(
    participant_text: str,
) -> str | None:
    """
    Convert workbook participant prefixes into AQSD names.
    """

    normalized = normalize_header(
        participant_text
    )

    return PARTICIPANT_ALIASES.get(
        normalized
    )


# ==========================================================
# DATE HANDLING
# ==========================================================

def parse_trade_date(
    value: object,
) -> date | None:
    """
    Parse one workbook date without guessing.

    Rules
    -----
    1. Genuine Excel/Python dates are preserved.
    2. Text is parsed using day-first convention.
    3. Invalid dates return None.
    4. Five-digit years are not automatically repaired.
    """

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    if isinstance(
        value,
        (
            pd.Timestamp,
            datetime,
            date,
        ),
    ):
        return pd.Timestamp(value).date()

    text = str(value).strip()

    if not text:
        return None

    if re.search(
        r"/\d{5}$|-\d{5}$|\.\d{5}$",
        text,
    ):
        return None

    try:
        parsed = pd.to_datetime(
            text,
            dayfirst=True,
            errors="raise",
        )

    except Exception:
        return None

    return pd.Timestamp(parsed).date()


def is_weekend(
    trade_date: date,
) -> bool:
    """
    Return True for Saturday or Sunday.
    """

    return trade_date.weekday() >= 5


# ==========================================================
# NUMERIC HANDLING
# ==========================================================

def parse_numeric_value(
    value: object,
) -> float:
    """
    Convert one workbook position value into float.

    Missing cells are stored as zero only when the column exists.
    """

    if value is None:
        return 0.0

    try:
        if pd.isna(value):
            return 0.0
    except TypeError:
        pass

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(value)

    cleaned = (
        str(value)
        .strip()
        .replace(",", "")
    )

    if cleaned.upper() in {
        "",
        "-",
        "--",
        "NA",
        "N/A",
        "NONE",
    }:
        return 0.0

    try:
        return float(cleaned)

    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric value: {value!r}"
        ) from exc


# ==========================================================
# COLUMN DISCOVERY
# ==========================================================

def discover_position_columns(
    dataframe: pd.DataFrame,
) -> dict[str, tuple[str, str, str]]:
    """
    Discover supported participant gross-position columns.

    Returns
    -------
    dict
        {
            workbook_column: (
                participant,
                APD segment,
                position side,
            )
        }
    """

    discovered: dict[
        str,
        tuple[str, str, str],
    ] = {}

    for original_column in dataframe.columns:
        normalized_column = normalize_header(
            str(original_column)
        )

        parts = normalized_column.split(
            "_",
            maxsplit=1,
        )

        if len(parts) != 2:
            continue

        participant_prefix = parts[0]
        field_name = parts[1]

        participant = standardize_participant(
            participant_prefix
        )

        if participant is None:
            continue

        mapping = POSITION_COLUMN_MAP.get(
            field_name
        )

        if mapping is None:
            continue

        segment, position_side = mapping

        discovered[str(original_column)] = (
            participant,
            segment,
            position_side,
        )

    return discovered


def expected_position_column_count() -> int:
    """
    Return the expected count for a full 67-column schema.

    Four participants × twelve gross Long/Short columns.
    """

    return (
        len(SUPPORTED_PARTICIPANTS)
        * len(POSITION_COLUMN_MAP)
    )


# ==========================================================
# WORKBOOK READING
# ==========================================================

def read_workbook(
    source_file: Path,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """
    Read the historical participant workbook.
    """

    if not source_file.exists():
        raise FileNotFoundError(
            f"Participant workbook not found: {source_file}"
        )

    if source_file.suffix.lower() not in {
        ".xlsx",
        ".xlsm",
    }:
        raise ValueError(
            "Historical participant source must be an "
            "Excel workbook (.xlsx or .xlsm)."
        )

    dataframe = pd.read_excel(
        source_file,
        sheet_name=sheet_name,
        engine="openpyxl",
    )

    dataframe = dataframe.dropna(
        how="all"
    ).reset_index(drop=True)

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    return dataframe


# ==========================================================
# RECORD CREATION
# ==========================================================

def create_historical_positions(
    *,
    dataframe: pd.DataFrame,
    source_file: Path,
) -> tuple[
    list[ParticipantPosition],
    list[DateIssue],
    list[date],
    int,
    int,
    int,
]:
    """
    Convert the historical workbook into APD records.

    Returns
    -------
    positions
    date issues
    valid dates
    invalid date rows
    duplicate date rows
    weekend date rows
    """

    if DATE_COLUMN not in dataframe.columns:
        raise KeyError(
            f"Required column not found: {DATE_COLUMN}"
        )

    column_map = discover_position_columns(
        dataframe
    )

    expected_count = expected_position_column_count()

    if len(column_map) != expected_count:
        discovered_names = "\n".join(
            sorted(column_map)
        )

        raise ValueError(
            "Historical participant schema is incomplete.\n"
            f"Expected gross position columns: {expected_count}\n"
            f"Discovered gross position columns: {len(column_map)}\n\n"
            f"Discovered columns:\n{discovered_names}"
        )

    positions: list[ParticipantPosition] = []
    issues: list[DateIssue] = []
    valid_dates: list[date] = []

    parsed_dates: list[
        date | None
    ] = []

    invalid_date_rows = 0
    weekend_date_rows = 0

    for dataframe_index, row in dataframe.iterrows():
        excel_row = int(dataframe_index) + 2
        original_date = row[DATE_COLUMN]

        parsed_date = parse_trade_date(
            original_date
        )

        parsed_dates.append(
            parsed_date
        )

        if parsed_date is None:
            invalid_date_rows += 1

            issues.append(
                DateIssue(
                    excel_row=excel_row,
                    original_value=str(
                        original_date
                    ),
                    issue_type="INVALID_DATE",
                    message=(
                        "Date could not be interpreted safely. "
                        "The row was not imported."
                    ),
                )
            )

            continue

        valid_dates.append(
            parsed_date
        )

        if is_weekend(parsed_date):
            weekend_date_rows += 1

            issues.append(
                DateIssue(
                    excel_row=excel_row,
                    original_value=str(
                        original_date
                    ),
                    issue_type="WEEKEND_DATE",
                    message=(
                        f"{parsed_date.isoformat()} is a "
                        "Saturday or Sunday. The row was "
                        "imported but requires review."
                    ),
                )
            )

        for (
            workbook_column,
            mapping,
        ) in column_map.items():
            participant, segment, position_side = mapping

            try:
                numeric_value = parse_numeric_value(
                    row[workbook_column]
                )

            except ValueError as exc:
                raise ValueError(
                    f"{exc} Excel row: {excel_row}; "
                    f"column: {workbook_column!r}"
                ) from exc

            positions.append(
                ParticipantPosition(
                    trade_date=parsed_date,
                    participant=participant,
                    segment=segment,
                    position_side=position_side,
                    value=numeric_value,
                    source_file=source_file.name,
                )
            )

    duplicate_date_rows = 0

    valid_date_series = pd.Series(
        [
            value
            for value in parsed_dates
            if value is not None
        ],
        dtype="object",
    )

    duplicated_dates = set(
        valid_date_series[
            valid_date_series.duplicated(
                keep=False
            )
        ].tolist()
    )

    if duplicated_dates:
        for dataframe_index, parsed_date in enumerate(
            parsed_dates
        ):
            if (
                parsed_date is not None
                and parsed_date in duplicated_dates
            ):
                duplicate_date_rows += 1

                issues.append(
                    DateIssue(
                        excel_row=dataframe_index + 2,
                        original_value=str(
                            dataframe.iloc[
                                dataframe_index
                            ][DATE_COLUMN]
                        ),
                        issue_type="DUPLICATE_DATE",
                        message=(
                            f"Duplicate trading date: "
                            f"{parsed_date.isoformat()}."
                        ),
                    )
                )

    return (
        positions,
        issues,
        valid_dates,
        invalid_date_rows,
        duplicate_date_rows,
        weekend_date_rows,
    )


# ==========================================================
# IMPORT ENGINE
# ==========================================================

def run_historical_import(
    *,
    source_file: Path,
    sheet_name: str | int = 0,
) -> HistoricalImportResult:
    """
    Import the 67-column participant workbook into APD.
    """

    dataframe = read_workbook(
        source_file=source_file,
        sheet_name=sheet_name,
    )

    discovered_columns = discover_position_columns(
        dataframe
    )

    print()
    print("=" * 82)
    print("AQSD HISTORICAL PARTICIPANT IMPORTER")
    print("=" * 82)
    print(f"Module                   : {MODULE_ID}")
    print(f"Version                  : {MODULE_VERSION}")
    print(f"Source Workbook          : {source_file}")
    print(f"Worksheet                : {sheet_name}")
    print(f"Workbook Rows            : {len(dataframe)}")
    print(
        f"Gross Columns Discovered : "
        f"{len(discovered_columns)}"
    )
    print(
        f"Gross Columns Expected   : "
        f"{expected_position_column_count()}"
    )
    print("-" * 82)

    (
        positions,
        issues,
        valid_dates,
        invalid_date_rows,
        duplicate_date_rows,
        weekend_date_rows,
    ) = create_historical_positions(
        dataframe=dataframe,
        source_file=source_file,
    )

    print(
        f"Position Records Created : "
        f"{len(positions):,}"
    )

    with ParticipantRepository() as repository:
        inserted, skipped = repository.insert_many(
            positions
        )

        database_total = repository.count_records()

    earliest_date = (
        min(valid_dates)
        if valid_dates
        else None
    )

    latest_date = (
        max(valid_dates)
        if valid_dates
        else None
    )

    status = (
        "SUCCESS"
        if invalid_date_rows == 0
        and duplicate_date_rows == 0
        else "REVIEW REQUIRED"
    )

    result = HistoricalImportResult(
        source_file=source_file,
        sheet_name=str(sheet_name),
        workbook_rows=len(dataframe),
        valid_date_rows=len(valid_dates),
        invalid_date_rows=invalid_date_rows,
        duplicate_date_rows=duplicate_date_rows,
        weekend_date_rows=weekend_date_rows,
        position_records_created=len(positions),
        records_inserted=inserted,
        records_skipped=skipped,
        database_total_records=database_total,
        earliest_import_date=earliest_date,
        latest_import_date=latest_date,
        status=status,
        date_issues=tuple(issues),
    )

    display_result(result)

    return result


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: HistoricalImportResult,
) -> None:
    """
    Print the historical-import summary.
    """

    print()
    print("=" * 82)
    print("APD HISTORICAL IMPORT SUMMARY")
    print("=" * 82)
    print(
        f"Workbook Rows             : "
        f"{result.workbook_rows:,}"
    )
    print(
        f"Valid Date Rows           : "
        f"{result.valid_date_rows:,}"
    )
    print(
        f"Invalid Date Rows         : "
        f"{result.invalid_date_rows:,}"
    )
    print(
        f"Duplicate Date Rows       : "
        f"{result.duplicate_date_rows:,}"
    )
    print(
        f"Weekend Date Rows         : "
        f"{result.weekend_date_rows:,}"
    )
    print("-" * 82)
    print(
        f"Position Records Created  : "
        f"{result.position_records_created:,}"
    )
    print(
        f"Records Inserted          : "
        f"{result.records_inserted:,}"
    )
    print(
        f"Records Skipped           : "
        f"{result.records_skipped:,}"
    )
    print(
        f"Total APD Records         : "
        f"{result.database_total_records:,}"
    )
    print("-" * 82)
    print(
        f"Earliest Imported Date    : "
        f"{result.earliest_import_date}"
    )
    print(
        f"Latest Imported Date      : "
        f"{result.latest_import_date}"
    )
    print(
        f"Date Issues Reported      : "
        f"{len(result.date_issues):,}"
    )
    print(
        f"Overall Status            : "
        f"{result.status}"
    )
    print("=" * 82)

    if result.date_issues:
        print()
        print("DATE ISSUES — FIRST 20")
        print("-" * 82)

        for issue in result.date_issues[:20]:
            print(
                f"Excel Row {issue.excel_row}: "
                f"{issue.issue_type} | "
                f"{issue.original_value} | "
                f"{issue.message}"
            )

        if len(result.date_issues) > 20:
            print(
                f"...and "
                f"{len(result.date_issues) - 20} "
                f"additional issues."
            )


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Import the historical 67-column AQSD Participant "
            "Excel workbook into the APD SQLite database."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the historical participant workbook.",
    )

    parser.add_argument(
        "--sheet",
        default=0,
        help=(
            "Excel worksheet name or zero-based worksheet number. "
            "Default: first worksheet."
        ),
    )

    return parser.parse_args()


def normalize_sheet_argument(
    value: object,
) -> str | int:
    """
    Convert a numeric sheet argument into an integer.
    """

    text = str(value).strip()

    if text.isdigit():
        return int(text)

    return text


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    result = run_historical_import(
        source_file=(
            arguments.input_file
            .expanduser()
            .resolve()
        ),
        sheet_name=normalize_sheet_argument(
            arguments.sheet
        ),
    )

    if result.status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()