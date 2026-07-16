
"""
AQSD Core
Module: Symbol Resolver & Validator
Version: 1.0

Purpose
-------
Maintains Yahoo/NSE symbol aliases without deleting historical data.

Features
--------
- Creates symbol_aliases and symbol_validation_log tables
- Tests active Yahoo symbols
- Records VALID / INVALID / NO DATA / ERROR status
- Applies only explicitly approved aliases
- Preserves old price history
- Produces CSV validation reports
- Supports manual corrections
- Can deactivate obsolete symbols safely

Important
---------
The resolver does not guess corporate-action replacements automatically.
A replacement is applied only when it is stored as APPROVED.

Commands
--------
python aqsd_symbol_resolver.py --setup
python aqsd_symbol_resolver.py --validate --limit 20
python aqsd_symbol_resolver.py --validate
python aqsd_symbol_resolver.py --failed
python aqsd_symbol_resolver.py --add-alias L&TFH LTF --reason "NSE symbol changed"
python aqsd_symbol_resolver.py --approve L&TFH
python aqsd_symbol_resolver.py --apply-approved
python aqsd_symbol_resolver.py --mark-inactive IDFC --reason "Merged / no longer traded"
python aqsd_symbol_resolver.py --export-report
python aqsd_symbol_resolver.py --status
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from aqsd_database import connect, setup_database, start_run, finish_run


# ============================================================
# PATHS / SETTINGS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
DATA_DIR = BASE_DIR / "Data"
REPORT_DIR = BASE_DIR / "Output" / "Symbol_Reports"

DEFAULT_PERIOD = "5d"
DEFAULT_PAUSE = 0.4


# ============================================================
# DATABASE EXTENSION
# ============================================================

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS symbol_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    old_nse_symbol TEXT NOT NULL UNIQUE,
    old_yahoo_symbol TEXT,
    new_nse_symbol TEXT,
    new_yahoo_symbol TEXT,
    alias_status TEXT NOT NULL DEFAULT 'PENDING',
    reason TEXT,
    source TEXT,
    approved_at TEXT,
    applied_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbol_validation_log (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    checked_at TEXT NOT NULL,
    yahoo_symbol TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    latest_market_date TEXT,
    rows_received INTEGER DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY(symbol_id)
        REFERENCES symbols(symbol_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbol_validation_symbol_time
ON symbol_validation_log(symbol_id, checked_at);

CREATE INDEX IF NOT EXISTS idx_symbol_validation_status
ON symbol_validation_log(validation_status);
"""


def setup_resolver_tables() -> None:
    setup_database()

    with connect() as connection:
        connection.executescript(EXTRA_SCHEMA)
        connection.commit()


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_nse_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()

    if symbol.endswith(".NS"):
        symbol = symbol[:-3]

    return symbol.replace(" ", "")


def normalize_yahoo_symbol(value: str) -> str:
    nse_symbol = normalize_nse_symbol(value)
    return f"{nse_symbol}.NS" if nse_symbol else ""


# ============================================================
# SYMBOL QUERIES
# ============================================================

def get_active_symbols(limit: int = 0) -> list[dict]:
    setup_resolver_tables()

    query = """
        SELECT
            symbol_id,
            nse_symbol,
            yahoo_symbol,
            company_name,
            sector,
            active
        FROM symbols
        WHERE active = 1
        ORDER BY nse_symbol
    """

    params: tuple = ()

    if limit > 0:
        query += " LIMIT ?"
        params = (limit,)

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_symbol_record(symbol: str) -> dict | None:
    nse_symbol = normalize_nse_symbol(symbol)
    yahoo_symbol = normalize_yahoo_symbol(symbol)

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM symbols
            WHERE nse_symbol = ?
               OR yahoo_symbol = ?
            LIMIT 1
            """,
            (nse_symbol, yahoo_symbol),
        ).fetchone()

    return dict(row) if row else None


# ============================================================
# YAHOO VALIDATION
# ============================================================

def flatten_close(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    if "Close" not in frame.columns:
        return pd.Series(dtype=float)

    return frame["Close"].dropna()


def validate_yahoo_symbol(
    yahoo_symbol: str,
    period: str,
) -> dict:
    """
    Return a conservative validation result.

    VALID:
        At least one usable close price was returned.

    NO_DATA:
        Request completed but no usable prices were returned.

    ERROR:
        yfinance raised an exception.
    """

    try:
        frame = yf.download(
            yahoo_symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )

        close = flatten_close(frame)

        if close.empty:
            return {
                "status": "NO_DATA",
                "rows": 0,
                "latest_date": None,
                "error": "No usable price rows returned",
            }

        latest = pd.to_datetime(close.index.max()).date().isoformat()

        return {
            "status": "VALID",
            "rows": int(len(close)),
            "latest_date": latest,
            "error": "",
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "rows": 0,
            "latest_date": None,
            "error": str(error),
        }


def record_validation(
    connection: sqlite3.Connection,
    symbol_id: int,
    yahoo_symbol: str,
    result: dict,
) -> None:
    connection.execute(
        """
        INSERT INTO symbol_validation_log(
            symbol_id,
            checked_at,
            yahoo_symbol,
            validation_status,
            latest_market_date,
            rows_received,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol_id,
            datetime.now().isoformat(timespec="seconds"),
            yahoo_symbol,
            result["status"],
            result["latest_date"],
            result["rows"],
            result["error"],
        ),
    )


