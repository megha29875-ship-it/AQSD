
"""
AQSD Core
Module: Price Cache
Version: 1.0

Downloads daily OHLCV data once and stores it in:

    AQSD/Data/aqsd_core.db

Uses symbols from the AQSD Symbol Master.

Commands
--------
python aqsd_price_cache.py --update
python aqsd_price_cache.py --update --period 10y
python aqsd_price_cache.py --symbol RELIANCE.NS --period 5y
python aqsd_price_cache.py --status
python aqsd_price_cache.py --stale
python aqsd_price_cache.py --export RELIANCE.NS
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
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
DATA_DIR = BASE_DIR / "Data"
EXPORT_DIR = DATA_DIR / "Price_Exports"


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_PERIOD = "10y"
DEFAULT_BATCH_SIZE = 40
DEFAULT_PAUSE_SECONDS = 1.5
DEFAULT_STALE_DAYS = 5


# ============================================================
# SYMBOL HELPERS
# ============================================================

def normalize_yahoo_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        return ""

    if symbol.endswith(".NS"):
        return symbol

    return f"{symbol}.NS"


def get_active_symbols(
    limit: int = 0,
) -> list[dict]:
    setup_database()

    query = """
        SELECT symbol_id, nse_symbol, yahoo_symbol
        FROM symbols
        WHERE active = 1
        ORDER BY nse_symbol
    """

    if limit > 0:
        query += " LIMIT ?"

    with connect() as connection:
        rows = connection.execute(
            query,
            (limit,) if limit > 0 else (),
        ).fetchall()

    return [dict(row) for row in rows]


def get_symbol_record(symbol: str) -> dict | None:
    setup_database()

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
            (
                yahoo_symbol,
                nse_symbol,
            ),
        ).fetchone()

    return dict(row) if row else None


# ============================================================
# DATA DOWNLOAD
# ============================================================

def flatten_yfinance_frame(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    frame = frame.rename(
        columns={
            "Adj Close": "Adjusted Close",
        }
    )

    required = ["Open", "High", "Low", "Close", "Volume"]

    missing = [
        column
        for column in required
        if column not in frame.columns
    ]

    if missing:
        raise RuntimeError(
            "Missing columns: " + ", ".join(missing)
        )

    if "Adjusted Close" not in frame.columns:
        frame["Adjusted Close"] = frame["Close"]

    output = frame[
        [
            "Open",
            "High",
            "Low",
            "Close",
            "Adjusted Close",
            "Volume",
        ]
    ].copy()

    output = output.dropna(
        subset=["Open", "High", "Low", "Close"]
    )

    output.index = pd.to_datetime(output.index)

    return output


def download_symbol_history(
    yahoo_symbol: str,
    period: str,
) -> pd.DataFrame:
    frame = yf.download(
        yahoo_symbol,
        period=period,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )

    if frame.empty:
        raise RuntimeError("No data downloaded")

    return flatten_yfinance_frame(frame)


# ============================================================
# DATABASE WRITE
# ============================================================

def upsert_prices(
    connection: sqlite3.Connection,
    symbol_id: int,
    frame: pd.DataFrame,
    source: str = "Yahoo Finance",
) -> int:
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
                float(row["Adjusted Close"]),
                float(row["Volume"] or 0),
                source,
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


def update_one_symbol(
    symbol_record: dict,
    period: str,
) -> int:
    frame = download_symbol_history(
        symbol_record["yahoo_symbol"],
        period,
    )

    with connect() as connection:
        count = upsert_prices(
            connection,
            symbol_record["symbol_id"],
            frame,
        )
        connection.commit()

    return count


# ============================================================
# CACHE UPDATE
# ============================================================

def update_cache(
    period: str,
    limit: int,
    pause_seconds: float,
) -> tuple[int, int, int]:
    symbols = get_active_symbols(limit)

    if not symbols:
        raise RuntimeError(
            "Symbol Master is empty. Run "
            "'python aqsd_symbol_master.py --import' first."
        )

    run_id = start_run(
        "aqsd_price_cache",
        (
            f"Updating {len(symbols)} symbols "
            f"for period {period}"
        ),
    )

    completed = 0
    failed = 0
    price_rows = 0

    try:
        print("\nAQSD PRICE CACHE")
        print("=" * 72)
        print(f"Symbols: {len(symbols)}")
        print(f"Period: {period}")

        for index, symbol in enumerate(symbols, start=1):
            yahoo_symbol = symbol["yahoo_symbol"]

            print(
                f"[{index}/{len(symbols)}] "
                f"{yahoo_symbol}",
                end="",
            )

            try:
                count = update_one_symbol(
                    symbol,
                    period,
                )

                completed += 1
                price_rows += count
                print(f"  OK ({count} rows)")

            except Exception as error:
                failed += 1
                print(f"  FAILED: {error}")

            if (
                pause_seconds > 0
                and index < len(symbols)
            ):
                time.sleep(pause_seconds)

        finish_run(
            run_id,
            status=(
                "SUCCESS"
                if failed == 0
                else "PARTIAL"
            ),
            records_processed=price_rows,
            errors_count=failed,
            message=(
                f"Symbols completed: {completed}; "
                f"failed: {failed}"
            ),
        )

        return completed, failed, price_rows

    except Exception as error:
        finish_run(
            run_id,
            status="FAILED",
            records_processed=price_rows,
            errors_count=failed + 1,
            message=str(error),
        )
        raise


# ============================================================
# STATUS / HEALTH
# ============================================================

def cache_status() -> dict:
    setup_database()

    with connect() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(DISTINCT symbol_id) AS symbols_with_prices,
                COUNT(*) AS price_rows,
                MIN(trade_date) AS first_date,
                MAX(trade_date) AS latest_date
            FROM daily_prices
            """
        ).fetchone()

        total_symbols = connection.execute(
            """
            SELECT COUNT(*)
            FROM symbols
            WHERE active = 1
            """
        ).fetchone()[0]

        missing = connection.execute(
            """
            SELECT s.nse_symbol, s.yahoo_symbol
            FROM symbols s
            LEFT JOIN daily_prices p
                ON p.symbol_id = s.symbol_id
            WHERE s.active = 1
            GROUP BY s.symbol_id
            HAVING COUNT(p.price_id) = 0
            ORDER BY s.nse_symbol
            """
        ).fetchall()

    return {
        "active_symbols": int(total_symbols or 0),
        "symbols_with_prices": int(
            summary["symbols_with_prices"] or 0
        ),
        "price_rows": int(summary["price_rows"] or 0),
        "first_date": summary["first_date"] or "No data",
        "latest_date": summary["latest_date"] or "No data",
        "missing": [dict(row) for row in missing],
    }


