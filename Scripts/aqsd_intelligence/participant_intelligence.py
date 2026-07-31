"""
AQSD
Participant Intelligence Engine

Module : APD-005
Version: 1.0.0

Description
-----------
Reads participant Open Interest records from the AQSD Participant
Database and converts them into participant-level market intelligence.

Current outputs
---------------
- Long position
- Short position
- Net position
- Gross exposure
- Long percentage
- Short percentage
- Directional bias
- Change from previous available trading date
- Positioning behaviour
- Institutional interpretation

Supported participants
----------------------
- FII
- PRO
- DII
- CLIENT

Important
---------
This engine analyses positions. It does not generate BUY or SELL orders.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_database.database import AQSDDatabase


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

MODULE_ID: Final[str] = "APD-005"
MODULE_VERSION: Final[str] = "1.0.0"

PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
    "CLIENT",
)

INDEX_FUTURES_SEGMENT: Final[str] = (
    "OPEN INTEREST - INDEX FUTURES"
)


# ==========================================================
# DATA MODELS
# ==========================================================

@dataclass(frozen=True)
class ParticipantSnapshot:
    """
    Position snapshot for one participant and one trading date.
    """

    trade_date: date
    participant: str
    long_position: float
    short_position: float
    net_position: float
    gross_exposure: float
    long_percentage: float
    short_percentage: float
    directional_bias: str


@dataclass(frozen=True)
class ParticipantIntelligence:
    """
    Intelligence result for one participant.
    """

    participant: str
    current_date: date
    previous_date: date | None

    current_long: float
    current_short: float
    current_net: float
    current_gross: float

    long_percentage: float
    short_percentage: float
    directional_bias: str

    long_change: float | None
    short_change: float | None
    net_change: float | None

    behaviour: str
    confidence: int
    interpretation: str


@dataclass(frozen=True)
class ParticipantIntelligenceResult:
    """
    Complete APD-005 result.
    """

    requested_date: date
    current_date: date
    previous_date: date | None
    participant_results: tuple[ParticipantIntelligence, ...]
    institutional_bias: str
    overall_confidence: int
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def safe_percentage(
    numerator: float,
    denominator: float,
) -> float:
    """
    Calculate percentage safely.
    """

    if denominator == 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        2,
    )


def determine_directional_bias(
    net_position: float,
    gross_exposure: float,
) -> str:
    """
    Determine directional bias using net position as a share
    of gross exposure.
    """

    if gross_exposure == 0:
        return "NEUTRAL"

    net_ratio = net_position / gross_exposure

    if net_ratio >= 0.25:
        return "STRONGLY BULLISH"

    if net_ratio >= 0.08:
        return "BULLISH"

    if net_ratio <= -0.25:
        return "STRONGLY BEARISH"

    if net_ratio <= -0.08:
        return "BEARISH"

    return "NEUTRAL"


# ==========================================================
# DATABASE QUERIES
# ==========================================================

def get_latest_available_date(
    database: AQSDDatabase,
    requested_date: date,
) -> date | None:
    """
    Return the latest APD date on or before the requested date.
    """

    row = database.query_one(
        """
        SELECT MAX(trade_date) AS available_date
        FROM participant_positions
        WHERE trade_date <= ?
        """,
        (
            requested_date.isoformat(),
        ),
    )

    if row is None:
        return None

    value = row["available_date"]

    if value is None:
        return None

    return date.fromisoformat(value)


def get_previous_available_date(
    database: AQSDDatabase,
    current_date: date,
) -> date | None:
    """
    Return the previous available APD trading date.
    """

    row = database.query_one(
        """
        SELECT MAX(trade_date) AS previous_date
        FROM participant_positions
        WHERE trade_date < ?
        """,
        (
            current_date.isoformat(),
        ),
    )

    if row is None:
        return None

    value = row["previous_date"]

    if value is None:
        return None

    return date.fromisoformat(value)


def load_index_futures_snapshot(
    database: AQSDDatabase,
    trade_date: date,
    participant: str,
) -> ParticipantSnapshot:
    """
    Load one participant's Index Futures OI snapshot.
    """

    rows = database.query(
        """
        SELECT
            position_side,
            SUM(value) AS total_value
        FROM participant_positions
        WHERE trade_date = ?
          AND participant = ?
          AND segment = ?
        GROUP BY position_side
        """,
        (
            trade_date.isoformat(),
            participant,
            INDEX_FUTURES_SEGMENT,
        ),
    )

    long_position = 0.0
    short_position = 0.0

    for row in rows:
        side = str(row["position_side"]).upper()
        value = float(row["total_value"] or 0)

        if side == "LONG":
            long_position = value

        elif side == "SHORT":
            short_position = value

    net_position = long_position - short_position
    gross_exposure = long_position + short_position

    long_percentage = safe_percentage(
        long_position,
        gross_exposure,
    )

    short_percentage = safe_percentage(
        short_position,
        gross_exposure,
    )

    directional_bias = determine_directional_bias(
        net_position,
        gross_exposure,
    )

    return ParticipantSnapshot(
        trade_date=trade_date,
        participant=participant,
        long_position=long_position,
        short_position=short_position,
        net_position=net_position,
        gross_exposure=gross_exposure,
        long_percentage=long_percentage,
        short_percentage=short_percentage,
        directional_bias=directional_bias,
    )


# ==========================================================
# BEHAVIOUR ENGINE
# ==========================================================

def determine_behaviour(
    current: ParticipantSnapshot,
    previous: ParticipantSnapshot | None,
) -> str:
    """
    Classify participant behaviour using changes in long and short
    positions.

    Rules
    -----
    Long rises and Short falls:
        Bullish Shift

    Long falls and Short rises:
        Bearish Shift

    Long rises and Short rises:
        Gross Expansion

    Long falls and Short falls:
        Gross Reduction
    """

    if previous is None:
        return "INSUFFICIENT HISTORY"

    long_change = (
        current.long_position
        - previous.long_position
    )

    short_change = (
        current.short_position
        - previous.short_position
    )

    if long_change > 0 and short_change < 0:
        return "BULLISH SHIFT"

    if long_change < 0 and short_change > 0:
        return "BEARISH SHIFT"

    if long_change > 0 and short_change > 0:
        if current.net_position > previous.net_position:
            return "GROSS EXPANSION WITH BULLISH TILT"

        if current.net_position < previous.net_position:
            return "GROSS EXPANSION WITH BEARISH TILT"

        return "GROSS EXPANSION"

    if long_change < 0 and short_change < 0:
        if current.net_position > previous.net_position:
            return "POSITION REDUCTION WITH BULLISH TILT"

        if current.net_position < previous.net_position:
            return "POSITION REDUCTION WITH BEARISH TILT"

        return "POSITION REDUCTION"

    if long_change > 0:
        return "LONG ADDITION"

    if long_change < 0:
        return "LONG REDUCTION"

    if short_change > 0:
        return "SHORT ADDITION"

    if short_change < 0:
        return "SHORT COVERING"

    return "UNCHANGED"


def calculate_confidence(
    current: ParticipantSnapshot,
    previous: ParticipantSnapshot | None,
) -> int:
    """
    Calculate a simple explainable confidence score.
    """

    if current.gross_exposure == 0:
        return 0

    net_strength = abs(
        current.net_position
        / current.gross_exposure
    )

    score = 40 + int(
        min(net_strength, 1.0) * 50
    )

    if previous is not None:
        net_change = abs(
            current.net_position
            - previous.net_position
        )

        change_ratio = (
            net_change / current.gross_exposure
            if current.gross_exposure
            else 0
        )

        score += int(
            min(change_ratio, 0.20) * 50
        )

    return max(
        0,
        min(score, 100),
    )


def build_interpretation(
    participant: str,
    current: ParticipantSnapshot,
    behaviour: str,
) -> str:
    """
    Create a readable explanation.
    """

    return (
        f"{participant} Index Futures positioning is "
        f"{current.directional_bias.lower()}. "
        f"Long positions are {current.long_percentage:.2f}% and "
        f"short positions are {current.short_percentage:.2f}% "
        f"of gross exposure. Current behaviour is "
        f"{behaviour.lower()}."
    )


# ==========================================================
# PARTICIPANT ANALYSIS
# ==========================================================

def analyse_participant(
    *,
    database: AQSDDatabase,
    participant: str,
    current_date: date,
    previous_date: date | None,
) -> ParticipantIntelligence:
    """
    Analyse one participant.
    """

    current = load_index_futures_snapshot(
        database=database,
        trade_date=current_date,
        participant=participant,
    )

    previous = (
        load_index_futures_snapshot(
            database=database,
            trade_date=previous_date,
            participant=participant,
        )
        if previous_date is not None
        else None
    )

    behaviour = determine_behaviour(
        current=current,
        previous=previous,
    )

    confidence = calculate_confidence(
        current=current,
        previous=previous,
    )

    interpretation = build_interpretation(
        participant=participant,
        current=current,
        behaviour=behaviour,
    )

    return ParticipantIntelligence(
        participant=participant,
        current_date=current_date,
        previous_date=previous_date,
        current_long=current.long_position,
        current_short=current.short_position,
        current_net=current.net_position,
        current_gross=current.gross_exposure,
        long_percentage=current.long_percentage,
        short_percentage=current.short_percentage,
        directional_bias=current.directional_bias,
        long_change=(
            current.long_position
            - previous.long_position
            if previous is not None
            else None
        ),
        short_change=(
            current.short_position
            - previous.short_position
            if previous is not None
            else None
        ),
        net_change=(
            current.net_position
            - previous.net_position
            if previous is not None
            else None
        ),
        behaviour=behaviour,
        confidence=confidence,
        interpretation=interpretation,
    )


# ==========================================================
# OVERALL INSTITUTIONAL VIEW
# ==========================================================

def determine_institutional_bias(
    results: tuple[ParticipantIntelligence, ...],
) -> str:
    """
    Determine combined FII, PRO and DII positioning.

    CLIENT is intentionally excluded from institutional scoring.
    """

    institutional_results = [
        result
        for result in results
        if result.participant in {
            "FII",
            "PRO",
            "DII",
        }
    ]

    combined_net = sum(
        result.current_net
        for result in institutional_results
    )

    combined_gross = sum(
        result.current_gross
        for result in institutional_results
    )

    return determine_directional_bias(
        combined_net,
        combined_gross,
    )


def calculate_overall_confidence(
    results: tuple[ParticipantIntelligence, ...],
) -> int:
    """
    Average institutional confidence.
    """

    institutional_scores = [
        result.confidence
        for result in results
        if result.participant in {
            "FII",
            "PRO",
            "DII",
        }
    ]

    if not institutional_scores:
        return 0

    return round(
        sum(institutional_scores)
        / len(institutional_scores)
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_intelligence(
    requested_date: date,
) -> ParticipantIntelligenceResult:
    """
    Run APD-005 participant intelligence.
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
                "No APD participant data is available."
            )

        previous_date = get_previous_available_date(
            database=database,
            current_date=current_date,
        )

        results = tuple(
            analyse_participant(
                database=database,
                participant=participant,
                current_date=current_date,
                previous_date=previous_date,
            )
            for participant in PARTICIPANTS
        )

    institutional_bias = determine_institutional_bias(
        results
    )

    overall_confidence = calculate_overall_confidence(
        results
    )

    return ParticipantIntelligenceResult(
        requested_date=requested_date,
        current_date=current_date,
        previous_date=previous_date,
        participant_results=results,
        institutional_bias=institutional_bias,
        overall_confidence=overall_confidence,
        status="SUCCESS",
    )