def validate_symbols(
    period: str,
    limit: int,
    pause: float,
) -> tuple[int, int, int]:
    symbols = get_active_symbols(limit)

    if not symbols:
        raise RuntimeError(
            "Symbol Master is empty. "
            "Run aqsd_symbol_master.py --import first."
        )

    run_id = start_run(
        "aqsd_symbol_resolver",
        f"Validating {len(symbols)} symbols",
    )

    valid = 0
    invalid = 0
    errors = 0

    print("\nAQSD SYMBOL VALIDATION")
    print("=" * 78)
    print(f"Symbols: {len(symbols)}")
    print(f"Validation period: {period}")

    try:
        with connect() as connection:
            for index, symbol in enumerate(symbols, start=1):
                yahoo_symbol = symbol["yahoo_symbol"]

                print(
                    f"[{index}/{len(symbols)}] "
                    f"{yahoo_symbol:<22}",
                    end="",
                )

                result = validate_yahoo_symbol(
                    yahoo_symbol,
                    period,
                )

                record_validation(
                    connection,
                    symbol["symbol_id"],
                    yahoo_symbol,
                    result,
                )

                if result["status"] == "VALID":
                    valid += 1
                    print(
                        f"VALID  "
                        f"{result['rows']} rows  "
                        f"{result['latest_date']}"
                    )

                elif result["status"] == "NO_DATA":
                    invalid += 1
                    print("NO DATA")

                else:
                    errors += 1
                    print(f"ERROR  {result['error']}")

                if pause > 0 and index < len(symbols):
                    time.sleep(pause)

            connection.commit()

        finish_run(
            run_id,
            status=(
                "SUCCESS"
                if invalid == 0 and errors == 0
                else "PARTIAL"
            ),
            records_processed=len(symbols),
            errors_count=invalid + errors,
            message=(
                f"Valid={valid}; "
                f"No data={invalid}; "
                f"Errors={errors}"
            ),
        )

        return valid, invalid, errors

    except Exception as error:
        finish_run(
            run_id,
            status="FAILED",
            records_processed=valid + invalid + errors,
            errors_count=errors + 1,
            message=str(error),
        )
        raise


# ============================================================
# ALIAS MANAGEMENT
# ============================================================

def add_alias(
    old_symbol: str,
    new_symbol: str,
    reason: str,
    source: str,
) -> None:
    setup_resolver_tables()

    old_nse = normalize_nse_symbol(old_symbol)
    new_nse = normalize_nse_symbol(new_symbol)

    if not old_nse or not new_nse:
        raise ValueError("Old and new symbols are required.")

    now = datetime.now().isoformat(timespec="seconds")

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO symbol_aliases(
                old_nse_symbol,
                old_yahoo_symbol,
                new_nse_symbol,
                new_yahoo_symbol,
                alias_status,
                reason,
                source,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
            ON CONFLICT(old_nse_symbol)
            DO UPDATE SET
                old_yahoo_symbol = excluded.old_yahoo_symbol,
                new_nse_symbol = excluded.new_nse_symbol,
                new_yahoo_symbol = excluded.new_yahoo_symbol,
                alias_status = 'PENDING',
                reason = excluded.reason,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                old_nse,
                normalize_yahoo_symbol(old_nse),
                new_nse,
                normalize_yahoo_symbol(new_nse),
                reason,
                source,
                now,
                now,
            ),
        )
        connection.commit()