def show_status() -> None:
    status = cache_status()

    print("\nAQSD PRICE CACHE STATUS")
    print("=" * 72)
    print(f"Active symbols:       {status['active_symbols']}")
    print(
        f"Symbols with prices:  "
        f"{status['symbols_with_prices']}"
    )
    print(f"Price rows:           {status['price_rows']}")
    print(f"First price date:     {status['first_date']}")
    print(f"Latest price date:    {status['latest_date']}")
    print(
        f"Symbols without data: "
        f"{len(status['missing'])}"
    )

    if status["missing"]:
        print("-" * 72)

        for row in status["missing"][:25]:
            print(
                f"{row['nse_symbol']:<18}"
                f"{row['yahoo_symbol']}"
            )

        if len(status["missing"]) > 25:
            print(
                f"... and "
                f"{len(status['missing']) - 25} more"
            )

    print("=" * 72)


def stale_symbols(
    stale_days: int,
) -> list[dict]:
    setup_database()

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


def show_stale_symbols(
    stale_days: int,
) -> None:
    rows = stale_symbols(stale_days)

    print("\nAQSD STALE PRICE DATA")
    print("=" * 72)
    print(f"Stale threshold: {stale_days} calendar days")
    print(f"Stale symbols: {len(rows)}")
    print("-" * 72)

    for row in rows:
        print(
            f"{row['nse_symbol']:<18}"
            f"{row['latest_date'] or 'NO DATA'}"
        )

    print("=" * 72)


# ============================================================
# READ API
# These functions will be used by future AQSD engines.
# ============================================================

