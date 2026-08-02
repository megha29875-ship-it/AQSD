"""
AQSD
NSE Security Master Enrichment Validator

Module : SMD-004
Version: 1.0.0
Author : AQSD

Purpose
-------
Validate the enriched AQSD Security Master created by SMD-003.

This module is READ ONLY.

It validates:
- enriched file availability
- row count consistency
- unique symbol consistency
- duplicate symbols
- blank symbols
- security type validity
- instrument class validity
- index/stock classification consistency
- F&O flag consistency
- AQSD scope consistency
- enrichment status/source availability

It does NOT:
- modify the historical database
- rebuild historical data
- modify the source Security Master
- modify the enriched Security Master
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-004"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

INPUT_CSV = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

VALIDATION_JSON = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enrichment_Validation.json"
)


# ============================================================
# VALID VALUES
# ============================================================

VALID_SECURITY_TYPES = {
    "INDEX",
    "EQUITY",
}

VALID_INSTRUMENT_CLASSES = {
    "INDEX_UNDERLYING",
    "STOCK_UNDERLYING",
}

VALID_YES_NO = {
    "YES",
    "NO",
}

VALID_AQSD_SCOPES = {
    "NSE_FNO_UNIVERSE",
    "NSE_SECURITY",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_column_name(
    value: object,
) -> str:
    return str(value).strip().lower()


def normalize_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def blank_mask(
    series: pd.Series,
) -> pd.Series:

    return (
        series.isna()
        | series.astype(str).str.strip().eq("")
        | series.astype(str)
        .str.strip()
        .str.lower()
        .eq("nan")
    )


def load_enriched_master() -> pd.DataFrame:

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Enriched Security Master not found: "
            f"{INPUT_CSV}"
        )

    dataframe = pd.read_csv(
        INPUT_CSV,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    return dataframe


def require_columns(
    dataframe: pd.DataFrame,
) -> list[str]:

    required_columns = [
        "security_id",
        "symbol",
        "security_type",
        "instrument_class",
        "is_index",
        "is_stock",
        "is_fno",
        "aqsd_scope",
        "enrichment_status",
        "enrichment_source",
    ]

    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    return missing


# ============================================================
# VALIDATION ENGINE
# ============================================================

def validate_enriched_master(
    dataframe: pd.DataFrame,
) -> dict[str, object]:

    issues: list[str] = []

    missing_required_columns = require_columns(
        dataframe
    )

    if missing_required_columns:
        issues.append(
            "Missing required columns: "
            + ", ".join(
                missing_required_columns
            )
        )

        return {
            "module_id": MODULE_ID,
            "module_version": MODULE_VERSION,
            "generated_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "status": "FAILED",
            "rows": len(dataframe),
            "columns": len(dataframe.columns),
            "missing_required_columns":
                missing_required_columns,
            "critical_issues":
                len(missing_required_columns),
            "issues": issues,
        }

    # --------------------------------------------------------
    # BASIC INTEGRITY
    # --------------------------------------------------------

    row_count = len(
        dataframe
    )

    symbol_series = (
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unique_symbols = int(
        symbol_series.nunique()
    )

    blank_symbols = int(
        blank_mask(
            dataframe["symbol"]
        ).sum()
    )

    duplicate_symbols = int(
        symbol_series.duplicated(
            keep=False
        ).sum()
    )

    blank_security_ids = int(
        blank_mask(
            dataframe["security_id"]
        ).sum()
    )

    duplicate_security_ids = int(
        dataframe["security_id"]
        .astype(str)
        .str.strip()
        .duplicated(
            keep=False
        )
        .sum()
    )

    # --------------------------------------------------------
    # CLASSIFICATION VALIDITY
    # --------------------------------------------------------

    invalid_security_type = 0
    invalid_instrument_class = 0
    invalid_is_index = 0
    invalid_is_stock = 0
    invalid_is_fno = 0
    invalid_aqsd_scope = 0

    for value in dataframe[
        "security_type"
    ]:
        if normalize_text(
            value
        ) not in VALID_SECURITY_TYPES:
            invalid_security_type += 1

    for value in dataframe[
        "instrument_class"
    ]:
        if normalize_text(
            value
        ) not in VALID_INSTRUMENT_CLASSES:
            invalid_instrument_class += 1

    for value in dataframe[
        "is_index"
    ]:
        if normalize_text(
            value
        ) not in VALID_YES_NO:
            invalid_is_index += 1

    for value in dataframe[
        "is_stock"
    ]:
        if normalize_text(
            value
        ) not in VALID_YES_NO:
            invalid_is_stock += 1

    for value in dataframe[
        "is_fno"
    ]:
        if normalize_text(
            value
        ) not in VALID_YES_NO:
            invalid_is_fno += 1

    for value in dataframe[
        "aqsd_scope"
    ]:
        if normalize_text(
            value
        ) not in VALID_AQSD_SCOPES:
            invalid_aqsd_scope += 1

    # --------------------------------------------------------
    # CROSS-FIELD CONSISTENCY
    # --------------------------------------------------------

    index_stock_conflicts = 0
    type_class_conflicts = 0
    fno_scope_conflicts = 0

    for _, row in dataframe.iterrows():

        security_type = normalize_text(
            row["security_type"]
        )

        instrument_class = normalize_text(
            row["instrument_class"]
        )

        is_index = normalize_text(
            row["is_index"]
        )

        is_stock = normalize_text(
            row["is_stock"]
        )

        is_fno = normalize_text(
            row["is_fno"]
        )

        aqsd_scope = normalize_text(
            row["aqsd_scope"]
        )

        # INDEX and STOCK must be mutually exclusive.
        if (
            is_index == "YES"
            and is_stock == "YES"
        ):
            index_stock_conflicts += 1

        if (
            is_index == "NO"
            and is_stock == "NO"
        ):
            index_stock_conflicts += 1

        # Security type must match instrument class.
        if security_type == "INDEX":

            if (
                instrument_class
                != "INDEX_UNDERLYING"
                or is_index != "YES"
                or is_stock != "NO"
            ):
                type_class_conflicts += 1

        elif security_type == "EQUITY":

            if (
                instrument_class
                != "STOCK_UNDERLYING"
                or is_index != "NO"
                or is_stock != "YES"
            ):
                type_class_conflicts += 1

        # Current enriched universe is F&O.
        if is_fno == "YES":

            if aqsd_scope != "NSE_FNO_UNIVERSE":
                fno_scope_conflicts += 1

        elif is_fno == "NO":

            if aqsd_scope != "NSE_SECURITY":
                fno_scope_conflicts += 1

    # --------------------------------------------------------
    # ENRICHMENT METADATA
    # --------------------------------------------------------

    blank_enrichment_status = int(
        blank_mask(
            dataframe[
                "enrichment_status"
            ]
        ).sum()
    )

    blank_enrichment_source = int(
        blank_mask(
            dataframe[
                "enrichment_source"
            ]
        ).sum()
    )

    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    index_count = int(
        (
            dataframe["is_index"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "YES"
        ).sum()
    )

    stock_count = int(
        (
            dataframe["is_stock"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "YES"
        ).sum()
    )

    fno_count = int(
        (
            dataframe["is_fno"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "YES"
        ).sum()
    )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    critical_issues = sum(
        [
            blank_symbols,
            duplicate_symbols,
            blank_security_ids,
            duplicate_security_ids,
            invalid_security_type,
            invalid_instrument_class,
            invalid_is_index,
            invalid_is_stock,
            invalid_is_fno,
            invalid_aqsd_scope,
            index_stock_conflicts,
            type_class_conflicts,
            fno_scope_conflicts,
            blank_enrichment_status,
            blank_enrichment_source,
        ]
    )

    if critical_issues == 0:
        status = "SUCCESS"
    else:
        status = "REVIEW REQUIRED"

    if blank_symbols:
        issues.append(
            f"{blank_symbols} blank symbols found."
        )

    if duplicate_symbols:
        issues.append(
            f"{duplicate_symbols} duplicate symbol rows found."
        )

    if index_stock_conflicts:
        issues.append(
            f"{index_stock_conflicts} index/stock "
            "classification conflicts found."
        )

    if type_class_conflicts:
        issues.append(
            f"{type_class_conflicts} security type / "
            "instrument class conflicts found."
        )

    if fno_scope_conflicts:
        issues.append(
            f"{fno_scope_conflicts} F&O scope conflicts found."
        )

    return {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "status": status,
        "input_file": str(
            INPUT_CSV
        ),
        "rows": row_count,
        "columns": len(
            dataframe.columns
        ),
        "unique_symbols": unique_symbols,
        "index_count": index_count,
        "stock_count": stock_count,
        "fno_count": fno_count,
        "blank_symbols": blank_symbols,
        "duplicate_symbols": duplicate_symbols,
        "blank_security_ids":
            blank_security_ids,
        "duplicate_security_ids":
            duplicate_security_ids,
        "invalid_security_type":
            invalid_security_type,
        "invalid_instrument_class":
            invalid_instrument_class,
        "invalid_is_index":
            invalid_is_index,
        "invalid_is_stock":
            invalid_is_stock,
        "invalid_is_fno":
            invalid_is_fno,
        "invalid_aqsd_scope":
            invalid_aqsd_scope,
        "index_stock_conflicts":
            index_stock_conflicts,
        "type_class_conflicts":
            type_class_conflicts,
        "fno_scope_conflicts":
            fno_scope_conflicts,
        "blank_enrichment_status":
            blank_enrichment_status,
        "blank_enrichment_source":
            blank_enrichment_source,
        "critical_issues":
            critical_issues,
        "issues": issues,
        "historical_database_modified":
            False,
        "source_security_master_modified":
            False,
        "enriched_security_master_modified":
            False,
    }


# ============================================================
# OUTPUT
# ============================================================

def save_validation_report(
    report: dict[str, object],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    VALIDATION_JSON.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_report(
    report: dict[str, object],
) -> None:

    print()
    print("=" * 80)
    print("AQSD SECURITY MASTER ENRICHMENT VALIDATOR")
    print("=" * 80)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print("-" * 80)

    print(
        f"Rows                      : "
        f"{int(report.get('rows', 0) or 0):,}"
    )

    print(
        f"Columns                   : "
        f"{int(report.get('columns', 0) or 0)}"
    )

    print(
        f"Unique Symbols            : "
        f"{int(report.get('unique_symbols', 0) or 0):,}"
    )

    print(
        f"Index Underlyings         : "
        f"{int(report.get('index_count', 0) or 0):,}"
    )

    print(
        f"Stock Underlyings         : "
        f"{int(report.get('stock_count', 0) or 0):,}"
    )

    print(
        f"F&O Securities            : "
        f"{int(report.get('fno_count', 0) or 0):,}"
    )

    print("-" * 80)

    print(
        f"Blank Symbols             : "
        f"{int(report.get('blank_symbols', 0) or 0)}"
    )

    print(
        f"Duplicate Symbols         : "
        f"{int(report.get('duplicate_symbols', 0) or 0)}"
    )

    print(
        f"Blank Security IDs        : "
        f"{int(report.get('blank_security_ids', 0) or 0)}"
    )

    print(
        f"Duplicate Security IDs    : "
        f"{int(report.get('duplicate_security_ids', 0) or 0)}"
    )

    print(
        f"Index/Stock Conflicts     : "
        f"{int(report.get('index_stock_conflicts', 0) or 0)}"
    )

    print(
        f"Type/Class Conflicts      : "
        f"{int(report.get('type_class_conflicts', 0) or 0)}"
    )

    print(
        f"F&O Scope Conflicts       : "
        f"{int(report.get('fno_scope_conflicts', 0) or 0)}"
    )

    print(
        f"Critical Issues           : "
        f"{int(report.get('critical_issues', 0) or 0)}"
    )

    print("-" * 80)

    print(
        "Historical Database       : READ ONLY / UNTOUCHED"
    )

    print(
        "Source Security Master    : READ ONLY / UNCHANGED"
    )

    print(
        "Enriched Security Master  : READ ONLY / UNCHANGED"
    )

    print(
        f"Validation JSON           : "
        f"{VALIDATION_JSON}"
    )

    print("-" * 80)

    print(
        f"Status                    : "
        f"{report.get('status', 'FAILED')}"
    )

    print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        dataframe = load_enriched_master()

        report = validate_enriched_master(
            dataframe
        )

        save_validation_report(
            report
        )

        display_report(
            report
        )

        if report[
            "status"
        ] != "SUCCESS":
            raise SystemExit(1)

    except SystemExit:
        raise

    except Exception as exc:

        print()
        print("=" * 80)
        print("AQSD SECURITY MASTER ENRICHMENT VALIDATOR")
        print("=" * 80)
        print("Status                    : FAILED")
        print(
            f"Reason                    : "
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 80)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()