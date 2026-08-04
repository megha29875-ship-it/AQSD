"""
AQSD
NSE Market Price Source Auditor

Module : MPD-003
Version: 1.1.0
Author : AQSD

Purpose
-------
Audit possible AQSD market-price sources and determine whether any
existing source is suitable for building the canonical Market Price
Database.

Core principle
--------------
A technically strong price source is NOT automatically eligible for
the Market Price Database.

The Market Price Database must represent canonical UNDERLYING /
CASH-MARKET prices.

Therefore:

UNDERLYING_PRICE
    May be eligible for canonical MPD use.

FUTURES
    Must remain in Futures Intelligence / FID.
    Never eligible as canonical MPD source.

OPTIONS
    Must remain in Options Intelligence / OID.
    Never eligible as canonical MPD source.

MARKET_BREADTH
    Supporting / derived source only.

ANALYTICAL_SNAPSHOT
    Derived analytical source only.

SUMMARY
    Supporting metadata only.

This module is READ ONLY.

It does NOT:
- modify any source
- rebuild historical data
- modify the frozen F&O database
- modify the Market Price database
- promote any source automatically
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID: Final[str] = "MPD-003"
MODULE_VERSION: Final[str] = "1.1.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

FROZEN_DATABASE: Final[Path] = Path(
    r"D:\AQSD_DATA\Databases\NSE_FNO_Historical.db"
)

SECURITY_MASTER: Final[Path] = (
    PROJECT_ROOT
    / "Output"
    / "AQSD_Security_Master_Enriched.csv"
)

MARKET_BREADTH_HISTORY: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "Market_Breadth"
    / "market_breadth_price_history.csv"
)

HISTORICAL_ROOT: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "Historical"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Source_Audit.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Source_Audit_Summary.json"
)


# ============================================================
# SOURCE CLASSIFICATION
# ============================================================

SOURCE_CLASSIFICATION: Final[dict[str, dict[str, object]]] = {

    "underlying_daily_summary": {
        "asset_class": "UNDERLYING_PRICE",
        "mpd_eligible": True,
        "destination": "MPD",
        "source_role": "PRIMARY_CANDIDATE",
    },

    "futures_history": {
        "asset_class": "FUTURES",
        "mpd_eligible": False,
        "destination": "FID",
        "source_role": "DERIVATIVES_SOURCE",
    },

    "options_history": {
        "asset_class": "OPTIONS",
        "mpd_eligible": False,
        "destination": "OID",
        "source_role": "DERIVATIVES_SOURCE",
    },

    "daily_summary": {
        "asset_class": "SUMMARY",
        "mpd_eligible": False,
        "destination": "SUPPORTING_DATA",
        "source_role": "SUMMARY_SOURCE",
    },

    "market_breadth_price_history": {
        "asset_class": "MARKET_BREADTH",
        "mpd_eligible": False,
        "destination": "BREADTH_INTELLIGENCE",
        "source_role": "SUPPORTING_PRICE_SOURCE",
    },

    "market_structure_history": {
        "asset_class": "ANALYTICAL_SNAPSHOT",
        "mpd_eligible": False,
        "destination": "MARKET_STRUCTURE",
        "source_role": "DERIVED_ANALYTICAL_SOURCE",
    },
}


# ============================================================
# HELPERS
# ============================================================

def ensure_output_directory() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def normalize_name(
    value: object,
) -> str:

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def load_security_master_symbols() -> set[str]:

    if not SECURITY_MASTER.exists():

        raise FileNotFoundError(
            f"Security Master not found: {SECURITY_MASTER}"
        )

    dataframe = pd.read_csv(
        SECURITY_MASTER,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_name(column)
        for column in dataframe.columns
    ]

    if "symbol" not in dataframe.columns:

        raise RuntimeError(
            "Security Master does not contain symbol column."
        )

    return set(
        dataframe["symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )


def open_frozen_database() -> sqlite3.Connection:

    if not FROZEN_DATABASE.exists():

        raise FileNotFoundError(
            f"Frozen database not found: {FROZEN_DATABASE}"
        )

    uri = (
        f"file:{FROZEN_DATABASE.as_posix()}"
        "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:

    rows = connection.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [
        str(row["name"])
        for row in rows
    ]


def detect_column(
    columns: list[str],
    candidates: list[str],
) -> str | None:

    normalized = {
        normalize_name(column): column
        for column in columns
    }

    for candidate in candidates:

        if candidate in normalized:
            return normalized[candidate]

    return None


def get_source_classification(
    source_name: str,
) -> dict[str, object]:

    return SOURCE_CLASSIFICATION.get(
        source_name,
        {
            "asset_class": "UNKNOWN",
            "mpd_eligible": False,
            "destination": "UNCLASSIFIED",
            "source_role": "UNKNOWN",
        },
    )


# ============================================================
# SUITABILITY LOGIC
# ============================================================

def determine_suitability(
    *,
    asset_class: str,
    mpd_eligible: bool,
    has_ohlc: bool,
    has_volume: bool,
    master_matches: int,
    future_rows: int,
) -> str:

    if not mpd_eligible:

        if asset_class in {
            "FUTURES",
            "OPTIONS",
        }:
            return "NOT ELIGIBLE - DERIVATIVE SOURCE"

        if asset_class == "MARKET_BREADTH":
            return "SUPPORTING ONLY"

        if asset_class == "ANALYTICAL_SNAPSHOT":
            return "DERIVED DATA - NOT CANONICAL"

        if asset_class == "SUMMARY":
            return "SUMMARY ONLY"

        return "NOT MPD ELIGIBLE"

    if master_matches <= 0:

        return "UNSUITABLE"

    if future_rows > 0:

        return "REJECT - FUTURE DATE CONTAMINATION"

    if not has_ohlc:

        return "PARTIAL - FULL OHLC REQUIRED"

    if not has_volume:

        return "PARTIAL - VOLUME MISSING"

    return "CANONICAL CANDIDATE"


# ============================================================
# SQLITE SOURCE AUDIT
# ============================================================

def audit_sqlite_table(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    security_master_symbols: set[str],
) -> dict[str, object]:

    classification = get_source_classification(
        table_name
    )

    if not table_exists(
        connection,
        table_name,
    ):

        return {
            "source_type": "SQLITE",
            "source_name": table_name,
            "asset_class": classification[
                "asset_class"
            ],
            "mpd_eligible": classification[
                "mpd_eligible"
            ],
            "destination": classification[
                "destination"
            ],
            "source_role": classification[
                "source_role"
            ],
            "exists": False,
            "status": "NOT FOUND",
        }

    columns = get_table_columns(
        connection,
        table_name,
    )

    symbol_column = detect_column(
        columns,
        [
            "symbol",
            "underlying",
            "aqsd_underlying",
        ],
    )

    date_column = detect_column(
        columns,
        [
            "trade_date",
            "date",
            "trading_date",
        ],
    )

    open_column = detect_column(
        columns,
        [
            "open",
            "underlying_open",
            "spot_open",
        ],
    )

    high_column = detect_column(
        columns,
        [
            "high",
            "underlying_high",
            "spot_high",
        ],
    )

    low_column = detect_column(
        columns,
        [
            "low",
            "underlying_low",
            "spot_low",
        ],
    )

    close_column = detect_column(
        columns,
        [
            "close",
            "underlying_close",
            "spot_close",
        ],
    )

    volume_column = detect_column(
        columns,
        [
            "volume",
            "underlying_volume",
        ],
    )

    total_rows = int(
        connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]
        or 0
    )

    unique_symbols = 0
    first_session = None
    last_session = None
    future_rows = 0
    master_matches = 0
    unknown_symbols = 0

    database_symbols: set[str] = set()

    if symbol_column:

        rows = connection.execute(
            f"""
            SELECT DISTINCT "{symbol_column}"
            FROM "{table_name}"
            WHERE "{symbol_column}" IS NOT NULL
              AND TRIM("{symbol_column}") <> ''
            """
        ).fetchall()

        database_symbols = {
            str(row[0])
            .strip()
            .upper()
            for row in rows
        }

        unique_symbols = len(
            database_symbols
        )

        master_matches = len(
            database_symbols
            & security_master_symbols
        )

        unknown_symbols = len(
            database_symbols
            - security_master_symbols
        )

    if date_column:

        row = connection.execute(
            f"""
            SELECT
                MIN("{date_column}"),
                MAX("{date_column}")
            FROM "{table_name}"
            """
        ).fetchone()

        first_session = row[0]
        last_session = row[1]

        try:

            future_rows = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM "{table_name}"
                    WHERE "{date_column}" > ?
                    """,
                    (
                        date.today().isoformat(),
                    ),
                ).fetchone()[0]
                or 0
            )

        except sqlite3.Error:

            future_rows = -1

    has_ohlc = all(
        [
            open_column,
            high_column,
            low_column,
            close_column,
        ]
    )

    has_volume = (
        volume_column is not None
    )

    coverage_percent = (
        round(
            (
                master_matches
                / len(
                    security_master_symbols
                )
            )
            * 100,
            2,
        )
        if security_master_symbols
        else 0.0
    )

    suitability = determine_suitability(
        asset_class=str(
            classification[
                "asset_class"
            ]
        ),
        mpd_eligible=bool(
            classification[
                "mpd_eligible"
            ]
        ),
        has_ohlc=bool(
            has_ohlc
        ),
        has_volume=bool(
            has_volume
        ),
        master_matches=master_matches,
        future_rows=future_rows,
    )

    return {
        "source_type": "SQLITE",
        "source_name": table_name,

        "asset_class":
            classification[
                "asset_class"
            ],

        "mpd_eligible":
            classification[
                "mpd_eligible"
            ],

        "destination":
            classification[
                "destination"
            ],

        "source_role":
            classification[
                "source_role"
            ],

        "exists": True,

        "rows":
            total_rows,

        "columns":
            ", ".join(
                columns
            ),

        "symbol_column":
            symbol_column,

        "date_column":
            date_column,

        "open_column":
            open_column,

        "high_column":
            high_column,

        "low_column":
            low_column,

        "close_column":
            close_column,

        "volume_column":
            volume_column,

        "has_ohlc":
            bool(
                has_ohlc
            ),

        "has_volume":
            bool(
                has_volume
            ),

        "unique_symbols":
            unique_symbols,

        "security_master_matches":
            master_matches,

        "security_master_total":
            len(
                security_master_symbols
            ),

        "coverage_percent":
            coverage_percent,

        "unknown_symbols":
            unknown_symbols,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "future_rows":
            future_rows,

        "suitability":
            suitability,

        "status":
            "AUDITED",
    }


