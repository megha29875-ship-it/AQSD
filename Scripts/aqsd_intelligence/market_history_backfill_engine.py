"""
AQSD
Market History Backfill Engine

Module : MHB-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Build AQSD historical Market Intelligence safely for a configurable
number of previous trading sessions.

Default backfill target:
60 trading sessions.

CRITICAL SAFETY PRINCIPLE
-------------------------
Historical dates must NEVER use current/live market data.

This engine therefore separates:

1. Backfill planning
2. Historical-source validation
3. Historical execution
4. Audit reporting

A date is processed only when historical evidence for that exact date
is available and passes validation.

No historical row is fabricated.

No current Option Chain / Futures snapshot is substituted for an
older trading date.

Architecture
------------
Trading Calendar
      ↓
Backfill Planner
      ↓
Historical Source Validation
      ↓
Historical Intelligence Execution
      ↓
Market Master Decision
      ↓
Market History Recorder
      ↓
Audit Report

Initial Stage
-------------
At this stage the engine is intentionally conservative.

It can:

- Build the previous 60-session backfill plan.
- Detect existing Market History dates.
- Detect dates already completed.
- Validate historical evidence folders.
- Refuse unsafe dates.
- Produce CSV/JSON audit reports.
- Resume interrupted backfills.

Historical source adapters can then be connected systematically.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MHB-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DATA_DIR: Final[Path] = BASE_DIR / "Data"
OUTPUT_DIR: Final[Path] = BASE_DIR / "Output"

MARKET_HISTORY_DIR: Final[Path] = (
    OUTPUT_DIR
    / "Market_History"
)

HISTORY_FILE: Final[Path] = (
    MARKET_HISTORY_DIR
    / "market_intelligence_history.csv"
)

BACKFILL_DIR: Final[Path] = (
    MARKET_HISTORY_DIR
    / "Backfill"
)

HISTORICAL_SOURCE_DIR: Final[Path] = (
    DATA_DIR
    / "Historical"
)

TRADING_CALENDAR_FILE: Final[Path] = (
    DATA_DIR
    / "NSE_Trading_Calendar.csv"
)

PLAN_FILE: Final[Path] = (
    BACKFILL_DIR
    / "market_history_backfill_plan.csv"
)

AUDIT_FILE: Final[Path] = (
    BACKFILL_DIR
    / "market_history_backfill_audit.csv"
)

SUMMARY_FILE: Final[Path] = (
    BACKFILL_DIR
    / "market_history_backfill_summary.json"
)

DEFAULT_SESSIONS: Final[int] = 60

MAX_SESSIONS: Final[int] = 2000


# ==========================================================
# HISTORICAL SOURCE REQUIREMENTS
# ==========================================================
#
# These files are deliberately date-specific.
#
# Example:
#
# Data/Historical/2026-07-31/
#     participant.csv
#     breadth.csv
#     sector.csv
#     futures.csv
#     options.csv
#     market_structure.csv
#
# We will later connect AQSD's historical acquisition modules
# to populate these automatically.
# ==========================================================

REQUIRED_HISTORICAL_SOURCES: Final[
    tuple[str, ...]
] = (
    "participant.csv",
    "breadth.csv",
    "sector.csv",
    "futures.csv",
    "options.csv",
    "market_structure.csv",
)


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class SourceValidationResult:
    trade_date: str

    source_directory: str

    required_sources: int
    available_sources: int
    missing_sources: tuple[str, ...]

    safe_to_process: bool

    status: str


@dataclass(frozen=True)
class BackfillSession:
    trade_date: str

    already_recorded: bool

    source_validation: SourceValidationResult

    action: str

    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def ensure_directories() -> None:
    """
    Create required Backfill directories.
    """

    MARKET_HISTORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKFILL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    HISTORICAL_SOURCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# EXISTING HISTORY
# ==========================================================

def load_existing_history_dates() -> set[str]:
    """
    Return already-recorded Market History dates.
    """

    if not HISTORY_FILE.exists():
        return set()

    frame = pd.read_csv(
        HISTORY_FILE,
        low_memory=False,
    )

    if "analysis_date" not in frame.columns:
        return set()

    dates = pd.to_datetime(
        frame["analysis_date"],
        errors="coerce",
    ).dropna()

    return {
        value.date().isoformat()
        for value in dates
    }


# ==========================================================
# TRADING CALENDAR
# ==========================================================

def load_calendar_dates() -> list[date]:
    """
    Load an explicit NSE trading calendar when available.

    Supported date-column names:

    trade_date
    Trade_Date
    date
    Date
    trading_date
    Trading_Date
    """

    if not TRADING_CALENDAR_FILE.exists():
        return []

    frame = pd.read_csv(
        TRADING_CALENDAR_FILE,
        low_memory=False,
    )

    candidate_columns = (
        "trade_date",
        "Trade_Date",
        "date",
        "Date",
        "trading_date",
        "Trading_Date",
    )

    selected_column: str | None = None

    for column in candidate_columns:
        if column in frame.columns:
            selected_column = column
            break

    if selected_column is None:
        raise RuntimeError(
            "NSE Trading Calendar exists but no recognized "
            "date column was found."
        )

    parsed = pd.to_datetime(
        frame[selected_column],
        errors="coerce",
    ).dropna()

    unique_dates = sorted(
        {
            value.date()
            for value in parsed
        }
    )

    return unique_dates


def weekday_fallback_dates(
    *,
    end_date: date,
    sessions: int,
) -> list[date]:
    """
    Build weekday dates only.

    IMPORTANT:
    This is NOT guaranteed to represent actual NSE sessions because
    exchange holidays are not known.

    It is therefore used for planning only.
    """

    dates: list[date] = []

    cursor = end_date

    while len(dates) < sessions:
        if cursor.weekday() < 5:
            dates.append(
                cursor
            )

        cursor -= timedelta(
            days=1
        )

    dates.sort()

    return dates


def resolve_trading_sessions(
    *,
    sessions: int,
    end_date: date,
) -> tuple[list[date], str]:
    """
    Resolve the requested historical session dates.
    """

    sessions = max(
        1,
        min(
            int(sessions),
            MAX_SESSIONS,
        ),
    )

    calendar_dates = load_calendar_dates()

    if calendar_dates:
        eligible = [
            value
            for value in calendar_dates
            if value <= end_date
        ]

        if len(eligible) < sessions:
            raise RuntimeError(
                "NSE Trading Calendar does not contain enough "
                f"sessions. Required={sessions}; "
                f"Available={len(eligible)}."
            )

        return (
            eligible[-sessions:],
            "NSE TRADING CALENDAR",
        )

    return (
        weekday_fallback_dates(
            end_date=end_date,
            sessions=sessions,
        ),
        "WEEKDAY FALLBACK - PLANNING ONLY",
    )


# ==========================================================
# HISTORICAL SOURCE VALIDATION
# ==========================================================

SOURCE_FILE_MAP: Final[
    dict[str, str]
] = {
    "participant": "participant.csv",
    "breadth": "breadth.csv",
    "sector": "sector.csv",
    "futures": "futures.csv",
    "options": "options.csv",
    "market_structure": "market_structure.csv",
}


def historical_date_directory(
    trade_date: date,
) -> Path:
    """
    Return the historical evidence directory
    for one trading session.
    """

    return (
        HISTORICAL_SOURCE_DIR
        / trade_date.isoformat()
    )


def source_file_is_ready(
    source_file: Path,
) -> bool:
    """
    Validate one historical source file.

    A source is considered ready only when:

    - the file exists
    - it is a normal file
    - it is non-empty
    """

    try:
        return (
            source_file.exists()
            and source_file.is_file()
            and source_file.stat().st_size > 0
        )

    except OSError:
        return False


def inspect_historical_sources(
    trade_date: date,
) -> dict[str, bool]:
    """
    Inspect each historical source family separately.
    """

    directory = historical_date_directory(
        trade_date
    )

    availability: dict[
        str,
        bool,
    ] = {}

    for (
        source_name,
        filename,
    ) in SOURCE_FILE_MAP.items():

        source_file = (
            directory
            / filename
        )

        availability[
            source_name
        ] = source_file_is_ready(
            source_file
        )

    return availability


def validate_historical_sources(
    trade_date: date,
) -> SourceValidationResult:
    """
    Validate all historical source families for one date.

    MHB-001 requires all six sources before a full historical
    Market Master Decision is allowed to run.

    Partial availability is still recorded diagnostically.
    """

    directory = historical_date_directory(
        trade_date
    )

    availability = inspect_historical_sources(
        trade_date
    )

    missing_sources: list[str] = []

    available_sources = 0

    for (
        source_name,
        filename,
    ) in SOURCE_FILE_MAP.items():

        if availability.get(
            source_name,
            False,
        ):
            available_sources += 1

        else:
            missing_sources.append(
                filename
            )

    required_sources = len(
        SOURCE_FILE_MAP
    )

    safe_to_process = (
        available_sources
        == required_sources
    )

    return SourceValidationResult(
        trade_date=(
            trade_date.isoformat()
        ),

        source_directory=str(
            directory
        ),

        required_sources=(
            required_sources
        ),

        available_sources=(
            available_sources
        ),

        missing_sources=tuple(
            missing_sources
        ),

        safe_to_process=(
            safe_to_process
        ),

        status=(
            "READY"
            if safe_to_process
            else (
                f"PARTIAL SOURCES "
                f"{available_sources}/"
                f"{required_sources}"
            )
        ),
    )

# ==========================================================
# BACKFILL PLAN
# ==========================================================

def build_backfill_plan(
    *,
    sessions: int = DEFAULT_SESSIONS,
    end_date: date,
) -> tuple[
    list[BackfillSession],
    str,
]:
    """
    Build a safe historical backfill plan.
    """

    existing_dates = (
        load_existing_history_dates()
    )

    (
        trading_dates,
        calendar_source,
    ) = resolve_trading_sessions(
        sessions=sessions,
        end_date=end_date,
    )

    plan: list[BackfillSession] = []

    for trade_date in trading_dates:
        trade_date_text = (
            trade_date.isoformat()
        )

        already_recorded = (
            trade_date_text
            in existing_dates
        )

        validation = (
            validate_historical_sources(
                trade_date
            )
        )

        if already_recorded:
            action = "SKIP"
            status = "ALREADY RECORDED"

        elif validation.safe_to_process:
            action = "PROCESS"
            status = "READY"

        else:
            action = "WAIT"
            status = (
                "HISTORICAL SOURCES REQUIRED"
            )

        plan.append(
            BackfillSession(
                trade_date=trade_date_text,

                already_recorded=(
                    already_recorded
                ),

                source_validation=(
                    validation
                ),

                action=action,

                status=status,
            )
        )

    return (
        plan,
        calendar_source,
    )


# ==========================================================
# PLAN OUTPUT
# ==========================================================

def plan_to_frame(
    plan: list[BackfillSession],
) -> pd.DataFrame:
    """
    Convert the Backfill plan into a detailed DataFrame.

    Each historical source family is shown separately.
    """

    rows: list[
        dict[str, object]
    ] = []

    for session in plan:
        validation = (
            session.source_validation
        )

        trade_date = parse_date(
            session.trade_date
        )

        availability = inspect_historical_sources(
            trade_date
        )

        rows.append(
            {
                "trade_date": (
                    session.trade_date
                ),

                "already_recorded": (
                    session.already_recorded
                ),

                "participant_ready": (
                    availability.get(
                        "participant",
                        False,
                    )
                ),

                "breadth_ready": (
                    availability.get(
                        "breadth",
                        False,
                    )
                ),

                "sector_ready": (
                    availability.get(
                        "sector",
                        False,
                    )
                ),

                "futures_ready": (
                    availability.get(
                        "futures",
                        False,
                    )
                ),

                "options_ready": (
                    availability.get(
                        "options",
                        False,
                    )
                ),

                "market_structure_ready": (
                    availability.get(
                        "market_structure",
                        False,
                    )
                ),

                "required_sources": (
                    validation.required_sources
                ),

                "available_sources": (
                    validation.available_sources
                ),

                "missing_sources": (
                    " | ".join(
                        validation.missing_sources
                    )
                ),

                "safe_to_process": (
                    validation.safe_to_process
                ),

                "action": (
                    session.action
                ),

                "status": (
                    session.status
                ),

                "source_directory": (
                    validation.source_directory
                ),
            }
        )

    return pd.DataFrame(
        rows
    )

def save_plan(
    plan: list[BackfillSession],
) -> Path:
    """
    Save the Backfill plan.
    """

    ensure_directories()

    frame = plan_to_frame(
        plan
    )

    frame.to_csv(
        PLAN_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return PLAN_FILE


# ==========================================================
# AUDIT
# ==========================================================

def load_audit() -> pd.DataFrame:
    """
    Load existing Backfill audit.
    """

    if not AUDIT_FILE.exists():
        return pd.DataFrame()

    return pd.read_csv(
        AUDIT_FILE,
        low_memory=False,
    )


def append_audit(
    *,
    trade_date: str,
    action: str,
    status: str,
    message: str,
) -> None:
    """
    Append one audit event.
    """

    ensure_directories()

    existing = load_audit()

    row = pd.DataFrame(
        [
            {
                "logged_at": (
                    datetime.now()
                    .isoformat(
                        timespec="seconds"
                    )
                ),

                "trade_date": trade_date,

                "action": action,

                "status": status,

                "message": message,
            }
        ]
    )

    combined = pd.concat(
        [
            existing,
            row,
        ],
        ignore_index=True,
    )

    combined.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )


# ==========================================================
# HISTORICAL EXECUTION PLACEHOLDER
# ==========================================================

def execute_historical_session(
    session: BackfillSession,
) -> str:
    """
    Execute one historical session.

    SAFETY:
    Historical execution is deliberately blocked until AQSD's
    date-specific source adapters are connected.

    We must NOT call the current Master Decision Engine here yet,
    because some present-day intelligence modules still read latest
    Option/Futures files.

    Once historical adapters are completed, this function becomes
    the controlled execution gateway.
    """

    if session.already_recorded:
        return "ALREADY RECORDED"

    if not session.source_validation.safe_to_process:
        return "HISTORICAL SOURCES INCOMPLETE"

    raise RuntimeError(
        "Historical evidence is complete, but MHB-001 execution "
        "is intentionally locked until AQSD historical source "
        "adapters are connected. This prevents accidental use "
        "of current/live data on historical dates."
    )


# ==========================================================
# BACKFILL RUNNER
# ==========================================================

def run_backfill(
    *,
    sessions: int,
    end_date: date,
) -> dict[str, object]:
    """
    Build the historical backfill plan and inspect
    date-specific source coverage safely.
    """

    (
        plan,
        calendar_source,
    ) = build_backfill_plan(
        sessions=sessions,
        end_date=end_date,
    )

    plan_file = save_plan(
        plan
    )

    counts = {
        "total": len(plan),
        "already_recorded": 0,

        "participant_ready": 0,
        "breadth_ready": 0,
        "sector_ready": 0,
        "futures_ready": 0,
        "options_ready": 0,
        "market_structure_ready": 0,

        "fully_ready": 0,
        "waiting": 0,
        "processed": 0,
        "failed": 0,
    }

    for session in plan:

        trade_date_object = parse_date(
            session.trade_date
        )

        availability = inspect_historical_sources(
            trade_date_object
        )

        # --------------------------------------------------
        # COUNT SOURCE COVERAGE
        # --------------------------------------------------

        for source_name in (
            "participant",
            "breadth",
            "sector",
            "futures",
            "options",
            "market_structure",
        ):
            if availability.get(
                source_name,
                False,
            ):
                counts[
                    f"{source_name}_ready"
                ] += 1

        # --------------------------------------------------
        # ALREADY RECORDED
        # --------------------------------------------------

        if session.already_recorded:

            counts[
                "already_recorded"
            ] += 1

            append_audit(
                trade_date=(
                    session.trade_date
                ),
                action="SKIP",
                status="ALREADY RECORDED",
                message=(
                    "Existing Market History "
                    "record preserved."
                ),
            )

            continue

        # --------------------------------------------------
        # PARTIAL / MISSING SOURCES
        # --------------------------------------------------

        if not (
            session
            .source_validation
            .safe_to_process
        ):

            counts[
                "waiting"
            ] += 1

            available_count = (
                session
                .source_validation
                .available_sources
            )

            required_count = (
                session
                .source_validation
                .required_sources
            )

            missing_text = ", ".join(
                session
                .source_validation
                .missing_sources
            )

            append_audit(
                trade_date=(
                    session.trade_date
                ),
                action="WAIT",
                status=(
                    f"PARTIAL SOURCES "
                    f"{available_count}/"
                    f"{required_count}"
                ),
                message=(
                    "Missing: "
                    + missing_text
                ),
            )

            continue

        # --------------------------------------------------
        # FULLY READY
        # --------------------------------------------------

        counts[
            "fully_ready"
        ] += 1

        try:
            result = execute_historical_session(
                session
            )

            counts[
                "processed"
            ] += 1

            append_audit(
                trade_date=(
                    session.trade_date
                ),
                action="PROCESS",
                status="SUCCESS",
                message=str(
                    result
                ),
            )

        except Exception as exc:

            counts[
                "failed"
            ] += 1

            append_audit(
                trade_date=(
                    session.trade_date
                ),
                action="PROCESS",
                status="BLOCKED",
                message=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

    # ======================================================
    # SUMMARY
    # ======================================================

    summary = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),

        "requested_sessions": (
            sessions
        ),

        "end_date": (
            end_date.isoformat()
        ),

        "calendar_source": (
            calendar_source
        ),

        "historical_source_root": str(
            HISTORICAL_SOURCE_DIR
        ),

        "plan_file": str(
            plan_file
        ),

        "audit_file": str(
            AUDIT_FILE
        ),

        **counts,

        "status": "SUCCESS",
    }

    ensure_directories()

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary

# ==========================================================
# DISPLAY
# ==========================================================

def display_summary(
    summary: dict[str, object],
) -> None:
    """
    Print Backfill summary.
    """

    print()
    print("=" * 100)
    print("AQSD MARKET HISTORY BACKFILL ENGINE")
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Requested Sessions        : "
        f"{summary['requested_sessions']}"
    )

    print(
        f"End Date                  : "
        f"{summary['end_date']}"
    )

    print(
        f"Calendar Source           : "
        f"{summary['calendar_source']}"
    )

    print("-" * 100)

    print("BACKFILL STATUS")
    print("-" * 100)

    print(
        f"Total Sessions            : "
        f"{summary['total']}"
    )

    print(
        f"Already Recorded          : "
        f"{summary['already_recorded']}"
    )

    print("-" * 100)

    print("HISTORICAL SOURCE COVERAGE")
    print("-" * 100)

    print(
        f"Participant Ready         : "
        f"{summary['participant_ready']}"
    )

    print(
        f"Breadth Ready             : "
        f"{summary['breadth_ready']}"
    )

    print(
        f"Sector Ready              : "
        f"{summary['sector_ready']}"
    )

    print(
        f"Futures Ready             : "
        f"{summary['futures_ready']}"
    )

    print(
        f"Options Ready             : "
        f"{summary['options_ready']}"
    )

    print(
        f"Market Structure Ready    : "
        f"{summary['market_structure_ready']}"
    )

    print("-" * 100)

    print(
        f"Fully Ready               : "
        f"{summary['fully_ready']}"
    )

    print(
        f"Waiting for Sources       : "
        f"{summary['waiting']}"
    )

    print(
        f"Processed                 : "
        f"{summary['processed']}"
    )

    print(
        f"Blocked / Failed          : "
        f"{summary['failed']}"
    )

    print("-" * 100)

    print("OUTPUT")
    print("-" * 100)

    print(
        f"Backfill Plan             : "
        f"{summary['plan_file']}"
    )

    print(
        f"Audit File                : "
        f"{summary['audit_file']}"
    )

    print(
        f"Historical Source Root    : "
        f"{summary['historical_source_root']}"
    )

    print("-" * 100)

    print(
        "IMPORTANT: MHB-001 does not substitute today's live "
        "Options/Futures data for historical dates."
    )

    print(
        "Historical execution will be enabled only after "
        "date-specific source adapters are connected."
    )

    print("-" * 100)

    print(
        f"Status                    : "
        f"{summary['status']}"
    )

    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Plan and validate AQSD historical "
            "Market Intelligence backfill."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
        help=(
            "Number of previous trading sessions. "
            "Default = 60."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Final backfill date in YYYY-MM-DD format. "
            "Defaults to today."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display configuration only."
        ),
    )

    return parser.parse_args()


def show_status() -> None:
    """
    Display Backfill configuration.
    """

    print()
    print("=" * 100)
    print("AQSD MARKET HISTORY BACKFILL STATUS")
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Default Sessions          : "
        f"{DEFAULT_SESSIONS}"
    )

    print(
        f"History File              : "
        f"{HISTORY_FILE}"
    )

    print(
        f"Historical Source Root    : "
        f"{HISTORICAL_SOURCE_DIR}"
    )

    print(
        f"NSE Trading Calendar      : "
        f"{TRADING_CALENDAR_FILE}"
    )

    print(
        f"Calendar Exists           : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )

    print("=" * 100)


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = (
        parse_arguments()
    )

    if arguments.status:
        show_status()
        return

    sessions = max(
        1,
        min(
            int(
                arguments.sessions
            ),
            MAX_SESSIONS,
        ),
    )

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else date.today()
    )

    ensure_directories()

    try:
        summary = run_backfill(
            sessions=sessions,
            end_date=end_date,
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print(
            "AQSD MARKET HISTORY BACKFILL ENGINE"
        )
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 100)

        raise SystemExit(
            1
        ) from exc

    display_summary(
        summary
    )


if __name__ == "__main__":
    main()