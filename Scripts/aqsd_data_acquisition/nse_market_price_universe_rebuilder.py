"""
AQSD
Market Price Universe Rebuilder

Module ID: FNO-005
Version: 1.0.0
Author: AQSD

Purpose
-------
Rebuild the ACTIVE Market Price acquisition universe from the
promoted AQSD Security Master.

Core Rules
----------
1. Use the LIVE promoted Security Master.
2. Include CURRENT F&O members only.
3. Preserve former F&O securities in the Security Master.
4. Do not delete historical securities.
5. Do not modify the Market Price Database.
6. Build a fresh acquisition universe.
7. Build a fresh acquisition queue.
8. Validate symbol identity and FYERS symbol readiness.
9. Block symbols that cannot be safely downloaded.
10. Produce audit and summary files.

Expected Current State
----------------------
Security Master Rows      : 249
Current F&O Members       : 213
Former F&O Members        : 36

Outputs
-------
AQSD_Market_Price_Universe.csv
AQSD_Market_Price_Acquisition_Queue.csv
AQSD_Market_Price_Universe_Blocked.csv
AQSD_Market_Price_Universe_Audit.csv
AQSD_Market_Price_Universe_Summary.json

Protection
----------
Security Master           : READ ONLY
Market Price Database     : NOT MODIFIED
Historical Database       : NOT MODIFIED
Historical Fabrication    : PROHIBITED
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "FNO-005"
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


# ============================================================
# INPUT FILES
# ============================================================

SECURITY_MASTER_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

FNO004_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Live_Promotion_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

UNIVERSE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Universe.csv"
)

ACQUISITION_QUEUE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue.csv"
)

BLOCKED_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Universe_Blocked.csv"
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


def separator() -> None:

    print(
        "=" * 100
    )


def sub_separator() -> None:

    print(
        "-" * 100
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
        .replace("/", "_")
        .replace(".", "_")
        .replace("(", "")
        .replace(")", "")
    )


def normalize_symbol(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    symbol = (
        str(value)
        .strip()
        .upper()
    )

    if symbol.startswith(
        "NSE:"
    ):
        symbol = symbol[4:]

    for suffix in (
        "-EQ",
        ".NS",
    ):

        if symbol.endswith(
            suffix
        ):

            symbol = symbol[
                : -len(suffix)
            ]

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYNEXT50": "NIFTYNXT50",
    }

    return aliases.get(
        symbol,
        symbol,
    )


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


def safe_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(
        value
    ).strip()


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input_files() -> None:

    required_files = [
        SECURITY_MASTER_FILE,
        FNO004_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required FNO-005 input files missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# LOADERS
# ============================================================

def load_security_master() -> pd.DataFrame:

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

    required_columns = {
        "security_id",
        "symbol",
        "current_fno_member",
    }

    missing = (
        required_columns
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Security Master missing required columns: "
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
        .map(
            normalize_symbol
        )
    )

    return dataframe


def load_fno004_summary() -> dict[str, object]:

    return json.loads(
        FNO004_SUMMARY_FILE.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# PRIOR MODULE VALIDATION
# ============================================================

def validate_fno004(
    summary: dict[str, object],
) -> None:

    status = str(
        summary.get(
            "status",
            "",
        )
    ).strip().upper()

    promotion_status = str(
        summary.get(
            "promotion_status",
            "",
        )
    ).strip().upper()

    critical_issues = int(
        summary.get(
            "critical_issues",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "FNO-004 status is not SUCCESS."
        )

    if promotion_status != "PROMOTED":

        raise RuntimeError(
            "FNO-004 promotion status is not PROMOTED."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "FNO-004 contains critical issues."
        )


# ============================================================
# FYERS SYMBOL RESOLUTION
# ============================================================

def resolve_fyers_symbol(
    row: pd.Series,
) -> tuple[str, str]:

    symbol = normalize_symbol(
        row[
            "symbol"
        ]
    )

    if not symbol:

        return (
            "",
            "BLANK_SYMBOL",
        )

    existing_fyers_symbol = ""

    if "fyers_symbol" in row.index:

        existing_fyers_symbol = safe_text(
            row[
                "fyers_symbol"
            ]
        )

    if existing_fyers_symbol:

        return (
            existing_fyers_symbol,
            "",
        )

    is_index = False

    if "is_index" in row.index:

        is_index = parse_bool(
            row[
                "is_index"
            ]
        )

    instrument_class = ""

    if "instrument_class" in row.index:

        instrument_class = (
            safe_text(
                row[
                    "instrument_class"
                ]
            )
            .upper()
        )

    security_type = ""

    if "security_type" in row.index:

        security_type = (
            safe_text(
                row[
                    "security_type"
                ]
            )
            .upper()
        )

    if (
        is_index
        or "INDEX" in instrument_class
        or "INDEX" in security_type
    ):

        index_map = {
            "NIFTY":
                "NSE:NIFTY50-INDEX",

            "BANKNIFTY":
                "NSE:NIFTYBANK-INDEX",

            "FINNIFTY":
                "NSE:FINNIFTY-INDEX",

            "MIDCPNIFTY":
                "NSE:MIDCPNIFTY-INDEX",

            "NIFTYNXT50":
                "NSE:NIFTYNXT50-INDEX",
        }

        resolved = index_map.get(
            symbol,
            "",
        )

        if resolved:

            return (
                resolved,
                "",
            )

        return (
            "",
            "UNRESOLVED_INDEX_SYMBOL",
        )

    return (
        f"NSE:{symbol}-EQ",
        "",
    )


# ============================================================
# BUILD UNIVERSE
# ============================================================

def build_market_price_universe(
    security_master: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:

    current_mask = (
        security_master[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
    )

    universe = security_master[
        current_mask
    ].copy()

    universe = universe[
        universe[
            "symbol"
        ].ne(
            ""
        )
    ].copy()

    resolved_symbols: list[str] = []
    block_reasons: list[str] = []

    for _, row in universe.iterrows():

        (
            fyers_symbol,
            block_reason,
        ) = resolve_fyers_symbol(
            row
        )

        resolved_symbols.append(
            fyers_symbol
        )

        block_reasons.append(
            block_reason
        )

    universe[
        "resolved_fyers_symbol"
    ] = resolved_symbols

    universe[
        "block_reason"
    ] = block_reasons

    universe[
        "acquisition_ready"
    ] = (
        universe[
            "block_reason"
        ].eq("")
        & universe[
            "resolved_fyers_symbol"
        ].ne("")
    )

    universe[
        "market_price_scope"
    ] = "CURRENT_FNO"

    universe[
        "acquisition_source"
    ] = "FYERS_HISTORY_API"

    universe[
        "resolution"
    ] = "1D"

    universe[
        "universe_module"
    ] = MODULE_ID

    universe[
        "universe_version"
    ] = MODULE_VERSION

    universe[
        "generated_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    blocked = universe[
        ~universe[
            "acquisition_ready"
        ]
    ].copy()

    return (
        universe,
        blocked,
    )


# ============================================================
# BUILD ACQUISITION QUEUE
# ============================================================

def build_acquisition_queue(
    universe: pd.DataFrame,
) -> pd.DataFrame:

    ready = universe[
        universe[
            "acquisition_ready"
        ]
    ].copy()

    queue_columns = [
        "security_id",
        "symbol",
        "resolved_fyers_symbol",
        "market_price_scope",
        "acquisition_source",
        "resolution",
    ]

    optional_columns = [
        "name",
        "sector",
        "industry",
        "exchange",
        "instrument_class",
        "security_type",
        "is_index",
        "is_stock",
        "fno_membership_status",
        "fno_membership_asof",
    ]

    for column in optional_columns:

        if column in ready.columns:

            queue_columns.append(
                column
            )

    queue = ready[
        queue_columns
    ].copy()

    queue[
        "queue_status"
    ] = "READY"

    queue[
        "download_required"
    ] = True

    queue[
        "queue_generated_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    queue = (
        queue
        .sort_values(
            by=[
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return queue


# ============================================================
# VALIDATION
# ============================================================

def validate_universe(
    security_master: pd.DataFrame,
    universe: pd.DataFrame,
    queue: pd.DataFrame,
    blocked: pd.DataFrame,
) -> dict[str, object]:

    live_current_members = int(
        security_master[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
        .sum()
    )

    universe_rows = int(
        len(
            universe
        )
    )

    queue_rows = int(
        len(
            queue
        )
    )

    blocked_rows = int(
        len(
            blocked
        )
    )

    universe_matches_live = (
        universe_rows
        == live_current_members
    )

    queue_reconciles = (
        queue_rows
        + blocked_rows
        == universe_rows
    )

    duplicate_security_ids = int(
        universe.duplicated(
            subset=[
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        universe.duplicated(
            subset=[
                "symbol",
            ],
            keep=False,
        ).sum()
    )

    duplicate_fyers_symbols = int(
        universe[
            universe[
                "resolved_fyers_symbol"
            ].ne("")
        ]
        .duplicated(
            subset=[
                "resolved_fyers_symbol",
            ],
            keep=False,
        )
        .sum()
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

    blank_ready_fyers_symbols = int(
        universe[
            universe[
                "acquisition_ready"
            ]
        ][
            "resolved_fyers_symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    critical_issues = (
        duplicate_security_ids
        + duplicate_symbols
        + duplicate_fyers_symbols
        + blank_security_ids
        + blank_symbols
        + blank_ready_fyers_symbols
    )

    if not universe_matches_live:

        critical_issues += 1

    if not queue_reconciles:

        critical_issues += 1

    return {
        "security_master_rows":
            int(
                len(
                    security_master
                )
            ),

        "live_current_fno_members":
            live_current_members,

        "universe_rows":
            universe_rows,

        "queue_rows":
            queue_rows,

        "blocked_rows":
            blocked_rows,

        "universe_matches_live":
            universe_matches_live,

        "queue_reconciles":
            queue_reconciles,

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "duplicate_fyers_symbols":
            duplicate_fyers_symbols,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "blank_ready_fyers_symbols":
            blank_ready_fyers_symbols,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# WRITE OUTPUTS
# ============================================================

def write_outputs(
    universe: pd.DataFrame,
    queue: pd.DataFrame,
    blocked: pd.DataFrame,
    summary: dict[str, object],
) -> None:

    universe.to_csv(
        UNIVERSE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    queue.to_csv(
        ACQUISITION_QUEUE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    blocked.to_csv(
        BLOCKED_CSV,
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
# RUN
# ============================================================

def run_rebuilder() -> dict[str, object]:

    ensure_output_directory()

    validate_input_files()

    fno004_summary = (
        load_fno004_summary()
    )

    validate_fno004(
        fno004_summary
    )

    security_master = (
        load_security_master()
    )

    (
        universe,
        blocked,
    ) = build_market_price_universe(
        security_master
    )

    queue = build_acquisition_queue(
        universe
    )

    validation = validate_universe(
        security_master,
        universe,
        queue,
        blocked,
    )

    status = (
        "SUCCESS"
        if validation[
            "critical_issues"
        ] == 0
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

        "security_master_rows":
            validation[
                "security_master_rows"
            ],

        "live_current_fno_members":
            validation[
                "live_current_fno_members"
            ],

        "universe_rows":
            validation[
                "universe_rows"
            ],

        "acquisition_ready":
            validation[
                "queue_rows"
            ],

        "acquisition_blocked":
            validation[
                "blocked_rows"
            ],

        "universe_matches_live":
            validation[
                "universe_matches_live"
            ],

        "queue_reconciles":
            validation[
                "queue_reconciles"
            ],

        "duplicate_security_ids":
            validation[
                "duplicate_security_ids"
            ],

        "duplicate_symbols":
            validation[
                "duplicate_symbols"
            ],

        "duplicate_fyers_symbols":
            validation[
                "duplicate_fyers_symbols"
            ],

        "blank_security_ids":
            validation[
                "blank_security_ids"
            ],

        "blank_symbols":
            validation[
                "blank_symbols"
            ],

        "blank_ready_fyers_symbols":
            validation[
                "blank_ready_fyers_symbols"
            ],

        "critical_issues":
            validation[
                "critical_issues"
            ],

        "universe_csv":
            str(
                UNIVERSE_CSV
            ),

        "acquisition_queue_csv":
            str(
                ACQUISITION_QUEUE_CSV
            ),

        "blocked_csv":
            str(
                BLOCKED_CSV
            ),

        "security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            status,
    }

    write_outputs(
        universe,
        queue,
        blocked,
        summary,
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "Market Price Universe validation failed."
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
        "AQSD MARKET PRICE UNIVERSE REBUILDER"
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

    sub_separator()

    print(
        f"Security Master Rows           : "
        f"{int(summary['security_master_rows']):,}"
    )

    print(
        f"Live Current F&O Members       : "
        f"{int(summary['live_current_fno_members']):,}"
    )

    print(
        f"Market Price Universe Rows     : "
        f"{int(summary['universe_rows']):,}"
    )

    sub_separator()

    print(
        f"Acquisition Ready              : "
        f"{int(summary['acquisition_ready']):,}"
    )

    print(
        f"Acquisition Blocked            : "
        f"{int(summary['acquisition_blocked']):,}"
    )

    print(
        f"Universe Matches Live          : "
        f"{summary['universe_matches_live']}"
    )

    print(
        f"Queue Reconciles               : "
        f"{summary['queue_reconciles']}"
    )

    sub_separator()

    print(
        f"Duplicate Security IDs         : "
        f"{int(summary['duplicate_security_ids']):,}"
    )

    print(
        f"Duplicate Symbols              : "
        f"{int(summary['duplicate_symbols']):,}"
    )

    print(
        f"Duplicate FYERS Symbols        : "
        f"{int(summary['duplicate_fyers_symbols']):,}"
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
        f"Blank Ready FYERS Symbols      : "
        f"{int(summary['blank_ready_fyers_symbols']):,}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Universe CSV                   : "
        f"{summary['universe_csv']}"
    )

    print(
        f"Acquisition Queue CSV          : "
        f"{summary['acquisition_queue_csv']}"
    )

    print(
        f"Blocked CSV                    : "
        f"{summary['blocked_csv']}"
    )

    sub_separator()

    print(
        "Security Master                : READ ONLY"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Historical Database            : NOT MODIFIED"
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

        summary = run_rebuilder()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        separator()

        print(
            "AQSD MARKET PRICE UNIVERSE REBUILDER"
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
            "Security Master                : NOT MODIFIED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        print(
            "Historical Database            : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()