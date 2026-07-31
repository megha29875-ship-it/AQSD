"""
AQSD
Participant Cycle Engine

Module : APD-013
Version: 1.0.0
Author : AQSD

Description
-----------
Classifies the institutional participant cycle using the outputs of:

- Participant Historical Change Engine
- Participant Decision Summary Engine
- Institutional Probability Engine
- Participant Regime Engine

Supported cycle phases
----------------------
- EARLY ACCUMULATION
- LATE ACCUMULATION
- MARKUP
- DISTRIBUTION
- LONG LIQUIDATION
- SHORT BUILD-UP
- CAPITULATION
- RECOVERY
- RE-ACCUMULATION
- RE-DISTRIBUTION
- CONSOLIDATION
- TRANSITION

Outputs
-------
- Current cycle
- Previous inferred cycle
- Next probable cycle
- Cycle direction
- Cycle strength
- Cycle maturity
- Cycle confidence
- Expected duration
- Risk level
- Expected behaviour
- Explanation

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
from Scripts.aqsd_intelligence.participant_regime_engine import (
    ParticipantRegimeResult,
    run_participant_regime_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-013"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantCycleResult:
    """
    Complete APD-013 participant-cycle result.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    institutional_alignment: str

    primary_regime: str
    regime_strength: str
    regime_maturity: str
    regime_confidence: int

    highest_probability_scenario: str
    highest_probability: float
    probability_confidence: int

    daily_net_change: float | None
    weekly_net_change: float | None
    monthly_net_change: float | None

    current_cycle: str
    previous_cycle: str
    next_probable_cycle: str

    cycle_direction: str
    cycle_strength: str
    cycle_maturity: str
    cycle_confidence: int
    expected_duration: str

    risk_level: str
    expected_behaviour: str
    environment: str
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


# ==========================================================
# CHANGE HELPERS
# ==========================================================

