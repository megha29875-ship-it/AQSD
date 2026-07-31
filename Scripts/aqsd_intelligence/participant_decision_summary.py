"""
AQSD
Participant Decision Summary Engine

Module : APD-010
Version: 1.0.0
Author : AQSD

Description
-----------
Converts APD historical participant intelligence into one concise,
explainable participant decision summary.

Inputs
------
- Current institutional positioning
- Daily institutional change
- Weekly institutional change
- Monthly institutional change
- Institutional trend
- Institutional alignment
- Historical conviction

Outputs
-------
- Current Positioning
- Momentum
- Structural State
- Risk Level
- Expected Behaviour
- Participant Environment
- Confidence
- Explanation

Important
---------
This engine provides analytical conclusions only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from Scripts.aqsd_intelligence.participant_historical_change_engine import (
    ParticipantHistoricalResult,
    run_historical_change_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-010"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantDecisionSummary:
    """
    Final participant decision-support summary.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    structural_state: str
    institutional_alignment: str

    risk_level: str
    expected_behaviour: str
    participant_environment: str

    confidence: int
    explanation: str
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def contains_bullish(value: str) -> bool:
    """
    Return True when a label contains bullish meaning.
    """

    return "BULLISH" in value.upper()


def contains_bearish(value: str) -> bool:
    """
    Return True when a label contains bearish meaning.
    """

    return "BEARISH" in value.upper()


def contains_improving(value: str) -> bool:
    """
    Return True when a label represents improving momentum.
    """

    normalized = value.upper()

    return (
        "IMPROVING" in normalized
        or "BULLISH" in normalized
    )


def contains_deteriorating(value: str) -> bool:
    """
    Return True when a label represents deteriorating momentum.
    """

    normalized = value.upper()

    return (
        "DETERIORATING" in normalized
        or "BEARISH" in normalized
    )


# ==========================================================
# CURRENT POSITIONING
# ==========================================================

def determine_current_positioning(
    historical_result: ParticipantHistoricalResult,
) -> str:
    """
    Return the current combined institutional positioning.
    """

    return historical_result.institutional_bias


# ==========================================================
# MOMENTUM
# ==========================================================

def determine_momentum(
    historical_result: ParticipantHistoricalResult,
) -> str:
    """
    Convert the institutional trend into a simpler momentum label.
    """

    trend = historical_result.institutional_trend.upper()

    if trend == "CONSISTENTLY IMPROVING":
        return "STRONGLY IMPROVING"

    if trend == "IMPROVING WITH MIXED PERIODS":
        return "IMPROVING"

    if trend == "CONSISTENTLY DETERIORATING":
        return "STRONGLY DETERIORATING"

    if trend == "DETERIORATING WITH MIXED PERIODS":
        return "DETERIORATING"

    if trend == "MIXED":
        return "MIXED"

    return "INSUFFICIENT HISTORY"


# ==========================================================
# STRUCTURAL STATE
# ==========================================================

