"""
AQSD
Market Price Raw Historical Validator

Module ID: MPD-008
Version: 1.1.0
Author: AQSD

Purpose
-------
Validate raw historical market-price files downloaded for the
CURRENT validated acquisition universe while preserving older
out-of-scope raw historical files.

Important Architectural Rule
----------------------------
RAW DATA IS IMMUTABLE.

Raw storage may legitimately contain securities that:
- were previously part of F&O
- are no longer current F&O members
- must remain available for historical research

Therefore:

CURRENT F&O RAW FILES
    -> strictly validated

OUT-OF-SCOPE HISTORICAL RAW FILES
    -> preserved
    -> reported separately
    -> NOT treated as validation failures

This module DOES NOT:
- delete raw files
- modify raw files
- modify the Security Master
- modify the Market Price Database
- modify the frozen historical database
- fabricate historical data
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

MODULE_ID: Final[str] = "MPD-008"
MODULE_VERSION: Final[str] = "1.1.0"


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


# ============================================================
# INPUT FILES
# ============================================================

VALIDATED_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue_Validated.csv"
)

MPD007_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Acquisition_Controller_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

VALIDATION_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Validation_Audit.csv"
)

VALIDATION_ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Validation_Issues.csv"
)

SYMBOL_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Symbol_Summary.csv"
)

OUT_OF_SCOPE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Out_Of_Scope.csv"
)

VALIDATION_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Raw_Historical_Validation_Summary.json"
)


# ============================================================
# CONSTANTS
# ============================================================

EXPECTED_PRICE_COLUMNS: Final[set[str]] = {
    "open",
    "high",
    "low",
    "close",
}

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

SECURITY_ID_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "security_id",
    "securityid",
)

SYMBOL_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "symbol",
    "underlying",
    "ticker",
)

FYERS_SYMBOL_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "fyers_symbol",
    "acquisition_symbol",
    "resolved_fyers_symbol",
)


# ============================================================
# DISPLAY
# ============================================================

def separator() -> None:
    print("=" * 100)


def sub_separator() -> None:
    print("-" * 100)


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

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


def parse_bool(
    value: object,
) -> bool:

    if pd.isna(value):
        return False

    return (
        str(value)
        .strip()
        .upper()
        in {
            "TRUE",
            "YES",
            "Y",
            "1",
        }
    )


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

    required = [
        VALIDATED_QUEUE_FILE,
        MPD007_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Missing MPD-008 input file(s): "
            + ", ".join(
                str(path)
                for path in missing
            )
        )

    if not RAW_ROOT.exists():

        raise FileNotFoundError(
            f"Raw market-price root not found: {RAW_ROOT}"
        )


# ============================================================
# MPD-007 GATE
# ============================================================

def validate_mpd007() -> dict[str, object]:

    summary = load_json(
        MPD007_SUMMARY_FILE
    )

    status = safe_text(
        summary.get(
            "status",
            "",
        )
    ).upper()

    expected_symbols = int(
        summary.get(
            "expected_symbols",
            0,
        )
    )

    processed_symbols = int(
        summary.get(
            "processed_symbols",
            0,
        )
    )

    successful_symbols = int(
        summary.get(
            "successful_symbols",
            0,
        )
    )

    failed_symbols = int(
        summary.get(
            "failed_symbols",
            0,
        )
    )

    downloaded_rows = int(
        summary.get(
            "downloaded_price_rows",
            0,
        )
    )

    reconciles = bool(
        summary.get(
            "processing_reconciles",
            False,
        )
    )

    critical_issues = int(
        summary.get(
            "controller_critical_issues",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-007 status is not SUCCESS."
        )

    if expected_symbols <= 0:

        raise RuntimeError(
            "MPD-007 expected symbol count is zero."
        )

    if processed_symbols != expected_symbols:

        raise RuntimeError(
            "MPD-007 processed symbol count does not reconcile."
        )

    if successful_symbols != expected_symbols:

        raise RuntimeError(
            "MPD-007 did not successfully acquire every symbol."
        )

    if failed_symbols != 0:

        raise RuntimeError(
            "MPD-007 contains failed symbols."
        )

    if not reconciles:

        raise RuntimeError(
            "MPD-007 processing reconciliation failed."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-007 contains critical issues."
        )

    if downloaded_rows <= 0:

        raise RuntimeError(
            "MPD-007 downloaded row count is zero."
        )

    return summary


# ============================================================
# EXPECTED CURRENT UNIVERSE
# ============================================================

def load_expected_universe() -> pd.DataFrame:

    dataframe = pd.read_csv(
        VALIDATED_QUEUE_FILE,
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

    missing = (
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Validated acquisition queue missing columns: "
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

    if "resolved_fyers_symbol" in dataframe.columns:

        dataframe[
            "expected_fyers_symbol"
        ] = (
            dataframe[
                "resolved_fyers_symbol"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    elif "acquisition_symbol" in dataframe.columns:

        dataframe[
            "expected_fyers_symbol"
        ] = (
            dataframe[
                "acquisition_symbol"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        dataframe[
            "expected_fyers_symbol"
        ] = ""

    if "validation_pass" in dataframe.columns:

        dataframe = dataframe[
            dataframe[
                "validation_pass"
            ].map(
                parse_bool
            )
        ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe[
        [
            "security_id",
            "symbol",
            "expected_fyers_symbol",
        ]
    ].copy()


# ============================================================
# RAW FILE DISCOVERY
# ============================================================

def discover_raw_files() -> list[Path]:

    files = sorted(
        path
        for path in RAW_ROOT.rglob(
            "*.csv"
        )
        if path.is_file()
    )

    if not files:

        raise RuntimeError(
            f"No raw CSV files found under {RAW_ROOT}"
        )

    return files


# ============================================================
# NORMALIZE RAW DATA
# ============================================================

def normalize_raw_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = dataframe.copy()

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    return dataframe


# ============================================================
# RESOLVE RAW FILE IDENTITY
# ============================================================

def resolve_file_identity(
    dataframe: pd.DataFrame,
    file: Path,
    expected_by_id: dict[str, dict[str, str]],
    expected_by_symbol: dict[str, dict[str, str]],
) -> tuple[str, str, str, bool]:

    security_id = ""
    symbol = ""
    fyers_symbol = ""

    security_column = first_existing_column(
        dataframe,
        SECURITY_ID_COLUMN_CANDIDATES,
    )

    symbol_column = first_existing_column(
        dataframe,
        SYMBOL_COLUMN_CANDIDATES,
    )

    fyers_column = first_existing_column(
        dataframe,
        FYERS_SYMBOL_COLUMN_CANDIDATES,
    )

    # --------------------------------------------------------
    # Read identity from file contents
    # --------------------------------------------------------

    if (
        security_column is not None
        and not dataframe.empty
    ):

        values = (
            dataframe[
                security_column
            ]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = values[
            values.ne("")
        ]

        if not values.empty:

            security_id = (
                values.iloc[0]
            )

    if (
        symbol_column is not None
        and not dataframe.empty
    ):

        values = (
            dataframe[
                symbol_column
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

        values = values[
            values.ne("")
        ]

        if not values.empty:

            symbol = (
                values.iloc[0]
            )

    if (
        fyers_column is not None
        and not dataframe.empty
    ):

        values = (
            dataframe[
                fyers_column
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

        values = values[
            values.ne("")
        ]

        if not values.empty:

            fyers_symbol = (
                values.iloc[0]
            )

    # --------------------------------------------------------
    # Match current universe using security ID
    # --------------------------------------------------------

    if (
        security_id
        and security_id in expected_by_id
    ):

        expected = expected_by_id[
            security_id
        ]

        if not symbol:

            symbol = expected[
                "symbol"
            ]

        if not fyers_symbol:

            fyers_symbol = expected[
                "expected_fyers_symbol"
            ]

        return (
            security_id,
            symbol,
            fyers_symbol,
            True,
        )

    # --------------------------------------------------------
    # Match using symbol
    # --------------------------------------------------------

    if (
        symbol
        and symbol in expected_by_symbol
    ):

        expected = expected_by_symbol[
            symbol
        ]

        if not security_id:

            security_id = expected[
                "security_id"
            ]

        if not fyers_symbol:

            fyers_symbol = expected[
                "expected_fyers_symbol"
            ]

        return (
            security_id,
            symbol,
            fyers_symbol,
            True,
        )

    # --------------------------------------------------------
    # Match filename against current symbols
    # --------------------------------------------------------

    filename_upper = (
        file.stem.upper()
    )

    matches = [
        expected_symbol
        for expected_symbol
        in expected_by_symbol
        if (
            expected_symbol
            and expected_symbol
            in filename_upper
        )
    ]

    matches.sort(
        key=len,
        reverse=True,
    )

    if matches:

        expected_symbol = matches[0]

        expected = expected_by_symbol[
            expected_symbol
        ]

        return (
            expected[
                "security_id"
            ],
            expected[
                "symbol"
            ],
            expected[
                "expected_fyers_symbol"
            ],
            True,
        )

    # --------------------------------------------------------
    # Not part of current universe
    # --------------------------------------------------------

    return (
        security_id,
        symbol,
        fyers_symbol,
        False,
    )


# ============================================================
# OUT OF SCOPE RECORD
# ============================================================

def build_out_of_scope_record(
    file: Path,
    dataframe: pd.DataFrame,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
) -> dict[str, object]:

    return {
        "file":
            str(
                file
            ),

        "security_id":
            security_id,

        "symbol":
            symbol,

        "fyers_symbol":
            fyers_symbol,

        "rows":
            int(
                len(
                    dataframe
                )
            ),

        "classification":
            "HISTORICAL_OUT_OF_SCOPE",

        "action":
            "PRESERVE",

        "validation_status":
            "NOT_APPLICABLE_CURRENT_UNIVERSE",
    }


# ============================================================
# ISSUE RECORD
# ============================================================

def add_issue(
    issues: list[dict[str, object]],
    *,
    issue_type: str,
    file: Path,
    security_id: str = "",
    symbol: str = "",
    message: str = "",
) -> None:

    issues.append(
        {
            "severity":
                "CRITICAL",

            "issue_type":
                issue_type,

            "file":
                str(
                    file
                ),

            "security_id":
                security_id,

            "symbol":
                symbol,

            "message":
                message,
        }
    )


# ============================================================
# VALIDATE CURRENT RAW FILE
# ============================================================

def validate_current_raw_file(
    file: Path,
    dataframe: pd.DataFrame,
    security_id: str,
    symbol: str,
    fyers_symbol: str,
    expected_by_id: dict[str, dict[str, str]],
    issues: list[dict[str, object]],
) -> dict[str, object]:

    critical_issues = 0

    rows = int(
        len(
            dataframe
        )
    )

    if dataframe.empty:

        add_issue(
            issues,
            issue_type="EMPTY_FILE",
            file=file,
            security_id=security_id,
            symbol=symbol,
            message=(
                "Current-universe raw historical file is empty."
            ),
        )

        critical_issues += 1

    # --------------------------------------------------------
    # Required price columns
    # --------------------------------------------------------

    missing_price_columns = sorted(
        EXPECTED_PRICE_COLUMNS
        - set(
            dataframe.columns
        )
    )

    if missing_price_columns:

        add_issue(
            issues,
            issue_type="MISSING_PRICE_COLUMNS",
            file=file,
            security_id=security_id,
            symbol=symbol,
            message=(
                "Missing price columns: "
                + ", ".join(
                    missing_price_columns
                )
            ),
        )

        critical_issues += 1

    # --------------------------------------------------------
    # Date validation
    # --------------------------------------------------------

    date_column = first_existing_column(
        dataframe,
        DATE_COLUMN_CANDIDATES,
    )

    first_session = ""
    last_session = ""

    duplicate_sessions = 0
    invalid_date_rows = 0
    future_date_rows = 0

    if date_column is None:

        add_issue(
            issues,
            issue_type="MISSING_DATE_COLUMN",
            file=file,
            security_id=security_id,
            symbol=symbol,
            message=(
                "No session/date column found."
            ),
        )

        critical_issues += 1

    else:

        parsed_dates = pd.to_datetime(
            dataframe[
                date_column
            ],
            errors="coerce",
        )

        invalid_date_rows = int(
            parsed_dates.isna().sum()
        )

        if invalid_date_rows:

            add_issue(
                issues,
                issue_type="INVALID_DATE",
                file=file,
                security_id=security_id,
                symbol=symbol,
                message=(
                    f"{invalid_date_rows:,} invalid date rows."
                ),
            )

            critical_issues += (
                invalid_date_rows
            )

        valid_dates = (
            parsed_dates.dropna()
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

            today = (
                pd.Timestamp.now()
                .normalize()
            )

            future_mask = (
                parsed_dates
                .dt.normalize()
                > today
            )

            future_date_rows = int(
                future_mask
                .fillna(False)
                .sum()
            )

            if future_date_rows:

                add_issue(
                    issues,
                    issue_type="FUTURE_DATE",
                    file=file,
                    security_id=security_id,
                    symbol=symbol,
                    message=(
                        f"{future_date_rows:,} future date rows."
                    ),
                )

                critical_issues += (
                    future_date_rows
                )

            duplicate_sessions = int(
                parsed_dates[
                    parsed_dates.notna()
                ]
                .duplicated(
                    keep=False
                )
                .sum()
            )

            if duplicate_sessions:

                add_issue(
                    issues,
                    issue_type="DUPLICATE_SESSION",
                    file=file,
                    security_id=security_id,
                    symbol=symbol,
                    message=(
                        f"{duplicate_sessions:,} rows "
                        "participate in duplicate sessions."
                    ),
                )

                critical_issues += (
                    duplicate_sessions
                )

    # --------------------------------------------------------
    # OHLC validation
    # --------------------------------------------------------

    invalid_ohlc_rows = 0
    missing_price_rows = 0

    if not missing_price_columns:

        numeric = pd.DataFrame(
            {
                column:
                    pd.to_numeric(
                        dataframe[
                            column
                        ],
                        errors="coerce",
                    )
                for column
                in EXPECTED_PRICE_COLUMNS
            }
        )

        missing_mask = (
            numeric
            .isna()
            .any(
                axis=1
            )
        )

        missing_price_rows = int(
            missing_mask.sum()
        )

        if missing_price_rows:

            add_issue(
                issues,
                issue_type="MISSING_PRICE",
                file=file,
                security_id=security_id,
                symbol=symbol,
                message=(
                    f"{missing_price_rows:,} missing/non-numeric "
                    "OHLC rows."
                ),
            )

            critical_issues += (
                missing_price_rows
            )

        valid_mask = (
            ~missing_mask
        )

        open_price = numeric["open"]
        high_price = numeric["high"]
        low_price = numeric["low"]
        close_price = numeric["close"]

        invalid_mask = (
            valid_mask
            & (
                (open_price <= 0)
                | (high_price <= 0)
                | (low_price <= 0)
                | (close_price <= 0)
                | (high_price < low_price)
                | (high_price < open_price)
                | (high_price < close_price)
                | (low_price > open_price)
                | (low_price > close_price)
            )
        )

        invalid_ohlc_rows = int(
            invalid_mask.sum()
        )

        if invalid_ohlc_rows:

            add_issue(
                issues,
                issue_type="INVALID_OHLC",
                file=file,
                security_id=security_id,
                symbol=symbol,
                message=(
                    f"{invalid_ohlc_rows:,} OHLC relationship errors."
                ),
            )

            critical_issues += (
                invalid_ohlc_rows
            )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    negative_volume_rows = 0

    volume_column = first_existing_column(
        dataframe,
        VOLUME_COLUMN_CANDIDATES,
    )

    if volume_column is not None:

        volume = pd.to_numeric(
            dataframe[
                volume_column
            ],
            errors="coerce",
        )

        negative_volume_rows = int(
            (
                volume < 0
            )
            .fillna(False)
            .sum()
        )

        if negative_volume_rows:

            add_issue(
                issues,
                issue_type="NEGATIVE_VOLUME",
                file=file,
                security_id=security_id,
                symbol=symbol,
                message=(
                    f"{negative_volume_rows:,} negative volume rows."
                ),
            )

            critical_issues += (
                negative_volume_rows
            )

    # --------------------------------------------------------
    # FYERS consistency
    # --------------------------------------------------------

    if (
        security_id
        and security_id in expected_by_id
    ):

        expected_fyers = (
            expected_by_id[
                security_id
            ][
                "expected_fyers_symbol"
            ]
        )

        if (
            expected_fyers
            and fyers_symbol
            and expected_fyers.upper()
            != fyers_symbol.upper()
        ):

            add_issue(
                issues,
                issue_type="FYERS_SYMBOL_MISMATCH",
                file=file,
                security_id=security_id,
                symbol=symbol,
                message=(
                    f"Expected {expected_fyers}, "
                    f"found {fyers_symbol}."
                ),
            )

            critical_issues += 1

    status = (
        "PASS"
        if critical_issues == 0
        else "FAIL"
    )

    return {
        "file":
            str(
                file
            ),

        "security_id":
            security_id,

        "symbol":
            symbol,

        "fyers_symbol":
            fyers_symbol,

        "rows":
            rows,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "duplicate_sessions":
            duplicate_sessions,

        "invalid_ohlc_rows":
            invalid_ohlc_rows,

        "negative_volume_rows":
            negative_volume_rows,

        "missing_price_rows":
            missing_price_rows,

        "future_date_rows":
            future_date_rows,

        "invalid_date_rows":
            invalid_date_rows,

        "critical_issues":
            critical_issues,

        "status":
            status,
    }


# ============================================================
# CURRENT UNIVERSE RECONCILIATION
# ============================================================

def reconcile_current_universe(
    audit: pd.DataFrame,
    expected: pd.DataFrame,
    issues: list[dict[str, object]],
) -> dict[str, object]:

    expected_ids = set(
        expected[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    expected_ids.discard("")

    current_ids = set(
        audit[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    current_ids.discard("")

    missing_ids = sorted(
        expected_ids
        - current_ids
    )

    extra_ids = sorted(
        current_ids
        - expected_ids
    )

    duplicate_security_ids = int(
        audit[
            "security_id"
        ]
        .replace(
            "",
            pd.NA,
        )
        .dropna()
        .duplicated(
            keep=False
        )
        .sum()
    )

    lookup = (
        expected
        .set_index(
            "security_id"
        )
        .to_dict(
            orient="index"
        )
    )

    for security_id in missing_ids:

        add_issue(
            issues,
            issue_type="MISSING_CURRENT_RAW_SECURITY",
            file=RAW_ROOT,
            security_id=security_id,
            symbol=lookup[
                security_id
            ][
                "symbol"
            ],
            message=(
                "Current acquisition universe security "
                "has no raw historical file."
            ),
        )

    if extra_ids:

        add_issue(
            issues,
            issue_type="CURRENT_SCOPE_EXTRA_SECURITY",
            file=RAW_ROOT,
            message=(
                "Current-scoped validator contains "
                f"{len(extra_ids):,} unexpected security IDs."
            ),
        )

    if duplicate_security_ids:

        add_issue(
            issues,
            issue_type="MULTIPLE_CURRENT_FILES_FOR_SECURITY",
            file=RAW_ROOT,
            message=(
                f"{duplicate_security_ids:,} rows participate "
                "in duplicate current security mappings."
            ),
        )

    represented = (
        expected_ids
        & current_ids
    )

    reconciles = (
        len(
            represented
        )
        == len(
            expected_ids
        )
        and not missing_ids
        and not extra_ids
        and duplicate_security_ids == 0
    )

    return {
        "expected_securities":
            len(
                expected_ids
            ),

        "represented_securities":
            len(
                represented
            ),

        "missing_securities":
            len(
                missing_ids
            ),

        "extra_current_securities":
            len(
                extra_ids
            ),

        "duplicate_current_security_ids":
            duplicate_security_ids,

        "universe_reconciles":
            reconciles,
    }


# ============================================================
# RUN
# ============================================================

def run_validator() -> dict[str, object]:

    ensure_directories()

    validate_inputs()

    mpd007 = validate_mpd007()

    expected = (
        load_expected_universe()
    )

    expected_by_id = {
        row[
            "security_id"
        ]: {
            "security_id":
                row[
                    "security_id"
                ],

            "symbol":
                row[
                    "symbol"
                ],

            "expected_fyers_symbol":
                row[
                    "expected_fyers_symbol"
                ],
        }
        for _, row
        in expected.iterrows()
    }

    expected_by_symbol = {
        row[
            "symbol"
        ]: {
            "security_id":
                row[
                    "security_id"
                ],

            "symbol":
                row[
                    "symbol"
                ],

            "expected_fyers_symbol":
                row[
                    "expected_fyers_symbol"
                ],
        }
        for _, row
        in expected.iterrows()
        if row[
            "symbol"
        ]
    }

    raw_files = (
        discover_raw_files()
    )

    audit_rows: list[
        dict[str, object]
    ] = []

    out_of_scope_rows: list[
        dict[str, object]
    ] = []

    issues: list[
        dict[str, object]
    ] = []

    print()

    separator()

    print(
        "AQSD MARKET PRICE RAW HISTORICAL VALIDATOR"
    )

    separator()

    print(
        f"Module                         : {MODULE_ID}"
    )

    print(
        f"Version                        : {MODULE_VERSION}"
    )

    print(
        f"Expected Current Securities    : {len(expected):,}"
    )

    print(
        f"All Raw CSV Files Discovered   : {len(raw_files):,}"
    )

    sub_separator()

    # --------------------------------------------------------
    # Classify and validate every raw file
    # --------------------------------------------------------

    for index, file in enumerate(
        raw_files,
        start=1,
    ):

        try:

            dataframe = pd.read_csv(
                file,
                low_memory=False,
            )

        except Exception as exc:

            # Unreadable files are still a raw-storage problem.
            add_issue(
                issues,
                issue_type="UNREADABLE_RAW_FILE",
                file=file,
                message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

            print(
                f"[{index:03d}/{len(raw_files):03d}] "
                f"{file.name} | UNREADABLE"
            )

            continue

        dataframe = (
            normalize_raw_dataframe(
                dataframe
            )
        )

        (
            security_id,
            symbol,
            fyers_symbol,
            is_current,
        ) = resolve_file_identity(
            dataframe,
            file,
            expected_by_id,
            expected_by_symbol,
        )

        # ----------------------------------------------------
        # Historical out-of-scope file
        # ----------------------------------------------------

        if not is_current:

            out_of_scope_rows.append(
                build_out_of_scope_record(
                    file,
                    dataframe,
                    security_id,
                    symbol,
                    fyers_symbol,
                )
            )

            print(
                f"[{index:03d}/{len(raw_files):03d}] "
                f"{symbol or file.name} "
                f"| rows={len(dataframe):,} "
                f"| HISTORICAL OUT-OF-SCOPE"
            )

            continue

        # ----------------------------------------------------
        # Current universe file
        # ----------------------------------------------------

        result = (
            validate_current_raw_file(
                file,
                dataframe,
                security_id,
                symbol,
                fyers_symbol,
                expected_by_id,
                issues,
            )
        )

        audit_rows.append(
            result
        )

        print(
            f"[{index:03d}/{len(raw_files):03d}] "
            f"{result['symbol']} "
            f"| rows={int(result['rows']):,} "
            f"| {result['status']}"
        )

    # --------------------------------------------------------
    # DataFrames
    # --------------------------------------------------------

    audit = pd.DataFrame(
        audit_rows
    )

    out_of_scope = pd.DataFrame(
        out_of_scope_rows
    )

    if audit.empty:

        raise RuntimeError(
            "No current-universe raw historical files "
            "were identified."
        )

    # --------------------------------------------------------
    # Reconciliation
    # --------------------------------------------------------

    reconciliation = (
        reconcile_current_universe(
            audit,
            expected,
            issues,
        )
    )

    # --------------------------------------------------------
    # Totals
    # --------------------------------------------------------

    current_raw_rows = int(
        pd.to_numeric(
            audit[
                "rows"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    historical_out_of_scope_rows = 0

    if not out_of_scope.empty:

        historical_out_of_scope_rows = int(
            pd.to_numeric(
                out_of_scope[
                    "rows"
                ],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )

    passed_files = int(
        audit[
            "status"
        ]
        .eq(
            "PASS"
        )
        .sum()
    )

    failed_files = int(
        audit[
            "status"
        ]
        .eq(
            "FAIL"
        )
        .sum()
    )

    duplicate_sessions = int(
        audit[
            "duplicate_sessions"
        ]
        .sum()
    )

    invalid_ohlc_rows = int(
        audit[
            "invalid_ohlc_rows"
        ]
        .sum()
    )

    negative_volume_rows = int(
        audit[
            "negative_volume_rows"
        ]
        .sum()
    )

    missing_price_rows = int(
        audit[
            "missing_price_rows"
        ]
        .sum()
    )

    future_date_rows = int(
        audit[
            "future_date_rows"
        ]
        .sum()
    )

    invalid_date_rows = int(
        audit[
            "invalid_date_rows"
        ]
        .sum()
    )

    mpd007_rows = int(
        mpd007.get(
            "downloaded_price_rows",
            0,
        )
    )

    current_rows_match_mpd007 = (
        current_raw_rows
        == mpd007_rows
    )

    issues_dataframe = pd.DataFrame(
        issues
    )

    critical_issue_records = int(
        len(
            issues_dataframe
        )
    )

    critical_issues = (
        critical_issue_records
    )

    if not reconciliation[
        "universe_reconciles"
    ]:

        critical_issues += 1

    if not current_rows_match_mpd007:

        critical_issues += 1

    if failed_files != 0:

        critical_issues += (
            failed_files
        )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    # --------------------------------------------------------
    # Save audit files
    # --------------------------------------------------------

    audit.to_csv(
        VALIDATION_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    audit.to_csv(
        SYMBOL_SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    if out_of_scope.empty:

        out_of_scope = pd.DataFrame(
            columns=[
                "file",
                "security_id",
                "symbol",
                "fyers_symbol",
                "rows",
                "classification",
                "action",
                "validation_status",
            ]
        )

    out_of_scope.to_csv(
        OUT_OF_SCOPE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    if issues_dataframe.empty:

        issues_dataframe = pd.DataFrame(
            columns=[
                "severity",
                "issue_type",
                "file",
                "security_id",
                "symbol",
                "message",
            ]
        )

    issues_dataframe.to_csv(
        VALIDATION_ISSUES_FILE,
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

        "mpd007_status":
            mpd007.get(
                "status"
            ),

        "all_raw_files_discovered":
            len(
                raw_files
            ),

        "expected_current_securities":
            reconciliation[
                "expected_securities"
            ],

        "current_raw_files":
            len(
                audit
            ),

        "historical_out_of_scope_files":
            len(
                out_of_scope
            ),

        "represented_current_securities":
            reconciliation[
                "represented_securities"
            ],

        "missing_current_securities":
            reconciliation[
                "missing_securities"
            ],

        "extra_current_securities":
            reconciliation[
                "extra_current_securities"
            ],

        "duplicate_current_security_ids":
            reconciliation[
                "duplicate_current_security_ids"
            ],

        "universe_reconciles":
            reconciliation[
                "universe_reconciles"
            ],

        "passed_current_files":
            passed_files,

        "failed_current_files":
            failed_files,

        "current_raw_rows":
            current_raw_rows,

        "historical_out_of_scope_rows":
            historical_out_of_scope_rows,

        "total_raw_storage_rows":
            (
                current_raw_rows
                + historical_out_of_scope_rows
            ),

        "mpd007_downloaded_rows":
            mpd007_rows,

        "current_rows_match_mpd007":
            current_rows_match_mpd007,

        "duplicate_sessions":
            duplicate_sessions,

        "invalid_ohlc_rows":
            invalid_ohlc_rows,

        "negative_volume_rows":
            negative_volume_rows,

        "missing_price_rows":
            missing_price_rows,

        "future_date_rows":
            future_date_rows,

        "invalid_date_rows":
            invalid_date_rows,

        "issue_records":
            critical_issue_records,

        "critical_issues":
            critical_issues,

        "raw_data_modified":
            False,

        "out_of_scope_raw_data_preserved":
            True,

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

        "symbol_summary_file":
            str(
                SYMBOL_SUMMARY_FILE
            ),

        "out_of_scope_file":
            str(
                OUT_OF_SCOPE_FILE
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
# DISPLAY SUMMARY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()

    separator()

    print(
        "AQSD MARKET PRICE RAW HISTORICAL VALIDATION SUMMARY"
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
        f"MPD-007 Status                 : "
        f"{summary['mpd007_status']}"
    )

    sub_separator()

    print(
        f"All Raw Files Discovered       : "
        f"{int(summary['all_raw_files_discovered']):,}"
    )

    print(
        f"Expected Current Securities    : "
        f"{int(summary['expected_current_securities']):,}"
    )

    print(
        f"Current Raw Files              : "
        f"{int(summary['current_raw_files']):,}"
    )

    print(
        f"Historical Out-of-Scope Files  : "
        f"{int(summary['historical_out_of_scope_files']):,}"
    )

    sub_separator()

    print(
        f"Represented Current Securities : "
        f"{int(summary['represented_current_securities']):,}"
    )

    print(
        f"Missing Current Securities     : "
        f"{int(summary['missing_current_securities']):,}"
    )

    print(
        f"Extra Current Securities       : "
        f"{int(summary['extra_current_securities']):,}"
    )

    print(
        f"Duplicate Current Security IDs : "
        f"{int(summary['duplicate_current_security_ids']):,}"
    )

    print(
        f"Universe Reconciles            : "
        f"{summary['universe_reconciles']}"
    )

    sub_separator()

    print(
        f"Passed Current Files           : "
        f"{int(summary['passed_current_files']):,}"
    )

    print(
        f"Failed Current Files           : "
        f"{int(summary['failed_current_files']):,}"
    )

    print(
        f"Current Raw Rows               : "
        f"{int(summary['current_raw_rows']):,}"
    )

    print(
        f"MPD-007 Downloaded Rows        : "
        f"{int(summary['mpd007_downloaded_rows']):,}"
    )

    print(
        f"Current Rows Match MPD-007     : "
        f"{summary['current_rows_match_mpd007']}"
    )

    print(
        f"Historical Preserved Rows      : "
        f"{int(summary['historical_out_of_scope_rows']):,}"
    )

    print(
        f"Total Raw Storage Rows         : "
        f"{int(summary['total_raw_storage_rows']):,}"
    )

    sub_separator()

    print(
        f"Duplicate Sessions             : "
        f"{int(summary['duplicate_sessions']):,}"
    )

    print(
        f"Invalid OHLC Rows              : "
        f"{int(summary['invalid_ohlc_rows']):,}"
    )

    print(
        f"Negative Volume Rows           : "
        f"{int(summary['negative_volume_rows']):,}"
    )

    print(
        f"Missing Price Rows             : "
        f"{int(summary['missing_price_rows']):,}"
    )

    print(
        f"Future Date Rows               : "
        f"{int(summary['future_date_rows']):,}"
    )

    print(
        f"Invalid Date Rows              : "
        f"{int(summary['invalid_date_rows']):,}"
    )

    print(
        f"Issue Records                  : "
        f"{int(summary['issue_records']):,}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        "Raw Data                       : NOT MODIFIED"
    )

    print(
        "Historical Out-of-Scope Data   : PRESERVED"
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
        f"Validation Audit               : "
        f"{summary['validation_audit_file']}"
    )

    print(
        f"Validation Issues              : "
        f"{summary['validation_issues_file']}"
    )

    print(
        f"Out-of-Scope Audit             : "
        f"{summary['out_of_scope_file']}"
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
            "AQSD MARKET PRICE RAW HISTORICAL VALIDATOR"
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
            "Historical Data                : PRESERVED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()