def change_direction(
    value: float | None,
) -> int:
    """
    Convert an optional change into:

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


def count_positive_periods(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count positive institutional net-change periods.
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
    Count negative institutional net-change periods.
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


def format_change(
    value: float | None,
) -> str:
    """
    Format an optional net-position change.
    """

    if value is None:
        return "NOT AVAILABLE"

    return f"{value:+,.0f}"


# ==========================================================
# CURRENT CYCLE
# ==========================================================

def determine_current_cycle(
    *,
    decision_summary: ParticipantDecisionSummary,
    historical_result: ParticipantHistoricalResult,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Determine the current institutional participant cycle.
    """

    positioning = (
        decision_summary.current_positioning.upper()
    )

    momentum = decision_summary.momentum.upper()

    regime = regime_result.primary_regime.upper()

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
    # RECOVERY
    # ------------------------------------------------------

    if (
        regime == "SHORT COVERING"
        and contains_bearish(positioning)
        and contains_improving(momentum)
    ):
        return "RECOVERY"

    # ------------------------------------------------------
    # LONG LIQUIDATION
    # ------------------------------------------------------

    if (
        regime == "LONG UNWINDING"
        and contains_bullish(positioning)
        and contains_deteriorating(momentum)
    ):
        return "LONG LIQUIDATION"

    # ------------------------------------------------------
    # EARLY ACCUMULATION
    # ------------------------------------------------------

    if (
        regime in {
            "ACCUMULATION",
            "BULLISH TRANSITION",
        }
        and positive_periods >= 2
        and contains_bearish(positioning)
    ):
        return "EARLY ACCUMULATION"

    # ------------------------------------------------------
    # LATE ACCUMULATION
    # ------------------------------------------------------

    if (
        regime == "ACCUMULATION"
        and positive_periods == 3
        and contains_bullish(positioning)
        and highest_scenario
        in {
            "BULLISH CONTINUATION",
            "BULLISH RECOVERY",
        }
    ):
        return "LATE ACCUMULATION"

    # ------------------------------------------------------
    # MARKUP
    # ------------------------------------------------------

    if (
        regime == "BULLISH CONTROL"
        and contains_bullish(positioning)
        and contains_improving(momentum)
        and highest_scenario
        == "BULLISH CONTINUATION"
    ):
        return "MARKUP"

    # ------------------------------------------------------
    # DISTRIBUTION
    # ------------------------------------------------------

    if (
        regime == "DISTRIBUTION"
        and negative_periods >= 2
        and contains_bullish(positioning)
    ):
        return "DISTRIBUTION"

    # ------------------------------------------------------
    # SHORT BUILD-UP
    # ------------------------------------------------------

    if (
        regime in {
            "BEARISH CONTROL",
            "BEARISH TRANSITION",
        }
        and contains_bearish(positioning)
        and contains_deteriorating(momentum)
        and negative_periods >= 2
    ):
        return "SHORT BUILD-UP"

    # ------------------------------------------------------
    # CAPITULATION
    # ------------------------------------------------------

    if (
        regime == "BEARISH CONTROL"
        and contains_bearish(positioning)
        and contains_deteriorating(momentum)
        and negative_periods == 3
        and probability_result.highest_probability >= 55
    ):
        return "CAPITULATION"

    # ------------------------------------------------------
    # RE-ACCUMULATION
    # ------------------------------------------------------

    if (
        regime == "ACCUMULATION"
        and contains_bullish(positioning)
        and positive_periods >= 2
        and probability_result.bullish_continuation_probability
        >= probability_result.bullish_recovery_probability
    ):
        return "RE-ACCUMULATION"

    # ------------------------------------------------------
    # RE-DISTRIBUTION
    # ------------------------------------------------------

    if (
        regime == "DISTRIBUTION"
        and contains_bearish(positioning)
        and negative_periods >= 2
        and probability_result.bearish_continuation_probability
        >= probability_result.bearish_reversal_probability
    ):
        return "RE-DISTRIBUTION"

    # ------------------------------------------------------
    # CONSOLIDATION
    # ------------------------------------------------------

    if regime == "CONSOLIDATION":
        return "CONSOLIDATION"

    return "TRANSITION"


# ==========================================================
# PREVIOUS CYCLE
# ==========================================================

def determine_previous_cycle(
    current_cycle: str,
) -> str:
    """
    Infer the most likely preceding cycle phase.
    """

    previous_cycle_map = {
        "EARLY ACCUMULATION": "CAPITULATION",
        "LATE ACCUMULATION": "EARLY ACCUMULATION",
        "MARKUP": "LATE ACCUMULATION",
        "DISTRIBUTION": "MARKUP",
        "LONG LIQUIDATION": "DISTRIBUTION",
        "SHORT BUILD-UP": "LONG LIQUIDATION",
        "CAPITULATION": "SHORT BUILD-UP",
        "RECOVERY": "CAPITULATION",
        "RE-ACCUMULATION": "CONSOLIDATION",
        "RE-DISTRIBUTION": "CONSOLIDATION",
        "CONSOLIDATION": "TRANSITION",
        "TRANSITION": "UNKNOWN",
    }

    return previous_cycle_map.get(
        current_cycle,
        "UNKNOWN",
    )


# ==========================================================
# NEXT PROBABLE CYCLE
# ==========================================================