def determine_structural_state(
    *,
    current_positioning: str,
    momentum: str,
) -> str:
    """
    Combine current exposure and multi-period momentum.

    Examples
    --------
    Bearish positioning + improving momentum:
        Bearish structure with recovery

    Bullish positioning + deteriorating momentum:
        Bullish structure losing strength
    """

    if (
        contains_bearish(current_positioning)
        and contains_improving(momentum)
    ):
        return "BEARISH STRUCTURE WITH RECOVERY"

    if (
        contains_bearish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return "BEARISH STRUCTURE STRENGTHENING"

    if (
        contains_bullish(current_positioning)
        and contains_improving(momentum)
    ):
        return "BULLISH STRUCTURE STRENGTHENING"

    if (
        contains_bullish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return "BULLISH STRUCTURE LOSING STRENGTH"

    if current_positioning == "NEUTRAL":
        return "NEUTRAL STRUCTURE"

    return "MIXED STRUCTURE"


# ==========================================================
# RISK ENGINE
# ==========================================================

def determine_risk_level(
    *,
    current_positioning: str,
    momentum: str,
    institutional_alignment: str,
    confidence: int,
) -> str:
    """
    Determine uncertainty and reversal risk.

    High risk means participant signals conflict or lack alignment.
    """

    alignment = institutional_alignment.upper()

    mixed_alignment = (
        "MIXED" in alignment
    )

    majority_alignment = (
        "MAJORITY" in alignment
    )

    full_alignment = (
        "FULL" in alignment
    )

    positioning_momentum_conflict = (
        (
            contains_bearish(current_positioning)
            and contains_improving(momentum)
        )
        or
        (
            contains_bullish(current_positioning)
            and contains_deteriorating(momentum)
        )
    )

    if confidence < 45:
        return "HIGH"

    if mixed_alignment and positioning_momentum_conflict:
        return "HIGH"

    if mixed_alignment:
        return "MODERATE TO HIGH"

    if majority_alignment:
        return "MODERATE"

    if full_alignment and confidence >= 70:
        return "LOW"

    return "MODERATE"


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    *,
    current_positioning: str,
    momentum: str,
    institutional_alignment: str,
) -> str:
    """
    Determine the likely participant-driven market behaviour.
    """

    alignment = institutional_alignment.upper()

    if (
        contains_bearish(current_positioning)
        and contains_improving(momentum)
    ):
        return (
            "SHORT COVERING OR RECOVERY MAY CONTINUE, "
            "BUT BEARISH EXPOSURE REMAINS DOMINANT"
        )

    if (
        contains_bearish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return (
            "BEARISH PRESSURE MAY CONTINUE AS SHORT EXPOSURE "
            "AND NEGATIVE POSITIONING REMAIN DOMINANT"
        )

    if (
        contains_bullish(current_positioning)
        and contains_improving(momentum)
    ):
        return (
            "BULLISH CONTINUATION IS SUPPORTED BY CURRENT "
            "POSITIONING AND IMPROVING PARTICIPANT MOMENTUM"
        )

    if (
        contains_bullish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return (
            "PROFIT BOOKING OR A PULLBACK IS POSSIBLE AS "
            "BULLISH POSITIONING LOSES MOMENTUM"
        )

    if "MIXED" in alignment:
        return (
            "RANGE-BOUND OR VOLATILE BEHAVIOUR IS POSSIBLE "
            "BECAUSE INSTITUTIONAL PARTICIPANTS ARE NOT ALIGNED"
        )

    return (
        "NO CLEAR PARTICIPANT-DRIVEN DIRECTIONAL ADVANTAGE "
        "IS CURRENTLY VISIBLE"
    )


# ==========================================================
# ENVIRONMENT
# ==========================================================

def determine_participant_environment(
    *,
    current_positioning: str,
    momentum: str,
    institutional_alignment: str,
) -> str:
    """
    Classify the overall participant environment.
    """

    alignment = institutional_alignment.upper()

    if (
        contains_bearish(current_positioning)
        and contains_improving(momentum)
    ):
        return "RECOVERY WITHIN BEARISH POSITIONING"

    if (
        contains_bearish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return "BEARISH PARTICIPANT CONTROL"

    if (
        contains_bullish(current_positioning)
        and contains_improving(momentum)
    ):
        return "BULLISH PARTICIPANT CONTROL"

    if (
        contains_bullish(current_positioning)
        and contains_deteriorating(momentum)
    ):
        return "BULLISH EXHAUSTION RISK"

    if "MIXED" in alignment:
        return "CONFLICTED PARTICIPANT ENVIRONMENT"

    return "NEUTRAL PARTICIPANT ENVIRONMENT"


# ==========================================================
# CONFIDENCE
# ==========================================================

def calculate_summary_confidence(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Adjust historical conviction based on institutional alignment.
    """

    score = historical_result.overall_conviction
    alignment = historical_result.institutional_alignment.upper()

    if "FULL" in alignment:
        score += 8

    elif "MAJORITY" in alignment:
        score += 3

    elif "MIXED" in alignment:
        score -= 5

    trend = historical_result.institutional_trend.upper()

    if trend in {
        "CONSISTENTLY IMPROVING",
        "CONSISTENTLY DETERIORATING",
    }:
        score += 4

    elif trend == "MIXED":
        score -= 4

    return max(
        0,
        min(score, 100),
    )


# ==========================================================
# EXPLANATION
# ==========================================================

def build_explanation(
    *,
    historical_result: ParticipantHistoricalResult,
    current_positioning: str,
    momentum: str,
    structural_state: str,
    risk_level: str,
    expected_behaviour: str,
) -> str:
    """
    Build the final explainable participant conclusion.
    """

    daily_change = (
        historical_result.institutional_daily_net_change
    )

    weekly_change = (
        historical_result.institutional_weekly_net_change
    )

    monthly_change = (
        historical_result.institutional_monthly_net_change
    )

    daily_text = (
        f"{daily_change:+,.0f}"
        if daily_change is not None
        else "not available"
    )

    weekly_text = (
        f"{weekly_change:+,.0f}"
        if weekly_change is not None
        else "not available"
    )

    monthly_text = (
        f"{monthly_change:+,.0f}"
        if monthly_change is not None
        else "not available"
    )

    return (
        f"Combined institutional positioning is "
        f"{current_positioning.lower()}, with a current net position "
        f"of {historical_result.institutional_current_net:+,.0f}. "
        f"Institutional net positioning changed by {daily_text} "
        f"over the daily period, {weekly_text} over the weekly period "
        f"and {monthly_text} over the monthly period. "
        f"Momentum is {momentum.lower()} and institutional alignment "
        f"is {historical_result.institutional_alignment.lower()}. "
        f"This creates a {structural_state.lower()} environment with "
        f"{risk_level.lower()} analytical risk. "
        f"{expected_behaviour.capitalize()}."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_decision_summary(
    requested_date: date,
) -> ParticipantDecisionSummary:
    """
    Run APD-010.
    """

    historical_result = run_historical_change_engine(
        requested_date
    )

    current_positioning = determine_current_positioning(
        historical_result
    )

    momentum = determine_momentum(
        historical_result
    )

    structural_state = determine_structural_state(
        current_positioning=current_positioning,
        momentum=momentum,
    )

    confidence = calculate_summary_confidence(
        historical_result
    )

    risk_level = determine_risk_level(
        current_positioning=current_positioning,
        momentum=momentum,
        institutional_alignment=(
            historical_result.institutional_alignment
        ),
        confidence=confidence,
    )

    expected_behaviour = determine_expected_behaviour(
        current_positioning=current_positioning,
        momentum=momentum,
        institutional_alignment=(
            historical_result.institutional_alignment
        ),
    )

    participant_environment = determine_participant_environment(
        current_positioning=current_positioning,
        momentum=momentum,
        institutional_alignment=(
            historical_result.institutional_alignment
        ),
    )

    explanation = build_explanation(
        historical_result=historical_result,
        current_positioning=current_positioning,
        momentum=momentum,
        structural_state=structural_state,
        risk_level=risk_level,
        expected_behaviour=expected_behaviour,
    )

    return ParticipantDecisionSummary(
        requested_date=requested_date,
        analysis_date=historical_result.current_date,
        current_positioning=current_positioning,
        momentum=momentum,
        structural_state=structural_state,
        institutional_alignment=(
            historical_result.institutional_alignment
        ),
        risk_level=risk_level,
        expected_behaviour=expected_behaviour,
        participant_environment=participant_environment,
        confidence=confidence,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantDecisionSummary,
) -> None:
    """
    Print the final participant decision summary.
    """

    print()
    print("=" * 88)
    print("AQSD PARTICIPANT DECISION SUMMARY")
    print("=" * 88)
    print(f"Module                  : {MODULE_ID}")
    print(f"Version                 : {MODULE_VERSION}")
    print(f"Requested Date          : {result.requested_date}")
    print(f"Analysis Date           : {result.analysis_date}")
    print("-" * 88)
    print(
        f"Current Positioning     : "
        f"{result.current_positioning}"
    )
    print(
        f"Momentum                : "
        f"{result.momentum}"
    )
    print(
        f"Structural State        : "
        f"{result.structural_state}"
    )
    print(
        f"Institutional Alignment : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Risk Level              : "
        f"{result.risk_level}"
    )
    print(
        f"Expected Behaviour      : "
        f"{result.expected_behaviour}"
    )
    print(
        f"Participant Environment : "
        f"{result.participant_environment}"
    )
    print(
        f"Confidence              : "
        f"{result.confidence}%"
    )
    print("-" * 88)
    print("EXPLANATION")
    print("-" * 88)
    print(result.explanation)
    print("-" * 88)
    print(f"Status                  : {result.status}")
    print("=" * 88)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Create an explainable participant decision summary "
            "from APD historical intelligence."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested analysis date in YYYY-MM-DD format.",
    )

    return parser.parse_args()


def parse_date(
    value: str,
) -> date:
    """
    Convert YYYY-MM-DD text into a Python date.
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
        result = run_participant_decision_summary(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 88)
        print("AQSD PARTICIPANT DECISION SUMMARY")
        print("=" * 88)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 88)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()