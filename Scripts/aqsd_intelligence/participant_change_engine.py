"""
AQSD
Participant Change Engine

Module : APD-006
Version: 1.0.0

Description
-----------
Compares participant Index Futures Open Interest between two
available APD trading dates.

Outputs
-------
- Long position change
- Short position change
- Net position change
- Gross exposure change
- Percentage changes
- Behaviour classification
- Conviction score
- Participant interpretation
- Combined institutional change bias

Important
---------
This engine provides market intelligence only.
It does not generate BUY or SELL orders.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_database.database import AQSDDatabase
from Scripts.aqsd_intelligence.participant_intelligence import (
    ParticipantSnapshot,
    get_latest_available_date,
    get_previous_available_date,
    load_index_futures_snapshot,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

APD_DATABASE_FILE: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "APD"
    / "participant_database.db"
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-006"
MODULE_VERSION: Final[str] = "1.0.0"

PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
    "CLIENT",
)

INSTITUTIONAL_PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
)


# ==========================================================
# DATA MODELS
# ==========================================================

@dataclass(frozen=True)
class ParticipantChange:
    """
    Change analysis for one participant.
    """

    participant: str
    current_date: date
    previous_date: date

    current_long: float
    previous_long: float
    long_change: float
    long_change_percent: float | None

    current_short: float
    previous_short: float
    short_change: float
    short_change_percent: float | None

    current_net: float
    previous_net: float
    net_change: float

    current_gross: float
    previous_gross: float
    gross_change: float
    gross_change_percent: float | None

    behaviour: str
    directional_effect: str
    conviction_score: int
    interpretation: str


@dataclass(frozen=True)
class ParticipantChangeResult:
    """
    Complete APD-006 engine result.
    """

    requested_date: date
    current_date: date
    previous_date: date
    participant_changes: tuple[ParticipantChange, ...]
    institutional_net_change: float
    institutional_gross_change: float
    institutional_change_bias: str
    overall_conviction: int
    status: str


# ==========================================================
# NUMBER HELPERS
# ==========================================================

def percentage_change(
    current_value: float,
    previous_value: float,
) -> float | None:
    """
    Calculate percentage change safely.

    Returns None when the previous value is zero.
    """

    if previous_value == 0:
        return None

    return round(
        (
            (current_value - previous_value)
            / abs(previous_value)
        )
        * 100,
        2,
    )


def format_percentage(
    value: float | None,
) -> str:
    """
    Format an optional percentage.
    """

    if value is None:
        return "N/A"

    return f"{value:,.2f}%"


# ==========================================================
# BEHAVIOUR CLASSIFICATION
# ==========================================================

def determine_change_behaviour(
    *,
    long_change: float,
    short_change: float,
    net_change: float,
) -> str:
    """
    Classify changes in long and short positions.

    Interpretations
    ---------------
    Long rises, Short falls:
        Bullish Shift

    Long falls, Short rises:
        Bearish Shift

    Long and Short both rise:
        Gross Expansion with directional tilt

    Long and Short both fall:
        Position Reduction with directional tilt
    """

    if long_change > 0 and short_change < 0:
        return "LONG ADDITION WITH SHORT COVERING"

    if long_change < 0 and short_change > 0:
        return "LONG REDUCTION WITH SHORT ADDITION"

    if long_change > 0 and short_change > 0:
        if net_change > 0:
            return "GROSS EXPANSION WITH BULLISH TILT"

        if net_change < 0:
            return "GROSS EXPANSION WITH BEARISH TILT"

        return "GROSS EXPANSION"

    if long_change < 0 and short_change < 0:
        if net_change > 0:
            return "POSITION REDUCTION WITH BULLISH TILT"

        if net_change < 0:
            return "POSITION REDUCTION WITH BEARISH TILT"

        return "POSITION REDUCTION"

    if long_change > 0:
        return "FRESH LONG ADDITION"

    if long_change < 0:
        return "LONG REDUCTION"

    if short_change > 0:
        return "FRESH SHORT ADDITION"

    if short_change < 0:
        return "SHORT COVERING"

    return "UNCHANGED"


def determine_directional_effect(
    net_change: float,
    current_gross: float,
) -> str:
    """
    Determine the directional effect of the daily net-position change.
    """

    if current_gross == 0:
        return "NEUTRAL"

    change_ratio = net_change / current_gross

    if change_ratio >= 0.15:
        return "STRONGLY BULLISH"

    if change_ratio >= 0.04:
        return "BULLISH"

    if change_ratio <= -0.15:
        return "STRONGLY BEARISH"

    if change_ratio <= -0.04:
        return "BEARISH"

    return "NEUTRAL"


# ==========================================================
# CONVICTION
# ==========================================================

def calculate_conviction_score(
    *,
    current: ParticipantSnapshot,
    previous: ParticipantSnapshot,
    long_change: float,
    short_change: float,
    net_change: float,
) -> int:
    """
    Calculate an explainable 0-100 conviction score.

    Components
    ----------
    - Current net-position strength
    - Net-position change relative to gross exposure
    - Directional agreement between long and short changes
    """

    if current.gross_exposure == 0:
        return 0

    current_net_strength = abs(
        current.net_position
        / current.gross_exposure
    )

    net_change_strength = abs(
        net_change
        / current.gross_exposure
    )

    score = 30

    score += int(
        min(current_net_strength, 1.0)
        * 35
    )

    score += int(
        min(net_change_strength, 0.50)
        * 50
    )

    directional_agreement = (
        (long_change > 0 and short_change < 0)
        or
        (long_change < 0 and short_change > 0)
    )

    if directional_agreement:
        score += 10

    gross_change = (
        current.gross_exposure
        - previous.gross_exposure
    )

    if abs(gross_change) > 0:
        score += 5

    return max(
        0,
        min(score, 100),
    )


# ==========================================================
# INTERPRETATION
# ==========================================================

def build_change_interpretation(
    *,
    participant: str,
    current: ParticipantSnapshot,
    previous: ParticipantSnapshot,
    behaviour: str,
    directional_effect: str,
) -> str:
    """
    Build a readable participant-change explanation.
    """

    long_change = (
        current.long_position
        - previous.long_position
    )

    short_change = (
        current.short_position
        - previous.short_position
    )

    net_change = (
        current.net_position
        - previous.net_position
    )

    return (
        f"{participant} Index Futures long positions changed by "
        f"{long_change:+,.0f}, while short positions changed by "
        f"{short_change:+,.0f}. Net positioning changed by "
        f"{net_change:+,.0f}. This is classified as "
        f"{behaviour.lower()} and has a "
        f"{directional_effect.lower()} directional effect."
    )


# ==========================================================
# PARTICIPANT ANALYSIS
# ==========================================================

def analyse_participant_change(
    *,
    database: AQSDDatabase,
    participant: str,
    current_date: date,
    previous_date: date,
) -> ParticipantChange:
    """
    Compare one participant across two trading dates.
    """

    current = load_index_futures_snapshot(
        database=database,
        trade_date=current_date,
        participant=participant,
    )

    previous = load_index_futures_snapshot(
        database=database,
        trade_date=previous_date,
        participant=participant,
    )

    long_change = (
        current.long_position
        - previous.long_position
    )

    short_change = (
        current.short_position
        - previous.short_position
    )

    net_change = (
        current.net_position
        - previous.net_position
    )

    gross_change = (
        current.gross_exposure
        - previous.gross_exposure
    )

    behaviour = determine_change_behaviour(
        long_change=long_change,
        short_change=short_change,
        net_change=net_change,
    )

    directional_effect = determine_directional_effect(
        net_change=net_change,
        current_gross=current.gross_exposure,
    )

    conviction_score = calculate_conviction_score(
        current=current,
        previous=previous,
        long_change=long_change,
        short_change=short_change,
        net_change=net_change,
    )

    interpretation = build_change_interpretation(
        participant=participant,
        current=current,
        previous=previous,
        behaviour=behaviour,
        directional_effect=directional_effect,
    )

    return ParticipantChange(
        participant=participant,
        current_date=current_date,
        previous_date=previous_date,
        current_long=current.long_position,
        previous_long=previous.long_position,
        long_change=long_change,
        long_change_percent=percentage_change(
            current.long_position,
            previous.long_position,
        ),
        current_short=current.short_position,
        previous_short=previous.short_position,
        short_change=short_change,
        short_change_percent=percentage_change(
            current.short_position,
            previous.short_position,
        ),
        current_net=current.net_position,
        previous_net=previous.net_position,
        net_change=net_change,
        current_gross=current.gross_exposure,
        previous_gross=previous.gross_exposure,
        gross_change=gross_change,
        gross_change_percent=percentage_change(
            current.gross_exposure,
            previous.gross_exposure,
        ),
        behaviour=behaviour,
        directional_effect=directional_effect,
        conviction_score=conviction_score,
        interpretation=interpretation,
    )


# ==========================================================
# INSTITUTIONAL SUMMARY
# ==========================================================

def determine_institutional_change_bias(
    institutional_net_change: float,
    institutional_current_gross: float,
) -> str:
    """
    Determine combined FII, PRO and DII daily change bias.
    """

    if institutional_current_gross == 0:
        return "NEUTRAL"

    change_ratio = (
        institutional_net_change
        / institutional_current_gross
    )

    if change_ratio >= 0.12:
        return "STRONGLY BULLISH"

    if change_ratio >= 0.03:
        return "BULLISH"

    if change_ratio <= -0.12:
        return "STRONGLY BEARISH"

    if change_ratio <= -0.03:
        return "BEARISH"

    return "NEUTRAL"


def calculate_overall_conviction(
    changes: tuple[ParticipantChange, ...],
) -> int:
    """
    Average conviction of FII, PRO and DII.
    """

    scores = [
        item.conviction_score
        for item in changes
        if item.participant
        in INSTITUTIONAL_PARTICIPANTS
    ]

    if not scores:
        return 0

    return round(
        sum(scores)
        / len(scores)
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_change_engine(
    requested_date: date,
) -> ParticipantChangeResult:
    """
    Run APD-006 for the latest available date on or before
    the requested date.
    """

    if not APD_DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"APD database not found: {APD_DATABASE_FILE}"
        )

    with AQSDDatabase(
        database_file=APD_DATABASE_FILE
    ) as database:
        current_date = get_latest_available_date(
            database=database,
            requested_date=requested_date,
        )

        if current_date is None:
            raise RuntimeError(
                "No participant data is available in APD."
            )

        previous_date = get_previous_available_date(
            database=database,
            current_date=current_date,
        )

        if previous_date is None:
            raise RuntimeError(
                "APD-006 requires at least two trading dates. "
                f"Only {current_date} is currently available."
            )

        participant_changes = tuple(
            analyse_participant_change(
                database=database,
                participant=participant,
                current_date=current_date,
                previous_date=previous_date,
            )
            for participant in PARTICIPANTS
        )

    institutional_changes = [
        item
        for item in participant_changes
        if item.participant
        in INSTITUTIONAL_PARTICIPANTS
    ]

    institutional_net_change = sum(
        item.net_change
        for item in institutional_changes
    )

    institutional_gross_change = sum(
        item.gross_change
        for item in institutional_changes
    )

    institutional_current_gross = sum(
        item.current_gross
        for item in institutional_changes
    )

    institutional_change_bias = (
        determine_institutional_change_bias(
            institutional_net_change=
                institutional_net_change,
            institutional_current_gross=
                institutional_current_gross,
        )
    )

    overall_conviction = calculate_overall_conviction(
        participant_changes
    )

    return ParticipantChangeResult(
        requested_date=requested_date,
        current_date=current_date,
        previous_date=previous_date,
        participant_changes=participant_changes,
        institutional_net_change=
            institutional_net_change,
        institutional_gross_change=
            institutional_gross_change,
        institutional_change_bias=
            institutional_change_bias,
        overall_conviction=overall_conviction,
        status="SUCCESS",
    )


# ==========================================================
# TERMINAL REPORT
# ==========================================================

def display_result(
    result: ParticipantChangeResult,
) -> None:
    """
    Display the APD-006 report.
    """

    print()
    print("=" * 82)
    print("AQSD PARTICIPANT CHANGE ENGINE")
    print("=" * 82)
    print(f"Module                 : {MODULE_ID}")
    print(f"Version                : {MODULE_VERSION}")
    print(f"Requested Date         : {result.requested_date}")
    print(f"Current APD Date       : {result.current_date}")
    print(f"Previous APD Date      : {result.previous_date}")
    print("-" * 82)

    for item in result.participant_changes:
        print(f"PARTICIPANT            : {item.participant}")

        print(
            f"Long                    : "
            f"{item.previous_long:,.0f} -> "
            f"{item.current_long:,.0f}"
        )

        print(
            f"Long Change             : "
            f"{item.long_change:+,.0f} "
            f"({format_percentage(item.long_change_percent)})"
        )

        print(
            f"Short                   : "
            f"{item.previous_short:,.0f} -> "
            f"{item.current_short:,.0f}"
        )

        print(
            f"Short Change            : "
            f"{item.short_change:+,.0f} "
            f"({format_percentage(item.short_change_percent)})"
        )

        print(
            f"Net                     : "
            f"{item.previous_net:,.0f} -> "
            f"{item.current_net:,.0f}"
        )

        print(
            f"Net Change              : "
            f"{item.net_change:+,.0f}"
        )

        print(
            f"Gross Change            : "
            f"{item.gross_change:+,.0f} "
            f"({format_percentage(item.gross_change_percent)})"
        )

        print(
            f"Behaviour               : "
            f"{item.behaviour}"
        )

        print(
            f"Directional Effect      : "
            f"{item.directional_effect}"
        )

        print(
            f"Conviction              : "
            f"{item.conviction_score}%"
        )

        print(
            f"Interpretation          : "
            f"{item.interpretation}"
        )

        print("-" * 82)

    print(
        f"Institutional Net Change: "
        f"{result.institutional_net_change:+,.0f}"
    )

    print(
        f"Institutional Gross Chg : "
        f"{result.institutional_gross_change:+,.0f}"
    )

    print(
        f"Institutional Change Bias: "
        f"{result.institutional_change_bias}"
    )

    print(
        f"Overall Conviction      : "
        f"{result.overall_conviction}%"
    )

    print(f"Status                  : {result.status}")
    print("=" * 82)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Compare participant Index Futures positioning "
            "between two APD trading dates."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested date in YYYY-MM-DD format.",
    )

    return parser.parse_args()


def parse_date(value: str) -> date:
    """
    Convert YYYY-MM-DD text into a date.
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


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = run_participant_change_engine(
            parse_date(arguments.date)
        )

    except RuntimeError as exc:
        print()
        print("=" * 82)
        print("AQSD PARTICIPANT CHANGE ENGINE")
        print("=" * 82)
        print(f"Status : INSUFFICIENT HISTORY")
        print(f"Reason : {exc}")
        print("=" * 82)
        return

    display_result(result)


if __name__ == "__main__":
    main()