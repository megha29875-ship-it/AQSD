"""
AQSD
NSE Market Price Canonical Builder

Module : MPD-004
Version: 1.1.0
Author : AQSD

Purpose
-------
Build a controlled canonical UNDERLYING market-price staging dataset.

This module DOES NOT write to the Market Price database.

It creates a canonical CSV that can later be validated by MPD-005
before any database ingestion occurs.

Architecture
------------
Approved source(s)
      ↓
Column normalization
      ↓
Symbol normalization
      ↓
Security Master reconciliation
      ↓
Trading-date checks
      ↓
OHLCV quality checks
      ↓
Source priority resolution
      ↓
Canonical staging dataset

Primary Key
-----------
trade_date + symbol

Protection
----------
- Frozen NSE F&O database is READ ONLY / untouched
- Security Master is READ ONLY
- AQSD_Market_Price.db is NOT MODIFIED
- No historical fabrication
- No futures/options substitution
"""

from __future__ import annotations

import json
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-004"
MODULE_VERSION: Final[str] = "1.1.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

SECURITY_MASTER_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Output"
    / "AQSD_Security_Master_Enriched.csv"
)

HISTORICAL_ROOT: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "Historical"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

CANONICAL_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical.csv"
)

REJECTS_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Rejects.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Summary.json"
)


# ============================================================
# SOURCE POLICY
# ============================================================

SOURCE_NAME: Final[str] = "MARKET_STRUCTURE_HISTORY"
SOURCE_PRIORITY: Final[int] = 100
SOURCE_FILE_PATTERN: Final[str] = "market_structure.csv"


# ============================================================
# CANONICAL COLUMNS
# ============================================================

CANONICAL_COLUMNS: Final[list[str]] = [
    "trade_date",
    "security_id",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "source_priority",
    "quality_status",
]


# ============================================================
# HELPERS
# ============================================================

def ensure_output_directory() -> None:
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


def normalize_market_symbol(
    value: object,
) -> str:
    """
    Convert external/provider symbols into canonical AQSD symbols.

    Examples
    --------
    NSE:NIFTYBANK-INDEX -> BANKNIFTY
    NSE:NIFTY50-INDEX   -> NIFTY
    NSE:RELIANCE-EQ     -> RELIANCE
    """

    if value is None:
        return ""

    symbol = str(value).strip().upper()

    if not symbol:
        return ""

    aliases = {
        "NSE:NIFTYBANK-INDEX": "BANKNIFTY",
        "NIFTYBANK-INDEX": "BANKNIFTY",
        "NIFTYBANK": "BANKNIFTY",

        "NSE:NIFTY50-INDEX": "NIFTY",
        "NIFTY50-INDEX": "NIFTY",
        "NIFTY50": "NIFTY",
    }

    if symbol in aliases:
        return aliases[symbol]

    if symbol.startswith("NSE:"):
        symbol = symbol[4:]

    if symbol.endswith("-EQ"):
        symbol = symbol[:-3]

    return symbol.strip()


