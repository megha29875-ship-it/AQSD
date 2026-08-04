"""
AQSD
NSE Market Price Canonical Validator

Module : MPD-005
Version: 1.0.0
Author : AQSD

Purpose
-------
Independently validate the canonical Market Price staging dataset
created by MPD-004 before any data is loaded into AQSD_Market_Price.db.

Validation includes:
- file availability
- required schema
- row count
- duplicate trade_date + symbol keys
- unique symbols
- Security Master reconciliation
- invalid / future dates
- chronological coverage
- null OHLC
- non-positive prices
- invalid OHLC relationships
- negative volume
- source field integrity
- source priority integrity
- quality status integrity
- per-symbol session coverage

Protection
----------
- Canonical CSV is READ ONLY
- Security Master is READ ONLY
- Market Price database is NOT MODIFIED
- Frozen historical database is NOT MODIFIED
- Historical fabrication is PROHIBITED
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-005"
MODULE_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

CANONICAL_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Output"
    / "AQSD_Market_Price_Canonical.csv"
)

SECURITY_MASTER_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Output"
    / "AQSD_Security_Master_Enriched.csv"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Validation_Audit.csv"
)

ISSUES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Validation_Issues.csv"
)

SYMBOL_COVERAGE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Symbol_Coverage.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Validation_Summary.json"
)


# ============================================================
# REQUIRED SCHEMA
# ============================================================

REQUIRED_COLUMNS: Final[list[str]] = [
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


# ============================================================
# LOAD CANONICAL DATA
# ============================================================

def load_canonical_data() -> pd.DataFrame:

    if not CANONICAL_FILE.exists():

        raise FileNotFoundError(
            f"Canonical Market Price file not found: "
            f"{CANONICAL_FILE}"
        )

    dataframe = pd.read_csv(
        CANONICAL_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    missing = sorted(
        set(REQUIRED_COLUMNS)
        - set(dataframe.columns)
    )

    if missing:

        raise RuntimeError(
            "Canonical file missing required columns: "
            + ", ".join(missing)
        )

    return dataframe


# ============================================================
# LOAD SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_FILE.exists():

        raise FileNotFoundError(
            f"Security Master not found: "
            f"{SECURITY_MASTER_FILE}"
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
        "security_id",
        "symbol",
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

    dataframe["security_id"] = (
        dataframe["security_id"]
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return (
        dataframe[
            [
                "security_id",
                "symbol",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )


# ============================================================
# STANDARDIZE CANONICAL DATA
# ============================================================

def standardize_canonical(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = dataframe.copy()

    dataframe["trade_date_parsed"] = pd.to_datetime(
        dataframe["trade_date"],
        errors="coerce",
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

    dataframe["source"] = (
        dataframe["source"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["quality_status"] = (
        dataframe["quality_status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source_priority",
    ]:

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    return dataframe


# ============================================================
# VALIDATION
# ============================================================

def validate_canonical(
    dataframe: pd.DataFrame,
    security_master: pd.DataFrame,
) -> tuple[
    dict[str, object],
    pd.DataFrame,
    pd.DataFrame,
]:

    dataframe = dataframe.copy()

    issues: list[dict[str, object]] = []

    # --------------------------------------------------------
    # Duplicate primary keys
    # --------------------------------------------------------

    duplicate_mask = dataframe.duplicated(
        subset=[
            "trade_date",
            "symbol",
        ],
        keep=False,
    )

    duplicate_keys = int(
        duplicate_mask.sum()
    )

    for _, row in dataframe[
        duplicate_mask
    ].head(100).iterrows():

        issues.append(
            {
                "issue_type":
                    "DUPLICATE_KEY",

                "trade_date":
                    row.get("trade_date"),

                "symbol":
                    row.get("symbol"),

                "security_id":
                    row.get("security_id"),

                "details":
                    "Duplicate trade_date + symbol key.",
            }
        )

    # --------------------------------------------------------
    # Invalid dates
    # --------------------------------------------------------

    invalid_date_mask = (
        dataframe["trade_date_parsed"].isna()
    )

    invalid_dates = int(
        invalid_date_mask.sum()
    )

    for _, row in dataframe[
        invalid_date_mask
    ].head(100).iterrows():

        issues.append(
            {
                "issue_type":
                    "INVALID_DATE",

                "trade_date":
                    row.get("trade_date"),

                "symbol":
                    row.get("symbol"),

                "security_id":
                    row.get("security_id"),

                "details":
                    "Trade date could not be parsed.",
            }
        )

    # --------------------------------------------------------
    # Future dates
    # --------------------------------------------------------

    valid_date_mask = (
        dataframe["trade_date_parsed"].notna()
    )

    future_date_mask = (
        valid_date_mask
        &
        (
            dataframe["trade_date_parsed"].dt.date
            > date.today()
        )
    )

    future_dates = int(
        future_date_mask.sum()
    )

    for _, row in dataframe[
        future_date_mask
    ].head(100).iterrows():

        issues.append(
            {
                "issue_type":
                    "FUTURE_DATE",

                "trade_date":
                    row.get("trade_date"),

                "symbol":
                    row.get("symbol"),

                "security_id":
                    row.get("security_id"),

                "details":
                    "Trade date is later than current date.",
            }
        )

    # --------------------------------------------------------
    # Blank symbols
    # --------------------------------------------------------

    blank_symbol_mask = (
        dataframe["symbol"].isna()
        |
        dataframe["symbol"].eq("")
        |
        dataframe["symbol"].eq("NAN")
    )

    blank_symbols = int(
        blank_symbol_mask.sum()
    )

    # --------------------------------------------------------
    # Blank Security IDs
    # --------------------------------------------------------

    blank_security_id_mask = (
        dataframe["security_id"].isna()
        |
        dataframe["security_id"].eq("")
        |
        dataframe["security_id"].eq("NAN")
    )

    blank_security_ids = int(
        blank_security_id_mask.sum()
    )

    # --------------------------------------------------------
    # Security Master reconciliation
    # --------------------------------------------------------

    master_pairs = set(
        zip(
            security_master["security_id"],
            security_master["symbol"],
        )
    )

    pair_mask = dataframe.apply(
        lambda row: (
            str(row["security_id"]).strip(),
            str(row["symbol"]).strip().upper(),
        )
        in master_pairs,
        axis=1,
    )

    unknown_security_pairs = int(
        (~pair_mask).sum()
    )

    for _, row in dataframe[
        ~pair_mask
    ].head(100).iterrows():

        issues.append(
            {
                "issue_type":
                    "SECURITY_MASTER_MISMATCH",

                "trade_date":
                    row.get("trade_date"),

                "symbol":
                    row.get("symbol"),

                "security_id":
                    row.get("security_id"),

                "details":
                    "security_id + symbol not found in Security Master.",
            }
        )

    # --------------------------------------------------------
    # Null OHLC
    # --------------------------------------------------------

    null_ohlc_mask = (
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

    null_ohlc = int(
        null_ohlc_mask.sum()
    )

    # --------------------------------------------------------
    # Non-positive OHLC
    # --------------------------------------------------------

    non_positive_mask = (
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

    non_positive_prices = int(
        non_positive_mask.sum()
    )

    # --------------------------------------------------------
    # Invalid OHLC relationships
    # --------------------------------------------------------

    invalid_ohlc_mask = (
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

    invalid_ohlc = int(
        invalid_ohlc_mask.sum()
    )

    # --------------------------------------------------------
    # Negative volume
    # --------------------------------------------------------

    negative_volume_mask = (
        dataframe["volume"] < 0
    )

    negative_volume = int(
        negative_volume_mask.sum()
    )

    # --------------------------------------------------------
    # Source integrity
    # --------------------------------------------------------

    blank_source_mask = (
        dataframe["source"].isna()
        |
        dataframe["source"].eq("")
        |
        dataframe["source"].eq("NAN")
    )

    blank_source = int(
        blank_source_mask.sum()
    )

    source_priority_invalid_mask = (
        dataframe["source_priority"].isna()
        |
        dataframe["source_priority"].le(0)
    )

    invalid_source_priority = int(
        source_priority_invalid_mask.sum()
    )

    invalid_quality_status_mask = (
        ~dataframe[
            "quality_status"
        ].isin(
            [
                "PASS",
            ]
        )
    )

    invalid_quality_status = int(
        invalid_quality_status_mask.sum()
    )

    # --------------------------------------------------------
    # Symbol coverage
    # --------------------------------------------------------

    canonical_symbols = set(
        dataframe["symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )

    master_symbols = set(
        security_master["symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )

    matched_symbols = (
        canonical_symbols
        & master_symbols
    )

    missing_master_symbols = (
        master_symbols
        - canonical_symbols
    )

    unknown_canonical_symbols = (
        canonical_symbols
        - master_symbols
    )

    coverage_percent = (
        round(
            (
                len(matched_symbols)
                / len(master_symbols)
            )
            * 100,
            2,
        )
        if master_symbols
        else 0.0
    )

    # --------------------------------------------------------
    # Date coverage
    # --------------------------------------------------------

    valid_dates = (
        dataframe.loc[
            dataframe["trade_date_parsed"].notna(),
            "trade_date_parsed",
        ]
    )

    first_session = (
        valid_dates.min().date().isoformat()
        if not valid_dates.empty
        else None
    )

    last_session = (
        valid_dates.max().date().isoformat()
        if not valid_dates.empty
        else None
    )

    trading_sessions = int(
        dataframe.loc[
            dataframe["trade_date_parsed"].notna(),
            "trade_date",
        ].nunique()
    )

    # --------------------------------------------------------
    # Per-symbol coverage
    # --------------------------------------------------------

    symbol_coverage = (
        dataframe.groupby(
            [
                "security_id",
                "symbol",
            ],
            dropna=False,
        )
        .agg(
            rows=(
                "trade_date",
                "size",
            ),
            sessions=(
                "trade_date",
                "nunique",
            ),
            first_session=(
                "trade_date",
                "min",
            ),
            last_session=(
                "trade_date",
                "max",
            ),
        )
        .reset_index()
        .sort_values(
            by=[
                "symbol",
            ]
        )
    )

    # --------------------------------------------------------
    # Critical issue count
    # --------------------------------------------------------

    critical_issues = (
        duplicate_keys
        + invalid_dates
        + future_dates
        + blank_symbols
        + blank_security_ids
        + unknown_security_pairs
        + null_ohlc
        + non_positive_prices
        + invalid_ohlc
        + negative_volume
        + blank_source
        + invalid_source_priority
        + invalid_quality_status
        + len(
            unknown_canonical_symbols
        )
    )

    warnings = len(
        missing_master_symbols
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
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
            .isoformat(
                timespec="seconds"
            ),

        "canonical_rows":
            len(dataframe),

        "canonical_columns":
            len(dataframe.columns),

        "unique_symbols":
            len(canonical_symbols),

        "security_master_symbols":
            len(master_symbols),

        "matched_symbols":
            len(matched_symbols),

        "missing_master_symbols":
            len(missing_master_symbols),

        "unknown_canonical_symbols":
            len(unknown_canonical_symbols),

        "coverage_percent":
            coverage_percent,

        "trading_sessions":
            trading_sessions,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "duplicate_keys":
            duplicate_keys,

        "invalid_dates":
            invalid_dates,

        "future_dates":
            future_dates,

        "blank_symbols":
            blank_symbols,

        "blank_security_ids":
            blank_security_ids,

        "security_master_mismatches":
            unknown_security_pairs,

        "null_ohlc":
            null_ohlc,

        "non_positive_prices":
            non_positive_prices,

        "invalid_ohlc":
            invalid_ohlc,

        "negative_volume":
            negative_volume,

        "blank_source":
            blank_source,

        "invalid_source_priority":
            invalid_source_priority,

        "invalid_quality_status":
            invalid_quality_status,

        "critical_issues":
            critical_issues,

        "warnings":
            warnings,

        "canonical_file":
            str(
                CANONICAL_FILE
            ),

        "security_master_file":
            str(
                SECURITY_MASTER_FILE
            ),

        "market_price_database_modified":
            False,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            status,
    }

    issues_dataframe = pd.DataFrame(
        issues
    )

    return (
        summary,
        issues_dataframe,
        symbol_coverage,
    )


# ============================================================
# WRITE OUTPUTS
# ============================================================

def write_outputs(
    summary: dict[str, object],
    issues: pd.DataFrame,
    symbol_coverage: pd.DataFrame,
) -> None:

    ensure_output_directory()

    pd.DataFrame(
        [summary]
    ).to_csv(
        AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    if issues.empty:

        issues = pd.DataFrame(
            columns=[
                "issue_type",
                "trade_date",
                "symbol",
                "security_id",
                "details",
            ]
        )

    issues.to_csv(
        ISSUES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    symbol_coverage.to_csv(
        SYMBOL_COVERAGE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()
    print("=" * 96)
    print("AQSD MARKET PRICE CANONICAL VALIDATOR")
    print("=" * 96)

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print("-" * 96)

    print(
        f"Canonical Rows                 : "
        f"{int(summary['canonical_rows']):,}"
    )

    print(
        f"Canonical Columns              : "
        f"{int(summary['canonical_columns']):,}"
    )

    print(
        f"Unique Symbols                 : "
        f"{int(summary['unique_symbols']):,}"
    )

    print(
        f"Security Master Symbols        : "
        f"{int(summary['security_master_symbols']):,}"
    )

    print(
        f"Matched Symbols                : "
        f"{int(summary['matched_symbols']):,}"
    )

    print(
        f"Missing Master Symbols         : "
        f"{int(summary['missing_master_symbols']):,}"
    )

    print(
        f"Unknown Canonical Symbols      : "
        f"{int(summary['unknown_canonical_symbols']):,}"
    )

    print(
        f"Coverage                       : "
        f"{summary['coverage_percent']}%"
    )

    print("-" * 96)

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
        f"Duplicate Keys                 : "
        f"{int(summary['duplicate_keys']):,}"
    )

    print(
        f"Invalid Dates                  : "
        f"{int(summary['invalid_dates']):,}"
    )

    print(
        f"Future Dates                   : "
        f"{int(summary['future_dates']):,}"
    )

    print(
        f"Blank Symbols                  : "
        f"{int(summary['blank_symbols']):,}"
    )

    print(
        f"Blank Security IDs             : "
        f"{int(summary['blank_security_ids']):,}"
    )

    print(
        f"Security Master Mismatches     : "
        f"{int(summary['security_master_mismatches']):,}"
    )

    print(
        f"Null OHLC                      : "
        f"{int(summary['null_ohlc']):,}"
    )

    print(
        f"Non-Positive Prices            : "
        f"{int(summary['non_positive_prices']):,}"
    )

    print(
        f"Invalid OHLC                   : "
        f"{int(summary['invalid_ohlc']):,}"
    )

    print(
        f"Negative Volume                : "
        f"{int(summary['negative_volume']):,}"
    )

    print(
        f"Blank Source                   : "
        f"{int(summary['blank_source']):,}"
    )

    print(
        f"Invalid Source Priority        : "
        f"{int(summary['invalid_source_priority']):,}"
    )

    print(
        f"Invalid Quality Status         : "
        f"{int(summary['invalid_quality_status']):,}"
    )

    print("-" * 96)

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    print(
        f"Warnings                       : "
        f"{int(summary['warnings']):,}"
    )

    print("-" * 96)

    print(
        f"Canonical File                 : "
        f"{CANONICAL_FILE}"
    )

    print(
        f"Audit CSV                      : "
        f"{AUDIT_CSV}"
    )

    print(
        f"Issues CSV                     : "
        f"{ISSUES_CSV}"
    )

    print(
        f"Symbol Coverage CSV            : "
        f"{SYMBOL_COVERAGE_CSV}"
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

        canonical = load_canonical_data()

        security_master = (
            load_security_master()
        )

        canonical = standardize_canonical(
            canonical
        )

        (
            summary,
            issues,
            symbol_coverage,
        ) = validate_canonical(
            canonical,
            security_master,
        )

        write_outputs(
            summary,
            issues,
            symbol_coverage,
        )

        display_summary(
            summary
        )

        if summary[
            "status"
        ] != "SUCCESS":

            raise SystemExit(1)

    except SystemExit:
        raise

    except Exception as exc:

        print()
        print("=" * 96)
        print("AQSD MARKET PRICE CANONICAL VALIDATOR")
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