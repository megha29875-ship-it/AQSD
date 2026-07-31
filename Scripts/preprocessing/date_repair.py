"""
AQSD
Participant Date Repair Utility

Module    : date_repair.py
Module ID : DB-000A
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Repairs and standardizes the Trade_Date column in the
AQSD Participant Database.

The original workbook is never modified.

Outputs
-------
1. PARTICIPANT_DATA_DATE_CLEAN.xlsx
2. date_repair_report.xlsx
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


# ==========================================================
# PROJECT PATHS
# ==========================================================

CURRENT_FILE = Path(__file__).resolve()
SCRIPTS_DIR = CURRENT_FILE.parents[1]
BASE_DIR = CURRENT_FILE.parents[2]

DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output" / "Preprocessing"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID = "DB-000A"
MODULE_NAME = "AQSD Date Repair Utility"
MODULE_VERSION = "1.0.0"

DATE_COLUMN = "Trade_Date"

CLEAN_FILENAME = "PARTICIPANT_DATA_DATE_CLEAN.xlsx"
REPORT_FILENAME = "date_repair_report.xlsx"

MIN_VALID_YEAR = 2000
MAX_VALID_YEAR = 2100


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(slots=True)
class DateRepairResult:
    success: bool
    input_file: Path
    clean_file: Path | None
    report_file: Path | None
    rows_checked: int
    rows_repaired: int
    rows_unchanged: int
    rows_invalid: int
    duplicate_dates: int
    weekend_dates: int


# ==========================================================
# DATE HELPERS
# ==========================================================

def clean_date_text(value: str) -> str:
    """
    Clean a text date before parsing.
    """

    text = value.strip()

    text = text.replace("\\", "/")
    text = text.replace(".", "/")
    text = text.replace("-", "/")

    text = re.sub(r"\s+", "", text)

    return text


def repair_year_text(text: str) -> tuple[str, bool]:
    """
    Repair obvious five-digit year typing errors.

    Examples
    --------
    1/10/20024  -> 1/10/2024
    19/11/20234 -> 19/11/2023

    Only obvious five-digit year errors are repaired.
    """

    match = re.fullmatch(
        r"(\d{1,2})/(\d{1,2})/(\d{5})",
        text,
    )

    if not match:
        return text, False

    day_text, month_text, year_text = match.groups()

    # Common typing pattern:
    # 20024 -> 2024
    # 20234 -> 2023
    repaired_year = year_text[:2] + year_text[-2:]

    repaired = (
        f"{day_text}/{month_text}/{repaired_year}"
    )

    return repaired, True


def parse_text_date(
    value: str,
) -> tuple[pd.Timestamp | None, str]:
    """
    Parse a text date using Indian day-first convention.
    """

    cleaned = clean_date_text(value)

    if not cleaned:
        return None, "MISSING"

    cleaned, year_repaired = repair_year_text(cleaned)

    try:
        parsed = pd.to_datetime(
            cleaned,
            dayfirst=True,
            errors="raise",
        )

        parsed = pd.Timestamp(parsed).normalize()

    except Exception:
        return None, "INVALID_TEXT_DATE"

    if not (
        MIN_VALID_YEAR
        <= parsed.year
        <= MAX_VALID_YEAR
    ):
        return None, "INVALID_YEAR"

    if year_repaired:
        return parsed, "REPAIRED_YEAR"

    return parsed, "PARSED_TEXT"


def swap_excel_day_month(
    value: pd.Timestamp,
) -> pd.Timestamp | None:
    """
    Return a day/month-swapped candidate for an ambiguous
    Excel date.

    Example
    -------
    01-Feb-2024 -> 02-Jan-2024

    This is only possible where both values are at most 12.
    """

    if value.day > 12 or value.month > 12:
        return None

    try:
        return pd.Timestamp(
            year=value.year,
            month=value.day,
            day=value.month,
        )

    except ValueError:
        return None


def distance_in_days(
    first: pd.Timestamp,
    second: pd.Timestamp,
) -> int:
    """
    Absolute difference between two dates.
    """

    return abs((first - second).days)


def choose_excel_date_candidate(
    actual: pd.Timestamp,
    previous_date: pd.Timestamp | None,
    next_known_date: pd.Timestamp | None,
) -> tuple[pd.Timestamp, str]:
    """
    Choose between the Excel-stored date and a swapped
    day/month candidate.

    The choice is based on chronological continuity.

    This handles Excel converting:
        2/1/2024 into 01-Feb-2024

    when the intended Indian date was:
        02-Jan-2024
    """

    actual = actual.normalize()
    swapped = swap_excel_day_month(actual)

    if swapped is None or swapped == actual:
        return actual, "EXCEL_DATE_UNCHANGED"

    actual_score = 0
    swapped_score = 0

    # Prefer a date after the previous valid date.
    if previous_date is not None:

        if actual <= previous_date:
            actual_score += 10_000
        else:
            actual_score += distance_in_days(
                actual,
                previous_date,
            )

        if swapped <= previous_date:
            swapped_score += 10_000
        else:
            swapped_score += distance_in_days(
                swapped,
                previous_date,
            )

    # Prefer a date before the next known date.
    if next_known_date is not None:

        if actual >= next_known_date:
            actual_score += 10_000
        else:
            actual_score += distance_in_days(
                actual,
                next_known_date,
            )

        if swapped >= next_known_date:
            swapped_score += 10_000
        else:
            swapped_score += distance_in_days(
                swapped,
                next_known_date,
            )

    if swapped_score < actual_score:
        return swapped, "EXCEL_DAY_MONTH_SWAPPED"

    return actual, "EXCEL_DATE_UNCHANGED"


def find_next_unambiguous_date(
    values: list[Any],
    start_position: int,
) -> pd.Timestamp | None:
    """
    Find the next date that can be interpreted reliably.

    Text dates are parsed day-first.
    Excel dates with a day greater than 12 are unambiguous.
    """

    for value in values[start_position + 1:]:

        if pd.isna(value):
            continue

        if isinstance(
            value,
            (
                pd.Timestamp,
                datetime,
                date,
            ),
        ):
            candidate = pd.Timestamp(value).normalize()

            if candidate.day > 12:
                return candidate

            continue

        parsed, _ = parse_text_date(str(value))

        if parsed is not None:
            return parsed

    return None


# ==========================================================
# REPAIR ENGINE
# ==========================================================

def repair_date_column(
    dataframe: pd.DataFrame,
    date_column: str = DATE_COLUMN,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Repair and standardize the selected date column.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        Clean dataframe and detailed repair report.
    """

    if date_column not in dataframe.columns:
        raise KeyError(
            f"Required date column not found: {date_column}"
        )

    clean_df = dataframe.copy()
    original_values = clean_df[date_column].tolist()

    repaired_dates: list[pd.Timestamp | pd.NaT] = []
    report_rows: list[dict[str, Any]] = []

    previous_valid_date: pd.Timestamp | None = None

    for position, original_value in enumerate(
        original_values
    ):
        excel_row = position + 2

        repaired_date: pd.Timestamp | None = None
        status = ""
        note = ""

        if pd.isna(original_value):
            status = "INVALID"
            note = "Missing date value"

        elif isinstance(
            original_value,
            (
                pd.Timestamp,
                datetime,
                date,
            ),
        ):
            actual = pd.Timestamp(
                original_value
            ).normalize()

            next_known_date = find_next_unambiguous_date(
                original_values,
                position,
            )

            repaired_date, status = (
                choose_excel_date_candidate(
                    actual=actual,
                    previous_date=previous_valid_date,
                    next_known_date=next_known_date,
                )
            )

            if status == "EXCEL_DAY_MONTH_SWAPPED":
                note = (
                    "Excel date appeared to use MM/DD; "
                    "converted to Indian DD/MM sequence"
                )

        else:
            repaired_date, status = parse_text_date(
                str(original_value)
            )

            if status == "REPAIRED_YEAR":
                note = (
                    "Obvious five-digit year typing error "
                    "was repaired"
                )

            elif status == "INVALID_TEXT_DATE":
                note = "Date could not be interpreted"

            elif status == "INVALID_YEAR":
                note = "Year outside permitted range"

        if repaired_date is not None:
            repaired_date = repaired_date.normalize()
            repaired_dates.append(repaired_date)
            previous_valid_date = repaired_date
        else:
            repaired_dates.append(pd.NaT)

        changed = False

        if repaired_date is not None:

            try:
                original_timestamp = pd.Timestamp(
                    original_value
                ).normalize()

                changed = (
                    original_timestamp != repaired_date
                )

            except Exception:
                changed = True

        report_rows.append(
            {
                "Excel_Row": excel_row,
                "Original_Value": str(original_value),
                "Corrected_Date": (
                    repaired_date.strftime("%d-%b-%Y")
                    if repaired_date is not None
                    else ""
                ),
                "Status": status,
                "Changed": changed,
                "Weekend": (
                    repaired_date.weekday() >= 5
                    if repaired_date is not None
                    else False
                ),
                "Note": note,
            }
        )

    clean_df[date_column] = pd.to_datetime(
        repaired_dates,
        errors="coerce",
    )

    report_df = pd.DataFrame(report_rows)

    # Duplicate-date identification
    duplicate_mask = (
        clean_df[date_column].notna()
        & clean_df[date_column].duplicated(
            keep=False
        )
    )

    duplicate_dates = set(
        clean_df.loc[
            duplicate_mask,
            date_column,
        ].dt.strftime("%d-%b-%Y")
    )

    report_df["Duplicate_Date"] = (
        report_df["Corrected_Date"].isin(
            duplicate_dates
        )
    )

    # Chronological-order check
    report_df["Chronology_Issue"] = False

    previous: pd.Timestamp | None = None

    for position, current in enumerate(
        clean_df[date_column]
    ):
        if pd.isna(current):
            continue

        current = pd.Timestamp(current)

        if (
            previous is not None
            and current <= previous
        ):
            report_df.loc[
                position,
                "Chronology_Issue",
            ] = True

        previous = current

    return clean_df, report_df


