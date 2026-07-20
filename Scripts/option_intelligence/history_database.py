"""
AQSD
OPTION INTELLIGENCE HISTORY DATABASE

Module: history_database.py
Version: 1.0
Author: AQSD

Purpose:
Store each BANKNIFTY Option Intelligence snapshot in one SQLite database.

Data source:
Output/DECISION/BANKNIFTY_LIVE_DECISION_INTELLIGENCE.json

Database:
Output/Database/AQSD_Option_Intelligence.db

Features:
- Creates the SQLite database automatically
- Creates the history table automatically
- Reads the latest Decision Intelligence JSON
- Extracts important analytics safely from nested JSON
- Prevents duplicate inserts for the same source timestamp
- Stores one compact intraday history record per refresh
- Supports database status and recent-row display
- Analytics only. No order placement

Examples:
    python -m Scripts.option_intelligence.history_database --save
    python -m Scripts.option_intelligence.history_database --status
    python -m Scripts.option_intelligence.history_database --recent 10
"""

from __future__ import annotations

import argparse
import json
import sqlite3

from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DECISION_JSON_FILE = (
    BASE_DIR
    / "Output"
    / "DECISION"
    / "BANKNIFTY_LIVE_DECISION_INTELLIGENCE.json"
)

DATABASE_DIR = (
    BASE_DIR
    / "Output"
    / "Database"
)