# ==========================================================
# TERMINAL DISPLAY
# ==========================================================

def display_result(
    result: ParticipantIntelligenceResult,
) -> None:
    """
    Print a readable terminal report.
    """

    print()
    print("=" * 78)
    print("AQSD PARTICIPANT INTELLIGENCE ENGINE")
    print("=" * 78)
    print(f"Module              : {MODULE_ID}")
    print(f"Version             : {MODULE_VERSION}")
    print(f"Requested Date      : {result.requested_date}")
    print(f"Current APD Date    : {result.current_date}")
    print(f"Previous APD Date   : {result.previous_date}")
    print("-" * 78)

    for item in result.participant_results:
        print(f"PARTICIPANT         : {item.participant}")
        print(f"Long                : {item.current_long:,.0f}")
        print(f"Short               : {item.current_short:,.0f}")
        print(f"Net                 : {item.current_net:,.0f}")
        print(f"Long %              : {item.long_percentage:.2f}%")
        print(f"Short %             : {item.short_percentage:.2f}%")
        print(f"Bias                : {item.directional_bias}")
        print(f"Behaviour           : {item.behaviour}")
        print(f"Confidence          : {item.confidence}%")
        print(f"Interpretation      : {item.interpretation}")
        print("-" * 78)

    print(f"Institutional Bias  : {result.institutional_bias}")
    print(f"Overall Confidence  : {result.overall_confidence}%")
    print(f"Status              : {result.status}")
    print("=" * 78)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read terminal arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Analyse NSE participant Index Futures positioning "
            "from the AQSD Participant Database."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Analysis date in YYYY-MM-DD format.",
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

    result = run_participant_intelligence(
        parse_date(arguments.date)
    )

    display_result(result)


if __name__ == "__main__":
    main()