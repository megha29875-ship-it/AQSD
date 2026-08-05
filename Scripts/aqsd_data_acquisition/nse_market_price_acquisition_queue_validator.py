"""
AQSD
Market Price Acquisition Queue Validator

Module ID: MPD-006
Version: 1.0.0
Author: AQSD

Purpose
-------
Validate the Market Price Acquisition Queue produced after the
official NSE F&O universe has been reconciled and promoted.

This module performs NO market-data download.

Protection
----------
Security Master        : READ ONLY
Acquisition Queue      : READ ONLY
Market Price Database  : NOT MODIFIED
Historical Database    : NOT MODIFIED
FYERS API              : NOT CALLED
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "MPD-006"
MODULE_VERSION: Final[str] = "1.0.0"


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "Output"

QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Acquisition_Queue.csv"
)

FNO005_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Universe_Summary.json"
)

VALIDATED_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Acquisition_Queue_Validated.csv"
)

REJECTED_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Acquisition_Queue_Rejected.csv"
)

AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Acquisition_Queue_Validation_Audit.csv"
)

SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR / "AQSD_Market_Price_Acquisition_Queue_Validation_Summary.json"
)


# ============================================================
# HELPERS
# ============================================================

def separator() -> None:
    print("=" * 100)


def sub_separator() -> None:
    print("-" * 100)


def normalize_column_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("(", "")
        .replace(")", "")
    )


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_symbol(value: object) -> str:
    return clean_text(value).upper()


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input_files() -> None:

    missing = [
        path
        for path in (
            QUEUE_FILE,
            FNO005_SUMMARY_FILE,
        )
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing MPD-006 input file(s): "
            + ", ".join(str(path) for path in missing)
        )


# ============================================================
# FNO-005 GATE
# ============================================================

def validate_fno005() -> dict[str, object]:

    summary = json.loads(
        FNO005_SUMMARY_FILE.read_text(
            encoding="utf-8"
        )
    )

    status = clean_text(
        summary.get("status", "")
    ).upper()

    critical_issues = int(
        summary.get("critical_issues", 0)
    )

    universe_matches_live = bool(
        summary.get(
            "universe_matches_live",
            False,
        )
    )

    queue_reconciles = bool(
        summary.get(
            "queue_reconciles",
            False,
        )
    )

    if status != "SUCCESS":
        raise RuntimeError(
            "FNO-005 status is not SUCCESS."
        )

    if critical_issues != 0:
        raise RuntimeError(
            "FNO-005 contains critical issues."
        )

    if not universe_matches_live:
        raise RuntimeError(
            "FNO-005 universe does not match live F&O membership."
        )

    if not queue_reconciles:
        raise RuntimeError(
            "FNO-005 acquisition queue does not reconcile."
        )

    return summary


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue() -> pd.DataFrame:

    dataframe = pd.read_csv(
        QUEUE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    required_columns = {
        "security_id",
        "symbol",
        "resolved_fyers_symbol",
        "queue_status",
    }

    missing = required_columns - set(
        dataframe.columns
    )

    if missing:
        raise RuntimeError(
            "Acquisition Queue missing required columns: "
            + ", ".join(sorted(missing))
        )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .map(normalize_symbol)
    )

    dataframe["resolved_fyers_symbol"] = (
        dataframe["resolved_fyers_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["queue_status"] = (
        dataframe["queue_status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return dataframe


# ============================================================
# SYMBOL VALIDATION
# ============================================================

def valid_security_id(value: str) -> bool:

    return bool(
        re.fullmatch(
            r"SMD-\d{4,}",
            value,
        )
    )


def valid_fyers_symbol(value: str) -> bool:

    if not value:
        return False

    if not value.startswith("NSE:"):
        return False

    if value.endswith("-EQ"):
        return True

    if value.endswith("-INDEX"):
        return True

    return False


# ============================================================
# ROW VALIDATION
# ============================================================

def validate_rows(
    queue: pd.DataFrame,
) -> pd.DataFrame:

    validated = queue.copy()

    reasons: list[str] = []

    for _, row in validated.iterrows():

        row_reasons: list[str] = []

        security_id = clean_text(
            row["security_id"]
        )

        symbol = normalize_symbol(
            row["symbol"]
        )

        fyers_symbol = normalize_symbol(
            row["resolved_fyers_symbol"]
        )

        queue_status = normalize_symbol(
            row["queue_status"]
        )

        if not security_id:
            row_reasons.append(
                "BLANK_SECURITY_ID"
            )

        elif not valid_security_id(
            security_id
        ):
            row_reasons.append(
                "INVALID_SECURITY_ID"
            )

        if not symbol:
            row_reasons.append(
                "BLANK_SYMBOL"
            )

        if not fyers_symbol:
            row_reasons.append(
                "BLANK_FYERS_SYMBOL"
            )

        elif not valid_fyers_symbol(
            fyers_symbol
        ):
            row_reasons.append(
                "INVALID_FYERS_SYMBOL_FORMAT"
            )

        if queue_status != "READY":
            row_reasons.append(
                "QUEUE_NOT_READY"
            )

        reasons.append(
            "|".join(row_reasons)
        )

    validated[
        "validation_reason"
    ] = reasons

    validated[
        "validation_pass"
    ] = (
        validated[
            "validation_reason"
        ].eq("")
    )

    return validated


# ============================================================
# DUPLICATE VALIDATION
# ============================================================

def apply_duplicate_checks(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    result = dataframe.copy()

    duplicate_security_id = (
        result.duplicated(
            subset=["security_id"],
            keep=False,
        )
    )

    duplicate_symbol = (
        result.duplicated(
            subset=["symbol"],
            keep=False,
        )
    )

    duplicate_fyers_symbol = (
        result.duplicated(
            subset=["resolved_fyers_symbol"],
            keep=False,
        )
    )

    for index in result.index:

        duplicate_reasons: list[str] = []

        if duplicate_security_id.loc[index]:
            duplicate_reasons.append(
                "DUPLICATE_SECURITY_ID"
            )

        if duplicate_symbol.loc[index]:
            duplicate_reasons.append(
                "DUPLICATE_SYMBOL"
            )

        if duplicate_fyers_symbol.loc[index]:
            duplicate_reasons.append(
                "DUPLICATE_FYERS_SYMBOL"
            )

        if duplicate_reasons:

            existing = clean_text(
                result.at[
                    index,
                    "validation_reason",
                ]
            )

            additions = "|".join(
                duplicate_reasons
            )

            if existing:
                result.at[
                    index,
                    "validation_reason",
                ] = (
                    existing
                    + "|"
                    + additions
                )
            else:
                result.at[
                    index,
                    "validation_reason",
                ] = additions

    result[
        "validation_pass"
    ] = (
        result[
            "validation_reason"
        ].eq("")
    )

    return result


# ============================================================
# FINAL QUEUES
# ============================================================

def split_queue(
    validated: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    accepted = validated[
        validated["validation_pass"]
    ].copy()

    rejected = validated[
        ~validated["validation_pass"]
    ].copy()

    accepted[
        "validated_queue_status"
    ] = "READY_FOR_DOWNLOAD"

    rejected[
        "validated_queue_status"
    ] = "REJECTED"

    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    accepted[
        "validated_at"
    ] = timestamp

    rejected[
        "validated_at"
    ] = timestamp

    accepted = (
        accepted
        .sort_values("symbol")
        .reset_index(drop=True)
    )

    rejected = (
        rejected
        .sort_values("symbol")
        .reset_index(drop=True)
    )

    return accepted, rejected


# ============================================================
# GLOBAL VALIDATION
# ============================================================

def calculate_validation(
    source_queue: pd.DataFrame,
    accepted: pd.DataFrame,
    rejected: pd.DataFrame,
    fno005_summary: dict[str, object],
) -> dict[str, object]:

    source_rows = len(
        source_queue
    )

    accepted_rows = len(
        accepted
    )

    rejected_rows = len(
        rejected
    )

    queue_reconciles = (
        accepted_rows
        + rejected_rows
        == source_rows
    )

    expected_rows = int(
        fno005_summary.get(
            "acquisition_ready",
            0,
        )
    )

    matches_fno005 = (
        source_rows
        == expected_rows
    )

    duplicate_security_ids = int(
        source_queue.duplicated(
            subset=["security_id"],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        source_queue.duplicated(
            subset=["symbol"],
            keep=False,
        ).sum()
    )

    duplicate_fyers_symbols = int(
        source_queue.duplicated(
            subset=["resolved_fyers_symbol"],
            keep=False,
        ).sum()
    )

    critical_issues = (
        rejected_rows
        + duplicate_security_ids
        + duplicate_symbols
        + duplicate_fyers_symbols
    )

    if not queue_reconciles:
        critical_issues += 1

    if not matches_fno005:
        critical_issues += 1

    return {
        "source_queue_rows":
            source_rows,

        "expected_fno005_rows":
            expected_rows,

        "validated_rows":
            accepted_rows,

        "rejected_rows":
            rejected_rows,

        "matches_fno005":
            matches_fno005,

        "queue_reconciles":
            queue_reconciles,

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "duplicate_fyers_symbols":
            duplicate_fyers_symbols,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# OUTPUT
# ============================================================

def write_outputs(
    accepted: pd.DataFrame,
    rejected: pd.DataFrame,
    summary: dict[str, object],
) -> None:

    accepted.to_csv(
        VALIDATED_QUEUE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    rejected.to_csv(
        REJECTED_QUEUE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [summary]
    ).to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# RUNNER
# ============================================================

def run_validator() -> dict[str, object]:

    validate_input_files()

    fno005_summary = validate_fno005()

    source_queue = load_queue()

    validated = validate_rows(
        source_queue
    )

    validated = apply_duplicate_checks(
        validated
    )

    accepted, rejected = split_queue(
        validated
    )

    validation = calculate_validation(
        source_queue,
        accepted,
        rejected,
        fno005_summary,
    )

    status = (
        "SUCCESS"
        if validation["critical_issues"] == 0
        else "FAILED"
    )

    summary = {
        "module_id":
            MODULE_ID,

        "module_version":
            MODULE_VERSION,

        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),

        **validation,

        "validated_queue_file":
            str(VALIDATED_QUEUE_FILE),

        "rejected_queue_file":
            str(REJECTED_QUEUE_FILE),

        "source_queue_modified":
            False,

        "security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "historical_database_modified":
            False,

        "fyers_api_called":
            False,

        "status":
            status,
    }

    write_outputs(
        accepted,
        rejected,
        summary,
    )

    return summary


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()
    separator()

    print(
        "AQSD MARKET PRICE ACQUISITION QUEUE VALIDATOR"
    )

    separator()

    print(
        f"Module                         : "
        f"{summary['module_id']}"
    )

    print(
        f"Version                        : "
        f"{summary['module_version']}"
    )

    sub_separator()

    print(
        f"Source Queue Rows              : "
        f"{summary['source_queue_rows']:,}"
    )

    print(
        f"Expected FNO-005 Rows          : "
        f"{summary['expected_fno005_rows']:,}"
    )

    print(
        f"Validated Download Rows        : "
        f"{summary['validated_rows']:,}"
    )

    print(
        f"Rejected Rows                  : "
        f"{summary['rejected_rows']:,}"
    )

    sub_separator()

    print(
        f"Matches FNO-005                : "
        f"{summary['matches_fno005']}"
    )

    print(
        f"Queue Reconciles               : "
        f"{summary['queue_reconciles']}"
    )

    print(
        f"Duplicate Security IDs         : "
        f"{summary['duplicate_security_ids']:,}"
    )

    print(
        f"Duplicate Symbols              : "
        f"{summary['duplicate_symbols']:,}"
    )

    print(
        f"Duplicate FYERS Symbols        : "
        f"{summary['duplicate_fyers_symbols']:,}"
    )

    print(
        f"Critical Issues                : "
        f"{summary['critical_issues']:,}"
    )

    sub_separator()

    print(
        f"Validated Queue                : "
        f"{summary['validated_queue_file']}"
    )

    print(
        f"Rejected Queue                 : "
        f"{summary['rejected_queue_file']}"
    )

    sub_separator()

    print(
        "FYERS API                      : NOT CALLED"
    )

    print(
        "Security Master                : READ ONLY"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Historical Database            : NOT MODIFIED"
    )

    sub_separator()

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    separator()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_validator()

        display_summary(
            summary
        )

        if summary["status"] != "SUCCESS":
            raise SystemExit(1)

    except Exception as exc:

        print()
        separator()

        print(
            "AQSD MARKET PRICE ACQUISITION QUEUE VALIDATOR"
        )

        separator()

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "FYERS API                      : NOT CALLED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()