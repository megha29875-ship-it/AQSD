"""
AQSD
Participant Master Decision Engine

Module : APD-016
Version: 1.0.0
Author : AQSD

Description
-----------
Combines the complete AQSD Participant Intelligence Layer into one
final, explainable institutional decision-support conclusion.

Input engines
-------------
- APD-009 Participant Historical Change Engine
- APD-010 Participant Decision Summary Engine
- APD-011 Institutional Probability Engine
- APD-012 Participant Regime Engine
- APD-013 Participant Cycle Engine
- APD-014 Participant Risk Engine
- APD-015 Participant Forecast Engine

Final outputs
-------------
- Institutional Bias
- Institutional Momentum
- Participant Regime
- Participant Cycle
- Primary Forecast
- Probability
- Risk
- Forecast Quality
- Participant Environment
- Expected Behaviour
- Confirmation Conditions
- Invalidation Conditions
- Master Confidence
- AQSD Participant Conclusion
- Explanation

Important
---------
This engine does not generate BUY, SELL or SHORT instructions.

It produces an analytical participant-intelligence conclusion for
the AQSD Master Decision Engine.
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
from Scripts.aqsd_intelligence.participant_forecast_engine import (
    ParticipantForecastResult,
    run_participant_forecast_engine,
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

MODULE_ID: Final[str] = "APD-016"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantMasterDecisionResult:
    """
    Final consolidated participant decision-support output.
    """

    requested_date: date
    analysis_date: date

    institutional_bias: str
    institutional_momentum: str
    institutional_alignment: str
    structural_state: str

    primary_regime: str
    secondary_regime: str
    regime_strength: str
    regime_maturity: str
    regime_confidence: int

    current_cycle: str
    previous_cycle: str
    next_probable_cycle: str
    cycle_direction: str
    cycle_strength: str
    cycle_maturity: str
    cycle_confidence: int

    primary_forecast: str
    secondary_forecast: str
    failure_scenario: str

    highest_probability_scenario: str
    highest_probability: float
    probability_confidence: int

    next_session_direction: str
    next_session_bullish_probability: float
    next_session_bearish_probability: float
    next_session_neutral_probability: float

    short_term_direction: str
    short_term_bullish_probability: float
    short_term_bearish_probability: float
    short_term_neutral_probability: float

    overall_risk_score: int
    overall_risk_level: str
    dominant_risk: str
    risk_direction: str

    forecast_confidence: int
    master_confidence: int
    forecast_quality: str
    decision_quality: str

    participant_environment: str
    expected_behaviour: str
    analytical_posture: str

    master_conclusion: str
    concise_summary: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    explanation: str
    status: str


# ==========================================================
# TEXT HELPERS
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
    Return True when a label indicates mixed evidence.
    """

    return "MIXED" in value.upper()


# ==========================================================
# NUMBER HELPERS
# ==========================================================

def clamp_score(value: float) -> int:
    """
    Restrict a score to 0-100.
    """

    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


def format_optional_change(
    value: float | None,
) -> str:
    """
    Format an optional participant-position change.
    """

    if value is None:
        return "NOT AVAILABLE"

    return f"{value:+,.0f}"


# ==========================================================
# FORECAST QUALITY
# ==========================================================

def determine_forecast_quality(
    *,
    forecast_result: ParticipantForecastResult,
    probability_result: InstitutionalProbabilityResult,
    risk_result: ParticipantRiskResult,
) -> str:
    """
    Determine the quality of the participant forecast.
    """

    confidence = forecast_result.forecast_confidence
    probability_confidence = (
        probability_result.probability_confidence
    )
    risk_score = risk_result.overall_risk_score

    if (
        confidence >= 75
        and probability_confidence >= 70
        and risk_score < 45
    ):
        return "HIGH"

    if (
        confidence >= 60
        and probability_confidence >= 55
        and risk_score < 65
    ):
        return "MODERATE"

    if (
        confidence >= 45
        and probability_confidence >= 45
    ):
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# MASTER CONFIDENCE
# ==========================================================