# ==========================================================
# EXPORT
# ==========================================================

def export_results(
    clean_df: pd.DataFrame,
    report_df: pd.DataFrame,
    output_folder: Path,
) -> tuple[Path, Path]:
    """
    Export the cleaned workbook and repair report.
    """

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    clean_file = output_folder / CLEAN_FILENAME
    report_file = output_folder / REPORT_FILENAME

    clean_export = clean_df.copy()

    # Keep a genuine Excel date value with consistent display.
    with pd.ExcelWriter(
        clean_file,
        engine="openpyxl",
        datetime_format="DD-MMM-YYYY",
        date_format="DD-MMM-YYYY",
    ) as writer:
        clean_export.to_excel(
            writer,
            sheet_name="Participant_Data",
            index=False,
        )

        worksheet = writer.sheets["Participant_Data"]

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = (
            worksheet.dimensions
        )

        worksheet.column_dimensions["A"].width = 15

        for cell in worksheet["A"][1:]:
            cell.number_format = "DD-MMM-YYYY"

    summary = pd.DataFrame(
        {
            "Metric": [
                "Rows Checked",
                "Dates Changed",
                "Invalid Dates",
                "Weekend Dates",
                "Duplicate-Date Rows",
                "Chronology Issues",
            ],
            "Value": [
                len(report_df),
                int(report_df["Changed"].sum()),
                int(
                    report_df[
                        "Corrected_Date"
                    ].eq("").sum()
                ),
                int(report_df["Weekend"].sum()),
                int(
                    report_df[
                        "Duplicate_Date"
                    ].sum()
                ),
                int(
                    report_df[
                        "Chronology_Issue"
                    ].sum()
                ),
            ],
        }
    )

    manual_review = report_df[
        report_df[
            [
                "Weekend",
                "Duplicate_Date",
                "Chronology_Issue",
            ]
        ].any(axis=1)
        | report_df["Corrected_Date"].eq("")
    ].copy()

    with pd.ExcelWriter(
        report_file,
        engine="openpyxl",
    ) as writer:
        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        report_df.to_excel(
            writer,
            sheet_name="All_Dates",
            index=False,
        )

        manual_review.to_excel(
            writer,
            sheet_name="Manual_Review",
            index=False,
        )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

    return clean_file, report_file


