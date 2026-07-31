"""
AQSD
Participant Risk Engine

Module : APD-014
Version: 1.0.0
Author : AQSD

Description
-----------
Measures the major risks present in institutional participant data.

Risk dimensions
---------------
- Positioning Risk
- Momentum Conflict Risk
- Institutional Alignment Risk
- Reversal Risk
- Continuation Failure Risk
- Regime Transition Risk
- Cycle Risk
- Probability Uncertainty Risk
- Data Quality Risk
- Overall Participant Risk

Inputs
------
- Participant Historical Change Engine
- Participant Decision Summary Engine
- Institutional Probability Engine
- Participant Regime Engine
- Participant Cycle Engine

Outputs
-------
- Individual risk scores from 0 to 100
- Overall risk score
- Overall risk level
- Dominant risk
- Risk direction
- Risk environment
- Risk warnings
- Explainable interpretation

Important
---------
A high risk score does not automatically mean that the market will fall.

It means participant evidence is uncertain, conflicted, vulnerable to
reversal, or insufficiently confirmed.

This engine does not generate BUY, SELL or SHORT instructions.
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


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-014"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class RiskComponent:
    """
    One participant-risk component.
    """

    name: str
    score: int
    level: str
    weight: float
    contribution: float
    explanation: str


@dataclass(frozen=True)
class ParticipantRiskResult:
    """
    Complete APD-014 participant-risk result.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    institutional_alignment: str

    primary_regime: str
    current_cycle: str
    highest_probability_scenario: str

    positioning_risk: int
    momentum_conflict_risk: int
    alignment_risk: int
    reversal_risk: int
    continuation_failure_risk: int
    transition_risk: int
    cycle_risk: int
    probability_uncertainty_risk: int
    data_quality_risk: int

    overall_risk_score: int
    overall_risk_level: str
    dominant_risk: str
    dominant_risk_score: int

    risk_direction: str
    risk_environment: str
    expected_risk_behaviour: str
    recommended_analytical_posture: str

    warnings: tuple[str, ...]
    components: tuple[RiskComponent, ...]
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
    Return True when text indicates mixed evidence.
    """

    return "MIXED" in value.upper()


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def clamp_score(
    value: float,
) -> int:
    """
    Limit a score to the range 0-100.
    """

    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


def risk_level_from_score(
    score: int,
) -> str:
    """
    Convert a numeric risk score into a risk level.
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