def determine_next_probable_cycle(
    *,
    current_cycle: str,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Determine the next probable cycle phase.
    """

    highest_scenario = (
        probability_result
        .highest_probability_scenario
        .upper()
    )

    next_cycle_map = {
        "EARLY ACCUMULATION": "LATE ACCUMULATION",
        "LATE ACCUMULATION": "MARKUP",
        "MARKUP": "DISTRIBUTION",
        "DISTRIBUTION": "LONG LIQUIDATION",
        "LONG LIQUIDATION": "SHORT BUILD-UP",
        "SHORT BUILD-UP": "CAPITULATION",
        "CAPITULATION": "RECOVERY",
        "RECOVERY": "RE-ACCUMULATION",
        "RE-ACCUMULATION": "MARKUP",
        "RE-DISTRIBUTION": "SHORT BUILD-UP",
        "CONSOLIDATION": "TRANSITION",
        "TRANSITION": "CONSOLIDATION",
    }

    default_next = next_cycle_map.get(
        current_cycle,
        "TRANSITION",
    )

    if (
        current_cycle == "RECOVERY"
        and highest_scenario == "BULLISH RECOVERY"
    ):
        return "RE-ACCUMULATION"

    if (
        current_cycle == "RECOVERY"
        and highest_scenario == "BEARISH CONTINUATION"
    ):
        return "SHORT BUILD-UP"

    if (
        current_cycle == "CONSOLIDATION"
        and highest_scenario == "BULLISH CONTINUATION"
    ):
        return "RE-ACCUMULATION"

    if (
        current_cycle == "CONSOLIDATION"
        and highest_scenario == "BEARISH CONTINUATION"
    ):
        return "RE-DISTRIBUTION"

    if (
        regime_result.primary_regime
        == "CONFLICTED TRANSITION"
    ):
        return "CONSOLIDATION"

    return default_next


# ==========================================================
# CYCLE DIRECTION
# ==========================================================

def determine_cycle_direction(
    current_cycle: str,
) -> str:
    """
    Convert the cycle into a broad directional classification.
    """

    bullish_cycles = {
        "EARLY ACCUMULATION",
        "LATE ACCUMULATION",
        "MARKUP",
        "RECOVERY",
        "RE-ACCUMULATION",
    }

    bearish_cycles = {
        "DISTRIBUTION",
        "LONG LIQUIDATION",
        "SHORT BUILD-UP",
        "CAPITULATION",
        "RE-DISTRIBUTION",
    }

    if current_cycle in bullish_cycles:
        return "BULLISH"

    if current_cycle in bearish_cycles:
        return "BEARISH"

    return "NEUTRAL"


# ==========================================================
# CYCLE STRENGTH
# ==========================================================

def determine_cycle_strength(
    *,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Determine cycle strength.
    """

    combined_confidence = round(
        (
            probability_result.probability_confidence
            + regime_result.regime_confidence
        )
        / 2
    )

    if (
        probability_result.highest_probability >= 55
        and combined_confidence >= 70
        and regime_result.regime_strength == "STRONG"
    ):
        return "STRONG"

    if (
        probability_result.highest_probability >= 40
        and combined_confidence >= 55
    ):
        return "MODERATE"

    return "WEAK"


# ==========================================================
# CYCLE MATURITY
# ==========================================================

def determine_cycle_maturity(
    *,
    current_cycle: str,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Determine the maturity of the current cycle.
    """

    early_cycles = {
        "EARLY ACCUMULATION",
        "RECOVERY",
        "LONG LIQUIDATION",
        "TRANSITION",
    }

    developing_cycles = {
        "LATE ACCUMULATION",
        "DISTRIBUTION",
        "SHORT BUILD-UP",
        "RE-ACCUMULATION",
        "RE-DISTRIBUTION",
    }

    mature_cycles = {
        "MARKUP",
        "CAPITULATION",
        "CONSOLIDATION",
    }

    if current_cycle in early_cycles:
        return "EARLY"

    if current_cycle in developing_cycles:
        return "DEVELOPING"

    if current_cycle in mature_cycles:
        return "MATURE"

    return regime_result.regime_maturity


# ==========================================================
# CYCLE CONFIDENCE
# ==========================================================

def calculate_cycle_confidence(
    *,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    decision_summary: ParticipantDecisionSummary,
    current_cycle: str,
) -> int:
    """
    Calculate cycle confidence from 0 to 100.
    """

    score = round(
        (
            probability_result.probability_confidence
            + regime_result.regime_confidence
            + decision_summary.confidence
        )
        / 3
    )

    if current_cycle not in {
        "TRANSITION",
        "CONSOLIDATION",
    }:
        score += 5

    if (
        probability_result.highest_probability
        >= 50
    ):
        score += 4

    alignment = (
        decision_summary
        .institutional_alignment
        .upper()
    )

    if "FULL" in alignment:
        score += 7

    elif "MAJORITY" in alignment:
        score += 3

    elif "MIXED" in alignment:
        score -= 5

    risk = decision_summary.risk_level.upper()

    if risk == "HIGH":
        score -= 6

    elif risk == "MODERATE TO HIGH":
        score -= 3

    elif risk == "LOW":
        score += 4

    return max(
        0,
        min(score, 100),
    )


# ==========================================================
# EXPECTED DURATION
# ==========================================================

def determine_expected_duration(
    *,
    current_cycle: str,
    cycle_strength: str,
    cycle_maturity: str,
) -> str:
    """
    Estimate a broad analytical duration range.
    """

    if current_cycle in {
        "RECOVERY",
        "LONG LIQUIDATION",
        "TRANSITION",
    }:
        return "2-5 TRADING DAYS"

    if current_cycle in {
        "EARLY ACCUMULATION",
        "LATE ACCUMULATION",
        "SHORT BUILD-UP",
        "DISTRIBUTION",
    }:
        return "3-10 TRADING DAYS"

    if current_cycle in {
        "MARKUP",
        "RE-ACCUMULATION",
        "RE-DISTRIBUTION",
    }:
        return "1-4 TRADING WEEKS"

    if current_cycle == "CAPITULATION":
        return "1-3 TRADING DAYS"

    if current_cycle == "CONSOLIDATION":
        if cycle_strength == "WEAK":
            return "2-7 TRADING DAYS"

        return "1-3 TRADING WEEKS"

    if cycle_maturity == "EARLY":
        return "2-5 TRADING DAYS"

    return "DURATION UNCERTAIN"


# ==========================================================
# RISK LEVEL
# ==========================================================

def determine_cycle_risk(
    *,
    decision_summary: ParticipantDecisionSummary,
    current_cycle: str,
    cycle_confidence: int,
) -> str:
    """
    Determine cycle-level risk.
    """

    if cycle_confidence < 45:
        return "HIGH"

    if current_cycle in {
        "TRANSITION",
        "RECOVERY",
        "LONG LIQUIDATION",
        "CAPITULATION",
    }:
        return "HIGH"

    if (
        decision_summary.risk_level
        in {
            "HIGH",
            "MODERATE TO HIGH",
        }
    ):
        return decision_summary.risk_level

    if cycle_confidence >= 70:
        return "LOW TO MODERATE"

    return "MODERATE"


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    current_cycle: str,
) -> str:
    """
    Return expected behaviour for the current cycle.
    """

    behaviour_map = {
        "EARLY ACCUMULATION": (
            "INSTITUTIONAL POSITIONING MAY CONTINUE TO IMPROVE, "
            "BUT PRICE CONFIRMATION MAY REMAIN INCOMPLETE"
        ),
        "LATE ACCUMULATION": (
            "POSITIVE POSITION BUILDING MAY PRECEDE A MORE "
            "SUSTAINED MARKUP PHASE"
        ),
        "MARKUP": (
            "POSITIVE INSTITUTIONAL CONTROL MAY SUPPORT "
            "CONTINUED UPWARD DEVELOPMENT"
        ),
        "DISTRIBUTION": (
            "INSTITUTIONS MAY CONTINUE REDUCING LONG EXPOSURE "
            "OR BUILDING DEFENSIVE POSITIONS"
        ),
        "LONG LIQUIDATION": (
            "WEAKNESS MAY CONTINUE AS EXISTING LONG EXPOSURE "
            "IS REDUCED"
        ),
        "SHORT BUILD-UP": (
            "NEGATIVE POSITIONING MAY CONTINUE TO CREATE "
            "DOWNWARD PRESSURE"
        ),
        "CAPITULATION": (
            "EXTREME NEGATIVE POSITIONING MAY CREATE SHARP "
            "VOLATILITY AND REVERSAL RISK"
        ),
        "RECOVERY": (
            "SHORT COVERING OR RECOVERY MAY CONTINUE, "
            "BUT BEARISH EXPOSURE REMAINS A VULNERABILITY"
        ),
        "RE-ACCUMULATION": (
            "INSTITUTIONS MAY CONSOLIDATE AND REBUILD POSITIVE "
            "EXPOSURE BEFORE ANOTHER MARKUP ATTEMPT"
        ),
        "RE-DISTRIBUTION": (
            "INSTITUTIONS MAY CONSOLIDATE BEFORE RENEWED "
            "NEGATIVE POSITIONING"
        ),
        "CONSOLIDATION": (
            "RANGE-BOUND OR VOLATILE PRICE BEHAVIOUR MAY "
            "CONTINUE UNTIL PARTICIPANT ALIGNMENT IMPROVES"
        ),
        "TRANSITION": (
            "THE PARTICIPANT CYCLE IS CHANGING AND PRICE "
            "BEHAVIOUR MAY REMAIN UNSTABLE"
        ),
    }

    return behaviour_map.get(
        current_cycle,
        "NO CLEAR PARTICIPANT-CYCLE BEHAVIOUR IS CONFIRMED",
    )


# ==========================================================
# ENVIRONMENT
# ==========================================================

def determine_environment(
    *,
    current_cycle: str,
    cycle_strength: str,
    cycle_maturity: str,
) -> str:
    """
    Build a concise cycle environment label.
    """

    return (
        f"{cycle_strength} "
        f"{cycle_maturity} "
        f"{current_cycle}"
    )


# ==========================================================
# EXPLANATION
# ==========================================================

def build_explanation(
    *,
    current_cycle: str,
    previous_cycle: str,
    next_probable_cycle: str,
    cycle_direction: str,
    cycle_strength: str,
    cycle_maturity: str,
    cycle_confidence: int,
    expected_duration: str,
    historical_result: ParticipantHistoricalResult,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Build the final participant-cycle explanation.
    """

    return (
        f"The participant cycle is classified as "
        f"{current_cycle.lower()}. The inferred previous cycle was "
        f"{previous_cycle.lower()}, while the next probable cycle is "
        f"{next_probable_cycle.lower()}. "
        f"The current regime is "
        f"{regime_result.primary_regime.lower()} with "
        f"{regime_result.secondary_regime.lower()} as the supporting "
        f"condition. Institutional net positioning changed by "
        f"{format_change(historical_result.institutional_daily_net_change)} "
        f"over the daily period, "
        f"{format_change(historical_result.institutional_weekly_net_change)} "
        f"over the weekly period and "
        f"{format_change(historical_result.institutional_monthly_net_change)} "
        f"over the monthly period. "
        f"The highest probability scenario is "
        f"{probability_result.highest_probability_scenario.lower()} "
        f"at {probability_result.highest_probability:.1f}%. "
        f"The cycle direction is {cycle_direction.lower()}, "
        f"its strength is {cycle_strength.lower()}, "
        f"its maturity is {cycle_maturity.lower()}, and "
        f"cycle confidence is {cycle_confidence}%. "
        f"The expected analytical duration is "
        f"{expected_duration.lower()}."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_cycle_engine(
    requested_date: date,
) -> ParticipantCycleResult:
    """
    Run APD-013.
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

    regime_result = (
        run_participant_regime_engine(
            requested_date
        )
    )

    current_cycle = determine_current_cycle(
        decision_summary=decision_summary,
        historical_result=historical_result,
        probability_result=probability_result,
        regime_result=regime_result,
    )

    previous_cycle = determine_previous_cycle(
        current_cycle
    )

    next_probable_cycle = (
        determine_next_probable_cycle(
            current_cycle=current_cycle,
            probability_result=probability_result,
            regime_result=regime_result,
        )
    )

    cycle_direction = determine_cycle_direction(
        current_cycle
    )

    cycle_strength = determine_cycle_strength(
        probability_result=probability_result,
        regime_result=regime_result,
    )

    cycle_maturity = determine_cycle_maturity(
        current_cycle=current_cycle,
        regime_result=regime_result,
    )

    cycle_confidence = calculate_cycle_confidence(
        probability_result=probability_result,
        regime_result=regime_result,
        decision_summary=decision_summary,
        current_cycle=current_cycle,
    )

    expected_duration = determine_expected_duration(
        current_cycle=current_cycle,
        cycle_strength=cycle_strength,
        cycle_maturity=cycle_maturity,
    )

    risk_level = determine_cycle_risk(
        decision_summary=decision_summary,
        current_cycle=current_cycle,
        cycle_confidence=cycle_confidence,
    )

    expected_behaviour = determine_expected_behaviour(
        current_cycle
    )

    environment = determine_environment(
        current_cycle=current_cycle,
        cycle_strength=cycle_strength,
        cycle_maturity=cycle_maturity,
    )

    explanation = build_explanation(
        current_cycle=current_cycle,
        previous_cycle=previous_cycle,
        next_probable_cycle=next_probable_cycle,
        cycle_direction=cycle_direction,
        cycle_strength=cycle_strength,
        cycle_maturity=cycle_maturity,
        cycle_confidence=cycle_confidence,
        expected_duration=expected_duration,
        historical_result=historical_result,
        probability_result=probability_result,
        regime_result=regime_result,
    )

    return ParticipantCycleResult(
        requested_date=requested_date,
        analysis_date=decision_summary.analysis_date,
        current_positioning=(
            decision_summary.current_positioning
        ),
        momentum=decision_summary.momentum,
        institutional_alignment=(
            decision_summary.institutional_alignment
        ),
        primary_regime=regime_result.primary_regime,
        regime_strength=regime_result.regime_strength,
        regime_maturity=regime_result.regime_maturity,
        regime_confidence=regime_result.regime_confidence,
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
        current_cycle=current_cycle,
        previous_cycle=previous_cycle,
        next_probable_cycle=next_probable_cycle,
        cycle_direction=cycle_direction,
        cycle_strength=cycle_strength,
        cycle_maturity=cycle_maturity,
        cycle_confidence=cycle_confidence,
        expected_duration=expected_duration,
        risk_level=risk_level,
        expected_behaviour=expected_behaviour,
        environment=environment,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantCycleResult,
) -> None:
    """
    Display the APD-013 terminal report.
    """

    print()
    print("=" * 92)
    print("AQSD PARTICIPANT CYCLE ENGINE")
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
        f"Institutional Alignment    : "
        f"{result.institutional_alignment}"
    )
    print("-" * 92)
    print(
        f"Primary Regime             : "
        f"{result.primary_regime}"
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
    print("=" * 92)
    print("CYCLE CLASSIFICATION")
    print("-" * 92)
    print(
        f"Current Cycle              : "
        f"{result.current_cycle}"
    )
    print(
        f"Previous Cycle             : "
        f"{result.previous_cycle}"
    )
    print(
        f"Next Probable Cycle        : "
        f"{result.next_probable_cycle}"
    )
    print(
        f"Cycle Direction            : "
        f"{result.cycle_direction}"
    )
    print(
        f"Cycle Strength             : "
        f"{result.cycle_strength}"
    )
    print(
        f"Cycle Maturity             : "
        f"{result.cycle_maturity}"
    )
    print(
        f"Cycle Confidence           : "
        f"{result.cycle_confidence}%"
    )
    print(
        f"Expected Duration          : "
        f"{result.expected_duration}"
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
            "Classify the current institutional participant cycle "
            "from APD intelligence."
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
        result = run_participant_cycle_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 92)
        print("AQSD PARTICIPANT CYCLE ENGINE")
        print("=" * 92)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 92)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()