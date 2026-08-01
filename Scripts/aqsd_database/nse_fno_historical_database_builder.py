"""
AQSD
NSE F&O Historical Database Builder

Module : FDB-001
Version: 1.1.0
Author : AQSD

Purpose
-------
Build a persistent historical NSE F&O database from the daily
processed UDiFF bhavcopy files produced by NFP-001.

Input
-----
D:/AQSD_DATA/Processed/NSE/Derivatives/YYYY-MM-DD/

    futures.csv
    options.csv
    fno_contracts.csv

Output
------
D:/AQSD_DATA/Databases/NSE_FNO_Historical.db

Primary Tables
--------------
1. futures_history
2. options_history
3. contract_master
4. daily_summary
5. underlying_daily_summary
6. build_audit

Design Principles
-----------------
- Entire NSE F&O universe
- Row-based architecture
- Incremental / restart-safe
- Existing date can be refreshed without duplication
- Millions of rows supported
- Database is indexed for research queries
- Raw NSE data is never modified
- Processed NSE data is never modified
- No historical data is fabricated
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time

from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from Scripts.aqsd_core.paths import (
    DATABASE_DIR,
    NSE_DERIVATIVES_PROCESSED_DIR,
    NSE_FNO_HISTORICAL_DB,
    OUTPUT_DIR,
    ensure_aqsd_directories,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "FDB-001"
MODULE_VERSION: Final[str] = "1.1.0"

PROCESSED_ROOT: Final[Path] = (
    NSE_DERIVATIVES_PROCESSED_DIR
)

DATABASE_FILE: Final[Path] = (
    NSE_FNO_HISTORICAL_DB
)


AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Historical_Database_Build_Audit.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Historical_Database_Build_Summary.json"
)

DEFAULT_SESSIONS: Final[int] = 60

CSV_CHUNK_SIZE: Final[int] = 50_000

SQL_INSERT_CHUNK_SIZE: Final[int] = 500


# ==========================================================
# DATABASE COLUMNS
# ==========================================================

HISTORY_COLUMNS: Final[
    tuple[str, ...]
] = (
    "trade_date",
    "segment",
    "source",
    "instrument",
    "underlying",
    "symbol",
    "expiry",
    "strike",
    "option_type",
    "open",
    "high",
    "low",
    "close",
    "last_price",
    "settle_price",
    "volume",
    "turnover",
    "open_interest",
    "change_in_oi",
    "source_row_number",
    "source_provider",
    "source_format",
    "contract_type",
    "aqsd_underlying",
)


TEXT_COLUMNS: Final[
    tuple[str, ...]
] = (
    "trade_date",
    "segment",
    "source",
    "instrument",
    "underlying",
    "symbol",
    "expiry",
    "option_type",
    "source_provider",
    "source_format",
    "contract_type",
    "aqsd_underlying",
)


REAL_COLUMNS: Final[
    tuple[str, ...]
] = (
    "strike",
    "open",
    "high",
    "low",
    "close",
    "last_price",
    "settle_price",
    "turnover",
)


INTEGER_COLUMNS: Final[
    tuple[str, ...]
] = (
    "volume",
    "open_interest",
    "change_in_oi",
    "source_row_number",
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
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def ensure_directories() -> None:
    """
    Create AQSD central data/output directories.

    Storage architecture:
        C: project / code / reports
        D: primary market data
        E: backup
    """

    ensure_aqsd_directories()

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# PROCESSED DATE DISCOVERY
# ==========================================================

def available_processed_dates() -> list[date]:
    """
    Discover all processed NSE F&O trading-date folders.
    """

    if not PROCESSED_ROOT.exists():
        return []

    dates: list[date] = []

    for path in PROCESSED_ROOT.iterdir():

        if not path.is_dir():
            continue

        try:
            parsed = datetime.strptime(
                path.name,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            continue

        futures_file = (
            path
            / "futures.csv"
        )

        options_file = (
            path
            / "options.csv"
        )

        if (
            futures_file.exists()
            and options_file.exists()
        ):
            dates.append(
                parsed
            )

    return sorted(
        dates
    )


def resolve_target_dates(
    *,
    sessions: int,
    end_date: date | None,
) -> list[date]:
    """
    Resolve processed sessions to ingest.
    """

    dates = available_processed_dates()

    if end_date is not None:
        dates = [
            value
            for value in dates
            if value <= end_date
        ]

    if not dates:
        raise RuntimeError(
            "No processed NSE F&O sessions were found."
        )

    sessions = max(
        1,
        int(
            sessions
        ),
    )

    return dates[
        -sessions:
    ]


# ==========================================================
# SQLITE CONNECTION
# ==========================================================

def create_connection() -> sqlite3.Connection:
    """
    Create optimized SQLite connection.
    """

    ensure_directories()

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.execute(
        "PRAGMA journal_mode=WAL;"
    )

    connection.execute(
        "PRAGMA synchronous=NORMAL;"
    )

    connection.execute(
        "PRAGMA temp_store=MEMORY;"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON;"
    )

    connection.execute(
        "PRAGMA cache_size=-100000;"
    )

    return connection


# ==========================================================
# TABLE CREATION
# ==========================================================

def create_history_table(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    """
    Create futures/options history table.
    """

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name}
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            trade_date TEXT NOT NULL,
            segment TEXT,
            source TEXT,
            instrument TEXT,
            underlying TEXT,
            symbol TEXT,
            expiry TEXT,

            strike REAL,
            option_type TEXT,

            open REAL,
            high REAL,
            low REAL,
            close REAL,
            last_price REAL,
            settle_price REAL,

            volume INTEGER,
            turnover REAL,
            open_interest INTEGER,
            change_in_oi INTEGER,

            source_row_number INTEGER,

            source_provider TEXT,
            source_format TEXT,

            contract_type TEXT,

            aqsd_underlying TEXT,

            inserted_at TEXT NOT NULL
        );
        """
    )


