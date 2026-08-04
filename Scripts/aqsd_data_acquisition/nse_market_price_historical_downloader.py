"""
AQSD
NSE Market Price Historical Downloader

Module : MPD-007
Version: 1.0.0
Author : AQSD

Purpose
-------
Download historical DAILY underlying price data for the AQSD
Market Price acquisition queue using FYERS historical API.

This module is a RAW DATA ACQUISITION module.

It DOES NOT:
- modify AQSD_Market_Price.db
- modify the frozen F&O historical database
- modify the Security Master
- fabricate missing historical data
- merge data into canonical price history

Outputs
-------
Per-symbol raw CSV files
Download audit CSV
Failure CSV
Summary JSON

Architecture
------------
MPD-006 Acquisition Queue
        ↓
MPD-007 FYERS Downloader
        ↓
RAW per-symbol OHLCV files
        ↓
Future validation / canonicalization
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-007"
MODULE_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

ENV_FILE: Final[Path] = (
    PROJECT_ROOT
    / ".env"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

DATA_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Data"
)

RAW_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Raw"
)

ACQUISITION_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue.csv"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Audit.csv"
)

FAILURES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Failures.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Summary.json"
)


# ============================================================
# DOWNLOAD POLICY
# ============================================================

RESOLUTION: Final[str] = "1D"

# Start with a controlled historical window.
# We can expand this later after validation.
LOOKBACK_DAYS: Final[int] = 365

MAX_RETRIES: Final[int] = 3

RETRY_DELAY_SECONDS: Final[float] = 2.0

REQUEST_DELAY_SECONDS: Final[float] = 0.35


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RAW_ROOT.mkdir(
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


def safe_filename(
    symbol: str,
) -> str:

    return (
        symbol
        .replace(":", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


# ============================================================
# ENVIRONMENT
# ============================================================

def read_environment_value(
    *names: str,
) -> str:

    for name in names:

        value = os.getenv(
            name,
            "",
        ).strip()

        if value:
            return value

    raise RuntimeError(
        "Missing required environment variable. "
        f"Tried: {', '.join(names)}"
    )


def load_fyers_client() -> fyersModel.FyersModel:

    if not ENV_FILE.exists():

        raise FileNotFoundError(
            f".env file not found: {ENV_FILE}"
        )

    load_dotenv(
        ENV_FILE,
        override=False,
    )

    client_id = read_environment_value(
        "FYERS_CLIENT_ID",
        "CLIENT_ID",
    )

    access_token = read_environment_value(
        "FYERS_ACCESS_TOKEN",
        "ACCESS_TOKEN",
    )

    return fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path="",
    )


# ============================================================
# ACQUISITION QUEUE
# ============================================================

def load_acquisition_queue() -> pd.DataFrame:

    if not ACQUISITION_QUEUE_FILE.exists():

        raise FileNotFoundError(
            "Acquisition queue not found: "
            f"{ACQUISITION_QUEUE_FILE}"
        )

    dataframe = pd.read_csv(
        ACQUISITION_QUEUE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
        "acquisition_symbol",
        "acquisition_ready",
        "acquisition_status",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:

        raise RuntimeError(
            "Acquisition queue missing required columns: "
            + ", ".join(missing)
        )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["acquisition_symbol"] = (
        dataframe["acquisition_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    ready_text = (
        dataframe["acquisition_ready"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["acquisition_ready"] = (
        ready_text.isin(
            {
                "TRUE",
                "YES",
                "Y",
                "1",
            }
        )
    )

    dataframe = dataframe[
        dataframe["acquisition_ready"]
    ].copy()

    dataframe = dataframe[
        dataframe["acquisition_symbol"].ne("")
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return dataframe


# ============================================================
# FYERS SYMBOL NORMALIZATION
# ============================================================

def build_fyers_symbol(
    row: pd.Series,
) -> str:

    acquisition_symbol = str(
        row.get(
            "acquisition_symbol",
            "",
        )
    ).strip()

    symbol = str(
        row.get(
            "symbol",
            "",
        )
    ).strip().upper()

    if acquisition_symbol:

        upper = acquisition_symbol.upper()

        if upper.startswith("NSE:"):
            return acquisition_symbol

    # --------------------------------------------------------
    # Index mappings
    # --------------------------------------------------------

    index_aliases = {
        "BANKNIFTY":
            "NSE:NIFTYBANK-INDEX",

        "NIFTY":
            "NSE:NIFTY50-INDEX",

        "FINNIFTY":
            "NSE:FINNIFTY-INDEX",

        "MIDCPNIFTY":
            "NSE:MIDCPNIFTY-INDEX",
    }

    if symbol in index_aliases:
        return index_aliases[symbol]

    # --------------------------------------------------------
    # Standard NSE equity
    # --------------------------------------------------------

    if symbol:
        return f"NSE:{symbol}-EQ"

    raise RuntimeError(
        "Could not resolve FYERS symbol."
    )


# ============================================================
# DATE RANGE
# ============================================================

def build_date_range() -> tuple[date, date]:

    end_date = date.today()

    start_date = (
        end_date
        - timedelta(
            days=LOOKBACK_DAYS
        )
    )

    return (
        start_date,
        end_date,
    )


# ============================================================
# FYERS HISTORY REQUEST
# ============================================================

def request_history(
    fyers: fyersModel.FyersModel,
    *,
    fyers_symbol: str,
    start_date: date,
    end_date: date,
) -> dict:

    payload = {
        "symbol":
            fyers_symbol,

        "resolution":
            RESOLUTION,

        "date_format":
            "1",

        "range_from":
            start_date.isoformat(),

        "range_to":
            end_date.isoformat(),

        "cont_flag":
            "1",
    }

    last_error: Exception | None = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = fyers.history(
                data=payload
            )

            if not isinstance(
                response,
                dict,
            ):

                raise RuntimeError(
                    "FYERS returned a non-dictionary response."
                )

            status = str(
                response.get(
                    "s",
                    "",
                )
            ).strip().lower()

            if status != "ok":

                message = (
                    response.get("message")
                    or response.get("msg")
                    or response
                )

                raise RuntimeError(
                    f"FYERS history request failed: {message}"
                )

            candles = response.get(
                "candles"
            )

            if candles is None:

                raise RuntimeError(
                    "FYERS response does not contain candles."
                )

            return response

        except Exception as exc:

            last_error = exc

            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY_SECONDS
                )

    raise RuntimeError(
        f"History request failed after "
        f"{MAX_RETRIES} attempts: "
        f"{type(last_error).__name__}: {last_error}"
    )


# ============================================================
# RESPONSE CONVERSION
# ============================================================

def candles_to_dataframe(
    candles: list,
    *,
    security_id: str,
    aqsd_symbol: str,
    fyers_symbol: str,
) -> pd.DataFrame:

    if not candles:

        return pd.DataFrame(
            columns=[
                "trade_date",
                "security_id",
                "symbol",
                "fyers_symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source",
                "downloaded_at",
            ]
        )

    dataframe = pd.DataFrame(
        candles,
        columns=[
            "epoch",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    dataframe["epoch"] = pd.to_numeric(
        dataframe["epoch"],
        errors="coerce",
    )

    dataframe["trade_date"] = pd.to_datetime(
        dataframe["epoch"],
        unit="s",
        errors="coerce",
    ).dt.date.astype(str)

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["security_id"] = security_id
    dataframe["symbol"] = aqsd_symbol
    dataframe["fyers_symbol"] = fyers_symbol
    dataframe["source"] = "FYERS_HISTORY"

    dataframe["downloaded_at"] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    dataframe = dataframe[
        [
            "trade_date",
            "security_id",
            "symbol",
            "fyers_symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source",
            "downloaded_at",
        ]
    ].copy()

    dataframe = (
        dataframe
        .dropna(
            subset=[
                "trade_date",
            ]
        )
        .drop_duplicates(
            subset=[
                "trade_date",
            ],
            keep="last",
        )
        .sort_values(
            by=[
                "trade_date",
            ]
        )
        .reset_index(drop=True)
    )

    return dataframe


# ============================================================
# SAVE RAW SYMBOL FILE
# ============================================================

def save_raw_symbol_file(
    dataframe: pd.DataFrame,
    *,
    security_id: str,
    symbol: str,
) -> Path:

    symbol_directory = (
        RAW_ROOT
        / safe_filename(
            symbol
        )
    )

    symbol_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        symbol_directory
        / "daily_history.csv"
    )

    dataframe.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    return output_file


# ============================================================
# DOWNLOAD ONE SECURITY
# ============================================================

def download_security(
    fyers: fyersModel.FyersModel,
    *,
    row: pd.Series,
    start_date: date,
    end_date: date,
) -> dict[str, object]:

    started = time.perf_counter()

    security_id = str(
        row["security_id"]
    ).strip()

    aqsd_symbol = str(
        row["symbol"]
    ).strip().upper()

    fyers_symbol = build_fyers_symbol(
        row
    )

    print(
        f"\n    FYERS SYMBOL : {fyers_symbol}"
    )

    response = request_history(
        fyers,
        fyers_symbol=fyers_symbol,
        start_date=start_date,
        end_date=end_date,
    )

    candles = response.get(
        "candles",
        [],
    )

    dataframe = candles_to_dataframe(
        candles,
        security_id=security_id,
        aqsd_symbol=aqsd_symbol,
        fyers_symbol=fyers_symbol,
    )

    if dataframe.empty:

        raise RuntimeError(
            "FYERS returned zero historical candles."
        )

    output_file = save_raw_symbol_file(
        dataframe,
        security_id=security_id,
        symbol=aqsd_symbol,
    )

    elapsed = round(
        time.perf_counter()
        - started,
        2,
    )

    return {
        "security_id":
            security_id,

        "symbol":
            aqsd_symbol,

        "fyers_symbol":
            fyers_symbol,

        "rows":
            len(dataframe),

        "first_session":
            dataframe[
                "trade_date"
            ].min(),

        "last_session":
            dataframe[
                "trade_date"
            ].max(),

        "output_file":
            str(
                output_file
            ),

        "seconds":
            elapsed,

        "status":
            "SUCCESS",

        "message":
            "",
    }


# ============================================================
# RUN DOWNLOADER
# ============================================================

def run_downloader() -> dict[str, object]:

    ensure_directories()

    queue = load_acquisition_queue()

    if queue.empty:

        raise RuntimeError(
            "Acquisition queue contains no ready securities."
        )

    fyers = load_fyers_client()

    start_date, end_date = (
        build_date_range()
    )

    print()
    print("=" * 100)
    print("AQSD MARKET PRICE HISTORICAL DOWNLOADER")
    print("=" * 100)

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Acquisition Queue              : "
        f"{len(queue):,}"
    )

    print(
        f"Resolution                     : "
        f"{RESOLUTION}"
    )

    print(
        f"Range From                     : "
        f"{start_date}"
    )

    print(
        f"Range To                       : "
        f"{end_date}"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Frozen Historical Database     : UNTOUCHED"
    )

    print("-" * 100)

    results: list[
        dict[str, object]
    ] = []

    for number, (_, row) in enumerate(
        queue.iterrows(),
        start=1,
    ):

        symbol = str(
            row["symbol"]
        )

        print(
            f"[{number:03d}/{len(queue):03d}] "
            f"{symbol:<20}",
            end=" ",
            flush=True,
        )

        try:

            result = download_security(
                fyers,
                row=row,
                start_date=start_date,
                end_date=end_date,
            )

            results.append(
                result
            )

            print(
                f"SUCCESS | "
                f"{int(result['rows']):,} rows | "
                f"{result['first_session']} -> "
                f"{result['last_session']} | "
                f"{result['seconds']} sec"
            )

        except Exception as exc:

            result = {
                "security_id":
                    str(
                        row.get(
                            "security_id",
                            "",
                        )
                    ),

                "symbol":
                    symbol,

                "fyers_symbol":
                    "",

                "rows":
                    0,

                "first_session":
                    "",

                "last_session":
                    "",

                "output_file":
                    "",

                "seconds":
                    0,

                "status":
                    "FAILED",

                "message":
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
            }

            results.append(
                result
            )

            print(
                f"FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    results_dataframe = pd.DataFrame(
        results
    )

    results_dataframe.to_csv(
        AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    failures = results_dataframe[
        results_dataframe[
            "status"
        ].eq(
            "FAILED"
        )
    ].copy()

    failures.to_csv(
        FAILURES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    successful = int(
        results_dataframe[
            "status"
        ]
        .eq(
            "SUCCESS"
        )
        .sum()
    )

    failed = int(
        results_dataframe[
            "status"
        ]
        .eq(
            "FAILED"
        )
        .sum()
    )

    total_rows = int(
        pd.to_numeric(
            results_dataframe[
                "rows"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

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

        "resolution":
            RESOLUTION,

        "range_from":
            start_date.isoformat(),

        "range_to":
            end_date.isoformat(),

        "queue_rows":
            len(queue),

        "successful_symbols":
            successful,

        "failed_symbols":
            failed,

        "downloaded_rows":
            total_rows,

        "raw_root":
            str(
                RAW_ROOT
            ),

        "audit_csv":
            str(
                AUDIT_CSV
            ),

        "failures_csv":
            str(
                FAILURES_CSV
            ),

        "market_price_database_modified":
            False,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            (
                "SUCCESS"
                if failed == 0
                else "PARTIAL"
            ),
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
# DISPLAY SUMMARY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()
    print("=" * 100)
    print("AQSD MARKET PRICE HISTORICAL DOWNLOAD SUMMARY")
    print("=" * 100)

    print(
        f"Queue Rows                     : "
        f"{int(summary['queue_rows']):,}"
    )

    print(
        f"Successful Symbols             : "
        f"{int(summary['successful_symbols']):,}"
    )

    print(
        f"Failed Symbols                 : "
        f"{int(summary['failed_symbols']):,}"
    )

    print(
        f"Downloaded Rows                : "
        f"{int(summary['downloaded_rows']):,}"
    )

    print(
        f"Raw Data Root                  : "
        f"{summary['raw_root']}"
    )

    print(
        f"Audit CSV                      : "
        f"{summary['audit_csv']}"
    )

    print(
        f"Failures CSV                   : "
        f"{summary['failures_csv']}"
    )

    print("-" * 100)

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Frozen Historical Database     : UNTOUCHED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print("-" * 100)

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_downloader()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        print("=" * 100)
        print("AQSD MARKET PRICE HISTORICAL DOWNLOADER")
        print("=" * 100)

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        print(
            "Frozen Historical Database     : UNTOUCHED"
        )

        print(
            "Historical Fabrication         : PROHIBITED"
        )

        print("=" * 100)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()