def calculate_master_confidence(
    *,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
    forecast_result: ParticipantForecastResult,
) -> int:
    """
    Calculate the final participant master confidence.

    Weighting
    ---------
    Decision Summary     : 15%
    Probability Engine   : 20%
    Regime Engine        : 15%
    Cycle Engine         : 15%
    Forecast Engine      : 25%
    Risk Adjustment      : 10%
    """

    base_score = (
        decision_summary.confidence * 0.15
        + probability_result.probability_confidence * 0.20
        + regime_result.regime_confidence * 0.15
        + cycle_result.cycle_confidence * 0.15
        + forecast_result.forecast_confidence * 0.25
        + (100 - risk_result.overall_risk_score) * 0.10
    )

    alignment = (
        decision_summary.institutional_alignment.upper()
    )

    if "FULL" in alignment:
        base_score += 6

    elif "MAJORITY" in alignment:
        base_score += 3

    elif "MIXED" in alignment:
        base_score -= 5

    if (
        forecast_result.primary_forecast
        == probability_result.highest_probability_scenario
    ):
        base_score += 4

    if (
        regime_result.regime_direction
        == cycle_result.cycle_direction
        and regime_result.regime_direction
        in {"BULLISH", "BEARISH"}
    ):
        base_score += 3

    if risk_result.overall_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        base_score -= 5

    return clamp_score(base_score)


# ==========================================================
# DECISION QUALITY
# ==========================================================

def determine_decision_quality(
    *,
    master_confidence: int,
    forecast_quality: str,
    overall_risk_level: str,
) -> str:
    """
    Convert confidence and risk into a final quality grade.
    """

    if (
        master_confidence >= 75
        and forecast_quality == "HIGH"
        and overall_risk_level
        in {
            "LOW",
            "LOW TO MODERATE",
        }
    ):
        return "A"

    if (
        master_confidence >= 65
        and forecast_quality
        in {
            "HIGH",
            "MODERATE",
        }
        and overall_risk_level != "VERY HIGH"
    ):
        return "B"

    if (
        master_confidence >= 50
        and forecast_quality
        in {
            "MODERATE",
            "LOW TO MODERATE",
        }
    ):
        return "C"

    return "D"


# ==========================================================
# PARTICIPANT ENVIRONMENT
# ==========================================================

def determine_participant_environment(
    *,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
    forecast_result: ParticipantForecastResult,
) -> str:
    """
    Build the final participant environment classification.
    """

    return (
        f"{regime_result.primary_regime} | "
        f"{cycle_result.current_cycle} | "
        f"{forecast_result.primary_forecast} | "
        f"{risk_result.overall_risk_level} RISK"
    )


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    *,
    forecast_result: ParticipantForecastResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
) -> str:
    """
    Select the final expected participant-driven behaviour.
    """

    if risk_result.overall_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        return (
            f"{forecast_result.expected_institutional_behaviour}. "
            f"However, {risk_result.expected_risk_behaviour.lower()}."
        )

    if cycle_result.current_cycle in {
        "RECOVERY",
        "CAPITULATION",
        "TRANSITION",
    }:
        return cycle_result.expected_behaviour

    return regime_result.expected_behaviour


# ==========================================================
# ANALYTICAL POSTURE
# ==========================================================