def available_change_count(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count available daily, weekly and monthly changes.
    """

    values = (
        historical_result.institutional_daily_net_change,
        historical_result.institutional_weekly_net_change,
        historical_result.institutional_monthly_net_change,
    )

    return sum(
        value is not None
        for value in values
    )


def change_direction(
    value: float | None,
) -> int:
    """
    Convert a change into a signed direction.
    """

    if value is None:
        return 0

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def count_positive_changes(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count positive institutional net-position changes.
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


def count_negative_changes(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Count negative institutional net-position changes.
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
# POSITIONING RISK
# ==========================================================

def calculate_positioning_risk(
    decision_summary: ParticipantDecisionSummary,
) -> int:
    """
    Measure risk caused by extreme current positioning.

    Extreme bullish or bearish exposure increases vulnerability to
    sharp reversals, covering or liquidation.
    """

    positioning = (
        decision_summary.current_positioning.upper()
    )

    if positioning in {
        "STRONGLY BULLISH",
        "STRONGLY BEARISH",
    }:
        return 65

    if positioning in {
        "BULLISH",
        "BEARISH",
    }:
        return 42

    return 25


# ==========================================================
# MOMENTUM CONFLICT RISK
# ==========================================================

def calculate_momentum_conflict_risk(
    decision_summary: ParticipantDecisionSummary,
) -> int:
    """
    Measure conflict between current exposure and momentum.
    """

    positioning = (
        decision_summary.current_positioning
    )

    momentum = decision_summary.momentum

    conflict = (
        (
            contains_bearish(positioning)
            and contains_improving(momentum)
        )
        or
        (
            contains_bullish(positioning)
            and contains_deteriorating(momentum)
        )
    )

    if conflict:
        if (
            "STRONGLY" in positioning.upper()
            and "STRONGLY" in momentum.upper()
        ):
            return 82

        return 70

    if (
        contains_mixed(momentum)
        or "INSUFFICIENT" in momentum.upper()
    ):
        return 58

    return 24


# ==========================================================
# ALIGNMENT RISK
# ==========================================================

def calculate_alignment_risk(
    decision_summary: ParticipantDecisionSummary,
) -> int:
    """
    Measure disagreement among FII, PRO and DII.
    """

    alignment = (
        decision_summary
        .institutional_alignment
        .upper()
    )

    if "MIXED" in alignment:
        return 82

    if "MAJORITY" in alignment:
        return 45

    if "FULL" in alignment:
        return 18

    return 60


# ==========================================================
# REVERSAL RISK
# ==========================================================

def calculate_reversal_risk(
    *,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    cycle_result: ParticipantCycleResult,
) -> int:
    """
    Measure the risk that the prevailing exposure reverses.
    """

    positioning = (
        decision_summary.current_positioning
    )

    momentum = decision_summary.momentum

    score = 20.0

    if (
        contains_bearish(positioning)
        and contains_improving(momentum)
    ):
        score += 35

    if (
        contains_bullish(positioning)
        and contains_deteriorating(momentum)
    ):
        score += 35

    if cycle_result.current_cycle in {
        "RECOVERY",
        "CAPITULATION",
        "LONG LIQUIDATION",
        "TRANSITION",
    }:
        score += 18

    reversal_probability = max(
        probability_result.bullish_recovery_probability,
        probability_result.bearish_reversal_probability,
    )

    score += min(
        reversal_probability * 0.35,
        20,
    )

    if probability_result.probability_confidence < 55:
        score += 8

    return clamp_score(score)


# ==========================================================
# CONTINUATION FAILURE RISK
# ==========================================================

def calculate_continuation_failure_risk(
    probability_result: InstitutionalProbabilityResult,
) -> int:
    """
    Measure the risk that the leading scenario fails.
    """

    highest = (
        probability_result.highest_probability
    )

    confidence = (
        probability_result.probability_confidence
    )

    score = 100 - highest

    if confidence < 50:
        score += 18

    elif confidence < 65:
        score += 10

    elif confidence >= 80:
        score -= 10

    if probability_result.institutional_strength == "LOW":
        score += 12

    elif probability_result.institutional_strength == "MODERATE":
        score += 5

    return clamp_score(score)


# ==========================================================
# TRANSITION RISK
# ==========================================================

def calculate_transition_risk(
    regime_result: ParticipantRegimeResult,
) -> int:
    """
    Measure instability caused by an emerging or changing regime.
    """

    regime = regime_result.primary_regime.upper()
    maturity = regime_result.regime_maturity.upper()
    strength = regime_result.regime_strength.upper()

    score = 20.0

    if regime in {
        "SHORT COVERING",
        "LONG UNWINDING",
        "BULLISH TRANSITION",
        "BEARISH TRANSITION",
        "CONFLICTED TRANSITION",
    }:
        score += 38

    if maturity in {
        "EMERGING",
        "EARLY",
    }:
        score += 22

    elif maturity == "DEVELOPING":
        score += 12

    if strength == "WEAK":
        score += 15

    elif strength == "MODERATE":
        score += 8

    if regime_result.regime_confidence < 55:
        score += 10

    return clamp_score(score)


# ==========================================================
# CYCLE RISK
# ==========================================================

def calculate_cycle_risk(
    cycle_result: ParticipantCycleResult,
) -> int:
    """
    Measure risk associated with the current participant cycle.
    """

    cycle = cycle_result.current_cycle.upper()
    maturity = cycle_result.cycle_maturity.upper()

    cycle_base_scores = {
        "RECOVERY": 72,
        "CAPITULATION": 88,
        "TRANSITION": 82,
        "LONG LIQUIDATION": 76,
        "SHORT BUILD-UP": 62,
        "DISTRIBUTION": 66,
        "EARLY ACCUMULATION": 60,
        "LATE ACCUMULATION": 42,
        "MARKUP": 32,
        "RE-ACCUMULATION": 40,
        "RE-DISTRIBUTION": 58,
        "CONSOLIDATION": 64,
    }

    score = cycle_base_scores.get(
        cycle,
        65,
    )

    if maturity == "EARLY":
        score += 8

    elif maturity == "MATURE":
        score -= 6

    if cycle_result.cycle_confidence < 50:
        score += 12

    elif cycle_result.cycle_confidence >= 75:
        score -= 8

    return clamp_score(score)


# ==========================================================
# PROBABILITY UNCERTAINTY RISK
# ==========================================================

def calculate_probability_uncertainty_risk(
    probability_result: InstitutionalProbabilityResult,
) -> int:
    """
    Measure uncertainty in the scenario distribution.
    """

    probabilities = sorted(
        [
            probability_result.bullish_continuation_probability,
            probability_result.bearish_continuation_probability,
            probability_result.bullish_recovery_probability,
            probability_result.bearish_reversal_probability,
            probability_result.sideways_probability,
        ],
        reverse=True,
    )

    highest = probabilities[0]
    second = probabilities[1]

    separation = highest - second

    score = 70.0

    score -= min(
        separation * 1.5,
        35,
    )

    score += (
        100
        - probability_result.probability_confidence
    ) * 0.30

    if probability_result.institutional_strength == "LOW":
        score += 12

    elif probability_result.institutional_strength == "HIGH":
        score -= 8

    return clamp_score(score)


# ==========================================================
# DATA QUALITY RISK
# ==========================================================

def calculate_data_quality_risk(
    historical_result: ParticipantHistoricalResult,
) -> int:
    """
    Measure whether sufficient comparison periods are available.
    """

    available_periods = available_change_count(
        historical_result
    )

    if available_periods == 3:
        return 12

    if available_periods == 2:
        return 38

    if available_periods == 1:
        return 68

    return 95


# ==========================================================
# COMPONENT CREATION
# ==========================================================

def create_risk_component(
    *,
    name: str,
    score: int,
    weight: float,
    explanation: str,
) -> RiskComponent:
    """
    Create one weighted risk component.
    """

    contribution = round(
        score * weight,
        2,
    )

    return RiskComponent(
        name=name,
        score=score,
        level=risk_level_from_score(score),
        weight=weight,
        contribution=contribution,
        explanation=explanation,
    )


def build_risk_components(
    *,
    positioning_risk: int,
    momentum_conflict_risk: int,
    alignment_risk: int,
    reversal_risk: int,
    continuation_failure_risk: int,
    transition_risk: int,
    cycle_risk: int,
    probability_uncertainty_risk: int,
    data_quality_risk: int,
) -> tuple[RiskComponent, ...]:
    """
    Build weighted risk components.
    """

    return (
        create_risk_component(
            name="POSITIONING RISK",
            score=positioning_risk,
            weight=0.10,
            explanation=(
                "Measures vulnerability created by extreme current "
                "institutional exposure."
            ),
        ),
        create_risk_component(
            name="MOMENTUM CONFLICT RISK",
            score=momentum_conflict_risk,
            weight=0.14,
            explanation=(
                "Measures conflict between current institutional "
                "positioning and multi-period momentum."
            ),
        ),
        create_risk_component(
            name="ALIGNMENT RISK",
            score=alignment_risk,
            weight=0.12,
            explanation=(
                "Measures disagreement among FII, PRO and DII."
            ),
        ),
        create_risk_component(
            name="REVERSAL RISK",
            score=reversal_risk,
            weight=0.15,
            explanation=(
                "Measures vulnerability to a reversal or covering move."
            ),
        ),
        create_risk_component(
            name="CONTINUATION FAILURE RISK",
            score=continuation_failure_risk,
            weight=0.12,
            explanation=(
                "Measures the chance that the leading scenario does "
                "not continue as expected."
            ),
        ),
        create_risk_component(
            name="REGIME TRANSITION RISK",
            score=transition_risk,
            weight=0.12,
            explanation=(
                "Measures instability caused by an emerging or "
                "changing participant regime."
            ),
        ),
        create_risk_component(
            name="CYCLE RISK",
            score=cycle_risk,
            weight=0.10,
            explanation=(
                "Measures instability associated with the current "
                "participant cycle."
            ),
        ),
        create_risk_component(
            name="PROBABILITY UNCERTAINTY RISK",
            score=probability_uncertainty_risk,
            weight=0.10,
            explanation=(
                "Measures uncertainty and lack of separation between "
                "scenario probabilities."
            ),
        ),
        create_risk_component(
            name="DATA QUALITY RISK",
            score=data_quality_risk,
            weight=0.05,
            explanation=(
                "Measures whether daily, weekly and monthly historical "
                "comparisons are available."
            ),
        ),
    )


# ==========================================================
# OVERALL RISK
# ==========================================================

def calculate_overall_risk_score(
    components: tuple[RiskComponent, ...],
) -> int:
    """
    Calculate weighted overall participant risk.
    """

    total_weight = sum(
        component.weight
        for component in components
    )

    if total_weight == 0:
        return 0

    total_contribution = sum(
        component.contribution
        for component in components
    )

    return clamp_score(
        total_contribution / total_weight
    )


def determine_dominant_risk(
    components: tuple[RiskComponent, ...],
) -> RiskComponent:
    """
    Return the highest-scoring risk component.
    """

    return max(
        components,
        key=lambda component: component.score,
    )


# ==========================================================
# RISK DIRECTION
# ==========================================================

def determine_risk_direction(
    *,
    decision_summary: ParticipantDecisionSummary,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> str:
    """
    Determine the broad direction in which risk is concentrated.
    """

    if (
        contains_bearish(
            decision_summary.current_positioning
        )
        and regime_result.primary_regime
        in {
            "SHORT COVERING",
            "BULLISH TRANSITION",
        }
    ):
        return "TWO-SIDED WITH BULLISH RECOVERY RISK"

    if (
        contains_bullish(
            decision_summary.current_positioning
        )
        and regime_result.primary_regime
        in {
            "LONG UNWINDING",
            "BEARISH TRANSITION",
        }
    ):
        return "TWO-SIDED WITH BEARISH REVERSAL RISK"

    if cycle_result.cycle_direction == "BULLISH":
        return "BULLISH DIRECTION WITH REVERSAL VULNERABILITY"

    if cycle_result.cycle_direction == "BEARISH":
        return "BEARISH DIRECTION WITH COVERING VULNERABILITY"

    return "NON-DIRECTIONAL OR CONFLICTED RISK"


# ==========================================================
# RISK ENVIRONMENT
# ==========================================================

def determine_risk_environment(
    *,
    overall_risk_level: str,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> str:
    """
    Build a compact risk-environment label.
    """

    return (
        f"{overall_risk_level} RISK | "
        f"{regime_result.primary_regime} | "
        f"{cycle_result.current_cycle}"
    )


# ==========================================================
# EXPECTED RISK BEHAVIOUR
# ==========================================================

def determine_expected_risk_behaviour(
    *,
    overall_risk_level: str,
    cycle_result: ParticipantCycleResult,
    regime_result: ParticipantRegimeResult,
) -> str:
    """
    Describe the likely behaviour created by current risks.
    """

    if cycle_result.current_cycle == "RECOVERY":
        return (
            "RECOVERY MAY CONTINUE, BUT SHARP REVERSALS REMAIN "
            "POSSIBLE BECAUSE BEARISH EXPOSURE IS STILL PRESENT"
        )

    if cycle_result.current_cycle == "CAPITULATION":
        return (
            "EXTREME VOLATILITY AND RAPID DIRECTIONAL REVERSALS "
            "ARE POSSIBLE"
        )

    if regime_result.primary_regime == "CONSOLIDATION":
        return (
            "RANGE EXPANSION, FALSE BREAKOUTS AND RAPID REVERSALS "
            "ARE POSSIBLE"
        )

    if overall_risk_level in {
        "VERY HIGH",
        "HIGH",
    }:
        return (
            "PARTICIPANT SIGNALS REQUIRE CONFIRMATION BECAUSE "
            "CURRENT CONDITIONS ARE VULNERABLE TO FAILURE"
        )

    if overall_risk_level == "MODERATE":
        return (
            "THE LEADING PARTICIPANT SCENARIO IS USABLE, BUT "
            "CONFLICTING SIGNALS SHOULD BE MONITORED"
        )

    return (
        "PARTICIPANT CONDITIONS ARE RELATIVELY STABLE, ALTHOUGH "
        "NORMAL MARKET RISK REMAINS"
    )


# ==========================================================
# ANALYTICAL POSTURE
# ==========================================================

def determine_analytical_posture(
    overall_risk_level: str,
) -> str:
    """
    Recommend an analytical posture without giving trade instructions.
    """

    posture_map = {
        "VERY HIGH": (
            "WAIT FOR STRONGER CONFIRMATION AND AVOID RELYING "
            "ON PARTICIPANT DATA ALONE"
        ),
        "HIGH": (
            "USE CONSERVATIVE INTERPRETATION AND REQUIRE "
            "CONFIRMATION FROM PRICE, STRUCTURE AND OPTIONS DATA"
        ),
        "MODERATE": (
            "USE PARTICIPANT INTELLIGENCE WITH NORMAL CONFIRMATION "
            "FROM OTHER AQSD ENGINES"
        ),
        "LOW TO MODERATE": (
            "PARTICIPANT SIGNALS ARE REASONABLY STABLE BUT SHOULD "
            "STILL BE CROSS-CHECKED"
        ),
        "LOW": (
            "PARTICIPANT CONDITIONS ARE WELL ALIGNED AND CAN RECEIVE "
            "NORMAL WEIGHT IN THE MASTER DECISION ENGINE"
        ),
    }

    return posture_map.get(
        overall_risk_level,
        "REQUIRE ADDITIONAL CONFIRMATION",
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    *,
    components: tuple[RiskComponent, ...],
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> tuple[str, ...]:
    """
    Build concise risk warnings.
    """

    warnings: list[str] = []

    for component in components:
        if component.score >= 70:
            warnings.append(
                f"{component.name}: {component.level} "
                f"({component.score}%)."
            )

    if contains_mixed(
        decision_summary.institutional_alignment
    ):
        warnings.append(
            "FII, PRO and DII are not fully aligned."
        )

    if probability_result.probability_confidence < 60:
        warnings.append(
            "Scenario probability confidence is below 60%."
        )

    if regime_result.regime_maturity in {
        "EMERGING",
        "EARLY",
    }:
        warnings.append(
            "The participant regime is still emerging."
        )

    if cycle_result.cycle_maturity == "EARLY":
        warnings.append(
            "The current participant cycle is in an early phase."
        )

    if not warnings:
        warnings.append(
            "No major participant-specific warning is currently active."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# EXPLANATION
# ==========================================================

def build_explanation(
    *,
    overall_risk_score: int,
    overall_risk_level: str,
    dominant_risk: RiskComponent,
    risk_direction: str,
    decision_summary: ParticipantDecisionSummary,
    probability_result: InstitutionalProbabilityResult,
    regime_result: ParticipantRegimeResult,
    cycle_result: ParticipantCycleResult,
) -> str:
    """
    Build the final participant-risk explanation.
    """

    return (
        f"Overall participant risk is {overall_risk_level.lower()} "
        f"at {overall_risk_score}%. The dominant risk is "
        f"{dominant_risk.name.lower()} at "
        f"{dominant_risk.score}%. Current institutional positioning "
        f"is {decision_summary.current_positioning.lower()}, while "
        f"momentum is {decision_summary.momentum.lower()}. "
        f"The leading scenario is "
        f"{probability_result.highest_probability_scenario.lower()} "
        f"at {probability_result.highest_probability:.1f}% with "
        f"{probability_result.probability_confidence}% probability "
        f"confidence. The participant regime is "
        f"{regime_result.primary_regime.lower()}, and the current "
        f"cycle is {cycle_result.current_cycle.lower()}. "
        f"Risk direction is classified as "
        f"{risk_direction.lower()}."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_participant_risk_engine(
    requested_date: date,
) -> ParticipantRiskResult:
    """
    Run APD-014.
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

    cycle_result = (
        run_participant_cycle_engine(
            requested_date
        )
    )

    positioning_risk = calculate_positioning_risk(
        decision_summary
    )

    momentum_conflict_risk = (
        calculate_momentum_conflict_risk(
            decision_summary
        )
    )

    alignment_risk = calculate_alignment_risk(
        decision_summary
    )

    reversal_risk = calculate_reversal_risk(
        decision_summary=decision_summary,
        probability_result=probability_result,
        cycle_result=cycle_result,
    )

    continuation_failure_risk = (
        calculate_continuation_failure_risk(
            probability_result
        )
    )

    transition_risk = calculate_transition_risk(
        regime_result
    )

    cycle_risk = calculate_cycle_risk(
        cycle_result
    )

    probability_uncertainty_risk = (
        calculate_probability_uncertainty_risk(
            probability_result
        )
    )

    data_quality_risk = calculate_data_quality_risk(
        historical_result
    )

    components = build_risk_components(
        positioning_risk=positioning_risk,
        momentum_conflict_risk=momentum_conflict_risk,
        alignment_risk=alignment_risk,
        reversal_risk=reversal_risk,
        continuation_failure_risk=continuation_failure_risk,
        transition_risk=transition_risk,
        cycle_risk=cycle_risk,
        probability_uncertainty_risk=(
            probability_uncertainty_risk
        ),
        data_quality_risk=data_quality_risk,
    )

    overall_risk_score = calculate_overall_risk_score(
        components
    )

    overall_risk_level = risk_level_from_score(
        overall_risk_score
    )

    dominant_risk_component = determine_dominant_risk(
        components
    )

    risk_direction = determine_risk_direction(
        decision_summary=decision_summary,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    risk_environment = determine_risk_environment(
        overall_risk_level=overall_risk_level,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    expected_risk_behaviour = (
        determine_expected_risk_behaviour(
            overall_risk_level=overall_risk_level,
            cycle_result=cycle_result,
            regime_result=regime_result,
        )
    )

    recommended_analytical_posture = (
        determine_analytical_posture(
            overall_risk_level
        )
    )

    warnings = build_warnings(
        components=components,
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    explanation = build_explanation(
        overall_risk_score=overall_risk_score,
        overall_risk_level=overall_risk_level,
        dominant_risk=dominant_risk_component,
        risk_direction=risk_direction,
        decision_summary=decision_summary,
        probability_result=probability_result,
        regime_result=regime_result,
        cycle_result=cycle_result,
    )

    return ParticipantRiskResult(
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
        current_cycle=cycle_result.current_cycle,
        highest_probability_scenario=(
            probability_result.highest_probability_scenario
        ),
        positioning_risk=positioning_risk,
        momentum_conflict_risk=momentum_conflict_risk,
        alignment_risk=alignment_risk,
        reversal_risk=reversal_risk,
        continuation_failure_risk=(
            continuation_failure_risk
        ),
        transition_risk=transition_risk,
        cycle_risk=cycle_risk,
        probability_uncertainty_risk=(
            probability_uncertainty_risk
        ),
        data_quality_risk=data_quality_risk,
        overall_risk_score=overall_risk_score,
        overall_risk_level=overall_risk_level,
        dominant_risk=dominant_risk_component.name,
        dominant_risk_score=dominant_risk_component.score,
        risk_direction=risk_direction,
        risk_environment=risk_environment,
        expected_risk_behaviour=expected_risk_behaviour,
        recommended_analytical_posture=(
            recommended_analytical_posture
        ),
        warnings=warnings,
        components=components,
        explanation=explanation,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: ParticipantRiskResult,
) -> None:
    """
    Display the APD-014 terminal report.
    """

    print()
    print("=" * 94)
    print("AQSD PARTICIPANT RISK ENGINE")
    print("=" * 94)
    print(f"Module                       : {MODULE_ID}")
    print(f"Version                      : {MODULE_VERSION}")
    print(f"Requested Date               : {result.requested_date}")
    print(f"Analysis Date                : {result.analysis_date}")
    print("-" * 94)
    print(
        f"Current Positioning          : "
        f"{result.current_positioning}"
    )
    print(
        f"Momentum                     : "
        f"{result.momentum}"
    )
    print(
        f"Institutional Alignment      : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Primary Regime               : "
        f"{result.primary_regime}"
    )
    print(
        f"Current Cycle                : "
        f"{result.current_cycle}"
    )
    print(
        f"Highest Probability Scenario : "
        f"{result.highest_probability_scenario}"
    )
    print("=" * 94)
    print("RISK COMPONENTS")
    print("-" * 94)

    for component in result.components:
        print(
            f"{component.name:<32}: "
            f"{component.score:>3}% | "
            f"{component.level:<16} | "
            f"Weight {component.weight:.0%}"
        )

        print(
            f"  Explanation                : "
            f"{component.explanation}"
        )

    print("=" * 94)
    print("OVERALL RISK")
    print("-" * 94)
    print(
        f"Overall Risk Score           : "
        f"{result.overall_risk_score}%"
    )
    print(
        f"Overall Risk Level           : "
        f"{result.overall_risk_level}"
    )
    print(
        f"Dominant Risk                : "
        f"{result.dominant_risk}"
    )
    print(
        f"Dominant Risk Score          : "
        f"{result.dominant_risk_score}%"
    )
    print(
        f"Risk Direction               : "
        f"{result.risk_direction}"
    )
    print(
        f"Risk Environment             : "
        f"{result.risk_environment}"
    )
    print("-" * 94)
    print(
        f"Expected Risk Behaviour      : "
        f"{result.expected_risk_behaviour}"
    )
    print(
        f"Analytical Posture           : "
        f"{result.recommended_analytical_posture}"
    )
    print("-" * 94)
    print("WARNINGS")
    print("-" * 94)

    for warning_number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(
            f"{warning_number}. {warning}"
        )

    print("-" * 94)
    print("EXPLANATION")
    print("-" * 94)
    print(result.explanation)
    print("-" * 94)
    print(f"Status                       : {result.status}")
    print("=" * 94)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Measure participant positioning, regime, cycle and "
            "probability risks from APD intelligence."
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
        result = run_participant_risk_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 94)
        print("AQSD PARTICIPANT RISK ENGINE")
        print("=" * 94)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 94)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()