def approve_alias(old_symbol: str) -> bool:
    old_nse = normalize_nse_symbol(old_symbol)
    now = datetime.now().isoformat(timespec="seconds")

    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE symbol_aliases
            SET alias_status = 'APPROVED',
                approved_at = ?,
                updated_at = ?
            WHERE old_nse_symbol = ?
            """,
            (now, now, old_nse),
        )
        connection.commit()

    return cursor.rowcount > 0


def reject_alias(old_symbol: str, reason: str = "") -> bool:
    old_nse = normalize_nse_symbol(old_symbol)
    now = datetime.now().isoformat(timespec="seconds")

    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE symbol_aliases
            SET alias_status = 'REJECTED',
                reason = CASE
                    WHEN ? <> '' THEN ?
                    ELSE reason
                END,
                updated_at = ?
            WHERE old_nse_symbol = ?
            """,
            (reason, reason, now, old_nse),
        )
        connection.commit()

    return cursor.rowcount > 0


def apply_one_alias(
    connection: sqlite3.Connection,
    alias: sqlite3.Row,
) -> str:
    """
    Apply an approved alias while preserving historical prices.

    The old symbol row is updated in place, so its symbol_id and all
    linked daily_prices records remain intact.
    """

    old_symbol = alias["old_nse_symbol"]
    new_symbol = alias["new_nse_symbol"]
    new_yahoo = alias["new_yahoo_symbol"]

    old_row = connection.execute(
        """
        SELECT *
        FROM symbols
        WHERE nse_symbol = ?
        """,
        (old_symbol,),
    ).fetchone()

    if not old_row:
        return f"{old_symbol}: old symbol not found"

    existing_new = connection.execute(
        """
        SELECT symbol_id
        FROM symbols
        WHERE nse_symbol = ?
          AND symbol_id <> ?
        """,
        (new_symbol, old_row["symbol_id"]),
    ).fetchone()

    if existing_new:
        return (
            f"{old_symbol}: replacement {new_symbol} "
            f"already exists; manual merge required"
        )

    connection.execute(
        """
        UPDATE symbols
        SET nse_symbol = ?,
            yahoo_symbol = ?,
            source = ?,
            last_updated = ?
        WHERE symbol_id = ?
        """,
        (
            new_symbol,
            new_yahoo,
            f"Alias from {old_symbol}",
            datetime.now().isoformat(timespec="seconds"),
            old_row["symbol_id"],
        ),
    )

    connection.execute(
        """
        UPDATE symbol_aliases
        SET alias_status = 'APPLIED',
            applied_at = ?,
            updated_at = ?
        WHERE alias_id = ?
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            datetime.now().isoformat(timespec="seconds"),
            alias["alias_id"],
        ),
    )

    return f"{old_symbol} -> {new_symbol}: applied"


def apply_approved_aliases() -> list[str]:
    setup_resolver_tables()
    messages: list[str] = []

    with connect() as connection:
        aliases = connection.execute(
            """
            SELECT *
            FROM symbol_aliases
            WHERE alias_status = 'APPROVED'
            ORDER BY old_nse_symbol
            """
        ).fetchall()

        for alias in aliases:
            messages.append(
                apply_one_alias(connection, alias)
            )

        connection.commit()

    return messages


def mark_inactive(symbol: str, reason: str) -> bool:
    nse_symbol = normalize_nse_symbol(symbol)
    now = datetime.now().isoformat(timespec="seconds")

    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE symbols
            SET active = 0,
                source = ?,
                last_updated = ?
            WHERE nse_symbol = ?
            """,
            (
                f"Inactive: {reason}",
                now,
                nse_symbol,
            ),
        )
        connection.commit()

    return cursor.rowcount > 0


# ============================================================
# REPORTING
# ============================================================