def determine_analytical_posture(
    *,
    risk_result: ParticipantRiskResult,
    forecast_quality: str,
    decision_quality: str,
) -> str:
    """
    Determine how heavily the AQSD Master Decision Engine should
    weight participant intelligence.
    """

    if risk_result.overall_risk_level == "VERY HIGH":
        return (
            "USE PARTICIPANT DATA AS A WARNING SIGNAL ONLY. "
            "REQUIRE STRONG CONFIRMATION FROM PRICE, STRUCTURE, "
            "OPTIONS AND MARKET REGIME ENGINES."
        )

    if risk_result.overall_risk_level == "HIGH":
        return (
            "USE PARTICIPANT INTELLIGENCE CONSERVATIVELY. "
            "REQUIRE CONFIRMATION FROM PRICE STRUCTURE AND "
            "OPTIONS INTELLIGENCE."
        )

    if (
        forecast_quality == "HIGH"
        and decision_quality in {"A", "B"}
    ):
        return (
            "PARTICIPANT INTELLIGENCE CAN RECEIVE NORMAL TO HIGH "
            "WEIGHT IN THE AQSD MASTER DECISION ENGINE."
        )

    if forecast_quality in {
        "MODERATE",
        "LOW TO MODERATE",
    }:
        return (
            "USE PARTICIPANT INTELLIGENCE WITH NORMAL CROSS-CHECKS "
            "FROM OTHER AQSD ENGINES."
        )

    return (
        "PARTICIPANT INTELLIGENCE SHOULD RECEIVE LOW WEIGHT UNTIL "
        "CONFIDENCE AND ALIGNMENT IMPROVE."
    )


# ==========================================================
# MASTER CONCLUSION
# ==========================================================

def determine_master_conclusion(
    *,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
    forecast_result: ParticipantForecastResult,
) -> str:
    """
    Create one concise final participant conclusion.
    """

    positioning = decision_summary.current_positioning
    momentum = decision_summary.momentum
    forecast = forecast_result.primary_forecast
    regime = regime_result.primary_regime
    cycle = cycle_result.current_cycle
    risk = risk_result.overall_risk_level

    if (
        contains_bearish(positioning)
        and contains_improving(momentum)
        and forecast == "BULLISH RECOVERY"
    ):
        return (
            "INSTITUTIONAL POSITIONING REMAINS BEARISH, BUT "
            "IMPROVING MOMENTUM, SHORT COVERING AND THE RECOVERY "
            "CYCLE SUPPORT A CONDITIONAL BULLISH RECOVERY VIEW. "
            "THE RECOVERY IS NOT YET A CONFIRMED BULLISH REVERSAL."
        )

    if (
        contains_bearish(positioning)
        and contains_deteriorating(momentum)
        and forecast == "BEARISH CONTINUATION"
    ):
        return (
            "INSTITUTIONAL POSITIONING AND MOMENTUM REMAIN BEARISH. "
            "THE PARTICIPANT REGIME SUPPORTS CONTINUED NEGATIVE "
            "PRESSURE, SUBJECT TO SHORT-COVERING RISK."
        )

    if (
        contains_bullish(positioning)
        and contains_improving(momentum)
        and forecast == "BULLISH CONTINUATION"
    ):
        return (
            "INSTITUTIONAL POSITIONING, MOMENTUM AND PARTICIPANT "
            "STRUCTURE ARE ALIGNED BULLISHLY. CONTINUATION IS "
            "SUPPORTED WHILE CONFIRMATION CONDITIONS REMAIN INTACT."
        )

    if (
        contains_bullish(positioning)
        and contains_deteriorating(momentum)
    ):
        return (
            "INSTITUTIONAL POSITIONING REMAINS BULLISH, BUT "
            "DETERIORATING MOMENTUM CREATES LONG-UNWINDING OR "
            "BEARISH-REVERSAL RISK."
        )

    if (
        contains_mixed(
            decision_summary.institutional_alignment
        )
        or risk in {
            "HIGH",
            "VERY HIGH",
        }
    ):
        return (
            f"PARTICIPANT EVIDENCE IS CONFLICTED. THE LEADING "
            f"FORECAST IS {forecast}, BUT {risk} RISK AND MIXED "
            f"INSTITUTIONAL ALIGNMENT REQUIRE STRONG CONFIRMATION."
        )

    return (
        f"THE PARTICIPANT REGIME IS {regime}, THE CURRENT CYCLE IS "
        f"{cycle}, AND THE PRIMARY FORECAST IS {forecast}. "
        f"THE VIEW REMAINS CONDITIONAL ON CONFIRMATION CONDITIONS."
    )


# ==========================================================
# CONCISE SUMMARY
# ==========================================================

