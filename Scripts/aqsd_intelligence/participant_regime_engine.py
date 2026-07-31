"""
AQSD
Participant Regime Engine

Module : APD-012
Version: 1.0.0
Author : AQSD

Description
-----------
Classifies the prevailing institutional participant regime using:

- Current institutional positioning
- Daily, weekly and monthly institutional net changes
- Institutional momentum
- Institutional alignment
- Participant structural state
- Scenario probabilities
- Probability confidence

Supported regimes
-----------------
- BULLISH CONTROL
- BEARISH CONTROL
- ACCUMULATION
- DISTRIBUTION
- SHORT COVERING
- LONG UNWINDING
- BULLISH TRANSITION
- BEARISH TRANSITION
- CONSOLIDATION
- CONFLICTED TRANSITION

Important
---------
This engine provides analytical market intelligence only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from Scripts.aqsd_intelligence.institutional_probability_engine import (
    InstitutionalProbabilityResult,
    run_institutional_probability_engine,
)
from Scripts.aqsd_intelligence.participant_decision_summary import (
    ParticipantDecisionSummary,
    run_participant_decision_summary,
)
from Scripts.aqsd_intelligence.participant_historical_change_engine import (
    ParticipantHistoricalResult,
    run_historical_change_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-012"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantRegimeResult:
    """
    Complete APD-012 participant-regime result.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    structural_state: str
    institutional_alignment: str

    daily_net_change: float | None
    weekly_net_change: float | None
    monthly_net_change: float | None

    highest_probability_scenario: str
    highest_probability: float
    probability_confidence: int

    primary_regime: str
    secondary_regime: str
    regime_direction: str
    regime_strength: str
    regime_maturity: str

    risk_level: str
    expected_behaviour: str
    environment: str

    regime_confidence: int
    explanation: str
    status: str


# ==========================================================
# TEXT HELPERS
# ==========================================================

def contains_bullish(value: str) -> bool:
    """
    Return True when text contains bullish meaning.
    """

    return "BULLISH" in value.upper()


def contains_bearish(value: str) -> bool:
    """
    Return True when text contains bearish meaning.
    """

    return "BEARISH" in value.upper()


def contains_improving(value: str) -> bool:
    """
    Return True when momentum is improving.
    """

    return "IMPROVING" in value.upper()


def contains_deteriorating(value: str) -> bool:
    """
    Return True when momentum is deteriorating.
    """

    return "DETERIORATING" in value.upper()


def contains_mixed(value: str) -> bool:
    """
    Return True when text represents mixed conditions.
    """

    return "MIXED" in value.upper()


# ==========================================================
# NUMBER HELPERS
# ==========================================================

def change_direction(
    value: float | None,
) -> int:
    """
    Convert a change into:

     1 = positive
     0 = unavailable or unchanged
    -1 = negative
    """

    if value is None:
        return 0

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def format_change(
    value: float | None,
) -> str:
    """
    Format an optional participant-position change.
    """

    if value is None:
        return "NOT AVAILABLE"

    return f"{value:+,.0f}"


# ==========================================================
# PERIOD DIRECTION
# ==========================================================

