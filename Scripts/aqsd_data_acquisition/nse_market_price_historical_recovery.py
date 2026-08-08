"""
AQSD
NSE Market Price Historical Recovery Engine

Module : MPD-REC-001
Version: 1.0.1
Author : AQSD

Purpose
-------
Recover exceptional historical market-price acquisition failures
without fabricating data and without repeating successful historical
downloads.

Current Recovery Cases
----------------------
1. Consolidated history contains non-positive OHLC values.
2. FYERS historical API returns "Bad request" for a large date range.

Recovery Principles
-------------------
- Immutable acquisition archives are NEVER modified.
- Existing consolidated data is backed up before repair.
- Invalid rows are quarantined, never silently discarded.
- FYERS Bad Request ranges are recursively split.
- DATA results are saved.
- NO_DATA results are remembered.
- FAILED ranges remain retryable.
- No historical prices are invented.

Important
---------
This recovery engine uses the existing failure CSV directly.

It DOES NOT depend on the acquisition queue.

Required failure-file fields:

    security_id
    symbol
    fyers_symbol
    status
    message
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd

from Scripts.aqsd_data_acquisition.market_price_acquisition_history import (
    record_acquisition_result,
)

from Scripts.aqsd_data_acquisition.nse_market_price_historical_downloader import (
    DateRange,
    RESOLUTION,
    candles_to_dataframe,
    get_consolidated_file,
    load_existing_history,
    load_fyers_client,
    merge_history,
    normalize_history_dataframe,
    save_consolidated_history,
    save_immutable_acquisition_chunk,
    validate_consolidated_history,
)


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-REC-001"
MODULE_VERSION: Final[str] = "1.0.1"

PROJECT_ROOT: Final[Path] = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

BACKUP_ROOT: Final[Path] = (
    PROJECT_ROOT
    / "Backup"
    / "Market_Price_Recovery"
)

QUARANTINE_ROOT: Final[Path] = (
    OUTPUT_DIR
    / "Market_Price_Recovery_Quarantine"
)


# ============================================================
# INPUT
# ============================================================

FAILURES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Failures.csv"
)


# ============================================================
# OUTPUTS
# ============================================================

RECOVERY_AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Recovery_Audit.csv"
)

RECOVERY_ISSUES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Recovery_Issues.csv"
)

RECOVERY_SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Recovery_Summary.json"
)


# ============================================================
# FYERS RECOVERY POLICY
# ============================================================

MAX_REQUEST_RETRIES: Final[int] = 3

RETRY_DELAY_SECONDS: Final[float] = 2.0

REQUEST_DELAY_SECONDS: Final[float] = 0.35

MIN_SPLIT_DAYS: Final[int] = 7


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(frozen=True)
class RangeResult:

    start_date: date

    end_date: date

    status: str

    rows: int

    message: str


# ============================================================
# GENERAL HELPERS
# ============================================================

def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKUP_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    QUARANTINE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


def now_text() -> str:

    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def safe_name(
    value: str,
) -> str:

    return (
        str(value)
        .strip()
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
# FAILURE INPUT
# ============================================================

def load_failure_file() -> pd.DataFrame:

    if not FAILURES_FILE.exists():

        raise FileNotFoundError(
            "Historical failure file not found: "
            f"{FAILURES_FILE}"
        )

    dataframe = pd.read_csv(
        FAILURES_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        str(column)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
        "fyers_symbol",
        "status",
        "message",
    }

    missing = sorted(
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Failure file missing required columns: "
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

    dataframe["fyers_symbol"] = (
        dataframe["fyers_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["status"] = (
        dataframe["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["message"] = (
        dataframe["message"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe = dataframe[
        dataframe[
            "status"
        ].eq(
            "FAILED"
        )
    ].copy()

    dataframe = dataframe[
        dataframe[
            "symbol"
        ].ne("")
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
                "symbol",
            ],
            keep="first",
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe


# ============================================================
# FAILURE CLASSIFICATION
# ============================================================

def classify_failure(
    message: str,
) -> str:

    text = str(
        message
    ).lower()

    if (
        "non-positive ohlc"
        in text
    ):

        return "NON_POSITIVE_OHLC"

    if (
        "bad request"
        in text
    ):

        return "FYERS_BAD_REQUEST"

    return "UNCLASSIFIED"


# ============================================================
# FAILED DATE RANGE PARSER
# ============================================================

def parse_failed_range(
    message: str,
) -> tuple[
    date,
    date,
] | None:

    match = re.search(
        (
            r"(\d{4}-\d{2}-\d{2})"
            r"\s*->\s*"
            r"(\d{4}-\d{2}-\d{2})"
        ),
        str(
            message
        ),
    )

    if match is None:

        return None

    return (
        date.fromisoformat(
            match.group(
                1
            )
        ),
        date.fromisoformat(
            match.group(
                2
            )
        ),
    )


# ============================================================
# BACKUP
# ============================================================

def backup_consolidated_file(
    symbol: str,
) -> Path | None:

    source = get_consolidated_file(
        symbol
    )

    if not source.exists():

        return None

    timestamp = (
        datetime.now()
        .astimezone()
        .strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    destination_directory = (
        BACKUP_ROOT
        / safe_name(
            symbol
        )
    )

    destination_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        destination_directory
        / (
            "daily_history_PRE_RECOVERY_"
            f"{timestamp}.csv"
        )
    )

    shutil.copy2(
        source,
        destination,
    )

    return destination


# ============================================================
# QUARANTINE
# ============================================================

def write_quarantine(
    dataframe: pd.DataFrame,
    *,
    symbol: str,
    reason: str,
) -> Path:

    timestamp = (
        datetime.now()
        .astimezone()
        .strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    destination_directory = (
        QUARANTINE_ROOT
        / safe_name(
            symbol
        )
    )

    destination_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        destination_directory
        / (
            f"{reason}_"
            f"{timestamp}.csv"
        )
    )

    dataframe.to_csv(
        destination,
        index=False,
        encoding="utf-8-sig",
    )

    return destination


# ============================================================
# INVALID OHLC IDENTIFICATION
# ============================================================

def identify_non_positive_ohlc(
    dataframe: pd.DataFrame,
) -> pd.Series:

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

    invalid = (
        numeric.isna().any(
            axis=1
        )
        |
        (
            numeric
            <= 0
        ).any(
            axis=1
        )
    )

    return invalid


# ============================================================
# NON-POSITIVE OHLC RECOVERY
# ============================================================

def recover_non_positive_ohlc(
    *,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
) -> dict[str, object]:

    if not fyers_symbol:

        raise RuntimeError(
            f"{symbol}: FYERS symbol missing "
            "from failure record."
        )

    existing = load_existing_history(
        symbol
    )

    if existing.empty:

        raise RuntimeError(
            f"{symbol}: consolidated history does not exist."
        )

    invalid_mask = (
        identify_non_positive_ohlc(
            existing
        )
    )

    invalid_rows = existing.loc[
        invalid_mask
    ].copy()

    if invalid_rows.empty:

        validate_consolidated_history(
            existing,
            security_id=security_id,
            symbol=symbol,
            fyers_symbol=fyers_symbol,
        )

        return {
            "symbol":
                symbol,
            "failure_type":
                "NON_POSITIVE_OHLC",
            "action":
                "NO_INVALID_ROWS_FOUND",
            "invalid_rows":
                0,
            "final_rows":
                int(
                    len(
                        existing
                    )
                ),
            "backup_file":
                "",
            "quarantine_file":
                "",
            "output_file":
                str(
                    get_consolidated_file(
                        symbol
                    )
                ),
            "status":
                "SUCCESS",
            "message":
                (
                    "Current consolidated history "
                    "contains no non-positive OHLC rows."
                ),
        }

    backup_file = (
        backup_consolidated_file(
            symbol
        )
    )

    quarantine_file = (
        write_quarantine(
            invalid_rows,
            symbol=symbol,
            reason="NON_POSITIVE_OHLC",
        )
    )

    repaired = existing.loc[
        ~invalid_mask
    ].copy()

    repaired = (
        normalize_history_dataframe(
            repaired
        )
    )

    if repaired.empty:

        raise RuntimeError(
            f"{symbol}: repair would leave no valid history."
        )

    validate_consolidated_history(
        repaired,
        security_id=security_id,
        symbol=symbol,
        fyers_symbol=fyers_symbol,
    )

    output_file = (
        save_consolidated_history(
            repaired,
            symbol=symbol,
        )
    )

    return {
        "symbol":
            symbol,
        "failure_type":
            "NON_POSITIVE_OHLC",
        "action":
            "QUARANTINED_INVALID_ROWS",
        "invalid_rows":
            int(
                len(
                    invalid_rows
                )
            ),
        "final_rows":
            int(
                len(
                    repaired
                )
            ),
        "backup_file":
            (
                str(
                    backup_file
                )
                if backup_file
                else ""
            ),
        "quarantine_file":
            str(
                quarantine_file
            ),
        "output_file":
            str(
                output_file
            ),
        "status":
            "SUCCESS",
        "message":
            (
                "Invalid consolidated OHLC rows were "
                "quarantined. Immutable acquisitions "
                "were not modified."
            ),
    }


# ============================================================
# FYERS RECOVERY REQUEST
# ============================================================

def request_recovery_history(
    fyers,
    *,
    fyers_symbol: str,
    start_date: date,
    end_date: date,
) -> tuple[
    str,
    list,
    str,
]:

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
        MAX_REQUEST_RETRIES + 1,
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

                if candles:

                    return (
                        "DATA",
                        candles,
                        message,
                    )

                return (
                    "NO_DATA",
                    [],
                    message
                    or "EMPTY_CANDLES",
                )

            if status in {
                "no_data",
                "nodata",
            }:

                return (
                    "NO_DATA",
                    [],
                    message
                    or "FYERS_NO_DATA",
                )

            if (
                candles == []
                and
                "no data"
                in message.lower()
            ):

                return (
                    "NO_DATA",
                    [],
                    message
                    or "FYERS_NO_DATA",
                )

            if (
                status == "error"
                and
                (
                    "bad request"
                    in message.lower()
                    or
                    str(
                        response.get(
                            "code",
                            "",
                        )
                    ) == "-99"
                )
            ):

                return (
                    "BAD_REQUEST",
                    [],
                    message
                    or "FYERS_BAD_REQUEST",
                )

            raise RuntimeError(
                "FYERS history request failed: "
                f"{response}"
            )

        except Exception as exc:

            last_error = exc

            if (
                attempt
                < MAX_REQUEST_RETRIES
            ):

                time.sleep(
                    RETRY_DELAY_SECONDS
                    * attempt
                )

    raise RuntimeError(
        "Recovery history request failed after "
        f"{MAX_REQUEST_RETRIES} attempts: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )


# ============================================================
# RANGE SPLIT
# ============================================================

def split_range(
    start_date: date,
    end_date: date,
) -> tuple[
    tuple[
        date,
        date,
    ],
    tuple[
        date,
        date,
    ],
]:

    total_days = (
        end_date
        - start_date
    ).days

    midpoint = (
        start_date
        + timedelta(
            days=(
                total_days
                // 2
            )
        )
    )

    left = (
        start_date,
        midpoint,
    )

    right = (
        midpoint
        + timedelta(
            days=1
        ),
        end_date,
    )

    return (
        left,
        right,
    )


# ============================================================
# RECURSIVE RANGE RECOVERY
# ============================================================

def recover_range_recursive(
    fyers,
    *,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
    start_date: date,
    end_date: date,
    collected_frames: list[pd.DataFrame],
    range_results: list[RangeResult],
    depth: int = 0,
) -> None:

    indent = (
        "        "
        + (
            "  "
            * depth
        )
    )

    print(
        f"{indent}"
        f"{start_date} -> "
        f"{end_date}",
        end=" ",
        flush=True,
    )

    (
        status,
        candles,
        message,
    ) = request_recovery_history(
        fyers,
        fyers_symbol=fyers_symbol,
        start_date=start_date,
        end_date=end_date,
    )

    # ========================================================
    # DATA
    # ========================================================

    if status == "DATA":

        dataframe = (
            candles_to_dataframe(
                candles,
                security_id=security_id,
                aqsd_symbol=symbol,
                fyers_symbol=fyers_symbol,
            )
        )

        if dataframe.empty:

            status = "NO_DATA"

        else:

            archive_range = DateRange(
                start_date=start_date,
                end_date=end_date,
                purpose="BAD_REQUEST_RECOVERY",
            )

            archive_file = (
                save_immutable_acquisition_chunk(
                    dataframe,
                    symbol=symbol,
                    date_range=archive_range,
                )
            )

            collected_frames.append(
                dataframe
            )

            record_acquisition_result(
                security_id=
                    security_id,
                symbol=
                    symbol,
                fyers_symbol=
                    fyers_symbol,
                range_from=
                    start_date,
                range_to=
                    end_date,
                resolution=
                    RESOLUTION,
                result_status=
                    "DATA",
                rows_received=
                    len(
                        dataframe
                    ),
                first_session=
                    str(
                        dataframe[
                            "trade_date"
                        ].min()
                    ),
                last_session=
                    str(
                        dataframe[
                            "trade_date"
                        ].max()
                    ),
                message=
                    (
                        "RECOVERY_DATA; "
                        f"IMMUTABLE_ARCHIVE="
                        f"{archive_file}"
                    ),
                module_version=
                    MODULE_VERSION,
            )

            range_results.append(
                RangeResult(
                    start_date=
                        start_date,
                    end_date=
                        end_date,
                    status=
                        "DATA",
                    rows=
                        int(
                            len(
                                dataframe
                            )
                        ),
                    message=
                        "RECOVERED",
                )
            )

            print(
                f"DATA "
                f"{len(dataframe):,} rows"
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

            return

    # ========================================================
    # NO DATA
    # ========================================================

    if status == "NO_DATA":

        record_acquisition_result(
            security_id=
                security_id,
            symbol=
                symbol,
            fyers_symbol=
                fyers_symbol,
            range_from=
                start_date,
            range_to=
                end_date,
            resolution=
                RESOLUTION,
            result_status=
                "NO_DATA",
            rows_received=
                0,
            first_session=
                None,
            last_session=
                None,
            message=
                (
                    message
                    or "RECOVERY_NO_DATA"
                ),
            module_version=
                MODULE_VERSION,
        )

        range_results.append(
            RangeResult(
                start_date=
                    start_date,
                end_date=
                    end_date,
                status=
                    "NO_DATA",
                rows=
                    0,
                message=
                    message,
            )
        )

        print(
            "NO_DATA"
        )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

        return

    # ========================================================
    # BAD REQUEST
    # ========================================================

    range_days = (
        (
            end_date
            - start_date
        ).days
        + 1
    )

    if (
        range_days
        <= MIN_SPLIT_DAYS
    ):

        record_acquisition_result(
            security_id=
                security_id,
            symbol=
                symbol,
            fyers_symbol=
                fyers_symbol,
            range_from=
                start_date,
            range_to=
                end_date,
            resolution=
                RESOLUTION,
            result_status=
                "FAILED",
            rows_received=
                0,
            first_session=
                None,
            last_session=
                None,
            message=
                (
                    "RECOVERY_BAD_REQUEST_"
                    "MINIMUM_RANGE: "
                    + message
                ),
            module_version=
                MODULE_VERSION,
        )

        range_results.append(
            RangeResult(
                start_date=
                    start_date,
                end_date=
                    end_date,
                status=
                    "FAILED",
                rows=
                    0,
                message=
                    message,
            )
        )

        print(
            "BAD_REQUEST - "
            "MINIMUM RANGE / FAILED"
        )

        return

    print(
        "BAD_REQUEST - SPLITTING"
    )

    (
        left,
        right,
    ) = split_range(
        start_date,
        end_date,
    )

    recover_range_recursive(
        fyers,
        security_id=
            security_id,
        symbol=
            symbol,
        fyers_symbol=
            fyers_symbol,
        start_date=
            left[0],
        end_date=
            left[1],
        collected_frames=
            collected_frames,
        range_results=
            range_results,
        depth=
            depth + 1,
    )

    recover_range_recursive(
        fyers,
        security_id=
            security_id,
        symbol=
            symbol,
        fyers_symbol=
            fyers_symbol,
        start_date=
            right[0],
        end_date=
            right[1],
        collected_frames=
            collected_frames,
        range_results=
            range_results,
        depth=
            depth + 1,
    )


# ============================================================
# BAD REQUEST RECOVERY
# ============================================================

def recover_bad_request(
    fyers,
    *,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
    message: str,
) -> dict[str, object]:

    if not fyers_symbol:

        raise RuntimeError(
            f"{symbol}: FYERS symbol missing "
            "from failure record."
        )

    parsed_range = (
        parse_failed_range(
            message
        )
    )

    if parsed_range is None:

        raise RuntimeError(
            f"{symbol}: could not parse "
            "failed FYERS date range."
        )

    (
        start_date,
        end_date,
    ) = parsed_range

    existing = load_existing_history(
        symbol
    )

    collected_frames: list[
        pd.DataFrame
    ] = []

    range_results: list[
        RangeResult
    ] = []

    print(
        "    Recovering FYERS "
        "Bad Request range "
        f"{start_date} -> {end_date}"
    )

    recover_range_recursive(
        fyers,
        security_id=
            security_id,
        symbol=
            symbol,
        fyers_symbol=
            fyers_symbol,
        start_date=
            start_date,
        end_date=
            end_date,
        collected_frames=
            collected_frames,
        range_results=
            range_results,
    )

    recovered_rows = int(
        sum(
            len(
                dataframe
            )
            for dataframe
            in collected_frames
        )
    )

    data_ranges = int(
        sum(
            item.status
            == "DATA"
            for item
            in range_results
        )
    )

    no_data_ranges = int(
        sum(
            item.status
            == "NO_DATA"
            for item
            in range_results
        )
    )

    failed_ranges = int(
        sum(
            item.status
            == "FAILED"
            for item
            in range_results
        )
    )

    final_rows = int(
        len(
            existing
        )
    )

    output_file = ""

    if collected_frames:

        consolidated = (
            merge_history(
                existing,
                collected_frames,
            )
        )

        validate_consolidated_history(
            consolidated,
            security_id=
                security_id,
            symbol=
                symbol,
            fyers_symbol=
                fyers_symbol,
        )

        saved_file = (
            save_consolidated_history(
                consolidated,
                symbol=symbol,
            )
        )

        output_file = str(
            saved_file
        )

        final_rows = int(
            len(
                consolidated
            )
        )

    recovery_status = (
        "SUCCESS"
        if failed_ranges == 0
        else "PARTIAL"
    )

    return {
        "symbol":
            symbol,
        "failure_type":
            "FYERS_BAD_REQUEST",
        "action":
            "RANGE_SPLIT_RECOVERY",
        "original_range_from":
            start_date.isoformat(),
        "original_range_to":
            end_date.isoformat(),
        "recovered_rows":
            recovered_rows,
        "data_ranges":
            data_ranges,
        "no_data_ranges":
            no_data_ranges,
        "failed_subranges":
            failed_ranges,
        "final_rows":
            final_rows,
        "output_file":
            output_file,
        "status":
            recovery_status,
        "message":
            (
                "Original FYERS Bad Request range "
                "was recursively split and classified."
            ),
    }


# ============================================================
# RECOVERY RUN
# ============================================================

def run_recovery() -> dict[str, object]:

    ensure_directories()

    failures = (
        load_failure_file()
    )

    if failures.empty:

        raise RuntimeError(
            "Historical failure file "
            "contains no FAILED rows."
        )

    fyers = (
        load_fyers_client()
    )

    audit_rows: list[
        dict[str, object]
    ] = []

    issue_rows: list[
        dict[str, object]
    ] = []

    print()

    print(
        "=" * 104
    )

    print(
        "AQSD MARKET PRICE HISTORICAL RECOVERY ENGINE"
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
        f"Failures To Review             : "
        f"{len(failures):,}"
    )

    print(
        f"Failure File                   : "
        f"{FAILURES_FILE}"
    )

    print(
        "Acquisition Queue              : NOT REQUIRED"
    )

    print(
        "Immutable Acquisition Archive  : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print(
        "-" * 104
    )

    for number, (_, failure) in enumerate(
        failures.iterrows(),
        start=1,
    ):

        security_id = str(
            failure[
                "security_id"
            ]
        ).strip()

        symbol = str(
            failure[
                "symbol"
            ]
        ).strip().upper()

        fyers_symbol = str(
            failure[
                "fyers_symbol"
            ]
        ).strip().upper()

        message = str(
            failure[
                "message"
            ]
        ).strip()

        failure_type = (
            classify_failure(
                message
            )
        )

        print()

        print(
            f"[{number:02d}/"
            f"{len(failures):02d}] "
            f"{symbol} | "
            f"{failure_type}"
        )

        try:

            if not security_id:

                raise RuntimeError(
                    f"{symbol}: security_id missing "
                    "from failure record."
                )

            if not fyers_symbol:

                raise RuntimeError(
                    f"{symbol}: FYERS symbol missing "
                    "from failure record."
                )

            # =================================================
            # CASE 1
            # =================================================

            if (
                failure_type
                == "NON_POSITIVE_OHLC"
            ):

                result = (
                    recover_non_positive_ohlc(
                        security_id=
                            security_id,
                        symbol=
                            symbol,
                        fyers_symbol=
                            fyers_symbol,
                    )
                )

            # =================================================
            # CASE 2
            # =================================================

            elif (
                failure_type
                == "FYERS_BAD_REQUEST"
            ):

                result = (
                    recover_bad_request(
                        fyers,
                        security_id=
                            security_id,
                        symbol=
                            symbol,
                        fyers_symbol=
                            fyers_symbol,
                        message=
                            message,
                    )
                )

            # =================================================
            # UNKNOWN
            # =================================================

            else:

                raise RuntimeError(
                    "Failure type is not supported "
                    "by current recovery engine."
                )

            result.update(
                {
                    "security_id":
                        security_id,
                    "fyers_symbol":
                        fyers_symbol,
                    "original_message":
                        message,
                    "generated_at":
                        now_text(),
                }
            )

            audit_rows.append(
                result
            )

            print(
                f"    STATUS : "
                f"{result['status']}"
            )

        except Exception as exc:

            recovery_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            issue = {
                "security_id":
                    security_id,
                "symbol":
                    symbol,
                "fyers_symbol":
                    fyers_symbol,
                "failure_type":
                    failure_type,
                "original_message":
                    message,
                "recovery_error":
                    recovery_error,
                "generated_at":
                    now_text(),
            }

            issue_rows.append(
                issue
            )

            audit_rows.append(
                {
                    "security_id":
                        security_id,
                    "symbol":
                        symbol,
                    "fyers_symbol":
                        fyers_symbol,
                    "failure_type":
                        failure_type,
                    "action":
                        "RECOVERY_FAILED",
                    "status":
                        "FAILED",
                    "message":
                        recovery_error,
                    "original_message":
                        message,
                    "generated_at":
                        now_text(),
                }
            )

            print(
                "    STATUS : FAILED"
            )

            print(
                f"    REASON : "
                f"{recovery_error}"
            )

    # ========================================================
    # WRITE AUDIT
    # ========================================================

    audit_dataframe = (
        pd.DataFrame(
            audit_rows
        )
    )

    issue_dataframe = (
        pd.DataFrame(
            issue_rows
        )
    )

    audit_dataframe.to_csv(
        RECOVERY_AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    issue_dataframe.to_csv(
        RECOVERY_ISSUES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # COUNTS
    # ========================================================

    status_series = (
        audit_dataframe.get(
            "status",
            pd.Series(
                dtype=str
            ),
        )
    )

    successful = int(
        (
            status_series
            == "SUCCESS"
        ).sum()
    )

    partial = int(
        (
            status_series
            == "PARTIAL"
        ).sum()
    )

    failed = int(
        (
            status_series
            == "FAILED"
        ).sum()
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    summary = {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "generated_at":
            now_text(),
        "failures_reviewed":
            int(
                len(
                    failures
                )
            ),
        "successful_recoveries":
            successful,
        "partial_recoveries":
            partial,
        "failed_recoveries":
            failed,
        "audit_csv":
            str(
                RECOVERY_AUDIT_CSV
            ),
        "issues_csv":
            str(
                RECOVERY_ISSUES_CSV
            ),
        "quarantine_root":
            str(
                QUARANTINE_ROOT
            ),
        "backup_root":
            str(
                BACKUP_ROOT
            ),
        "acquisition_queue_required":
            False,
        "immutable_acquisition_archive_modified":
            False,
        "historical_fabrication":
            False,
        "status":
            (
                "SUCCESS"
                if (
                    failed == 0
                    and
                    partial == 0
                )
                else "PARTIAL"
            ),
    }

    RECOVERY_SUMMARY_JSON.write_text(
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

    print(
        "=" * 104
    )

    print(
        "AQSD MARKET PRICE HISTORICAL RECOVERY SUMMARY"
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
        "-" * 104
    )

    print(
        f"Failures Reviewed              : "
        f"{int(summary['failures_reviewed']):,}"
    )

    print(
        f"Successful Recoveries          : "
        f"{int(summary['successful_recoveries']):,}"
    )

    print(
        f"Partial Recoveries             : "
        f"{int(summary['partial_recoveries']):,}"
    )

    print(
        f"Failed Recoveries              : "
        f"{int(summary['failed_recoveries']):,}"
    )

    print(
        "-" * 104
    )

    print(
        f"Audit CSV                      : "
        f"{summary['audit_csv']}"
    )

    print(
        f"Issues CSV                     : "
        f"{summary['issues_csv']}"
    )

    print(
        f"Quarantine                     : "
        f"{summary['quarantine_root']}"
    )

    print(
        f"Backup                         : "
        f"{summary['backup_root']}"
    )

    print(
        "-" * 104
    )

    print(
        "Acquisition Queue              : NOT REQUIRED"
    )

    print(
        "Immutable Acquisition Archive  : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
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

        summary = (
            run_recovery()
        )

        display_summary(
            summary
        )

    except KeyboardInterrupt:

        print()

        print(
            "=" * 104
        )

        print(
            "AQSD MARKET PRICE HISTORICAL RECOVERY ENGINE"
        )

        print(
            "=" * 104
        )

        print(
            "Status                         : INTERRUPTED"
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
            "AQSD MARKET PRICE HISTORICAL RECOVERY ENGINE"
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
            "Acquisition Queue              : NOT REQUIRED"
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