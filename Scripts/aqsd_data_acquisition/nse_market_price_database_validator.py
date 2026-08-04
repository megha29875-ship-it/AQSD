"""
AQSD
NSE Market Price Database Validator

Module : MPD-002
Version: 1.0.0
Author : AQSD

Purpose
-------
Validate the AQSD Market Price Database before it is accepted as a
trusted AQSD data source.

Validation includes:
- database availability
- SQLite integrity
- required table availability
- required columns
- row count
- unique symbols
- trading session coverage
- duplicate trade_date + symbol keys
- blank symbols
- invalid dates
- future dates
- null OHLC values
- non-positive prices
- invalid OHLC relationships
- negative volume
- Security Master symbol reconciliation

Protection
----------
- Market Price database opened READ ONLY
- Frozen NSE F&O database untouched
- Security Master read only
- No INSERT / UPDATE / DELETE
- No historical fabrication
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-002"
MODULE_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

DATABASE_FILE: Final[Path] = Path(
    r"D:\AQSD_DATA\Databases\AQSD_Market_Price.db"
)

SECURITY_MASTER_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Output"
    / "AQSD_Security_Master_Enriched.csv"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Database_Validation_Audit.csv"
)

ISSUES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Database_Validation_Issues.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Database_Validation_Summary.json"
)

TABLE_NAME: Final[str] = "market_price"

REQUIRED_COLUMNS: Final[set[str]] = {
    "trade_date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
}


# ============================================================
# HELPERS
# ============================================================

def ensure_output_directory() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def open_read_only_database() -> sqlite3.Connection:

    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Market Price database not found: {DATABASE_FILE}"
        )

    uri = (
        f"file:{DATABASE_FILE.as_posix()}"
        "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:

    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [
        str(row["name"])
        for row in rows
    ]


def load_security_master_symbols() -> set[str]:

    if not SECURITY_MASTER_FILE.exists():
        return set()

    dataframe = pd.read_csv(
        SECURITY_MASTER_FILE,
        usecols=["symbol"],
        low_memory=False,
    )

    return set(
        dataframe["symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )


# ============================================================
# SQLITE INTEGRITY
# ============================================================

def run_integrity_check(
    connection: sqlite3.Connection,
) -> str:

    row = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()

    if row is None:
        return "UNKNOWN"

    return str(
        row[0]
    ).strip()


# ============================================================
# CORE DATABASE STATISTICS
# ============================================================

def read_database_statistics(
    connection: sqlite3.Connection,
) -> dict[str, object]:

    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT symbol) AS unique_symbols,
            COUNT(DISTINCT trade_date) AS sessions,
            MIN(trade_date) AS first_session,
            MAX(trade_date) AS last_session
        FROM "{TABLE_NAME}"
        """
    ).fetchone()

    return {
        "total_rows":
            int(row["total_rows"] or 0),
        "unique_symbols":
            int(row["unique_symbols"] or 0),
        "sessions":
            int(row["sessions"] or 0),
        "first_session":
            row["first_session"],
        "last_session":
            row["last_session"],
    }


# ============================================================
# VALIDATION QUERIES
# ============================================================

