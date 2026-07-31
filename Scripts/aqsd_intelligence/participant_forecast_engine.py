"""
AQSD
Participant Forecast Engine

Module : APD-015
Version: 1.0.0
Author : AQSD

Description
-----------
Creates a multi-horizon institutional participant forecast using:

- Participant Historical Change Engine
- Participant Decision Summary Engine
- Institutional Probability Engine
- Participant Regime Engine
- Participant Cycle Engine
- Participant Risk Engine

Forecast horizons
-----------------
- Next Trading Session
- Next 2-3 Trading Sessions
- Next Trading Week
- Positional / Monthly Outlook

Outputs
-------
- Directional forecast for every horizon
- Bullish, bearish and neutral probabilities
- Primary scenario
- Secondary scenario
- Failure scenario
- Expected volatility
- Expected institutional behaviour
- Forecast confidence
- Forecast risk
- Invalidating conditions
- Explainable conclusion

Important
---------
This engine produces analytical forecasts only.

The probabilities are rule-based analytical estimates. They are not
statistically calibrated forecasts.

The engine does not generate BUY, SELL or SHORT instructions.
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
from Scripts.aqsd_intelligence.participant_cycle_engine import (
    ParticipantCycleResult,
    run_participant_cycle_engine,
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
from Scripts.aqsd_intelligence.participant_risk_engine import (
    ParticipantRiskResult,
    run_participant_risk_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-015"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class ForecastHorizon:
    """
    Forecast for one analytical time horizon.
    """

    horizon: str
    direction: str
    scenario: str

    bullish_probability: float
    bearish_probability: float
    neutral_probability: float

    confidence: int
    risk_level: str
    expected_behaviour: str
    explanation: str


@dataclass(frozen=True)
class ParticipantForecastResult:
    """
    Complete APD-015 participant forecast.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    institutional_alignment: str

    primary_regime: str
    current_cycle: str
    next_probable_cycle: str

    highest_probability_scenario: str
    highest_probability: float
    probability_confidence: int

    overall_risk_score: int
    overall_risk_level: str
    dominant_risk: str

    next_session: ForecastHorizon
    next_two_three_sessions: ForecastHorizon
    weekly: ForecastHorizon
    positional: ForecastHorizon

    primary_forecast: str
    secondary_forecast: str
    failure_scenario: str

    expected_volatility: str
    expected_institutional_behaviour: str
    forecast_environment: str

    forecast_confidence: int
    forecast_risk: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]

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
    Return True when evidence is mixed.
    """

    return "MIXED" in value.upper()


# ==========================================================
# NUMBER HELPERS
# ==========================================================

def clamp_percentage(value: float) -> float:
    """
    Restrict a percentage to 0-100.
    """

    return max(
        0.0,
        min(
            round(value, 1),
            100.0,
        ),
    )


def clamp_score(value: float) -> int:
    """
    Restrict an integer score to 0-100.
    """

    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


def normalize_three_probabilities(
    *,
    bullish: float,
    bearish: float,
    neutral: float,
) -> tuple[float, float, float]:
    """
    Normalize three positive values so that they total 100.
    """

    bullish = max(bullish, 0.1)
    bearish = max(bearish, 0.1)
    neutral = max(neutral, 0.1)

    total = bullish + bearish + neutral

    bullish_probability = round(
        bullish / total * 100,
        1,
    )

    bearish_probability = round(
        bearish / total * 100,
        1,
    )

    neutral_probability = round(
        neutral / total * 100,
        1,
    )

    difference = round(
        100.0
        - bullish_probability
        - bearish_probability
        - neutral_probability,
        1,
    )

    values = {
        "BULLISH": bullish_probability,
        "BEARISH": bearish_probability,
        "NEUTRAL": neutral_probability,
    }

    highest_key = max(
        values,
        key=values.get,
    )

    values[highest_key] = round(
        values[highest_key] + difference,
        1,
    )

    return (
        values["BULLISH"],
        values["BEARISH"],
        values["NEUTRAL"],
    )


def change_direction(value: float | None) -> int:
    """
    Convert a net-position change into a signed direction.
    """

    if value is None:
        return 0

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def risk_level_from_score(score: int) -> str:
    """
    Convert a score into a forecast-risk label.
    """

    if score >= 80:
        return "VERY HIGH"

    if score >= 65:
        return "HIGH"

    if score >= 45:
        return "MODERATE"

    if score >= 25:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# DIRECTION HELPERS
# ==========================================================

def direction_from_probabilities(
    *,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> str:
    """
    Determine the leading direction.
    """

    values = {
        "BULLISH": bullish_probability,
        "BEARISH": bearish_probability,
        "NEUTRAL": neutral_probability,
    }

    ordered = sorted(
        values.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    leading_direction = ordered[0][0]
    leading_probability = ordered[0][1]
    second_probability = ordered[1][1]

    separation = leading_probability - second_probability

    if separation < 7:
        return "MIXED"

    return leading_direction


def scenario_from_direction(
    *,
    direction: str,
    cycle_result: ParticipantCycleResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Build a scenario label from direction, cycle and regime.
    """

    if direction == "BULLISH":
        if cycle_result.current_cycle == "RECOVERY":
            return "BULLISH RECOVERY"

        if cycle_result.current_cycle in {
            "EARLY ACCUMULATION",
            "LATE ACCUMULATION",
            "RE-ACCUMULATION",
        }:
            return "BULLISH ACCUMULATION"

        return "BULLISH CONTINUATION"

    if direction == "BEARISH":
        if cycle_result.current_cycle in {
            "LONG LIQUIDATION",
            "DISTRIBUTION",
        }:
            return "BEARISH DETERIORATION"

        if cycle_result.current_cycle == "CAPITULATION":
            return "BEARISH CAPITULATION"

        return "BEARISH CONTINUATION"

    if regime_result.primary_regime == "CONSOLIDATION":
        return "SIDEWAYS CONSOLIDATION"

    return "CONFLICTED TRANSITION"