# ============================================================
# CSV SOURCE AUDIT
# ============================================================

def audit_csv_file(
    path: Path,
    *,
    source_name: str,
    security_master_symbols: set[str],
) -> dict[str, object]:

    classification = get_source_classification(
        source_name
    )

    if not path.exists():

        return {
            "source_type": "CSV",
            "source_name": source_name,

            "asset_class":
                classification[
                    "asset_class"
                ],

            "mpd_eligible":
                classification[
                    "mpd_eligible"
                ],

            "destination":
                classification[
                    "destination"
                ],

            "source_role":
                classification[
                    "source_role"
                ],

            "path": str(
                path
            ),

            "exists": False,

            "status": "NOT FOUND",
        }

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_name(column)
        for column in dataframe.columns
    ]

    columns = list(
        dataframe.columns
    )

    symbol_column = detect_column(
        columns,
        [
            "symbol",
            "underlying",
        ],
    )

    date_column = detect_column(
        columns,
        [
            "trade_date",
            "date",
        ],
    )

    open_column = detect_column(
        columns,
        ["open"],
    )

    high_column = detect_column(
        columns,
        ["high"],
    )

    low_column = detect_column(
        columns,
        ["low"],
    )

    close_column = detect_column(
        columns,
        ["close"],
    )

    volume_column = detect_column(
        columns,
        ["volume"],
    )

    symbols: set[str] = set()

    if symbol_column:

        symbols = set(
            dataframe[
                symbol_column
            ]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

    master_matches = len(
        symbols
        & security_master_symbols
    )

    unknown_symbols = len(
        symbols
        - security_master_symbols
    )

    first_session = None
    last_session = None
    future_rows = 0

    if date_column:

        parsed_dates = pd.to_datetime(
            dataframe[
                date_column
            ],
            errors="coerce",
        )

        if parsed_dates.notna().any():

            first_session = (
                parsed_dates.min()
                .date()
                .isoformat()
            )

            last_session = (
                parsed_dates.max()
                .date()
                .isoformat()
            )

            future_rows = int(
                (
                    parsed_dates.dt.date
                    > date.today()
                ).sum()
            )

    has_ohlc = all(
        [
            open_column,
            high_column,
            low_column,
            close_column,
        ]
    )

    has_volume = (
        volume_column is not None
    )

    coverage_percent = (
        round(
            (
                master_matches
                / len(
                    security_master_symbols
                )
            )
            * 100,
            2,
        )
        if security_master_symbols
        else 0.0
    )

    suitability = determine_suitability(
        asset_class=str(
            classification[
                "asset_class"
            ]
        ),
        mpd_eligible=bool(
            classification[
                "mpd_eligible"
            ]
        ),
        has_ohlc=bool(
            has_ohlc
        ),
        has_volume=bool(
            has_volume
        ),
        master_matches=master_matches,
        future_rows=future_rows,
    )

    return {
        "source_type": "CSV",
        "source_name": source_name,

        "asset_class":
            classification[
                "asset_class"
            ],

        "mpd_eligible":
            classification[
                "mpd_eligible"
            ],

        "destination":
            classification[
                "destination"
            ],

        "source_role":
            classification[
                "source_role"
            ],

        "path":
            str(
                path
            ),

        "exists":
            True,

        "rows":
            len(
                dataframe
            ),

        "columns":
            ", ".join(
                columns
            ),

        "symbol_column":
            symbol_column,

        "date_column":
            date_column,

        "open_column":
            open_column,

        "high_column":
            high_column,

        "low_column":
            low_column,

        "close_column":
            close_column,

        "volume_column":
            volume_column,

        "has_ohlc":
            bool(
                has_ohlc
            ),

        "has_volume":
            bool(
                has_volume
            ),

        "unique_symbols":
            len(
                symbols
            ),

        "security_master_matches":
            master_matches,

        "security_master_total":
            len(
                security_master_symbols
            ),

        "coverage_percent":
            coverage_percent,

        "unknown_symbols":
            unknown_symbols,

        "first_session":
            first_session,

        "last_session":
            last_session,

        "future_rows":
            future_rows,

        "suitability":
            suitability,

        "status":
            "AUDITED",
    }


# ============================================================
# HISTORICAL MARKET STRUCTURE AUDIT
# ============================================================

def audit_market_structure_history(
    security_master_symbols: set[str],
) -> dict[str, object]:

    source_name = "market_structure_history"

    classification = get_source_classification(
        source_name
    )

    files = sorted(
        HISTORICAL_ROOT.rglob(
            "market_structure.csv"
        )
    )

    if not files:

        return {
            "source_type": "CSV_COLLECTION",
            "source_name": source_name,

            "asset_class":
                classification[
                    "asset_class"
                ],

            "mpd_eligible":
                classification[
                    "mpd_eligible"
                ],

            "destination":
                classification[
                    "destination"
                ],

            "source_role":
                classification[
                    "source_role"
                ],

            "exists": False,

            "status": "NOT FOUND",
        }

    symbols: set[str] = set()

    earliest = None
    latest = None

    total_rows = 0

    has_ohlc = True
    has_volume = True

    future_rows = 0

    columns_seen: set[str] = set()

    for path in files:

        try:

            dataframe = pd.read_csv(
                path,
                low_memory=False,
            )

        except Exception:

            continue

        dataframe.columns = [
            normalize_name(column)
            for column in dataframe.columns
        ]

        columns_seen.update(
            dataframe.columns
        )

        total_rows += len(
            dataframe
        )

        if "symbol" in dataframe.columns:

            symbols.update(
                dataframe["symbol"]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
            )

        required_ohlc = {
            "open",
            "high",
            "low",
            "close",
        }

        if not required_ohlc.issubset(
            dataframe.columns
        ):

            has_ohlc = False

        if "volume" not in dataframe.columns:

            has_volume = False

        if "date" in dataframe.columns:

            parsed = pd.to_datetime(
                dataframe["date"],
                errors="coerce",
            )

            valid = parsed.dropna()

            if not valid.empty:

                file_first = (
                    valid.min().date()
                )

                file_last = (
                    valid.max().date()
                )

                if (
                    earliest is None
                    or file_first < earliest
                ):

                    earliest = file_first

                if (
                    latest is None
                    or file_last > latest
                ):

                    latest = file_last

                future_rows += int(
                    (
                        parsed.dt.date
                        > date.today()
                    ).sum()
                )

    master_matches = len(
        symbols
        & security_master_symbols
    )

    coverage_percent = (
        round(
            (
                master_matches
                / len(
                    security_master_symbols
                )
            )
            * 100,
            2,
        )
        if security_master_symbols
        else 0.0
    )

    suitability = determine_suitability(
        asset_class=str(
            classification[
                "asset_class"
            ]
        ),
        mpd_eligible=bool(
            classification[
                "mpd_eligible"
            ]
        ),
        has_ohlc=has_ohlc,
        has_volume=has_volume,
        master_matches=master_matches,
        future_rows=future_rows,
    )

    return {
        "source_type":
            "CSV_COLLECTION",

        "source_name":
            source_name,

        "asset_class":
            classification[
                "asset_class"
            ],

        "mpd_eligible":
            classification[
                "mpd_eligible"
            ],

        "destination":
            classification[
                "destination"
            ],

        "source_role":
            classification[
                "source_role"
            ],

        "path":
            str(
                HISTORICAL_ROOT
            ),

        "exists":
            True,

        "files":
            len(
                files
            ),

        "rows":
            total_rows,

        "columns":
            ", ".join(
                sorted(
                    columns_seen
                )
            ),

        "has_ohlc":
            has_ohlc,

        "has_volume":
            has_volume,

        "unique_symbols":
            len(
                symbols
            ),

        "security_master_matches":
            master_matches,

        "security_master_total":
            len(
                security_master_symbols
            ),

        "coverage_percent":
            coverage_percent,

        "unknown_symbols":
            len(
                symbols
                - security_master_symbols
            ),

        "first_session":
            (
                earliest.isoformat()
                if earliest
                else None
            ),

        "last_session":
            (
                latest.isoformat()
                if latest
                else None
            ),

        "future_rows":
            future_rows,

        "suitability":
            suitability,

        "status":
            "AUDITED",
    }


# ============================================================
# QUALITY SCORE
# ============================================================

def score_source(
    row: dict[str, object],
) -> float:

    if not row.get(
        "exists",
        False,
    ):
        return -1.0

    score = 0.0

    if row.get(
        "has_ohlc",
        False,
    ):

        score += 50.0

    if row.get(
        "has_volume",
        False,
    ):

        score += 10.0

    score += float(
        row.get(
            "coverage_percent",
            0.0,
        )
        or 0.0
    )

    future_rows = int(
        row.get(
            "future_rows",
            0,
        )
        or 0
    )

    if future_rows > 0:

        score -= 50.0

    if (
        row.get(
            "source_type"
        )
        == "SQLITE"
    ):

        score += 10.0

    return round(
        score,
        2,
    )


# ============================================================
# CANONICAL ELIGIBILITY SCORE
# ============================================================

def canonical_score(
    row: dict[str, object],
) -> float:

    if not row.get(
        "exists",
        False,
    ):

        return -1.0

    if not bool(
        row.get(
            "mpd_eligible",
            False,
        )
    ):

        return -1.0

    score = score_source(
        row
    )

    if not row.get(
        "has_ohlc",
        False,
    ):

        score -= 100.0

    if int(
        row.get(
            "future_rows",
            0,
        )
        or 0
    ) > 0:

        score -= 100.0

    return round(
        score,
        2,
    )


# ============================================================
# RUN AUDIT
# ============================================================

def run_audit() -> dict[str, object]:

    ensure_output_directory()

    security_master_symbols = (
        load_security_master_symbols()
    )

    sources: list[
        dict[str, object]
    ] = []

    connection = open_frozen_database()

    try:

        for table_name in [
            "underlying_daily_summary",
            "futures_history",
            "daily_summary",
        ]:
            sources.append(
                audit_sqlite_table(
                    connection,
                    table_name=table_name,
                    security_master_symbols=security_master_symbols,
                )
            )

    finally:

        connection.close()

    sources.append(
        audit_csv_file(
            MARKET_BREADTH_HISTORY,
            source_name="market_breadth_price_history",
            security_master_symbols=security_master_symbols,
        )
    )

    sources.append(
        audit_market_structure_history(
            security_master_symbols
        )
    )

    for row in sources:

        row["quality_score"] = score_source(
            row
        )

        row["canonical_score"] = canonical_score(
            row
        )

    eligible_sources = [
        row
        for row in sources
        if (
            row.get(
                "exists",
                False,
            )
            and row.get(
                "mpd_eligible",
                False,
            )
        )
    ]

    ranked_eligible = sorted(
        eligible_sources,
        key=lambda row: float(
            row.get(
                "canonical_score",
                -1,
            )
        ),
        reverse=True,
    )

    recommended = None

    for row in ranked_eligible:

        if (
            row.get(
                "suitability"
            )
            == "CANONICAL CANDIDATE"
        ):

            recommended = row
            break

    if recommended:

        recommendation_status = (
            "CANONICAL SOURCE FOUND"
        )

        recommendation_reason = (
            "Eligible underlying-price source passed "
            "OHLC, volume and future-date checks."
        )

    else:

        recommendation_status = (
            "NO CANONICAL SOURCE FOUND"
        )

        recommendation_reason = (
            "No existing audited UNDERLYING_PRICE source "
            "currently satisfies canonical MPD requirements."
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

        "security_master_symbols":
            len(
                security_master_symbols
            ),

        "sources_audited":
            len(
                sources
            ),

        "mpd_eligible_sources":
            len(
                eligible_sources
            ),

        "recommendation_status":
            recommendation_status,

        "recommendation_reason":
            recommendation_reason,

        "recommended_source":
            (
                recommended.get(
                    "source_name"
                )
                if recommended
                else None
            ),

        "recommended_asset_class":
            (
                recommended.get(
                    "asset_class"
                )
                if recommended
                else None
            ),

        "recommended_canonical_score":
            (
                recommended.get(
                    "canonical_score"
                )
                if recommended
                else None
            ),

        "sources":
            sources,

        "frozen_database_modified":
            False,

        "security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "status":
            "SUCCESS",
    }

    return summary


# ============================================================
# OUTPUT
# ============================================================

def write_outputs(
    summary: dict[str, object],
) -> None:

    sources = list(
        summary.get(
            "sources",
            [],
        )
    )

    pd.DataFrame(
        sources
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
    print("=" * 100)
    print("AQSD MARKET PRICE SOURCE AUDITOR")
    print("=" * 100)

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Security Master Symbols        : "
        f"{summary['security_master_symbols']}"
    )

    print(
        f"Sources Audited                : "
        f"{summary['sources_audited']}"
    )

    print(
        f"MPD Eligible Sources           : "
        f"{summary['mpd_eligible_sources']}"
    )

    print("-" * 100)

    ranked = sorted(
        summary["sources"],
        key=lambda item: float(
            item.get(
                "quality_score",
                -1,
            )
        ),
        reverse=True,
    )

    for row in ranked:

        print(
            f"{row.get('source_name', '')}"
        )

        print(
            f"  Source Type                  : "
            f"{row.get('source_type')}"
        )

        print(
            f"  Asset Class                  : "
            f"{row.get('asset_class')}"
        )

        print(
            f"  MPD Eligible                 : "
            f"{row.get('mpd_eligible')}"
        )

        print(
            f"  Destination                  : "
            f"{row.get('destination')}"
        )

        print(
            f"  Source Role                  : "
            f"{row.get('source_role')}"
        )

        print(
            f"  Rows                         : "
            f"{int(row.get('rows', 0) or 0):,}"
        )

        print(
            f"  Unique Symbols               : "
            f"{int(row.get('unique_symbols', 0) or 0):,}"
        )

        print(
            f"  Security Master Matches      : "
            f"{int(row.get('security_master_matches', 0) or 0):,}"
        )

        print(
            f"  Coverage                     : "
            f"{row.get('coverage_percent', 0)}%"
        )

        print(
            f"  OHLC                         : "
            f"{row.get('has_ohlc', False)}"
        )

        print(
            f"  Volume                       : "
            f"{row.get('has_volume', False)}"
        )

        print(
            f"  First Session                : "
            f"{row.get('first_session')}"
        )

        print(
            f"  Last Session                 : "
            f"{row.get('last_session')}"
        )

        print(
            f"  Future Rows                  : "
            f"{row.get('future_rows', 0)}"
        )

        print(
            f"  Suitability                  : "
            f"{row.get('suitability')}"
        )

        print(
            f"  Quality Score                : "
            f"{row.get('quality_score')}"
        )

        print(
            f"  Canonical MPD Score          : "
            f"{row.get('canonical_score')}"
        )

        print("-" * 100)

    print()
    print("CANONICAL MARKET PRICE DECISION")
    print("-" * 100)

    print(
        f"Recommendation Status          : "
        f"{summary['recommendation_status']}"
    )

    print(
        f"Recommended Source             : "
        f"{summary['recommended_source']}"
    )

    print(
        f"Recommended Asset Class        : "
        f"{summary['recommended_asset_class']}"
    )

    print(
        f"Recommended Canonical Score    : "
        f"{summary['recommended_canonical_score']}"
    )

    print(
        f"Reason                         : "
        f"{summary['recommendation_reason']}"
    )

    print("-" * 100)

    print(
        "Frozen Historical Database     : READ ONLY / UNTOUCHED"
    )

    print(
        "Security Master                : READ ONLY / UNCHANGED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Futures Source Policy          : FID ONLY / NEVER CANONICAL MPD"
    )

    print(
        "Options Source Policy          : OID ONLY / NEVER CANONICAL MPD"
    )

    print(
        "Derived Snapshot Policy        : NEVER CANONICAL MPD"
    )

    print(
        f"Audit CSV                      : "
        f"{AUDIT_CSV}"
    )

    print(
        f"Summary JSON                   : "
        f"{SUMMARY_JSON}"
    )

    print("-" * 100)

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_audit()

        write_outputs(
            summary
        )

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        print("=" * 100)
        print("AQSD MARKET PRICE SOURCE AUDITOR")
        print("=" * 100)

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "Source Modification            : NONE"
        )

        print(
            "Frozen Historical Database     : UNTOUCHED"
        )

        print("=" * 100)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()