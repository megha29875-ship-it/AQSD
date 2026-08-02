"""
AQSD
NSE Security Master Enrichment Builder

Module : SMD-003
Version: 1.0.0
Author : AQSD

Purpose
-------
Enrich the validated AQSD Security Master with structured security
classification fields while preserving the frozen historical database.

This module:
- reads AQSD_Security_Master.csv
- does NOT modify the historical NSE F&O database
- does NOT rebuild historical data
- does NOT fabricate external metadata
- creates an enriched Security Master output

Initial enrichment fields
-------------------------
- security_type
- instrument_class
- is_index
- is_stock
- is_fno
- aqsd_scope
- enrichment_status
- enrichment_source

External metadata such as:
- sector
- industry
- ISIN
- NSE token
- FYERS symbol
- lot size

is preserved if already available, but is not invented here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-003"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

INPUT_CSV = OUTPUT_DIR / "AQSD_Security_Master.csv"

OUTPUT_CSV = OUTPUT_DIR / "AQSD_Security_Master_Enriched.csv"

OUTPUT_JSON = OUTPUT_DIR / "AQSD_Security_Master_Enriched.json"

SUMMARY_JSON = OUTPUT_DIR / "AQSD_Security_Master_Enrichment_Summary.json"


# ============================================================
# KNOWN NSE INDEX UNDERLYINGS
# ============================================================

KNOWN_INDEX_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_column_name(value: object) -> str:
    return str(value).strip().lower()


def ensure_output_directory() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def load_security_master() -> pd.DataFrame:

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Security Master not found: {INPUT_CSV}"
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


def require_column(
    dataframe: pd.DataFrame,
    column_name: str,
) -> None:

    if column_name not in dataframe.columns:
        raise RuntimeError(
            f"Required column missing: {column_name}"
        )


def normalize_symbol(value: object) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


# ============================================================
# CLASSIFICATION LOGIC
# ============================================================

def classify_security(
    symbol: str,
    fno_flag: str,
) -> dict[str, object]:

    is_index = symbol in KNOWN_INDEX_SYMBOLS

    is_fno = (
        str(fno_flag).strip().upper() == "YES"
    )

    if is_index:
        security_type = "INDEX"
        instrument_class = "INDEX_UNDERLYING"
        is_stock = False

    else:
        security_type = "EQUITY"
        instrument_class = "STOCK_UNDERLYING"
        is_stock = True

    if is_fno:
        aqsd_scope = "NSE_FNO_UNIVERSE"
    else:
        aqsd_scope = "NSE_SECURITY"

    return {
        "security_type": security_type,
        "instrument_class": instrument_class,
        "is_index": "YES" if is_index else "NO",
        "is_stock": "YES" if is_stock else "NO",
        "is_fno": "YES" if is_fno else "NO",
        "aqsd_scope": aqsd_scope,
    }


# ============================================================
# ENRICHMENT ENGINE
# ============================================================

def enrich_security_master(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    require_column(
        dataframe,
        "security_id",
    )

    require_column(
        dataframe,
        "symbol",
    )

    if "fno_flag" not in dataframe.columns:
        dataframe["fno_flag"] = "YES"

    enriched = dataframe.copy()

    security_type_values: list[str] = []
    instrument_class_values: list[str] = []
    is_index_values: list[str] = []
    is_stock_values: list[str] = []
    is_fno_values: list[str] = []
    aqsd_scope_values: list[str] = []

    for _, row in enriched.iterrows():

        symbol = normalize_symbol(
            row["symbol"]
        )

        classification = classify_security(
            symbol=symbol,
            fno_flag=row.get(
                "fno_flag",
                "YES",
            ),
        )

        security_type_values.append(
            str(
                classification[
                    "security_type"
                ]
            )
        )

        instrument_class_values.append(
            str(
                classification[
                    "instrument_class"
                ]
            )
        )

        is_index_values.append(
            str(
                classification[
                    "is_index"
                ]
            )
        )

        is_stock_values.append(
            str(
                classification[
                    "is_stock"
                ]
            )
        )

        is_fno_values.append(
            str(
                classification[
                    "is_fno"
                ]
            )
        )

        aqsd_scope_values.append(
            str(
                classification[
                    "aqsd_scope"
                ]
            )
        )

    enriched["security_type"] = security_type_values
    enriched["instrument_class"] = instrument_class_values
    enriched["is_index"] = is_index_values
    enriched["is_stock"] = is_stock_values
    enriched["is_fno"] = is_fno_values
    enriched["aqsd_scope"] = aqsd_scope_values

    enriched["enrichment_status"] = "FOUNDATION_COMPLETE"
    enriched["enrichment_source"] = "AQSD_INTERNAL_CLASSIFICATION"

    return enriched


# ============================================================
# VALIDATION
# ============================================================

def validate_enriched_master(
    dataframe: pd.DataFrame,
) -> dict[str, object]:

    total_rows = len(
        dataframe
    )

    unique_symbols = int(
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
        .nunique()
    )

    duplicate_symbols = int(
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
        .duplicated(
            keep=False
        )
        .sum()
    )

    blank_symbols = int(
        dataframe["symbol"]
        .isna()
        .sum()
        +
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    index_count = int(
        (
            dataframe["is_index"] == "YES"
        ).sum()
    )

    stock_count = int(
        (
            dataframe["is_stock"] == "YES"
        ).sum()
    )

    fno_count = int(
        (
            dataframe["is_fno"] == "YES"
        ).sum()
    )

    critical_issues = (
        duplicate_symbols
        + blank_symbols
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "REVIEW REQUIRED"
    )

    return {
        "rows": total_rows,
        "unique_symbols": unique_symbols,
        "duplicate_symbols": duplicate_symbols,
        "blank_symbols": blank_symbols,
        "index_count": index_count,
        "stock_count": stock_count,
        "fno_count": fno_count,
        "critical_issues": critical_issues,
        "status": status,
    }


# ============================================================
# OUTPUT
# ============================================================

def write_outputs(
    dataframe: pd.DataFrame,
    validation: dict[str, object],
) -> None:

    ensure_output_directory()

    dataframe.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    records = dataframe.where(
        pd.notna(dataframe),
        None,
    ).to_dict(
        orient="records"
    )

    OUTPUT_JSON.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "input_file": str(
            INPUT_CSV
        ),
        "output_csv": str(
            OUTPUT_CSV
        ),
        "output_json": str(
            OUTPUT_JSON
        ),
        "rows": validation[
            "rows"
        ],
        "unique_symbols": validation[
            "unique_symbols"
        ],
        "index_count": validation[
            "index_count"
        ],
        "stock_count": validation[
            "stock_count"
        ],
        "fno_count": validation[
            "fno_count"
        ],
        "duplicate_symbols": validation[
            "duplicate_symbols"
        ],
        "blank_symbols": validation[
            "blank_symbols"
        ],
        "critical_issues": validation[
            "critical_issues"
        ],
        "historical_database_modified": False,
        "security_master_source_modified": False,
        "status": validation[
            "status"
        ],
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    validation: dict[str, object],
) -> None:

    print()
    print("=" * 78)
    print("AQSD SECURITY MASTER ENRICHMENT")
    print("=" * 78)

    print(
        f"Module                 : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Security Master Rows   : "
        f"{validation['rows']:,}"
    )

    print(
        f"Unique Symbols         : "
        f"{validation['unique_symbols']:,}"
    )

    print(
        f"Index Underlyings      : "
        f"{validation['index_count']:,}"
    )

    print(
        f"Stock Underlyings      : "
        f"{validation['stock_count']:,}"
    )

    print(
        f"F&O Securities         : "
        f"{validation['fno_count']:,}"
    )

    print(
        f"Duplicate Symbols      : "
        f"{validation['duplicate_symbols']}"
    )

    print(
        f"Blank Symbols          : "
        f"{validation['blank_symbols']}"
    )

    print(
        f"Critical Issues        : "
        f"{validation['critical_issues']}"
    )

    print("-" * 78)

    print(
        "Historical Database    : READ ONLY / UNTOUCHED"
    )

    print(
        "Source Security Master : READ ONLY / UNCHANGED"
    )

    print(
        f"Enriched CSV           : "
        f"{OUTPUT_CSV}"
    )

    print(
        f"Enriched JSON          : "
        f"{OUTPUT_JSON}"
    )

    print("-" * 78)

    print(
        f"Status                 : "
        f"{validation['status']}"
    )

    print("=" * 78)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    dataframe = load_security_master()

    enriched = enrich_security_master(
        dataframe
    )

    validation = validate_enriched_master(
        enriched
    )

    write_outputs(
        enriched,
        validation,
    )

    display_summary(
        validation
    )

    if validation[
        "status"
    ] != "SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()