"""
AQSD
Historical Source Adapter

Module : HSA-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Build date-specific historical source files required by the
AQSD Market History Backfill Engine.

Phase 1
-------
Market Structure historical source.

For every historical trading session AQSD stores an OHLCV window
ending exactly on that session:

Data/Historical/YYYY-MM-DD/market_structure.csv

CRITICAL RULE
-------------
A historical date must NEVER receive market information from a
future date.

For example:

Data/Historical/2026-06-15/market_structure.csv

may contain candles up to 2026-06-15 only.

It must never contain a 2026-06-16 or later candle.

This module does NOT fabricate:
- Participant data
- Options data
- Futures data
- Sector data
- Breadth data

Those sources will be connected separately.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
from fyers_apiv3 import fyersModel


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "HSA-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DATA_DIR: Final[Path] = BASE_DIR / "Data"
OUTPUT_DIR: Final[Path] = BASE_DIR / "Output"

CONFIG_FILE: Final[Path] = (
    DATA_DIR
    / "fyers_config.env"
)

TRADING_CALENDAR_FILE: Final[Path] = (
    DATA_DIR
    / "NSE_Trading_Calendar.csv"
)

HISTORICAL_ROOT: Final[Path] = (
    DATA_DIR
    / "Historical"
)

AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "Historical_Source_Adapter_Audit.csv"
)

SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "Historical_Source_Adapter_Summary.json"
)

DEFAULT_SYMBOL: Final[str] = (
    "NSE:NIFTYBANK-INDEX"
)

DEFAULT_SESSIONS: Final[int] = 60

# Market Structure requires enough historical bars for
# EMA200 and structural analysis.
DEFAULT_WINDOW_SESSIONS: Final[int] = 250

# Extra history requested from FYERS to ensure enough
# valid trading candles remain after holidays/weekends.
DOWNLOAD_BUFFER_DAYS: Final[int] = 500


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
    Create required AQSD directories.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    HISTORICAL_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# FYERS CONFIGURATION
# ==========================================================

def load_fyers_config() -> dict[str, str]:
    """
    Load FYERS credentials from AQSD's central configuration.

    Supported keys:

    FYERS_CLIENT_ID
    CLIENT_ID

    FYERS_ACCESS_TOKEN
    ACCESS_TOKEN
    """

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "FYERS configuration file not found:\n"
            f"{CONFIG_FILE}"
        )

    raw_config: dict[str, str] = {}

    for raw_line in CONFIG_FILE.read_text(
        encoding="utf-8",
    ).splitlines():

        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        raw_config[
            key.strip()
        ] = (
            value
            .strip()
            .strip('"')
            .strip("'")
        )

    client_id = (
        raw_config.get(
            "FYERS_CLIENT_ID"
        )
        or raw_config.get(
            "CLIENT_ID"
        )
        or ""
    )

    access_token = (
        raw_config.get(
            "FYERS_ACCESS_TOKEN"
        )
        or raw_config.get(
            "ACCESS_TOKEN"
        )
        or ""
    )

    missing: list[str] = []

    if not client_id:
        missing.append(
            "FYERS_CLIENT_ID"
        )

    if not access_token:
        missing.append(
            "FYERS_ACCESS_TOKEN"
        )

    if missing:
        raise RuntimeError(
            "Missing FYERS configuration values: "
            + ", ".join(
                missing
            )
        )

    return {
        "client_id": client_id,
        "access_token": access_token,
    }


def create_fyers_client() -> fyersModel.FyersModel:
    """
    Create authenticated FYERS client.
    """

    config = load_fyers_config()

    return fyersModel.FyersModel(
        client_id=config[
            "client_id"
        ],
        token=config[
            "access_token"
        ],
        is_async=False,
        log_path="",
    )


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

    calendar = load_trading_calendar()

    eligible = calendar.loc[
        calendar[
            "trade_date"
        ].dt.date
        <= end_date
    ].copy()

    if eligible.empty:
        raise RuntimeError(
            "No NSE trading sessions are available "
            f"on or before {end_date}."
        )

    sessions = max(
        1,
        int(
            sessions
        ),
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
# FYERS HISTORICAL DOWNLOAD
# ==========================================================

def download_daily_history(
    *,
    client: fyersModel.FyersModel,
    symbol: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Download daily historical candles from FYERS in smaller
    date chunks and combine them.

    Chunking avoids oversized History API requests and makes
    historical acquisition more reliable.
    """

    if end_date < start_date:
        raise ValueError(
            "Historical end_date cannot be before start_date."
        )

    chunk_days = 90

    frames: list[pd.DataFrame] = []

    chunk_start = start_date

    while chunk_start <= end_date:

        chunk_end = min(
            chunk_start
            + timedelta(
                days=chunk_days - 1
            ),
            end_date,
        )

        payload = {
            "symbol": symbol,
            "resolution": "D",
            "date_format": "1",
            "range_from": (
                chunk_start.isoformat()
            ),
            "range_to": (
                chunk_end.isoformat()
            ),
            "cont_flag": "1",
        }

        response = client.history(
            data=payload
        )

        if not isinstance(
            response,
            dict,
        ):
            raise RuntimeError(
                "FYERS history returned unexpected response "
                f"for {chunk_start} to {chunk_end}."
            )

        if response.get(
            "s"
        ) != "ok":
            raise RuntimeError(
                "FYERS history request failed "
                f"for {chunk_start} to {chunk_end}. "
                f"Code: {response.get('code')}; "
                f"Message: {response.get('message')}"
            )

        candles = response.get(
            "candles"
        )

        if candles:
            chunk_frame = pd.DataFrame(
                candles,
                columns=[
                    "timestamp",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                ],
            )

            frames.append(
                chunk_frame
            )

        chunk_start = (
            chunk_end
            + timedelta(
                days=1
            )
        )

    if not frames:
        raise RuntimeError(
            "FYERS returned no historical candles "
            f"for {symbol}."
        )

    frame = pd.concat(
        frames,
        ignore_index=True,
    )

    frame[
        "Date"
    ] = pd.to_datetime(
        frame[
            "timestamp"
        ],
        unit="s",
        errors="coerce",
    )

    frame = (
        frame
        .dropna(
            subset=[
                "Date"
            ]
        )
        .sort_values(
            "Date"
        )
        .drop_duplicates(
            subset=[
                "Date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    for column in (
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ):
        frame[
            column
        ] = pd.to_numeric(
            frame[
                column
            ],
            errors="coerce",
        )

    frame = frame.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    ).copy()

    return frame[
        [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    ]

# ==========================================================
# POINT-IN-TIME WINDOW
# ==========================================================

def build_point_in_time_window(
    *,
    full_history: pd.DataFrame,
    trade_date: date,
    window_sessions: int,
) -> pd.DataFrame:
    """
    Build historical OHLCV using data available on or before trade_date.

    No future candles can enter this result.
    """

    historical = full_history.loc[
        full_history[
            "Date"
        ].dt.date
        <= trade_date
    ].copy()

    if historical.empty:
        raise RuntimeError(
            f"No market history exists on or before {trade_date}."
        )

    historical = historical.tail(
        max(
            1,
            int(
                window_sessions
            ),
        )
    ).copy()

    latest_date = (
        historical[
            "Date"
        ]
        .iloc[-1]
        .date()
    )

    if latest_date > trade_date:
        raise RuntimeError(
            "POINT-IN-TIME VALIDATION FAILED: "
            "future market data entered historical window."
        )

    historical.insert(
        0,
        "Symbol",
        DEFAULT_SYMBOL,
    )

    historical[
        "Analysis_Date"
    ] = trade_date.isoformat()

    historical[
        "Source"
    ] = "FYERS HISTORICAL API"

    historical[
        "Point_In_Time_Validated"
    ] = True

    return historical


# ==========================================================
# SOURCE STORAGE
# ==========================================================

def source_directory(
    trade_date: date,
) -> Path:
    """
    Return one dated historical-source directory.
    """

    return (
        HISTORICAL_ROOT
        / trade_date.isoformat()
    )


def save_market_structure_source(
    *,
    trade_date: date,
    frame: pd.DataFrame,
    overwrite: bool,
) -> tuple[
    str,
    Path,
]:
    """
    Save date-specific Market Structure historical source.
    """

    directory = source_directory(
        trade_date
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        directory
        / "market_structure.csv"
    )

    if (
        output_file.exists()
        and not overwrite
    ):
        return (
            "SKIPPED EXISTING",
            output_file,
        )

    frame.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    manifest = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),
        "analysis_date": (
            trade_date.isoformat()
        ),
        "source_type": (
            "MARKET STRUCTURE OHLCV"
        ),
        "source_provider": "FYERS",
        "symbol": DEFAULT_SYMBOL,
        "rows": int(
            len(
                frame
            )
        ),
        "first_candle": (
            frame[
                "Date"
            ]
            .iloc[0]
            .date()
            .isoformat()
        ),
        "last_candle": (
            frame[
                "Date"
            ]
            .iloc[-1]
            .date()
            .isoformat()
        ),
        "point_in_time_validated": True,
        "created_at": (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        ),
        "file": str(
            output_file
        ),
    }

    (
        directory
        / "market_structure_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )

    return (
        "CREATED",
        output_file,
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
    Save historical source adapter audit.
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

def run_historical_source_adapter(
    *,
    sessions: int,
    end_date: date,
    symbol: str,
    window_sessions: int,
    overwrite: bool,
) -> dict[str, object]:
    """
    Build point-in-time Market Structure historical sources.
    """

    ensure_directories()

    target_dates = resolve_target_dates(
        sessions=sessions,
        end_date=end_date,
    )

    earliest_target = min(
        target_dates
    )

    download_start = (
        earliest_target
        - timedelta(
            days=DOWNLOAD_BUFFER_DAYS
        )
    )

    client = create_fyers_client()

    full_history = download_daily_history(
        client=client,
        symbol=symbol,
        start_date=download_start,
        end_date=end_date,
    )

    audit_rows: list[
        dict[str, object]
    ] = []

    created = 0
    skipped = 0
    failed = 0

    for trade_date in target_dates:
        try:
            frame = build_point_in_time_window(
                full_history=full_history,
                trade_date=trade_date,
                window_sessions=(
                    window_sessions
                ),
            )

            # Ensure requested symbol is written correctly.
            frame[
                "Symbol"
            ] = symbol

            (
                action,
                output_file,
            ) = save_market_structure_source(
                trade_date=trade_date,
                frame=frame,
                overwrite=overwrite,
            )

            if action == "CREATED":
                created += 1
            else:
                skipped += 1

            audit_rows.append(
                {
                    "trade_date": (
                        trade_date.isoformat()
                    ),
                    "status": "SUCCESS",
                    "action": action,
                    "rows": len(
                        frame
                    ),
                    "latest_candle": (
                        frame[
                            "Date"
                        ]
                        .iloc[-1]
                        .date()
                        .isoformat()
                    ),
                    "file": str(
                        output_file
                    ),
                    "message": (
                        "Point-in-time validation passed."
                    ),
                }
            )

        except Exception as exc:
            failed += 1

            audit_rows.append(
                {
                    "trade_date": (
                        trade_date.isoformat()
                    ),
                    "status": "FAILED",
                    "action": "NONE",
                    "rows": 0,
                    "latest_candle": "",
                    "file": "",
                    "message": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    audit_file = save_audit(
        audit_rows
    )

    summary = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),
        "symbol": symbol,
        "requested_sessions": (
            sessions
        ),
        "resolved_sessions": len(
            target_dates
        ),
        "end_date": (
            end_date.isoformat()
        ),
        "window_sessions": (
            window_sessions
        ),
        "download_start": (
            download_start.isoformat()
        ),
        "downloaded_candles": len(
            full_history
        ),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "historical_root": str(
            HISTORICAL_ROOT
        ),
        "audit_file": str(
            audit_file
        ),
        "status": (
            "SUCCESS"
            if failed == 0
            else "SUCCESS WITH FAILURES"
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
    Display Historical Source Adapter summary.
    """

    print()
    print("=" * 100)
    print("AQSD HISTORICAL SOURCE ADAPTER")
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
        f"Symbol                    : "
        f"{summary['symbol']}"
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
        f"End Date                  : "
        f"{summary['end_date']}"
    )

    print(
        f"Historical Window         : "
        f"{summary['window_sessions']} sessions"
    )

    print("-" * 100)

    print("MARKET STRUCTURE HISTORICAL SOURCES")
    print("-" * 100)

    print(
        f"FYERS Candles Downloaded  : "
        f"{summary['downloaded_candles']}"
    )

    print(
        f"Created                   : "
        f"{summary['created']}"
    )

    print(
        f"Skipped Existing          : "
        f"{summary['skipped']}"
    )

    print(
        f"Failed                    : "
        f"{summary['failed']}"
    )

    print("-" * 100)

    print(
        f"Historical Source Root    : "
        f"{summary['historical_root']}"
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
        "Safety                    : "
        "POINT-IN-TIME VALIDATION ENABLED"
    )

    print(
        "Future Candles            : "
        "PROHIBITED"
    )

    print(
        "Participant/Options/etc.  : "
        "NOT FABRICATED"
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
    Display adapter configuration.
    """

    print()
    print("=" * 100)
    print("AQSD HISTORICAL SOURCE ADAPTER STATUS")
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
        f"FYERS Config              : "
        f"{CONFIG_FILE}"
    )

    print(
        f"FYERS Config Exists       : "
        f"{'YES' if CONFIG_FILE.exists() else 'NO'}"
    )

    print(
        f"NSE Trading Calendar      : "
        f"{TRADING_CALENDAR_FILE}"
    )

    print(
        f"Calendar Exists           : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )

    print(
        f"Historical Root           : "
        f"{HISTORICAL_ROOT}"
    )

    print(
        f"Default Sessions          : "
        f"{DEFAULT_SESSIONS}"
    )

    print(
        f"Market Structure Window   : "
        f"{DEFAULT_WINDOW_SESSIONS}"
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
            "Build date-specific historical AQSD source files."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
        help=(
            "Number of NSE trading sessions. "
            "Default = 60."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Last historical trading date YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=(
            "FYERS historical symbol."
        ),
    )

    parser.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW_SESSIONS,
        help=(
            "Historical OHLCV sessions stored per date."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Overwrite existing market_structure.csv files."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display adapter status."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    if arguments.status:
        show_status()
        return

    sessions = max(
        1,
        int(
            arguments.sessions
        ),
    )

    window_sessions = max(
        20,
        int(
            arguments.window
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
        summary = run_historical_source_adapter(
            sessions=sessions,
            end_date=end_date,
            symbol=(
                arguments.symbol
                .strip()
                .upper()
            ),
            window_sessions=(
                window_sessions
            ),
            overwrite=(
                arguments.overwrite
            ),
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print("AQSD HISTORICAL SOURCE ADAPTER")
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
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