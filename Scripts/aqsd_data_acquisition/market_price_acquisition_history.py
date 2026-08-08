"""
AQSD
Market Price Data Engine

Module : Historical Acquisition Coverage Ledger
Module ID : MPD-011
Version: 1.0.0

Description
-----------
Maintains a permanent SQLite ledger of historical market-price
acquisition attempts.

Purpose
-------
AQSD must never repeatedly request historical periods from FYERS
that have already been checked.

The ledger records both:

    DATA
        FYERS returned valid historical candles.

    NO_DATA
        FYERS was successfully queried but no candles existed
        for the requested period.

    FAILED
        The request failed and may therefore be retried later.

This allows AQSD to distinguish between:

    "We have never checked this period"

and

    "We checked this period and FYERS confirmed there was no data."

Database
--------
Databases/MPD/market_price_acquisition_history.db
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MPD-011"
MODULE_VERSION: Final[str] = "1.0.0"

STATUS_DATA: Final[str] = "DATA"
STATUS_NO_DATA: Final[str] = "NO_DATA"
STATUS_FAILED: Final[str] = "FAILED"

COMPLETED_STATUSES: Final[tuple[str, ...]] = (
    STATUS_DATA,
    STATUS_NO_DATA,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DATABASE_DIRECTORY: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "MPD"
)

DATABASE_FILE: Final[Path] = (
    DATABASE_DIRECTORY
    / "market_price_acquisition_history.db"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class AcquisitionRecord:
    """
    One historical market-price acquisition attempt.
    """

    security_id: str

    symbol: str

    fyers_symbol: str

    range_from: str

    range_to: str

    resolution: str

    result_status: str

    rows_received: int

    first_session: str | None

    last_session: str | None

    message: str

    acquired_at: str

    module_version: str


# ==========================================================
# DATABASE CONNECTION
# ==========================================================

def create_connection() -> sqlite3.Connection:
    """
    Create and return the acquisition-history database connection.
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

def initialize_acquisition_history() -> Path:
    """
    Create the acquisition-history table and indexes.
    """

    with create_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            market_price_acquisition_history
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                security_id TEXT NOT NULL,

                symbol TEXT NOT NULL,

                fyers_symbol TEXT NOT NULL,

                range_from TEXT NOT NULL,

                range_to TEXT NOT NULL,

                resolution TEXT NOT NULL,

                result_status TEXT NOT NULL,

                rows_received INTEGER NOT NULL DEFAULT 0,

                first_session TEXT,

                last_session TEXT,

                message TEXT NOT NULL DEFAULT '',

                acquired_at TEXT NOT NULL,

                module_version TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_mpd_acquisition_lookup
            ON market_price_acquisition_history
            (
                fyers_symbol,
                resolution,
                range_from,
                range_to,
                result_status
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_mpd_acquisition_symbol
            ON market_price_acquisition_history
            (
                security_id,
                symbol,
                fyers_symbol
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_mpd_acquisition_status
            ON market_price_acquisition_history
            (
                result_status
            )
            """
        )

        connection.commit()

    return DATABASE_FILE


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_status(
    status: str,
) -> str:
    """
    Normalize and validate an acquisition result status.
    """

    normalized = str(status).strip().upper()

    valid_statuses = {
        STATUS_DATA,
        STATUS_NO_DATA,
        STATUS_FAILED,
    }

    if normalized not in valid_statuses:

        raise ValueError(
            f"Invalid acquisition status: {status}. "
            f"Expected one of: "
            f"{sorted(valid_statuses)}"
        )

    return normalized


def normalize_resolution(
    resolution: str,
) -> str:
    """
    Normalize FYERS candle resolution.
    """

    value = str(resolution).strip()

    if not value:

        raise ValueError(
            "Resolution cannot be empty."
        )

    return value


# ==========================================================
# EXACT COVERAGE CHECK
# ==========================================================

def get_completed_acquisition(
    *,
    fyers_symbol: str,
    range_from: date,
    range_to: date,
    resolution: str,
) -> sqlite3.Row | None:
    """
    Return the latest completed acquisition for an exact range.

    DATA and NO_DATA are both considered completed.

    FAILED is deliberately excluded because failed requests
    must remain eligible for retry.
    """

    initialize_acquisition_history()

    normalized_symbol = (
        str(fyers_symbol)
        .strip()
        .upper()
    )

    normalized_resolution = normalize_resolution(
        resolution
    )

    with create_connection() as connection:

        row = connection.execute(
            """
            SELECT
                id,
                security_id,
                symbol,
                fyers_symbol,
                range_from,
                range_to,
                resolution,
                result_status,
                rows_received,
                first_session,
                last_session,
                message,
                acquired_at,
                module_version

            FROM market_price_acquisition_history

            WHERE fyers_symbol = ?
              AND resolution = ?
              AND range_from = ?
              AND range_to = ?
              AND result_status IN ('DATA', 'NO_DATA')

            ORDER BY id DESC

            LIMIT 1
            """,
            (
                normalized_symbol,
                normalized_resolution,
                range_from.isoformat(),
                range_to.isoformat(),
            ),
        ).fetchone()

    return row


def is_range_already_checked(
    *,
    fyers_symbol: str,
    range_from: date,
    range_to: date,
    resolution: str,
) -> tuple[bool, str | None, int]:
    """
    Determine whether an exact historical range has already
    been successfully checked.

    Returns
    -------
    tuple:
        already_checked
        previous_status
        previous_rows_received

    Examples
    --------
    (True, "DATA", 250)

    (True, "NO_DATA", 0)

    (False, None, 0)
    """

    row = get_completed_acquisition(
        fyers_symbol=fyers_symbol,
        range_from=range_from,
        range_to=range_to,
        resolution=resolution,
    )

    if row is None:

        return False, None, 0

    return (
        True,
        str(row["result_status"]),
        int(row["rows_received"]),
    )


# ==========================================================
# RECORD ACQUISITION
# ==========================================================

def record_acquisition(
    record: AcquisitionRecord,
) -> int:
    """
    Insert one acquisition attempt into the permanent ledger.
    """

    initialize_acquisition_history()

    status = normalize_status(
        record.result_status
    )

    resolution = normalize_resolution(
        record.resolution
    )

    with create_connection() as connection:

        cursor = connection.execute(
            """
            INSERT INTO
            market_price_acquisition_history
            (
                security_id,
                symbol,
                fyers_symbol,
                range_from,
                range_to,
                resolution,
                result_status,
                rows_received,
                first_session,
                last_session,
                message,
                acquired_at,
                module_version
            )

            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(record.security_id).strip(),
                str(record.symbol).strip().upper(),
                str(record.fyers_symbol).strip().upper(),
                record.range_from,
                record.range_to,
                resolution,
                status,
                int(record.rows_received),
                record.first_session,
                record.last_session,
                str(record.message),
                record.acquired_at,
                str(record.module_version),
            ),
        )

        connection.commit()

        return int(
            cursor.lastrowid or 0
        )


