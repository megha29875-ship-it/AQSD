"""
AQSD
Canonical Market Price Candidate Builder

Module ID: MPD-011
Version: 1.0.0
Author: AQSD

Purpose
-------
Build a candidate canonical Market Price Dataset from the processed
historical dataset that has already passed MPD-010 validation.

Architecture
------------
MPD-009
    |
    v
Processed Historical Dataset
    |
    v
MPD-010
Independent Validation
    |
    v
MPD-011
Canonical Candidate Builder
    |
    v
Candidate Canonical Dataset

Important Rules
---------------
1. MPD-010 must be SUCCESS.
2. MPD-010 must contain zero critical issues.
3. Processed historical dataset is READ ONLY.
4. Security Master is NOT modified.
5. Live Market Price Database is NOT modified.
6. Frozen historical database is NOT modified.
7. Candidate output must reconcile exactly with MPD-010.
8. trade_date + security_id must remain unique.
9. No historical fabrication.
10. Candidate promotion is NOT performed here.
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

MODULE_ID: Final[str] = "MPD-011"
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

CANDIDATE_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Candidate"
)


# ============================================================
# INPUT FILES
# ============================================================

PROCESSED_DATASET_FILE: Final[Path] = (
    PROCESSED_ROOT
    / "AQSD_Market_Price_Processed_Historical.csv"
)

MPD010_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Validation_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

CANDIDATE_FILE: Final[Path] = (
    CANDIDATE_ROOT
    / "AQSD_Market_Price_Canonical_Candidate.csv"
)

CANDIDATE_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Build_Audit.csv"
)

CANDIDATE_ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Build_Issues.csv"
)

CANDIDATE_SECURITY_COVERAGE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Security_Coverage.csv"
)

CANDIDATE_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Build_Summary.json"
)


# ============================================================
# CANONICAL SCHEMA
# ============================================================

CANONICAL_COLUMNS: Final[list[str]] = [
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


def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CANDIDATE_ROOT.mkdir(
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
        PROCESSED_DATASET_FILE,
        MPD010_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-011 input file(s) missing: "
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

    duplicate_keys = int(
        summary.get(
            "duplicate_keys",
            0,
        )
    )

    chronology_issues = int(
        summary.get(
            "chronology_issues",
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

    if processed_rows != expected_rows:

        raise RuntimeError(
            "MPD-010 row count does not reconcile."
        )

    if unique_securities != expected_securities:

        raise RuntimeError(
            "MPD-010 security count does not reconcile."
        )

    if not row_count_matches:

        raise RuntimeError(
            "MPD-010 row count match is False."
        )

    if not security_count_matches:

        raise RuntimeError(
            "MPD-010 security count match is False."
        )

    if duplicate_keys != 0:

        raise RuntimeError(
            "MPD-010 contains duplicate canonical keys."
        )

    if chronology_issues != 0:

        raise RuntimeError(
            "MPD-010 contains chronology issues."
        )

    return summary


# ============================================================
# LOAD PROCESSED DATA
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

    required_columns = {
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
    }

    missing = (
        required_columns
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Processed dataset missing required columns: "
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
# BUILD CANONICAL CANDIDATE
# ============================================================

def build_candidate(
    processed: pd.DataFrame,
) -> pd.DataFrame:

    candidate = processed.copy()

    generated_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    candidate[
        "canonical_builder_module"
    ] = MODULE_ID

    candidate[
        "canonical_builder_version"
    ] = MODULE_VERSION

    candidate[
        "canonical_candidate_generated_at"
    ] = generated_at

    candidate = candidate[
        CANONICAL_COLUMNS
    ].copy()

    candidate = (
        candidate
        .sort_values(
            by=[
                "trade_date",
                "security_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return candidate


# ============================================================
# VALIDATE CANDIDATE
# ============================================================

def validate_candidate(
    candidate: pd.DataFrame,
    mpd010: dict[str, object],
) -> tuple[
    dict[str, object],
    pd.DataFrame,
]:

    issues: list[
        dict[str, object]
    ] = []

    candidate_rows = int(
        len(
            candidate
        )
    )

    expected_rows = int(
        mpd010[
            "processed_rows"
        ]
    )

    unique_securities = int(
        candidate[
            "security_id"
        ]
        .nunique()
    )

    expected_securities = int(
        mpd010[
            "unique_securities"
        ]
    )

    row_count_matches = (
        candidate_rows
        == expected_rows
    )

    security_count_matches = (
        unique_securities
        == expected_securities
    )

    # --------------------------------------------------------
    # Duplicate canonical key
    # --------------------------------------------------------

    duplicate_keys = int(
        candidate.duplicated(
            subset=[
                "trade_date",
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    if duplicate_keys:

        issues.append(
            {
                "issue_type":
                    "DUPLICATE_CANONICAL_KEY",

                "count":
                    duplicate_keys,

                "message":
                    (
                        f"{duplicate_keys:,} rows participate in "
                        "duplicate trade_date + security_id keys."
                    ),
            }
        )

    # --------------------------------------------------------
    # Blank identity
    # --------------------------------------------------------

    blank_security_ids = int(
        candidate[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if blank_security_ids:

        issues.append(
            {
                "issue_type":
                    "BLANK_SECURITY_ID",

                "count":
                    blank_security_ids,

                "message":
                    (
                        f"{blank_security_ids:,} candidate rows "
                        "have blank security_id."
                    ),
            }
        )

    blank_symbols = int(
        candidate[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if blank_symbols:

        issues.append(
            {
                "issue_type":
                    "BLANK_SYMBOL",

                "count":
                    blank_symbols,

                "message":
                    (
                        f"{blank_symbols:,} candidate rows "
                        "have blank symbol."
                    ),
            }
        )

    blank_fyers_symbols = int(
        candidate[
            "fyers_symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if blank_fyers_symbols:

        issues.append(
            {
                "issue_type":
                    "BLANK_FYERS_SYMBOL",

                "count":
                    blank_fyers_symbols,

                "message":
                    (
                        f"{blank_fyers_symbols:,} candidate rows "
                        "have blank FYERS symbol."
                    ),
            }
        )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    invalid_dates = int(
        candidate[
            "trade_date"
        ]
        .isna()
        .sum()
    )

    if invalid_dates:

        issues.append(
            {
                "issue_type":
                    "INVALID_TRADE_DATE",

                "count":
                    invalid_dates,

                "message":
                    (
                        f"{invalid_dates:,} candidate rows "
                        "contain invalid trade dates."
                    ),
            }
        )

    today = (
        pd.Timestamp.now()
        .normalize()
    )

    future_dates = int(
        (
            candidate[
                "trade_date"
            ]
            > today
        )
        .fillna(False)
        .sum()
    )

    if future_dates:

        issues.append(
            {
                "issue_type":
                    "FUTURE_TRADE_DATE",

                "count":
                    future_dates,

                "message":
                    (
                        f"{future_dates:,} candidate rows "
                        "contain future dates."
                    ),
            }
        )

    # --------------------------------------------------------
    # OHLC
    # --------------------------------------------------------

    null_ohlc = int(
        candidate[
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

    invalid_ohlc = int(
        (
            (
                candidate[
                    "high"
                ]
                < candidate[
                    "low"
                ]
            )
            |
            (
                candidate[
                    "high"
                ]
                < candidate[
                    "open"
                ]
            )
            |
            (
                candidate[
                    "high"
                ]
                < candidate[
                    "close"
                ]
            )
            |
            (
                candidate[
                    "low"
                ]
                > candidate[
                    "open"
                ]
            )
            |
            (
                candidate[
                    "low"
                ]
                > candidate[
                    "close"
                ]
            )
        )
        .fillna(False)
        .sum()
    )

    non_positive_prices = int(
        (
            candidate[
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
        .sum()
    )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    negative_volume = int(
        (
            candidate[
                "volume"
            ]
            < 0
        )
        .fillna(False)
        .sum()
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
            candidate[
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

            issues.append(
                {
                    "issue_type":
                        (
                            "BLANK_PROVENANCE_"
                            + column.upper()
                        ),

                    "count":
                        blanks,

                    "message":
                        (
                            f"{blanks:,} rows contain blank "
                            f"{column}."
                        ),
                }
            )

    # --------------------------------------------------------
    # Identity relationships
    # --------------------------------------------------------

    security_symbol_mismatches = int(
        (
            candidate
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
            candidate
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
            candidate
            .groupby(
                "security_id"
            )[
                "fyers_symbol"
            ]
            .nunique()
            > 1
        ).sum()
    )

    # --------------------------------------------------------
    # Chronology
    # --------------------------------------------------------

    chronology_issues = 0

    for _, group in candidate.groupby(
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

    # --------------------------------------------------------
    # First and last session
    # --------------------------------------------------------

    valid_dates = (
        candidate[
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
    # Critical issues
    # --------------------------------------------------------

    critical_issues = (
        duplicate_keys
        + blank_security_ids
        + blank_symbols
        + blank_fyers_symbols
        + invalid_dates
        + future_dates
        + null_ohlc
        + invalid_ohlc
        + non_positive_prices
        + negative_volume
        + blank_provenance
        + security_symbol_mismatches
        + symbol_security_mismatches
        + security_fyers_mismatches
        + chronology_issues
    )

    if not row_count_matches:

        critical_issues += 1

        issues.append(
            {
                "issue_type":
                    "ROW_COUNT_MISMATCH",

                "count":
                    1,

                "message":
                    (
                        f"Candidate rows={candidate_rows:,}; "
                        f"expected={expected_rows:,}."
                    ),
            }
        )

    if not security_count_matches:

        critical_issues += 1

        issues.append(
            {
                "issue_type":
                    "SECURITY_COUNT_MISMATCH",

                "count":
                    1,

                "message":
                    (
                        f"Candidate securities="
                        f"{unique_securities:,}; expected="
                        f"{expected_securities:,}."
                    ),
            }
        )

    issues_dataframe = pd.DataFrame(
        issues
    )

    return (
        {
            "candidate_rows":
                candidate_rows,

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

            "blank_fyers_symbols":
                blank_fyers_symbols,

            "invalid_dates":
                invalid_dates,

            "future_dates":
                future_dates,

            "null_ohlc":
                null_ohlc,

            "invalid_ohlc":
                invalid_ohlc,

            "non_positive_prices":
                non_positive_prices,

            "negative_volume":
                negative_volume,

            "blank_provenance":
                blank_provenance,

            "security_symbol_mismatches":
                security_symbol_mismatches,

            "symbol_security_mismatches":
                symbol_security_mismatches,

            "security_fyers_mismatches":
                security_fyers_mismatches,

            "chronology_issues":
                chronology_issues,

            "first_session":
                first_session,

            "last_session":
                last_session,

            "critical_issues":
                critical_issues,
        },
        issues_dataframe,
    )


# ============================================================
# SECURITY COVERAGE
# ============================================================

def build_security_coverage(
    candidate: pd.DataFrame,
) -> pd.DataFrame:

    coverage = (
        candidate
        .groupby(
            [
                "security_id",
                "symbol",
                "fyers_symbol",
            ],
            as_index=False,
        )
        .agg(
            rows=(
                "trade_date",
                "size",
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
    )

    coverage[
        "first_session"
    ] = (
        pd.to_datetime(
            coverage[
                "first_session"
            ],
            errors="coerce",
        )
        .dt.date
        .astype(str)
    )

    coverage[
        "last_session"
    ] = (
        pd.to_datetime(
            coverage[
                "last_session"
            ],
            errors="coerce",
        )
        .dt.date
        .astype(str)
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

    return coverage


# ============================================================
# RUN BUILDER
# ============================================================

def run_builder() -> dict[str, object]:

    ensure_directories()

    validate_inputs()

    mpd010 = (
        validate_mpd010()
    )

    processed = (
        load_processed_dataset()
    )

    candidate = (
        build_candidate(
            processed
        )
    )

    (
        validation,
        issues,
    ) = validate_candidate(
        candidate,
        mpd010,
    )

    coverage = (
        build_security_coverage(
            candidate
        )
    )

    status = (
        "SUCCESS"
        if validation[
            "critical_issues"
        ] == 0
        else "FAILED"
    )

    # --------------------------------------------------------
    # Candidate output
    # --------------------------------------------------------

    candidate.to_csv(
        CANDIDATE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Issues
    # --------------------------------------------------------

    if issues.empty:

        issues = pd.DataFrame(
            columns=[
                "issue_type",
                "count",
                "message",
            ]
        )

    issues.to_csv(
        CANDIDATE_ISSUES_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Coverage
    # --------------------------------------------------------

    coverage.to_csv(
        CANDIDATE_SECURITY_COVERAGE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Candidate hash
    # --------------------------------------------------------

    candidate_sha256 = (
        file_sha256(
            CANDIDATE_FILE
        )
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

                "critical_issues":
                    validation[
                        "critical_issues"
                    ],

                "candidate_sha256":
                    candidate_sha256,

                "status":
                    status,
            }
        ]
    )

    audit.to_csv(
        CANDIDATE_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Row coverage statistics
    # --------------------------------------------------------

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

        "candidate_rows":
            validation[
                "candidate_rows"
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

        "blank_fyers_symbols":
            validation[
                "blank_fyers_symbols"
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

        "invalid_ohlc":
            validation[
                "invalid_ohlc"
            ],

        "non_positive_prices":
            validation[
                "non_positive_prices"
            ],

        "negative_volume":
            validation[
                "negative_volume"
            ],

        "blank_provenance":
            validation[
                "blank_provenance"
            ],

        "security_symbol_mismatches":
            validation[
                "security_symbol_mismatches"
            ],

        "symbol_security_mismatches":
            validation[
                "symbol_security_mismatches"
            ],

        "security_fyers_mismatches":
            validation[
                "security_fyers_mismatches"
            ],

        "chronology_issues":
            validation[
                "chronology_issues"
            ],

        "minimum_rows_per_security":
            minimum_rows_per_security,

        "maximum_rows_per_security":
            maximum_rows_per_security,

        "median_rows_per_security":
            median_rows_per_security,

        "first_session":
            validation[
                "first_session"
            ],

        "last_session":
            validation[
                "last_session"
            ],

        "candidate_sha256":
            candidate_sha256,

        "critical_issues":
            validation[
                "critical_issues"
            ],

        "candidate_file":
            str(
                CANDIDATE_FILE
            ),

        "candidate_audit_file":
            str(
                CANDIDATE_AUDIT_FILE
            ),

        "candidate_issues_file":
            str(
                CANDIDATE_ISSUES_FILE
            ),

        "candidate_security_coverage_file":
            str(
                CANDIDATE_SECURITY_COVERAGE_FILE
            ),

        "processed_dataset_modified":
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

        "status":
            status,
    }

    CANDIDATE_SUMMARY_FILE.write_text(
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
        "AQSD CANONICAL MARKET PRICE CANDIDATE BUILDER"
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

    sub_separator()

    print(
        f"Candidate Rows                 : "
        f"{int(summary['candidate_rows']):,}"
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
        f"Invalid OHLC                   : "
        f"{int(summary['invalid_ohlc']):,}"
    )

    print(
        f"Non-Positive Prices            : "
        f"{int(summary['non_positive_prices']):,}"
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
        f"Chronology Issues              : "
        f"{int(summary['chronology_issues']):,}"
    )

    print(
        f"Blank Provenance               : "
        f"{int(summary['blank_provenance']):,}"
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
        f"Candidate SHA256               : "
        f"{summary['candidate_sha256']}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Candidate File                 : "
        f"{summary['candidate_file']}"
    )

    print(
        f"Candidate Audit                : "
        f"{summary['candidate_audit_file']}"
    )

    print(
        f"Candidate Issues               : "
        f"{summary['candidate_issues_file']}"
    )

    print(
        f"Security Coverage              : "
        f"{summary['candidate_security_coverage_file']}"
    )

    sub_separator()

    print(
        "Processed Dataset              : READ ONLY"
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
            run_builder()
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
            "AQSD CANONICAL MARKET PRICE CANDIDATE BUILDER"
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
            "Live Market Price Database     : NOT MODIFIED"
        )

        print(
            "Frozen Historical Database     : NOT MODIFIED"
        )

        print(
            "Automatic Promotion            : PROHIBITED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()