DATABASE_FILE = (
    DATABASE_DIR
    / "AQSD_Option_Intelligence.db"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

TABLE_NAME = "option_intelligence_history"

SCHEMA_VERSION = 1


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(frozen=True)
class HistorySnapshot:
    """
    One stored Option Intelligence snapshot.

    All numeric values are stored as REAL in SQLite.
    Text values are stored as TEXT.
    """

    source_timestamp: str
    recorded_at: str
    underlying: str | None

    spot_price: float | None
    atm_strike: float | None

    oi_pcr: float | None
    change_oi_pcr: float | None
    modified_pcr: float | None
    volume_pcr: float | None
    atm_zone_pcr: float | None
    pcr_trend: str | None

    max_pain_strike: float | None
    pinning_probability: float | None

    call_wall: float | None
    put_wall: float | None
    fresh_call_wall: float | None
    fresh_put_wall: float | None
    wall_shift: str | None

    atm_iv: float | None
    historical_volatility: float | None
    iv_rank: float | None
    iv_percentile: float | None
    volatility_regime: str | None

    bullish_probability: float | None
    bearish_probability: float | None
    continuation_probability: float | None
    reversal_probability: float | None

    final_decision: str | None
    decision_bias: str | None
    confidence_score: float | None
    trade_grade: str | None
    trade_quality: str | None
    market_regime: str | None
    risk_level: str | None

    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    target_one: float | None
    target_two: float | None

    source_file_modified_at: str | None


# ============================================================
# JSON HELPERS
# ============================================================

def load_json_file(
    file_path: Path,
) -> dict[str, Any]:
    """Read a JSON dictionary from disk."""

    if not file_path.exists():
        raise FileNotFoundError(
            "Decision Intelligence JSON was not found:\n"
            f"{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        value = json.load(
            handle
        )

    if not isinstance(value, dict):
        raise ValueError(
            "Decision Intelligence JSON must contain a dictionary."
        )

    return value


def recursive_find(
    value: Any,
    key_name: str,
) -> Any:
    """
    Find the first matching key anywhere inside nested dictionaries/lists.

    Key comparison is case-insensitive and ignores surrounding spaces.
    """

    target = (
        str(key_name)
        .strip()
        .lower()
    )

    if isinstance(value, dict):
        for key, item in value.items():
            if (
                str(key)
                .strip()
                .lower()
                == target
            ):
                return item

        for item in value.values():
            found = recursive_find(
                item,
                key_name,
            )

            if found is not None:
                return found

    elif isinstance(value, list):
        for item in value:
            found = recursive_find(
                item,
                key_name,
            )

            if found is not None:
                return found

    return None


def first_available(
    data: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first available value from alternative key names."""

    for key in keys:
        value = recursive_find(
            data,
            key,
        )

        if value is not None:
            return value

    return default


def to_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float safely.

    Handles commas and percentage signs in text values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return float(
            value
        )

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(
            value
        )

    text = (
        str(value)
        .strip()
        .replace(",", "")
        .replace("%", "")
    )

    if not text:
        return None

    if text.upper() in {
        "N/A",
        "NA",
        "NONE",
        "NULL",
        "-",
        "--",
    }:
        return None

    try:
        return float(
            text
        )
    except ValueError:
        return None


def to_text(
    value: Any,
) -> str | None:
    """Convert a value to clean text safely."""

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    return text


def normalize_timestamp(
    value: Any,
) -> str:
    """
    Normalize the source timestamp.

    If the source JSON does not contain a timestamp, use the current
    local timestamp.
    """

    text = to_text(
        value
    )

    if text:
        return text

    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


# ============================================================
# SNAPSHOT EXTRACTION
# ============================================================

def build_snapshot(
    data: dict[str, Any],
) -> HistorySnapshot:
    """Extract one robust history snapshot from nested Decision JSON."""

    try:
        modified_at = (
            datetime.fromtimestamp(
                DECISION_JSON_FILE.stat().st_mtime
            )
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        )
    except OSError:
        modified_at = None

    source_timestamp = normalize_timestamp(
        first_available(
            data,
            "timestamp",
            "generated_at",
            "updated_at",
            "fetched_at",
            "calculated_at",
        )
    )

    recorded_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    return HistorySnapshot(
        source_timestamp=source_timestamp,
        recorded_at=recorded_at,
        underlying=to_text(
            first_available(
                data,
                "underlying",
                "symbol",
                default="BANKNIFTY",
            )
        ),

        spot_price=to_float(
            first_available(
                data,
                "spot_price",
                "spot",
                "underlying_price",
            )
        ),
        atm_strike=to_float(
            first_available(
                data,
                "atm_strike",
                "atm",
            )
        ),

        oi_pcr=to_float(
            first_available(
                data,
                "oi_pcr",
                "pcr_oi",
            )
        ),
        change_oi_pcr=to_float(
            first_available(
                data,
                "change_oi_pcr",
                "change_in_oi_pcr",
                "coi_pcr",
            )
        ),
        modified_pcr=to_float(
            first_available(
                data,
                "modified_pcr",
            )
        ),
        volume_pcr=to_float(
            first_available(
                data,
                "volume_pcr",
                "vol_pcr",
            )
        ),
        atm_zone_pcr=to_float(
            first_available(
                data,
                "atm_zone_pcr",
                "atm_pcr",
            )
        ),
        pcr_trend=to_text(
            first_available(
                data,
                "pcr_trend",
            )
        ),

        max_pain_strike=to_float(
            first_available(
                data,
                "max_pain_strike",
                "max_pain",
            )
        ),
        pinning_probability=to_float(
            first_available(
                data,
                "pinning_probability",
            )
        ),

        call_wall=to_float(
            first_available(
                data,
                "call_wall",
                "positional_call_wall",
            )
        ),
        put_wall=to_float(
            first_available(
                data,
                "put_wall",
                "positional_put_wall",
            )
        ),
        fresh_call_wall=to_float(
            first_available(
                data,
                "fresh_call_wall",
                "change_oi_call_wall",
            )
        ),
        fresh_put_wall=to_float(
            first_available(
                data,
                "fresh_put_wall",
                "change_oi_put_wall",
            )
        ),
        wall_shift=to_text(
            first_available(
                data,
                "combined_wall_shift",
                "wall_shift",
            )
        ),

        atm_iv=to_float(
            first_available(
                data,
                "atm_iv",
            )
        ),
        historical_volatility=to_float(
            first_available(
                data,
                "historical_volatility",
                "hv",
            )
        ),
        iv_rank=to_float(
            first_available(
                data,
                "iv_rank",
                "ivr",
            )
        ),
        iv_percentile=to_float(
            first_available(
                data,
                "iv_percentile",
                "ivp",
            )
        ),
        volatility_regime=to_text(
            first_available(
                data,
                "volatility_regime",
                "iv_regime",
            )
        ),

        bullish_probability=to_float(
            first_available(
                data,
                "bullish_probability",
                "bullish",
                "probability_up",
            )
        ),
        bearish_probability=to_float(
            first_available(
                data,
                "bearish_probability",
                "bearish",
                "probability_down",
            )
        ),
        continuation_probability=to_float(
            first_available(
                data,
                "continuation_probability",
                "continuation",
            )
        ),
        reversal_probability=to_float(
            first_available(
                data,
                "reversal_probability",
                "reversal",
            )
        ),

        final_decision=to_text(
            first_available(
                data,
                "final_decision",
                "suggested_action",
                "decision",
            )
        ),
        decision_bias=to_text(
            first_available(
                data,
                "decision_bias",
                "directional_bias",
                "bias",
            )
        ),
        confidence_score=to_float(
            first_available(
                data,
                "confidence_score",
                "confidence",
            )
        ),
        trade_grade=to_text(
            first_available(
                data,
                "trade_grade",
                "grade",
            )
        ),
        trade_quality=to_text(
            first_available(
                data,
                "trade_quality",
                "quality",
            )
        ),
        market_regime=to_text(
            first_available(
                data,
                "market_regime",
            )
        ),
        risk_level=to_text(
            first_available(
                data,
                "risk_level",
            )
        ),

        entry_low=to_float(
            first_available(
                data,
                "entry_low",
            )
        ),
        entry_high=to_float(
            first_available(
                data,
                "entry_high",
            )
        ),
        stop_loss=to_float(
            first_available(
                data,
                "stop_loss",
            )
        ),
        target_one=to_float(
            first_available(
                data,
                "target_one",
                "target_1",
            )
        ),
        target_two=to_float(
            first_available(
                data,
                "target_two",
                "target_2",
            )
        ),

        source_file_modified_at=modified_at,
    )


# ============================================================
# DATABASE HELPERS
# ============================================================

def connect_database() -> sqlite3.Connection:
    """Create the database folder and return a configured connection."""

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_FILE,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )
    connection.execute(
        "PRAGMA synchronous=NORMAL"
    )
    connection.execute(
        "PRAGMA foreign_keys=ON"
    )

    return connection


def create_database_schema(
    connection: sqlite3.Connection,
) -> None:
    """Create metadata and history tables when missing."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS database_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source_timestamp TEXT NOT NULL UNIQUE,
            recorded_at TEXT NOT NULL,
            underlying TEXT,

            spot_price REAL,
            atm_strike REAL,

            oi_pcr REAL,
            change_oi_pcr REAL,
            modified_pcr REAL,
            volume_pcr REAL,
            atm_zone_pcr REAL,
            pcr_trend TEXT,

            max_pain_strike REAL,
            pinning_probability REAL,

            call_wall REAL,
            put_wall REAL,
            fresh_call_wall REAL,
            fresh_put_wall REAL,
            wall_shift TEXT,

            atm_iv REAL,
            historical_volatility REAL,
            iv_rank REAL,
            iv_percentile REAL,
            volatility_regime TEXT,

            bullish_probability REAL,
            bearish_probability REAL,
            continuation_probability REAL,
            reversal_probability REAL,

            final_decision TEXT,
            decision_bias TEXT,
            confidence_score REAL,
            trade_grade TEXT,
            trade_quality TEXT,
            market_regime TEXT,
            risk_level TEXT,

            entry_low REAL,
            entry_high REAL,
            stop_loss REAL,
            target_one REAL,
            target_two REAL,

            source_file_modified_at TEXT
        )
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TABLE_NAME}_recorded_at
        ON {TABLE_NAME}(recorded_at)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TABLE_NAME}_underlying
        ON {TABLE_NAME}(underlying)
        """
    )

    connection.execute(
        """
        INSERT INTO database_metadata (
            key,
            value
        )
        VALUES (
            'schema_version',
            ?
        )
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value
        """,
        (
            str(SCHEMA_VERSION),
        ),
    )

    connection.commit()


def snapshot_columns() -> list[str]:
    """Return HistorySnapshot field names in database order."""

    return [
        field.name
        for field in fields(
            HistorySnapshot
        )
    ]


def snapshot_values(
    snapshot: HistorySnapshot,
) -> list[Any]:
    """Return HistorySnapshot values in database order."""

    return [
        getattr(
            snapshot,
            column,
        )
        for column in snapshot_columns()
    ]


def save_snapshot(
    connection: sqlite3.Connection,
    snapshot: HistorySnapshot,
) -> bool:
    """
    Insert one history snapshot.

    Returns:
        True when a new row was inserted.
        False when the source timestamp already existed.
    """

    columns = snapshot_columns()

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    column_sql = ", ".join(
        columns
    )

    cursor = connection.execute(
        f"""
        INSERT OR IGNORE INTO {TABLE_NAME} (
            {column_sql}
        )
        VALUES (
            {placeholders}
        )
        """,
        snapshot_values(
            snapshot
        ),
    )

    connection.commit()

    return cursor.rowcount == 1


def count_rows(
    connection: sqlite3.Connection,
) -> int:
    """Return the number of stored history rows."""

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS row_count
        FROM {TABLE_NAME}
        """
    ).fetchone()

    return int(
        row["row_count"]
    )