# ==========================================================
# NEXT-SESSION PROBABILITIES
# ==========================================================

def calculate_next_session_probabilities(
    *,
    probability_result: InstitutionalProbabilityResult,
    historical_result: ParticipantHistoricalResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
) -> tuple[float, float, float]:
    """
    Calculate the next-session directional probabilities.
    """

    bullish = (
        probability_result.bullish_continuation_probability
        + probability_result.bullish_recovery_probability
    )

    bearish = (
        probability_result.bearish_continuation_probability
        + probability_result.bearish_reversal_probability
    )

    neutral = probability_result.sideways_probability

    daily_direction = change_direction(
        historical_result.institutional_daily_net_change
    )

    if daily_direction > 0:
        bullish += 8
        bearish -= 3

    elif daily_direction < 0:
        bearish += 8
        bullish -= 3

    if cycle_result.current_cycle == "RECOVERY":
        bullish += 7
        neutral += 2

    elif cycle_result.current_cycle in {
        "SHORT BUILD-UP",
        "LONG LIQUIDATION",
    }:
        bearish += 7

    if risk_result.overall_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        neutral += 7

    return normalize_three_probabilities(
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
    )


# ==========================================================
# 2-3 SESSION PROBABILITIES
# ==========================================================

def calculate_short_term_probabilities(
    *,
    probability_result: InstitutionalProbabilityResult,
    historical_result: ParticipantHistoricalResult,
    cycle_result: ParticipantCycleResult,
    regime_result: ParticipantRegimeResult,
    risk_result: ParticipantRiskResult,
) -> tuple[float, float, float]:
    """
    Calculate probabilities for the next 2-3 trading sessions.
    """

    bullish = (
        probability_result.bullish_continuation_probability
        + probability_result.bullish_recovery_probability
    )

    bearish = (
        probability_result.bearish_continuation_probability
        + probability_result.bearish_reversal_probability
    )

    neutral = probability_result.sideways_probability

    daily_direction = change_direction(
        historical_result.institutional_daily_net_change
    )

    weekly_direction = change_direction(
        historical_result.institutional_weekly_net_change
    )

    if daily_direction > 0:
        bullish += 5

    elif daily_direction < 0:
        bearish += 5

    if weekly_direction > 0:
        bullish += 10

    elif weekly_direction < 0:
        bearish += 10

    if regime_result.primary_regime == "SHORT COVERING":
        bullish += 8
        neutral += 3

    elif regime_result.primary_regime == "LONG UNWINDING":
        bearish += 8

    if cycle_result.next_probable_cycle == "RE-ACCUMULATION":
        bullish += 6

    elif cycle_result.next_probable_cycle in {
        "SHORT BUILD-UP",
        "RE-DISTRIBUTION",
    }:
        bearish += 6

    if risk_result.overall_risk_score >= 70:
        neutral += 8

    return normalize_three_probabilities(
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
    )


# ==========================================================
# WEEKLY PROBABILITIES
# ==========================================================

