"""
AQSD
NSE Market Price Post-Recovery Validator

Module : MPD-VAL-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Perform a full validation of consolidated historical market-price data
after historical recovery has completed.

This validator confirms that the historical dataset is safe to move
forward into canonical/database promotion.

Validation Scope
----------------
- Expected security coverage
- Missing consolidated history files
- Duplicate trading dates
- Invalid dates
- Future dates
- Null OHLC
- Non-positive OHLC
- Invalid OHLC relationships
- Negative volume
- Blank security IDs
- Blank symbols
- Security ID reconciliation
- Symbol reconciliation
- FYERS symbol reconciliation
- Chronological integrity
- First and last session coverage
- Row-count statistics

Protection
----------
- Historical files are READ ONLY
- Security Master is READ ONLY
- Market Price database is NOT modified
- Immutable acquisition archives are NOT modified
- No historical fabrication
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

MODULE_ID: Final[str] = "MPD-VAL-001"
MODULE_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

RAW_ROOT: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "Market_Price"
    / "Raw"
)

ACQUISITION_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue.csv"
)

SECURITY_MASTER_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)


# ============================================================
# OUTPUT FILES
# ============================================================

VALIDATION_AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Post_Recovery_Validation_Audit.csv"
)

VALIDATION_ISSUES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Post_Recovery_Validation_Issues.csv"
)

SECURITY_SUMMARY_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Post_Recovery_Security_Summary.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Post_Recovery_Validation_Summary.json"
)


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_HISTORY_COLUMNS: Final[set[str]] = {
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
    "downloaded_at",
}


# ============================================================
# GENERAL HELPERS
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


def safe_filename(
    symbol: str,
) -> str:

    return (
        str(symbol)
        .strip()
        .replace(":", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


# ============================================================
# EXPECTED UNIVERSE
# ============================================================

def load_expected_universe() -> pd.DataFrame:

    if not ACQUISITION_QUEUE_FILE.exists():

        raise FileNotFoundError(
            "Acquisition queue not found: "
            f"{ACQUISITION_QUEUE_FILE}"
        )

    dataframe = pd.read_csv(
        ACQUISITION_QUEUE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
    }

    missing = sorted(
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Acquisition queue missing required columns: "
            + ", ".join(
                missing
            )
        )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if (
        "acquisition_symbol"
        in dataframe.columns
    ):

        dataframe["fyers_symbol"] = (
            dataframe["acquisition_symbol"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    elif (
        "fyers_symbol"
        in dataframe.columns
    ):

        dataframe["fyers_symbol"] = (
            dataframe["fyers_symbol"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        dataframe["fyers_symbol"] = ""

    dataframe = dataframe[
        dataframe[
            "security_id"
        ].ne("")
    ].copy()

    dataframe = dataframe[
        dataframe[
            "symbol"
        ].ne("")
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .sort_values(
            by=[
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe[
        [
            "security_id",
            "symbol",
            "fyers_symbol",
        ]
    ].copy()


# ============================================================
# SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_FILE.exists():

        return pd.DataFrame(
            columns=[
                "security_id",
                "symbol",
            ]
        )

    dataframe = pd.read_csv(
        SECURITY_MASTER_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
    }

    if not required.issubset(
        dataframe.columns
    ):

        return pd.DataFrame(
            columns=[
                "security_id",
                "symbol",
            ]
        )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .fillna("")
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
        .reset_index(
            drop=True
        )
    )


# ============================================================
# HISTORY FILE
# ============================================================

def get_history_file(
    symbol: str,
) -> Path:

    return (
        RAW_ROOT
        / safe_filename(
            symbol
        )
        / "daily_history.csv"
    )


# ============================================================
# LOAD HISTORY
# ============================================================

def load_history_file(
    path: Path,
) -> pd.DataFrame:

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    missing = sorted(
        REQUIRED_HISTORY_COLUMNS
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Missing required columns: "
            + ", ".join(
                missing
            )
        )

    dataframe["security_id"] = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe["symbol"] = (
        dataframe["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["fyers_symbol"] = (
        dataframe["fyers_symbol"]
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

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    return dataframe


# ============================================================
# SINGLE SECURITY VALIDATION
# ============================================================

def validate_security(
    *,
    expected_security_id: str,
    expected_symbol: str,
    expected_fyers_symbol: str,
    history_file: Path,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
]:

    issues: list[
        dict[str, object]
    ] = []

    if not history_file.exists():

        summary = {
            "security_id":
                expected_security_id,
            "symbol":
                expected_symbol,
            "fyers_symbol":
                expected_fyers_symbol,
            "history_file":
                str(
                    history_file
                ),
            "file_exists":
                False,
            "rows":
                0,
            "first_session":
                "",
            "last_session":
                "",
            "duplicate_dates":
                0,
            "invalid_dates":
                0,
            "future_dates":
                0,
            "null_ohlc":
                0,
            "non_positive_ohlc":
                0,
            "invalid_ohlc":
                0,
            "negative_volume":
                0,
            "blank_security_ids":
                0,
            "blank_symbols":
                0,
            "security_id_mismatch":
                0,
            "symbol_mismatch":
                0,
            "fyers_symbol_mismatch":
                0,
            "chronology_issue":
                0,
            "critical_issues":
                1,
            "status":
                "FAILED",
        }

        issues.append(
            {
                "security_id":
                    expected_security_id,
                "symbol":
                    expected_symbol,
                "issue_type":
                    "MISSING_HISTORY_FILE",
                "trade_date":
                    "",
                "details":
                    str(
                        history_file
                    ),
            }
        )

        return (
            summary,
            issues,
        )

    try:

        dataframe = load_history_file(
            history_file
        )

    except Exception as exc:

        summary = {
            "security_id":
                expected_security_id,
            "symbol":
                expected_symbol,
            "fyers_symbol":
                expected_fyers_symbol,
            "history_file":
                str(
                    history_file
                ),
            "file_exists":
                True,
            "rows":
                0,
            "first_session":
                "",
            "last_session":
                "",
            "duplicate_dates":
                0,
            "invalid_dates":
                0,
            "future_dates":
                0,
            "null_ohlc":
                0,
            "non_positive_ohlc":
                0,
            "invalid_ohlc":
                0,
            "negative_volume":
                0,
            "blank_security_ids":
                0,
            "blank_symbols":
                0,
            "security_id_mismatch":
                0,
            "symbol_mismatch":
                0,
            "fyers_symbol_mismatch":
                0,
            "chronology_issue":
                0,
            "critical_issues":
                1,
            "status":
                "FAILED",
        }

        issues.append(
            {
                "security_id":
                    expected_security_id,
                "symbol":
                    expected_symbol,
                "issue_type":
                    "HISTORY_FILE_READ_ERROR",
                "trade_date":
                    "",
                "details":
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
            }
        )

        return (
            summary,
            issues,
        )

    # ========================================================
    # CORE COUNTS
    # ========================================================

    total_rows = int(
        len(
            dataframe
        )
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    parsed_dates = pd.to_datetime(
        dataframe[
            "trade_date"
        ],
        errors="coerce",
    )

    invalid_date_mask = (
        parsed_dates.isna()
    )

    invalid_dates = int(
        invalid_date_mask.sum()
    )

    future_date_mask = (
        parsed_dates.notna()
        &
        (
            parsed_dates.dt.date
            > date.today()
        )
    )

    future_dates = int(
        future_date_mask.sum()
    )

    # --------------------------------------------------------
    # Duplicate dates
    # --------------------------------------------------------

    duplicate_date_mask = (
        dataframe.duplicated(
            subset=[
                "trade_date",
            ],
            keep=False,
        )
    )

    duplicate_dates = int(
        duplicate_date_mask.sum()
    )

    # --------------------------------------------------------
    # OHLC
    # --------------------------------------------------------

    numeric_ohlc = dataframe[
        [
            "open",
            "high",
            "low",
            "close",
        ]
    ]

    null_ohlc_mask = (
        numeric_ohlc.isna().any(
            axis=1
        )
    )

    null_ohlc = int(
        null_ohlc_mask.sum()
    )

    non_positive_ohlc_mask = (
        (
            numeric_ohlc
            <= 0
        ).any(
            axis=1
        )
    )

    non_positive_ohlc = int(
        non_positive_ohlc_mask.sum()
    )

    invalid_ohlc_mask = (
        (
            dataframe[
                "high"
            ]
            <
            dataframe[
                "low"
            ]
        )
        |
        (
            dataframe[
                "open"
            ]
            <
            dataframe[
                "low"
            ]
        )
        |
        (
            dataframe[
                "open"
            ]
            >
            dataframe[
                "high"
            ]
        )
        |
        (
            dataframe[
                "close"
            ]
            <
            dataframe[
                "low"
            ]
        )
        |
        (
            dataframe[
                "close"
            ]
            >
            dataframe[
                "high"
            ]
        )
    ).fillna(
        False
    )

    invalid_ohlc = int(
        invalid_ohlc_mask.sum()
    )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    negative_volume_mask = (
        dataframe[
            "volume"
        ]
        < 0
    ).fillna(
        False
    )

    negative_volume = int(
        negative_volume_mask.sum()
    )

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    blank_security_id_mask = (
        dataframe[
            "security_id"
        ]
        .eq("")
    )

    blank_security_ids = int(
        blank_security_id_mask.sum()
    )

    blank_symbol_mask = (
        dataframe[
            "symbol"
        ]
        .eq("")
    )

    blank_symbols = int(
        blank_symbol_mask.sum()
    )

    security_id_mismatch_mask = (
        dataframe[
            "security_id"
        ]
        .ne(
            expected_security_id
        )
    )

    security_id_mismatch = int(
        security_id_mismatch_mask.sum()
    )

    symbol_mismatch_mask = (
        dataframe[
            "symbol"
        ]
        .ne(
            expected_symbol
        )
    )

    symbol_mismatch = int(
        symbol_mismatch_mask.sum()
    )

    if expected_fyers_symbol:

        fyers_symbol_mismatch_mask = (
            dataframe[
                "fyers_symbol"
            ]
            .ne(
                expected_fyers_symbol
            )
        )

        fyers_symbol_mismatch = int(
            fyers_symbol_mismatch_mask.sum()
        )

    else:

        fyers_symbol_mismatch_mask = (
            pd.Series(
                False,
                index=dataframe.index,
            )
        )

        fyers_symbol_mismatch = 0

    # --------------------------------------------------------
    # Chronology
    # --------------------------------------------------------

    valid_dates = (
        parsed_dates[
            parsed_dates.notna()
        ]
    )

    chronology_issue = 0

    if not valid_dates.empty:

        chronological = (
            valid_dates
            .reset_index(
                drop=True
            )
            .is_monotonic_increasing
        )

        if not chronological:

            chronology_issue = 1

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

    # ========================================================
    # ISSUE RECORDS
    # ========================================================

    def add_issue_rows(
        *,
        mask: pd.Series,
        issue_type: str,
        details: str,
        limit: int = 20,
    ) -> None:

        selected = dataframe.loc[
            mask
        ].head(
            limit
        )

        for _, row in selected.iterrows():

            issues.append(
                {
                    "security_id":
                        expected_security_id,
                    "symbol":
                        expected_symbol,
                    "issue_type":
                        issue_type,
                    "trade_date":
                        row.get(
                            "trade_date",
                            "",
                        ),
                    "details":
                        details,
                }
            )

    if duplicate_dates:

        add_issue_rows(
            mask=duplicate_date_mask,
            issue_type="DUPLICATE_DATE",
            details="Duplicate trading date.",
        )

    if invalid_dates:

        add_issue_rows(
            mask=invalid_date_mask,
            issue_type="INVALID_DATE",
            details="Trade date could not be parsed.",
        )

    if future_dates:

        add_issue_rows(
            mask=future_date_mask,
            issue_type="FUTURE_DATE",
            details="Trade date is in future.",
        )

    if null_ohlc:

        add_issue_rows(
            mask=null_ohlc_mask,
            issue_type="NULL_OHLC",
            details="One or more OHLC fields are null.",
        )

    if non_positive_ohlc:

        add_issue_rows(
            mask=non_positive_ohlc_mask,
            issue_type="NON_POSITIVE_OHLC",
            details="One or more OHLC values are <= 0.",
        )

    if invalid_ohlc:

        add_issue_rows(
            mask=invalid_ohlc_mask,
            issue_type="INVALID_OHLC_RELATIONSHIP",
            details="OHLC relationships are invalid.",
        )

    if negative_volume:

        add_issue_rows(
            mask=negative_volume_mask,
            issue_type="NEGATIVE_VOLUME",
            details="Volume is negative.",
        )

    if blank_security_ids:

        add_issue_rows(
            mask=blank_security_id_mask,
            issue_type="BLANK_SECURITY_ID",
            details="Security ID is blank.",
        )

    if blank_symbols:

        add_issue_rows(
            mask=blank_symbol_mask,
            issue_type="BLANK_SYMBOL",
            details="Symbol is blank.",
        )

    if security_id_mismatch:

        add_issue_rows(
            mask=security_id_mismatch_mask,
            issue_type="SECURITY_ID_MISMATCH",
            details=(
                "History security_id does not match "
                f"{expected_security_id}."
            ),
        )

    if symbol_mismatch:

        add_issue_rows(
            mask=symbol_mismatch_mask,
            issue_type="SYMBOL_MISMATCH",
            details=(
                "History symbol does not match "
                f"{expected_symbol}."
            ),
        )

    if fyers_symbol_mismatch:

        add_issue_rows(
            mask=fyers_symbol_mismatch_mask,
            issue_type="FYERS_SYMBOL_MISMATCH",
            details=(
                "History FYERS symbol does not match "
                f"{expected_fyers_symbol}."
            ),
        )

    if chronology_issue:

        issues.append(
            {
                "security_id":
                    expected_security_id,
                "symbol":
                    expected_symbol,
                "issue_type":
                    "CHRONOLOGY_ISSUE",
                "trade_date":
                    "",
                "details":
                    "History file is not sorted chronologically.",
            }
        )

    # ========================================================
    # CRITICAL ISSUES
    # ========================================================

    critical_issues = (
        duplicate_dates
        + invalid_dates
        + future_dates
        + null_ohlc
        + non_positive_ohlc
        + invalid_ohlc
        + negative_volume
        + blank_security_ids
        + blank_symbols
        + security_id_mismatch
        + symbol_mismatch
        + fyers_symbol_mismatch
        + chronology_issue
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    summary = {
        "security_id":
            expected_security_id,
        "symbol":
            expected_symbol,
        "fyers_symbol":
            expected_fyers_symbol,
        "history_file":
            str(
                history_file
            ),
        "file_exists":
            True,
        "rows":
            total_rows,
        "first_session":
            first_session,
        "last_session":
            last_session,
        "duplicate_dates":
            duplicate_dates,
        "invalid_dates":
            invalid_dates,
        "future_dates":
            future_dates,
        "null_ohlc":
            null_ohlc,
        "non_positive_ohlc":
            non_positive_ohlc,
        "invalid_ohlc":
            invalid_ohlc,
        "negative_volume":
            negative_volume,
        "blank_security_ids":
            blank_security_ids,
        "blank_symbols":
            blank_symbols,
        "security_id_mismatch":
            security_id_mismatch,
        "symbol_mismatch":
            symbol_mismatch,
        "fyers_symbol_mismatch":
            fyers_symbol_mismatch,
        "chronology_issue":
            chronology_issue,
        "critical_issues":
            critical_issues,
        "status":
            status,
    }

    return (
        summary,
        issues,
    )


# ============================================================
# SECURITY MASTER RECONCILIATION
# ============================================================

def validate_security_master_reconciliation(
    expected_universe: pd.DataFrame,
    security_master: pd.DataFrame,
) -> tuple[
    int,
    list[dict[str, object]],
]:

    if security_master.empty:

        return (
            0,
            []
        )

    expected_pairs = set(
        zip(
            expected_universe[
                "security_id"
            ],
            expected_universe[
                "symbol"
            ],
        )
    )

    master_pairs = set(
        zip(
            security_master[
                "security_id"
            ],
            security_master[
                "symbol"
            ],
        )
    )

    missing_pairs = sorted(
        expected_pairs
        - master_pairs
    )

    issues: list[
        dict[str, object]
    ] = []

    for security_id, symbol in missing_pairs:

        issues.append(
            {
                "security_id":
                    security_id,
                "symbol":
                    symbol,
                "issue_type":
                    "SECURITY_MASTER_RECONCILIATION",
                "trade_date":
                    "",
                "details":
                    (
                        "Expected acquisition security is "
                        "missing from Security Master."
                    ),
            }
        )

    return (
        len(
            missing_pairs
        ),
        issues,
    )


# ============================================================
# VALIDATION RUN
# ============================================================

def run_validation() -> dict[str, object]:

    ensure_output_directory()

    expected_universe = (
        load_expected_universe()
    )

    security_master = (
        load_security_master()
    )

    print()

    print(
        "=" * 104
    )

    print(
        "AQSD MARKET PRICE POST-RECOVERY VALIDATOR"
    )

    print(
        "=" * 104
    )

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Expected Securities            : "
        f"{len(expected_universe):,}"
    )

    print(
        f"Historical Root                : "
        f"{RAW_ROOT}"
    )

    print(
        "Historical Data                : READ ONLY"
    )

    print(
        "Security Master                : READ ONLY"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print(
        "-" * 104
    )

    summary_rows: list[
        dict[str, object]
    ] = []

    issue_rows: list[
        dict[str, object]
    ] = []

    total_expected = int(
        len(
            expected_universe
        )
    )

    for number, (_, expected) in enumerate(
        expected_universe.iterrows(),
        start=1,
    ):

        security_id = str(
            expected[
                "security_id"
            ]
        ).strip()

        symbol = str(
            expected[
                "symbol"
            ]
        ).strip().upper()

        fyers_symbol = str(
            expected[
                "fyers_symbol"
            ]
        ).strip().upper()

        history_file = get_history_file(
            symbol
        )

        (
            security_summary,
            security_issues,
        ) = validate_security(
            expected_security_id=
                security_id,
            expected_symbol=
                symbol,
            expected_fyers_symbol=
                fyers_symbol,
            history_file=
                history_file,
        )

        summary_rows.append(
            security_summary
        )

        issue_rows.extend(
            security_issues
        )

        print(
            f"[{number:03d}/"
            f"{total_expected:03d}] "
            f"{symbol:<16} "
            f"{security_summary['status']:<7} "
            f"Rows="
            f"{int(security_summary['rows']):>6,} "
            f"Issues="
            f"{int(security_summary['critical_issues']):>4,}"
        )

    # ========================================================
    # SECURITY MASTER RECONCILIATION
    # ========================================================

    (
        master_reconciliation_issues,
        master_issue_rows,
    ) = validate_security_master_reconciliation(
        expected_universe,
        security_master,
    )

    issue_rows.extend(
        master_issue_rows
    )

    # ========================================================
    # DATAFRAMES
    # ========================================================

    summary_dataframe = pd.DataFrame(
        summary_rows
    )

    issues_dataframe = pd.DataFrame(
        issue_rows
    )

    # ========================================================
    # WRITE OUTPUTS
    # ========================================================

    summary_dataframe.to_csv(
        SECURITY_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    if issues_dataframe.empty:

        issues_dataframe = pd.DataFrame(
            columns=[
                "security_id",
                "symbol",
                "issue_type",
                "trade_date",
                "details",
            ]
        )

    issues_dataframe.to_csv(
        VALIDATION_ISSUES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # OVERALL COUNTS
    # ========================================================

    successful_securities = int(
        summary_dataframe[
            "status"
        ]
        .eq(
            "SUCCESS"
        )
        .sum()
    )

    failed_securities = int(
        summary_dataframe[
            "status"
        ]
        .eq(
            "FAILED"
        )
        .sum()
    )

    missing_files = int(
        (
            ~summary_dataframe[
                "file_exists"
            ]
        ).sum()
    )

    total_rows = int(
        pd.to_numeric(
            summary_dataframe[
                "rows"
            ],
            errors="coerce",
        )
        .fillna(
            0
        )
        .sum()
    )

    total_duplicate_dates = int(
        summary_dataframe[
            "duplicate_dates"
        ].sum()
    )

    total_invalid_dates = int(
        summary_dataframe[
            "invalid_dates"
        ].sum()
    )

    total_future_dates = int(
        summary_dataframe[
            "future_dates"
        ].sum()
    )

    total_null_ohlc = int(
        summary_dataframe[
            "null_ohlc"
        ].sum()
    )

    total_non_positive_ohlc = int(
        summary_dataframe[
            "non_positive_ohlc"
        ].sum()
    )

    total_invalid_ohlc = int(
        summary_dataframe[
            "invalid_ohlc"
        ].sum()
    )

    total_negative_volume = int(
        summary_dataframe[
            "negative_volume"
        ].sum()
    )

    total_identity_issues = int(
        summary_dataframe[
            [
                "blank_security_ids",
                "blank_symbols",
                "security_id_mismatch",
                "symbol_mismatch",
                "fyers_symbol_mismatch",
            ]
        ]
        .sum(
            axis=1
        )
        .sum()
    )

    total_chronology_issues = int(
        summary_dataframe[
            "chronology_issue"
        ].sum()
    )

    total_security_critical = int(
        summary_dataframe[
            "critical_issues"
        ].sum()
    )

    total_critical_issues = (
        total_security_critical
        + master_reconciliation_issues
    )

    overall_status = (
        "SUCCESS"
        if (
            failed_securities == 0
            and
            total_critical_issues == 0
        )
        else "FAILED"
    )

    # ========================================================
    # AUDIT
    # ========================================================

    audit_row = {
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
        "expected_securities":
            total_expected,
        "successful_securities":
            successful_securities,
        "failed_securities":
            failed_securities,
        "missing_history_files":
            missing_files,
        "total_rows":
            total_rows,
        "duplicate_dates":
            total_duplicate_dates,
        "invalid_dates":
            total_invalid_dates,
        "future_dates":
            total_future_dates,
        "null_ohlc":
            total_null_ohlc,
        "non_positive_ohlc":
            total_non_positive_ohlc,
        "invalid_ohlc":
            total_invalid_ohlc,
        "negative_volume":
            total_negative_volume,
        "identity_issues":
            total_identity_issues,
        "chronology_issues":
            total_chronology_issues,
        "security_master_reconciliation_issues":
            master_reconciliation_issues,
        "critical_issues":
            total_critical_issues,
        "historical_data_modified":
            False,
        "security_master_modified":
            False,
        "market_price_database_modified":
            False,
        "immutable_archive_modified":
            False,
        "historical_fabrication":
            False,
        "status":
            overall_status,
    }

    pd.DataFrame(
        [
            audit_row
        ]
    ).to_csv(
        VALIDATION_AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    # ========================================================
    # SUMMARY JSON
    # ========================================================

    SUMMARY_JSON.write_text(
        json.dumps(
            audit_row,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return audit_row


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()

    print(
        "=" * 104
    )

    print(
        "AQSD MARKET PRICE POST-RECOVERY VALIDATION SUMMARY"
    )

    print(
        "=" * 104
    )

    print(
        f"Module                         : "
        f"{summary['module_id']}"
    )

    print(
        f"Version                        : "
        f"{summary['module_version']}"
    )

    print(
        "-" * 104
    )

    print(
        f"Expected Securities            : "
        f"{int(summary['expected_securities']):,}"
    )

    print(
        f"Successful Securities          : "
        f"{int(summary['successful_securities']):,}"
    )

    print(
        f"Failed Securities              : "
        f"{int(summary['failed_securities']):,}"
    )

    print(
        f"Missing History Files          : "
        f"{int(summary['missing_history_files']):,}"
    )

    print(
        f"Total Historical Rows          : "
        f"{int(summary['total_rows']):,}"
    )

    print(
        "-" * 104
    )

    print(
        f"Duplicate Dates                : "
        f"{int(summary['duplicate_dates']):,}"
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
        f"Non-Positive OHLC              : "
        f"{int(summary['non_positive_ohlc']):,}"
    )

    print(
        f"Invalid OHLC Relationships     : "
        f"{int(summary['invalid_ohlc']):,}"
    )

    print(
        f"Negative Volume                : "
        f"{int(summary['negative_volume']):,}"
    )

    print(
        f"Identity Issues                : "
        f"{int(summary['identity_issues']):,}"
    )

    print(
        f"Chronology Issues              : "
        f"{int(summary['chronology_issues']):,}"
    )

    print(
        f"Security Master Reconciliation : "
        f"{int(summary['security_master_reconciliation_issues']):,}"
    )

    print(
        "-" * 104
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    print(
        f"Audit CSV                      : "
        f"{VALIDATION_AUDIT_CSV}"
    )

    print(
        f"Issues CSV                     : "
        f"{VALIDATION_ISSUES_CSV}"
    )

    print(
        f"Security Summary               : "
        f"{SECURITY_SUMMARY_CSV}"
    )

    print(
        "-" * 104
    )

    print(
        "Historical Data                : READ ONLY"
    )

    print(
        "Security Master                : NOT MODIFIED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Immutable Archive              : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    print(
        "-" * 104
    )

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    print(
        "=" * 104
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = (
            run_validation()
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

            raise SystemExit(
                1
            )

    except SystemExit:

        raise

    except Exception as exc:

        print()

        print(
            "=" * 104
        )

        print(
            "AQSD MARKET PRICE POST-RECOVERY VALIDATOR"
        )

        print(
            "=" * 104
        )

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            "Historical Data                : NOT MODIFIED"
        )

        print(
            "Historical Fabrication         : PROHIBITED"
        )

        print(
            "=" * 104
        )

        raise SystemExit(
            1
        ) from exc


if __name__ == "__main__":
    main()