def build_concise_summary(
    *,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
    forecast_result: ParticipantForecastResult,
    master_confidence: int,
) -> str:
    """
    Build a dashboard-ready single-line summary.
    """

    return (
        f"{decision_summary.current_positioning} POSITIONING | "
        f"{decision_summary.momentum} MOMENTUM | "
        f"{regime_result.primary_regime} REGIME | "
        f"{cycle_result.current_cycle} CYCLE | "
        f"{forecast_result.primary_forecast} FORECAST | "
        f"{probability_result.highest_probability:.1f}% PROBABILITY | "
        f"{risk_result.overall_risk_level} RISK | "
        f"{master_confidence}% CONFIDENCE"
    )


# ==========================================================
# CONFIRMATION CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    forecast_result: ParticipantForecastResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> tuple[str, ...]:
    """
    Combine and deduplicate confirmation conditions.
    """

    conditions = list(
        forecast_result.confirmation_conditions
    )

    if regime_result.primary_regime == "SHORT COVERING":
        conditions.append(
            "Short covering should continue without renewed aggressive "
            "short build-up."
        )

    if cycle_result.next_probable_cycle == "RE-ACCUMULATION":
        conditions.append(
            "The recovery cycle should develop into re-accumulation."
        )

    if regime_result.primary_regime == "BULLISH CONTROL":
        conditions.append(
            "Bullish institutional alignment should remain intact."
        )

    if regime_result.primary_regime == "BEARISH CONTROL":
        conditions.append(
            "Negative institutional positioning should remain dominant."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# INVALIDATION CONDITIONS
# ==========================================================

def build_invalidation_conditions(
    *,
    forecast_result: ParticipantForecastResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> tuple[str, ...]:
    """
    Combine and deduplicate invalidation conditions.
    """

    conditions = list(
        forecast_result.invalidation_conditions
    )

    if regime_result.primary_regime == "SHORT COVERING":
        conditions.append(
            "Renewed short build-up invalidates the short-covering regime."
        )

    if cycle_result.current_cycle == "RECOVERY":
        conditions.append(
            "A return to the short build-up cycle invalidates the recovery."
        )

    if cycle_result.current_cycle == "MARKUP":
        conditions.append(
            "Distribution or long liquidation invalidates the markup cycle."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_master_warnings(
    *,
    risk_result: ParticipantRiskResult,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    forecast_result: ParticipantForecastResult,
) -> tuple[str, ...]:
    """
    Build final participant warnings.
    """

    warnings = list(
        risk_result.warnings
    )

    if forecast_result.forecast_confidence < 55:
        warnings.append(
            "Forecast confidence is below 55%."
        )

    if probability_result.probability_confidence < 60:
        warnings.append(
            "Institutional probability confidence is below 60%."
        )

    if contains_mixed(
        decision_summary.institutional_alignment
    ):
        warnings.append(
            "Institutional participants remain directionally mixed."
        )

    if (
        forecast_result.primary_forecast
        != probability_result.highest_probability_scenario
    ):
        warnings.append(
            "The primary multi-horizon forecast differs from the "
            "highest single probability scenario."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# EXPLANATION
# ==========================================================

def build_explanation(
    *,
    historical_result: ParticipantHistoricalResult,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
    risk_result: ParticipantRiskResult,
    forecast_result: ParticipantForecastResult,
    forecast_quality: str,
    decision_quality: str,
    master_confidence: int,
    master_conclusion: str,
) -> str:
    """
    Build the final APD-016 explanation.
    """

    return (
        f"Combined institutional positioning is "
        f"{decision_summary.current_positioning.lower()}, with "
        f"{decision_summary.momentum.lower()} momentum and "
        f"{decision_summary.institutional_alignment.lower()}. "
        f"Institutional net positioning changed by "
        f"{format_optional_change(historical_result.institutional_daily_net_change)} "
        f"over the daily period, "
        f"{format_optional_change(historical_result.institutional_weekly_net_change)} "
        f"over the weekly period and "
        f"{format_optional_change(historical_result.institutional_monthly_net_change)} "
        f"over the monthly period. "
        f"The highest probability scenario is "
        f"{probability_result.highest_probability_scenario.lower()} "
        f"at {probability_result.highest_probability:.1f}%. "
        f"The participant regime is "
        f"{regime_result.primary_regime.lower()} and the current cycle is "
        f"{cycle_result.current_cycle.lower()}, with "
        f"{cycle_result.next_probable_cycle.lower()} as the next probable "
        f"cycle. The primary forecast is "
        f"{forecast_result.primary_forecast.lower()}. "
        f"Participant risk is {risk_result.overall_risk_level.lower()} "
        f"at {risk_result.overall_risk_score}%, with "
        f"{risk_result.dominant_risk.lower()} as the dominant risk. "
        f"Forecast quality is {forecast_quality.lower()}, decision quality "
        f"is grade {decision_quality}, and master confidence is "
        f"{master_confidence}%. Final conclusion: "
        f"{master_conclusion}"
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_master_decision_engine(
    requested_date: date,
) -> ParticipantMasterDecisionResult:
    """
    Run APD-016.
    """

    historical_result = run_historical_change_engine(
        requested_date
    )

    decision_summary = run_participant_decision_summary(
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

    forecast_result = run_participant_forecast_engine(
        requested_date
    )

    forecast_quality = determine_forecast_quality(
        forecast_result=forecast_result,
        probability_result=probability_result,
        risk_result=risk_result,
    )

    master_confidence = calculate_master_confidence(
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
        forecast_result=forecast_result,
    )

    decision_quality = determine_decision_quality(
        master_confidence=master_confidence,
        forecast_quality=forecast_quality,
        overall_risk_level=risk_result.overall_risk_level,
    )

    participant_environment = (
        determine_participant_environment(
            regime_result=regime_result,
            cycle_result=cycle_result,
            risk_result=risk_result,
            forecast_result=forecast_result,
        )
    )

    expected_behaviour = determine_expected_behaviour(
        forecast_result=forecast_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
    )

    analytical_posture = determine_analytical_posture(
        risk_result=risk_result,
        forecast_quality=forecast_quality,
        decision_quality=decision_quality,
    )

    master_conclusion = determine_master_conclusion(
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
        forecast_result=forecast_result,
    )

    concise_summary = build_concise_summary(
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
        forecast_result=forecast_result,
        master_confidence=master_confidence,
    )

    confirmation_conditions = build_confirmation_conditions(
        forecast_result=forecast_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    invalidation_conditions = build_invalidation_conditions(
        forecast_result=forecast_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    warnings = build_master_warnings(
        risk_result=risk_result,
        decision_summary=decision_summary,
        probability_result=probability_result,
        forecast_result=forecast_result,
    )

    explanation = build_explanation(
        historical_result=historical_result,
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
        risk_result=risk_result,
        forecast_result=forecast_result,
        forecast_quality=forecast_quality,
        decision_quality=decision_quality,
        master_confidence=master_confidence,
        master_conclusion=master_conclusion,
    )

    return ParticipantMasterDecisionResult(
        requested_date=requested_date,
        analysis_date=decision_summary.analysis_date,
        institutional_bias=decision_summary.current_positioning,
        institutional_momentum=decision_summary.momentum,
        institutional_alignment=(
            decision_summary.institutional_alignment
        ),
        structural_state=decision_summary.structural_state,
        primary_regime=regime_result.primary_regime,
        secondary_regime=regime_result.secondary_regime,
        regime_strength=regime_result.regime_strength,
        regime_maturity=regime_result.regime_maturity,
        regime_confidence=regime_result.regime_confidence,
        current_cycle=cycle_result.current_cycle,
        previous_cycle=cycle_result.previous_cycle,
        next_probable_cycle=cycle_result.next_probable_cycle,
        cycle_direction=cycle_result.cycle_direction,
        cycle_strength=cycle_result.cycle_strength,
        cycle_maturity=cycle_result.cycle_maturity,
        cycle_confidence=cycle_result.cycle_confidence,
        primary_forecast=forecast_result.primary_forecast,
        secondary_forecast=forecast_result.secondary_forecast,
        failure_scenario=forecast_result.failure_scenario,
        highest_probability_scenario=(
            probability_result.highest_probability_scenario
        ),
        highest_probability=probability_result.highest_probability,
        probability_confidence=(
            probability_result.probability_confidence
        ),
        next_session_direction=(
            forecast_result.next_session.direction
        ),
        next_session_bullish_probability=(
            forecast_result.next_session.bullish_probability
        ),
        next_session_bearish_probability=(
            forecast_result.next_session.bearish_probability
        ),
        next_session_neutral_probability=(
            forecast_result.next_session.neutral_probability
        ),
        short_term_direction=(
            forecast_result.next_two_three_sessions.direction
        ),
        short_term_bullish_probability=(
            forecast_result
            .next_two_three_sessions
            .bullish_probability
        ),
        short_term_bearish_probability=(
            forecast_result
            .next_two_three_sessions
            .bearish_probability
        ),
        short_term_neutral_probability=(
            forecast_result
            .next_two_three_sessions
            .neutral_probability
        ),
        overall_risk_score=risk_result.overall_risk_score,
        overall_risk_level=risk_result.overall_risk_level,
        dominant_risk=risk_result.dominant_risk,
        risk_direction=risk_result.risk_direction,
        forecast_confidence=forecast_result.forecast_confidence,
        master_confidence=master_confidence,
        forecast_quality=forecast_quality,
        decision_quality=decision_quality,
        participant_environment=participant_environment,
        expected_behaviour=expected_behaviour,
        analytical_posture=analytical_posture,
        master_conclusion=master_conclusion,
        concise_summary=concise_summary,
        confirmation_conditions=confirmation_conditions,
        invalidation_conditions=invalidation_conditions,
        warnings=warnings,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantMasterDecisionResult,
) -> None:
    """
    Display the APD-016 terminal report.
    """

    print()
    print("=" * 104)
    print("AQSD PARTICIPANT MASTER DECISION ENGINE")
    print("=" * 104)
    print(f"Module                           : {MODULE_ID}")
    print(f"Version                          : {MODULE_VERSION}")
    print(f"Requested Date                   : {result.requested_date}")
    print(f"Analysis Date                    : {result.analysis_date}")
    print("=" * 104)

    print("INSTITUTIONAL POSITIONING")
    print("-" * 104)
    print(
        f"Institutional Bias               : "
        f"{result.institutional_bias}"
    )
    print(
        f"Institutional Momentum           : "
        f"{result.institutional_momentum}"
    )
    print(
        f"Institutional Alignment          : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Structural State                 : "
        f"{result.structural_state}"
    )
    print("-" * 104)

    print("REGIME")
    print("-" * 104)
    print(
        f"Primary Regime                   : "
        f"{result.primary_regime}"
    )
    print(
        f"Secondary Regime                 : "
        f"{result.secondary_regime}"
    )
    print(
        f"Regime Strength                  : "
        f"{result.regime_strength}"
    )
    print(
        f"Regime Maturity                  : "
        f"{result.regime_maturity}"
    )
    print(
        f"Regime Confidence                : "
        f"{result.regime_confidence}%"
    )
    print("-" * 104)

    print("CYCLE")
    print("-" * 104)
    print(
        f"Current Cycle                    : "
        f"{result.current_cycle}"
    )
    print(
        f"Previous Cycle                   : "
        f"{result.previous_cycle}"
    )
    print(
        f"Next Probable Cycle              : "
        f"{result.next_probable_cycle}"
    )
    print(
        f"Cycle Direction                  : "
        f"{result.cycle_direction}"
    )
    print(
        f"Cycle Strength                   : "
        f"{result.cycle_strength}"
    )
    print(
        f"Cycle Maturity                   : "
        f"{result.cycle_maturity}"
    )
    print(
        f"Cycle Confidence                 : "
        f"{result.cycle_confidence}%"
    )
    print("-" * 104)

    print("PROBABILITY")
    print("-" * 104)
    print(
        f"Highest Probability Scenario     : "
        f"{result.highest_probability_scenario}"
    )
    print(
        f"Highest Probability              : "
        f"{result.highest_probability:.1f}%"
    )
    print(
        f"Probability Confidence           : "
        f"{result.probability_confidence}%"
    )
    print("-" * 104)

    print("FORECAST")
    print("-" * 104)
    print(
        f"Primary Forecast                 : "
        f"{result.primary_forecast}"
    )
    print(
        f"Secondary Forecast               : "
        f"{result.secondary_forecast}"
    )
    print(
        f"Failure Scenario                 : "
        f"{result.failure_scenario}"
    )
    print(
        f"Forecast Confidence              : "
        f"{result.forecast_confidence}%"
    )
    print(
        f"Forecast Quality                 : "
        f"{result.forecast_quality}"
    )
    print("-" * 104)

    print("NEXT SESSION")
    print("-" * 104)
    print(
        f"Direction                        : "
        f"{result.next_session_direction}"
    )
    print(
        f"Bullish Probability              : "
        f"{result.next_session_bullish_probability:.1f}%"
    )
    print(
        f"Bearish Probability              : "
        f"{result.next_session_bearish_probability:.1f}%"
    )
    print(
        f"Neutral Probability              : "
        f"{result.next_session_neutral_probability:.1f}%"
    )
    print("-" * 104)

    print("NEXT 2-3 SESSIONS")
    print("-" * 104)
    print(
        f"Direction                        : "
        f"{result.short_term_direction}"
    )
    print(
        f"Bullish Probability              : "
        f"{result.short_term_bullish_probability:.1f}%"
    )
    print(
        f"Bearish Probability              : "
        f"{result.short_term_bearish_probability:.1f}%"
    )
    print(
        f"Neutral Probability              : "
        f"{result.short_term_neutral_probability:.1f}%"
    )
    print("-" * 104)

    print("RISK")
    print("-" * 104)
    print(
        f"Overall Risk Score               : "
        f"{result.overall_risk_score}%"
    )
    print(
        f"Overall Risk Level               : "
        f"{result.overall_risk_level}"
    )
    print(
        f"Dominant Risk                    : "
        f"{result.dominant_risk}"
    )
    print(
        f"Risk Direction                   : "
        f"{result.risk_direction}"
    )
    print("-" * 104)

    print("MASTER DECISION")
    print("-" * 104)
    print(
        f"Master Confidence                : "
        f"{result.master_confidence}%"
    )
    print(
        f"Decision Quality                 : "
        f"{result.decision_quality}"
    )
    print(
        f"Participant Environment          : "
        f"{result.participant_environment}"
    )
    print(
        f"Expected Behaviour               : "
        f"{result.expected_behaviour}"
    )
    print(
        f"Analytical Posture               : "
        f"{result.analytical_posture}"
    )
    print("-" * 104)

    print("MASTER CONCLUSION")
    print("-" * 104)
    print(result.master_conclusion)
    print("-" * 104)

    print("CONCISE SUMMARY")
    print("-" * 104)
    print(result.concise_summary)
    print("-" * 104)

    print("CONFIRMATION CONDITIONS")
    print("-" * 104)

    for number, condition in enumerate(
        result.confirmation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 104)
    print("INVALIDATION CONDITIONS")
    print("-" * 104)

    for number, condition in enumerate(
        result.invalidation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 104)
    print("WARNINGS")
    print("-" * 104)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(f"{number}. {warning}")

    print("-" * 104)
    print("EXPLANATION")
    print("-" * 104)
    print(result.explanation)
    print("-" * 104)
    print(
        "Method                           : "
        "RULE-BASED PARTICIPANT MASTER DECISION"
    )
    print(
        f"Status                           : "
        f"{result.status}"
    )
    print("=" * 104)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete AQSD Participant Master Decision Engine."
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
        result = run_participant_master_decision_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 104)
        print("AQSD PARTICIPANT MASTER DECISION ENGINE")
        print("=" * 104)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 104)

        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()