def count_positive_periods(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count positive institutional-change periods.
    """

    values = (
        historical_result.institutional_daily_net_change,
        historical_result.institutional_weekly_net_change,
        historical_result.institutional_monthly_net_change,
    )

    return sum(
        change_direction(value) > 0
        for value in values
    )


def count_negative_periods(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count negative institutional-change periods.
    """

    values = (
        historical_result.institutional_daily_net_change,
        historical_result.institutional_weekly_net_change,
        historical_result.institutional_monthly_net_change,
    )

    return sum(
        change_direction(value) < 0
        for value in values
    )


# ==========================================================
# PRIMARY REGIME
# ==========================================================

def determine_primary_regime(
    *,
    decision_summary: ParticipantDecisionSummary,
    historical_result: ParticipantHistoricalResult,
    probability_result: InstitutionalProbabilityResult,
) -> str:
    """
    Determine the dominant participant regime.
    """

    positioning = (
        decision_summary.current_positioning.upper()
    )

    momentum = decision_summary.momentum.upper()

    structural_state = (
        decision_summary.structural_state.upper()
    )

    highest_scenario = (
        probability_result
        .highest_probability_scenario
        .upper()
    )

    positive_periods = count_positive_periods(
        historical_result
    )

    negative_periods = count_negative_periods(
        historical_result
    )

    # ------------------------------------------------------
    # BULLISH CONTROL
    # ------------------------------------------------------

    if (
        contains_bullish(positioning)
        and contains_improving(momentum)
        and highest_scenario
        == "BULLISH CONTINUATION"
    ):
        return "BULLISH CONTROL"

    # ------------------------------------------------------
    # BEARISH CONTROL
    # ------------------------------------------------------

    if (
        contains_bearish(positioning)
        and contains_deteriorating(momentum)
        and highest_scenario
        == "BEARISH CONTINUATION"
    ):
        return "BEARISH CONTROL"

    # ------------------------------------------------------
    # SHORT COVERING
    # ------------------------------------------------------

    if (
        contains_bearish(positioning)
        and contains_improving(momentum)
        and positive_periods >= 2
        and highest_scenario
        == "BULLISH RECOVERY"
    ):
        return "SHORT COVERING"

    # ------------------------------------------------------
    # LONG UNWINDING
    # ------------------------------------------------------

    if (
        contains_bullish(positioning)
        and contains_deteriorating(momentum)
        and negative_periods >= 2
        and highest_scenario
        == "BEARISH REVERSAL"
    ):
        return "LONG UNWINDING"

    # ------------------------------------------------------
    # ACCUMULATION
    # ------------------------------------------------------

    if (
        positive_periods >= 2
        and (
            "RECOVERY" in structural_state
            or "STRENGTHENING" in structural_state
        )
        and not contains_bearish(momentum)
    ):
        return "ACCUMULATION"

    # ------------------------------------------------------
    # DISTRIBUTION
    # ------------------------------------------------------

    if (
        negative_periods >= 2
        and (
            "LOSING STRENGTH" in structural_state
            or "STRENGTHENING" in structural_state
        )
        and not contains_bullish(momentum)
    ):
        return "DISTRIBUTION"

    # ------------------------------------------------------
    # BULLISH TRANSITION
    # ------------------------------------------------------

    if (
        contains_bearish(positioning)
        and contains_improving(momentum)
        and positive_periods >= 1
    ):
        return "BULLISH TRANSITION"

    # ------------------------------------------------------
    # BEARISH TRANSITION
    # ------------------------------------------------------

    if (
        contains_bullish(positioning)
        and contains_deteriorating(momentum)
        and negative_periods >= 1
    ):
        return "BEARISH TRANSITION"

    # ------------------------------------------------------
    # CONSOLIDATION
    # ------------------------------------------------------

    if (
        highest_scenario
        == "SIDEWAYS CONSOLIDATION"
        or (
            contains_mixed(
                decision_summary.institutional_alignment
            )
            and positive_periods == negative_periods
        )
    ):
        return "CONSOLIDATION"

    return "CONFLICTED TRANSITION"


# ==========================================================
# SECONDARY REGIME
# ==========================================================

def determine_secondary_regime(
    *,
    primary_regime: str,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
) -> str:
    """
    Determine a supporting secondary regime.
    """

    if primary_regime == "SHORT COVERING":
        return "BEARISH EXPOSURE REMAINS"

    if primary_regime == "LONG UNWINDING":
        return "BULLISH EXPOSURE REMAINS"

    if primary_regime == "ACCUMULATION":
        return "POSITIONAL IMPROVEMENT"

    if primary_regime == "DISTRIBUTION":
        return "POSITIONAL DETERIORATION"

    if primary_regime == "BULLISH CONTROL":
        return "BULLISH CONTINUATION"

    if primary_regime == "BEARISH CONTROL":
        return "BEARISH CONTINUATION"

    if primary_regime == "BULLISH TRANSITION":
        return "RECOVERY ATTEMPT"

    if primary_regime == "BEARISH TRANSITION":
        return "REVERSAL RISK"

    if primary_regime == "CONSOLIDATION":
        return "MIXED PARTICIPANT ALIGNMENT"

    return (
        probability_result
        .highest_probability_scenario
    )


# ==========================================================
# REGIME DIRECTION
# ==========================================================

def determine_regime_direction(
    primary_regime: str,
) -> str:
    """
    Convert the regime into a broad directional label.
    """

    bullish_regimes = {
        "BULLISH CONTROL",
        "ACCUMULATION",
        "SHORT COVERING",
        "BULLISH TRANSITION",
    }

    bearish_regimes = {
        "BEARISH CONTROL",
        "DISTRIBUTION",
        "LONG UNWINDING",
        "BEARISH TRANSITION",
    }

    if primary_regime in bullish_regimes:
        return "BULLISH"

    if primary_regime in bearish_regimes:
        return "BEARISH"

    return "NEUTRAL"


# ==========================================================
# REGIME STRENGTH
# ==========================================================

def determine_regime_strength(
    *,
    probability_result: InstitutionalProbabilityResult,
    decision_summary: ParticipantDecisionSummary,
) -> str:
    """
    Determine regime strength using probability and confidence.
    """

    highest_probability = (
        probability_result.highest_probability
    )

    confidence = (
        probability_result.probability_confidence
    )

    alignment = (
        decision_summary
        .institutional_alignment
        .upper()
    )

    if (
        highest_probability >= 55
        and confidence >= 70
        and "MIXED" not in alignment
    ):
        return "STRONG"

    if (
        highest_probability >= 40
        and confidence >= 55
    ):
        return "MODERATE"

    return "WEAK"


# ==========================================================
# REGIME MATURITY
# ==========================================================

def determine_regime_maturity(
    *,
    primary_regime: str,
    historical_result: ParticipantHistoricalResult,
) -> str:
    """
    Determine whether the regime is emerging or established.
    """

    positive_periods = count_positive_periods(
        historical_result
    )

    negative_periods = count_negative_periods(
        historical_result
    )

    transition_regimes = {
        "BULLISH TRANSITION",
        "BEARISH TRANSITION",
        "SHORT COVERING",
        "LONG UNWINDING",
        "CONFLICTED TRANSITION",
    }

    if primary_regime in transition_regimes:
        return "EMERGING"

    if (
        primary_regime
        in {
            "BULLISH CONTROL",
            "ACCUMULATION",
        }
        and positive_periods == 3
    ):
        return "ESTABLISHED"

    if (
        primary_regime
        in {
            "BEARISH CONTROL",
            "DISTRIBUTION",
        }
        and negative_periods == 3
    ):
        return "ESTABLISHED"

    if primary_regime == "CONSOLIDATION":
        return "MATURE"

    return "DEVELOPING"


# ==========================================================
# REGIME CONFIDENCE
# ==========================================================

def calculate_regime_confidence(
    *,
    probability_result: InstitutionalProbabilityResult,
    decision_summary: ParticipantDecisionSummary,
    historical_result: ParticipantHistoricalResult,
    primary_regime: str,
) -> int:
    """
    Calculate an explainable regime-confidence score.
    """

    score = (
        probability_result.probability_confidence
    )

    positive_periods = count_positive_periods(
        historical_result
    )

    negative_periods = count_negative_periods(
        historical_result
    )

    if (
        primary_regime
        in {
            "BULLISH CONTROL",
            "ACCUMULATION",
            "SHORT COVERING",
            "BULLISH TRANSITION",
        }
        and positive_periods >= 2
    ):
        score += 7

    if (
        primary_regime
        in {
            "BEARISH CONTROL",
            "DISTRIBUTION",
            "LONG UNWINDING",
            "BEARISH TRANSITION",
        }
        and negative_periods >= 2
    ):
        score += 7

    alignment = (
        decision_summary
        .institutional_alignment
        .upper()
    )

    if "FULL" in alignment:
        score += 8

    elif "MAJORITY" in alignment:
        score += 4

    elif "MIXED" in alignment:
        score -= 6

    risk = decision_summary.risk_level.upper()

    if risk == "HIGH":
        score -= 7

    elif risk == "MODERATE TO HIGH":
        score -= 4

    elif risk == "LOW":
        score += 5

    return max(
        0,
        min(score, 100),
    )


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    primary_regime: str,
) -> str:
    """
    Return expected participant-driven behaviour.
    """

    behaviour_map = {
        "BULLISH CONTROL": (
            "POSITIVE INSTITUTIONAL POSITIONING MAY CONTINUE "
            "TO SUPPORT THE MARKET"
        ),
        "BEARISH CONTROL": (
            "NEGATIVE INSTITUTIONAL POSITIONING MAY CONTINUE "
            "TO PRESSURE THE MARKET"
        ),
        "ACCUMULATION": (
            "GRADUAL POSITION BUILDING MAY SUPPORT FURTHER "
            "POSITIVE DEVELOPMENT"
        ),
        "DISTRIBUTION": (
            "GRADUAL POSITION REDUCTION OR SHORT BUILDING MAY "
            "CREATE DOWNWARD PRESSURE"
        ),
        "SHORT COVERING": (
            "RECOVERY MAY CONTINUE AS SHORT EXPOSURE IS REDUCED, "
            "BUT THE MOVE MAY REMAIN VULNERABLE"
        ),
        "LONG UNWINDING": (
            "PULLBACK OR WEAKNESS MAY CONTINUE AS LONG EXPOSURE "
            "IS REDUCED"
        ),
        "BULLISH TRANSITION": (
            "POSITIONING IS IMPROVING, BUT FULL BULLISH CONTROL "
            "IS NOT YET CONFIRMED"
        ),
        "BEARISH TRANSITION": (
            "POSITIONING IS DETERIORATING, BUT FULL BEARISH "
            "CONTROL IS NOT YET CONFIRMED"
        ),
        "CONSOLIDATION": (
            "RANGE-BOUND OR VOLATILE BEHAVIOUR MAY CONTINUE "
            "WITHOUT CLEAR INSTITUTIONAL CONTROL"
        ),
        "CONFLICTED TRANSITION": (
            "PARTICIPANT SIGNALS REMAIN CONFLICTED AND MAY "
            "PRODUCE UNSTABLE OR REVERSING PRICE BEHAVIOUR"
        ),
    }

    return behaviour_map.get(
        primary_regime,
        "NO CLEAR PARTICIPANT-DRIVEN BEHAVIOUR IS CONFIRMED",
    )