def database_size_bytes() -> int:
    """Return SQLite file size safely."""

    try:
        return DATABASE_FILE.stat().st_size
    except OSError:
        return 0


def human_size(
    size_bytes: int,
) -> str:
    """Convert bytes to a readable storage size."""

    value = float(
        size_bytes
    )

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ):
        if value < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}"

        value /= 1024.0

    return f"{size_bytes} B"


# ============================================================
# DISPLAY HELPERS
# ============================================================

def display_snapshot(
    snapshot: HistorySnapshot,
) -> None:
    """Print the important fields of one extracted snapshot."""

    print()
    print("=" * 78)
    print("AQSD OPTION INTELLIGENCE HISTORY SNAPSHOT")
    print("=" * 78)

    rows = (
        ("Timestamp", snapshot.source_timestamp),
        ("Underlying", snapshot.underlying),
        ("Spot", snapshot.spot_price),
        ("ATM", snapshot.atm_strike),
        ("OI PCR", snapshot.oi_pcr),
        ("Change-OI PCR", snapshot.change_oi_pcr),
        ("Modified PCR", snapshot.modified_pcr),
        ("Volume PCR", snapshot.volume_pcr),
        ("Max Pain", snapshot.max_pain_strike),
        ("Call Wall", snapshot.call_wall),
        ("Put Wall", snapshot.put_wall),
        ("ATM IV", snapshot.atm_iv),
        ("HV", snapshot.historical_volatility),
        ("IV Rank", snapshot.iv_rank),
        ("IV Percentile", snapshot.iv_percentile),
        ("Bullish Probability", snapshot.bullish_probability),
        ("Bearish Probability", snapshot.bearish_probability),
        ("Final Decision", snapshot.final_decision),
        ("Confidence", snapshot.confidence_score),
        ("Market Regime", snapshot.market_regime),
    )

    for label, value in rows:
        print(
            f"{label:<24}: {value}"
        )


