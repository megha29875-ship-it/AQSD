"""
AQSD
NSE Historical F&O Downloader

Module : NHF-001
Version: 1.2.0
Author : AQSD

Purpose
-------
Download official NSE historical F&O UDiFF Common Bhavcopy files
for a configurable number of ACTUAL NSE trading sessions.

Phase 1:
    60 trading sessions

Phase 2:
    250 trading sessions

Universe:
    Entire NSE F&O universe contained in each official
    NSE UDiFF F&O bhavcopy.

Architecture
------------
NSE Trading Calendar
        ↓
Requested Historical Sessions
        ↓
Official NSE UDiFF F&O Bhavcopy
        ↓
Immutable Raw Storage
        ↓
NFP-001 Bhavcopy Parser
        ↓
Futures + Options + All Underlyings

Storage
-------
Data/Raw/NSE/Derivatives/YYYY-MM-DD/

Important AQSD Rules
--------------------
1. Raw NSE data is NEVER modified.
2. Existing valid raw files are preserved.
3. HTML/error pages are rejected.
4. ZIP integrity is validated.
5. Every file gets a SHA256 fingerprint.
6. Missing dates are never fabricated.
7. Downloader can safely resume interrupted runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd
import requests

from Scripts.aqsd_core.paths import (
    NSE_DERIVATIVES_RAW_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "NHF-001"
MODULE_VERSION: Final[str] = "1.2.0"

BASE_DIR: Final[Path] = PROJECT_ROOT

TRADING_CALENDAR_FILE: Final[Path] = (
    BASE_DIR
    / "Data"
    / "NSE_Trading_Calendar.csv"
)

RAW_ROOT: Final[Path] = NSE_DERIVATIVES_RAW_DIR


AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "NSE_Historical_FNO_Download_Audit.csv"
)

SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "NSE_Historical_FNO_Download_Summary.json"
)

NSE_HOME: Final[str] = (
    "https://www.nseindia.com/"
)

NSE_ARCHIVE_ROOT: Final[str] = (
    "https://nsearchives.nseindia.com/content/fo/"
)

DEFAULT_SESSIONS: Final[int] = 60

MAX_SESSIONS: Final[int] = 2000

REQUEST_TIMEOUT: Final[int] = 45

REQUEST_DELAY_SECONDS: Final[float] = 0.30

MAX_RETRIES: Final[int] = 3

RETRY_DELAY_SECONDS: Final[float] = 2.0


# ==========================================================
# REPORT MODEL
# ==========================================================

@dataclass(frozen=True)
class ReportDefinition:
    """
    Official NSE report definition.
    """

    report_id: str
    display_name: str
    filename_template: str
    required: bool


# ==========================================================
# REPORT CATALOG
# ==========================================================
#
# This report path has already been validated successfully
# against NSE archive downloads in AQSD.
#
# Example:
#
# BhavCopy_NSE_FO_0_0_0_20260731_F_0000.csv.zip
#
# ==========================================================

REPORTS: Final[
    tuple[ReportDefinition, ...]
] = (
    ReportDefinition(
        report_id="udiff_bhavcopy",
        display_name=(
            "F&O UDiFF Common Bhavcopy Final"
        ),
        filename_template=(
            "BhavCopy_NSE_FO_0_0_0_"
            "{yyyymmdd}_F_0000.csv.zip"
        ),
        required=True,
    ),
)


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. "
            "Use YYYY-MM-DD."
        ) from exc


def ensure_directories() -> None:
    """
    Create AQSD directories.
    """

    RAW_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def sha256_file(
    path: Path,
) -> str:
    """
    Calculate SHA256 fingerprint.
    """

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


# ==========================================================
# TRADING CALENDAR
# ==========================================================

def load_trading_calendar() -> pd.DataFrame:
    """
    Load AQSD NSE trading calendar.
    """

    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(
            "NSE Trading Calendar not found:\n"
            f"{TRADING_CALENDAR_FILE}"
        )

    frame = pd.read_csv(
        TRADING_CALENDAR_FILE,
        low_memory=False,
    )

    if "trade_date" not in frame.columns:
        raise RuntimeError(
            "NSE Trading Calendar does not contain "
            "'trade_date'."
        )

    frame[
        "trade_date"
    ] = pd.to_datetime(
        frame[
            "trade_date"
        ],
        errors="coerce",
    )

    frame = (
        frame
        .dropna(
            subset=[
                "trade_date"
            ]
        )
        .sort_values(
            "trade_date"
        )
        .drop_duplicates(
            subset=[
                "trade_date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return frame


def resolve_target_dates(
    *,
    sessions: int,
    end_date: date,
) -> list[date]:
    """
    Resolve exact NSE trading sessions.
    """

    sessions = max(
        1,
        min(
            int(
                sessions
            ),
            MAX_SESSIONS,
        ),
    )

    calendar = load_trading_calendar()

    eligible = calendar.loc[
        calendar[
            "trade_date"
        ].dt.date
        <= end_date
    ].copy()

    if eligible.empty:
        raise RuntimeError(
            "No NSE trading sessions available "
            f"on or before {end_date.isoformat()}."
        )

    if len(
        eligible
    ) < sessions:
        raise RuntimeError(
            "Trading calendar does not contain enough "
            f"sessions. Requested={sessions}; "
            f"Available={len(eligible)}."
        )

    selected = eligible.tail(
        sessions
    )

    return [
        value.date()
        for value in selected[
            "trade_date"
        ]
    ]


# ==========================================================
# HTTP SESSION
# ==========================================================

def create_nse_session() -> requests.Session:
    """
    Create browser-like NSE session.
    """

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "application/zip,"
                "*/*;q=0.8"
            ),

            "Accept-Language": (
                "en-US,en;q=0.9"
            ),

            "Referer": (
                "https://www.nseindia.com/"
            ),

            "Connection": (
                "keep-alive"
            ),
        }
    )

    try:
        session.get(
            NSE_HOME,
            timeout=REQUEST_TIMEOUT,
        )

    except requests.RequestException:
        # Archive host can still work even if
        # homepage initialization fails.
        pass

    return session


# ==========================================================
# FILE NAMING
# ==========================================================

def report_filename(
    *,
    definition: ReportDefinition,
    trade_date: date,
) -> str:
    """
    Resolve report filename.
    """

    return (
        definition
        .filename_template
        .format(
            yyyymmdd=(
                trade_date.strftime(
                    "%Y%m%d"
                )
            ),
            ddmmyyyy=(
                trade_date.strftime(
                    "%d%m%Y"
                )
            ),
        )
    )


def report_url(
    filename: str,
) -> str:
    """
    Build NSE archive URL.
    """

    return (
        NSE_ARCHIVE_ROOT
        + filename
    )


# ==========================================================
# RAW STORAGE
# ==========================================================

def raw_date_directory(
    trade_date: date,
) -> Path:
    """
    Return immutable raw date folder.
    """

    return (
        RAW_ROOT
        / trade_date.isoformat()
    )


# ==========================================================
# RESPONSE VALIDATION
# ==========================================================

def looks_like_html(
    content: bytes,
) -> bool:
    """
    Detect HTML/error response.
    """

    leading = (
        content[:500]
        .lower()
        .lstrip()
    )

    return (
        leading.startswith(
            b"<!doctype html"
        )
        or leading.startswith(
            b"<html"
        )
        or b"<html" in leading
    )


def validate_zip_bytes(
    content: bytes,
    temporary_path: Path,
) -> tuple[
    bool,
    str,
]:
    """
    Validate ZIP integrity using temporary file.
    """

    temporary_path.write_bytes(
        content
    )

    try:
        if not zipfile.is_zipfile(
            temporary_path
        ):
            return (
                False,
                "Downloaded content is not a valid ZIP.",
            )

        with zipfile.ZipFile(
            temporary_path,
            "r",
        ) as archive:

            bad_member = (
                archive.testzip()
            )

            if bad_member is not None:
                return (
                    False,
                    (
                        "ZIP integrity failed for member: "
                        f"{bad_member}"
                    ),
                )

            csv_members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(
                    ".csv"
                )
            ]

            if not csv_members:
                return (
                    False,
                    "ZIP contains no CSV file.",
                )

    except Exception as exc:
        return (
            False,
            (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    return (
        True,
        "ZIP integrity validated.",
    )


# ==========================================================
# EXISTING FILE VALIDATION
# ==========================================================

def validate_existing_file(
    path: Path,
) -> bool:
    """
    Validate previously downloaded raw ZIP.
    """

    try:
        if not path.exists():
            return False

        if not path.is_file():
            return False

        if path.stat().st_size <= 0:
            return False

        if not zipfile.is_zipfile(
            path
        ):
            return False

        with zipfile.ZipFile(
            path,
            "r",
        ) as archive:

            if archive.testzip() is not None:
                return False

            if not any(
                name.lower().endswith(
                    ".csv"
                )
                for name in archive.namelist()
            ):
                return False

        return True

    except Exception:
        return False


# ==========================================================
# DOWNLOAD ONE REPORT
# ==========================================================

def download_report(
    *,
    session: requests.Session,
    trade_date: date,
    definition: ReportDefinition,
    overwrite: bool,
) -> dict[str, object]:
    """
    Download one NSE report safely.
    """

    directory = raw_date_directory(
        trade_date
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = report_filename(
        definition=definition,
        trade_date=trade_date,
    )

    destination = (
        directory
        / filename
    )

    temporary_path = (
        directory
        / (
            filename
            + ".download"
        )
    )

    url = report_url(
        filename
    )

    # ------------------------------------------------------
    # PRESERVE VALID EXISTING RAW FILE
    # ------------------------------------------------------

    if (
        not overwrite
        and validate_existing_file(
            destination
        )
    ):
        return {
            "trade_date": (
                trade_date.isoformat()
            ),

            "report_id": (
                definition.report_id
            ),

            "report_name": (
                definition.display_name
            ),

            "required": (
                definition.required
            ),

            "filename": (
                filename
            ),

            "url": (
                url
            ),

            "status": (
                "SKIPPED EXISTING"
            ),

            "http_status": "",

            "attempts": 0,

            "bytes": (
                destination
                .stat()
                .st_size
            ),

            "sha256": (
                sha256_file(
                    destination
                )
            ),

            "path": str(
                destination
            ),

            "message": (
                "Existing valid immutable raw file preserved."
            ),
        }

    # ------------------------------------------------------
    # REMOVE INVALID TEMP FILE
    # ------------------------------------------------------

    if temporary_path.exists():
        temporary_path.unlink()

    # ------------------------------------------------------
    # RETRY LOOP
    # ------------------------------------------------------

    last_message = ""
    last_http_status: int | str = ""

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.RequestException as exc:

            last_message = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        last_http_status = (
            response.status_code
        )

        # --------------------------------------------------
        # FILE NOT AVAILABLE
        # --------------------------------------------------

        if response.status_code == 404:
            return {
                "trade_date": (
                    trade_date.isoformat()
                ),

                "report_id": (
                    definition.report_id
                ),

                "report_name": (
                    definition.display_name
                ),

                "required": (
                    definition.required
                ),

                "filename": filename,

                "url": url,

                "status": (
                    "NOT AVAILABLE"
                ),

                "http_status": (
                    response.status_code
                ),

                "attempts": attempt,

                "bytes": 0,

                "sha256": "",

                "path": "",

                "message": (
                    "NSE archive returned HTTP 404."
                ),
            }

        # --------------------------------------------------
        # SERVER / RATE LIMIT RETRY
        # --------------------------------------------------

        if response.status_code in {
            403,
            429,
            500,
            502,
            503,
            504,
        }:

            last_message = (
                "Retryable HTTP response: "
                f"{response.status_code}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        if response.status_code != 200:

            last_message = (
                "Unexpected HTTP response: "
                f"{response.status_code}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        content = (
            response.content
        )

        # --------------------------------------------------
        # EMPTY RESPONSE
        # --------------------------------------------------

        if not content:
            last_message = (
                "NSE returned an empty response."
            )

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        # --------------------------------------------------
        # HTML ERROR PAGE
        # --------------------------------------------------

        if looks_like_html(
            content
        ):
            last_message = (
                "NSE returned HTML instead of ZIP data."
            )

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        # --------------------------------------------------
        # ZIP INTEGRITY
        # --------------------------------------------------

        (
            zip_valid,
            zip_message,
        ) = validate_zip_bytes(
            content,
            temporary_path,
        )

        if not zip_valid:

            last_message = (
                zip_message
            )

            if temporary_path.exists():
                temporary_path.unlink()

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

            continue

        # --------------------------------------------------
        # COMMIT RAW FILE
        # --------------------------------------------------

        if destination.exists():
            destination.unlink()

        temporary_path.replace(
            destination
        )

        return {
            "trade_date": (
                trade_date.isoformat()
            ),

            "report_id": (
                definition.report_id
            ),

            "report_name": (
                definition.display_name
            ),

            "required": (
                definition.required
            ),

            "filename": (
                filename
            ),

            "url": (
                url
            ),

            "status": (
                "DOWNLOADED"
            ),

            "http_status": (
                response.status_code
            ),

            "attempts": attempt,

            "bytes": (
                destination
                .stat()
                .st_size
            ),

            "sha256": (
                sha256_file(
                    destination
                )
            ),

            "path": str(
                destination
            ),

            "message": (
                "Official NSE UDiFF raw ZIP downloaded "
                "and integrity validated."
            ),
        }

    # ------------------------------------------------------
    # ALL RETRIES FAILED
    # ------------------------------------------------------

    if temporary_path.exists():
        temporary_path.unlink()

    return {
        "trade_date": (
            trade_date.isoformat()
        ),

        "report_id": (
            definition.report_id
        ),

        "report_name": (
            definition.display_name
        ),

        "required": (
            definition.required
        ),

        "filename": filename,

        "url": url,

        "status": (
            "FAILED"
        ),

        "http_status": (
            last_http_status
        ),

        "attempts": (
            MAX_RETRIES
        ),

        "bytes": 0,

        "sha256": "",

        "path": "",

        "message": (
            last_message
            or "Download failed after all retries."
        ),
    }


# ==========================================================
# DATE MANIFEST
# ==========================================================

def save_date_manifest(
    *,
    trade_date: date,
    results: list[
        dict[str, object]
    ],
) -> None:
    """
    Save source manifest for one trading date.
    """

    directory = raw_date_directory(
        trade_date
    )

    required_rows = [
        row
        for row in results
        if bool(
            row[
                "required"
            ]
        )
    ]

    available_required = [
        row
        for row in required_rows
        if row[
            "status"
        ]
        in {
            "DOWNLOADED",
            "SKIPPED EXISTING",
        }
    ]

    manifest = {
        "module_id": (
            MODULE_ID
        ),

        "module_version": (
            MODULE_VERSION
        ),

        "trade_date": (
            trade_date.isoformat()
        ),

        "created_at": (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        ),

        "raw_directory": str(
            directory
        ),

        "required_reports": len(
            required_rows
        ),

        "required_available": len(
            available_required
        ),

        "complete": (
            len(
                required_rows
            )
            == len(
                available_required
            )
        ),

        "reports": (
            results
        ),
    }

    manifest_file = (
        directory
        / "manifest.json"
    )

    manifest_file.write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================================
# AUDIT
# ==========================================================

def save_audit(
    rows: list[
        dict[str, object]
    ],
) -> Path:
    """
    Save complete download audit.
    """

    frame = pd.DataFrame(
        rows
    )

    frame.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return AUDIT_FILE


# ==========================================================
# ENGINE
# ==========================================================

def run_downloader(
    *,
    sessions: int,
    end_date: date,
    overwrite: bool,
) -> dict[str, object]:
    """
    Download NSE UDiFF bhavcopy history.
    """

    ensure_directories()

    target_dates = (
        resolve_target_dates(
            sessions=sessions,
            end_date=end_date,
        )
    )

    http_session = (
        create_nse_session()
    )

    audit_rows: list[
        dict[str, object]
    ] = []

    downloaded = 0
    skipped = 0
    unavailable = 0
    failed = 0

    complete_dates = 0

    for number, trade_date in enumerate(
        target_dates,
        start=1,
    ):

        print(
            f"[{number:03d}/{len(target_dates):03d}] "
            f"{trade_date.isoformat()}",
            end=" ",
            flush=True,
        )

        date_results: list[
            dict[str, object]
        ] = []

        for definition in REPORTS:

            result = (
                download_report(
                    session=http_session,
                    trade_date=trade_date,
                    definition=definition,
                    overwrite=overwrite,
                )
            )

            date_results.append(
                result
            )

            audit_rows.append(
                result
            )

            status = str(
                result[
                    "status"
                ]
            )

            if status == "DOWNLOADED":
                downloaded += 1

            elif status == "SKIPPED EXISTING":
                skipped += 1

            elif status == "NOT AVAILABLE":
                unavailable += 1

            else:
                failed += 1

            print(
                status
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        save_date_manifest(
            trade_date=trade_date,
            results=date_results,
        )

        required_rows = [
            row
            for row in date_results
            if bool(
                row[
                    "required"
                ]
            )
        ]

        date_complete = all(
            row[
                "status"
            ]
            in {
                "DOWNLOADED",
                "SKIPPED EXISTING",
            }
            for row in required_rows
        )

        if date_complete:
            complete_dates += 1

    audit_file = save_audit(
        audit_rows
    )

    summary = {
        "module_id": (
            MODULE_ID
        ),

        "module_version": (
            MODULE_VERSION
        ),

        "requested_sessions": (
            sessions
        ),

        "resolved_sessions": len(
            target_dates
        ),

        "first_session": (
            target_dates[0]
            .isoformat()
        ),

        "last_session": (
            target_dates[-1]
            .isoformat()
        ),

        "end_date": (
            end_date.isoformat()
        ),

        "reports_per_session": (
            len(
                REPORTS
            )
        ),

        "downloaded": (
            downloaded
        ),

        "skipped_existing": (
            skipped
        ),

        "unavailable": (
            unavailable
        ),

        "failed": (
            failed
        ),

        "complete_dates": (
            complete_dates
        ),

        "raw_root": str(
            RAW_ROOT
        ),

        "audit_file": str(
            audit_file
        ),

        "status": (
            "SUCCESS"
            if (
                failed == 0
                and unavailable == 0
                and complete_dates
                == len(
                    target_dates
                )
            )
            else "INCOMPLETE"
        ),
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary


# ==========================================================
# DISPLAY
# ==========================================================

def display_summary(
    summary: dict[str, object],
) -> None:
    """
    Display production download summary.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE HISTORICAL F&O DOWNLOADER"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Requested Sessions        : "
        f"{summary['requested_sessions']}"
    )

    print(
        f"Resolved Sessions         : "
        f"{summary['resolved_sessions']}"
    )

    print(
        f"First Session             : "
        f"{summary['first_session']}"
    )

    print(
        f"Last Session              : "
        f"{summary['last_session']}"
    )

    print("-" * 100)

    print(
        "NSE F&O UDIFF HISTORICAL ACQUISITION"
    )

    print("-" * 100)

    print(
        f"Downloaded                : "
        f"{summary['downloaded']}"
    )

    print(
        f"Skipped Existing          : "
        f"{summary['skipped_existing']}"
    )

    print(
        f"Unavailable               : "
        f"{summary['unavailable']}"
    )

    print(
        f"Failed                    : "
        f"{summary['failed']}"
    )

    print(
        f"Complete Trading Dates    : "
        f"{summary['complete_dates']}"
        f"/{summary['resolved_sessions']}"
    )

    print("-" * 100)

    print(
        f"Raw Root                  : "
        f"{summary['raw_root']}"
    )

    print(
        f"Audit CSV                 : "
        f"{summary['audit_file']}"
    )

    print(
        f"Summary JSON              : "
        f"{SUMMARY_FILE}"
    )

    print("-" * 100)

    print(
        "Universe                  : "
        "ENTIRE NSE F&O UDIFF BHAVCOPY"
    )

    print(
        "Raw Storage               : "
        "IMMUTABLE"
    )

    print(
        "ZIP Validation            : "
        "ENABLED"
    )

    print(
        "SHA256 Audit              : "
        "ENABLED"
    )

    print(
        "Resume Support            : "
        "ENABLED"
    )

    print(
        "Historical Fabrication    : "
        "PROHIBITED"
    )

    print("-" * 100)

    print(
        f"Status                    : "
        f"{summary['status']}"
    )

    print("=" * 100)


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    """
    Display downloader status.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE HISTORICAL F&O DOWNLOADER STATUS"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Trading Calendar          : "
        f"{TRADING_CALENDAR_FILE}"
    )

    print(
        f"Calendar Exists           : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )

    print(
        f"Raw Root                  : "
        f"{RAW_ROOT}"
    )

    print(
        f"Default Sessions          : "
        f"{DEFAULT_SESSIONS}"
    )

    print(
        f"Maximum Sessions          : "
        f"{MAX_SESSIONS}"
    )

    print(
        f"Required Reports / Date   : "
        f"{len(REPORTS)}"
    )

    print()

    for definition in REPORTS:

        print(
            f"Report                     : "
            f"{definition.display_name}"
        )

        print(
            f"Required                   : "
            f"{definition.required}"
        )

    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse CLI arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Download official NSE historical "
            "F&O UDiFF bhavcopy files."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
        help=(
            "Number of actual NSE trading sessions."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Final trading date YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Overwrite valid existing raw ZIP files."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display downloader status."
        ),
    )

    return parser.parse_args()


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:
    """
    Command-line entry point.
    """

    arguments = (
        parse_arguments()
    )

    if arguments.status:

        show_status()

        return

    sessions = max(
        1,
        min(
            int(
                arguments.sessions
            ),
            MAX_SESSIONS,
        ),
    )

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else date.today()
    )

    try:

        summary = run_downloader(
            sessions=sessions,
            end_date=end_date,
            overwrite=(
                arguments.overwrite
            ),
        )

    except Exception as exc:

        print()
        print("=" * 100)
        print(
            "AQSD NSE HISTORICAL F&O DOWNLOADER"
        )
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print("=" * 100)

        raise SystemExit(
            1
        ) from exc

    display_summary(
        summary
    )


if __name__ == "__main__":
    main()