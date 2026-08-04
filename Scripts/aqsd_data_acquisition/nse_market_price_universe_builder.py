"""
AQSD
NSE Market Price Universe Builder

Module : MPD-006
Version: 1.0.0
Author : AQSD

Purpose
-------
Build the authoritative AQSD Market Price universe from the
enriched AQSD Security Master and reconcile it against the
validated canonical Market Price dataset.

This module DOES NOT fabricate historical prices and DOES NOT
modify any database.

Responsibilities
----------------
1. Load AQSD Security Master.
2. Select securities approved for AQSD Market Price coverage.
3. Load the validated canonical Market Price staging dataset.
4. Determine which securities currently have canonical history.
5. Determine which securities still require historical acquisition.
6. Produce an authoritative universe manifest.
7. Produce a missing-history acquisition queue.
8. Produce audit and JSON summary outputs.

Protection
----------
- Security Master is READ ONLY.
- Canonical Market Price CSV is READ ONLY.
- AQSD_Market_Price.db is NOT MODIFIED.
- Frozen NSE_FNO_Historical.db is UNTOUCHED.
- Historical fabrication is PROHIBITED.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-006"
MODULE_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

SECURITY_MASTER_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

CANONICAL_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical.csv"
)

UNIVERSE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Universe.csv"
)

ACQUISITION_QUEUE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue.csv"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Universe_Audit.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Universe_Summary.json"
)


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


def normalize_text(
    series: pd.Series,
) -> pd.Series:

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalize_upper(
    series: pd.Series,
) -> pd.Series:

    return (
        normalize_text(series)
        .str.upper()
    )


def bool_from_value(
    value: object,
) -> bool:

    if pd.isna(value):
        return False

    text = str(value).strip().upper()

    return text in {
        "TRUE",
        "YES",
        "Y",
        "1",
        "ACTIVE",
    }


# ============================================================
# SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_FILE.exists():

        raise FileNotFoundError(
            "Security Master not found: "
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
        normalize_text(
            dataframe["security_id"]
        )
    )

    dataframe["symbol"] = (
        normalize_upper(
            dataframe["symbol"]
        )
    )

    for column in [
        "name",
        "exchange",
        "segment",
        "security_type",
        "instrument_class",
        "aqsd_scope",
        "fyers_symbol",
        "nse_token",
    ]:

        if column not in dataframe.columns:
            dataframe[column] = ""

        dataframe[column] = (
            normalize_text(
                dataframe[column]
            )
        )

    for column in [
        "active_flag",
        "is_index",
        "is_stock",
        "is_fno",
    ]:

        if column not in dataframe.columns:
            dataframe[column] = False

        dataframe[column] = (
            dataframe[column]
            .apply(bool_from_value)
        )

    return dataframe


# ============================================================
# BUILD AUTHORITATIVE MPD UNIVERSE
# ============================================================

def build_market_price_universe(
    security_master: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = security_master.copy()

    # --------------------------------------------------------
    # Remove unusable identity rows
    # --------------------------------------------------------

    dataframe = dataframe[
        dataframe["security_id"].ne("")
        &
        dataframe["symbol"].ne("")
    ].copy()

    # --------------------------------------------------------
    # AQSD scope
    #
    # Current Security Master was deliberately constructed as
    # the AQSD F&O / index analytical universe.
    #
    # We therefore preserve all authoritative Security Master
    # rows rather than inventing additional symbols.
    # --------------------------------------------------------

    if "active_flag" in dataframe.columns:

        active = dataframe[
            dataframe["active_flag"]
        ].copy()

        # Do not accidentally destroy the universe if legacy
        # rows do not yet carry an active flag.
        if not active.empty:
            dataframe = active

    # --------------------------------------------------------
    # One authoritative record per security_id
    # --------------------------------------------------------

    dataframe = (
        dataframe
        .sort_values(
            by=[
                "security_id",
                "symbol",
            ]
        )
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return dataframe


# ============================================================
# CANONICAL HISTORY
# ============================================================

def load_canonical_history() -> pd.DataFrame:

    if not CANONICAL_FILE.exists():

        raise FileNotFoundError(
            "Canonical Market Price file not found: "
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

    required = {
        "trade_date",
        "security_id",
        "symbol",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:

        raise RuntimeError(
            "Canonical Market Price file missing columns: "
            + ", ".join(missing)
        )

    dataframe["security_id"] = (
        normalize_text(
            dataframe["security_id"]
        )
    )

    dataframe["symbol"] = (
        normalize_upper(
            dataframe["symbol"]
        )
    )

    dataframe["trade_date_parsed"] = pd.to_datetime(
        dataframe["trade_date"],
        errors="coerce",
    )

    return dataframe


# ============================================================
# HISTORY COVERAGE
# ============================================================

def build_history_coverage(
    canonical: pd.DataFrame,
) -> pd.DataFrame:

    if canonical.empty:

        return pd.DataFrame(
            columns=[
                "security_id",
                "canonical_symbol",
                "canonical_rows",
                "canonical_sessions",
                "first_history_date",
                "last_history_date",
            ]
        )

    coverage = (
        canonical
        .groupby(
            "security_id",
            dropna=False,
        )
        .agg(
            canonical_symbol=(
                "symbol",
                "first",
            ),
            canonical_rows=(
                "trade_date",
                "size",
            ),
            canonical_sessions=(
                "trade_date",
                "nunique",
            ),
            first_history_date=(
                "trade_date_parsed",
                "min",
            ),
            last_history_date=(
                "trade_date_parsed",
                "max",
            ),
        )
        .reset_index()
    )

    coverage[
        "first_history_date"
    ] = (
        coverage[
            "first_history_date"
        ]
        .dt.date
        .astype(str)
    )

    coverage[
        "last_history_date"
    ] = (
        coverage[
            "last_history_date"
        ]
        .dt.date
        .astype(str)
    )

    return coverage


# ============================================================
# RECONCILIATION
# ============================================================

def reconcile_universe(
    universe: pd.DataFrame,
    coverage: pd.DataFrame,
) -> pd.DataFrame:

    result = universe.merge(
        coverage,
        on="security_id",
        how="left",
        validate="one_to_one",
    )

    result["canonical_rows"] = (
        pd.to_numeric(
            result["canonical_rows"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    result["canonical_sessions"] = (
        pd.to_numeric(
            result["canonical_sessions"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    result["has_canonical_history"] = (
        result["canonical_rows"] > 0
    )

    result["history_status"] = (
        result["has_canonical_history"]
        .map(
            {
                True:
                    "AVAILABLE",
                False:
                    "MISSING",
            }
        )
    )

    result["requires_acquisition"] = (
        ~result["has_canonical_history"]
    )

    # --------------------------------------------------------
    # Identity consistency
    # --------------------------------------------------------

    canonical_symbol = (
        result["canonical_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    master_symbol = (
        result["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["symbol_identity_match"] = (
        (canonical_symbol == "")
        |
        (canonical_symbol == master_symbol)
    )

    # --------------------------------------------------------
    # Acquisition symbol preference
    #
    # FYERS symbol is preferred when available because it is
    # already part of AQSD's broker integration.
    #
    # This file does NOT call FYERS.
    # --------------------------------------------------------

    result["acquisition_symbol"] = (
        result["fyers_symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    missing_fyers = (
        result["acquisition_symbol"].eq("")
    )

    result.loc[
        missing_fyers,
        "acquisition_symbol",
    ] = result.loc[
        missing_fyers,
        "symbol",
    ]

    result["acquisition_ready"] = (
        result["requires_acquisition"]
        &
        result["acquisition_symbol"].ne("")
    )

    result["acquisition_status"] = "NOT_REQUIRED"

    result.loc[
        result["requires_acquisition"],
        "acquisition_status",
    ] = "READY"

    result.loc[
        result["requires_acquisition"]
        &
        ~result["acquisition_ready"],
        "acquisition_status",
    ] = "BLOCKED_NO_SYMBOL"

    return result


# ============================================================
# ACQUISITION QUEUE
# ============================================================

def build_acquisition_queue(
    universe: pd.DataFrame,
) -> pd.DataFrame:

    queue = universe[
        universe[
            "requires_acquisition"
        ]
    ].copy()

    wanted_columns = [
        "security_id",
        "symbol",
        "name",
        "exchange",
        "segment",
        "security_type",
        "instrument_class",
        "is_index",
        "is_stock",
        "is_fno",
        "fyers_symbol",
        "nse_token",
        "acquisition_symbol",
        "acquisition_ready",
        "acquisition_status",
        "history_status",
    ]

    for column in wanted_columns:

        if column not in queue.columns:
            queue[column] = ""

    queue = queue[
        wanted_columns
    ].copy()

    queue = (
        queue
        .sort_values(
            by=[
                "acquisition_ready",
                "symbol",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    return queue


# ============================================================
# VALIDATION
# ============================================================

def validate_universe(
    universe: pd.DataFrame,
    canonical: pd.DataFrame,
    acquisition_queue: pd.DataFrame,
) -> dict[str, object]:

    duplicate_security_ids = int(
        universe.duplicated(
            subset=[
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    blank_security_ids = int(
        universe[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_symbols = int(
        universe[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    symbol_identity_mismatches = int(
        (
            ~universe[
                "symbol_identity_match"
            ]
        ).sum()
    )

    universe_symbols = int(
        len(universe)
    )

    symbols_with_history = int(
        universe[
            "has_canonical_history"
        ].sum()
    )

    symbols_missing_history = int(
        universe[
            "requires_acquisition"
        ].sum()
    )

    acquisition_ready = int(
        acquisition_queue[
            "acquisition_ready"
        ].sum()
        if not acquisition_queue.empty
        else 0
    )

    acquisition_blocked = int(
        (
            acquisition_queue[
                "acquisition_status"
            ]
            == "BLOCKED_NO_SYMBOL"
        ).sum()
        if not acquisition_queue.empty
        else 0
    )

    coverage_percent = (
        round(
            (
                symbols_with_history
                / universe_symbols
            )
            * 100,
            2,
        )
        if universe_symbols
        else 0.0
    )

    canonical_rows = int(
        len(canonical)
    )

    canonical_unique_symbols = int(
        canonical[
            "security_id"
        ]
        .nunique()
    )

    critical_issues = (
        duplicate_security_ids
        + blank_security_ids
        + blank_symbols
        + symbol_identity_mismatches
    )

    # Missing historical coverage is NOT a structural failure.
    # It is precisely what MPD-006 is designed to identify.
    warnings = (
        symbols_missing_history
        + acquisition_blocked
    )

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "FAILED"
    )

    return {
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

        "security_master_file":
            str(
                SECURITY_MASTER_FILE
            ),

        "canonical_file":
            str(
                CANONICAL_FILE
            ),

        "universe_symbols":
            universe_symbols,

        "canonical_rows":
            canonical_rows,

        "canonical_unique_symbols":
            canonical_unique_symbols,

        "symbols_with_history":
            symbols_with_history,

        "symbols_missing_history":
            symbols_missing_history,

        "coverage_percent":
            coverage_percent,

        "acquisition_queue_rows":
            len(
                acquisition_queue
            ),

        "acquisition_ready":
            acquisition_ready,

        "acquisition_blocked":
            acquisition_blocked,

        "duplicate_security_ids":
            duplicate_security_ids,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "symbol_identity_mismatches":
            symbol_identity_mismatches,

        "critical_issues":
            critical_issues,

        "warnings":
            warnings,

        "market_price_database_modified":
            False,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            status,
    }


# ============================================================
# WRITE OUTPUTS
# ============================================================

def write_outputs(
    universe: pd.DataFrame,
    acquisition_queue: pd.DataFrame,
    summary: dict[str, object],
) -> None:

    ensure_output_directory()

    universe.to_csv(
        UNIVERSE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    acquisition_queue.to_csv(
        ACQUISITION_QUEUE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [summary]
    ).to_csv(
        AUDIT_CSV,
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
    print("AQSD MARKET PRICE UNIVERSE BUILDER")
    print("=" * 96)

    print(
        f"Module                         : "
        f"{summary['module_id']}"
    )

    print(
        f"Version                        : "
        f"{summary['module_version']}"
    )

    print("-" * 96)

    print(
        f"Universe Symbols               : "
        f"{int(summary['universe_symbols']):,}"
    )

    print(
        f"Canonical Rows                 : "
        f"{int(summary['canonical_rows']):,}"
    )

    print(
        f"Canonical Unique Symbols       : "
        f"{int(summary['canonical_unique_symbols']):,}"
    )

    print(
        f"Symbols With History           : "
        f"{int(summary['symbols_with_history']):,}"
    )

    print(
        f"Symbols Missing History        : "
        f"{int(summary['symbols_missing_history']):,}"
    )

    print(
        f"Historical Coverage            : "
        f"{summary['coverage_percent']}%"
    )

    print("-" * 96)

    print(
        f"Acquisition Queue              : "
        f"{int(summary['acquisition_queue_rows']):,}"
    )

    print(
        f"Acquisition Ready              : "
        f"{int(summary['acquisition_ready']):,}"
    )

    print(
        f"Acquisition Blocked            : "
        f"{int(summary['acquisition_blocked']):,}"
    )

    print("-" * 96)

    print(
        f"Duplicate Security IDs         : "
        f"{int(summary['duplicate_security_ids']):,}"
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
        f"Symbol Identity Mismatches     : "
        f"{int(summary['symbol_identity_mismatches']):,}"
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
        f"Universe CSV                   : "
        f"{UNIVERSE_CSV}"
    )

    print(
        f"Acquisition Queue CSV          : "
        f"{ACQUISITION_QUEUE_CSV}"
    )

    print(
        f"Audit CSV                      : "
        f"{AUDIT_CSV}"
    )

    print(
        f"Summary JSON                   : "
        f"{SUMMARY_JSON}"
    )

    print("-" * 96)

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
# MAIN BUILDER
# ============================================================

def run_builder() -> dict[str, object]:

    ensure_output_directory()

    security_master = (
        load_security_master()
    )

    universe = (
        build_market_price_universe(
            security_master
        )
    )

    canonical = (
        load_canonical_history()
    )

    coverage = (
        build_history_coverage(
            canonical
        )
    )

    universe = (
        reconcile_universe(
            universe,
            coverage,
        )
    )

    acquisition_queue = (
        build_acquisition_queue(
            universe
        )
    )

    summary = (
        validate_universe(
            universe,
            canonical,
            acquisition_queue,
        )
    )

    write_outputs(
        universe,
        acquisition_queue,
        summary,
    )

    return summary


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_builder()

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
        print("AQSD MARKET PRICE UNIVERSE BUILDER")
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

        print(
            "Historical Fabrication         : PROHIBITED"
        )

        print("=" * 96)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()