# ============================================================
# SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Security Master not found: {SECURITY_MASTER_FILE}"
        )

    dataframe = pd.read_csv(
        SECURITY_MASTER_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    required = {
        "symbol",
        "security_id",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:
        raise RuntimeError(
            "Security Master missing required columns: "
            + ", ".join(missing)
        )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .astype(str)
        .str.strip()
    )

    dataframe = (
        dataframe[
            [
                "symbol",
                "security_id",
            ]
        ]
        .drop_duplicates(
            subset=["symbol"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return dataframe


# ============================================================
# SOURCE DISCOVERY
# ============================================================

def discover_source_files() -> list[Path]:

    if not HISTORICAL_ROOT.exists():
        raise FileNotFoundError(
            f"Historical root not found: {HISTORICAL_ROOT}"
        )

    return sorted(
        HISTORICAL_ROOT.rglob(
            SOURCE_FILE_PATTERN
        )
    )


# ============================================================
# SOURCE READING
# ============================================================

def read_source_file(
    path: Path,
) -> pd.DataFrame:

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    aliases = {
        "date": "trade_date",
        "trading_date": "trade_date",
        "ticker": "symbol",
        "security": "symbol",
        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",
        "total_traded_quantity": "volume",
        "traded_quantity": "volume",
    }

    rename_map: dict[str, str] = {}

    for old_name, new_name in aliases.items():
        if (
            old_name in dataframe.columns
            and new_name not in dataframe.columns
        ):
            rename_map[old_name] = new_name

    if rename_map:
        dataframe = dataframe.rename(
            columns=rename_map
        )

    required = {
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:
        raise RuntimeError(
            f"{path}: missing required columns: "
            + ", ".join(missing)
        )

    dataframe = dataframe[
        [
            "trade_date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ].copy()

    dataframe["source_file"] = str(path)

    return dataframe


# ============================================================
# STANDARDIZATION
# ============================================================

def standardize_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = dataframe.copy()

    dataframe["trade_date"] = pd.to_datetime(
        dataframe["trade_date"],
        errors="coerce",
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .apply(normalize_market_symbol)
    )

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

    return dataframe


# ============================================================
# QUALITY RULES
# ============================================================

def apply_quality_rules(
    dataframe: pd.DataFrame,
    *,
    security_master: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    dataframe = dataframe.copy()

    dataframe = dataframe.merge(
        security_master,
        how="left",
        on="symbol",
    )

    dataframe["reject_reason"] = ""

    invalid_date = (
        dataframe["trade_date"].isna()
    )

    dataframe.loc[
        invalid_date,
        "reject_reason",
    ] += "INVALID_DATE;"

    future_date = (
        dataframe["trade_date"].notna()
        &
        (
            dataframe["trade_date"].dt.date
            > date.today()
        )
    )

    dataframe.loc[
        future_date,
        "reject_reason",
    ] += "FUTURE_DATE;"

    blank_symbol = (
        dataframe["symbol"].isna()
        |
        dataframe["symbol"].eq("")
    )

    dataframe.loc[
        blank_symbol,
        "reject_reason",
    ] += "BLANK_SYMBOL;"

    unknown_symbol = (
        dataframe["security_id"].isna()
    )

    dataframe.loc[
        unknown_symbol,
        "reject_reason",
    ] += "UNKNOWN_SYMBOL;"

    null_ohlc = (
        dataframe[
            [
                "open",
                "high",
                "low",
                "close",
            ]
        ]
        .isna()
        .any(axis=1)
    )

    dataframe.loc[
        null_ohlc,
        "reject_reason",
    ] += "NULL_OHLC;"

    non_positive_price = (
        dataframe[
            [
                "open",
                "high",
                "low",
                "close",
            ]
        ]
        .le(0)
        .any(axis=1)
    )

    dataframe.loc[
        non_positive_price,
        "reject_reason",
    ] += "NON_POSITIVE_PRICE;"

    invalid_ohlc = (
        (
            dataframe["high"]
            < dataframe["low"]
        )
        |
        (
            dataframe["open"]
            < dataframe["low"]
        )
        |
        (
            dataframe["open"]
            > dataframe["high"]
        )
        |
        (
            dataframe["close"]
            < dataframe["low"]
        )
        |
        (
            dataframe["close"]
            > dataframe["high"]
        )
    )

    dataframe.loc[
        invalid_ohlc,
        "reject_reason",
    ] += "INVALID_OHLC;"

    negative_volume = (
        dataframe["volume"] < 0
    )

    dataframe.loc[
        negative_volume,
        "reject_reason",
    ] += "NEGATIVE_VOLUME;"

    accepted = dataframe[
        dataframe["reject_reason"].eq("")
    ].copy()

    rejected = dataframe[
        dataframe["reject_reason"].ne("")
    ].copy()

    return accepted, rejected


# ============================================================
# CANONICALIZATION
# ============================================================

def canonicalize(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = dataframe.copy()

    dataframe["trade_date"] = (
        dataframe["trade_date"]
        .dt.strftime("%Y-%m-%d")
    )

    dataframe["source"] = SOURCE_NAME
    dataframe["source_priority"] = SOURCE_PRIORITY
    dataframe["quality_status"] = "PASS"

    dataframe = dataframe.sort_values(
        by=[
            "trade_date",
            "symbol",
            "source_priority",
        ],
        ascending=[
            True,
            True,
            False,
        ],
    )

    dataframe = dataframe.drop_duplicates(
        subset=[
            "trade_date",
            "symbol",
        ],
        keep="first",
    )

    dataframe = dataframe[
        CANONICAL_COLUMNS
    ].copy()

    return dataframe


# ============================================================
# DUPLICATE CHECK
# ============================================================

def count_duplicate_keys(
    dataframe: pd.DataFrame,
) -> int:

    return int(
        dataframe.duplicated(
            subset=[
                "trade_date",
                "symbol",
            ],
            keep=False,
        ).sum()
    )


# ============================================================
# REJECTION DIAGNOSTICS
# ============================================================

def display_rejection_diagnostics(
    rejected_all: pd.DataFrame,
) -> None:

    if rejected_all.empty:
        return

    print()
    print("=" * 96)
    print("REJECTION DIAGNOSTICS")
    print("=" * 96)

    print(
        rejected_all["reject_reason"]
        .value_counts(dropna=False)
        .to_string()
    )

    print()
    print("SAMPLE REJECTED ROWS")
    print("-" * 96)

    columns_to_show = [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "security_id",
        "reject_reason",
    ]

    available_columns = [
        column
        for column in columns_to_show
        if column in rejected_all.columns
    ]

    print(
        rejected_all[
            available_columns
        ]
        .head(10)
        .to_string(index=False)
    )


# ============================================================
# RUN BUILDER
# ============================================================

def run_builder() -> dict[str, object]:

    ensure_output_directory()

    security_master = load_security_master()
    source_files = discover_source_files()

    if not source_files:
        raise RuntimeError(
            "No approved source files were found."
        )

    accepted_frames: list[pd.DataFrame] = []
    rejected_frames: list[pd.DataFrame] = []

    total_source_rows = 0
    files_loaded = 0
    files_failed = 0

    print()
    print(
        f"Approved Source Files       : "
        f"{len(source_files)}"
    )

    for number, path in enumerate(
        source_files,
        start=1,
    ):

        print(
            f"[{number:03d}/{len(source_files):03d}] "
            f"{path.parent.name} ",
            end="",
            flush=True,
        )

        try:

            dataframe = read_source_file(
                path
            )

            dataframe = standardize_dataframe(
                dataframe
            )

            total_source_rows += len(
                dataframe
            )

            accepted, rejected = apply_quality_rules(
                dataframe,
                security_master=security_master,
            )

            if not accepted.empty:
                accepted_frames.append(
                    accepted
                )

            if not rejected.empty:
                rejected_frames.append(
                    rejected
                )

            files_loaded += 1

            print(
                f"SUCCESS | "
                f"Rows={len(dataframe):,} | "
                f"Accepted={len(accepted):,} | "
                f"Rejected={len(rejected):,}"
            )

        except Exception as exc:

            files_failed += 1

            print(
                f"FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

    if accepted_frames:
        accepted_all = pd.concat(
            accepted_frames,
            ignore_index=True,
        )
    else:
        accepted_all = pd.DataFrame()

    if rejected_frames:
        rejected_all = pd.concat(
            rejected_frames,
            ignore_index=True,
        )
    else:
        rejected_all = pd.DataFrame()

    if accepted_all.empty:

        if not rejected_all.empty:

            display_rejection_diagnostics(
                rejected_all
            )

            rejected_all.to_csv(
                REJECTS_CSV,
                index=False,
                encoding="utf-8-sig",
            )

            print()
            print(
                f"Rejects CSV : {REJECTS_CSV}"
            )

        raise RuntimeError(
            "No valid canonical price rows were produced."
        )

    canonical = canonicalize(
        accepted_all
    )

    duplicate_keys = count_duplicate_keys(
        canonical
    )

    if duplicate_keys != 0:
        raise RuntimeError(
            f"Canonical dataset contains "
            f"{duplicate_keys} duplicate keys."
        )

    canonical.to_csv(
        CANONICAL_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    if not rejected_all.empty:

        rejected_all.to_csv(
            REJECTS_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    else:

        pd.DataFrame(
            columns=[
                "trade_date",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source_file",
                "security_id",
                "reject_reason",
            ]
        ).to_csv(
            REJECTS_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    unique_symbols = int(
        canonical["symbol"].nunique()
    )

    sessions = int(
        canonical["trade_date"].nunique()
    )

    first_session = (
        canonical["trade_date"].min()
    )

    last_session = (
        canonical["trade_date"].max()
    )

    security_master_symbols = int(
        security_master["symbol"].nunique()
    )

    coverage_percent = round(
        (
            unique_symbols
            / security_master_symbols
        )
        * 100,
        2,
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

        "source_name":
            SOURCE_NAME,

        "source_priority":
            SOURCE_PRIORITY,

        "source_files_found":
            len(source_files),

        "files_loaded":
            files_loaded,

        "files_failed":
            files_failed,

        "source_rows":
            total_source_rows,

        "canonical_rows":
            len(canonical),

        "rejected_rows":
            len(rejected_all),

        "duplicate_keys":
            duplicate_keys,

        "unique_symbols":
            unique_symbols,

        "security_master_symbols":
            security_master_symbols,

        "coverage_percent":
            coverage_percent,

        "trading_sessions":
            sessions,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "canonical_csv":
            str(CANONICAL_CSV),

        "rejects_csv":
            str(REJECTS_CSV),

        "market_price_database_modified":
            False,

        "frozen_fno_database_modified":
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
    print("=" * 96)
    print("AQSD MARKET PRICE CANONICAL BUILDER")
    print("=" * 96)

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Source                         : "
        f"{summary['source_name']}"
    )

    print("-" * 96)

    print(
        f"Source Files Found             : "
        f"{summary['source_files_found']}"
    )

    print(
        f"Files Loaded                   : "
        f"{summary['files_loaded']}"
    )

    print(
        f"Files Failed                   : "
        f"{summary['files_failed']}"
    )

    print(
        f"Source Rows                    : "
        f"{int(summary['source_rows']):,}"
    )

    print(
        f"Canonical Rows                 : "
        f"{int(summary['canonical_rows']):,}"
    )

    print(
        f"Rejected Rows                  : "
        f"{int(summary['rejected_rows']):,}"
    )

    print(
        f"Duplicate Keys                 : "
        f"{int(summary['duplicate_keys']):,}"
    )

    print("-" * 96)

    print(
        f"Unique Symbols                 : "
        f"{int(summary['unique_symbols']):,}"
    )

    print(
        f"Security Master Symbols        : "
        f"{int(summary['security_master_symbols']):,}"
    )

    print(
        f"Coverage                       : "
        f"{summary['coverage_percent']}%"
    )

    print(
        f"Trading Sessions               : "
        f"{int(summary['trading_sessions']):,}"
    )

    print(
        f"First Session                  : "
        f"{summary['first_session']}"
    )

    print(
        f"Last Session                   : "
        f"{summary['last_session']}"
    )

    print("-" * 96)

    print(
        f"Canonical CSV                  : "
        f"{CANONICAL_CSV}"
    )

    print(
        f"Rejects CSV                    : "
        f"{REJECTS_CSV}"
    )

    print(
        f"Summary JSON                   : "
        f"{SUMMARY_JSON}"
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

    print("-" * 96)

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    print("=" * 96)


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

        traceback.print_exc()

        print()
        print("=" * 96)
        print("AQSD MARKET PRICE CANONICAL BUILDER")
        print("=" * 96)

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

        print("=" * 96)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()