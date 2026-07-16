
"""
AQSD Core
Module: Incremental Price Updater
Version: 1.0

Updates only the missing daily OHLCV data for symbols already stored
in AQSD/Data/aqsd_core.db.

Commands
--------
python aqsd_incremental_updater.py --update
python aqsd_incremental_updater.py --update --limit 20
python aqsd_incremental_updater.py --symbol RELIANCE.NS
python aqsd_incremental_updater.py --status
python aqsd_incremental_updater.py --repair-missing
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from aqsd_database import connect, setup_database, start_run, finish_run


# ============================================================
# PATHS / SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "Data" / "aqsd_core.db"

DEFAULT_LOOKBACK_DAYS = 10
DEFAULT_PAUSE_SECONDS = 0.6
DEFAULT_STALE_DAYS = 5


# ============================================================
# SYMBOL HELPERS
# ============================================================

def normalize_yahoo_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        return ""

    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def get_active_symbols(limit: int = 0) -> list[dict]:
    setup_database()

    query = """
        SELECT symbol_id, nse_symbol, yahoo_symbol
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
    yahoo_symbol = normalize_yahoo_symbol(symbol)
    nse_symbol = yahoo_symbol.removesuffix(".NS")

    with connect() as connection:
        row = connection.execute(
            """
            SELECT symbol_id, nse_symbol, yahoo_symbol
            FROM symbols
            WHERE yahoo_symbol = ?
               OR nse_symbol = ?
            LIMIT 1
            """,
            (yahoo_symbol, nse_symbol),
        ).fetchone()

    return dict(row) if row else None


# ============================================================
# DATE / CACHE HELPERS
# ============================================================

def latest_cached_date(symbol_id: int) -> date | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT MAX(trade_date) AS latest_date
            FROM daily_prices
            WHERE symbol_id = ?
            """,
            (symbol_id,),
        ).fetchone()

    if not row or not row["latest_date"]:
        return None

    return datetime.strptime(
        row["latest_date"],
        "%Y-%m-%d",
    ).date()


def calculate_download_start(
    latest_date: date | None,
    fallback_days: int,
) -> date:
    if latest_date is None:
        return date.today() - timedelta(days=fallback_days)

    # overlap a few days to safely repair revised/missed records
    return latest_date - timedelta(days=3)


def flatten_yfinance_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    if "Adj Close" not in frame.columns:
        frame["Adj Close"] = frame["Close"]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    missing = [
        column
        for column in required
        if column not in frame.columns
    ]

    if missing:
        raise RuntimeError(
            "Missing columns: " + ", ".join(missing)
        )

    output = frame[required].copy()
    output = output.dropna(
        subset=["Open", "High", "Low", "Close"]
    )
    output.index = pd.to_datetime(output.index)

    return output


# ============================================================
# DOWNLOAD / STORE
# ============================================================

def download_incremental(
    yahoo_symbol: str,
    start_date: date,
) -> pd.DataFrame:
    end_date = date.today() + timedelta(days=1)

    frame = yf.download(
        yahoo_symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )

    if frame.empty:
        return pd.DataFrame()

    return flatten_yfinance_frame(frame)


def upsert_prices(
    connection: sqlite3.Connection,
    symbol_id: int,
    frame: pd.DataFrame,
) -> int:
    if frame.empty:
        return 0

    downloaded_at = datetime.now().isoformat(
        timespec="seconds"
    )

    rows = []

    for index, row in frame.iterrows():
        rows.append(
            (
                symbol_id,
                index.date().isoformat(),
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                float(row["Adj Close"]),
                float(row["Volume"] or 0),
                "Yahoo Finance",
                downloaded_at,
            )
        )

    connection.executemany(
        """
        INSERT INTO daily_prices(
            symbol_id,
            trade_date,
            open,
            high,
            low,
            close,
            adjusted_close,
            volume,
            source,
            downloaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol_id, trade_date)
        DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            adjusted_close = excluded.adjusted_close,
            volume = excluded.volume,
            source = excluded.source,
            downloaded_at = excluded.downloaded_at
        """,
        rows,
    )

    return len(rows)


def update_symbol(
    record: dict,
    fallback_days: int,
) -> tuple[int, str]:
    latest = latest_cached_date(record["symbol_id"])
    start_date = calculate_download_start(
        latest,
        fallback_days,
    )

    frame = download_incremental(
        record["yahoo_symbol"],
        start_date,
    )

    if frame.empty:
        return 0, "NO NEW DATA"

    with connect() as connection:
        count = upsert_prices(
            connection,
            record["symbol_id"],
            frame,
        )
        connection.commit()

    newest = frame.index.max().date().isoformat()

    return count, newest


# ============================================================
# BULK UPDATE
# ============================================================

def update_all(
    limit: int,
    pause_seconds: float,
    fallback_days: int,
) -> tuple[int, int, int]:
    symbols = get_active_symbols(limit)

    if not symbols:
        raise RuntimeError(
            "No active symbols found. "
            "Run aqsd_symbol_master.py --import first."
        )

    run_id = start_run(
        "aqsd_incremental_updater",
        f"Incremental update for {len(symbols)} symbols",
    )

    completed = 0
    failed = 0
    rows_stored = 0

    try:
        print("\nAQSD INCREMENTAL PRICE UPDATER")
        print("=" * 72)
        print(f"Symbols: {len(symbols)}")

        for index, record in enumerate(symbols, start=1):
            print(
                f"[{index}/{len(symbols)}] "
                f"{record['yahoo_symbol']}",
                end="",
            )

            try:
                count, newest = update_symbol(
                    record,
                    fallback_days,
                )

                completed += 1
                rows_stored += count
                print(f"  OK ({count} rows, latest {newest})")

            except Exception as error:
                failed += 1
                print(f"  FAILED: {error}")

            if pause_seconds > 0 and index < len(symbols):
                time.sleep(pause_seconds)

        finish_run(
            run_id,
            status="SUCCESS" if failed == 0 else "PARTIAL",
            records_processed=rows_stored,
            errors_count=failed,
            message=(
                f"Symbols completed: {completed}; "
                f"failed: {failed}"
            ),
        )

        return completed, failed, rows_stored

    except Exception as error:
        finish_run(
            run_id,
            status="FAILED",
            records_processed=rows_stored,
            errors_count=failed + 1,
            message=str(error),
        )
        raise


# ============================================================
# STATUS / REPAIR
# ============================================================

def stale_symbols(stale_days: int) -> list[dict]:
    cutoff = (
        date.today() - timedelta(days=stale_days)
    ).isoformat()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                s.symbol_id,
                s.nse_symbol,
                s.yahoo_symbol,
                MAX(p.trade_date) AS latest_date
            FROM symbols s
            LEFT JOIN daily_prices p
                ON p.symbol_id = s.symbol_id
            WHERE s.active = 1
            GROUP BY
                s.symbol_id,
                s.nse_symbol,
                s.yahoo_symbol
            HAVING latest_date IS NULL
                OR latest_date < ?
            ORDER BY latest_date, s.nse_symbol
            """,
            (cutoff,),
        ).fetchall()

    return [dict(row) for row in rows]


