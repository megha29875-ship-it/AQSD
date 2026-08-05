"""
AQSD
Market Price Processed Historical Validator

Module ID: MPD-010
Version: 1.0.0
Author: AQSD

Purpose
-------
Independently validate the processed historical market-price dataset
created by MPD-009 before any canonical Market Price Database build
or promotion is permitted.

Validation Scope
----------------
1. MPD-009 must be SUCCESS.
2. Processed row count must reconcile to MPD-009.
3. Security count must reconcile to MPD-009.
4. trade_date + security_id must be unique.
5. OHLC integrity must hold.
6. Dates must be valid and non-future.
7. Volume must not be negative.
8. Security IDs and symbols must be populated.
9. Provenance fields must be present.
10. Per-security chronological order is validated.
11. Per-security first/last session and row coverage are reported.
12. Market Price Database is NOT modified.

Protection
----------
Processed Dataset         : READ ONLY
Raw Data                  : READ ONLY
Security Master           : NOT MODIFIED
Market Price Database     : NOT MODIFIED
Frozen Historical DB      : NOT MODIFIED
Historical Fabrication    : PROHIBITED
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

MODULE_ID: Final[str] = "MPD-010"
MODULE_VERSION: Final[str] = "1.0.0"


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT: Final[Path] = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

DATA_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Data"
)

PROCESSED_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Processed"
)


# ============================================================
# INPUT FILES
# ============================================================

PROCESSED_DATASET_FILE: Final[Path] = (
    PROCESSED_ROOT
    / "AQSD_Market_Price_Processed_Historical.csv"
)

MPD009_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Build_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

VALIDATION_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Validation_Audit.csv"
)

VALIDATION_ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Validation_Issues.csv"
)

SECURITY_COVERAGE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Security_Coverage.csv"
)

VALIDATION_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Validation_Summary.json"
)


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS: Final[set[str]] = {
    "trade_date",
    "security_id",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "source_file",
    "source_module",
    "validation_module",
    "processing_module",
    "processing_version",
    "processed_at",
}


# ============================================================
# HELPERS
# ============================================================

def separator() -> None:
    print("=" * 100)


def sub_separator() -> None:
    print("-" * 100)


def ensure_output_directory() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def normalize_column_name(
    value: object,
) -> str:

    text = (
        str(value)
        .strip()
        .lower()
    )

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def safe_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip()


def load_json(
    path: Path,
) -> dict[str, object]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs() -> None:

    required_files = [
        PROCESSED_DATASET_FILE,
        MPD009_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-010 input file(s) missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# MPD-009 GATE
# ============================================================

def validate_mpd009() -> dict[str, object]:

    summary = load_json(
        MPD009_SUMMARY_FILE
    )

    status = safe_text(
        summary.get(
            "status",
            "",
        )
    ).upper()

    critical_issues = int(
        summary.get(
            "critical_issues",
            0,
        )
    )

    processed_rows = int(
        summary.get(
            "processed_rows",
            0,
        )
    )

    expected_rows = int(
        summary.get(
            "expected_rows",
            0,
        )
    )

    unique_securities = int(
        summary.get(
            "unique_securities",
            0,
        )
    )

    expected_securities = int(
        summary.get(
            "expected_securities",
            0,
        )
    )

    row_count_matches = bool(
        summary.get(
            "row_count_matches",
            False,
        )
    )

    security_count_matches = bool(
        summary.get(
            "security_count_matches",
            False,
        )
    )

    processing_failures = int(
        summary.get(
            "processing_failures",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-009 status is not SUCCESS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-009 contains critical issues."
        )

    if processing_failures != 0:

        raise RuntimeError(
            "MPD-009 contains processing failures."
        )

    if processed_rows != expected_rows:

        raise RuntimeError(
            "MPD-009 processed row count mismatch."
        )

    if unique_securities != expected_securities:

        raise RuntimeError(
            "MPD-009 security count mismatch."
        )

    if not row_count_matches:

        raise RuntimeError(
            "MPD-009 row reconciliation failed."
        )

    if not security_count_matches:

        raise RuntimeError(
            "MPD-009 security reconciliation failed."
        )

    return summary


# ============================================================
# LOAD PROCESSED DATASET
# ============================================================

def load_processed_dataset() -> pd.DataFrame:

    dataframe = pd.read_csv(
        PROCESSED_DATASET_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    missing = (
        REQUIRED_COLUMNS
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Processed historical dataset missing columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    dataframe[
        "security_id"
    ] = (
        dataframe[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe[
        "symbol"
    ] = (
        dataframe[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe[
        "trade_date"
    ] = pd.to_datetime(
        dataframe[
            "trade_date"
        ],
        errors="coerce",
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):

        dataframe[
            column
        ] = pd.to_numeric(
            dataframe[
                column
            ],
            errors="coerce",
        )

    return dataframe


# ============================================================
# ISSUE HELPER
# ============================================================

def add_issue(
    issues: list[dict[str, object]],
    *,
    issue_type: str,
    severity: str = "CRITICAL",
    security_id: str = "",
    symbol: str = "",
    trade_date: object = "",
    count: int = 1,
    message: str = "",
) -> None:

    issues.append(
        {
            "severity":
                severity,

            "issue_type":
                issue_type,

            "security_id":
                security_id,

            "symbol":
                symbol,

            "trade_date":
                safe_text(
                    trade_date
                ),

            "count":
                count,

            "message":
                message,
        }
    )


# ============================================================
# DATASET VALIDATION
# ============================================================

def validate_dataset(
    dataframe: pd.DataFrame,
    mpd009_summary: dict[str, object],
    issues: list[dict[str, object]],
) -> dict[str, object]:

    expected_rows = int(
        mpd009_summary[
            "processed_rows"
        ]
    )

    expected_securities = int(
        mpd009_summary[
            "unique_securities"
        ]
    )

    processed_rows = int(
        len(
            dataframe
        )
    )

    unique_securities = int(
        dataframe[
            "security_id"
        ]
        .nunique()
    )

    row_count_matches = (
        processed_rows
        == expected_rows
    )

    security_count_matches = (
        unique_securities
        == expected_securities
    )

    # --------------------------------------------------------
    # Duplicate keys
    # --------------------------------------------------------

    duplicate_mask = (
        dataframe.duplicated(
            subset=[
                "trade_date",
                "security_id",
            ],
            keep=False,
        )
    )

    duplicate_keys = int(
        duplicate_mask.sum()
    )

    if duplicate_keys:

        add_issue(
            issues,
            issue_type="DUPLICATE_TRADE_DATE_SECURITY_ID",
            count=duplicate_keys,
            message=(
                f"{duplicate_keys:,} rows participate in "
                "duplicate trade_date + security_id keys."
            ),
        )

    # --------------------------------------------------------
    # Blank identity
    # --------------------------------------------------------

    blank_security_ids = int(
        dataframe[
            "security_id"
        ]
        .eq("")
        .sum()
    )

    if blank_security_ids:

        add_issue(
            issues,
            issue_type="BLANK_SECURITY_ID",
            count=blank_security_ids,
            message=(
                f"{blank_security_ids:,} processed rows "
                "have blank security_id."
            ),
        )

    blank_symbols = int(
        dataframe[
            "symbol"
        ]
        .eq("")
        .sum()
    )

    if blank_symbols:

        add_issue(
            issues,
            issue_type="BLANK_SYMBOL",
            count=blank_symbols,
            message=(
                f"{blank_symbols:,} processed rows "
                "have blank symbol."
            ),
        )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    invalid_dates = int(
        dataframe[
            "trade_date"
        ]
        .isna()
        .sum()
    )

    if invalid_dates:

        add_issue(
            issues,
            issue_type="INVALID_TRADE_DATE",
            count=invalid_dates,
            message=(
                f"{invalid_dates:,} rows contain invalid dates."
            ),
        )

    today = (
        pd.Timestamp.now()
        .normalize()
    )

    future_date_mask = (
        dataframe[
            "trade_date"
        ]
        .dt.normalize()
        > today
    )

    future_dates = int(
        future_date_mask
        .fillna(False)
        .sum()
    )

    if future_dates:

        add_issue(
            issues,
            issue_type="FUTURE_TRADE_DATE",
            count=future_dates,
            message=(
                f"{future_dates:,} processed rows "
                "contain future trade dates."
            ),
        )

    # --------------------------------------------------------
    # OHLC
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
        .any(
            axis=1
        )
    )

    null_ohlc = int(
        null_ohlc_mask.sum()
    )

    if null_ohlc:

        add_issue(
            issues,
            issue_type="NULL_OHLC",
            count=null_ohlc,
            message=(
                f"{null_ohlc:,} rows contain null OHLC."
            ),
        )

    non_positive_price_mask = (
        (
            dataframe[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            ]
            <= 0
        )
        .any(
            axis=1
        )
    )

    non_positive_prices = int(
        non_positive_price_mask
        .fillna(False)
        .sum()
    )

    if non_positive_prices:

        add_issue(
            issues,
            issue_type="NON_POSITIVE_PRICE",
            count=non_positive_prices,
            message=(
                f"{non_positive_prices:,} rows contain "
                "non-positive OHLC values."
            ),
        )

    invalid_ohlc_mask = (
        (
            dataframe[
                "high"
            ]
            < dataframe[
                "low"
            ]
        )
        |
        (
            dataframe[
                "high"
            ]
            < dataframe[
                "open"
            ]
        )
        |
        (
            dataframe[
                "high"
            ]
            < dataframe[
                "close"
            ]
        )
        |
        (
            dataframe[
                "low"
            ]
            > dataframe[
                "open"
            ]
        )
        |
        (
            dataframe[
                "low"
            ]
            > dataframe[
                "close"
            ]
        )
    )

    invalid_ohlc = int(
        invalid_ohlc_mask
        .fillna(False)
        .sum()
    )

    if invalid_ohlc:

        add_issue(
            issues,
            issue_type="INVALID_OHLC_RELATIONSHIP",
            count=invalid_ohlc,
            message=(
                f"{invalid_ohlc:,} rows violate "
                "OHLC relationships."
            ),
        )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    negative_volume_mask = (
        dataframe[
            "volume"
        ]
        < 0
    )

    negative_volume = int(
        negative_volume_mask
        .fillna(False)
        .sum()
    )

    if negative_volume:

        add_issue(
            issues,
            issue_type="NEGATIVE_VOLUME",
            count=negative_volume,
            message=(
                f"{negative_volume:,} rows contain "
                "negative volume."
            ),
        )

    # --------------------------------------------------------
    # Provenance
    # --------------------------------------------------------

    provenance_columns = [
        "source",
        "source_file",
        "source_module",
        "validation_module",
        "processing_module",
        "processing_version",
        "processed_at",
    ]

    blank_provenance_rows = 0

    for column in provenance_columns:

        blanks = int(
            dataframe[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        blank_provenance_rows += (
            blanks
        )

        if blanks:

            add_issue(
                issues,
                issue_type=(
                    f"BLANK_PROVENANCE_{column.upper()}"
                ),
                count=blanks,
                message=(
                    f"{blanks:,} rows contain blank "
                    f"{column}."
                ),
            )

    # --------------------------------------------------------
    # Source module consistency
    # --------------------------------------------------------

    unexpected_source_module = int(
        (
            dataframe[
                "source_module"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .ne(
                "MPD-007"
            )
        ).sum()
    )

    if unexpected_source_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_SOURCE_MODULE",
            count=unexpected_source_module,
            message=(
                f"{unexpected_source_module:,} rows have "
                "unexpected source_module."
            ),
        )

    unexpected_validation_module = int(
        (
            dataframe[
                "validation_module"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .ne(
                "MPD-008"
            )
        ).sum()
    )

    if unexpected_validation_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_VALIDATION_MODULE",
            count=unexpected_validation_module,
            message=(
                f"{unexpected_validation_module:,} rows have "
                "unexpected validation_module."
            ),
        )

    unexpected_processing_module = int(
        (
            dataframe[
                "processing_module"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .ne(
                "MPD-009"
            )
        ).sum()
    )

    if unexpected_processing_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_PROCESSING_MODULE",
            count=unexpected_processing_module,
            message=(
                f"{unexpected_processing_module:,} rows have "
                "unexpected processing_module."
            ),
        )

    # --------------------------------------------------------
    # Symbol identity consistency
    # One security_id must map to one symbol.
    # One symbol must map to one security_id.
    # --------------------------------------------------------

    symbols_per_security = (
        dataframe
        .groupby(
            "security_id"
        )[
            "symbol"
        ]
        .nunique()
    )

    security_symbol_mismatches = int(
        (
            symbols_per_security
            > 1
        ).sum()
    )

    if security_symbol_mismatches:

        add_issue(
            issues,
            issue_type="SECURITY_ID_TO_MULTIPLE_SYMBOLS",
            count=security_symbol_mismatches,
            message=(
                f"{security_symbol_mismatches:,} security IDs "
                "map to multiple symbols."
            ),
        )

    securities_per_symbol = (
        dataframe
        .groupby(
            "symbol"
        )[
            "security_id"
        ]
        .nunique()
    )

    symbol_security_mismatches = int(
        (
            securities_per_symbol
            > 1
        ).sum()
    )

    if symbol_security_mismatches:

        add_issue(
            issues,
            issue_type="SYMBOL_TO_MULTIPLE_SECURITY_IDS",
            count=symbol_security_mismatches,
            message=(
                f"{symbol_security_mismatches:,} symbols "
                "map to multiple security IDs."
            ),
        )

    # --------------------------------------------------------
    # Global first / last dates
    # --------------------------------------------------------

    valid_dates = (
        dataframe[
            "trade_date"
        ]
        .dropna()
    )

    first_session = ""

    last_session = ""

    if not valid_dates.empty:

        first_session = (
            valid_dates
            .min()
            .date()
            .isoformat()
        )

        last_session = (
            valid_dates
            .max()
            .date()
            .isoformat()
        )

    # --------------------------------------------------------
    # Critical issue total
    # --------------------------------------------------------

    critical_issues = (
        duplicate_keys
        + blank_security_ids
        + blank_symbols
        + invalid_dates
        + future_dates
        + null_ohlc
        + non_positive_prices
        + invalid_ohlc
        + negative_volume
        + blank_provenance_rows
        + unexpected_source_module
        + unexpected_validation_module
        + unexpected_processing_module
        + security_symbol_mismatches
        + symbol_security_mismatches
    )

    if not row_count_matches:

        critical_issues += 1

        add_issue(
            issues,
            issue_type="ROW_COUNT_MISMATCH",
            message=(
                f"Processed file contains {processed_rows:,} rows; "
                f"MPD-009 expected {expected_rows:,}."
            ),
        )

    if not security_count_matches:

        critical_issues += 1

        add_issue(
            issues,
            issue_type="SECURITY_COUNT_MISMATCH",
            message=(
                f"Processed file contains {unique_securities:,} "
                f"securities; MPD-009 expected "
                f"{expected_securities:,}."
            ),
        )

    return {
        "processed_rows":
            processed_rows,

        "expected_rows":
            expected_rows,

        "unique_securities":
            unique_securities,

        "expected_securities":
            expected_securities,

        "row_count_matches":
            row_count_matches,

        "security_count_matches":
            security_count_matches,

        "duplicate_keys":
            duplicate_keys,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "invalid_dates":
            invalid_dates,

        "future_dates":
            future_dates,

        "null_ohlc":
            null_ohlc,

        "non_positive_prices":
            non_positive_prices,

        "invalid_ohlc":
            invalid_ohlc,

        "negative_volume":
            negative_volume,

        "blank_provenance_rows":
            blank_provenance_rows,

        "unexpected_source_module":
            unexpected_source_module,

        "unexpected_validation_module":
            unexpected_validation_module,

        "unexpected_processing_module":
            unexpected_processing_module,

        "security_symbol_mismatches":
            security_symbol_mismatches,

        "symbol_security_mismatches":
            symbol_security_mismatches,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# SECURITY COVERAGE
# ============================================================

def build_security_coverage(
    dataframe: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    dict[str, object],
]:

    rows: list[
        dict[str, object]
    ] = []

    chronology_issues = 0

    for (
        security_id,
        group,
    ) in dataframe.groupby(
        "security_id",
        sort=True,
    ):

        group = group.copy()

        symbol_values = (
            group[
                "symbol"
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

        symbol = (
            symbol_values.iloc[0]
            if not symbol_values.empty
            else ""
        )

        valid_dates = (
            group[
                "trade_date"
            ]
            .dropna()
        )

        first_session = ""

        last_session = ""

        if not valid_dates.empty:

            first_session = (
                valid_dates
                .min()
                .date()
                .isoformat()
            )

            last_session = (
                valid_dates
                .max()
                .date()
                .isoformat()
            )

        # ----------------------------------------------------
        # Check original order inside this security
        # ----------------------------------------------------

        ordered_dates = (
            group[
                "trade_date"
            ]
            .dropna()
        )

        chronology_ok = (
            ordered_dates
            .is_monotonic_increasing
        )

        if not chronology_ok:

            chronology_issues += 1

        duplicate_sessions = int(
            group.duplicated(
                subset=[
                    "trade_date",
                ],
                keep=False,
            ).sum()
        )

        rows.append(
            {
                "security_id":
                    security_id,

                "symbol":
                    symbol,

                "rows":
                    int(
                        len(
                            group
                        )
                    ),

                "first_session":
                    first_session,

                "last_session":
                    last_session,

                "chronology_ok":
                    chronology_ok,

                "duplicate_sessions":
                    duplicate_sessions,

                "null_ohlc_rows":
                    int(
                        group[
                            [
                                "open",
                                "high",
                                "low",
                                "close",
                            ]
                        ]
                        .isna()
                        .any(
                            axis=1
                        )
                        .sum()
                    ),

                "negative_volume_rows":
                    int(
                        (
                            group[
                                "volume"
                            ]
                            < 0
                        )
                        .fillna(False)
                        .sum()
                    ),
            }
        )

    coverage = pd.DataFrame(
        rows
    )

    coverage = (
        coverage
        .sort_values(
            by=[
                "symbol",
                "security_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    min_rows = 0
    max_rows = 0
    median_rows = 0.0

    if not coverage.empty:

        min_rows = int(
            coverage[
                "rows"
            ]
            .min()
        )

        max_rows = int(
            coverage[
                "rows"
            ]
            .max()
        )

        median_rows = float(
            coverage[
                "rows"
            ]
            .median()
        )

    return (
        coverage,
        {
            "chronology_issues":
                chronology_issues,

            "minimum_rows_per_security":
                min_rows,

            "maximum_rows_per_security":
                max_rows,

            "median_rows_per_security":
                median_rows,
        },
    )


# ============================================================
# RUN
# ============================================================

def run_validator() -> dict[str, object]:

    ensure_output_directory()

    validate_inputs()

    mpd009_summary = (
        validate_mpd009()
    )

    dataframe = (
        load_processed_dataset()
    )

    issues: list[
        dict[str, object]
    ] = []

    validation = (
        validate_dataset(
            dataframe,
            mpd009_summary,
            issues,
        )
    )

    (
        security_coverage,
        coverage_stats,
    ) = build_security_coverage(
        dataframe
    )

    chronology_issues = int(
        coverage_stats[
            "chronology_issues"
        ]
    )

    if chronology_issues:

        add_issue(
            issues,
            issue_type="SECURITY_CHRONOLOGY_ERROR",
            count=chronology_issues,
            message=(
                f"{chronology_issues:,} securities are not "
                "ordered chronologically in the processed dataset."
            ),
        )

    critical_issues = int(
        validation[
            "critical_issues"
        ]
    ) + chronology_issues

    issue_dataframe = pd.DataFrame(
        issues
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    # --------------------------------------------------------
    # Audit output
    # --------------------------------------------------------

    audit = pd.DataFrame(
        [
            {
                "module_id":
                    MODULE_ID,

                "module_version":
                    MODULE_VERSION,

                "processed_rows":
                    validation[
                        "processed_rows"
                    ],

                "expected_rows":
                    validation[
                        "expected_rows"
                    ],

                "unique_securities":
                    validation[
                        "unique_securities"
                    ],

                "expected_securities":
                    validation[
                        "expected_securities"
                    ],

                "duplicate_keys":
                    validation[
                        "duplicate_keys"
                    ],

                "chronology_issues":
                    chronology_issues,

                "critical_issues":
                    critical_issues,

                "status":
                    status,
            }
        ]
    )

    audit.to_csv(
        VALIDATION_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Issue output
    # --------------------------------------------------------

    if issue_dataframe.empty:

        issue_dataframe = pd.DataFrame(
            columns=[
                "severity",
                "issue_type",
                "security_id",
                "symbol",
                "trade_date",
                "count",
                "message",
            ]
        )

    issue_dataframe.to_csv(
        VALIDATION_ISSUES_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Coverage output
    # --------------------------------------------------------

    security_coverage.to_csv(
        SECURITY_COVERAGE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

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

        "mpd009_status":
            mpd009_summary.get(
                "status"
            ),

        "processed_rows":
            validation[
                "processed_rows"
            ],

        "expected_rows":
            validation[
                "expected_rows"
            ],

        "unique_securities":
            validation[
                "unique_securities"
            ],

        "expected_securities":
            validation[
                "expected_securities"
            ],

        "row_count_matches":
            validation[
                "row_count_matches"
            ],

        "security_count_matches":
            validation[
                "security_count_matches"
            ],

        "duplicate_keys":
            validation[
                "duplicate_keys"
            ],

        "blank_security_ids":
            validation[
                "blank_security_ids"
            ],

        "blank_symbols":
            validation[
                "blank_symbols"
            ],

        "invalid_dates":
            validation[
                "invalid_dates"
            ],

        "future_dates":
            validation[
                "future_dates"
            ],

        "null_ohlc":
            validation[
                "null_ohlc"
            ],

        "non_positive_prices":
            validation[
                "non_positive_prices"
            ],

        "invalid_ohlc":
            validation[
                "invalid_ohlc"
            ],

        "negative_volume":
            validation[
                "negative_volume"
            ],

        "blank_provenance_rows":
            validation[
                "blank_provenance_rows"
            ],

        "unexpected_source_module":
            validation[
                "unexpected_source_module"
            ],

        "unexpected_validation_module":
            validation[
                "unexpected_validation_module"
            ],

        "unexpected_processing_module":
            validation[
                "unexpected_processing_module"
            ],

        "security_symbol_mismatches":
            validation[
                "security_symbol_mismatches"
            ],

        "symbol_security_mismatches":
            validation[
                "symbol_security_mismatches"
            ],

        "chronology_issues":
            chronology_issues,

        "minimum_rows_per_security":
            coverage_stats[
                "minimum_rows_per_security"
            ],

        "maximum_rows_per_security":
            coverage_stats[
                "maximum_rows_per_security"
            ],

        "median_rows_per_security":
            coverage_stats[
                "median_rows_per_security"
            ],

        "first_session":
            validation[
                "first_session"
            ],

        "last_session":
            validation[
                "last_session"
            ],

        "issue_records":
            len(
                issue_dataframe
            )
            if not (
                issue_dataframe.empty
            )
            else 0,

        "critical_issues":
            critical_issues,

        "processed_dataset_modified":
            False,

        "raw_data_modified":
            False,

        "security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "validation_audit_file":
            str(
                VALIDATION_AUDIT_FILE
            ),

        "validation_issues_file":
            str(
                VALIDATION_ISSUES_FILE
            ),

        "security_coverage_file":
            str(
                SECURITY_COVERAGE_FILE
            ),

        "status":
            status,
    }

    VALIDATION_SUMMARY_FILE.write_text(
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

    separator()

    print(
        "AQSD MARKET PRICE PROCESSED HISTORICAL VALIDATION SUMMARY"
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

    print(
        f"MPD-009 Status                 : "
        f"{summary['mpd009_status']}"
    )

    sub_separator()

    print(
        f"Processed Rows                 : "
        f"{int(summary['processed_rows']):,}"
    )

    print(
        f"Expected Rows                  : "
        f"{int(summary['expected_rows']):,}"
    )

    print(
        f"Unique Securities              : "
        f"{int(summary['unique_securities']):,}"
    )

    print(
        f"Expected Securities            : "
        f"{int(summary['expected_securities']):,}"
    )

    print(
        f"Row Count Matches              : "
        f"{summary['row_count_matches']}"
    )

    print(
        f"Security Count Matches         : "
        f"{summary['security_count_matches']}"
    )

    sub_separator()

    print(
        f"Duplicate Keys                 : "
        f"{int(summary['duplicate_keys']):,}"
    )

    print(
        f"Blank Security IDs             : "
        f"{int(summary['blank_security_ids']):,}"
    )

    print(
        f"Blank Symbols                  : "
        f"{int(summary['blank_symbols']):,}"
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

    sub_separator()

    print(
        f"Blank Provenance Fields        : "
        f"{int(summary['blank_provenance_rows']):,}"
    )

    print(
        f"Unexpected Source Module       : "
        f"{int(summary['unexpected_source_module']):,}"
    )

    print(
        f"Unexpected Validation Module   : "
        f"{int(summary['unexpected_validation_module']):,}"
    )

    print(
        f"Unexpected Processing Module   : "
        f"{int(summary['unexpected_processing_module']):,}"
    )

    print(
        f"Security/Symbol Mismatches     : "
        f"{int(summary['security_symbol_mismatches']):,}"
    )

    print(
        f"Symbol/Security Mismatches     : "
        f"{int(summary['symbol_security_mismatches']):,}"
    )

    print(
        f"Chronology Issues              : "
        f"{int(summary['chronology_issues']):,}"
    )

    sub_separator()

    print(
        f"Minimum Rows / Security        : "
        f"{int(summary['minimum_rows_per_security']):,}"
    )

    print(
        f"Maximum Rows / Security        : "
        f"{int(summary['maximum_rows_per_security']):,}"
    )

    print(
        f"Median Rows / Security         : "
        f"{float(summary['median_rows_per_security']):,.1f}"
    )

    print(
        f"First Session                  : "
        f"{summary['first_session']}"
    )

    print(
        f"Last Session                   : "
        f"{summary['last_session']}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Validation Audit               : "
        f"{summary['validation_audit_file']}"
    )

    print(
        f"Validation Issues              : "
        f"{summary['validation_issues_file']}"
    )

    print(
        f"Security Coverage              : "
        f"{summary['security_coverage_file']}"
    )

    sub_separator()

    print(
        "Processed Dataset              : READ ONLY"
    )

    print(
        "Raw Data                       : READ ONLY"
    )

    print(
        "Security Master                : NOT MODIFIED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Frozen Historical Database     : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
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

        summary = (
            run_validator()
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

        separator()

        print(
            "AQSD MARKET PRICE PROCESSED HISTORICAL VALIDATOR"
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
            "Processed Dataset              : NOT MODIFIED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()