# ==========================================================
# PUBLIC RUNNER
# ==========================================================

def run_date_repair(
    input_file: Path,
    sheet_name: str | int = 0,
) -> DateRepairResult:
    """
    Run the complete date-repair process.
    """

    if not input_file.exists():
        raise FileNotFoundError(
            f"Workbook not found: {input_file}"
        )

    dataframe = pd.read_excel(
        input_file,
        sheet_name=sheet_name,
        engine="openpyxl",
    )

    dataframe.columns = (
        dataframe.columns
        .astype(str)
        .str.strip()
    )

    clean_df, report_df = repair_date_column(
        dataframe=dataframe,
        date_column=DATE_COLUMN,
    )

    clean_file, report_file = export_results(
        clean_df=clean_df,
        report_df=report_df,
        output_folder=OUTPUT_DIR,
    )

    invalid_count = int(
        report_df["Corrected_Date"].eq("").sum()
    )

    duplicate_count = int(
        report_df["Duplicate_Date"].sum()
    )

    weekend_count = int(
        report_df["Weekend"].sum()
    )

    repaired_count = int(
        report_df["Changed"].sum()
    )

    unchanged_count = (
        len(report_df)
        - repaired_count
        - invalid_count
    )

    success = (
        invalid_count == 0
        and duplicate_count == 0
        and int(
            report_df[
                "Chronology_Issue"
            ].sum()
        ) == 0
    )

    return DateRepairResult(
        success=success,
        input_file=input_file,
        clean_file=clean_file,
        report_file=report_file,
        rows_checked=len(report_df),
        rows_repaired=repaired_count,
        rows_unchanged=unchanged_count,
        rows_invalid=invalid_count,
        duplicate_dates=duplicate_count,
        weekend_dates=weekend_count,
    )


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse terminal arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Repair and standardize the Trade_Date "
            "column in the AQSD Participant Database."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the participant workbook.",
    )

    parser.add_argument(
        "--sheet",
        default=0,
        help=(
            "Worksheet name or zero-based worksheet "
            "number. Default: first worksheet."
        ),
    )

    return parser.parse_args()


