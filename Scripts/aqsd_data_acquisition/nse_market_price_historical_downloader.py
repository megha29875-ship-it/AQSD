"""
AQSD
NSE Market Price Historical Downloader

Module : MPD-007
Version: 2.2.0
Author : AQSD

Purpose
-------
Acquire deep historical DAILY underlying market-price data using the
FYERS historical API while permanently avoiding unnecessary repeated
historical requests.

Major Features
--------------
- Deep historical backfill.
- Incremental updates.
- Controlled 365-day request chunks.
- Permanent acquisition coverage ledger.
- DATA ranges remembered.
- NO_DATA ranges remembered.
- FAILED ranges remain retryable.
- Existing consolidated history preserved.
- Previously downloaded immutable acquisition chunks recovered.
- Already downloaded ranges are not downloaded again.
- Immutable raw acquisition archive.
- Atomic consolidated-file update.
- No historical fabrication.

Architecture
------------
MPD-006 Validated Acquisition Queue
        ↓
Historical Acquisition Controller
        ↓
This Historical Downloader
        ↓
Coverage Check
   ┌────┼──────────────┐
   │    │              │
Existing Archive     Ledger
   │    │              │
   └────┼──────────────┘
        ↓
Only Missing Ranges
        ↓
FYERS Historical API
        ↓
Immutable Raw Acquisition Chunks
        ↓
Consolidated Raw History
        ↓
MPD-008 Raw Historical Validator

Coverage Policy
---------------
Before calling FYERS for any historical range AQSD checks:

1. Is the range already physically present in an immutable
   acquisition file?

2. Has the range already been recorded in the permanent
   acquisition coverage ledger?

3. Is the required period already represented in consolidated
   historical data?

If already completed:

    DATA      -> SKIP / RECOVER FROM ARCHIVE
    NO_DATA   -> SKIP
    FAILED    -> RETRY
    UNKNOWN   -> CALL FYERS

Historical fabrication is prohibited.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from Scripts.aqsd_data_acquisition.market_price_acquisition_history import (
    get_database_file as get_coverage_database_file,
    is_range_already_checked,
    record_acquisition_result,
)


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-007"
MODULE_VERSION: Final[str] = "2.2.0"

PROJECT_ROOT: Final[Path] = (
    Path(__file__)
    .resolve()
    .parents[2]
)

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


# ============================================================
# STORAGE PATHS
# ============================================================

RAW_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Raw"
)

RAW_ACQUISITION_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Raw_Acquisitions"
)


# ============================================================
# INPUT
# ============================================================

ACQUISITION_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue.csv"
)


# ============================================================
# OUTPUT FILES
# ============================================================

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

DEFAULT_HISTORY_START_DATE: Final[date] = date(
    2000,
    1,
    1,
)

HISTORY_CHUNK_DAYS: Final[int] = 365

MAX_RETRIES: Final[int] = 3

RETRY_DELAY_SECONDS: Final[float] = 2.0

REQUEST_DELAY_SECONDS: Final[float] = 0.35

# ------------------------------------------------------------
# IMPORTANT
#
# False means AQSD will NOT deliberately re-download recent
# completed sessions.
#
# Missing/new sessions are still downloaded automatically.
# ------------------------------------------------------------

ENABLE_RECENT_REFRESH: Final[bool] = False

RECENT_REFRESH_DAYS: Final[int] = 5


# ============================================================
# DATA MODELS
# ============================================================

@dataclass(frozen=True)
class DateRange:

    start_date: date

    end_date: date

    purpose: str


@dataclass(frozen=True)
class HistoryResponse:

    status: str

    candles: list

    message: str


# ============================================================
# DIRECTORY HELPERS
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

    RAW_ACQUISITION_ROOT.mkdir(
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


def read_optional_environment_value(
    *names: str,
) -> str:

    for name in names:

        value = os.getenv(
            name,
            "",
        ).strip()

        if value:

            return value

    return ""


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
# HISTORY START POLICY
# ============================================================

def get_history_start_date() -> date:

    configured = read_optional_environment_value(
        "AQSD_MARKET_PRICE_HISTORY_START"
    )

    if not configured:

        return DEFAULT_HISTORY_START_DATE

    try:

        return datetime.strptime(
            configured,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:

        raise RuntimeError(
            "AQSD_MARKET_PRICE_HISTORY_START "
            "must use YYYY-MM-DD format."
        ) from exc


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
        normalize_column_name(
            column
        )
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
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Acquisition queue missing required columns: "
            + ", ".join(
                missing
            )
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
        dataframe[
            "acquisition_ready"
        ]
    ].copy()

    dataframe = dataframe[
        dataframe[
            "acquisition_symbol"
        ].ne("")
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .sort_values(
            by=[
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe


# ============================================================
# FYERS SYMBOL
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

        upper = (
            acquisition_symbol
            .upper()
        )

        if upper.startswith(
            "NSE:"
        ):

            return upper

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

        return index_aliases[
            symbol
        ]

    if symbol:

        return (
            f"NSE:{symbol}-EQ"
        )

    raise RuntimeError(
        "Could not resolve FYERS symbol."
    )


# ============================================================
# EMPTY PRICE DATAFRAME
# ============================================================

def empty_price_dataframe() -> pd.DataFrame:

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


# ============================================================
# HISTORY NORMALIZATION
# ============================================================

def normalize_history_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    if dataframe.empty:

        return empty_price_dataframe()

    dataframe = dataframe.copy()

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    required = {
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
    }

    missing = sorted(
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Historical dataframe missing columns: "
            + ", ".join(
                missing
            )
        )

    dataframe["trade_date"] = pd.to_datetime(
        dataframe["trade_date"],
        errors="coerce",
    )

    dataframe = dataframe[
        dataframe[
            "trade_date"
        ].notna()
    ].copy()

    dataframe["trade_date"] = (
        dataframe["trade_date"]
        .dt.date
        .astype(str)
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

    dataframe["fyers_symbol"] = (
        dataframe["fyers_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["source"] = (
        dataframe["source"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["downloaded_at"] = (
        dataframe["downloaded_at"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe = (
        dataframe
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
        .reset_index(
            drop=True
        )
    )

    return dataframe[
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


# ============================================================
# FILE PATHS
# ============================================================

def get_consolidated_file(
    symbol: str,
) -> Path:

    directory = (
        RAW_ROOT
        / safe_filename(
            symbol
        )
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        directory
        / "daily_history.csv"
    )


def get_acquisition_directory(
    symbol: str,
) -> Path:

    directory = (
        RAW_ACQUISITION_ROOT
        / safe_filename(
            symbol
        )
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ============================================================
# EXISTING CONSOLIDATED HISTORY
# ============================================================

def load_existing_history(
    symbol: str,
) -> pd.DataFrame:

    file = get_consolidated_file(
        symbol
    )

    if not file.exists():

        return empty_price_dataframe()

    try:

        dataframe = pd.read_csv(
            file,
            low_memory=False,
        )

    except pd.errors.EmptyDataError:

        return empty_price_dataframe()

    return normalize_history_dataframe(
        dataframe
    )


# ============================================================
# DATE RANGE GENERATION
# ============================================================

def split_date_range(
    start_date: date,
    end_date: date,
    *,
    purpose: str,
) -> list[DateRange]:

    if start_date > end_date:

        return []

    ranges: list[
        DateRange
    ] = []

    cursor = start_date

    while cursor <= end_date:

        chunk_end = min(
            cursor
            + timedelta(
                days=(
                    HISTORY_CHUNK_DAYS
                    - 1
                )
            ),
            end_date,
        )

        ranges.append(
            DateRange(
                start_date=cursor,
                end_date=chunk_end,
                purpose=purpose,
            )
        )

        cursor = (
            chunk_end
            + timedelta(
                days=1
            )
        )

    return ranges


def remove_duplicate_ranges(
    ranges: list[DateRange],
) -> list[DateRange]:

    seen: set[
        tuple[
            date,
            date,
            str,
        ]
    ] = set()

    output: list[
        DateRange
    ] = []

    for item in ranges:

        key = (
            item.start_date,
            item.end_date,
            item.purpose,
        )

        if key in seen:

            continue

        seen.add(
            key
        )

        output.append(
            item
        )

    return output


def build_required_ranges(
    existing: pd.DataFrame,
    *,
    history_start: date,
    today: date,
) -> list[DateRange]:

    ranges: list[
        DateRange
    ] = []

    # --------------------------------------------------------
    # No consolidated data exists.
    # --------------------------------------------------------

    if existing.empty:

        return split_date_range(
            history_start,
            today,
            purpose="INITIAL_BACKFILL",
        )

    existing_dates = pd.to_datetime(
        existing[
            "trade_date"
        ],
        errors="coerce",
    ).dropna()

    if existing_dates.empty:

        return split_date_range(
            history_start,
            today,
            purpose="INITIAL_BACKFILL",
        )

    first_existing = (
        existing_dates
        .min()
        .date()
    )

    last_existing = (
        existing_dates
        .max()
        .date()
    )

    # --------------------------------------------------------
    # Historical backfill before earliest existing data.
    # --------------------------------------------------------

    if first_existing > history_start:

        ranges.extend(
            split_date_range(
                history_start,
                first_existing
                - timedelta(
                    days=1
                ),
                purpose="HISTORICAL_BACKFILL",
            )
        )

    # --------------------------------------------------------
    # Incremental update after latest existing data.
    # --------------------------------------------------------

    if last_existing < today:

        ranges.extend(
            split_date_range(
                last_existing
                + timedelta(
                    days=1
                ),
                today,
                purpose="INCREMENTAL_UPDATE",
            )
        )

    # --------------------------------------------------------
    # Optional recent refresh.
    # Disabled by default to avoid unnecessary requests.
    # --------------------------------------------------------

    if ENABLE_RECENT_REFRESH:

        refresh_start = max(
            history_start,
            today
            - timedelta(
                days=RECENT_REFRESH_DAYS
            ),
        )

        ranges.append(
            DateRange(
                start_date=refresh_start,
                end_date=today,
                purpose="RECENT_REFRESH",
            )
        )

    return remove_duplicate_ranges(
        ranges
    )


# ============================================================
# IMMUTABLE ARCHIVE DISCOVERY
# ============================================================

def find_existing_archive_file(
    *,
    symbol: str,
    date_range: DateRange,
) -> Path | None:

    directory = get_acquisition_directory(
        symbol
    )

    prefix = (
        date_range.start_date.isoformat()
        + "__"
        + date_range.end_date.isoformat()
        + "__"
    )

    candidates = sorted(
        (
            path
            for path in directory.glob(
                f"{prefix}*.csv"
            )
            if path.is_file()
        ),
        key=lambda path: (
            path.stat().st_mtime
        ),
        reverse=True,
    )

    if not candidates:

        return None

    return candidates[0]


def load_archive_file(
    *,
    archive_file: Path,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
) -> pd.DataFrame:

    try:

        dataframe = pd.read_csv(
            archive_file,
            low_memory=False,
        )

    except Exception as exc:

        raise RuntimeError(
            "Could not read archived acquisition file: "
            f"{archive_file}: {exc}"
        ) from exc

    dataframe = normalize_history_dataframe(
        dataframe
    )

    if dataframe.empty:

        raise RuntimeError(
            "Archived acquisition file is empty: "
            f"{archive_file}"
        )

    security_ids = set(
        dataframe[
            "security_id"
        ]
        .astype(str)
        .str.strip()
    )

    if security_ids != {
        security_id
    }:

        raise RuntimeError(
            "Archive security_id mismatch: "
            f"{archive_file}"
        )

    symbols = set(
        dataframe[
            "symbol"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if symbols != {
        symbol
    }:

        raise RuntimeError(
            "Archive symbol mismatch: "
            f"{archive_file}"
        )

    fyers_symbols = set(
        dataframe[
            "fyers_symbol"
        ]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if fyers_symbols != {
        fyers_symbol.upper()
    }:

        raise RuntimeError(
            "Archive FYERS symbol mismatch: "
            f"{archive_file}"
        )

    return dataframe


# ============================================================
# CONSOLIDATED RANGE PRESENCE
# ============================================================

def consolidated_contains_data_for_range(
    existing: pd.DataFrame,
    date_range: DateRange,
) -> bool:

    if existing.empty:

        return False

    dates = pd.to_datetime(
        existing[
            "trade_date"
        ],
        errors="coerce",
    ).dropna()

    if dates.empty:

        return False

    start_timestamp = pd.Timestamp(
        date_range.start_date
    )

    end_timestamp = pd.Timestamp(
        date_range.end_date
    )

    return bool(
        (
            (dates >= start_timestamp)
            &
            (dates <= end_timestamp)
        ).any()
    )


# ============================================================
# FYERS REQUEST
# ============================================================

def request_history(
    fyers: fyersModel.FyersModel,
    *,
    fyers_symbol: str,
    start_date: date,
    end_date: date,
) -> HistoryResponse:

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

            candles = response.get(
                "candles",
                [],
            )

            message = str(
                response.get(
                    "message",
                    response.get(
                        "msg",
                        "",
                    ),
                )
                or ""
            ).strip()

            # ------------------------------------------------
            # VALID DATA
            # ------------------------------------------------

            if status == "ok":

                if candles is None:

                    candles = []

                if not isinstance(
                    candles,
                    list,
                ):

                    raise RuntimeError(
                        "FYERS candles field is not a list."
                    )

                if not candles:

                    return HistoryResponse(
                        status="NO_DATA",
                        candles=[],
                        message=(
                            message
                            or "EMPTY_CANDLES"
                        ),
                    )

                return HistoryResponse(
                    status="DATA",
                    candles=candles,
                    message=message,
                )

            # ------------------------------------------------
            # VALID NO-DATA PERIOD
            # ------------------------------------------------

            if status in {
                "no_data",
                "nodata",
            }:

                return HistoryResponse(
                    status="NO_DATA",
                    candles=[],
                    message=(
                        message
                        or "FYERS_NO_DATA"
                    ),
                )

            if (
                candles == []
                and "no data"
                in message.lower()
            ):

                return HistoryResponse(
                    status="NO_DATA",
                    candles=[],
                    message=(
                        message
                        or "FYERS_NO_DATA"
                    ),
                )

            raise RuntimeError(
                "FYERS history request failed: "
                f"{response}"
            )

        except Exception as exc:

            last_error = exc

            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

    raise RuntimeError(
        "History request failed after "
        f"{MAX_RETRIES} attempts: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )


# ============================================================
# FYERS RESPONSE CONVERSION
# ============================================================

def candles_to_dataframe(
    candles: list,
    *,
    security_id: str,
    aqsd_symbol: str,
    fyers_symbol: str,
) -> pd.DataFrame:

    if not candles:

        return empty_price_dataframe()

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
    ).dt.date.astype(
        str
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["security_id"] = (
        security_id
    )

    dataframe["symbol"] = (
        aqsd_symbol
    )

    dataframe["fyers_symbol"] = (
        fyers_symbol
    )

    dataframe["source"] = (
        "FYERS_HISTORY"
    )

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

    return normalize_history_dataframe(
        dataframe
    )


# ============================================================
# IMMUTABLE ACQUISITION SAVE
# ============================================================

def save_immutable_acquisition_chunk(
    dataframe: pd.DataFrame,
    *,
    symbol: str,
    date_range: DateRange,
) -> Path:

    if dataframe.empty:

        raise RuntimeError(
            "Cannot archive an empty acquisition dataframe."
        )

    directory = get_acquisition_directory(
        symbol
    )

    timestamp = (
        datetime.now()
        .astimezone()
        .strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    suffix = (
        uuid.uuid4()
        .hex[:8]
    )

    filename = (
        date_range.start_date.isoformat()
        + "__"
        + date_range.end_date.isoformat()
        + "__"
        + date_range.purpose.lower()
        + "__"
        + timestamp
        + "__"
        + suffix
        + ".csv"
    )

    output_file = (
        directory
        / filename
    )

    if output_file.exists():

        raise RuntimeError(
            "Immutable acquisition filename collision: "
            f"{output_file}"
        )

    dataframe.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    return output_file


# ============================================================
# MERGE HISTORY
# ============================================================

def merge_history(
    existing: pd.DataFrame,
    new_frames: list[pd.DataFrame],
) -> pd.DataFrame:

    frames: list[
        pd.DataFrame
    ] = []

    if not existing.empty:

        frames.append(
            existing
        )

    for dataframe in new_frames:

        if not dataframe.empty:

            frames.append(
                dataframe
            )

    if not frames:

        return empty_price_dataframe()

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    combined = normalize_history_dataframe(
        combined
    )

    combined = (
        combined
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
        .reset_index(
            drop=True
        )
    )

    return combined


# ============================================================
# VALIDATE CONSOLIDATED HISTORY
# ============================================================

def validate_consolidated_history(
    dataframe: pd.DataFrame,
    *,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
) -> None:

    if dataframe.empty:

        raise RuntimeError(
            "Consolidated history is empty."
        )

    duplicate_dates = int(
        dataframe.duplicated(
            subset=[
                "trade_date",
            ],
            keep=False,
        ).sum()
    )

    if duplicate_dates:

        raise RuntimeError(
            "Consolidated history contains "
            f"{duplicate_dates:,} duplicate sessions."
        )

    security_ids = set(
        dataframe[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    security_ids.discard(
        ""
    )

    if security_ids != {
        security_id
    }:

        raise RuntimeError(
            "Consolidated security_id mismatch."
        )

    symbols = set(
        dataframe[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    symbols.discard(
        ""
    )

    if symbols != {
        symbol
    }:

        raise RuntimeError(
            "Consolidated symbol mismatch."
        )

    fyers_symbols = set(
        dataframe[
            "fyers_symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    fyers_symbols.discard(
        ""
    )

    if fyers_symbols != {
        fyers_symbol.upper()
    }:

        raise RuntimeError(
            "Consolidated FYERS symbol mismatch."
        )

    dates = pd.to_datetime(
        dataframe[
            "trade_date"
        ],
        errors="coerce",
    )

    if dates.isna().any():

        raise RuntimeError(
            "Consolidated history contains invalid dates."
        )

    if (
        dates.dt.date
        > date.today()
    ).any():

        raise RuntimeError(
            "Consolidated history contains future dates."
        )

    numeric = dataframe[
        [
            "open",
            "high",
            "low",
            "close",
        ]
    ].apply(
        pd.to_numeric,
        errors="coerce",
    )

    if numeric.isna().any(
        axis=None
    ):

        raise RuntimeError(
            "Consolidated history contains "
            "null/non-numeric OHLC."
        )

    if (
        numeric
        <= 0
    ).any(
        axis=None
    ):

        raise RuntimeError(
            "Consolidated history contains "
            "non-positive OHLC."
        )

    invalid_ohlc = (
        (
            numeric["high"]
            < numeric["low"]
        )
        |
        (
            numeric["open"]
            < numeric["low"]
        )
        |
        (
            numeric["open"]
            > numeric["high"]
        )
        |
        (
            numeric["close"]
            < numeric["low"]
        )
        |
        (
            numeric["close"]
            > numeric["high"]
        )
    )

    if invalid_ohlc.any():

        raise RuntimeError(
            "Consolidated history contains "
            "invalid OHLC relationships."
        )

    volume = pd.to_numeric(
        dataframe[
            "volume"
        ],
        errors="coerce",
    )

    if (
        volume
        < 0
    ).fillna(
        False
    ).any():

        raise RuntimeError(
            "Consolidated history contains negative volume."
        )


# ============================================================
# ATOMIC CONSOLIDATED SAVE
# ============================================================

def save_consolidated_history(
    dataframe: pd.DataFrame,
    *,
    symbol: str,
) -> Path:

    output_file = get_consolidated_file(
        symbol
    )

    temporary_file = (
        output_file.parent
        / (
            output_file.name
            + ".__aqsd_tmp__"
        )
    )

    temporary_file.unlink(
        missing_ok=True
    )

    dataframe.to_csv(
        temporary_file,
        index=False,
        encoding="utf-8-sig",
    )

    verification = pd.read_csv(
        temporary_file,
        low_memory=False,
    )

    if len(
        verification
    ) != len(
        dataframe
    ):

        temporary_file.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            "Temporary consolidated history "
            "row-count verification failed."
        )

    os.replace(
        temporary_file,
        output_file,
    )

    return output_file


# ============================================================
# DOWNLOAD ONE SECURITY
# ============================================================

def download_security(
    fyers: fyersModel.FyersModel,
    *,
    row: pd.Series,
    history_start: date,
    today: date,
) -> dict[str, object]:

    started = time.perf_counter()

    security_id = str(
        row[
            "security_id"
        ]
    ).strip()

    symbol = str(
        row[
            "symbol"
        ]
    ).strip().upper()

    fyers_symbol = (
        build_fyers_symbol(
            row
        )
        .strip()
        .upper()
    )

    print(
        f"\n    FYERS SYMBOL : "
        f"{fyers_symbol}"
    )

    existing = load_existing_history(
        symbol
    )

    existing_rows = int(
        len(
            existing
        )
    )

    required_ranges = build_required_ranges(
        existing,
        history_start=history_start,
        today=today,
    )

    new_frames: list[
        pd.DataFrame
    ] = []

    requests_made = 0

    ranges_with_data = 0

    no_data_ranges = 0

    skipped_ledger_data = 0

    skipped_ledger_no_data = 0

    recovered_archive_ranges = 0

    acquired_rows = 0

    immutable_chunks_saved = 0

    for request_number, date_range in enumerate(
        required_ranges,
        start=1,
    ):

        print(
            "        "
            f"[{request_number:02d}/"
            f"{len(required_ranges):02d}] "
            f"{date_range.start_date} -> "
            f"{date_range.end_date} "
            f"{date_range.purpose}",
            end=" ",
            flush=True,
        )

        # ====================================================
        # 1. CHECK PHYSICAL IMMUTABLE ARCHIVE FIRST
        # ====================================================

        archive_file = find_existing_archive_file(
            symbol=symbol,
            date_range=date_range,
        )

        if archive_file is not None:

            try:

                archived_dataframe = load_archive_file(
                    archive_file=archive_file,
                    security_id=security_id,
                    symbol=symbol,
                    fyers_symbol=fyers_symbol,
                )

                new_frames.append(
                    archived_dataframe
                )

                recovered_archive_ranges += 1

                ranges_with_data += 1

                # Register old physical acquisition in the
                # new coverage ledger if not already present.
                already_checked, _, _ = (
                    is_range_already_checked(
                        fyers_symbol=fyers_symbol,
                        range_from=date_range.start_date,
                        range_to=date_range.end_date,
                        resolution=RESOLUTION,
                    )
                )

                if not already_checked:

                    record_acquisition_result(
                        security_id=security_id,
                        symbol=symbol,
                        fyers_symbol=fyers_symbol,
                        range_from=date_range.start_date,
                        range_to=date_range.end_date,
                        resolution=RESOLUTION,
                        result_status="DATA",
                        rows_received=len(
                            archived_dataframe
                        ),
                        first_session=(
                            archived_dataframe[
                                "trade_date"
                            ].min()
                        ),
                        last_session=(
                            archived_dataframe[
                                "trade_date"
                            ].max()
                        ),
                        message=(
                            "BOOTSTRAPPED_FROM_EXISTING_"
                            "IMMUTABLE_ARCHIVE"
                        ),
                        module_version=MODULE_VERSION,
                    )

                print(
                    "ARCHIVE EXISTS - RECOVERED / "
                    "FYERS SKIPPED"
                )

                continue

            except Exception as exc:

                print(
                    "ARCHIVE INVALID - "
                    f"WILL RECHECK FYERS ({exc})"
                )

        # ====================================================
        # 2. CHECK PERMANENT COVERAGE LEDGER
        # ====================================================

        (
            already_checked,
            previous_status,
            previous_rows,
        ) = is_range_already_checked(
            fyers_symbol=fyers_symbol,
            range_from=date_range.start_date,
            range_to=date_range.end_date,
            resolution=RESOLUTION,
        )

        if already_checked:

            if previous_status == "NO_DATA":

                skipped_ledger_no_data += 1

                no_data_ranges += 1

                print(
                    "KNOWN NO_DATA - FYERS SKIPPED"
                )

                continue

            if previous_status == "DATA":

                # Ledger says DATA was acquired previously.
                # Before skipping, confirm physical historical
                # data still exists somewhere.

                if consolidated_contains_data_for_range(
                    existing,
                    date_range,
                ):

                    skipped_ledger_data += 1

                    print(
                        f"ALREADY HAVE DATA "
                        f"({previous_rows:,} ledger rows) "
                        "- FYERS SKIPPED"
                    )

                    continue

                # DATA is recorded in ledger but neither an
                # archive file nor consolidated data exists.
                # Do not blindly trust metadata; reacquire.

                print(
                    "LEDGER DATA BUT PHYSICAL DATA "
                    "NOT FOUND - REACQUIRING"
                )

        # ====================================================
        # 3. FYERS REQUEST REQUIRED
        # ====================================================

        try:

            response = request_history(
                fyers,
                fyers_symbol=fyers_symbol,
                start_date=date_range.start_date,
                end_date=date_range.end_date,
            )

            requests_made += 1

            # =================================================
            # VALID NO_DATA
            # =================================================

            if response.status == "NO_DATA":

                no_data_ranges += 1

                record_acquisition_result(
                    security_id=security_id,
                    symbol=symbol,
                    fyers_symbol=fyers_symbol,
                    range_from=date_range.start_date,
                    range_to=date_range.end_date,
                    resolution=RESOLUTION,
                    result_status="NO_DATA",
                    rows_received=0,
                    first_session=None,
                    last_session=None,
                    message=(
                        response.message
                        or "FYERS_NO_DATA"
                    ),
                    module_version=MODULE_VERSION,
                )

                print(
                    "NO DATA - RECORDED / "
                    "FUTURE RUNS WILL SKIP"
                )

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

                continue

            # =================================================
            # DATA RECEIVED
            # =================================================

            dataframe = candles_to_dataframe(
                response.candles,
                security_id=security_id,
                aqsd_symbol=symbol,
                fyers_symbol=fyers_symbol,
            )

            if dataframe.empty:

                no_data_ranges += 1

                record_acquisition_result(
                    security_id=security_id,
                    symbol=symbol,
                    fyers_symbol=fyers_symbol,
                    range_from=date_range.start_date,
                    range_to=date_range.end_date,
                    resolution=RESOLUTION,
                    result_status="NO_DATA",
                    rows_received=0,
                    first_session=None,
                    last_session=None,
                    message="NORMALIZED_EMPTY_DATASET",
                    module_version=MODULE_VERSION,
                )

                print(
                    "EMPTY DATA - RECORDED NO_DATA"
                )

                continue

            archive_file = (
                save_immutable_acquisition_chunk(
                    dataframe,
                    symbol=symbol,
                    date_range=date_range,
                )
            )

            immutable_chunks_saved += 1

            new_frames.append(
                dataframe
            )

            ranges_with_data += 1

            acquired_rows += int(
                len(
                    dataframe
                )
            )

            first_session = str(
                dataframe[
                    "trade_date"
                ].min()
            )

            last_session = str(
                dataframe[
                    "trade_date"
                ].max()
            )

            record_acquisition_result(
                security_id=security_id,
                symbol=symbol,
                fyers_symbol=fyers_symbol,
                range_from=date_range.start_date,
                range_to=date_range.end_date,
                resolution=RESOLUTION,
                result_status="DATA",
                rows_received=len(
                    dataframe
                ),
                first_session=first_session,
                last_session=last_session,
                message=(
                    f"IMMUTABLE_ARCHIVE={archive_file}"
                ),
                module_version=MODULE_VERSION,
            )

            print(
                f"{len(dataframe):,} rows "
                "- SAVED / LEDGER UPDATED"
            )

        except Exception as exc:

            # ------------------------------------------------
            # FAILED attempts are recorded, but FAILED does
            # NOT block later retry.
            # ------------------------------------------------

            record_acquisition_result(
                security_id=security_id,
                symbol=symbol,
                fyers_symbol=fyers_symbol,
                range_from=date_range.start_date,
                range_to=date_range.end_date,
                resolution=RESOLUTION,
                result_status="FAILED",
                rows_received=0,
                first_session=None,
                last_session=None,
                message=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
                module_version=MODULE_VERSION,
            )

            print(
                "FAILED - RECORDED / "
                "RETRY ALLOWED NEXT RUN"
            )

            raise RuntimeError(
                f"{date_range.start_date} -> "
                f"{date_range.end_date}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ) from exc

        finally:

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    # ========================================================
    # MERGE
    # ========================================================

    consolidated = merge_history(
        existing,
        new_frames,
    )

    if consolidated.empty:

        raise RuntimeError(
            "No historical candles available for security."
        )

    validate_consolidated_history(
        consolidated,
        security_id=security_id,
        symbol=symbol,
        fyers_symbol=fyers_symbol,
    )

    output_file = save_consolidated_history(
        consolidated,
        symbol=symbol,
    )

    final_rows = int(
        len(
            consolidated
        )
    )

    net_new_rows = max(
        final_rows
        - existing_rows,
        0,
    )

    first_session = str(
        consolidated[
            "trade_date"
        ].min()
    )

    last_session = str(
        consolidated[
            "trade_date"
        ].max()
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
            symbol,

        "fyers_symbol":
            fyers_symbol,

        # Compatibility with controller / MPD-008
        "rows":
            final_rows,

        "existing_rows":
            existing_rows,

        "new_rows_acquired":
            acquired_rows,

        "net_new_rows":
            net_new_rows,

        "final_rows":
            final_rows,

        "requests_made":
            requests_made,

        "ranges_with_data":
            ranges_with_data,

        "no_data_ranges":
            no_data_ranges,

        "skipped_ledger_data":
            skipped_ledger_data,

        "skipped_ledger_no_data":
            skipped_ledger_no_data,

        "recovered_archive_ranges":
            recovered_archive_ranges,

        "immutable_chunks_saved":
            immutable_chunks_saved,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "output_file":
            str(
                output_file
            ),

        "immutable_archive_root":
            str(
                get_acquisition_directory(
                    symbol
                )
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

    history_start = get_history_start_date()

    today = date.today()

    if history_start > today:

        raise RuntimeError(
            "Historical start date cannot be in future."
        )

    coverage_database = (
        get_coverage_database_file()
    )

    print()

    print(
        "=" * 104
    )

    print(
        "AQSD MARKET PRICE HISTORICAL DOWNLOADER"
    )

    print(
        "=" * 104
    )

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
        f"Historical Target From         : "
        f"{history_start}"
    )

    print(
        f"Historical Target To           : "
        f"{today}"
    )

    print(
        f"Request Chunk Days             : "
        f"{HISTORY_CHUNK_DAYS}"
    )

    print(
        f"Coverage Ledger                : "
        f"{coverage_database}"
    )

    print(
        f"Immutable Raw Archive          : "
        f"{RAW_ACQUISITION_ROOT}"
    )

    print(
        f"Consolidated Raw Root          : "
        f"{RAW_ROOT}"
    )

    print(
        f"Automatic Recent Refresh       : "
        f"{ENABLE_RECENT_REFRESH}"
    )

    print(
        "Completed Historical Ranges    : NEVER RE-DOWNLOADED"
    )

    print(
        "Known NO_DATA Ranges           : NEVER RE-DOWNLOADED"
    )

    print(
        "FAILED Ranges                  : RETRY ENABLED"
    )

    print(
        "Existing Archive Files         : REUSED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print(
        "-" * 104
    )

    results: list[
        dict[str, object]
    ] = []

    total_securities = len(
        queue
    )

    for number, (_, row) in enumerate(
        queue.iterrows(),
        start=1,
    ):

        symbol = str(
            row[
                "symbol"
            ]
        ).strip().upper()

        print()

        print(
            f"[{number:03d}/"
            f"{total_securities:03d}] "
            f"{symbol}"
        )

        try:

            result = download_security(
                fyers,
                row=row,
                history_start=history_start,
                today=today,
            )

            results.append(
                result
            )

            print(
                "    SUCCESS | "
                f"Existing="
                f"{int(result['existing_rows']):,} | "
                f"Acquired="
                f"{int(result['new_rows_acquired']):,} | "
                f"Net New="
                f"{int(result['net_new_rows']):,} | "
                f"Final="
                f"{int(result['final_rows']):,}"
            )

            print(
                "    SAVED CALLS | "
                f"Ledger DATA="
                f"{int(result['skipped_ledger_data']):,} | "
                f"Ledger NO_DATA="
                f"{int(result['skipped_ledger_no_data']):,} | "
                f"Archive Recovered="
                f"{int(result['recovered_archive_ranges']):,}"
            )

            print(
                "    COVERAGE | "
                f"{result['first_session']} "
                f"-> "
                f"{result['last_session']} | "
                f"FYERS Calls="
                f"{int(result['requests_made']):,}"
            )

        except Exception as exc:

            fyers_symbol = ""

            try:

                fyers_symbol = (
                    build_fyers_symbol(
                        row
                    )
                )

            except Exception:

                pass

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
                    fyers_symbol,

                "rows":
                    0,

                "existing_rows":
                    0,

                "new_rows_acquired":
                    0,

                "net_new_rows":
                    0,

                "final_rows":
                    0,

                "requests_made":
                    0,

                "ranges_with_data":
                    0,

                "no_data_ranges":
                    0,

                "skipped_ledger_data":
                    0,

                "skipped_ledger_no_data":
                    0,

                "recovered_archive_ranges":
                    0,

                "immutable_chunks_saved":
                    0,

                "first_session":
                    "",

                "last_session":
                    "",

                "output_file":
                    "",

                "immutable_archive_root":
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
                "    FAILED | "
                f"{type(exc).__name__}: "
                f"{exc}"
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

    def sum_column(
        column: str,
    ) -> int:

        if column not in results_dataframe.columns:

            return 0

        return int(
            pd.to_numeric(
                results_dataframe[
                    column
                ],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )

    total_rows = sum_column(
        "rows"
    )

    total_existing_rows = sum_column(
        "existing_rows"
    )

    total_acquired_rows = sum_column(
        "new_rows_acquired"
    )

    total_net_new_rows = sum_column(
        "net_new_rows"
    )

    total_requests = sum_column(
        "requests_made"
    )

    total_ledger_data_skips = sum_column(
        "skipped_ledger_data"
    )

    total_ledger_no_data_skips = sum_column(
        "skipped_ledger_no_data"
    )

    total_archive_recoveries = sum_column(
        "recovered_archive_ranges"
    )

    total_chunks_saved = sum_column(
        "immutable_chunks_saved"
    )

    fyers_calls_saved = (
        total_ledger_data_skips
        + total_ledger_no_data_skips
        + total_archive_recoveries
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

        "history_target_from":
            history_start.isoformat(),

        "history_target_to":
            today.isoformat(),

        "range_from":
            history_start.isoformat(),

        "range_to":
            today.isoformat(),

        "history_chunk_days":
            HISTORY_CHUNK_DAYS,

        "queue_rows":
            len(
                queue
            ),

        "successful_symbols":
            successful,

        "failed_symbols":
            failed,

        # Compatibility
        "downloaded_rows":
            total_rows,

        "consolidated_raw_rows":
            total_rows,

        "existing_rows_before_run":
            total_existing_rows,

        "api_rows_acquired":
            total_acquired_rows,

        "net_new_rows":
            total_net_new_rows,

        "api_requests":
            total_requests,

        "ledger_data_skips":
            total_ledger_data_skips,

        "ledger_no_data_skips":
            total_ledger_no_data_skips,

        "archive_recoveries":
            total_archive_recoveries,

        "estimated_fyers_calls_saved":
            fyers_calls_saved,

        "immutable_chunks_saved":
            total_chunks_saved,

        "coverage_database":
            str(
                coverage_database
            ),

        "raw_root":
            str(
                RAW_ROOT
            ),

        "immutable_raw_archive":
            str(
                RAW_ACQUISITION_ROOT
            ),

        "audit_csv":
            str(
                AUDIT_CSV
            ),

        "failures_csv":
            str(
                FAILURES_CSV
            ),

        "completed_ranges_redownloaded":
            False,

        "known_no_data_redownloaded":
            False,

        "failed_ranges_retryable":
            True,

        "existing_archives_reused":
            True,

        "existing_history_preserved":
            True,

        "deep_historical_backfill_supported":
            True,

        "incremental_update_supported":
            True,

        "market_price_database_modified":
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

    print(
        "=" * 104
    )

    print(
        "AQSD HISTORICAL MARKET PRICE DOWNLOAD SUMMARY"
    )

    print(
        "=" * 104
    )

    print(
        f"Module                         : "
        f"{summary['module_id']}"
    )

    print(
        f"Version                        : "
        f"{summary['module_version']}"
    )

    print(
        "-" * 104
    )

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
        "-" * 104
    )

    print(
        f"Existing Rows Before Run       : "
        f"{int(summary['existing_rows_before_run']):,}"
    )

    print(
        f"API Rows Acquired              : "
        f"{int(summary['api_rows_acquired']):,}"
    )

    print(
        f"Net New Historical Rows        : "
        f"{int(summary['net_new_rows']):,}"
    )

    print(
        f"Final Consolidated Rows        : "
        f"{int(summary['consolidated_raw_rows']):,}"
    )

    print(
        "-" * 104
    )

    print(
        f"Actual FYERS Calls             : "
        f"{int(summary['api_requests']):,}"
    )

    print(
        f"Known DATA Ranges Skipped      : "
        f"{int(summary['ledger_data_skips']):,}"
    )

    print(
        f"Known NO_DATA Ranges Skipped   : "
        f"{int(summary['ledger_no_data_skips']):,}"
    )

    print(
        f"Existing Archives Recovered    : "
        f"{int(summary['archive_recoveries']):,}"
    )

    print(
        f"Estimated FYERS Calls Saved    : "
        f"{int(summary['estimated_fyers_calls_saved']):,}"
    )

    print(
        f"New Immutable Chunks Saved     : "
        f"{int(summary['immutable_chunks_saved']):,}"
    )

    print(
        "-" * 104
    )

    print(
        f"Coverage Ledger                : "
        f"{summary['coverage_database']}"
    )

    print(
        f"Immutable Raw Archive          : "
        f"{summary['immutable_raw_archive']}"
    )

    print(
        f"Consolidated Raw Root          : "
        f"{summary['raw_root']}"
    )

    print(
        "-" * 104
    )

    print(
        "Completed Historical Ranges    : SKIPPED"
    )

    print(
        "Known NO_DATA Ranges           : SKIPPED"
    )

    print(
        "FAILED Ranges                  : RETRYABLE"
    )

    print(
        "Existing Acquisition Files     : REUSED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "-" * 104
    )

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    print(
        "=" * 104
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_downloader()

        display_summary(
            summary
        )

    except KeyboardInterrupt:

        print()

        print(
            "=" * 104
        )

        print(
            "AQSD HISTORICAL MARKET PRICE DOWNLOADER"
        )

        print(
            "=" * 104
        )

        print(
            "Status                         : INTERRUPTED"
        )

        print(
            "Previously completed data      : PRESERVED"
        )

        print(
            "Historical Fabrication         : NONE"
        )

        print(
            "=" * 104
        )

        raise SystemExit(
            130
        )

    except Exception as exc:

        print()

        print(
            "=" * 104
        )

        print(
            "AQSD HISTORICAL MARKET PRICE DOWNLOADER"
        )

        print(
            "=" * 104
        )

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            "Existing Historical Data       : PRESERVED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        print(
            "Historical Fabrication         : PROHIBITED"
        )

        print(
            "=" * 104
        )

        raise SystemExit(
            1
        ) from exc


if __name__ == "__main__":
    main()