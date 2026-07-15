
"""
AQSD Core
Module: Database Foundation
Version: 1.0

Creates and manages the central SQLite database:

    AQSD/Data/aqsd_core.db

Features
--------
- Database setup
- Schema versioning
- Core tables for symbols, prices, intelligence, news,
  macro, global markets, commodities and system runs
- Integrity check
- Database status report
- Safe migrations

Commands
--------
python aqsd_database.py --setup
python aqsd_database.py --status
python aqsd_database.py --integrity
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
DATABASE_FILE = DATA_DIR / "aqsd_core.db"

SCHEMA_VERSION = 1


# ============================================================
# CONNECTION
# ============================================================

def connect() -> sqlite3.Connection:
    """
    Open the AQSD SQLite database.

    Foreign keys are enabled for every connection.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")

    return connection


# ============================================================
# SCHEMA
# ============================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nse_symbol TEXT NOT NULL UNIQUE,
    yahoo_symbol TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector TEXT,
    industry TEXT,
    fno_eligible INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    source TEXT,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adjusted_close REAL,
    volume REAL,
    source TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    UNIQUE(symbol_id, trade_date),
    FOREIGN KEY(symbol_id)
        REFERENCES symbols(symbol_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_date
ON daily_prices(symbol_id, trade_date);

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT NOT NULL,
    symbol_id INTEGER NOT NULL,
    last_price REAL,
    day_change REAL,
    day_change_percent REAL,
    volume REAL,
    open_interest REAL,
    source TEXT,
    FOREIGN KEY(symbol_id)
        REFERENCES symbols(symbol_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_time
ON market_snapshots(symbol_id, snapshot_time);

CREATE TABLE IF NOT EXISTS intelligence_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    score_date TEXT NOT NULL,
    symbol_id INTEGER NOT NULL,
    structure_score REAL,
    trend_score REAL,
    relative_strength_score REAL,
    sector_score REAL,
    pivot_score REAL,
    news_score REAL,
    macro_score REAL,
    commodity_score REAL,
    global_score REAL,
    derivatives_score REAL,
    master_score REAL,
    directional_bias TEXT,
    recommendation TEXT,
    confidence_grade TEXT,
    explanation TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(score_date, symbol_id),
    FOREIGN KEY(symbol_id)
        REFERENCES symbols(symbol_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_intelligence_symbol_date
ON intelligence_scores(symbol_id, score_date);

CREATE TABLE IF NOT EXISTS sectors (
    sector_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_name TEXT NOT NULL UNIQUE,
    benchmark_symbol TEXT,
    rotation_score REAL,
    rank_value INTEGER,
    snapshot_date TEXT,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS news_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    source TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT,
    event_type TEXT,
    company_name TEXT,
    nse_symbol TEXT,
    sector TEXT,
    country TEXT,
    sentiment_score REAL,
    materiality_score REAL,
    credibility_score REAL,
    urgency_score REAL,
    expected_impact TEXT,
    time_horizon TEXT,
    status TEXT,
    raw_payload TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_symbol_time
ON news_events(nse_symbol, event_time);

CREATE TABLE IF NOT EXISTS macro_events (
    macro_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,
    country TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    actual_value REAL,
    expected_value REAL,
    previous_value REAL,
    unit TEXT,
    surprise_score REAL,
    sector_impact TEXT,
    source TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS global_markets (
    global_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    market_name TEXT,
    asset_type TEXT,
    close_value REAL,
    day_change_percent REAL,
    five_day_change_percent REAL,
    risk_signal TEXT,
    source TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(snapshot_date, symbol)
);

CREATE TABLE IF NOT EXISTS commodities (
    commodity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    commodity_name TEXT,
    close_value REAL,
    day_change_percent REAL,
    five_day_change_percent REAL,
    affected_sectors TEXT,
    source TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(snapshot_date, symbol)
);

CREATE TABLE IF NOT EXISTS system_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    records_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT,
    setting_type TEXT,
    updated_at TEXT NOT NULL
);
"""


# ============================================================
# DATABASE SETUP
# ============================================================

def setup_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA_SQL)

        current = connection.execute(
            "SELECT MAX(version) AS version FROM schema_version"
        ).fetchone()["version"]

        if current is None:
            connection.execute(
                """
                INSERT INTO schema_version(version, applied_at)
                VALUES (?, ?)
                """,
                (
                    SCHEMA_VERSION,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

        elif current < SCHEMA_VERSION:
            migrate_database(
                connection,
                current,
                SCHEMA_VERSION,
            )

        connection.commit()


def migrate_database(
    connection: sqlite3.Connection,
    current_version: int,
    target_version: int,
) -> None:
    """
    Apply future schema migrations.

    Version 1 is the initial schema.
    """

    version = current_version

    while version < target_version:
        next_version = version + 1

        if next_version == 1:
            pass

        else:
            raise RuntimeError(
                f"No migration available for schema version {next_version}"
            )

        connection.execute(
            """
            INSERT INTO schema_version(version, applied_at)
            VALUES (?, ?)
            """,
            (
                next_version,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        version = next_version


# ============================================================
# RUN LOGGING
# ============================================================

def start_run(
    module_name: str,
    message: str = "",
) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO system_runs(
                module_name,
                started_at,
                status,
                message
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                module_name,
                datetime.now().isoformat(timespec="seconds"),
                "RUNNING",
                message,
            ),
        )

        connection.commit()
        return int(cursor.lastrowid)


def finish_run(
    run_id: int,
    status: str,
    records_processed: int = 0,
    errors_count: int = 0,
    message: str = "",
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE system_runs
            SET completed_at = ?,
                status = ?,
                records_processed = ?,
                errors_count = ?,
                message = ?
            WHERE run_id = ?
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                status,
                records_processed,
                errors_count,
                message,
                run_id,
            ),
        )

        connection.commit()


# ============================================================
# HEALTH & STATUS
# ============================================================

def integrity_check() -> tuple[bool, str]:
    setup_database()

    with connect() as connection:
        result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

    return result == "ok", str(result)


def table_counts() -> dict[str, int]:
    setup_database()

    tables = [
        "symbols",
        "daily_prices",
        "market_snapshots",
        "intelligence_scores",
        "sectors",
        "news_events",
        "macro_events",
        "global_markets",
        "commodities",
        "system_runs",
        "settings",
    ]

    counts: dict[str, int] = {}

    with connect() as connection:
        for table in tables:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            counts[table] = int(count)

    return counts


def latest_price_date() -> str:
    setup_database()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM daily_prices
            """
        ).fetchone()

    return row["latest_date"] or "No price data"


def database_size_mb() -> float:
    if not DATABASE_FILE.exists():
        return 0.0

    return DATABASE_FILE.stat().st_size / (1024 * 1024)


def show_status() -> None:
    setup_database()

    ok, integrity_message = integrity_check()
    counts = table_counts()

    with connect() as connection:
        schema_version = connection.execute(
            """
            SELECT MAX(version) AS version
            FROM schema_version
            """
        ).fetchone()["version"]

    print("\nAQSD CORE DATABASE STATUS")
    print("=" * 72)
    print(f"Database: {DATABASE_FILE}")
    print(f"Schema version: {schema_version}")
    print(f"Integrity: {'GOOD' if ok else 'FAILED'}")
    print(f"Integrity message: {integrity_message}")
    print(f"Database size: {database_size_mb():.2f} MB")
    print(f"Latest price date: {latest_price_date()}")
    print("-" * 72)

    for table, count in counts.items():
        print(f"{table:<24} {count:>10}")

    print("=" * 72)


# ============================================================
# COMMAND LINE
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage the AQSD Core SQLite database."
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create or upgrade the AQSD database.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Display database status and table counts.",
    )

    parser.add_argument(
        "--integrity",
        action="store_true",
        help="Run SQLite integrity checks.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.integrity:
        ok, message = integrity_check()

        print("\nAQSD DATABASE INTEGRITY CHECK")
        print("=" * 72)
        print(f"Result: {'PASS' if ok else 'FAIL'}")
        print(f"Message: {message}")
        print(f"Database: {DATABASE_FILE}")
        return

    if args.status:
        show_status()
        return

    setup_database()

    print("\nAQSD CORE DATABASE")
    print("=" * 72)
    print("Database setup completed successfully.")
    print(f"Database: {DATABASE_FILE}")
    print(f"Schema version: {SCHEMA_VERSION}")
    print("=" * 72)


if __name__ == "__main__":
    main()