def get_history(
    symbol: str,
    rows: int = 250,
) -> pd.DataFrame:
    record = get_symbol_record(symbol)

    if not record:
        raise ValueError(f"Unknown symbol: {symbol}")

    with connect() as connection:
        data = connection.execute(
            """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                adjusted_close,
                volume
            FROM daily_prices
            WHERE symbol_id = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (
                record["symbol_id"],
                rows,
            ),
        ).fetchall()

    if not data:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [dict(row) for row in data]
    )

    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"]
    )

    frame = frame.sort_values(
        "trade_date"
    ).set_index("trade_date")

    return frame


def get_last_price(symbol: str) -> dict | None:
    record = get_symbol_record(symbol)

    if not record:
        return None

    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                adjusted_close,
                volume
            FROM daily_prices
            WHERE symbol_id = ?
            ORDER BY trade_date DESC
            LIMIT 1
            """,
            (record["symbol_id"],),
        ).fetchone()

    return dict(row) if row else None


# ============================================================
# EXPORT
# ============================================================

def export_symbol_history(
    symbol: str,
    rows: int = 0,
) -> Path:
    record = get_symbol_record(symbol)

    if not record:
        raise ValueError(f"Unknown symbol: {symbol}")

    query = """
        SELECT
            trade_date,
            open,
            high,
            low,
            close,
            adjusted_close,
            volume,
            source,
            downloaded_at
        FROM daily_prices
        WHERE symbol_id = ?
        ORDER BY trade_date
    """

    parameters: list[object] = [
        record["symbol_id"]
    ]

    if rows > 0:
        query = """
            SELECT *
            FROM (
                SELECT
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    adjusted_close,
                    volume,
                    source,
                    downloaded_at
                FROM daily_prices
                WHERE symbol_id = ?
                ORDER BY trade_date DESC
                LIMIT ?
            )
            ORDER BY trade_date
        """
        parameters.append(rows)

    with connect() as connection:
        frame = pd.read_sql_query(
            query,
            connection,
            params=parameters,
        )

    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        EXPORT_DIR
        / f"{record['nse_symbol']}_history.csv"
    )

    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    return path


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage the AQSD Core daily price cache."
    )

    parser.add_argument(
        "--update",
        action="store_true",
        help="Update price data for active symbols.",
    )

    parser.add_argument(
        "--symbol",
        metavar="SYMBOL",
        help="Update one NSE or Yahoo symbol.",
    )

    parser.add_argument(
        "--period",
        default=DEFAULT_PERIOD,
        help="Yahoo Finance period, e.g. 1y, 5y, 10y.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of symbols. Use 0 for all.",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE_SECONDS,
        help="Pause between symbol requests in seconds.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show cache statistics.",
    )

    parser.add_argument(
        "--stale",
        action="store_true",
        help="List stale or missing price data.",
    )

    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help="Calendar days used by --stale.",
    )

    parser.add_argument(
        "--export",
        metavar="SYMBOL",
        help="Export one symbol's cached history to CSV.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=0,
        help="Maximum rows for --export. Use 0 for all.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    setup_database()

    if args.status:
        show_status()
        return

    if args.stale:
        show_stale_symbols(args.stale_days)
        return

    if args.export:
        path = export_symbol_history(
            args.export,
            args.rows,
        )

        print(f"Export created:\n{path}")
        return

    if args.symbol:
        record = get_symbol_record(args.symbol)

        if not record:
            raise RuntimeError(
                f"Symbol not found in Symbol Master: "
                f"{args.symbol}"
            )

        print("\nAQSD PRICE CACHE - SINGLE SYMBOL")
        print("=" * 72)
        print(f"Symbol: {record['yahoo_symbol']}")
        print(f"Period: {args.period}")

        count = update_one_symbol(
            record,
            args.period,
        )

        print(f"Rows stored: {count}")
        print("=" * 72)
        return

    if args.update:
        completed, failed, rows = update_cache(
            period=args.period,
            limit=args.limit,
            pause_seconds=args.pause,
        )

        print("=" * 72)
        print(f"Symbols completed: {completed}")
        print(f"Symbols failed:    {failed}")
        print(f"Rows stored:       {rows}")
        print("=" * 72)
        return

    show_status()


if __name__ == "__main__":
    main()
