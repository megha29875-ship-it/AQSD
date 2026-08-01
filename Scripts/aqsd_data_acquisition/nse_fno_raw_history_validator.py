"""
AQSD
NSE F&O Raw Historical Data Validator

Module : NHRV-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Validate the NSE F&O raw historical archive before parsing or
database ingestion.

Validation
----------
1. Resolve the requested NSE trading sessions from the AQSD calendar.
2. Confirm one expected NSE F&O UDiFF Bhavcopy ZIP per session.
3. Confirm no requested session is missing.
4. Confirm no duplicate matching ZIP exists for a requested session.
5. Validate ZIP structure.
6. Validate that the expected CSV exists inside each ZIP.
7. Detect non-trading-date F&O ZIP contamination inside the window.
8. Produce an audit CSV and summary JSON.

Safety
------
READ ONLY.

This module does not:
- download data
- modify raw files
- parse contracts
- modify the database
- fabricate missing sessions
- delete anything
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from Scripts.aqsd_core.paths import (
    NSE_DERIVATIVES_RAW_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "NHRV-001"
MODULE_VERSION: Final[str] = "1.0.0"

DEFAULT_SESSIONS: Final[int] = 250

TRADING_CALENDAR_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "NSE_Trading_Calendar.csv"
)

RAW_ROOT: Final[Path] = (
    NSE_DERIVATIVES_RAW_DIR
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Raw_History_Validation_Audit.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Raw_History_Validation_Summary.json"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class ValidationRow:
    trade_date: str
    expected_filename: str
    session_dir_exists: bool
    expected_zip_exists: bool
    matching_zip_count: int
    duplicate_match: bool
    zip_valid: bool
    expected_csv_inside: bool
    sha256: str
    size_bytes: int
    status: str
    message: str


# ==========================================================
# HELPERS
# ==========================================================

def separator(character: str = "-") -> None:
    print(character * 100)


def heading(text: str) -> None:
    print()
    separator("=")
    print(text)
    separator("=")


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def expected_zip_filename(
    trading_date: date,
) -> str:
    date_token = trading_date.strftime(
        "%Y%m%d"
    )

    return (
        "BhavCopy_NSE_FO_0_0_0_"
        f"{date_token}"
        "_F_0000.csv.zip"
    )


def expected_csv_filename(
    trading_date: date,
) -> str:
    zip_name = expected_zip_filename(
        trading_date
    )

    return zip_name.removesuffix(
        ".zip"
    )


def calculate_sha256(
    file_path: Path,
) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_trading_sessions(
    *,
    sessions: int,
    end_date: date | None,
) -> list[date]:
    if sessions <= 0:
        raise ValueError(
            "sessions must be greater than zero."
        )

    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(
            "AQSD trading calendar not found: "
            f"{TRADING_CALENDAR_FILE}"
        )

    frame = pd.read_csv(
        TRADING_CALENDAR_FILE,
        low_memory=False,
    )

    if "trade_date" not in frame.columns:
        raise RuntimeError(
            "Trading calendar is missing trade_date."
        )

    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"],
        errors="coerce",
    )

    frame = frame.dropna(
        subset=["trade_date"]
    )

    if "is_trading_day" in frame.columns:
        values = (
            frame["is_trading_day"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        trading_mask = values.isin(
            {
                "true",
                "1",
                "yes",
            }
        )

        frame = frame.loc[
            trading_mask
        ].copy()

    if end_date is not None:
        frame = frame.loc[
            frame["trade_date"].dt.date
            <= end_date
        ].copy()

    frame = (
        frame
        .sort_values("trade_date")
        .drop_duplicates(
            subset=["trade_date"],
            keep="last",
        )
    )

    if len(frame) < sessions:
        raise RuntimeError(
            "Trading calendar does not contain enough "
            f"sessions. Required={sessions}, "
            f"Available={len(frame)}."
        )

    selected = frame.tail(
        sessions
    )

    return [
        timestamp.date()
        for timestamp in selected[
            "trade_date"
        ]
    ]


def validate_zip(
    *,
    zip_path: Path,
    trading_date: date,
    deep: bool,
) -> tuple[
    bool,
    bool,
    str,
]:
    expected_csv = expected_csv_filename(
        trading_date
    )

    try:
        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as archive:
            names = archive.namelist()

            expected_csv_inside = any(
                Path(name).name
                == expected_csv
                for name in names
            )

            if deep:
                bad_member = archive.testzip()

                if bad_member is not None:
                    return (
                        False,
                        expected_csv_inside,
                        f"Corrupt ZIP member: {bad_member}",
                    )

            return (
                True,
                expected_csv_inside,
                "",
            )

    except (
        zipfile.BadZipFile,
        OSError,
    ) as exc:
        return (
            False,
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==========================================================
# SESSION VALIDATION
# ==========================================================

def validate_session(
    *,
    trading_date: date,
    deep: bool,
) -> ValidationRow:
    date_text = trading_date.isoformat()

    session_dir = (
        RAW_ROOT
        / date_text
    )

    expected_name = (
        expected_zip_filename(
            trading_date
        )
    )

    expected_path = (
        session_dir
        / expected_name
    )

    session_dir_exists = (
        session_dir.is_dir()
    )

    matching_files: list[Path] = []

    if session_dir_exists:
        date_token = trading_date.strftime(
            "%Y%m%d"
        )

        matching_files = sorted(
            session_dir.glob(
                "BhavCopy_NSE_FO_0_0_0_"
                f"{date_token}"
                "_F_*.csv.zip"
            )
        )

    matching_zip_count = len(
        matching_files
    )

    duplicate_match = (
        matching_zip_count > 1
    )

    expected_zip_exists = (
        expected_path.is_file()
    )

    if not session_dir_exists:
        return ValidationRow(
            trade_date=date_text,
            expected_filename=expected_name,
            session_dir_exists=False,
            expected_zip_exists=False,
            matching_zip_count=0,
            duplicate_match=False,
            zip_valid=False,
            expected_csv_inside=False,
            sha256="",
            size_bytes=0,
            status="MISSING",
            message="Session directory not found.",
        )

    if not expected_zip_exists:
        return ValidationRow(
            trade_date=date_text,
            expected_filename=expected_name,
            session_dir_exists=True,
            expected_zip_exists=False,
            matching_zip_count=matching_zip_count,
            duplicate_match=duplicate_match,
            zip_valid=False,
            expected_csv_inside=False,
            sha256="",
            size_bytes=0,
            status="MISSING",
            message="Expected NSE F&O ZIP not found.",
        )

    zip_valid, expected_csv_inside, zip_message = (
        validate_zip(
            zip_path=expected_path,
            trading_date=trading_date,
            deep=deep,
        )
    )

    size_bytes = (
        expected_path.stat().st_size
    )

    sha256 = calculate_sha256(
        expected_path
    )

    if duplicate_match:
        status = "FAILED"
        message = (
            "Duplicate matching NSE F&O ZIP files "
            "found for session."
        )

    elif not zip_valid:
        status = "FAILED"
        message = (
            zip_message
            or "ZIP validation failed."
        )

    elif not expected_csv_inside:
        status = "FAILED"
        message = (
            "Expected UDiFF CSV not found inside ZIP."
        )

    elif size_bytes <= 0:
        status = "FAILED"
        message = "ZIP file is empty."

    else:
        status = "PASS"
        message = ""

    return ValidationRow(
        trade_date=date_text,
        expected_filename=expected_name,
        session_dir_exists=True,
        expected_zip_exists=True,
        matching_zip_count=matching_zip_count,
        duplicate_match=duplicate_match,
        zip_valid=zip_valid,
        expected_csv_inside=expected_csv_inside,
        sha256=sha256,
        size_bytes=size_bytes,
        status=status,
        message=message,
    )


# ==========================================================
# CONTAMINATION CHECK
# ==========================================================

def detect_non_session_archives(
    *,
    first_session: date,
    last_session: date,
    expected_sessions: set[str],
) -> list[str]:
    """
    Detect valid-looking F&O archive ZIPs inside the requested
    date window that belong to dates not present in the trading
    calendar selection.
    """

    contamination: list[str] = []

    if not RAW_ROOT.exists():
        return contamination

    for directory in RAW_ROOT.iterdir():

        if not directory.is_dir():
            continue

        try:
            directory_date = parse_date(
                directory.name
            )
        except ValueError:
            continue

        if not (
            first_session
            <= directory_date
            <= last_session
        ):
            continue

        date_text = (
            directory_date.isoformat()
        )

        if date_text in expected_sessions:
            continue

        pattern = (
            "BhavCopy_NSE_FO_0_0_0_"
            f"{directory_date:%Y%m%d}"
            "_F_*.csv.zip"
        )

        matching = list(
            directory.glob(
                pattern
            )
        )

        if matching:
            contamination.append(
                date_text
            )

    return sorted(
        contamination
    )


# ==========================================================
# OUTPUT
# ==========================================================

def save_audit(
    rows: list[ValidationRow],
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        asdict(rows[0]).keys()
    )

    with AUDIT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                asdict(row)
            )


def save_summary(
    *,
    requested_sessions: int,
    resolved_sessions: int,
    first_session: date,
    last_session: date,
    rows: list[ValidationRow],
    contamination: list[str],
    deep: bool,
    status: str,
) -> None:
    counts = {
        "pass": sum(
            row.status == "PASS"
            for row in rows
        ),
        "missing": sum(
            row.status == "MISSING"
            for row in rows
        ),
        "failed": sum(
            row.status == "FAILED"
            for row in rows
        ),
        "duplicate_sessions": sum(
            row.duplicate_match
            for row in rows
        ),
    }

    summary = {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "requested_sessions": requested_sessions,
        "resolved_sessions": resolved_sessions,
        "first_session": first_session.isoformat(),
        "last_session": last_session.isoformat(),
        "raw_root": str(RAW_ROOT),
        "trading_calendar": str(
            TRADING_CALENDAR_FILE
        ),
        "deep_zip_test": deep,
        "counts": counts,
        "non_session_archive_dates": (
            contamination
        ),
        "audit_csv": str(AUDIT_CSV),
        "status": status,
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================================
# ENGINE
# ==========================================================

def run_validation(
    *,
    sessions: int,
    end_date: date | None,
    deep: bool,
) -> bool:
    heading(
        "AQSD NSE F&O RAW HISTORICAL VALIDATION"
    )

    trading_sessions = (
        load_trading_sessions(
            sessions=sessions,
            end_date=end_date,
        )
    )

    first_session = (
        trading_sessions[0]
    )

    last_session = (
        trading_sessions[-1]
    )

    print(
        f"Module                  : {MODULE_ID}"
    )
    print(
        f"Version                 : {MODULE_VERSION}"
    )
    print(
        f"Requested Sessions      : {sessions}"
    )
    print(
        f"Resolved Sessions       : {len(trading_sessions)}"
    )
    print(
        f"First Session           : {first_session}"
    )
    print(
        f"Last Session            : {last_session}"
    )
    print(
        f"Raw Root                : {RAW_ROOT}"
    )
    print(
        f"Trading Calendar        : {TRADING_CALENDAR_FILE}"
    )
    print(
        f"Deep ZIP Test           : {'YES' if deep else 'NO'}"
    )

    separator()

    rows: list[
        ValidationRow
    ] = []

    total = len(
        trading_sessions
    )

    for index, trading_date in enumerate(
        trading_sessions,
        start=1,
    ):
        result = validate_session(
            trading_date=trading_date,
            deep=deep,
        )

        rows.append(
            result
        )

        print(
            f"[{index:03d}/{total:03d}] "
            f"{trading_date} "
            f"{result.status}"
        )

    expected_session_set = {
        session.isoformat()
        for session in trading_sessions
    }

    contamination = (
        detect_non_session_archives(
            first_session=first_session,
            last_session=last_session,
            expected_sessions=(
                expected_session_set
            ),
        )
    )

    passed = sum(
        row.status == "PASS"
        for row in rows
    )

    missing = sum(
        row.status == "MISSING"
        for row in rows
    )

    failed = sum(
        row.status == "FAILED"
        for row in rows
    )

    duplicates = sum(
        row.duplicate_match
        for row in rows
    )

    overall_success = (
        passed == total
        and missing == 0
        and failed == 0
        and duplicates == 0
        and len(contamination) == 0
    )

    status = (
        "SUCCESS"
        if overall_success
        else "FAILED"
    )

    save_audit(
        rows
    )

    save_summary(
        requested_sessions=sessions,
        resolved_sessions=total,
        first_session=first_session,
        last_session=last_session,
        rows=rows,
        contamination=contamination,
        deep=deep,
        status=status,
    )

    heading(
        "AQSD RAW HISTORY VALIDATION SUMMARY"
    )

    print(
        f"Expected Trading Dates  : {total}"
    )
    print(
        f"Validated Sessions      : {passed}"
    )
    print(
        f"Missing Sessions        : {missing}"
    )
    print(
        f"Failed Sessions         : {failed}"
    )
    print(
        f"Duplicate Sessions      : {duplicates}"
    )
    print(
        f"Non-Session Archives    : {len(contamination)}"
    )

    if contamination:
        print()
        print(
            "Non-session archive dates:"
        )

        for value in contamination:
            print(
                f"  {value}"
            )

    separator()

    print(
        f"Audit CSV               : {AUDIT_CSV}"
    )
    print(
        f"Summary JSON            : {SUMMARY_JSON}"
    )

    separator()

    print(
        "Raw Files               : UNCHANGED"
    )
    print(
        "Historical Fabrication  : PROHIBITED"
    )
    print(
        "Deletion                : NONE"
    )

    separator()

    print(
        f"Status                  : {status}"
    )

    separator("=")

    return overall_success


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    heading(
        "AQSD NSE F&O RAW HISTORY VALIDATOR STATUS"
    )

    print(
        f"Module                  : {MODULE_ID}"
    )
    print(
        f"Version                 : {MODULE_VERSION}"
    )
    print(
        f"Trading Calendar        : {TRADING_CALENDAR_FILE}"
    )
    print(
        f"Calendar Exists         : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )
    print(
        f"Raw Root                : {RAW_ROOT}"
    )
    print(
        f"Raw Root Exists         : "
        f"{'YES' if RAW_ROOT.exists() else 'NO'}"
    )
    print(
        f"Default Sessions        : {DEFAULT_SESSIONS}"
    )
    print(
        f"Audit CSV               : {AUDIT_CSV}"
    )
    print(
        f"Summary JSON            : {SUMMARY_JSON}"
    )

    separator("=")


# ==========================================================
# CLI
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate AQSD NSE F&O raw historical archive."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
        help=(
            "Number of trading sessions to validate. "
            f"Default {DEFAULT_SESSIONS}."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Last permitted trading date YYYY-MM-DD. "
            "Default: latest date in AQSD trading calendar."
        ),
    )

    parser.add_argument(
        "--deep",
        action="store_true",
        help=(
            "Run zipfile.testzip() on every requested archive. "
            "Slower but performs deeper ZIP integrity checking."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show validator configuration only.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = (
        parse_arguments()
    )

    if arguments.status:
        show_status()
        return

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else None
    )

    try:
        success = run_validation(
            sessions=arguments.sessions,
            end_date=end_date,
            deep=arguments.deep,
        )

    except Exception as exc:
        print()
        separator("=")
        print(
            "AQSD NSE F&O RAW HISTORICAL VALIDATION"
        )
        separator("=")
        print(
            "Status : FAILED"
        )
        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )
        separator("=")

        raise SystemExit(
            1
        ) from exc

    if not success:
        raise SystemExit(
            1
        )


if __name__ == "__main__":
    main()
