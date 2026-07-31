"""
AQSD
Data Acquisition Engine

Module : Download History
Version: 1.0.0

Description
-----------
Maintains a permanent SQLite history of every AQSD download.

Responsibilities:
- Create the download-history database.
- Record successful and failed downloads.
- Detect previously downloaded files.
- Compare SHA256 hashes.
- Prevent unnecessary duplicate downloads.

Database:
Databases/DAQ/download_history.db
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DATABASE_DIRECTORY: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "DAQ"
)

DATABASE_FILE: Final[Path] = (
    DATABASE_DIRECTORY
    / "download_history.db"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class DownloadHistoryRecord:
    """
    One download-history database record.
    """

    source: str
    report_id: str
    report_name: str
    trade_date: str
    url: str
    output_file: str
    status: str
    file_size_bytes: int
    sha256: str | None
    message: str
    downloaded_at: str
    module_version: str


# ==========================================================
# DATABASE CONNECTION
# ==========================================================

def create_connection() -> sqlite3.Connection:
    """
    Create and return the SQLite database connection.
    """

    DATABASE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================

def initialize_download_history() -> Path:
    """
    Create the download-history table and indexes.
    """

    with create_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                source TEXT NOT NULL,

                report_id TEXT NOT NULL,

                report_name TEXT NOT NULL,

                trade_date TEXT NOT NULL,

                url TEXT NOT NULL,

                output_file TEXT NOT NULL,

                status TEXT NOT NULL,

                file_size_bytes INTEGER NOT NULL DEFAULT 0,

                sha256 TEXT,

                message TEXT NOT NULL,

                downloaded_at TEXT NOT NULL,

                module_version TEXT NOT NULL,

                UNIQUE (
                    source,
                    report_id,
                    trade_date,
                    sha256
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_download_history_lookup
            ON download_history (
                source,
                report_id,
                trade_date,
                status
            )
            """
        )

        connection.commit()

    return DATABASE_FILE


# ==========================================================
# DUPLICATE CHECKS
# ==========================================================

def get_successful_download(
    *,
    source: str,
    report_id: str,
    trade_date: date,
) -> sqlite3.Row | None:
    """
    Return the latest successful download for a report and date.
    """

    initialize_download_history()

    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                source,
                report_id,
                report_name,
                trade_date,
                url,
                output_file,
                status,
                file_size_bytes,
                sha256,
                message,
                downloaded_at,
                module_version

            FROM download_history

            WHERE source = ?
              AND report_id = ?
              AND trade_date = ?
              AND status = 'SUCCESS'

            ORDER BY id DESC

            LIMIT 1
            """,
            (
                source.strip().upper(),
                report_id.strip().upper(),
                trade_date.isoformat(),
            ),
        ).fetchone()

    return row


def is_download_complete(
    *,
    source: str,
    report_id: str,
    trade_date: date,
) -> tuple[bool, Path | None, str | None]:
    """
    Check whether a valid successful download already exists.

    Returns:
        completed
        existing file path
        existing SHA256
    """

    row = get_successful_download(
        source=source,
        report_id=report_id,
        trade_date=trade_date,
    )

    if row is None:
        return False, None, None

    existing_file = Path(
        row["output_file"]
    )

    if not existing_file.exists():
        return False, existing_file, row["sha256"]

    if not existing_file.is_file():
        return False, existing_file, row["sha256"]

    expected_size = int(
        row["file_size_bytes"]
    )

    actual_size = existing_file.stat().st_size

    if actual_size != expected_size:
        return False, existing_file, row["sha256"]

    return True, existing_file, row["sha256"]


# ==========================================================
# HISTORY INSERT
# ==========================================================

def record_download(
    record: DownloadHistoryRecord,
) -> int:
    """
    Insert one download-history record.

    Returns the database row ID.
    """

    initialize_download_history()

    with create_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO download_history (
                source,
                report_id,
                report_name,
                trade_date,
                url,
                output_file,
                status,
                file_size_bytes,
                sha256,
                message,
                downloaded_at,
                module_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.source.strip().upper(),
                record.report_id.strip().upper(),
                record.report_name.strip(),
                record.trade_date,
                record.url,
                record.output_file,
                record.status.strip().upper(),
                record.file_size_bytes,
                record.sha256,
                record.message,
                record.downloaded_at,
                record.module_version,
            ),
        )

        connection.commit()

        return int(cursor.lastrowid or 0)


def record_download_result(
    *,
    source: str,
    report_id: str,
    report_name: str,
    trade_date: date,
    url: str,
    output_file: Path,
    status: str,
    file_size_bytes: int,
    sha256: str | None,
    message: str,
    module_version: str,
) -> int:
    """
    Convenience function for recording a manager result.
    """

    record = DownloadHistoryRecord(
        source=source,
        report_id=report_id,
        report_name=report_name,
        trade_date=trade_date.isoformat(),
        url=url,
        output_file=str(output_file),
        status=status,
        file_size_bytes=file_size_bytes,
        sha256=sha256,
        message=message,
        downloaded_at=(
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        module_version=module_version,
    )

    return record_download(record)


# ==========================================================
# HISTORY REPORTING
# ==========================================================

def count_downloads() -> int:
    """
    Return the total number of download-history records.
    """

    initialize_download_history()

    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS record_count
            FROM download_history
            """
        ).fetchone()

    return int(row["record_count"])


def get_database_file() -> Path:
    """
    Return the download-history database location.
    """

    initialize_download_history()

    return DATABASE_FILE