def calculate_weekly_probabilities(
    *,
    probability_result: InstitutionalProbabilityResult,
    historical_result: ParticipantHistoricalResult,
    cycle_result: ParticipantCycleResult,
    decision_summary: ParticipantDecisionSummary,
) -> tuple[float, float, float]:
    """
    Calculate the next-week directional probabilities.
    """

    bullish = 30.0
    bearish = 30.0
    neutral = 20.0

    weekly_direction = change_direction(
        historical_result.institutional_weekly_net_change
    )

    monthly_direction = change_direction(
        historical_result.institutional_monthly_net_change
    )

    if weekly_direction > 0:
        bullish += 15

    elif weekly_direction < 0:
        bearish += 15

    if monthly_direction > 0:
        bullish += 12

    elif monthly_direction < 0:
        bearish += 12

    if contains_bullish(decision_summary.momentum):
        bullish += 8

    if contains_improving(decision_summary.momentum):
        bullish += 8

    if contains_bearish(decision_summary.momentum):
        bearish += 8

    if contains_deteriorating(decision_summary.momentum):
        bearish += 8

    if cycle_result.next_probable_cycle in {
        "RE-ACCUMULATION",
        "MARKUP",
        "LATE ACCUMULATION",
    }:
        bullish += 12

    elif cycle_result.next_probable_cycle in {
        "SHORT BUILD-UP",
        "RE-DISTRIBUTION",
        "LONG LIQUIDATION",
    }:
        bearish += 12

    if contains_mixed(
        decision_summary.institutional_alignment
    ):
        neutral += 10

    bullish += (
        probability_result.bullish_recovery_probability
        * 0.15
    )

    bearish += (
        probability_result.bearish_continuation_probability
        * 0.15
    )

    return normalize_three_probabilities(
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
    )


# ==========================================================
# POSITIONAL PROBABILITIES
# ==========================================================

def calculate_positional_probabilities(
    *,
    historical_result: ParticipantHistoricalResult,
    decision_summary: ParticipantDecisionSummary,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
) -> tuple[float, float, float]:
    """
    Calculate the positional or monthly outlook.
    """

    bullish = 30.0
    bearish = 30.0
    neutral = 25.0

    monthly_direction = change_direction(
        historical_result.institutional_monthly_net_change
    )

    if monthly_direction > 0:
        bullish += 20

    elif monthly_direction < 0:
        bearish += 20

    if contains_bullish(
        decision_summary.current_positioning
    ):
        bullish += 12

    elif contains_bearish(
        decision_summary.current_positioning
    ):
        bearish += 12

    if cycle_result.next_probable_cycle in {
        "RE-ACCUMULATION",
        "MARKUP",
    }:
        bullish += 15

    elif cycle_result.next_probable_cycle in {
        "SHORT BUILD-UP",
        "RE-DISTRIBUTION",
    }:
        bearish += 15

    if (
        contains_bearish(
            decision_summary.current_positioning
        )
        and contains_improving(
            decision_summary.momentum
        )
    ):
        bullish += 9
        neutral += 6

    if (
        contains_bullish(
            decision_summary.current_positioning
        )
        and contains_deteriorating(
            decision_summary.momentum
        )
    ):
        bearish += 9
        neutral += 6

    if risk_result.overall_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        neutral += 12

    return normalize_three_probabilities(
        bullish=bullish,
        bearish=bearish,
        neutral=neutral,
    )


# ==========================================================
# HORIZON CONFIDENCE
# ==========================================================

def calculate_horizon_confidence(
    *,
    leading_probability: float,
    second_probability: float,
    base_confidence: int,
    risk_score: int,
    horizon_penalty: int,
) -> int:
    """
    Calculate confidence for one forecast horizon.
    """

    separation = max(
        leading_probability - second_probability,
        0,
    )

    score = base_confidence

    score += min(
        separation * 0.5,
        12,
    )

    score -= risk_score * 0.12
    score -= horizon_penalty

    return clamp_score(score)


def calculate_horizon_risk(
    *,
    base_risk_score: int,
    direction: str,
    horizon_penalty: int,
) -> str:
    """
    Calculate a horizon-specific risk level.
    """

    score = base_risk_score + horizon_penalty

    if direction == "MIXED":
        score += 8

    return risk_level_from_score(
        clamp_score(score)
    )


# ==========================================================
# HORIZON BEHAVIOUR
# ==========================================================

def determine_horizon_behaviour(
    *,
    horizon: str,
    direction: str,
    scenario: str,
    cycle_result: ParticipantCycleResult,
) -> str:
    """
    Describe expected behaviour for one horizon.
    """

    if direction == "BULLISH":
        if scenario == "BULLISH RECOVERY":
            return (
                "SHORT COVERING OR RECOVERY MAY CONTINUE, "
                "ALTHOUGH PULLBACKS AND REVERSALS MAY REMAIN SHARP"
            )

        if scenario == "BULLISH ACCUMULATION":
            return (
                "INSTITUTIONAL POSITION BUILDING MAY SUPPORT "
                "GRADUAL POSITIVE DEVELOPMENT"
            )

        return (
            "POSITIVE PARTICIPANT MOMENTUM MAY SUPPORT "
            "CONTINUED UPWARD DEVELOPMENT"
        )

    if direction == "BEARISH":
        if scenario == "BEARISH CAPITULATION":
            return (
                "NEGATIVE POSITIONING MAY CREATE SHARP WEAKNESS "
                "WITH ELEVATED REVERSAL RISK"
            )

        if scenario == "BEARISH DETERIORATION":
            return (
                "LONG REDUCTION OR DISTRIBUTION MAY CONTINUE "
                "TO CREATE DOWNWARD PRESSURE"
            )

        return (
            "NEGATIVE PARTICIPANT POSITIONING MAY CONTINUE "
            "TO PRESSURE THE MARKET"
        )

    if direction == "MIXED":
        return (
            "CONFLICTING PARTICIPANT EVIDENCE MAY PRODUCE "
            "VOLATILITY, FALSE BREAKOUTS OR RAPID REVERSALS"
        )

    if cycle_result.current_cycle == "CONSOLIDATION":
        return (
            "RANGE-BOUND BEHAVIOUR MAY CONTINUE UNTIL "
            "INSTITUTIONAL ALIGNMENT IMPROVES"
        )

    return (
        f"{horizon.upper()} CONDITIONS DO NOT SHOW A CLEAR "
        "PARTICIPANT-DRIVEN DIRECTION"
    )