def normalize_sheet_argument(
    value: Any,
) -> str | int:
    """
    Convert a numeric sheet argument to an integer.
    """

    text = str(value).strip()

    if text.isdigit():
        return int(text)

    return text


def main() -> int:
    """
    Run from the terminal.
    """

    arguments = parse_arguments()

    result = run_date_repair(
        input_file=(
            arguments.input_file
            .expanduser()
            .resolve()
        ),
        sheet_name=normalize_sheet_argument(
            arguments.sheet
        ),
    )

    print()
    print("=" * 72)
    print("AQSD DATE REPAIR UTILITY")
    print("=" * 72)
    print(
        f"Status          : "
        f"{'PASS' if result.success else 'REVIEW REQUIRED'}"
    )
    print(
        f"Rows Checked    : {result.rows_checked}"
    )
    print(
        f"Dates Repaired  : {result.rows_repaired}"
    )
    print(
        f"Dates Unchanged : {result.rows_unchanged}"
    )
    print(
        f"Invalid Dates   : {result.rows_invalid}"
    )
    print(
        f"Duplicate Rows  : {result.duplicate_dates}"
    )
    print(
        f"Weekend Dates   : {result.weekend_dates}"
    )
    print(
        f"Clean Workbook  : {result.clean_file}"
    )
    print(
        f"Repair Report   : {result.report_file}"
    )
    print("=" * 72)

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())