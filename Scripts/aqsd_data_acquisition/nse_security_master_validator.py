"""
AQSD
NSE F&O Security Master Validator

Module: SMD-002
Version: 1.0.0

Purpose
-------
Validate the AQSD Security Master produced by SMD-001.

This module is READ ONLY.

It does NOT:
- modify the historical database
- rebuild historical data
- modify the security master
- fabricate missing data

It validates:
- file availability
- row count
- column structure
- security_id integrity
- duplicate security IDs
- duplicate symbols
- blank/null symbols
- blank/null security IDs
- basic master consistency

Input
-----
Output/AQSD_Security_Master.csv

Output
------
Output/AQSD_Security_Master_Validation.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-002"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

SECURITY_MASTER_CSV = OUTPUT_DIR / "AQSD_Security_Master.csv"

VALIDATION_JSON = (
    OUTPUT_DIR / "AQSD_Security_Master_Validation.json"
)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def print_header() -> None:
    print()
    print("=" * 76)
    print("AQSD SECURITY MASTER VALIDATOR")
    print("=" * 76)
    print(f"Module                 : {MODULE_ID}")
    print(f"Version                : {MODULE_VERSION}")
    print("Mode                   : READ ONLY")
    print("Historical Database    : UNTOUCHED")
    print("=" * 76)


def normalize_column_name(value: object) -> str:
    return str(value).strip().lower()


def blank_mask(series: pd.Series) -> pd.Series:
    """
    Return True for null, empty or whitespace-only values.
    """

    return (
        series.isna()
        | series.astype(str).str.strip().eq("")
        | series.astype(str).str.strip().str.lower().eq("nan")
    )


# ============================================================
# LOAD SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_CSV.exists():
        raise FileNotFoundError(
            f"Security Master not found: {SECURITY_MASTER_CSV}"
        )

    dataframe = pd.read_csv(
        SECURITY_MASTER_CSV,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    return dataframe


# ============================================================
# COLUMN DETECTION
# ============================================================

def find_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
) -> str | None:

    available = set(dataframe.columns)

    for candidate in candidates:
        candidate = candidate.lower()

        if candidate in available:
            return candidate

    return None


def detect_columns(
    dataframe: pd.DataFrame,
) -> dict[str, str | None]:

    security_id_column = find_column(
        dataframe,
        [
            "security_id",
            "securityid",
            "aqsd_security_id",
            "id",
        ],
    )

    symbol_column = find_column(
        dataframe,
        [
            "symbol",
            "underlying",
            "underlying_symbol",
            "ticker",
            "nse_symbol",
        ],
    )

    return {
        "security_id": security_id_column,
        "symbol": symbol_column,
    }


# ============================================================
# VALIDATION ENGINE
# ============================================================

def validate_security_master(
    dataframe: pd.DataFrame,
) -> dict[str, object]:

    detected = detect_columns(dataframe)

    security_id_column = detected["security_id"]
    symbol_column = detected["symbol"]

    issues: list[str] = []

    row_count = len(dataframe)

    # --------------------------------------------------------
    # SECURITY ID VALIDATION
    # --------------------------------------------------------

    blank_security_ids = 0
    duplicate_security_ids = 0

    if security_id_column is None:

        issues.append(
            "Security ID column could not be identified."
        )

    else:

        blank_security_ids = int(
            blank_mask(
                dataframe[security_id_column]
            ).sum()
        )

        valid_ids = dataframe.loc[
            ~blank_mask(dataframe[security_id_column]),
            security_id_column,
        ].astype(str).str.strip()

        duplicate_security_ids = int(
            valid_ids.duplicated(
                keep=False
            ).sum()
        )

        if blank_security_ids:
            issues.append(
                f"{blank_security_ids} blank security IDs found."
            )

        if duplicate_security_ids:
            issues.append(
                f"{duplicate_security_ids} rows contain "
                "duplicate security IDs."
            )

    # --------------------------------------------------------
    # SYMBOL VALIDATION
    # --------------------------------------------------------

    blank_symbols = 0
    duplicate_symbols = 0
    unique_symbols = 0

    if symbol_column is None:

        issues.append(
            "Symbol column could not be identified."
        )

    else:

        blank_symbols = int(
            blank_mask(
                dataframe[symbol_column]
            ).sum()
        )

        valid_symbols = dataframe.loc[
            ~blank_mask(dataframe[symbol_column]),
            symbol_column,
        ].astype(str).str.strip().str.upper()

        unique_symbols = int(
            valid_symbols.nunique()
        )

        duplicate_symbols = int(
            valid_symbols.duplicated(
                keep=False
            ).sum()
        )

        if blank_symbols:
            issues.append(
                f"{blank_symbols} blank symbols found."
            )

        if duplicate_symbols:
            issues.append(
                f"{duplicate_symbols} rows contain "
                "duplicate symbols."
            )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    critical_issues = (
        blank_security_ids
        + duplicate_security_ids
        + blank_symbols
        + duplicate_symbols
    )

    if security_id_column is None:
        critical_issues += 1

    if symbol_column is None:
        critical_issues += 1

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "REVIEW REQUIRED"
    )

    return {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "status": status,
        "security_master_file": str(
            SECURITY_MASTER_CSV
        ),
        "rows": row_count,
        "columns": len(dataframe.columns),
        "detected_security_id_column":
            security_id_column,
        "detected_symbol_column":
            symbol_column,
        "unique_symbols": unique_symbols,
        "blank_security_ids":
            blank_security_ids,
        "duplicate_security_ids":
            duplicate_security_ids,
        "blank_symbols":
            blank_symbols,
        "duplicate_symbols":
            duplicate_symbols,
        "critical_issues":
            critical_issues,
        "issues": issues,
    }


# ============================================================
# SAVE VALIDATION REPORT
# ============================================================

def save_validation_report(
    report: dict[str, object],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with VALIDATION_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False,
        )


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_report(
    report: dict[str, object],
) -> None:

    print()
    print("-" * 76)
    print("SECURITY MASTER INTEGRITY")
    print("-" * 76)

    print(
        f"Security Master Rows   : "
        f"{report['rows']:,}"
    )

    print(
        f"Columns                : "
        f"{report['columns']}"
    )

    print(
        f"Unique Symbols         : "
        f"{report['unique_symbols']:,}"
    )

    print()
    print(
        f"Blank Security IDs     : "
        f"{report['blank_security_ids']}"
    )

    print(
        f"Duplicate Security IDs : "
        f"{report['duplicate_security_ids']}"
    )

    print(
        f"Blank Symbols          : "
        f"{report['blank_symbols']}"
    )

    print(
        f"Duplicate Symbols      : "
        f"{report['duplicate_symbols']}"
    )

    print(
        f"Critical Issues        : "
        f"{report['critical_issues']}"
    )

    print()
    print("-" * 76)
    print("AQSD PROTECTION")
    print("-" * 76)

    print("Historical Database    : READ ONLY / UNTOUCHED")
    print("Historical Rebuild     : NOT USED")
    print("Security Master Modify : NOT USED")

    print()
    print(
        f"Validation JSON        : "
        f"{VALIDATION_JSON}"
    )

    print()
    print("=" * 76)
    print(
        f"Status                 : "
        f"{report['status']}"
    )
    print("=" * 76)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print_header()

    try:

        dataframe = load_security_master()

        report = validate_security_master(
            dataframe
        )

        save_validation_report(
            report
        )

        display_report(
            report
        )

        if report["status"] != "SUCCESS":
            raise SystemExit(1)

    except Exception as exc:

        print()
        print("=" * 76)
        print("Status                 : FAILED")
        print(
            f"Reason                 : "
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 76)

        raise


if __name__ == "__main__":
    main()