def show_status(stale_days: int) -> None:
    rows = stale_symbols(stale_days)

    with connect() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS rows_count,
                COUNT(DISTINCT symbol_id) AS symbol_count,
                MIN(trade_date) AS first_date,
                MAX(trade_date) AS latest_date
            FROM daily_prices
            """
        ).fetchone()

    print("\nAQSD INCREMENTAL UPDATE STATUS")
    print("=" * 72)
    print(f"Cached symbols:       {summary['symbol_count'] or 0}")
    print(f"Cached rows:          {summary['rows_count'] or 0}")
    print(f"First cached date:    {summary['first_date'] or 'No data'}")
    print(f"Latest cached date:   {summary['latest_date'] or 'No data'}")
    print(f"Stale symbols:        {len(rows)}")
    print("-" * 72)

    for item in rows[:30]:
        print(
            f"{item['nse_symbol']:<18}"
            f"{item['latest_date'] or 'NO DATA'}"
        )

    if len(rows) > 30:
        print(f"... and {len(rows) - 30} more")

    print("=" * 72)


def repair_missing(
    pause_seconds: float,
    fallback_days: int,
) -> tuple[int, int, int]:
    rows = stale_symbols(stale_days=36500)

    if not rows:
        print("No missing-price symbols found.")
        return 0, 0, 0

    completed = 0
    failed = 0
    stored = 0

    print("\nAQSD REPAIR MISSING PRICE DATA")
    print("=" * 72)

    for index, record in enumerate(rows, start=1):
        print(
            f"[{index}/{len(rows)}] "
            f"{record['yahoo_symbol']}",
            end="",
        )

        try:
            count, newest = update_symbol(
                record,
                fallback_days,
            )
            completed += 1
            stored += count
            print(f"  OK ({count} rows, latest {newest})")

        except Exception as error:
            failed += 1
            print(f"  FAILED: {error}")

        if pause_seconds > 0 and index < len(rows):
            time.sleep(pause_seconds)

    return completed, failed, stored


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally update AQSD cached prices."
    )

    parser.add_argument(
        "--update",
        action="store_true",
        help="Update all active symbols incrementally.",
    )

    parser.add_argument(
        "--symbol",
        metavar="SYMBOL",
        help="Update a single NSE/Yahoo symbol.",
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
        default=DEFAULT_PAUSE_SECONDS,
        help="Pause between Yahoo requests.",
    )

    parser.add_argument(
        "--fallback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="History requested when a symbol has no cache.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show cache freshness and stale symbols.",
    )

    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help="Calendar days defining stale data.",
    )

    parser.add_argument(
        "--repair-missing",
        action="store_true",
        help="Retry symbols with no cached data.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    setup_database()

    if args.status:
        show_status(args.stale_days)
        return

    if args.repair_missing:
        completed, failed, stored = repair_missing(
            pause_seconds=args.pause,
            fallback_days=max(args.fallback_days, 3650),
        )

        print("=" * 72)
        print(f"Symbols completed: {completed}")
        print(f"Symbols failed:    {failed}")
        print(f"Rows stored:       {stored}")
        return

    if args.symbol:
        record = get_symbol_record(args.symbol)

        if not record:
            raise RuntimeError(
                f"Symbol not found in Symbol Master: "
                f"{args.symbol}"
            )

        count, newest = update_symbol(
            record,
            args.fallback_days,
        )

        print("\nAQSD SINGLE-SYMBOL UPDATE")
        print("=" * 72)
        print(f"Symbol: {record['yahoo_symbol']}")
        print(f"Rows stored: {count}")
        print(f"Latest date: {newest}")
        return

    if args.update:
        completed, failed, stored = update_all(
            limit=args.limit,
            pause_seconds=args.pause,
            fallback_days=args.fallback_days,
        )

        print("=" * 72)
        print(f"Symbols completed: {completed}")
        print(f"Symbols failed:    {failed}")
        print(f"Rows stored:       {stored}")
        return

    show_status(args.stale_days)


if __name__ == "__main__":
    main()