def latest_validation_rows(
    failed_only: bool = False,
) -> list[dict]:
    setup_resolver_tables()

    status_filter = (
        "AND latest.validation_status <> 'VALID'"
        if failed_only
        else ""
    )

    query = f"""
        SELECT
            s.symbol_id,
            s.nse_symbol,
            s.yahoo_symbol,
            s.company_name,
            s.active,
            latest.checked_at,
            latest.validation_status,
            latest.latest_market_date,
            latest.rows_received,
            latest.error_message
        FROM symbols s
        LEFT JOIN symbol_validation_log latest
            ON latest.validation_id = (
                SELECT validation_id
                FROM symbol_validation_log v
                WHERE v.symbol_id = s.symbol_id
                ORDER BY checked_at DESC, validation_id DESC
                LIMIT 1
            )
        WHERE 1 = 1
        {status_filter}
        ORDER BY
            CASE latest.validation_status
                WHEN 'ERROR' THEN 1
                WHEN 'NO_DATA' THEN 2
                WHEN 'VALID' THEN 3
                ELSE 4
            END,
            s.nse_symbol
    """

    with connect() as connection:
        rows = connection.execute(query).fetchall()

    return [dict(row) for row in rows]


def show_failed() -> None:
    rows = latest_validation_rows(failed_only=True)

    print("\nAQSD FAILED / UNRESOLVED SYMBOLS")
    print("=" * 100)

    if not rows:
        print("No failed symbols in the latest validation results.")
        return

    print(
        f"{'NSE':<18}"
        f"{'Yahoo':<23}"
        f"{'Status':<12}"
        f"{'Last market date':<18}"
        f"Error"
    )
    print("-" * 100)

    for row in rows:
        print(
            f"{row['nse_symbol']:<18}"
            f"{row['yahoo_symbol']:<23}"
            f"{str(row['validation_status'] or 'NOT CHECKED'):<12}"
            f"{str(row['latest_market_date'] or ''):<18}"
            f"{str(row['error_message'] or '')[:40]}"
        )