# ==========================================================
# HORIZON EXPLANATION
# ==========================================================

def build_horizon_explanation(
    *,
    horizon: str,
    direction: str,
    scenario: str,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
    confidence: int,
    risk_level: str,
) -> str:
    """
    Build an explanation for one forecast horizon.
    """

    return (
        f"The {horizon.lower()} forecast is {direction.lower()} "
        f"and is classified as {scenario.lower()}. "
        f"Bullish probability is {bullish_probability:.1f}%, "
        f"bearish probability is {bearish_probability:.1f}% and "
        f"neutral probability is {neutral_probability:.1f}%. "
        f"Forecast confidence is {confidence}% with "
        f"{risk_level.lower()} risk."
    )


# ==========================================================
# CREATE HORIZON
# ==========================================================

def create_forecast_horizon(
    *,
    horizon: str,
    probabilities: tuple[float, float, float],
    base_confidence: int,
    base_risk_score: int,
    horizon_penalty: int,
    cycle_result: ParticipantCycleResult,
    regime_result: ParticipantRegimeResult,
) -> ForecastHorizon:
    """
    Build one complete forecast-horizon result.
    """

    bullish_probability = probabilities[0]
    bearish_probability = probabilities[1]
    neutral_probability = probabilities[2]

    direction = direction_from_probabilities(
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
    )

    scenario = scenario_from_direction(
        direction=direction,
        cycle_result=cycle_result,
        regime_result=regime_result,
    )

    ordered_probabilities = sorted(
        [
            bullish_probability,
            bearish_probability,
            neutral_probability,
        ],
        reverse=True,
    )

    confidence = calculate_horizon_confidence(
        leading_probability=ordered_probabilities[0],
        second_probability=ordered_probabilities[1],
        base_confidence=base_confidence,
        risk_score=base_risk_score,
        horizon_penalty=horizon_penalty,
    )

    risk_level = calculate_horizon_risk(
        base_risk_score=base_risk_score,
        direction=direction,
        horizon_penalty=horizon_penalty,
    )

    expected_behaviour = determine_horizon_behaviour(
        horizon=horizon,
        direction=direction,
        scenario=scenario,
        cycle_result=cycle_result,
    )

    explanation = build_horizon_explanation(
        horizon=horizon,
        direction=direction,
        scenario=scenario,
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
        confidence=confidence,
        risk_level=risk_level,
    )

    return ForecastHorizon(
        horizon=horizon,
        direction=direction,
        scenario=scenario,
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
        confidence=confidence,
        risk_level=risk_level,
        expected_behaviour=expected_behaviour,
        explanation=explanation,
    )


# ==========================================================
# PRIMARY AND SECONDARY FORECASTS
# ==========================================================

def determine_primary_forecast(
    *,
    next_session: ForecastHorizon,
    short_term: ForecastHorizon,
) -> str:
    """
    Determine the main forecast.
    """

    if (
        next_session.direction == short_term.direction
        and next_session.direction != "MIXED"
    ):
        return short_term.scenario

    if short_term.confidence >= next_session.confidence:
        return short_term.scenario

    return next_session.scenario


def determine_secondary_forecast(
    probability_result: InstitutionalProbabilityResult,
) -> str:
    """
    Return the second-ranked institutional scenario.
    """

    if len(probability_result.scenarios) < 2:
        return "NOT AVAILABLE"

    return probability_result.scenarios[1].scenario


def determine_failure_scenario(
    *,
    primary_forecast: str,
    probability_result: InstitutionalProbabilityResult,
    cycle_result: ParticipantCycleResult,
) -> str:
    """
    Determine the scenario that invalidates the main forecast.
    """

    if "BULLISH" in primary_forecast:
        if cycle_result.current_cycle == "RECOVERY":
            return (
                "RECOVERY FAILURE FOLLOWED BY RENEWED "
                "BEARISH CONTINUATION"
            )

        return "BEARISH REVERSAL OR DISTRIBUTION"

    if "BEARISH" in primary_forecast:
        return (
            "SHORT COVERING OR BULLISH REVERSAL "
            "INVALIDATES THE BEARISH FORECAST"
        )

    return (
        f"A DECISIVE BREAK TOWARD "
        f"{probability_result.highest_probability_scenario}"
    )


