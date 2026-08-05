"""
AQSD
Market Price Processed Historical Dataset Builder

Module ID: MPD-009
Version: 1.0.0
Author: AQSD

Purpose
-------
Build a clean, standardized processed historical market-price dataset
from the current-universe raw files already validated by MPD-008.

Rules
-----
1. MPD-008 must be SUCCESS.
2. Only current validated raw securities are processed.
3. Historical out-of-scope raw files are ignored here, not deleted.
4. Raw data is READ ONLY.
5. No canonical MPD write occurs in this module.
6. Every output row retains source/provenance.
7. No historical fabrication.
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

MODULE_ID: Final[str] = "MPD-009"
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

RAW_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Raw"
)

PROCESSED_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Processed"
)


# ============================================================
# INPUT FILES
# ============================================================

MPD008_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Validation_Summary.json"
)

MPD008_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Validation_Audit.csv"
)


# ============================================================
# OUTPUT FILES
# ============================================================

PROCESSED_DATASET_FILE: Final[Path] = (
    PROCESSED_ROOT
    / "AQSD_Market_Price_Processed_Historical.csv"
)

PROCESSED_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Build_Audit.csv"
)

PROCESSED_ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Build_Issues.csv"
)

PROCESSED_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Processed_Historical_Build_Summary.json"
)


# ============================================================
# CONSTANTS
# ============================================================

DATE_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "trade_date",
    "date",
    "session",
    "timestamp",
    "datetime",
    "time",
)

VOLUME_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "volume",
    "vol",
)


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

    PROCESSED_ROOT.mkdir(
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


def first_existing_column(
    dataframe: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str | None:

    for column in candidates:

        if column in dataframe.columns:
            return column

    return None


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs() -> None:

    required_files = [
        MPD008_SUMMARY_FILE,
        MPD008_AUDIT_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-009 input file(s) missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# MPD-008 GATE
# ============================================================

def validate_mpd008() -> dict[str, object]:

    summary = load_json(
        MPD008_SUMMARY_FILE
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

    expected_securities = int(
        summary.get(
            "expected_current_securities",
            0,
        )
    )

    represented = int(
        summary.get(
            "represented_current_securities",
            0,
        )
    )

    failed_files = int(
        summary.get(
            "failed_current_files",
            0,
        )
    )

    current_raw_rows = int(
        summary.get(
            "current_raw_rows",
            0,
        )
    )

    universe_reconciles = bool(
        summary.get(
            "universe_reconciles",
            False,
        )
    )

    row_match = bool(
        summary.get(
            "current_rows_match_mpd007",
            False,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-008 status is not SUCCESS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-008 contains critical issues."
        )

    if failed_files != 0:

        raise RuntimeError(
            "MPD-008 contains failed current raw files."
        )

    if expected_securities != represented:

        raise RuntimeError(
            "MPD-008 current universe representation mismatch."
        )

    if not universe_reconciles:

        raise RuntimeError(
            "MPD-008 universe does not reconcile."
        )

    if not row_match:

        raise RuntimeError(
            "MPD-008 raw rows do not reconcile to MPD-007."
        )

    if current_raw_rows <= 0:

        raise RuntimeError(
            "MPD-008 current raw row count is zero."
        )

    return summary


# ============================================================
# LOAD VALIDATED CURRENT RAW FILE LIST
# ============================================================

def load_current_raw_audit() -> pd.DataFrame:

    dataframe = pd.read_csv(
        MPD008_AUDIT_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    required = {
        "file",
        "security_id",
        "symbol",
        "rows",
        "status",
    }

    missing = (
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "MPD-008 audit missing required columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    dataframe[
        "status"
    ] = (
        dataframe[
            "status"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe = dataframe[
        dataframe[
            "status"
        ].eq(
            "PASS"
        )
    ].copy()

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

    return (
        dataframe
        .sort_values(
            by=[
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# STANDARDIZE ONE RAW FILE
# ============================================================

def standardize_raw_file(
    audit_row: pd.Series,
) -> pd.DataFrame:

    file_path = Path(
        safe_text(
            audit_row[
                "file"
            ]
        )
    )

    if not file_path.exists():

        raise FileNotFoundError(
            f"Validated raw file missing: {file_path}"
        )

    dataframe = pd.read_csv(
        file_path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    date_column = first_existing_column(
        dataframe,
        DATE_COLUMN_CANDIDATES,
    )

    if date_column is None:

        raise RuntimeError(
            f"No date column found in {file_path}"
        )

    required_price_columns = {
        "open",
        "high",
        "low",
        "close",
    }

    missing_prices = (
        required_price_columns
        - set(
            dataframe.columns
        )
    )

    if missing_prices:

        raise RuntimeError(
            f"Raw file {file_path} missing price columns: "
            + ", ".join(
                sorted(
                    missing_prices
                )
            )
        )

    volume_column = first_existing_column(
        dataframe,
        VOLUME_COLUMN_CANDIDATES,
    )

    output = pd.DataFrame()

    output[
        "trade_date"
    ] = pd.to_datetime(
        dataframe[
            date_column
        ],
        errors="coerce",
    ).dt.normalize()

    output[
        "security_id"
    ] = safe_text(
        audit_row[
            "security_id"
        ]
    )

    output[
        "symbol"
    ] = safe_text(
        audit_row[
            "symbol"
        ]
    ).upper()

    for column in (
        "open",
        "high",
        "low",
        "close",
    ):

        output[
            column
        ] = pd.to_numeric(
            dataframe[
                column
            ],
            errors="coerce",
        )

    if volume_column is not None:

        output[
            "volume"
        ] = pd.to_numeric(
            dataframe[
                volume_column
            ],
            errors="coerce",
        )

    else:

        output[
            "volume"
        ] = pd.NA

    if (
        "fyers_symbol"
        in audit_row.index
    ):

        output[
            "fyers_symbol"
        ] = safe_text(
            audit_row[
                "fyers_symbol"
            ]
        ).upper()

    else:

        output[
            "fyers_symbol"
        ] = ""

    output[
        "source"
    ] = "FYERS_HISTORY_API"

    output[
        "source_file"
    ] = str(
        file_path
    )

    output[
        "source_module"
    ] = "MPD-007"

    output[
        "validation_module"
    ] = "MPD-008"

    output[
        "processing_module"
    ] = MODULE_ID

    output[
        "processing_version"
    ] = MODULE_VERSION

    output[
        "processed_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    return output


# ============================================================
# BUILD PROCESSED DATASET
# ============================================================

def build_processed_dataset(
    audit: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:

    frames: list[
        pd.DataFrame
    ] = []

    issues: list[
        dict[str, object]
    ] = []

    for number, row in audit.iterrows():

        try:

            processed = (
                standardize_raw_file(
                    row
                )
            )

            frames.append(
                processed
            )

            print(
                f"[{number + 1:03d}/{len(audit):03d}] "
                f"{row['symbol']} "
                f"| rows={len(processed):,} "
                f"| SUCCESS"
            )

        except Exception as exc:

            issues.append(
                {
                    "security_id":
                        safe_text(
                            row.get(
                                "security_id",
                                "",
                            )
                        ),

                    "symbol":
                        safe_text(
                            row.get(
                                "symbol",
                                "",
                            )
                        ),

                    "file":
                        safe_text(
                            row.get(
                                "file",
                                "",
                            )
                        ),

                    "issue_type":
                        "PROCESSING_FAILURE",

                    "message":
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                }
            )

            print(
                f"[{number + 1:03d}/{len(audit):03d}] "
                f"{row['symbol']} "
                f"| FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

    if not frames:

        raise RuntimeError(
            "No processed historical rows were produced."
        )

    processed_all = pd.concat(
        frames,
        ignore_index=True,
    )

    issues_dataframe = pd.DataFrame(
        issues
    )

    return (
        processed_all,
        issues_dataframe,
    )


# ============================================================
# DATASET VALIDATION
# ============================================================

def validate_processed_dataset(
    processed: pd.DataFrame,
    mpd008_summary: dict[str, object],
    expected_security_count: int,
) -> dict[str, object]:

    rows = int(
        len(
            processed
        )
    )

    expected_rows = int(
        mpd008_summary[
            "current_raw_rows"
        ]
    )

    unique_securities = int(
        processed[
            "security_id"
        ]
        .nunique()
    )

    row_count_matches = (
        rows
        == expected_rows
    )

    security_count_matches = (
        unique_securities
        == expected_security_count
    )

    duplicate_keys = int(
        processed.duplicated(
            subset=[
                "trade_date",
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    blank_security_ids = int(
        processed[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_symbols = int(
        processed[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    invalid_dates = int(
        processed[
            "trade_date"
        ]
        .isna()
        .sum()
    )

    null_ohlc = int(
        processed[
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
                processed[
                    "high"
                ]
                < processed[
                    "low"
                ]
            )
            |
            (
                processed[
                    "high"
                ]
                < processed[
                    "open"
                ]
            )
            |
            (
                processed[
                    "high"
                ]
                < processed[
                    "close"
                ]
            )
            |
            (
                processed[
                    "low"
                ]
                > processed[
                    "open"
                ]
            )
            |
            (
                processed[
                    "low"
                ]
                > processed[
                    "close"
                ]
            )
        )
        .fillna(False)
        .sum()
    )

    negative_volume = int(
        (
            pd.to_numeric(
                processed[
                    "volume"
                ],
                errors="coerce",
            )
            < 0
        )
        .fillna(False)
        .sum()
    )

    critical_issues = (
        duplicate_keys
        + blank_security_ids
        + blank_symbols
        + invalid_dates
        + null_ohlc
        + invalid_ohlc
        + negative_volume
    )

    if not row_count_matches:

        critical_issues += 1

    if not security_count_matches:

        critical_issues += 1

    first_session = ""

    last_session = ""

    if not processed.empty:

        valid_dates = (
            processed[
                "trade_date"
            ]
            .dropna()
        )

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

    return {
        "processed_rows":
            rows,

        "expected_rows":
            expected_rows,

        "unique_securities":
            unique_securities,

        "expected_securities":
            expected_security_count,

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

        "null_ohlc":
            null_ohlc,

        "invalid_ohlc":
            invalid_ohlc,

        "negative_volume":
            negative_volume,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# RUN
# ============================================================

def run_builder() -> dict[str, object]:

    ensure_directories()

    validate_inputs()

    mpd008_summary = (
        validate_mpd008()
    )

    audit = (
        load_current_raw_audit()
    )

    expected_security_count = int(
        mpd008_summary[
            "expected_current_securities"
        ]
    )

    if len(
        audit
    ) != expected_security_count:

        raise RuntimeError(
            "MPD-008 PASS file count does not match "
            "expected current security count."
        )

    print()

    separator()

    print(
        "AQSD MARKET PRICE PROCESSED HISTORICAL BUILDER"
    )

    separator()

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Validated Current Raw Files    : "
        f"{len(audit):,}"
    )

    print(
        f"Expected Raw Rows              : "
        f"{int(mpd008_summary['current_raw_rows']):,}"
    )

    sub_separator()

    processed, issues = (
        build_processed_dataset(
            audit
        )
    )

    validation = (
        validate_processed_dataset(
            processed,
            mpd008_summary,
            expected_security_count,
        )
    )

    processing_failures = int(
        len(
            issues
        )
    )

    critical_issues = int(
        validation[
            "critical_issues"
        ]
    ) + processing_failures

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    processed = (
        processed
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

    processed.to_csv(
        PROCESSED_DATASET_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    if issues.empty:

        issues = pd.DataFrame(
            columns=[
                "security_id",
                "symbol",
                "file",
                "issue_type",
                "message",
            ]
        )

    issues.to_csv(
        PROCESSED_ISSUES_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    audit_summary = pd.DataFrame(
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

                "critical_issues":
                    critical_issues,

                "status":
                    status,
            }
        ]
    )

    audit_summary.to_csv(
        PROCESSED_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
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

        "mpd008_status":
            mpd008_summary.get(
                "status"
            ),

        "validated_raw_files":
            len(
                audit
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

        "null_ohlc":
            validation[
                "null_ohlc"
            ],

        "invalid_ohlc":
            validation[
                "invalid_ohlc"
            ],

        "negative_volume":
            validation[
                "negative_volume"
            ],

        "processing_failures":
            processing_failures,

        "first_session":
            validation[
                "first_session"
            ],

        "last_session":
            validation[
                "last_session"
            ],

        "critical_issues":
            critical_issues,

        "processed_dataset_file":
            str(
                PROCESSED_DATASET_FILE
            ),

        "processed_audit_file":
            str(
                PROCESSED_AUDIT_FILE
            ),

        "processed_issues_file":
            str(
                PROCESSED_ISSUES_FILE
            ),

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

        "status":
            status,
    }

    PROCESSED_SUMMARY_FILE.write_text(
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
        "AQSD MARKET PRICE PROCESSED HISTORICAL BUILD SUMMARY"
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
        f"MPD-008 Status                 : "
        f"{summary['mpd008_status']}"
    )

    sub_separator()

    print(
        f"Validated Raw Files            : "
        f"{int(summary['validated_raw_files']):,}"
    )

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

    sub_separator()

    print(
        f"Row Count Matches              : "
        f"{summary['row_count_matches']}"
    )

    print(
        f"Security Count Matches         : "
        f"{summary['security_count_matches']}"
    )

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
        f"Null OHLC                      : "
        f"{int(summary['null_ohlc']):,}"
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
        f"Processing Failures            : "
        f"{int(summary['processing_failures']):,}"
    )

    sub_separator()

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
        f"Processed Dataset              : "
        f"{summary['processed_dataset_file']}"
    )

    print(
        f"Processed Audit                : "
        f"{summary['processed_audit_file']}"
    )

    print(
        f"Processed Issues               : "
        f"{summary['processed_issues_file']}"
    )

    sub_separator()

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
            run_builder()
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
            "AQSD MARKET PRICE PROCESSED HISTORICAL BUILDER"
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
            "Raw Data                       : NOT MODIFIED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()