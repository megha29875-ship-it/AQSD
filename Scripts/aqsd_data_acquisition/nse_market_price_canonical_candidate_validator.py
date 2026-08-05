"""
AQSD
Canonical Market Price Candidate Validator

Module ID: MPD-012
Version: 1.0.0
Author: AQSD

Purpose
-------
Independently validate the canonical Market Price candidate created
by MPD-011 before any promotion to the live Market Price Database.

Validation Principles
---------------------
1. MPD-010 must be SUCCESS.
2. MPD-011 must be SUCCESS.
3. Candidate file is reopened from disk.
4. Candidate SHA256 must match MPD-011.
5. Candidate schema must match canonical requirements.
6. Row count and security count must reconcile.
7. trade_date + security_id must be unique.
8. OHLC integrity must hold.
9. Dates must be valid and non-future.
10. Volume must not be negative.
11. Security/symbol/FYERS identity must remain stable.
12. Provenance must be complete and consistent.
13. Chronology must be valid per security.
14. Candidate is READ ONLY.
15. Live Market Price Database is NOT modified.
16. Automatic promotion is PROHIBITED.
17. Historical fabrication is PROHIBITED.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "MPD-012"
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

CANDIDATE_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Candidate"
)


# ============================================================
# INPUT FILES
# ============================================================

CANDIDATE_FILE: Final[Path] = (
    CANDIDATE_ROOT
    / "AQSD_Market_Price_Canonical_Candidate.csv"
)

MPD010_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Validation_Summary.json"
)

MPD011_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Build_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

VALIDATION_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Validation_Audit.csv"
)

VALIDATION_ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Validation_Issues.csv"
)

SECURITY_COVERAGE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Validation_Security_Coverage.csv"
)

VALIDATION_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Validation_Summary.json"
)


# ============================================================
# CANONICAL SCHEMA
# ============================================================

REQUIRED_COLUMNS: Final[list[str]] = [
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
    "source_file",
    "source_module",
    "validation_module",
    "processing_module",
    "processing_version",
    "canonical_builder_module",
    "canonical_builder_version",
    "canonical_candidate_generated_at",
]


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


def file_sha256(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs() -> None:

    required_files = [
        CANDIDATE_FILE,
        MPD010_SUMMARY_FILE,
        MPD011_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-012 input file(s) missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# MPD-010 GATE
# ============================================================

def validate_mpd010() -> dict[str, object]:

    summary = load_json(
        MPD010_SUMMARY_FILE
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

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-010 status is not SUCCESS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-010 contains critical issues."
        )

    return summary


# ============================================================
# MPD-011 GATE
# ============================================================

def validate_mpd011() -> dict[str, object]:

    summary = load_json(
        MPD011_SUMMARY_FILE
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

    candidate_rows = int(
        summary.get(
            "candidate_rows",
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

    candidate_sha256 = safe_text(
        summary.get(
            "candidate_sha256",
            "",
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-011 status is not SUCCESS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-011 contains critical issues."
        )

    if candidate_rows != expected_rows:

        raise RuntimeError(
            "MPD-011 candidate row count mismatch."
        )

    if unique_securities != expected_securities:

        raise RuntimeError(
            "MPD-011 candidate security count mismatch."
        )

    if not row_count_matches:

        raise RuntimeError(
            "MPD-011 row reconciliation failed."
        )

    if not security_count_matches:

        raise RuntimeError(
            "MPD-011 security reconciliation failed."
        )

    if not candidate_sha256:

        raise RuntimeError(
            "MPD-011 candidate SHA256 is blank."
        )

    return summary


# ============================================================
# LOAD CANDIDATE
# ============================================================

def load_candidate() -> pd.DataFrame:

    dataframe = pd.read_csv(
        CANDIDATE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    missing = (
        set(
            REQUIRED_COLUMNS
        )
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Canonical candidate missing required columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    dataframe[
        "trade_date"
    ] = pd.to_datetime(
        dataframe[
            "trade_date"
        ],
        errors="coerce",
    ).dt.normalize()

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
        "fyers_symbol"
    ] = (
        dataframe[
            "fyers_symbol"
        ]
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
    count: int = 1,
    severity: str = "CRITICAL",
    message: str = "",
) -> None:

    issues.append(
        {
            "severity":
                severity,

            "issue_type":
                issue_type,

            "count":
                int(
                    count
                ),

            "message":
                message,
        }
    )


# ============================================================
# VALIDATE SHA256
# ============================================================

def validate_candidate_hash(
    mpd011: dict[str, object],
    issues: list[dict[str, object]],
) -> tuple[
    str,
    str,
    bool,
]:

    expected_sha256 = safe_text(
        mpd011.get(
            "candidate_sha256",
            "",
        )
    )

    actual_sha256 = (
        file_sha256(
            CANDIDATE_FILE
        )
    )

    matches = (
        expected_sha256
        == actual_sha256
    )

    if not matches:

        add_issue(
            issues,
            issue_type="CANDIDATE_SHA256_MISMATCH",
            message=(
                "Canonical candidate SHA256 differs from "
                "the hash recorded by MPD-011."
            ),
        )

    return (
        expected_sha256,
        actual_sha256,
        matches,
    )


# ============================================================
# SCHEMA VALIDATION
# ============================================================

def validate_schema(
    dataframe: pd.DataFrame,
    issues: list[dict[str, object]],
) -> dict[str, object]:

    actual_columns = list(
        dataframe.columns
    )

    required_set = set(
        REQUIRED_COLUMNS
    )

    actual_set = set(
        actual_columns
    )

    missing_columns = sorted(
        required_set
        - actual_set
    )

    extra_columns = sorted(
        actual_set
        - required_set
    )

    exact_column_order = (
        actual_columns
        == REQUIRED_COLUMNS
    )

    if missing_columns:

        add_issue(
            issues,
            issue_type="MISSING_CANONICAL_COLUMNS",
            count=len(
                missing_columns
            ),
            message=(
                "Missing canonical columns: "
                + ", ".join(
                    missing_columns
                )
            ),
        )

    if extra_columns:

        add_issue(
            issues,
            issue_type="EXTRA_CANONICAL_COLUMNS",
            count=len(
                extra_columns
            ),
            message=(
                "Unexpected canonical columns: "
                + ", ".join(
                    extra_columns
                )
            ),
        )

    if not exact_column_order:

        add_issue(
            issues,
            issue_type="CANONICAL_COLUMN_ORDER_MISMATCH",
            message=(
                "Candidate column order does not exactly "
                "match the canonical schema."
            ),
        )

    return {
        "missing_columns":
            len(
                missing_columns
            ),

        "extra_columns":
            len(
                extra_columns
            ),

        "exact_column_order":
            exact_column_order,
    }


# ============================================================
# CORE DATA VALIDATION
# ============================================================

def validate_candidate_dataset(
    dataframe: pd.DataFrame,
    mpd010: dict[str, object],
    mpd011: dict[str, object],
    issues: list[dict[str, object]],
) -> dict[str, object]:

    candidate_rows = int(
        len(
            dataframe
        )
    )

    mpd011_rows = int(
        mpd011[
            "candidate_rows"
        ]
    )

    mpd010_rows = int(
        mpd010[
            "processed_rows"
        ]
    )

    unique_securities = int(
        dataframe[
            "security_id"
        ]
        .nunique()
    )

    mpd011_securities = int(
        mpd011[
            "unique_securities"
        ]
    )

    mpd010_securities = int(
        mpd010[
            "unique_securities"
        ]
    )

    rows_match_mpd011 = (
        candidate_rows
        == mpd011_rows
    )

    rows_match_mpd010 = (
        candidate_rows
        == mpd010_rows
    )

    securities_match_mpd011 = (
        unique_securities
        == mpd011_securities
    )

    securities_match_mpd010 = (
        unique_securities
        == mpd010_securities
    )

    if not rows_match_mpd011:

        add_issue(
            issues,
            issue_type="ROW_COUNT_MISMATCH_MPD011",
            message=(
                f"Candidate rows={candidate_rows:,}; "
                f"MPD-011 rows={mpd011_rows:,}."
            ),
        )

    if not rows_match_mpd010:

        add_issue(
            issues,
            issue_type="ROW_COUNT_MISMATCH_MPD010",
            message=(
                f"Candidate rows={candidate_rows:,}; "
                f"MPD-010 rows={mpd010_rows:,}."
            ),
        )

    if not securities_match_mpd011:

        add_issue(
            issues,
            issue_type="SECURITY_COUNT_MISMATCH_MPD011",
            message=(
                f"Candidate securities={unique_securities:,}; "
                f"MPD-011 securities={mpd011_securities:,}."
            ),
        )

    if not securities_match_mpd010:

        add_issue(
            issues,
            issue_type="SECURITY_COUNT_MISMATCH_MPD010",
            message=(
                f"Candidate securities={unique_securities:,}; "
                f"MPD-010 securities={mpd010_securities:,}."
            ),
        )

    # --------------------------------------------------------
    # Duplicate keys
    # --------------------------------------------------------

    duplicate_keys = int(
        dataframe.duplicated(
            subset=[
                "trade_date",
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    if duplicate_keys:

        add_issue(
            issues,
            issue_type="DUPLICATE_CANONICAL_KEYS",
            count=duplicate_keys,
            message=(
                f"{duplicate_keys:,} rows participate in duplicate "
                "trade_date + security_id keys."
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

    blank_symbols = int(
        dataframe[
            "symbol"
        ]
        .eq("")
        .sum()
    )

    blank_fyers_symbols = int(
        dataframe[
            "fyers_symbol"
        ]
        .eq("")
        .sum()
    )

    if blank_security_ids:

        add_issue(
            issues,
            issue_type="BLANK_SECURITY_ID",
            count=blank_security_ids,
        )

    if blank_symbols:

        add_issue(
            issues,
            issue_type="BLANK_SYMBOL",
            count=blank_symbols,
        )

    if blank_fyers_symbols:

        add_issue(
            issues,
            issue_type="BLANK_FYERS_SYMBOL",
            count=blank_fyers_symbols,
        )

    # --------------------------------------------------------
    # Date validation
    # --------------------------------------------------------

    invalid_dates = int(
        dataframe[
            "trade_date"
        ]
        .isna()
        .sum()
    )

    today = (
        pd.Timestamp.now()
        .normalize()
    )

    future_dates = int(
        (
            dataframe[
                "trade_date"
            ]
            > today
        )
        .fillna(False)
        .sum()
    )

    if invalid_dates:

        add_issue(
            issues,
            issue_type="INVALID_TRADE_DATE",
            count=invalid_dates,
        )

    if future_dates:

        add_issue(
            issues,
            issue_type="FUTURE_TRADE_DATE",
            count=future_dates,
        )

    # --------------------------------------------------------
    # OHLC validation
    # --------------------------------------------------------

    null_ohlc = int(
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
        .sum()
    )

    non_positive_prices = int(
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
        .fillna(False)
        .sum()
    )

    invalid_ohlc = int(
        (
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
        .fillna(False)
        .sum()
    )

    if null_ohlc:

        add_issue(
            issues,
            issue_type="NULL_OHLC",
            count=null_ohlc,
        )

    if non_positive_prices:

        add_issue(
            issues,
            issue_type="NON_POSITIVE_PRICES",
            count=non_positive_prices,
        )

    if invalid_ohlc:

        add_issue(
            issues,
            issue_type="INVALID_OHLC_RELATIONSHIP",
            count=invalid_ohlc,
        )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    negative_volume = int(
        (
            dataframe[
                "volume"
            ]
            < 0
        )
        .fillna(False)
        .sum()
    )

    if negative_volume:

        add_issue(
            issues,
            issue_type="NEGATIVE_VOLUME",
            count=negative_volume,
        )

    # --------------------------------------------------------
    # Identity consistency
    # --------------------------------------------------------

    security_symbol_mismatches = int(
        (
            dataframe
            .groupby(
                "security_id"
            )[
                "symbol"
            ]
            .nunique()
            > 1
        ).sum()
    )

    symbol_security_mismatches = int(
        (
            dataframe
            .groupby(
                "symbol"
            )[
                "security_id"
            ]
            .nunique()
            > 1
        ).sum()
    )

    security_fyers_mismatches = int(
        (
            dataframe
            .groupby(
                "security_id"
            )[
                "fyers_symbol"
            ]
            .nunique()
            > 1
        ).sum()
    )

    if security_symbol_mismatches:

        add_issue(
            issues,
            issue_type="SECURITY_TO_MULTIPLE_SYMBOLS",
            count=security_symbol_mismatches,
        )

    if symbol_security_mismatches:

        add_issue(
            issues,
            issue_type="SYMBOL_TO_MULTIPLE_SECURITIES",
            count=symbol_security_mismatches,
        )

    if security_fyers_mismatches:

        add_issue(
            issues,
            issue_type="SECURITY_TO_MULTIPLE_FYERS_SYMBOLS",
            count=security_fyers_mismatches,
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
        "canonical_builder_module",
        "canonical_builder_version",
        "canonical_candidate_generated_at",
    ]

    blank_provenance = 0

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

        blank_provenance += (
            blanks
        )

        if blanks:

            add_issue(
                issues,
                issue_type=(
                    "BLANK_PROVENANCE_"
                    + column.upper()
                ),
                count=blanks,
            )

    # --------------------------------------------------------
    # Module provenance consistency
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

    unexpected_builder_module = int(
        (
            dataframe[
                "canonical_builder_module"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .ne(
                "MPD-011"
            )
        ).sum()
    )

    if unexpected_source_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_SOURCE_MODULE",
            count=unexpected_source_module,
        )

    if unexpected_validation_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_VALIDATION_MODULE",
            count=unexpected_validation_module,
        )

    if unexpected_processing_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_PROCESSING_MODULE",
            count=unexpected_processing_module,
        )

    if unexpected_builder_module:

        add_issue(
            issues,
            issue_type="UNEXPECTED_CANONICAL_BUILDER_MODULE",
            count=unexpected_builder_module,
        )

    # --------------------------------------------------------
    # Chronology
    # --------------------------------------------------------

    chronology_issues = 0

    for _, group in dataframe.groupby(
        "security_id",
        sort=False,
    ):

        if not (
            group[
                "trade_date"
            ]
            .is_monotonic_increasing
        ):

            chronology_issues += 1

    if chronology_issues:

        add_issue(
            issues,
            issue_type="SECURITY_CHRONOLOGY_ERROR",
            count=chronology_issues,
        )

    # --------------------------------------------------------
    # First / last session
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
        + blank_fyers_symbols
        + invalid_dates
        + future_dates
        + null_ohlc
        + non_positive_prices
        + invalid_ohlc
        + negative_volume
        + security_symbol_mismatches
        + symbol_security_mismatches
        + security_fyers_mismatches
        + blank_provenance
        + unexpected_source_module
        + unexpected_validation_module
        + unexpected_processing_module
        + unexpected_builder_module
        + chronology_issues
    )

    if not rows_match_mpd011:
        critical_issues += 1

    if not rows_match_mpd010:
        critical_issues += 1

    if not securities_match_mpd011:
        critical_issues += 1

    if not securities_match_mpd010:
        critical_issues += 1

    return {
        "candidate_rows":
            candidate_rows,

        "mpd011_rows":
            mpd011_rows,

        "mpd010_rows":
            mpd010_rows,

        "unique_securities":
            unique_securities,

        "mpd011_securities":
            mpd011_securities,

        "mpd010_securities":
            mpd010_securities,

        "rows_match_mpd011":
            rows_match_mpd011,

        "rows_match_mpd010":
            rows_match_mpd010,

        "securities_match_mpd011":
            securities_match_mpd011,

        "securities_match_mpd010":
            securities_match_mpd010,

        "duplicate_keys":
            duplicate_keys,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "blank_fyers_symbols":
            blank_fyers_symbols,

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

        "security_symbol_mismatches":
            security_symbol_mismatches,

        "symbol_security_mismatches":
            symbol_security_mismatches,

        "security_fyers_mismatches":
            security_fyers_mismatches,

        "blank_provenance":
            blank_provenance,

        "unexpected_source_module":
            unexpected_source_module,

        "unexpected_validation_module":
            unexpected_validation_module,

        "unexpected_processing_module":
            unexpected_processing_module,

        "unexpected_builder_module":
            unexpected_builder_module,

        "chronology_issues":
            chronology_issues,

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
) -> pd.DataFrame:

    rows: list[
        dict[str, object]
    ] = []

    for (
        security_id,
        group,
    ) in dataframe.groupby(
        "security_id",
        sort=True,
    ):

        symbol_values = (
            group[
                "symbol"
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

        fyers_values = (
            group[
                "fyers_symbol"
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

        fyers_symbol = (
            fyers_values.iloc[0]
            if not fyers_values.empty
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

        rows.append(
            {
                "security_id":
                    security_id,

                "symbol":
                    symbol,

                "fyers_symbol":
                    fyers_symbol,

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
                    bool(
                        group[
                            "trade_date"
                        ]
                        .is_monotonic_increasing
                    ),

                "duplicate_sessions":
                    int(
                        group.duplicated(
                            subset=[
                                "trade_date",
                            ],
                            keep=False,
                        ).sum()
                    ),
            }
        )

    coverage = pd.DataFrame(
        rows
    )

    return (
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


# ============================================================
# RUN VALIDATOR
# ============================================================

def run_validator() -> dict[str, object]:

    ensure_output_directory()

    validate_inputs()

    mpd010 = (
        validate_mpd010()
    )

    mpd011 = (
        validate_mpd011()
    )

    issues: list[
        dict[str, object]
    ] = []

    (
        expected_sha256,
        actual_sha256,
        sha256_matches,
    ) = validate_candidate_hash(
        mpd011,
        issues,
    )

    dataframe = (
        load_candidate()
    )

    schema = (
        validate_schema(
            dataframe,
            issues,
        )
    )

    validation = (
        validate_candidate_dataset(
            dataframe,
            mpd010,
            mpd011,
            issues,
        )
    )

    coverage = (
        build_security_coverage(
            dataframe
        )
    )

    schema_critical_issues = (
        int(
            schema[
                "missing_columns"
            ]
        )
        + int(
            schema[
                "extra_columns"
            ]
        )
        + (
            0
            if schema[
                "exact_column_order"
            ]
            else 1
        )
    )

    hash_critical_issues = (
        0
        if sha256_matches
        else 1
    )

    critical_issues = (
        int(
            validation[
                "critical_issues"
            ]
        )
        + schema_critical_issues
        + hash_critical_issues
    )

    issue_dataframe = pd.DataFrame(
        issues
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    # --------------------------------------------------------
    # Coverage stats
    # --------------------------------------------------------

    minimum_rows_per_security = 0
    maximum_rows_per_security = 0
    median_rows_per_security = 0.0

    if not coverage.empty:

        minimum_rows_per_security = int(
            coverage[
                "rows"
            ]
            .min()
        )

        maximum_rows_per_security = int(
            coverage[
                "rows"
            ]
            .max()
        )

        median_rows_per_security = float(
            coverage[
                "rows"
            ]
            .median()
        )

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    audit = pd.DataFrame(
        [
            {
                "module_id":
                    MODULE_ID,

                "module_version":
                    MODULE_VERSION,

                "candidate_rows":
                    validation[
                        "candidate_rows"
                    ],

                "unique_securities":
                    validation[
                        "unique_securities"
                    ],

                "sha256_matches":
                    sha256_matches,

                "schema_exact":
                    schema[
                        "exact_column_order"
                    ],

                "duplicate_keys":
                    validation[
                        "duplicate_keys"
                    ],

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
    # Issues
    # --------------------------------------------------------

    if issue_dataframe.empty:

        issue_dataframe = pd.DataFrame(
            columns=[
                "severity",
                "issue_type",
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
    # Coverage
    # --------------------------------------------------------

    coverage.to_csv(
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

        "mpd010_status":
            mpd010.get(
                "status"
            ),

        "mpd011_status":
            mpd011.get(
                "status"
            ),

        "candidate_file":
            str(
                CANDIDATE_FILE
            ),

        "expected_sha256":
            expected_sha256,

        "actual_sha256":
            actual_sha256,

        "sha256_matches":
            sha256_matches,

        "missing_columns":
            schema[
                "missing_columns"
            ],

        "extra_columns":
            schema[
                "extra_columns"
            ],

        "exact_column_order":
            schema[
                "exact_column_order"
            ],

        **validation,

        "minimum_rows_per_security":
            minimum_rows_per_security,

        "maximum_rows_per_security":
            maximum_rows_per_security,

        "median_rows_per_security":
            median_rows_per_security,

        "issue_records":
            int(
                len(
                    issue_dataframe
                )
            ),

        "critical_issues":
            critical_issues,

        "candidate_modified":
            False,

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

        "automatic_promotion":
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

        "promotion_decision":
            (
                "PASS"
                if critical_issues == 0
                else "BLOCK"
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
        "AQSD CANONICAL MARKET PRICE CANDIDATE VALIDATOR"
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
        f"MPD-010 Status                 : "
        f"{summary['mpd010_status']}"
    )

    print(
        f"MPD-011 Status                 : "
        f"{summary['mpd011_status']}"
    )

    sub_separator()

    print(
        f"Candidate Rows                 : "
        f"{int(summary['candidate_rows']):,}"
    )

    print(
        f"MPD-011 Rows                   : "
        f"{int(summary['mpd011_rows']):,}"
    )

    print(
        f"MPD-010 Rows                   : "
        f"{int(summary['mpd010_rows']):,}"
    )

    print(
        f"Rows Match MPD-011             : "
        f"{summary['rows_match_mpd011']}"
    )

    print(
        f"Rows Match MPD-010             : "
        f"{summary['rows_match_mpd010']}"
    )

    sub_separator()

    print(
        f"Unique Securities              : "
        f"{int(summary['unique_securities']):,}"
    )

    print(
        f"MPD-011 Securities             : "
        f"{int(summary['mpd011_securities']):,}"
    )

    print(
        f"MPD-010 Securities             : "
        f"{int(summary['mpd010_securities']):,}"
    )

    print(
        f"Securities Match MPD-011       : "
        f"{summary['securities_match_mpd011']}"
    )

    print(
        f"Securities Match MPD-010       : "
        f"{summary['securities_match_mpd010']}"
    )

    sub_separator()

    print(
        f"SHA256 Matches                 : "
        f"{summary['sha256_matches']}"
    )

    print(
        f"Exact Canonical Column Order   : "
        f"{summary['exact_column_order']}"
    )

    print(
        f"Missing Columns                : "
        f"{int(summary['missing_columns']):,}"
    )

    print(
        f"Extra Columns                  : "
        f"{int(summary['extra_columns']):,}"
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
        f"Blank FYERS Symbols            : "
        f"{int(summary['blank_fyers_symbols']):,}"
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
        f"Security/Symbol Mismatches     : "
        f"{int(summary['security_symbol_mismatches']):,}"
    )

    print(
        f"Symbol/Security Mismatches     : "
        f"{int(summary['symbol_security_mismatches']):,}"
    )

    print(
        f"Security/FYERS Mismatches      : "
        f"{int(summary['security_fyers_mismatches']):,}"
    )

    print(
        f"Blank Provenance               : "
        f"{int(summary['blank_provenance']):,}"
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
        f"Unexpected Builder Module      : "
        f"{int(summary['unexpected_builder_module']):,}"
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

    sub_separator()

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    print(
        f"Promotion Decision             : "
        f"{summary['promotion_decision']}"
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
        "Canonical Candidate            : READ ONLY"
    )

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
        "Live Market Price Database     : NOT MODIFIED"
    )

    print(
        "Frozen Historical Database     : NOT MODIFIED"
    )

    print(
        "Automatic Promotion            : PROHIBITED"
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

        if (
            summary[
                "status"
            ]
            != "SUCCESS"
        ):

            raise SystemExit(1)

    except SystemExit:

        raise

    except Exception as exc:

        print()

        separator()

        print(
            "AQSD CANONICAL MARKET PRICE CANDIDATE VALIDATOR"
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
            "Canonical Candidate            : NOT MODIFIED"
        )

        print(
            "Live Market Price Database     : NOT MODIFIED"
        )

        print(
            "Automatic Promotion            : PROHIBITED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()