# ==========================================================
# EXPECTED VOLATILITY
# ==========================================================

def determine_expected_volatility(
    *,
    risk_result: ParticipantRiskResult,
    cycle_result: ParticipantCycleResult,
    decision_summary: ParticipantDecisionSummary,
) -> str:
    """
    Estimate participant-driven volatility.
    """

    if risk_result.overall_risk_score >= 80:
        return "VERY HIGH"

    if cycle_result.current_cycle in {
        "CAPITULATION",
        "RECOVERY",
        "TRANSITION",
        "LONG LIQUIDATION",
    }:
        return "HIGH"

    if contains_mixed(
        decision_summary.institutional_alignment
    ):
        return "MODERATE TO HIGH"

    if risk_result.overall_risk_score >= 45:
        return "MODERATE"

    return "LOW TO MODERATE"


# ==========================================================
# EXPECTED INSTITUTIONAL BEHAVIOUR
# ==========================================================

def determine_expected_institutional_behaviour(
    *,
    cycle_result: ParticipantCycleResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Describe the likely next institutional behaviour.
    """

    cycle = cycle_result.current_cycle

    behaviour_map = {
        "RECOVERY": (
            "SHORT EXPOSURE MAY CONTINUE TO REDUCE WHILE "
            "SELECTIVE LONG EXPOSURE GRADUALLY IMPROVES"
        ),
        "RE-ACCUMULATION": (
            "INSTITUTIONS MAY CONSOLIDATE AND BUILD "
            "POSITIVE EXPOSURE GRADUALLY"
        ),
        "EARLY ACCUMULATION": (
            "EARLY POSITION BUILDING MAY CONTINUE WITHOUT "
            "FULL DIRECTIONAL CONFIRMATION"
        ),
        "LATE ACCUMULATION": (
            "INSTITUTIONAL LONG EXPOSURE MAY STRENGTHEN "
            "BEFORE A MARKUP ATTEMPT"
        ),
        "MARKUP": (
            "POSITIVE POSITIONING MAY REMAIN DOMINANT"
        ),
        "DISTRIBUTION": (
            "LONG EXPOSURE MAY REDUCE WHILE DEFENSIVE OR "
            "SHORT POSITIONS INCREASE"
        ),
        "LONG LIQUIDATION": (
            "INSTITUTIONS MAY CONTINUE REDUCING LONG EXPOSURE"
        ),
        "SHORT BUILD-UP": (
            "INSTITUTIONAL SHORT EXPOSURE MAY CONTINUE TO INCREASE"
        ),
        "CAPITULATION": (
            "EXTREME SHORT POSITIONING MAY BE FOLLOWED BY "
            "RAPID COVERING OR REVERSAL"
        ),
        "CONSOLIDATION": (
            "INSTITUTIONS MAY REMAIN HEDGED OR DIRECTIONALLY MIXED"
        ),
        "TRANSITION": (
            "INSTITUTIONAL POSITIONING MAY CHANGE RAPIDLY "
            "WITHOUT STABLE ALIGNMENT"
        ),
    }

    return behaviour_map.get(
        cycle,
        regime_result.expected_behaviour,
    )


# ==========================================================
# FORECAST ENVIRONMENT
# ==========================================================

def determine_forecast_environment(
    *,
    primary_forecast: str,
    expected_volatility: str,
    forecast_risk: str,
) -> str:
    """
    Build a compact forecast-environment label.
    """

    return (
        f"{primary_forecast} | "
        f"{expected_volatility} VOLATILITY | "
        f"{forecast_risk} RISK"
    )


# ==========================================================
# FORECAST CONFIDENCE
# ==========================================================

def calculate_overall_forecast_confidence(
    *,
    horizons: tuple[ForecastHorizon, ...],
    probability_result: InstitutionalProbabilityResult,
    risk_result: ParticipantRiskResult,
) -> int:
    """
    Calculate the overall forecast confidence.
    """

    horizon_average = sum(
        horizon.confidence
        for horizon in horizons
    ) / len(horizons)

    score = (
        horizon_average * 0.60
        + probability_result.probability_confidence * 0.40
    )

    score -= risk_result.overall_risk_score * 0.10

    return clamp_score(score)


# ==========================================================
# CONFIRMATION CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    primary_forecast: str,
    historical_result: ParticipantHistoricalResult,
    cycle_result: ParticipantCycleResult,
) -> tuple[str, ...]:
    """
    Build conditions that strengthen the forecast.
    """

    conditions: list[str] = []

    if "BULLISH" in primary_forecast:
        conditions.extend(
            [
                (
                    "Institutional daily net positioning should "
                    "remain positive or improve further."
                ),
                (
                    "Weekly institutional improvement should "
                    "remain intact."
                ),
                (
                    "FII and PRO positioning should show stronger "
                    "bullish alignment."
                ),
            ]
        )

        if cycle_result.next_probable_cycle == "RE-ACCUMULATION":
            conditions.append(
                "The recovery cycle should progress toward re-accumulation."
            )

    elif "BEARISH" in primary_forecast:
        conditions.extend(
            [
                (
                    "Institutional daily net positioning should "
                    "turn negative or deteriorate further."
                ),
                (
                    "Short exposure should increase or long exposure "
                    "should continue to reduce."
                ),
                (
                    "FII and PRO positioning should align bearishly."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "Institutional alignment should remain mixed."
                ),
                (
                    "Daily and weekly net-position changes should "
                    "remain small or conflicting."
                ),
            ]
        )

    if (
        historical_result.institutional_monthly_net_change
        is not None
    ):
        conditions.append(
            "Monthly positioning direction should not reverse sharply."
        )

    return tuple(conditions)


# ==========================================================
# INVALIDATION CONDITIONS
# ==========================================================

def build_invalidation_conditions(
    *,
    primary_forecast: str,
    risk_result: ParticipantRiskResult,
) -> tuple[str, ...]:
    """
    Build conditions that invalidate the forecast.
    """

    conditions: list[str] = []

    if "BULLISH" in primary_forecast:
        conditions.extend(
            [
                (
                    "Institutional daily net positioning turns "
                    "materially negative."
                ),
                (
                    "Short exposure begins expanding faster than "
                    "long exposure."
                ),
                (
                    "The participant regime returns to bearish control "
                    "or short build-up."
                ),
            ]
        )

    elif "BEARISH" in primary_forecast:
        conditions.extend(
            [
                (
                    "Institutional daily and weekly net positioning "
                    "improve materially."
                ),
                (
                    "Short covering accelerates while fresh long "
                    "exposure increases."
                ),
                (
                    "The participant cycle shifts into recovery or "
                    "re-accumulation."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "A strong directional institutional alignment develops."
                ),
                (
                    "One directional scenario becomes dominant with "
                    "higher confidence."
                ),
            ]
        )

    if risk_result.overall_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        conditions.append(
            "A sharp reversal can invalidate the forecast before confirmation."
        )

    return tuple(conditions)


# ==========================================================
# FINAL EXPLANATION
# ==========================================================

def build_explanation(
    *,
    primary_forecast: str,
    secondary_forecast: str,
    failure_scenario: str,
    forecast_confidence: int,
    forecast_risk: str,
    expected_volatility: str,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
) -> str:
    """
    Build the final APD-015 forecast explanation.
    """

    return (
        f"The primary participant forecast is "
        f"{primary_forecast.lower()}, while the secondary forecast is "
        f"{secondary_forecast.lower()}. Current institutional positioning "
        f"is {decision_summary.current_positioning.lower()} and momentum is "
        f"{decision_summary.momentum.lower()}. The participant regime is "
        f"{regime_result.primary_regime.lower()}, while the current cycle is "
        f"{cycle_result.current_cycle.lower()} and the next probable cycle is "
        f"{cycle_result.next_probable_cycle.lower()}. The leading analytical "
        f"scenario is "
        f"{probability_result.highest_probability_scenario.lower()} at "
        f"{probability_result.highest_probability:.1f}%. Overall participant "
        f"risk is {risk_result.overall_risk_level.lower()} at "
        f"{risk_result.overall_risk_score}%. Forecast confidence is "
        f"{forecast_confidence}% with {forecast_risk.lower()} forecast risk "
        f"and {expected_volatility.lower()} expected volatility. The principal "
        f"failure scenario is {failure_scenario.lower()}."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_forecast_engine(
    requested_date: date,
) -> ParticipantForecastResult:
    """
    Run APD-015.
    """

    decision_summary = run_participant_decision_summary(
        requested_date
    )

    historical_result = run_historical_change_engine(
        requested_date
    )

    probability_result = run_institutional_probability_engine(
        requested_date
    )

    regime_result = run_participant_regime_engine(
        requested_date
    )

    cycle_result = run_participant_cycle_engine(
        requested_date
    )

    risk_result = run_participant_risk_engine(
        requested_date
    )

    base_confidence = round(
        (
            decision_summary.confidence
            + probability_result.probability_confidence
            + regime_result.regime_confidence
            + cycle_result.cycle_confidence
        )
        / 4
    )

    next_session_probabilities = (
        calculate_next_session_probabilities(
            probability_result=probability_result,
            historical_result=historical_result,
            cycle_result=cycle_result,
            risk_result=risk_result,
        )
    )

    short_term_probabilities = (
        calculate_short_term_probabilities(
            probability_result=probability_result,
            historical_result=historical_result,
            cycle_result=cycle_result,
            regime_result=regime_result,
            risk_result=risk_result,
        )
    )

    weekly_probabilities = calculate_weekly_probabilities(
        probability_result=probability_result,
        historical_result=historical_result,
        cycle_result=cycle_result,
        decision_summary=decision_summary,
    )

    positional_probabilities = (
        calculate_positional_probabilities(
            historical_result=historical_result,
            decision_summary=decision_summary,
            cycle_result=cycle_result,
            risk_result=risk_result,
        )
    )

    next_session = create_forecast_horizon(
        horizon="NEXT TRADING SESSION",
        probabilities=next_session_probabilities,
        base_confidence=base_confidence,
        base_risk_score=risk_result.overall_risk_score,
        horizon_penalty=0,
        cycle_result=cycle_result,
        regime_result=regime_result,
    )

    next_two_three_sessions = create_forecast_horizon(
        horizon="NEXT 2-3 TRADING SESSIONS",
        probabilities=short_term_probabilities,
        base_confidence=base_confidence,
        base_risk_score=risk_result.overall_risk_score,
        horizon_penalty=2,
        cycle_result=cycle_result,
        regime_result=regime_result,
    )

    weekly = create_forecast_horizon(
        horizon="NEXT TRADING WEEK",
        probabilities=weekly_probabilities,
        base_confidence=base_confidence,
        base_risk_score=risk_result.overall_risk_score,
        horizon_penalty=5,
        cycle_result=cycle_result,
        regime_result=regime_result,
    )

    positional = create_forecast_horizon(
        horizon="POSITIONAL / MONTHLY",
        probabilities=positional_probabilities,
        base_confidence=base_confidence,
        base_risk_score=risk_result.overall_risk_score,
        horizon_penalty=9,
        cycle_result=cycle_result,
        regime_result=regime_result,
    )

    horizons = (
        next_session,
        next_two_three_sessions,
        weekly,
        positional,
    )

    primary_forecast = determine_primary_forecast(
        next_session=next_session,
        short_term=next_two_three_sessions,
    )

    secondary_forecast = determine_secondary_forecast(
        probability_result
    )

    failure_scenario = determine_failure_scenario(
        primary_forecast=primary_forecast,
        probability_result=probability_result,
        cycle_result=cycle_result,
    )

    expected_volatility = determine_expected_volatility(
        risk_result=risk_result,
        cycle_result=cycle_result,
        decision_summary=decision_summary,
    )

    expected_institutional_behaviour = (
        determine_expected_institutional_behaviour(
            cycle_result=cycle_result,
            regime_result=regime_result,
        )
    )

    forecast_confidence = (
        calculate_overall_forecast_confidence(
            horizons=horizons,
            probability_result=probability_result,
            risk_result=risk_result,
        )
    )

    forecast_risk = risk_level_from_score(
        risk_result.overall_risk_score
    )

    forecast_environment = determine_forecast_environment(
        primary_forecast=primary_forecast,
        expected_volatility=expected_volatility,
        forecast_risk=forecast_risk,
    )

    confirmation_conditions = build_confirmation_conditions(
        primary_forecast=primary_forecast,
        historical_result=historical_result,
        cycle_result=cycle_result,
    )

    invalidation_conditions = build_invalidation_conditions(
        primary_forecast=primary_forecast,
        risk_result=risk_result,
    )

    explanation = build_explanation(
        primary_forecast=primary_forecast,
        secondary_forecast=secondary_forecast,
        failure_scenario=failure_scenario,
        forecast_confidence=forecast_confidence,
        forecast_risk=forecast_risk,
        expected_volatility=expected_volatility,
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
    )

    return ParticipantForecastResult(
        requested_date=requested_date,
        analysis_date=decision_summary.analysis_date,
        current_positioning=decision_summary.current_positioning,
        momentum=decision_summary.momentum,
        institutional_alignment=(
            decision_summary.institutional_alignment
        ),
        primary_regime=regime_result.primary_regime,
        current_cycle=cycle_result.current_cycle,
        next_probable_cycle=cycle_result.next_probable_cycle,
        highest_probability_scenario=(
            probability_result.highest_probability_scenario
        ),
        highest_probability=(
            probability_result.highest_probability
        ),
        probability_confidence=(
            probability_result.probability_confidence
        ),
        overall_risk_score=risk_result.overall_risk_score,
        overall_risk_level=risk_result.overall_risk_level,
        dominant_risk=risk_result.dominant_risk,
        next_session=next_session,
        next_two_three_sessions=next_two_three_sessions,
        weekly=weekly,
        positional=positional,
        primary_forecast=primary_forecast,
        secondary_forecast=secondary_forecast,
        failure_scenario=failure_scenario,
        expected_volatility=expected_volatility,
        expected_institutional_behaviour=(
            expected_institutional_behaviour
        ),
        forecast_environment=forecast_environment,
        forecast_confidence=forecast_confidence,
        forecast_risk=forecast_risk,
        confirmation_conditions=confirmation_conditions,
        invalidation_conditions=invalidation_conditions,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def display_horizon(
    horizon: ForecastHorizon,
) -> None:
    """
    Display one forecast horizon.
    """

    print(f"Horizon                     : {horizon.horizon}")
    print(f"Direction                   : {horizon.direction}")
    print(f"Scenario                    : {horizon.scenario}")
    print(
        f"Bullish Probability         : "
        f"{horizon.bullish_probability:.1f}%"
    )
    print(
        f"Bearish Probability         : "
        f"{horizon.bearish_probability:.1f}%"
    )
    print(
        f"Neutral Probability         : "
        f"{horizon.neutral_probability:.1f}%"
    )
    print(f"Confidence                  : {horizon.confidence}%")
    print(f"Risk Level                  : {horizon.risk_level}")
    print(
        f"Expected Behaviour          : "
        f"{horizon.expected_behaviour}"
    )
    print(f"Explanation                 : {horizon.explanation}")


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantForecastResult,
) -> None:
    """
    Display the APD-015 terminal report.
    """

    print()
    print("=" * 98)
    print("AQSD PARTICIPANT FORECAST ENGINE")
    print("=" * 98)
    print(f"Module                         : {MODULE_ID}")
    print(f"Version                        : {MODULE_VERSION}")
    print(f"Requested Date                 : {result.requested_date}")
    print(f"Analysis Date                  : {result.analysis_date}")
    print("-" * 98)
    print(
        f"Current Positioning            : "
        f"{result.current_positioning}"
    )
    print(
        f"Momentum                       : "
        f"{result.momentum}"
    )
    print(
        f"Institutional Alignment        : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Primary Regime                 : "
        f"{result.primary_regime}"
    )
    print(
        f"Current Cycle                  : "
        f"{result.current_cycle}"
    )
    print(
        f"Next Probable Cycle            : "
        f"{result.next_probable_cycle}"
    )
    print("-" * 98)
    print(
        f"Highest Probability Scenario   : "
        f"{result.highest_probability_scenario}"
    )
    print(
        f"Highest Probability            : "
        f"{result.highest_probability:.1f}%"
    )
    print(
        f"Probability Confidence         : "
        f"{result.probability_confidence}%"
    )
    print(
        f"Overall Participant Risk       : "
        f"{result.overall_risk_score}% "
        f"({result.overall_risk_level})"
    )
    print(
        f"Dominant Risk                  : "
        f"{result.dominant_risk}"
    )
    print("=" * 98)

    display_horizon(
        result.next_session
    )

    print("-" * 98)

    display_horizon(
        result.next_two_three_sessions
    )

    print("-" * 98)

    display_horizon(
        result.weekly
    )

    print("-" * 98)

    display_horizon(
        result.positional
    )

    print("=" * 98)
    print("FINAL FORECAST")
    print("-" * 98)
    print(
        f"Primary Forecast               : "
        f"{result.primary_forecast}"
    )
    print(
        f"Secondary Forecast             : "
        f"{result.secondary_forecast}"
    )
    print(
        f"Failure Scenario               : "
        f"{result.failure_scenario}"
    )
    print(
        f"Expected Volatility            : "
        f"{result.expected_volatility}"
    )
    print(
        f"Expected Institutional Behaviour: "
        f"{result.expected_institutional_behaviour}"
    )
    print(
        f"Forecast Environment           : "
        f"{result.forecast_environment}"
    )
    print(
        f"Forecast Confidence            : "
        f"{result.forecast_confidence}%"
    )
    print(
        f"Forecast Risk                  : "
        f"{result.forecast_risk}"
    )
    print("-" * 98)
    print("CONFIRMATION CONDITIONS")
    print("-" * 98)

    for number, condition in enumerate(
        result.confirmation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 98)
    print("INVALIDATION CONDITIONS")
    print("-" * 98)

    for number, condition in enumerate(
        result.invalidation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 98)
    print("EXPLANATION")
    print("-" * 98)
    print(result.explanation)
    print("-" * 98)
    print(
        "Method                         : "
        "RULE-BASED MULTI-HORIZON FORECAST"
    )
    print(f"Status                         : {result.status}")
    print("=" * 98)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Create multi-horizon institutional participant forecasts "
            "from APD intelligence."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested analysis date in YYYY-MM-DD format.",
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
        result = run_participant_forecast_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 98)
        print("AQSD PARTICIPANT FORECAST ENGINE")
        print("=" * 98)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 98)

        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()