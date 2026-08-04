"""
AQSD
NSE Market Price Database Builder

Module : MPD-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Build the AQSD Market Price Database from existing AQSD processed
price data.

Architecture
------------
One row = one security for one trading date.

Primary Key
-----------
trade_date + symbol

Principles
----------
- Historical F&O database remains untouched.
- No historical fabrication.
- Existing rows are preserved.
- Duplicate date/symbol rows are prohibited.
- Database is designed for incremental append.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "MPD-001"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_ROOT = Path(r"D:\AQSD_DATA")

DATABASE_DIR = DATA_ROOT / "Databases"

DATABASE_FILE = (
    DATABASE_DIR
    / "AQSD_Market_Price.db"
)

OUTPUT_DIR = PROJECT_ROOT / "Output"

SUMMARY_JSON = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Database_Summary.json"
)


# ============================================================
# SOURCE CANDIDATES
# ============================================================

SOURCE_CANDIDATES = [
    PROJECT_ROOT / "Data" / "Market_Prices",
    PROJECT_ROOT / "Data",
    DATA_ROOT / "Processed",
    DATA_ROOT / "Processed" / "NSE",
]


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def normalize_column_name(
    value: object,
) -> str:

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def normalize_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = dataframe.copy()

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    rename_map = {}

    candidates = {
        "date": "trade_date",
        "trading_date": "trade_date",
        "timestamp": "trade_date",

        "ticker": "symbol",
        "security": "symbol",
        "underlying": "symbol",

        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",

        "total_traded_quantity": "volume",
        "traded_quantity": "volume",

        "average_price": "avg_price",
        "average_traded_price": "avg_price",
        "atp": "avg_price",
    }

    for old_name, new_name in candidates.items():

        if (
            old_name in dataframe.columns
            and new_name not in dataframe.columns
        ):

            rename_map[
                old_name
            ] = new_name

    if rename_map:

        dataframe = dataframe.rename(
            columns=rename_map
        )

    return dataframe


def detect_source_files() -> list[Path]:

    files: list[Path] = []

    for root in SOURCE_CANDIDATES:

        if not root.exists():
            continue

        for pattern in (
            "*.csv",
            "*.CSV",
        ):

            files.extend(
                root.rglob(
                    pattern
                )
            )

    unique_files = sorted(
        set(files)
    )

    return unique_files


def is_price_file(
    path: Path,
) -> bool:

    name = path.name.lower()

    exclude_terms = [
        "security_master",
        "participant",
        "option",
        "futures",
        "audit",
        "issue",
        "summary",
        "calendar",
        "breadth",
        "contract",
        "change",
    ]

    if any(
        term in name
        for term in exclude_terms
    ):
        return False

    return True


# ============================================================
# DATABASE
# ============================================================

def create_connection() -> sqlite3.Connection:

    ensure_directories()

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA synchronous=NORMAL"
    )

    return connection


def create_tables(
    connection: sqlite3.Connection,
) -> None:

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS market_price (
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,

            open REAL,
            high REAL,
            low REAL,
            close REAL,

            volume REAL,
            avg_price REAL,

            source_file TEXT,
            loaded_at TEXT NOT NULL,

            PRIMARY KEY (
                trade_date,
                symbol
            )
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_price_symbol
        ON market_price(symbol)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_market_price_date
        ON market_price(trade_date)
        """
    )

    connection.commit()


# ============================================================
# PREPARATION
# ============================================================