def show_aliases() -> None:
    setup_resolver_tables()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM symbol_aliases
            ORDER BY
                CASE alias_status
                    WHEN 'PENDING' THEN 1
                    WHEN 'APPROVED' THEN 2
                    WHEN 'APPLIED' THEN 3
                    ELSE 4
                END,
                old_nse_symbol
            """
        ).fetchall()

    print("\nAQSD SYMBOL ALIASES")
    print("=" * 100)

    if not rows:
        print("No aliases recorded.")
        return

    print(
        f"{'Old Symbol':<18}"
        f"{'New Symbol':<18}"
        f"{'Status':<12}"
        f"{'Reason'}"
    )
    print("-" * 100)

    for row in rows:
        print(
            f"{row['old_nse_symbol']:<18}"
            f"{str(row['new_nse_symbol'] or ''):<18}"
            f"{row['alias_status']:<12}"
            f"{str(row['reason'] or '')[:50]}"
        )


def export_report() -> Path:
    rows = latest_validation_rows(failed_only=False)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    path = (
        REPORT_DIR
        / (
            "symbol_validation_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".csv"
        )
    )

    fields = [
        "symbol_id",
        "nse_symbol",
        "yahoo_symbol",
        "company_name",
        "active",
        "checked_at",
        "validation_status",
        "latest_market_date",
        "rows_received",
        "error_message",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in fields
                }
            )

    return path


def show_status() -> None:
    setup_resolver_tables()

    with connect() as connection:
        symbol_counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN active = 0 THEN 1 ELSE 0 END) AS inactive
            FROM symbols
            """
        ).fetchone()

        alias_counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN alias_status = 'PENDING' THEN 1 ELSE 0 END)
                    AS pending,
                SUM(CASE WHEN alias_status = 'APPROVED' THEN 1 ELSE 0 END)
                    AS approved,
                SUM(CASE WHEN alias_status = 'APPLIED' THEN 1 ELSE 0 END)
                    AS applied
            FROM symbol_aliases
            """
        ).fetchone()

        validation_counts = connection.execute(
            """
            SELECT
                COUNT(*) AS checks,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END)
                    AS valid,
                SUM(CASE WHEN validation_status = 'NO_DATA' THEN 1 ELSE 0 END)
                    AS no_data,
                SUM(CASE WHEN validation_status = 'ERROR' THEN 1 ELSE 0 END)
                    AS errors
            FROM symbol_validation_log
            """
        ).fetchone()

    print("\nAQSD SYMBOL RESOLVER STATUS")
    print("=" * 72)
    print(f"Total symbols:          {symbol_counts['total'] or 0}")
    print(f"Active symbols:         {symbol_counts['active'] or 0}")
    print(f"Inactive symbols:       {symbol_counts['inactive'] or 0}")
    print("-" * 72)
    print(f"Aliases total:          {alias_counts['total'] or 0}")
    print(f"Aliases pending:        {alias_counts['pending'] or 0}")
    print(f"Aliases approved:       {alias_counts['approved'] or 0}")
    print(f"Aliases applied:        {alias_counts['applied'] or 0}")
    print("-" * 72)
    print(f"Validation checks:      {validation_counts['checks'] or 0}")
    print(f"Valid results:          {validation_counts['valid'] or 0}")
    print(f"No-data results:        {validation_counts['no_data'] or 0}")
    print(f"Error results:          {validation_counts['errors'] or 0}")
    print("=" * 72)


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and validate AQSD market symbols."
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create resolver database tables.",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate active Yahoo symbols.",
    )

    parser.add_argument(
        "--period",
        default=DEFAULT_PERIOD,
        help="Short Yahoo validation period, e.g. 5d or 1mo.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum symbols. Use 0 for all.",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE,
        help="Pause between validation requests.",
    )

    parser.add_argument(
        "--failed",
        action="store_true",
        help="Show unresolved symbols from latest checks.",
    )

    parser.add_argument(
        "--aliases",
        action="store_true",
        help="Show alias records.",
    )

    parser.add_argument(
        "--add-alias",
        nargs=2,
        metavar=("OLD_SYMBOL", "NEW_SYMBOL"),
        help="Create or replace a pending alias.",
    )

    parser.add_argument(
        "--reason",
        default="",
        help="Reason for alias, rejection or inactivation.",
    )

    parser.add_argument(
        "--source",
        default="Manual review",
        help="Source supporting an alias.",
    )

    parser.add_argument(
        "--approve",
        metavar="OLD_SYMBOL",
        help="Approve one pending alias.",
    )

    parser.add_argument(
        "--reject",
        metavar="OLD_SYMBOL",
        help="Reject one alias.",
    )

    parser.add_argument(
        "--apply-approved",
        action="store_true",
        help="Apply all explicitly approved aliases.",
    )

    parser.add_argument(
        "--mark-inactive",
        metavar="SYMBOL",
        help="Deactivate an obsolete symbol without deleting history.",
    )

    parser.add_argument(
        "--export-report",
        action="store_true",
        help="Export latest validation results to CSV.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show resolver statistics.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    setup_resolver_tables()

    if args.setup:
        print("AQSD Symbol Resolver tables created successfully.")
        return

    if args.validate:
        valid, no_data, errors = validate_symbols(
            period=args.period,
            limit=args.limit,
            pause=args.pause,
        )

        print("=" * 78)
        print(f"Valid symbols:    {valid}")
        print(f"No-data symbols:  {no_data}")
        print(f"Errors:           {errors}")
        return

    if args.failed:
        show_failed()
        return

    if args.aliases:
        show_aliases()
        return

    if args.add_alias:
        old_symbol, new_symbol = args.add_alias

        add_alias(
            old_symbol,
            new_symbol,
            reason=args.reason,
            source=args.source,
        )

        print(
            f"Pending alias saved: "
            f"{normalize_nse_symbol(old_symbol)} -> "
            f"{normalize_nse_symbol(new_symbol)}"
        )
        print("Review and approve it before applying.")
        return

    if args.approve:
        changed = approve_alias(args.approve)
        print(
            "Alias approved."
            if changed
            else "Alias not found."
        )
        return

    if args.reject:
        changed = reject_alias(
            args.reject,
            args.reason,
        )
        print(
            "Alias rejected."
            if changed
            else "Alias not found."
        )
        return

    if args.apply_approved:
        messages = apply_approved_aliases()

        if not messages:
            print("No approved aliases waiting to be applied.")
        else:
            for message in messages:
                print(message)

        return

    if args.mark_inactive:
        changed = mark_inactive(
            args.mark_inactive,
            args.reason or "Manual review",
        )

        print(
            "Symbol marked inactive."
            if changed
            else "Symbol not found."
        )
        return

    if args.export_report:
        path = export_report()
        print(f"Report created:\n{path}")
        return

    show_status()


if __name__ == "__main__":
    main()