def count_duplicate_keys(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT
                trade_date,
                symbol,
                COUNT(*) AS row_count
            FROM "{TABLE_NAME}"
            GROUP BY
                trade_date,
                symbol
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_blank_symbols(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE symbol IS NULL
           OR TRIM(symbol) = ''
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_null_ohlc(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE open IS NULL
           OR high IS NULL
           OR low IS NULL
           OR close IS NULL
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_non_positive_prices(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE open <= 0
           OR high <= 0
           OR low <= 0
           OR close <= 0
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_invalid_ohlc(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE
            high < low

            OR open < low
            OR open > high

            OR close < low
            OR close > high
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_negative_volume(
    connection: sqlite3.Connection,
) -> int:

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE volume < 0
        """
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def count_invalid_dates(
    connection: sqlite3.Connection,
) -> int:

    rows = connection.execute(
        f"""
        SELECT DISTINCT trade_date
        FROM "{TABLE_NAME}"
        """
    ).fetchall()

    invalid = 0

    for row in rows:

        value = row[0]

        if value is None:
            invalid += 1
            continue

        try:
            date.fromisoformat(
                str(value)
            )

        except ValueError:
            invalid += 1

    return invalid


def count_future_dates(
    connection: sqlite3.Connection,
) -> int:

    today_text = date.today().isoformat()

    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM "{TABLE_NAME}"
        WHERE trade_date > ?
        """,
        (today_text,),
    ).fetchone()

    return int(
        row[0]
        or 0
    )


def read_database_symbols(
    connection: sqlite3.Connection,
) -> set[str]:

    rows = connection.execute(
        f"""
        SELECT DISTINCT symbol
        FROM "{TABLE_NAME}"
        WHERE symbol IS NOT NULL
          AND TRIM(symbol) <> ''
        """
    ).fetchall()

    return {
        str(row[0])
        .strip()
        .upper()
        for row in rows
    }


# ============================================================
# ISSUE SAMPLE
# ============================================================

def collect_future_date_samples(
    connection: sqlite3.Connection,
    *,
    limit: int = 25,
) -> list[dict[str, object]]:

    rows = connection.execute(
        f"""
        SELECT
            trade_date,
            symbol,
            open,
            high,
            low,
            close,
            volume,
            source_file
        FROM "{TABLE_NAME}"
        WHERE trade_date > ?
        ORDER BY trade_date, symbol
        LIMIT ?
        """,
        (
            date.today().isoformat(),
            limit,
        ),
    ).fetchall()

    output: list[
        dict[str, object]
    ] = []

    for row in rows:

        output.append(
            {
                "issue_type":
                    "FUTURE_DATE",
                "trade_date":
                    row["trade_date"],
                "symbol":
                    row["symbol"],
                "open":
                    row["open"],
                "high":
                    row["high"],
                "low":
                    row["low"],
                "close":
                    row["close"],
                "volume":
                    row["volume"],
                "source_file":
                    row["source_file"],
            }
        )

    return output


def collect_null_ohlc_samples(
    connection: sqlite3.Connection,
    *,
    limit: int = 25,
) -> list[dict[str, object]]:

    rows = connection.execute(
        f"""
        SELECT
            trade_date,
            symbol,
            open,
            high,
            low,
            close,
            volume,
            source_file
        FROM "{TABLE_NAME}"
        WHERE open IS NULL
           OR high IS NULL
           OR low IS NULL
           OR close IS NULL
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    output: list[
        dict[str, object]
    ] = []

    for row in rows:

        output.append(
            {
                "issue_type":
                    "NULL_OHLC",
                "trade_date":
                    row["trade_date"],
                "symbol":
                    row["symbol"],
                "open":
                    row["open"],
                "high":
                    row["high"],
                "low":
                    row["low"],
                "close":
                    row["close"],
                "volume":
                    row["volume"],
                "source_file":
                    row["source_file"],
            }
        )

    return output


# ============================================================
# VALIDATION
# ============================================================

def validate_database() -> dict[str, object]:

    ensure_output_directory()

    connection = open_read_only_database()

    try:

        integrity = run_integrity_check(
            connection
        )

        if not table_exists(
            connection,
            TABLE_NAME,
        ):
            raise RuntimeError(
                f"Required table not found: {TABLE_NAME}"
            )

        columns = get_table_columns(
            connection,
            TABLE_NAME,
        )

        missing_columns = sorted(
            REQUIRED_COLUMNS
            - set(columns)
        )

        if missing_columns:
            raise RuntimeError(
                "Missing required columns: "
                + ", ".join(
                    missing_columns
                )
            )

        statistics = read_database_statistics(
            connection
        )

        duplicate_keys = count_duplicate_keys(
            connection
        )

        blank_symbols = count_blank_symbols(
            connection
        )

        null_ohlc = count_null_ohlc(
            connection
        )

        non_positive_prices = (
            count_non_positive_prices(
                connection
            )
        )

        invalid_ohlc = count_invalid_ohlc(
            connection
        )

        negative_volume = count_negative_volume(
            connection
        )

        invalid_dates = count_invalid_dates(
            connection
        )

        future_dates = count_future_dates(
            connection
        )

        database_symbols = read_database_symbols(
            connection
        )

        security_master_symbols = (
            load_security_master_symbols()
        )

        unknown_symbols = sorted(
            database_symbols
            - security_master_symbols
        )

        missing_master_symbols = sorted(
            security_master_symbols
            - database_symbols
        )

        issue_samples = []

        issue_samples.extend(
            collect_future_date_samples(
                connection
            )
        )

        issue_samples.extend(
            collect_null_ohlc_samples(
                connection
            )
        )

    finally:
        connection.close()

    # ========================================================
    # CRITICAL / WARNING CLASSIFICATION
    # ========================================================

    critical_issues = 0

    if integrity.lower() != "ok":
        critical_issues += 1

    critical_issues += duplicate_keys
    critical_issues += blank_symbols
    critical_issues += null_ohlc
    critical_issues += non_positive_prices
    critical_issues += invalid_ohlc
    critical_issues += negative_volume
    critical_issues += invalid_dates
    critical_issues += future_dates

    # Unknown database symbols are critical because MPD
    # must reconcile to the approved Security Master.
    critical_issues += len(
        unknown_symbols
    )

    warnings = len(
        missing_master_symbols
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    result = {
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

        "database":
            str(
                DATABASE_FILE
            ),

        "table":
            TABLE_NAME,

        "sqlite_integrity":
            integrity,

        "database_rows":
            statistics[
                "total_rows"
            ],

        "unique_symbols":
            statistics[
                "unique_symbols"
            ],

        "trading_sessions":
            statistics[
                "sessions"
            ],

        "first_session":
            statistics[
                "first_session"
            ],

        "last_session":
            statistics[
                "last_session"
            ],

        "duplicate_keys":
            duplicate_keys,

        "blank_symbols":
            blank_symbols,

        "null_ohlc":
            null_ohlc,

        "non_positive_prices":
            non_positive_prices,

        "invalid_ohlc":
            invalid_ohlc,

        "negative_volume":
            negative_volume,

        "invalid_dates":
            invalid_dates,

        "future_date_rows":
            future_dates,

        "security_master_symbols":
            len(
                security_master_symbols
            ),

        "unknown_database_symbols":
            len(
                unknown_symbols
            ),

        "missing_security_master_symbols":
            len(
                missing_master_symbols
            ),

        "unknown_symbols":
            unknown_symbols,

        "missing_master_symbols":
            missing_master_symbols,

        "critical_issues":
            critical_issues,

        "warnings":
            warnings,

        "database_modified":
            False,

        "frozen_fno_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            status,

        "issue_samples":
            issue_samples,
    }

    return result


# ============================================================
# OUTPUT FILES
# ============================================================

def write_outputs(
    result: dict[str, object],
) -> None:

    ensure_output_directory()

    audit_row = {
        key: value
        for key, value in result.items()
        if key not in {
            "unknown_symbols",
            "missing_master_symbols",
            "issue_samples",
        }
    }

    pd.DataFrame(
        [audit_row]
    ).to_csv(
        AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    issues = list(
        result.get(
            "issue_samples",
            [],
        )
    )

    if issues:

        pd.DataFrame(
            issues
        ).to_csv(
            ISSUES_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    else:

        pd.DataFrame(
            columns=[
                "issue_type",
                "trade_date",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source_file",
            ]
        ).to_csv(
            ISSUES_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    SUMMARY_JSON.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    result: dict[str, object],
) -> None:

    print()
    print("=" * 88)
    print("AQSD MARKET PRICE DATABASE VALIDATOR")
    print("=" * 88)

    print(
        f"Module                     : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                    : "
        f"{MODULE_VERSION}"
    )

    print(
        "Access Mode                : READ ONLY"
    )

    print("-" * 88)

    print(
        f"SQLite Integrity           : "
        f"{result['sqlite_integrity']}"
    )

    print(
        f"Database Rows              : "
        f"{int(result['database_rows']):,}"
    )

    print(
        f"Unique Symbols             : "
        f"{int(result['unique_symbols']):,}"
    )

    print(
        f"Trading Sessions           : "
        f"{int(result['trading_sessions']):,}"
    )

    print(
        f"First Session              : "
        f"{result['first_session']}"
    )

    print(
        f"Last Session               : "
        f"{result['last_session']}"
    )

    print("-" * 88)

    print(
        f"Duplicate Keys             : "
        f"{int(result['duplicate_keys']):,}"
    )

    print(
        f"Blank Symbols              : "
        f"{int(result['blank_symbols']):,}"
    )

    print(
        f"Null OHLC                  : "
        f"{int(result['null_ohlc']):,}"
    )

    print(
        f"Non-Positive Prices        : "
        f"{int(result['non_positive_prices']):,}"
    )

    print(
        f"Invalid OHLC               : "
        f"{int(result['invalid_ohlc']):,}"
    )

    print(
        f"Negative Volume            : "
        f"{int(result['negative_volume']):,}"
    )

    print(
        f"Invalid Dates              : "
        f"{int(result['invalid_dates']):,}"
    )

    print(
        f"Future-Date Rows           : "
        f"{int(result['future_date_rows']):,}"
    )

    print("-" * 88)

    print(
        f"Security Master Symbols    : "
        f"{int(result['security_master_symbols']):,}"
    )

    print(
        f"Unknown DB Symbols         : "
        f"{int(result['unknown_database_symbols']):,}"
    )

    print(
        f"Master Symbols Missing MPD : "
        f"{int(result['missing_security_master_symbols']):,}"
    )

    print("-" * 88)

    print(
        f"Critical Issues            : "
        f"{int(result['critical_issues']):,}"
    )

    print(
        f"Warnings                   : "
        f"{int(result['warnings']):,}"
    )

    print("-" * 88)

    print(
        f"Database                   : "
        f"{DATABASE_FILE}"
    )

    print(
        "Market Price DB Modified   : NO"
    )

    print(
        "Frozen F&O DB Modified     : NO"
    )

    print(
        "Historical Fabrication     : PROHIBITED"
    )

    print(
        f"Audit CSV                  : "
        f"{AUDIT_CSV}"
    )

    print(
        f"Issues CSV                 : "
        f"{ISSUES_CSV}"
    )

    print(
        f"Summary JSON               : "
        f"{SUMMARY_JSON}"
    )

    print("-" * 88)

    print(
        f"Status                     : "
        f"{result['status']}"
    )

    print("=" * 88)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        result = validate_database()

        write_outputs(
            result
        )

        display_summary(
            result
        )

        if result[
            "status"
        ] != "SUCCESS":

            raise SystemExit(1)

    except SystemExit:
        raise

    except Exception as exc:

        print()
        print("=" * 88)
        print("AQSD MARKET PRICE DATABASE VALIDATOR")
        print("=" * 88)

        print(
            "Status                     : FAILED"
        )

        print(
            f"Reason                     : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "Database Modification      : NONE"
        )

        print("=" * 88)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()