def create_tables(
    connection: sqlite3.Connection,
) -> None:
    """
    Create all FDB-001 tables.
    """

    create_history_table(
        connection,
        "futures_history",
    )

    create_history_table(
        connection,
        "options_history",
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_master
        (
            contract_key TEXT PRIMARY KEY,

            contract_type TEXT,

            instrument TEXT,
            aqsd_underlying TEXT,
            underlying TEXT,
            symbol TEXT,

            expiry TEXT,
            strike REAL,
            option_type TEXT,

            first_seen TEXT,
            last_seen TEXT,

            observations INTEGER,

            updated_at TEXT
        );
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summary
        (
            trade_date TEXT PRIMARY KEY,

            futures_rows INTEGER,
            options_rows INTEGER,
            total_rows INTEGER,

            futures_underlyings INTEGER,
            options_underlyings INTEGER,
            total_underlyings INTEGER,

            futures_volume INTEGER,
            options_volume INTEGER,

            futures_open_interest INTEGER,
            options_open_interest INTEGER,

            futures_turnover REAL,
            options_turnover REAL,

            updated_at TEXT
        );
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS underlying_daily_summary
        (
            trade_date TEXT NOT NULL,
            aqsd_underlying TEXT NOT NULL,

            futures_rows INTEGER,
            options_rows INTEGER,

            futures_volume INTEGER,
            options_volume INTEGER,

            futures_open_interest INTEGER,
            options_open_interest INTEGER,

            futures_change_in_oi INTEGER,
            options_change_in_oi INTEGER,

            futures_turnover REAL,
            options_turnover REAL,

            PRIMARY KEY
            (
                trade_date,
                aqsd_underlying
            )
        );
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS build_audit
        (
            trade_date TEXT PRIMARY KEY,

            futures_rows INTEGER,
            options_rows INTEGER,

            futures_file TEXT,
            options_file TEXT,

            status TEXT,
            message TEXT,

            processed_at TEXT
        );
        """
    )

    connection.commit()


# ==========================================================
# INDEXES
# ==========================================================

def create_indexes(
    connection: sqlite3.Connection,
) -> None:
    """
    Create research/query indexes.

    Run after bulk loading for better ingestion speed.
    """

    index_statements = (
        """
        CREATE INDEX IF NOT EXISTS
        idx_futures_trade_date
        ON futures_history(trade_date);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_futures_underlying
        ON futures_history(aqsd_underlying);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_futures_date_underlying
        ON futures_history(
            trade_date,
            aqsd_underlying
        );
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_futures_expiry
        ON futures_history(expiry);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_trade_date
        ON options_history(trade_date);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_underlying
        ON options_history(aqsd_underlying);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_date_underlying
        ON options_history(
            trade_date,
            aqsd_underlying
        );
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_expiry
        ON options_history(expiry);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_strike
        ON options_history(strike);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_type
        ON options_history(option_type);
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_options_lookup
        ON options_history(
            trade_date,
            aqsd_underlying,
            expiry,
            strike,
            option_type
        );
        """,
    )

    for statement in index_statements:
        connection.execute(
            statement
        )

    connection.commit()


# ==========================================================
# DATA NORMALIZATION
# ==========================================================

def normalize_chunk(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize parser output before SQLite ingestion.
    """

    working = frame.copy()

    for column in HISTORY_COLUMNS:

        if column not in working.columns:
            working[
                column
            ] = pd.NA

    working = working[
        list(
            HISTORY_COLUMNS
        )
    ].copy()

    # ------------------------------------------------------
    # TEXT
    # ------------------------------------------------------

    for column in TEXT_COLUMNS:

        working[
            column
        ] = (
            working[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        working.loc[
            working[
                column
            ].isin(
                [
                    "nan",
                    "NaN",
                    "NaT",
                    "<NA>",
                ]
            ),
            column,
        ] = ""

    # ------------------------------------------------------
    # REAL
    # ------------------------------------------------------

    for column in REAL_COLUMNS:

        working[
            column
        ] = pd.to_numeric(
            working[
                column
            ],
            errors="coerce",
        )

    # ------------------------------------------------------
    # INTEGER
    # ------------------------------------------------------

    for column in INTEGER_COLUMNS:

        working[
            column
        ] = pd.to_numeric(
            working[
                column
            ],
            errors="coerce",
        ).astype(
            "Int64"
        )

    return working


# ==========================================================
# DATE DELETE
# ==========================================================

def delete_existing_date(
    connection: sqlite3.Connection,
    *,
    trade_date: str,
) -> None:
    """
    Remove one date before rebuilding it.

    This makes FDB-001 restart-safe and duplication-safe.
    """

    connection.execute(
        """
        DELETE FROM futures_history
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )

    connection.execute(
        """
        DELETE FROM options_history
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )

    connection.execute(
        """
        DELETE FROM daily_summary
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )

    connection.execute(
        """
        DELETE FROM underlying_daily_summary
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )

    connection.execute(
        """
        DELETE FROM build_audit
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )


# ==========================================================
# CHUNK INSERT
# ==========================================================

def insert_csv_to_history(
    connection: sqlite3.Connection,
    *,
    csv_file: Path,
    table_name: str,
    trade_date: str,
) -> int:
    """
    Insert a large CSV into SQLite in chunks.
    """

    total_rows = 0

    inserted_at = (
        datetime.now()
        .isoformat(
            timespec="seconds"
        )
    )

    for chunk in pd.read_csv(
        csv_file,
        chunksize=CSV_CHUNK_SIZE,
        low_memory=False,
    ):

        working = normalize_chunk(
            chunk
        )

        # Force exact source-date consistency.
        working[
            "trade_date"
        ] = trade_date

        working[
            "inserted_at"
        ] = inserted_at

        working.to_sql(
            table_name,
            connection,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=SQL_INSERT_CHUNK_SIZE,
        )

        total_rows += len(
            working
        )

    return total_rows


# ==========================================================
# DAILY SUMMARY
# ==========================================================

def rebuild_daily_summary(
    connection: sqlite3.Connection,
    *,
    trade_date: str,
) -> None:
    """
    Rebuild market-wide daily derivatives summary.
    """

    timestamp = (
        datetime.now()
        .isoformat(
            timespec="seconds"
        )
    )

    connection.execute(
        """
        INSERT OR REPLACE INTO daily_summary
        (
            trade_date,

            futures_rows,
            options_rows,
            total_rows,

            futures_underlyings,
            options_underlyings,
            total_underlyings,

            futures_volume,
            options_volume,

            futures_open_interest,
            options_open_interest,

            futures_turnover,
            options_turnover,

            updated_at
        )

        SELECT
            ?,

            (
                SELECT COUNT(*)
                FROM futures_history
                WHERE trade_date = ?
            ),

            (
                SELECT COUNT(*)
                FROM options_history
                WHERE trade_date = ?
            ),

            (
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM futures_history
                        WHERE trade_date = ?
                    )
                    +
                    (
                        SELECT COUNT(*)
                        FROM options_history
                        WHERE trade_date = ?
                    )
            ),

            (
                SELECT COUNT(
                    DISTINCT aqsd_underlying
                )
                FROM futures_history
                WHERE trade_date = ?
            ),

            (
                SELECT COUNT(
                    DISTINCT aqsd_underlying
                )
                FROM options_history
                WHERE trade_date = ?
            ),

            (
                SELECT COUNT(
                    DISTINCT aqsd_underlying
                )
                FROM
                (
                    SELECT aqsd_underlying
                    FROM futures_history
                    WHERE trade_date = ?

                    UNION

                    SELECT aqsd_underlying
                    FROM options_history
                    WHERE trade_date = ?
                )
            ),

            (
                SELECT COALESCE(
                    SUM(volume),
                    0
                )
                FROM futures_history
                WHERE trade_date = ?
            ),

            (
                SELECT COALESCE(
                    SUM(volume),
                    0
                )
                FROM options_history
                WHERE trade_date = ?
            ),

            (
                SELECT COALESCE(
                    SUM(open_interest),
                    0
                )
                FROM futures_history
                WHERE trade_date = ?
            ),

            (
                SELECT COALESCE(
                    SUM(open_interest),
                    0
                )
                FROM options_history
                WHERE trade_date = ?
            ),

            (
                SELECT COALESCE(
                    SUM(turnover),
                    0
                )
                FROM futures_history
                WHERE trade_date = ?
            ),

            (
                SELECT COALESCE(
                    SUM(turnover),
                    0
                )
                FROM options_history
                WHERE trade_date = ?
            ),

            ?
        ;
        """,
        (
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            timestamp,
        ),
    )


# ==========================================================
# UNDERLYING DAILY SUMMARY
# ==========================================================

def rebuild_underlying_daily_summary(
    connection: sqlite3.Connection,
    *,
    trade_date: str,
) -> None:
    """
    Build one row per date + underlying.
    """

    connection.execute(
        """
        DELETE FROM underlying_daily_summary
        WHERE trade_date = ?;
        """,
        (
            trade_date,
        ),
    )

    connection.execute(
        """
        INSERT INTO underlying_daily_summary
        (
            trade_date,
            aqsd_underlying,

            futures_rows,
            options_rows,

            futures_volume,
            options_volume,

            futures_open_interest,
            options_open_interest,

            futures_change_in_oi,
            options_change_in_oi,

            futures_turnover,
            options_turnover
        )

        WITH underlyings AS
        (
            SELECT aqsd_underlying
            FROM futures_history
            WHERE trade_date = ?

            UNION

            SELECT aqsd_underlying
            FROM options_history
            WHERE trade_date = ?
        )

        SELECT
            ?,

            u.aqsd_underlying,

            COALESCE(
                (
                    SELECT COUNT(*)
                    FROM futures_history f
                    WHERE
                        f.trade_date = ?
                        AND
                        f.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT COUNT(*)
                    FROM options_history o
                    WHERE
                        o.trade_date = ?
                        AND
                        o.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(volume)
                    FROM futures_history f
                    WHERE
                        f.trade_date = ?
                        AND
                        f.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(volume)
                    FROM options_history o
                    WHERE
                        o.trade_date = ?
                        AND
                        o.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(open_interest)
                    FROM futures_history f
                    WHERE
                        f.trade_date = ?
                        AND
                        f.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(open_interest)
                    FROM options_history o
                    WHERE
                        o.trade_date = ?
                        AND
                        o.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(change_in_oi)
                    FROM futures_history f
                    WHERE
                        f.trade_date = ?
                        AND
                        f.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(change_in_oi)
                    FROM options_history o
                    WHERE
                        o.trade_date = ?
                        AND
                        o.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(turnover)
                    FROM futures_history f
                    WHERE
                        f.trade_date = ?
                        AND
                        f.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            ),

            COALESCE(
                (
                    SELECT SUM(turnover)
                    FROM options_history o
                    WHERE
                        o.trade_date = ?
                        AND
                        o.aqsd_underlying
                        = u.aqsd_underlying
                ),
                0
            )

        FROM underlyings u

        WHERE
            u.aqsd_underlying IS NOT NULL
            AND
            TRIM(
                u.aqsd_underlying
            ) <> ''
        ;
        """,
        (
            trade_date,
            trade_date,

            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,

            trade_date,
            trade_date,
        ),
    )


# ==========================================================
# CONTRACT MASTER
# ==========================================================

def rebuild_contract_master(
    connection: sqlite3.Connection,
) -> None:
    """
    Rebuild contract master from historical observations.

    This is intentionally done after all selected sessions
    are ingested.
    """

    connection.execute(
        """
        DELETE FROM contract_master;
        """
    )

    connection.execute(
        """
        INSERT INTO contract_master
        (
            contract_key,

            contract_type,
            instrument,

            aqsd_underlying,
            underlying,
            symbol,

            expiry,
            strike,
            option_type,

            first_seen,
            last_seen,

            observations,

            updated_at
        )

        SELECT
            contract_key,

            contract_type,
            instrument,

            aqsd_underlying,
            underlying,
            symbol,

            expiry,
            strike,
            option_type,

            MIN(
                trade_date
            ),

            MAX(
                trade_date
            ),

            COUNT(*),

            ?

        FROM
        (
            SELECT
                (
                    COALESCE(
                        contract_type,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        instrument,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        aqsd_underlying,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        symbol,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        expiry,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        CAST(
                            strike AS TEXT
                        ),
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        option_type,
                        ''
                    )
                ) AS contract_key,

                contract_type,
                instrument,

                aqsd_underlying,
                underlying,
                symbol,

                expiry,
                strike,
                option_type,

                trade_date

            FROM futures_history

            UNION ALL

            SELECT
                (
                    COALESCE(
                        contract_type,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        instrument,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        aqsd_underlying,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        symbol,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        expiry,
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        CAST(
                            strike AS TEXT
                        ),
                        ''
                    )
                    || '|'
                    ||
                    COALESCE(
                        option_type,
                        ''
                    )
                ) AS contract_key,

                contract_type,
                instrument,

                aqsd_underlying,
                underlying,
                symbol,

                expiry,
                strike,
                option_type,

                trade_date

            FROM options_history
        )

        GROUP BY
            contract_key,
            contract_type,
            instrument,
            aqsd_underlying,
            underlying,
            symbol,
            expiry,
            strike,
            option_type
        ;
        """,
        (
            datetime.now()
            .isoformat(
                timespec="seconds"
            ),
        ),
    )


# ==========================================================
# AUDIT
# ==========================================================

def write_build_audit(
    connection: sqlite3.Connection,
    *,
    trade_date: str,
    futures_rows: int,
    options_rows: int,
    futures_file: Path,
    options_file: Path,
    status: str,
    message: str,
) -> None:
    """
    Record one session build result.
    """

    connection.execute(
        """
        INSERT OR REPLACE INTO build_audit
        (
            trade_date,

            futures_rows,
            options_rows,

            futures_file,
            options_file,

            status,
            message,

            processed_at
        )

        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?
        );
        """,
        (
            trade_date,

            futures_rows,
            options_rows,

            str(
                futures_file
            ),

            str(
                options_file
            ),

            status,
            message,

            datetime.now()
            .isoformat(
                timespec="seconds"
            ),
        ),
    )


# ==========================================================
# BUILD ONE SESSION
# ==========================================================

def build_session(
    connection: sqlite3.Connection,
    *,
    trade_date: date,
) -> dict[str, object]:
    """
    Build one NSE F&O trading date.
    """

    date_text = (
        trade_date.isoformat()
    )

    directory = (
        PROCESSED_ROOT
        / date_text
    )

    futures_file = (
        directory
        / "futures.csv"
    )

    options_file = (
        directory
        / "options.csv"
    )

    if not futures_file.exists():
        raise FileNotFoundError(
            f"Missing futures.csv for {date_text}"
        )

    if not options_file.exists():
        raise FileNotFoundError(
            f"Missing options.csv for {date_text}"
        )

    start_time = time.perf_counter()

    # ======================================================
    # BEGIN TRANSACTION
    # ======================================================

    connection.execute(
        "BEGIN;"
    )

    try:

        delete_existing_date(
            connection,
            trade_date=date_text,
        )

        futures_rows = (
            insert_csv_to_history(
                connection,
                csv_file=futures_file,
                table_name=(
                    "futures_history"
                ),
                trade_date=date_text,
            )
        )

        options_rows = (
            insert_csv_to_history(
                connection,
                csv_file=options_file,
                table_name=(
                    "options_history"
                ),
                trade_date=date_text,
            )
        )

        rebuild_daily_summary(
            connection,
            trade_date=date_text,
        )

        rebuild_underlying_daily_summary(
            connection,
            trade_date=date_text,
        )

        write_build_audit(
            connection,
            trade_date=date_text,
            futures_rows=futures_rows,
            options_rows=options_rows,
            futures_file=futures_file,
            options_file=options_file,
            status="SUCCESS",
            message=(
                "NSE F&O historical session "
                "loaded successfully."
            ),
        )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    elapsed = (
        time.perf_counter()
        - start_time
    )

    return {
        "trade_date": date_text,
        "futures_rows": futures_rows,
        "options_rows": options_rows,
        "total_rows": (
            futures_rows
            + options_rows
        ),
        "seconds": round(
            elapsed,
            2,
        ),
        "status": "SUCCESS",
    }


# ==========================================================
# DATABASE STATISTICS
# ==========================================================

def database_statistics(
    connection: sqlite3.Connection,
) -> dict[str, object]:
    """
    Read consolidated database statistics.
    """

    futures_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM futures_history;
        """
    ).fetchone()[0]

    options_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM options_history;
        """
    ).fetchone()[0]

    sessions = connection.execute(
        """
        SELECT COUNT(
            DISTINCT trade_date
        )
        FROM daily_summary;
        """
    ).fetchone()[0]

    underlyings = connection.execute(
        """
        SELECT COUNT(
            DISTINCT aqsd_underlying
        )
        FROM
        (
            SELECT aqsd_underlying
            FROM futures_history

            UNION

            SELECT aqsd_underlying
            FROM options_history
        );
        """
    ).fetchone()[0]

    contracts = connection.execute(
        """
        SELECT COUNT(*)
        FROM contract_master;
        """
    ).fetchone()[0]

    return {
        "sessions": int(
            sessions
        ),
        "futures_rows": int(
            futures_rows
        ),
        "options_rows": int(
            options_rows
        ),
        "total_rows": int(
            futures_rows
            + options_rows
        ),
        "unique_underlyings": int(
            underlyings
        ),
        "contract_master_rows": int(
            contracts
        ),
    }


# ==========================================================
# CSV AUDIT EXPORT
# ==========================================================

def export_audit(
    connection: sqlite3.Connection,
) -> None:
    """
    Export SQLite build audit to CSV.
    """

    frame = pd.read_sql_query(
        """
        SELECT *
        FROM build_audit
        ORDER BY trade_date;
        """,
        connection,
    )

    frame.to_csv(
        AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )


# ==========================================================
# ENGINE
# ==========================================================

def run_builder(
    *,
    sessions: int,
    end_date: date | None,
) -> dict[str, object]:
    """
    Build AQSD historical NSE F&O database.
    """

    ensure_directories()

    target_dates = resolve_target_dates(
        sessions=sessions,
        end_date=end_date,
    )

    connection = (
        create_connection()
    )

    try:

        create_tables(
            connection
        )

        results: list[
            dict[str, object]
        ] = []

        failed = 0

        print()

        for number, trade_date in enumerate(
            target_dates,
            start=1,
        ):

            print(
                f"[{number:03d}/"
                f"{len(target_dates):03d}] "
                f"{trade_date.isoformat()}",
                end=" ",
                flush=True,
            )

            try:

                result = build_session(
                    connection,
                    trade_date=trade_date,
                )

                results.append(
                    result
                )

                print(
                    f"SUCCESS | "
                    f"{result['total_rows']:,} rows | "
                    f"{result['seconds']} sec"
                )

            except Exception as exc:

                failed += 1

                result = {
                    "trade_date": (
                        trade_date.isoformat()
                    ),
                    "futures_rows": 0,
                    "options_rows": 0,
                    "total_rows": 0,
                    "seconds": 0,
                    "status": "FAILED",
                    "message": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }

                results.append(
                    result
                )

                print(
                    f"FAILED | "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

        # ==================================================
        # MASTER TABLES
        # ==================================================

        print()
        print(
            "Rebuilding Contract Master..."
        )

        rebuild_contract_master(
            connection
        )

        connection.commit()

        print(
            "Creating / validating indexes..."
        )

        create_indexes(
            connection
        )

        export_audit(
            connection
        )

        statistics = (
            database_statistics(
                connection
            )
        )

    finally:

        connection.close()

    successful = sum(
        1
        for row in results
        if row[
            "status"
        ]
        == "SUCCESS"
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

        "successful_sessions": (
            successful
        ),

        "failed_sessions": (
            failed
        ),

        "first_session": (
            target_dates[0]
            .isoformat()
        ),

        "last_session": (
            target_dates[-1]
            .isoformat()
        ),

        "database_file": str(
            DATABASE_FILE
        ),

        **statistics,

        "status": (
            "SUCCESS"
            if failed == 0
            else "SUCCESS WITH FAILURES"
        ),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    """
    Display database builder status.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE F&O HISTORICAL DATABASE STATUS"
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
        f"Processed Root            : "
        f"{PROCESSED_ROOT}"
    )

    dates = (
        available_processed_dates()
    )

    print(
        f"Processed Sessions        : "
        f"{len(dates)}"
    )

    if dates:

        print(
            f"First Processed Session   : "
            f"{dates[0]}"
        )

        print(
            f"Last Processed Session    : "
            f"{dates[-1]}"
        )

    print(
        f"Database                  : "
        f"{DATABASE_FILE}"
    )

    print(
        f"Database Exists           : "
        f"{'YES' if DATABASE_FILE.exists() else 'NO'}"
    )

    if DATABASE_FILE.exists():

        try:

            connection = (
                create_connection()
            )

            create_tables(
                connection
            )

            statistics = (
                database_statistics(
                    connection
                )
            )

            connection.close()

            print("-" * 100)

            print(
                f"Stored Sessions           : "
                f"{statistics['sessions']}"
            )

            print(
                f"Futures Rows              : "
                f"{statistics['futures_rows']:,}"
            )

            print(
                f"Options Rows              : "
                f"{statistics['options_rows']:,}"
            )

            print(
                f"Total Rows                : "
                f"{statistics['total_rows']:,}"
            )

            print(
                f"Unique Underlyings        : "
                f"{statistics['unique_underlyings']}"
            )

            print(
                f"Contract Master Rows      : "
                f"{statistics['contract_master_rows']:,}"
            )

        except Exception as exc:

            print(
                f"Database Read Error       : "
                f"{type(exc).__name__}: {exc}"
            )

    print("=" * 100)


# ==========================================================
# DISPLAY SUMMARY
# ==========================================================

def display_summary(
    summary: dict[str, object],
) -> None:
    """
    Display final database build summary.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE F&O HISTORICAL DATABASE BUILDER"
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
        f"Successful Sessions       : "
        f"{summary['successful_sessions']}"
    )

    print(
        f"Failed Sessions           : "
        f"{summary['failed_sessions']}"
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
        "DATABASE COVERAGE"
    )
    print("-" * 100)

    print(
        f"Stored Sessions           : "
        f"{summary['sessions']}"
    )

    print(
        f"Futures Rows              : "
        f"{summary['futures_rows']:,}"
    )

    print(
        f"Options Rows              : "
        f"{summary['options_rows']:,}"
    )

    print(
        f"Total Historical Rows     : "
        f"{summary['total_rows']:,}"
    )

    print(
        f"Unique Underlyings        : "
        f"{summary['unique_underlyings']}"
    )

    print(
        f"Contract Master Rows      : "
        f"{summary['contract_master_rows']:,}"
    )

    print("-" * 100)

    print(
        f"Database                  : "
        f"{summary['database_file']}"
    )

    print(
        f"Audit CSV                 : "
        f"{AUDIT_CSV}"
    )

    print(
        f"Summary JSON              : "
        f"{SUMMARY_JSON}"
    )

    print("-" * 100)

    print(
        "Architecture              : "
        "ROW-BASED / ENTIRE NSE F&O UNIVERSE"
    )

    print(
        "Incremental Rebuild       : "
        "SUPPORTED"
    )

    print(
        "Duplicate Protection      : "
        "ENABLED BY DATE REBUILD"
    )

    print(
        "Research Indexes          : "
        "ENABLED"
    )

    print(
        "Raw NSE Files             : "
        "UNCHANGED"
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
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Build AQSD NSE historical "
            "Futures & Options SQLite database."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
        help=(
            "Number of processed trading sessions."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Last trading date YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display current database status."
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
        int(
            arguments.sessions
        ),
    )

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else None
    )

    try:

        summary = run_builder(
            sessions=sessions,
            end_date=end_date,
        )

    except Exception as exc:

        print()
        print("=" * 100)
        print(
            "AQSD NSE F&O HISTORICAL DATABASE BUILDER"
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