def prepare_price_data(
    dataframe: pd.DataFrame,
    *,
    source_file: Path,
) -> pd.DataFrame:

    dataframe = normalize_dataframe(
        dataframe
    )

    required = {
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:

        raise RuntimeError(
            f"{source_file.name}: missing required columns: "
            + ", ".join(
                missing
            )
        )

    dataframe = dataframe.copy()

    dataframe["trade_date"] = pd.to_datetime(
        dataframe["trade_date"],
        errors="coerce",
        dayfirst=True,
    ).dt.strftime(
        "%Y-%m-%d"
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "avg_price",
    ]:

        if column not in dataframe.columns:
            dataframe[column] = None

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe = dataframe[
        dataframe[
            "trade_date"
        ].notna()
    ]

    dataframe = dataframe[
        dataframe[
            "symbol"
        ].ne("")
    ]

    invalid_ohlc = (
        (dataframe["high"] < dataframe["low"])
        |
        (dataframe["open"] < dataframe["low"])
        |
        (dataframe["open"] > dataframe["high"])
        |
        (dataframe["close"] < dataframe["low"])
        |
        (dataframe["close"] > dataframe["high"])
    )

    dataframe = dataframe.loc[
        ~invalid_ohlc
    ].copy()

    dataframe = dataframe.drop_duplicates(
        subset=[
            "trade_date",
            "symbol",
        ],
        keep="last",
    )

    dataframe["source_file"] = str(
        source_file
    )

    dataframe["loaded_at"] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    return dataframe[
        [
            "trade_date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "avg_price",
            "source_file",
            "loaded_at",
        ]
    ]


# ============================================================
# INGESTION
# ============================================================

def insert_dataframe(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> int:

    if dataframe.empty:
        return 0

    rows = [
        tuple(row)
        for row in dataframe.itertuples(
            index=False,
            name=None,
        )
    ]

    connection.executemany(
        """
        INSERT OR IGNORE INTO market_price (
            trade_date,
            symbol,
            open,
            high,
            low,
            close,
            volume,
            avg_price,
            source_file,
            loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    connection.commit()

    return int(
        connection.total_changes
    )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def read_database_summary(
    connection: sqlite3.Connection,
) -> dict[str, object]:

    row = connection.execute(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT symbol) AS symbols,
            COUNT(DISTINCT trade_date) AS sessions,
            MIN(trade_date) AS first_session,
            MAX(trade_date) AS last_session
        FROM market_price
        """
    ).fetchone()

    return {
        "rows":
            int(
                row[0]
                or 0
            ),
        "symbols":
            int(
                row[1]
                or 0
            ),
        "sessions":
            int(
                row[2]
                or 0
            ),
        "first_session":
            row[3],
        "last_session":
            row[4],
    }


# ============================================================
# RUN BUILDER
# ============================================================

def run_builder() -> dict[str, object]:

    source_files = [
        path
        for path in detect_source_files()
        if is_price_file(
            path
        )
    ]

    print()
    print(
        f"Candidate Source Files     : "
        f"{len(source_files)}"
    )

    connection = create_connection()

    create_tables(
        connection
    )

    files_loaded = 0
    files_skipped = 0
    rows_prepared = 0

    try:

        for path in source_files:

            try:

                dataframe = pd.read_csv(
                    path,
                    low_memory=False,
                )

                prepared = prepare_price_data(
                    dataframe,
                    source_file=path,
                )

                if prepared.empty:

                    files_skipped += 1
                    continue

                insert_dataframe(
                    connection,
                    prepared,
                )

                files_loaded += 1

                rows_prepared += len(
                    prepared
                )

                print(
                    f"LOADED  "
                    f"{path.name:<45} "
                    f"{len(prepared):>10,} rows"
                )

            except Exception:

                files_skipped += 1

        database_summary = read_database_summary(
            connection
        )

    finally:

        connection.close()

    summary = {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            ),
        "database_file":
            str(
                DATABASE_FILE
            ),
        "candidate_source_files":
            len(
                source_files
            ),
        "files_loaded":
            files_loaded,
        "files_skipped":
            files_skipped,
        "rows_prepared":
            rows_prepared,
        **database_summary,
        "historical_fno_database_modified":
            False,
        "historical_fabrication":
            False,
        "status":
            "SUCCESS",
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return summary


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()
    print("=" * 82)
    print("AQSD MARKET PRICE DATABASE BUILDER")
    print("=" * 82)

    print(
        f"Module                     : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                    : "
        f"{MODULE_VERSION}"
    )

    print("-" * 82)

    print(
        f"Candidate Source Files     : "
        f"{summary['candidate_source_files']}"
    )

    print(
        f"Files Loaded               : "
        f"{summary['files_loaded']}"
    )

    print(
        f"Files Skipped              : "
        f"{summary['files_skipped']}"
    )

    print(
        f"Prepared Rows              : "
        f"{summary['rows_prepared']:,}"
    )

    print("-" * 82)

    print(
        f"Database Rows              : "
        f"{summary['rows']:,}"
    )

    print(
        f"Unique Symbols             : "
        f"{summary['symbols']:,}"
    )

    print(
        f"Trading Sessions           : "
        f"{summary['sessions']:,}"
    )

    print(
        f"First Session              : "
        f"{summary['first_session']}"
    )

    print(
        f"Last Session               : "
        f"{summary['last_session']}"
    )

    print("-" * 82)

    print(
        f"Database                   : "
        f"{DATABASE_FILE}"
    )

    print(
        "Frozen F&O Database        : UNTOUCHED"
    )

    print(
        "Historical Fabrication     : PROHIBITED"
    )

    print("-" * 82)

    print(
        f"Status                     : "
        f"{summary['status']}"
    )

    print("=" * 82)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_builder()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        print("=" * 82)
        print("AQSD MARKET PRICE DATABASE BUILDER")
        print("=" * 82)

        print(
            "Status                     : FAILED"
        )

        print(
            f"Reason                     : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 82)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()