def record_acquisition_result(
    *,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
    range_from: date,
    range_to: date,
    resolution: str,
    result_status: str,
    rows_received: int = 0,
    first_session: date | str | None = None,
    last_session: date | str | None = None,
    message: str = "",
    module_version: str,
) -> int:
    """
    Convenience function used by the historical downloader.
    """

    def convert_session(
        value: date | str | None,
    ) -> str | None:

        if value is None:
            return None

        if isinstance(value, date):
            return value.isoformat()

        return str(value)

    record = AcquisitionRecord(

        security_id=str(
            security_id
        ).strip(),

        symbol=str(
            symbol
        ).strip().upper(),

        fyers_symbol=str(
            fyers_symbol
        ).strip().upper(),

        range_from=range_from.isoformat(),

        range_to=range_to.isoformat(),

        resolution=normalize_resolution(
            resolution
        ),

        result_status=normalize_status(
            result_status
        ),

        rows_received=max(
            0,
            int(rows_received),
        ),

        first_session=convert_session(
            first_session
        ),

        last_session=convert_session(
            last_session
        ),

        message=str(
            message
        ),

        acquired_at=(
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        ),

        module_version=str(
            module_version
        ),
    )

    return record_acquisition(
        record
    )


# ==========================================================
# REPORTING
# ==========================================================

def count_acquisition_records() -> int:
    """
    Return total number of acquisition-history records.
    """

    initialize_acquisition_history()

    with create_connection() as connection:

        row = connection.execute(
            """
            SELECT COUNT(*) AS record_count
            FROM market_price_acquisition_history
            """
        ).fetchone()

    return int(
        row["record_count"]
    )


def count_completed_ranges() -> int:
    """
    Return number of completed DATA / NO_DATA ranges.
    """

    initialize_acquisition_history()

    with create_connection() as connection:

        row = connection.execute(
            """
            SELECT COUNT(*) AS record_count

            FROM market_price_acquisition_history

            WHERE result_status
            IN ('DATA', 'NO_DATA')
            """
        ).fetchone()

    return int(
        row["record_count"]
    )


def count_failed_ranges() -> int:
    """
    Return number of failed acquisition attempts.
    """

    initialize_acquisition_history()

    with create_connection() as connection:

        row = connection.execute(
            """
            SELECT COUNT(*) AS record_count

            FROM market_price_acquisition_history

            WHERE result_status = 'FAILED'
            """
        ).fetchone()

    return int(
        row["record_count"]
    )


def get_symbol_acquisition_history(
    *,
    fyers_symbol: str,
) -> list[sqlite3.Row]:
    """
    Return complete acquisition history for one FYERS symbol.
    """

    initialize_acquisition_history()

    normalized_symbol = (
        str(fyers_symbol)
        .strip()
        .upper()
    )

    with create_connection() as connection:

        rows = connection.execute(
            """
            SELECT
                id,
                security_id,
                symbol,
                fyers_symbol,
                range_from,
                range_to,
                resolution,
                result_status,
                rows_received,
                first_session,
                last_session,
                message,
                acquired_at,
                module_version

            FROM market_price_acquisition_history

            WHERE fyers_symbol = ?

            ORDER BY
                range_from,
                range_to,
                id
            """,
            (
                normalized_symbol,
            ),
        ).fetchall()

    return list(rows)


# ==========================================================
# DATABASE INFORMATION
# ==========================================================

def get_database_file() -> Path:
    """
    Return the permanent acquisition-history database path.
    """

    initialize_acquisition_history()

    return DATABASE_FILE


# ==========================================================
# STANDALONE DIAGNOSTIC
# ==========================================================

def main() -> None:
    """
    Initialize the ledger and print basic diagnostics.
    """

    database_file = (
        initialize_acquisition_history()
    )

    print("=" * 70)
    print("AQSD HISTORICAL ACQUISITION COVERAGE LEDGER")
    print("=" * 70)

    print(
        f"Module ID       : {MODULE_ID}"
    )

    print(
        f"Module version  : {MODULE_VERSION}"
    )

    print(
        f"Database        : {database_file}"
    )

    print(
        f"Total records   : "
        f"{count_acquisition_records()}"
    )

    print(
        f"Completed       : "
        f"{count_completed_ranges()}"
    )

    print(
        f"Failed          : "
        f"{count_failed_ranges()}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()