# ==========================================================
# ENVIRONMENT
# ==========================================================

def determine_environment(
    *,
    primary_regime: str,
    regime_strength: str,
    regime_maturity: str,
) -> str:
    """
    Build a compact participant-environment classification.
    """

    return (
        f"{regime_strength} "
        f"{regime_maturity} "
        f"{primary_regime}"
    )


# ==========================================================
# EXPLANATION
# ==========================================================

def build_explanation(
    *,
    primary_regime: str,
    secondary_regime: str,
    regime_direction: str,
    regime_strength: str,
    regime_maturity: str,
    regime_confidence: int,
    decision_summary: ParticipantDecisionSummary,
    historical_result: ParticipantHistoricalResult,
    probability_result: InstitutionalProbabilityResult,
) -> str:
    """
    Build the final explainable regime conclusion.
    """

    return (
        f"The participant regime is classified as "
        f"{primary_regime.lower()}, with "
        f"{secondary_regime.lower()} as the supporting condition. "
        f"Current institutional positioning is "
        f"{decision_summary.current_positioning.lower()}, while "
        f"momentum is {decision_summary.momentum.lower()}. "
        f"Institutional net positioning changed by "
        f"{format_change(historical_result.institutional_daily_net_change)} "
        f"over the daily period, "
        f"{format_change(historical_result.institutional_weekly_net_change)} "
        f"over the weekly period and "
        f"{format_change(historical_result.institutional_monthly_net_change)} "
        f"over the monthly period. "
        f"The highest probability scenario is "
        f"{probability_result.highest_probability_scenario.lower()} "
        f"at {probability_result.highest_probability:.1f}%. "
        f"The regime direction is {regime_direction.lower()}, "
        f"its strength is {regime_strength.lower()}, "
        f"and its maturity is {regime_maturity.lower()}. "
        f"Regime confidence is {regime_confidence}%."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_regime_engine(
    requested_date: date,
) -> ParticipantRegimeResult:
    """
    Run APD-012.
    """

    decision_summary = (
        run_participant_decision_summary(
            requested_date
        )
    )

    historical_result = (
        run_historical_change_engine(
            requested_date
        )
    )

    probability_result = (
        run_institutional_probability_engine(
            requested_date
        )
    )

    primary_regime = determine_primary_regime(
        decision_summary=decision_summary,
        historical_result=historical_result,
        probability_result=probability_result,
    )

    secondary_regime = determine_secondary_regime(
        primary_regime=primary_regime,
        decision_summary=decision_summary,
        probability_result=probability_result,
    )

    regime_direction = determine_regime_direction(
        primary_regime
    )

    regime_strength = determine_regime_strength(
        probability_result=probability_result,
        decision_summary=decision_summary,
    )

    regime_maturity = determine_regime_maturity(
        primary_regime=primary_regime,
        historical_result=historical_result,
    )

    regime_confidence = calculate_regime_confidence(
        probability_result=probability_result,
        decision_summary=decision_summary,
        historical_result=historical_result,
        primary_regime=primary_regime,
    )

    expected_behaviour = determine_expected_behaviour(
        primary_regime
    )

    environment = determine_environment(
        primary_regime=primary_regime,
        regime_strength=regime_strength,
        regime_maturity=regime_maturity,
    )

    explanation = build_explanation(
        primary_regime=primary_regime,
        secondary_regime=secondary_regime,
        regime_direction=regime_direction,
        regime_strength=regime_strength,
        regime_maturity=regime_maturity,
        regime_confidence=regime_confidence,
        decision_summary=decision_summary,
        historical_result=historical_result,
        probability_result=probability_result,
    )

    return ParticipantRegimeResult(
        requested_date=requested_date,
        analysis_date=decision_summary.analysis_date,
        current_positioning=(
            decision_summary.current_positioning
        ),
        momentum=decision_summary.momentum,
        structural_state=(
            decision_summary.structural_state
        ),
        institutional_alignment=(
            decision_summary.institutional_alignment
        ),
        daily_net_change=(
            historical_result
            .institutional_daily_net_change
        ),
        weekly_net_change=(
            historical_result
            .institutional_weekly_net_change
        ),
        monthly_net_change=(
            historical_result
            .institutional_monthly_net_change
        ),
        highest_probability_scenario=(
            probability_result
            .highest_probability_scenario
        ),
        highest_probability=(
            probability_result.highest_probability
        ),
        probability_confidence=(
            probability_result.probability_confidence
        ),
        primary_regime=primary_regime,
        secondary_regime=secondary_regime,
        regime_direction=regime_direction,
        regime_strength=regime_strength,
        regime_maturity=regime_maturity,
        risk_level=decision_summary.risk_level,
        expected_behaviour=expected_behaviour,
        environment=environment,
        regime_confidence=regime_confidence,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantRegimeResult,
) -> None:
    """
    Display the APD-012 terminal report.
    """

    print()
    print("=" * 92)
    print("AQSD PARTICIPANT REGIME ENGINE")
    print("=" * 92)
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Requested Date             : {result.requested_date}")
    print(f"Analysis Date              : {result.analysis_date}")
    print("-" * 92)
    print(
        f"Current Positioning        : "
        f"{result.current_positioning}"
    )
    print(
        f"Momentum                   : "
        f"{result.momentum}"
    )
    print(
        f"Structural State           : "
        f"{result.structural_state}"
    )
    print(
        f"Institutional Alignment    : "
        f"{result.institutional_alignment}"
    )
    print("-" * 92)
    print(
        f"Daily Net Change           : "
        f"{format_change(result.daily_net_change)}"
    )
    print(
        f"Weekly Net Change          : "
        f"{format_change(result.weekly_net_change)}"
    )
    print(
        f"Monthly Net Change         : "
        f"{format_change(result.monthly_net_change)}"
    )
    print("-" * 92)
    print(
        f"Highest Probability        : "
        f"{result.highest_probability_scenario}"
    )
    print(
        f"Probability Value          : "
        f"{result.highest_probability:.1f}%"
    )
    print(
        f"Probability Confidence     : "
        f"{result.probability_confidence}%"
    )
    print("=" * 92)
    print("REGIME CLASSIFICATION")
    print("-" * 92)
    print(
        f"Primary Regime             : "
        f"{result.primary_regime}"
    )
    print(
        f"Secondary Regime           : "
        f"{result.secondary_regime}"
    )
    print(
        f"Regime Direction           : "
        f"{result.regime_direction}"
    )
    print(
        f"Regime Strength            : "
        f"{result.regime_strength}"
    )
    print(
        f"Regime Maturity            : "
        f"{result.regime_maturity}"
    )
    print(
        f"Regime Confidence          : "
        f"{result.regime_confidence}%"
    )
    print(
        f"Risk Level                 : "
        f"{result.risk_level}"
    )
    print(
        f"Environment                : "
        f"{result.environment}"
    )
    print("-" * 92)
    print(
        f"Expected Behaviour         : "
        f"{result.expected_behaviour}"
    )
    print("-" * 92)
    print("EXPLANATION")
    print("-" * 92)
    print(result.explanation)
    print("-" * 92)
    print(f"Status                     : {result.status}")
    print("=" * 92)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Classify the prevailing institutional participant "
            "regime from APD intelligence."
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
        result = run_participant_regime_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 92)
        print("AQSD PARTICIPANT REGIME ENGINE")
        print("=" * 92)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 92)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()