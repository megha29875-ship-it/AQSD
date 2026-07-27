"""
AQSD
Research Database Builder

Module    : database.py
Module ID : DB-001
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Builds the AQSD Master Database from the raw participant workbook.

Process
-------
1. Read the source workbook.
2. Validate columns, dates, numeric data and trading sessions.
3. Generate permanent AQSD IDs.
4. Add calendar metadata.
5. Export the master database.
6. Create the validation report.
7. Create the database manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
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
OUTPUT_DIR = BASE_DIR / "Output"
LOG_DIR = BASE_DIR / "Logs"

# Allow imports such as:
# from aqsd_core...
# from aqsd_database...
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ==========================================================
# AQSD IMPORTS
# ==========================================================

from aqsd_core.logger import get_logger, log_end, log_start
from aqsd_database.exporter import DatabaseExporter
from aqsd_database.id_generator import AQSDIDGenerator
from aqsd_database.models import (
    DatabaseResult,
    ValidationSummary,
    WorkbookInfo,
)
from aqsd_database.reader import read_workbook
from aqsd_database.report_generator import ReportGenerator
from aqsd_database.validator import DatabaseValidator


# ==========================================================
# MODULE CONSTANTS
# ==========================================================

MODULE_ID = "DB-001"
MODULE_NAME = "AQSD Research Database Builder"
MODULE_VERSION = "1.0.0"

DATE_COLUMN = "Date"

MASTER_EXCEL_FILENAME = "AQSD_Master_Database.xlsx"
MASTER_CSV_FILENAME = "AQSD_Master_Database.csv"
VALIDATION_REPORT_FILENAME = "validation_report.xlsx"
MANIFEST_FILENAME = "database_manifest.json"

logger = get_logger(__name__)


# ==========================================================
# PARTICIPANT WORKBOOK CONFIGURATION
# ==========================================================
#
# IMPORTANT:
# Replace or add column names below so they exactly match
# the headings in your participant workbook.
#
# The Date column is mandatory.
#
# Start with Date only if your workbook headings have not yet
# been confirmed. We can add all participant columns after
# checking the actual workbook.
# ==========================================================

REQUIRED_COLUMNS: list[str] = [
    "Date",
]

NUMERIC_COLUMNS: list[str] = [
    # Examples:
    # "NIFTY",
    # "BANKNIFTY",
    # "FII Index Futures Long",
    # "FII Index Futures Short",
    # "PRO Index Futures Long",
    # "PRO Index Futures Short",
    # "CLIENT Index Futures Long",
    # "CLIENT Index Futures Short",
]


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def calculate_sha256(file_path: Path) -> str:
    """
    Calculate the SHA-256 checksum of a file.
    """

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def get_file_metadata(file_path: Path) -> dict[str, Any]:
    """
    Return source workbook metadata.
    """

    statistics = file_path.stat()

    return {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "file_size_bytes": statistics.st_size,
        "last_modified": datetime.fromtimestamp(
            statistics.st_mtime
        ).isoformat(timespec="seconds"),
        "sha256": calculate_sha256(file_path),
    }


def create_build_id() -> str:
    """
    Create a unique database build identifier.

    Example
    -------
    DB001-20260727-201530
    """

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"DB001-{timestamp}"


def create_build_folder(build_id: str) -> Path:
    """
    Create a separate output folder for the current build.
    """

    build_folder = OUTPUT_DIR / "Database_Builds" / build_id

    build_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return build_folder


def convert_validation_result(
    core_result: Any,
) -> ValidationSummary:
    """
    Convert the shared core validation result into the
    Database Builder validation model.
    """

    summary = ValidationSummary()

    for error in getattr(core_result, "errors", []):
        summary.add_error(str(error))

    for warning in getattr(core_result, "warnings", []):
        summary.add_warning(str(warning))

    return summary


def add_calendar_metadata(
    dataframe: pd.DataFrame,
    date_column: str = DATE_COLUMN,
) -> pd.DataFrame:
    """
    Add commonly required date fields to the master database.
    """

    df = dataframe.copy()

    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="raise",
    ).dt.normalize()

    iso_calendar = df[date_column].dt.isocalendar()

    df["Trade_Date"] = df[date_column]
    df["Trading_Day_No"] = range(1, len(df) + 1)
    df["Calendar_Year"] = df[date_column].dt.year
    df["Calendar_Month"] = df[date_column].dt.month
    df["Month_Name"] = df[date_column].dt.strftime("%b")
    df["Calendar_Quarter"] = (
        "Q" + df[date_column].dt.quarter.astype(str)
    )
    df["ISO_Week_No"] = iso_calendar.week.astype(int)
    df["Day_Name"] = df[date_column].dt.day_name()

    # Indian financial year:
    # April to March
    financial_year_start = df[date_column].dt.year.where(
        df[date_column].dt.month >= 4,
        df[date_column].dt.year - 1,
    )

    df["Financial_Year"] = (
        "FY"
        + financial_year_start.astype(str).str[-2:]
        + "-"
        + (financial_year_start + 1).astype(str).str[-2:]
    )

    return df


def create_manifest(
    *,
    build_id: str,
    input_file: Path,
    workbook: WorkbookInfo,
    validation: ValidationSummary,
    input_rows: int,
    output_rows: int,
    execution_time: float,
    output_files: dict[str, Path | None],
) -> dict[str, Any]:
    """
    Create the database build manifest.
    """

    return {
        "aqsd": {
            "project": "AQSD",
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
        },
        "build": {
            "build_id": build_id,
            "build_time": datetime.now().isoformat(
                timespec="seconds"
            ),
            "execution_time_seconds": round(
                execution_time,
                4,
            ),
            "status": (
                "SUCCESS"
                if validation.passed
                else "VALIDATION_FAILED"
            ),
        },
        "source_workbook": {
            **get_file_metadata(input_file),
            "sheet_name": workbook.sheet_name,
            "rows": workbook.rows,
            "columns": workbook.columns,
            "loaded_at": workbook.loaded_at.isoformat(
                timespec="seconds"
            ),
        },
        "validation": {
            "passed": validation.passed,
            "error_count": validation.error_count,
            "warning_count": validation.warning_count,
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "database": {
            "input_rows": input_rows,
            "output_rows": output_rows,
        },
        "outputs": {
            name: str(path) if path else None
            for name, path in output_files.items()
        },
    }


def save_manifest(
    manifest: dict[str, Any],
    file_path: Path,
) -> Path:
    """
    Save the database manifest as JSON.
    """

    with file_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=4,
            ensure_ascii=False,
            default=str,
        )

    logger.info("Manifest created: %s", file_path)

    return file_path


def create_failed_workbook_info(
    input_file: Path,
    sheet_name: str | int,
) -> WorkbookInfo:
    """
    Create basic workbook information when reading fails.
    """

    return WorkbookInfo(
        file_path=input_file,
        file_name=input_file.name,
        sheet_name=str(sheet_name),
        rows=0,
        columns=0,
    )


# ==========================================================
# DATABASE BUILDER
# ==========================================================

def build_database(
    input_file: Path,
    sheet_name: str | int = 0,
) -> DatabaseResult:
    """
    Build the AQSD Master Database.

    Parameters
    ----------
    input_file:
        Path to the raw participant workbook.

    sheet_name:
        Excel worksheet name or worksheet index.

    Returns
    -------
    DatabaseResult
        Structured result of the database build.
    """

    start_time = time.perf_counter()
    build_id = create_build_id()
    build_folder = create_build_folder(build_id)

    log_start(logger, f"{MODULE_ID} - {MODULE_NAME}")

    logger.info("Build ID: %s", build_id)
    logger.info("Input workbook: %s", input_file)
    logger.info("Output folder: %s", build_folder)

    empty_dataframe = pd.DataFrame()
    validation = ValidationSummary()
    workbook = create_failed_workbook_info(
        input_file,
        sheet_name,
    )

    output_excel: Path | None = None
    output_csv: Path | None = None
    validation_report: Path | None = None
    manifest_file: Path | None = None

    try:
        # --------------------------------------------------
        # 1. Validate source file
        # --------------------------------------------------

        if not input_file.exists():
            validation.add_error(
                f"DB010 : Source workbook not found -> "
                f"{input_file}"
            )

            raise FileNotFoundError(
                f"Source workbook not found: {input_file}"
            )

        if input_file.suffix.lower() not in {
            ".xlsx",
            ".xlsm",
        }:
            validation.add_error(
                "DB011 : Source file must be an Excel "
                "workbook (.xlsx or .xlsm)"
            )

            raise ValueError(
                "Unsupported source workbook format."
            )

        # --------------------------------------------------
        # 2. Read workbook
        # --------------------------------------------------

        dataframe, workbook = read_workbook(
            file_path=input_file,
            sheet_name=sheet_name,
        )

        logger.info(
            "Input rows: %d",
            len(dataframe),
        )

        # --------------------------------------------------
        # 3. Validate workbook
        # --------------------------------------------------

        validator = DatabaseValidator(
            required_columns=REQUIRED_COLUMNS,
            numeric_columns=NUMERIC_COLUMNS,
            date_column=DATE_COLUMN,
        )

        try:
            core_validation = validator.validate(
                dataframe
            )

            validation = convert_validation_result(
                core_validation
            )

        except KeyError as exception:
            validation.add_error(
                "DB003 : Required date or validation "
                f"column missing -> {exception}"
            )

        except Exception as exception:
            validation.add_error(
                "DB012 : Validation engine failed -> "
                f"{exception}"
            )

            logger.exception(
                "Validation engine failed."
            )

        # --------------------------------------------------
        # 4. Always create validation report
        # --------------------------------------------------

        report_generator = ReportGenerator(
            output_folder=build_folder
        )

        validation_report = (
            report_generator.create_validation_report(
                validation=validation,
                filename=VALIDATION_REPORT_FILENAME,
            )
        )

        # --------------------------------------------------
        # 5. Stop if critical validation failed
        # --------------------------------------------------

        if not validation.passed:
            elapsed = time.perf_counter() - start_time

            logger.error(
                "Database build rejected. "
                "Errors: %d | Warnings: %d",
                validation.error_count,
                validation.warning_count,
            )

            manifest = create_manifest(
                build_id=build_id,
                input_file=input_file,
                workbook=workbook,
                validation=validation,
                input_rows=len(dataframe),
                output_rows=0,
                execution_time=elapsed,
                output_files={
                    "master_excel": None,
                    "master_csv": None,
                    "validation_report": validation_report,
                    "manifest": (
                        build_folder / MANIFEST_FILENAME
                    ),
                },
            )

            manifest_file = save_manifest(
                manifest=manifest,
                file_path=build_folder / MANIFEST_FILENAME,
            )

            return DatabaseResult(
                success=False,
                dataframe=dataframe,
                workbook=workbook,
                validation=validation,
                rows_processed=0,
                execution_time=elapsed,
                output_file=None,
                validation_report=validation_report,
                log_file=LOG_DIR / "aqsd.log",
            )

        # --------------------------------------------------
        # 6. Generate AQSD IDs
        # --------------------------------------------------

        id_generator = AQSDIDGenerator(
            prefix="AQSD",
            date_column=DATE_COLUMN,
        )

        master_dataframe = id_generator.generate(
            dataframe
        )

        # --------------------------------------------------
        # 7. Add calendar metadata
        # --------------------------------------------------

        master_dataframe = add_calendar_metadata(
            dataframe=master_dataframe,
            date_column=DATE_COLUMN,
        )

        # --------------------------------------------------
        # 8. Export database
        # --------------------------------------------------

        exporter = DatabaseExporter(
            output_folder=build_folder
        )

        output_excel = exporter.export_excel(
            dataframe=master_dataframe,
            filename=MASTER_EXCEL_FILENAME,
        )

        output_csv = exporter.export_csv(
            dataframe=master_dataframe,
            filename=MASTER_CSV_FILENAME,
        )

        elapsed = time.perf_counter() - start_time

        # --------------------------------------------------
        # 9. Create manifest
        # --------------------------------------------------

        manifest_path = build_folder / MANIFEST_FILENAME

        manifest = create_manifest(
            build_id=build_id,
            input_file=input_file,
            workbook=workbook,
            validation=validation,
            input_rows=len(dataframe),
            output_rows=len(master_dataframe),
            execution_time=elapsed,
            output_files={
                "master_excel": output_excel,
                "master_csv": output_csv,
                "validation_report": validation_report,
                "manifest": manifest_path,
            },
        )

        manifest_file = save_manifest(
            manifest=manifest,
            file_path=manifest_path,
        )

        logger.info(
            "Database build completed successfully."
        )
        logger.info(
            "Rows processed: %d",
            len(master_dataframe),
        )
        logger.info(
            "Execution time: %.3f seconds",
            elapsed,
        )
        logger.info(
            "Master database: %s",
            output_excel,
        )
        logger.info(
            "Validation report: %s",
            validation_report,
        )
        logger.info(
            "Manifest: %s",
            manifest_file,
        )

        return DatabaseResult(
            success=True,
            dataframe=master_dataframe,
            workbook=workbook,
            validation=validation,
            rows_processed=len(master_dataframe),
            execution_time=elapsed,
            output_file=output_excel,
            validation_report=validation_report,
            log_file=LOG_DIR / "aqsd.log",
        )

    except Exception as exception:
        elapsed = time.perf_counter() - start_time

        if validation.passed:
            validation.add_error(
                f"DB099 : Unexpected database build failure "
                f"-> {exception}"
            )

        logger.exception(
            "Database build failed."
        )

        try:
            report_generator = ReportGenerator(
                output_folder=build_folder
            )

            validation_report = (
                report_generator.create_validation_report(
                    validation=validation,
                    filename=VALIDATION_REPORT_FILENAME,
                )
            )
        except Exception:
            logger.exception(
                "Could not create validation report."
            )

        if input_file.exists():
            try:
                manifest = create_manifest(
                    build_id=build_id,
                    input_file=input_file,
                    workbook=workbook,
                    validation=validation,
                    input_rows=workbook.rows,
                    output_rows=0,
                    execution_time=elapsed,
                    output_files={
                        "master_excel": None,
                        "master_csv": None,
                        "validation_report": validation_report,
                        "manifest": (
                            build_folder / MANIFEST_FILENAME
                        ),
                    },
                )

                manifest_file = save_manifest(
                    manifest=manifest,
                    file_path=(
                        build_folder / MANIFEST_FILENAME
                    ),
                )
            except Exception:
                logger.exception(
                    "Could not create failure manifest."
                )

        return DatabaseResult(
            success=False,
            dataframe=empty_dataframe,
            workbook=workbook,
            validation=validation,
            rows_processed=0,
            execution_time=elapsed,
            output_file=None,
            validation_report=validation_report,
            log_file=LOG_DIR / "aqsd.log",
        )

    finally:
        log_end(logger, f"{MODULE_ID} - {MODULE_NAME}")


# ==========================================================
# COMMAND-LINE INTERFACE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Build the AQSD Master Database from a "
            "participant Excel workbook."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the participant Excel workbook.",
    )

    parser.add_argument(
        "--sheet",
        default=0,
        help=(
            "Excel sheet name or zero-based sheet number. "
            "Default: first sheet."
        ),
    )

    return parser.parse_args()


def normalize_sheet_argument(value: Any) -> str | int:
    """
    Convert numeric worksheet arguments into integers.
    """

    text = str(value).strip()

    if text.isdigit():
        return int(text)

    return text


def main() -> int:
    """
    Run DB-001 from the terminal.
    """

    arguments = parse_arguments()

    input_file = arguments.input_file.expanduser().resolve()

    result = build_database(
        input_file=input_file,
        sheet_name=normalize_sheet_argument(
            arguments.sheet
        ),
    )

    print()
    print("=" * 72)
    print("AQSD DATABASE BUILDER")
    print("=" * 72)
    print(
        f"Status           : "
        f"{'SUCCESS' if result.success else 'FAILED'}"
    )
    print(
        f"Rows Processed   : {result.rows_processed}"
    )
    print(
        f"Errors           : "
        f"{result.validation.error_count}"
    )
    print(
        f"Warnings         : "
        f"{result.validation.warning_count}"
    )
    print(
        f"Execution Time   : "
        f"{result.execution_time:.3f} seconds"
    )

    if result.output_file:
        print(
            f"Master Database  : {result.output_file}"
        )

    if result.validation_report:
        print(
            f"Validation Report: "
            f"{result.validation_report}"
        )

    print("=" * 72)

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())