def display_database_status(
    connection: sqlite3.Connection,
) -> None:
    """Print database path, row count and storage size."""

    print()
    print("=" * 78)
    print("AQSD OPTION INTELLIGENCE DATABASE STATUS")
    print("=" * 78)
    print(f"Database : {DATABASE_FILE}")
    print(f"Rows     : {count_rows(connection)}")
    print(
        f"Size     : {human_size(database_size_bytes())}"
    )


def display_recent_rows(
    connection: sqlite3.Connection,
    limit: int,
) -> None:
    """Print recent stored history rows."""

    rows = connection.execute(
        f"""
        SELECT
            id,
            source_timestamp,
            spot_price,
            oi_pcr,
            modified_pcr,
            max_pain_strike,
            call_wall,
            put_wall,
            atm_iv,
            final_decision,
            confidence_score,
            market_regime
        FROM {TABLE_NAME}
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            limit,
        ),
    ).fetchall()

    print()
    print("=" * 126)
    print(f"RECENT {len(rows)} OPTION INTELLIGENCE HISTORY ROW(S)")
    print("=" * 126)

    if not rows:
        print("No history rows have been stored yet.")
        return

    header = (
        f"{'ID':>5}  "
        f"{'TIMESTAMP':<25}  "
        f"{'SPOT':>10}  "
        f"{'OI PCR':>7}  "
        f"{'MOD PCR':>8}  "
        f"{'MAX PAIN':>9}  "
        f"{'CALL WALL':>10}  "
        f"{'PUT WALL':>9}  "
        f"{'ATM IV':>7}  "
        f"{'DECISION':<14}  "
        f"{'CONF':>7}"
    )

    print(
        header
    )
    print(
        "-" * len(header)
    )

    for row in rows:
        print(
            f"{row['id']:>5}  "
            f"{str(row['source_timestamp']):<25.25}  "
            f"{format_optional(row['spot_price'], 2):>10}  "
            f"{format_optional(row['oi_pcr'], 3):>7}  "
            f"{format_optional(row['modified_pcr'], 3):>8}  "
            f"{format_optional(row['max_pain_strike'], 0):>9}  "
            f"{format_optional(row['call_wall'], 0):>10}  "
            f"{format_optional(row['put_wall'], 0):>9}  "
            f"{format_optional(row['atm_iv'], 2):>7}  "
            f"{str(row['final_decision'] or 'N/A'):<14.14}  "
            f"{format_optional(row['confidence_score'], 1):>7}"
        )


def format_optional(
    value: Any,
    decimals: int,
) -> str:
    """Format an optional numeric value for terminal display."""

    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{decimals}f}"
    except (
        TypeError,
        ValueError,
    ):
        return str(
            value
        )


# ============================================================
# COMMAND-LINE INTERFACE
# ============================================================

def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=(
            "Store and inspect AQSD Option Intelligence history "
            "in SQLite."
        )
    )

    action_group = parser.add_mutually_exclusive_group(
        required=False
    )

    action_group.add_argument(
        "--save",
        action="store_true",
        help="Save the latest Decision Intelligence JSON snapshot.",
    )

    action_group.add_argument(
        "--status",
        action="store_true",
        help="Show database status.",
    )

    action_group.add_argument(
        "--recent",
        type=int,
        metavar="COUNT",
        help="Display the most recent COUNT history rows.",
    )

    action_group.add_argument(
        "--preview",
        action="store_true",
        help="Extract and display the latest snapshot without saving.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the requested database operation."""

    args = parse_arguments()

    with connect_database() as connection:
        create_database_schema(
            connection
        )

        if args.status:
            display_database_status(
                connection
            )
            return

        if args.recent is not None:
            if args.recent < 1:
                raise SystemExit(
                    "--recent must be at least 1."
                )

            display_recent_rows(
                connection,
                args.recent,
            )
            return

        data = load_json_file(
            DECISION_JSON_FILE
        )

        snapshot = build_snapshot(
            data
        )

        if args.preview:
            display_snapshot(
                snapshot
            )
            return

        inserted = save_snapshot(
            connection,
            snapshot,
        )

        display_snapshot(
            snapshot
        )

        print()
        print("=" * 78)

        if inserted:
            print(
                "HISTORY SNAPSHOT SAVED SUCCESSFULLY"
            )
        else:
            print(
                "DUPLICATE SOURCE TIMESTAMP — NO NEW ROW INSERTED"
            )

        print("=" * 78)
        print(f"Database : {DATABASE_FILE}")
        print(f"Rows     : {count_rows(connection)}")
        print(
            f"Size     : {human_size(database_size_bytes())}"
        )


if __name__ == "__main__":
    main()
