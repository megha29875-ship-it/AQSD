"""
AQSD
Institutional Probability Engine

Module : APD-011
Version: 1.0.0
Author : AQSD

Description
-----------
Converts the AQSD Participant Decision Summary and historical
participant intelligence into explainable institutional scenario
probabilities.

Scenarios
---------
- Bullish Continuation
- Bearish Continuation
- Bullish Recovery
- Bearish Reversal
- Sideways Consolidation

Inputs
------
- Current institutional positioning
- Institutional momentum
- Structural state
- Institutional alignment
- Daily, weekly and monthly net-position changes
- Participant confidence
- Participant risk level

Important
---------
These are analytical scenario probabilities derived from transparent
rules. They are not statistically calibrated forecasting probabilities.

This engine does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

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

MODULE_ID: Final[str] = "APD-011"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class ScenarioProbability:
    """
    One institutional scenario and its probability.
    """

    scenario: str
    probability: float
    rank: int
    explanation: str


@dataclass(frozen=True)
class InstitutionalProbabilityResult:
    """
    Complete APD-011 result.
    """

    requested_date: date
    analysis_date: date

    current_positioning: str
    momentum: str
    structural_state: str
    institutional_alignment: str
    risk_level: str

    bullish_continuation_probability: float
    bearish_continuation_probability: float
    bullish_recovery_probability: float
    bearish_reversal_probability: float
    sideways_probability: float

    highest_probability_scenario: str
    highest_probability: float

    institutional_strength: str
    probability_confidence: int
    expected_behaviour: str
    explanation: str

    scenarios: tuple[ScenarioProbability, ...]
    status: str


# ==========================================================
# SCORE MODEL
# ==========================================================

@dataclass
class ScenarioScores:
    """
    Mutable scenario scores before normalization.
    """

    bullish_continuation: float = 10.0
    bearish_continuation: float = 10.0
    bullish_recovery: float = 10.0
    bearish_reversal: float = 10.0
    sideways: float = 10.0


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
    Return True when a label represents mixed conditions.
    """

    return "MIXED" in value.upper()


# ==========================================================
# NUMERIC HELPERS
# ==========================================================

def signed_direction(
    value: float | None,
    neutral_threshold: float = 0.0,
) -> int:
    """
    Convert an optional number into:

     1 = positive
     0 = neutral or unavailable
    -1 = negative
    """

    if value is None:
        return 0

    if value > neutral_threshold:
        return 1

    if value < -neutral_threshold:
        return -1

    return 0


def normalize_probabilities(
    scores: ScenarioScores,
) -> dict[str, float]:
    """
    Convert positive scenario scores into percentages totalling 100.
    """

    raw_scores = {
        "BULLISH CONTINUATION": max(
            scores.bullish_continuation,
            0.1,
        ),
        "BEARISH CONTINUATION": max(
            scores.bearish_continuation,
            0.1,
        ),
        "BULLISH RECOVERY": max(
            scores.bullish_recovery,
            0.1,
        ),
        "BEARISH REVERSAL": max(
            scores.bearish_reversal,
            0.1,
        ),
        "SIDEWAYS CONSOLIDATION": max(
            scores.sideways,
            0.1,
        ),
    }

    total_score = sum(
        raw_scores.values()
    )

    unrounded = {
        scenario: (
            score / total_score
        )
        * 100
        for scenario, score in raw_scores.items()
    }

    probabilities = {
        scenario: round(
            probability,
            1,
        )
        for scenario, probability in unrounded.items()
    }

    rounding_difference = round(
        100.0 - sum(probabilities.values()),
        1,
    )

    highest_scenario = max(
        probabilities,
        key=probabilities.get,
    )

    probabilities[highest_scenario] = round(
        probabilities[highest_scenario]
        + rounding_difference,
        1,
    )

    return probabilities


# ==========================================================
# CURRENT POSITIONING SCORES
# ==========================================================

def apply_positioning_scores(
    *,
    scores: ScenarioScores,
    current_positioning: str,
) -> None:
    """
    Apply current institutional-positioning evidence.
    """

    positioning = current_positioning.upper()

    if positioning == "STRONGLY BULLISH":
        scores.bullish_continuation += 35
        scores.bearish_reversal += 12
        scores.sideways -= 3

    elif positioning == "BULLISH":
        scores.bullish_continuation += 24
        scores.bearish_reversal += 9
        scores.sideways += 2

    elif positioning == "STRONGLY BEARISH":
        scores.bearish_continuation += 35
        scores.bullish_recovery += 12
        scores.sideways -= 3

    elif positioning == "BEARISH":
        scores.bearish_continuation += 24
        scores.bullish_recovery += 9
        scores.sideways += 2

    else:
        scores.sideways += 22
        scores.bullish_recovery += 4
        scores.bearish_reversal += 4


# ==========================================================
# MOMENTUM SCORES
# ==========================================================

def apply_momentum_scores(
    *,
    scores: ScenarioScores,
    current_positioning: str,
    momentum: str,
) -> None:
    """
    Apply institutional momentum evidence.
    """

    bullish_positioning = contains_bullish(
        current_positioning
    )

    bearish_positioning = contains_bearish(
        current_positioning
    )

    normalized_momentum = momentum.upper()

    if normalized_momentum == "STRONGLY IMPROVING":
        if bearish_positioning:
            scores.bullish_recovery += 30
            scores.bearish_continuation -= 8

        elif bullish_positioning:
            scores.bullish_continuation += 28
            scores.bearish_reversal -= 5

        else:
            scores.bullish_recovery += 17

    elif normalized_momentum == "IMPROVING":
        if bearish_positioning:
            scores.bullish_recovery += 21
            scores.bearish_continuation -= 4

        elif bullish_positioning:
            scores.bullish_continuation += 19

        else:
            scores.bullish_recovery += 12

    elif normalized_momentum == "STRONGLY DETERIORATING":
        if bullish_positioning:
            scores.bearish_reversal += 30
            scores.bullish_continuation -= 8

        elif bearish_positioning:
            scores.bearish_continuation += 28
            scores.bullish_recovery -= 5

        else:
            scores.bearish_reversal += 17

    elif normalized_momentum == "DETERIORATING":
        if bullish_positioning:
            scores.bearish_reversal += 21
            scores.bullish_continuation -= 4

        elif bearish_positioning:
            scores.bearish_continuation += 19

        else:
            scores.bearish_reversal += 12

    else:
        scores.sideways += 18


# ==========================================================
# STRUCTURAL SCORES
# ==========================================================

def apply_structural_scores(
    *,
    scores: ScenarioScores,
    structural_state: str,
) -> None:
    """
    Apply the participant structural-state evidence.
    """

    state = structural_state.upper()

    if state == "BULLISH STRUCTURE STRENGTHENING":
        scores.bullish_continuation += 22
        scores.bearish_reversal -= 4

    elif state == "BEARISH STRUCTURE STRENGTHENING":
        scores.bearish_continuation += 22
        scores.bullish_recovery -= 4

    elif state == "BEARISH STRUCTURE WITH RECOVERY":
        scores.bullish_recovery += 23
        scores.bearish_continuation += 7

    elif state == "BULLISH STRUCTURE LOSING STRENGTH":
        scores.bearish_reversal += 23
        scores.bullish_continuation += 7

    elif state == "NEUTRAL STRUCTURE":
        scores.sideways += 20

    else:
        scores.sideways += 12
        scores.bullish_recovery += 4
        scores.bearish_reversal += 4


# ==========================================================
# ALIGNMENT SCORES
# ==========================================================

def apply_alignment_scores(
    *,
    scores: ScenarioScores,
    institutional_alignment: str,
    current_positioning: str,
) -> None:
    """
    Apply FII, PRO and DII alignment evidence.
    """

    alignment = institutional_alignment.upper()

    if "FULL BULLISH" in alignment:
        scores.bullish_continuation += 18
        scores.sideways -= 4

    elif "FULL BEARISH" in alignment:
        scores.bearish_continuation += 18
        scores.sideways -= 4

    elif "MAJORITY BULLISH" in alignment:
        scores.bullish_continuation += 11
        scores.sideways += 2

    elif "MAJORITY BEARISH" in alignment:
        scores.bearish_continuation += 11
        scores.sideways += 2

    elif "MIXED" in alignment:
        scores.sideways += 17

        if contains_bearish(current_positioning):
            scores.bullish_recovery += 5

        elif contains_bullish(current_positioning):
            scores.bearish_reversal += 5


# ==========================================================
# MULTI-PERIOD CHANGE SCORES
# ==========================================================

def apply_change_scores(
    *,
    scores: ScenarioScores,
    historical_result: ParticipantHistoricalResult,
) -> None:
    """
    Apply daily, weekly and monthly institutional net changes.
    """

    period_changes = (
        (
            historical_result.institutional_daily_net_change,
            5.0,
        ),
        (
            historical_result.institutional_weekly_net_change,
            8.0,
        ),
        (
            historical_result.institutional_monthly_net_change,
            10.0,
        ),
    )

    current_positioning = (
        historical_result.institutional_bias
    )

    for change_value, weight in period_changes:
        direction = signed_direction(
            change_value
        )

        if direction > 0:
            if contains_bearish(current_positioning):
                scores.bullish_recovery += weight
                scores.bearish_continuation -= weight * 0.20

            else:
                scores.bullish_continuation += weight

        elif direction < 0:
            if contains_bullish(current_positioning):
                scores.bearish_reversal += weight
                scores.bullish_continuation -= weight * 0.20

            else:
                scores.bearish_continuation += weight

        else:
            scores.sideways += weight * 0.40


# ==========================================================
# RISK SCORES
# ==========================================================

def apply_risk_scores(
    *,
    scores: ScenarioScores,
    risk_level: str,
) -> None:
    """
    Apply uncertainty based on the participant risk level.
    """

    risk = risk_level.upper()

    if risk == "HIGH":
        scores.sideways += 12
        scores.bullish_recovery += 3
        scores.bearish_reversal += 3

    elif risk == "MODERATE TO HIGH":
        scores.sideways += 9

    elif risk == "MODERATE":
        scores.sideways += 5

    elif risk == "LOW":
        scores.sideways -= 3


# ==========================================================
# PROBABILITY CONFIDENCE
# ==========================================================

def calculate_probability_confidence(
    *,
    decision_summary: ParticipantDecisionSummary,
    probabilities: dict[str, float],
) -> int:
    """
    Calculate confidence in the probability distribution.

    Confidence is based on:
    - APD-010 confidence
    - Separation between first and second scenarios
    - Institutional alignment
    - Risk level
    """

    sorted_values = sorted(
        probabilities.values(),
        reverse=True,
    )

    highest = sorted_values[0]
    second_highest = sorted_values[1]

    separation = (
        highest
        - second_highest
    )

    confidence = (
        decision_summary.confidence
    )

    confidence += int(
        min(separation, 25.0)
        * 0.6
    )

    alignment = (
        decision_summary
        .institutional_alignment
        .upper()
    )

    if "FULL" in alignment:
        confidence += 8

    elif "MAJORITY" in alignment:
        confidence += 4

    elif "MIXED" in alignment:
        confidence -= 7

    risk = decision_summary.risk_level.upper()

    if risk == "HIGH":
        confidence -= 8

    elif risk == "MODERATE TO HIGH":
        confidence -= 5

    elif risk == "LOW":
        confidence += 5

    return max(
        0,
        min(confidence, 100),
    )


# ==========================================================
# INSTITUTIONAL STRENGTH
# ==========================================================

def determine_institutional_strength(
    *,
    highest_probability: float,
    probability_confidence: int,
    institutional_alignment: str,
) -> str:
    """
    Determine the strength of the institutional signal.
    """

    alignment = institutional_alignment.upper()

    if (
        highest_probability >= 50
        and probability_confidence >= 70
        and "MIXED" not in alignment
    ):
        return "HIGH"

    if (
        highest_probability >= 38
        and probability_confidence >= 55
    ):
        return "MODERATE"

    return "LOW"


# ==========================================================
# SCENARIO EXPLANATIONS
# ==========================================================

def build_scenario_explanation(
    *,
    scenario: str,
    decision_summary: ParticipantDecisionSummary,
) -> str:
    """
    Build a short explanation for one scenario.
    """

    explanations = {
        "BULLISH CONTINUATION": (
            "Bullish institutional exposure and improving momentum "
            "support continued positive positioning."
        ),
        "BEARISH CONTINUATION": (
            "Negative institutional exposure remains dominant and "
            "supports continued bearish pressure."
        ),
        "BULLISH RECOVERY": (
            "Institutional positioning remains bearish, but improving "
            "net changes support recovery or short-covering potential."
        ),
        "BEARISH REVERSAL": (
            "Institutional positioning remains bullish, but weakening "
            "momentum creates reversal or profit-booking risk."
        ),
        "SIDEWAYS CONSOLIDATION": (
            "Mixed participant alignment and conflicting evidence "
            "increase the probability of consolidation or volatility."
        ),
    }

    base_explanation = explanations[scenario]

    return (
        f"{base_explanation} Current structure: "
        f"{decision_summary.structural_state.lower()}."
    )


# ==========================================================
# OVERALL EXPLANATION
# ==========================================================

def build_overall_explanation(
    *,
    decision_summary: ParticipantDecisionSummary,
    highest_scenario: str,
    highest_probability: float,
    probability_confidence: int,
) -> str:
    """
    Build the final APD-011 explanation.
    """

    return (
        f"Current institutional positioning is "
        f"{decision_summary.current_positioning.lower()}, while "
        f"momentum is {decision_summary.momentum.lower()}. "
        f"The participant structure is classified as "
        f"{decision_summary.structural_state.lower()}, with "
        f"{decision_summary.institutional_alignment.lower()}. "
        f"The highest analytical scenario is "
        f"{highest_scenario.lower()} at "
        f"{highest_probability:.1f}%. "
        f"Probability confidence is {probability_confidence}%. "
        f"{decision_summary.expected_behaviour.capitalize()}."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_institutional_probability_engine(
    requested_date: date,
) -> InstitutionalProbabilityResult:
    """
    Run APD-011.
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

    scores = ScenarioScores()

    apply_positioning_scores(
        scores=scores,
        current_positioning=(
            decision_summary.current_positioning
        ),
    )

    apply_momentum_scores(
        scores=scores,
        current_positioning=(
            decision_summary.current_positioning
        ),
        momentum=decision_summary.momentum,
    )

    apply_structural_scores(
        scores=scores,
        structural_state=(
            decision_summary.structural_state
        ),
    )

    apply_alignment_scores(
        scores=scores,
        institutional_alignment=(
            decision_summary.institutional_alignment
        ),
        current_positioning=(
            decision_summary.current_positioning
        ),
    )

    apply_change_scores(
        scores=scores,
        historical_result=historical_result,
    )

    apply_risk_scores(
        scores=scores,
        risk_level=decision_summary.risk_level,
    )

    probabilities = normalize_probabilities(
        scores
    )

    ordered_scenarios = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    highest_scenario = (
        ordered_scenarios[0][0]
    )

    highest_probability = (
        ordered_scenarios[0][1]
    )

    probability_confidence = (
        calculate_probability_confidence(
            decision_summary=decision_summary,
            probabilities=probabilities,
        )
    )

    institutional_strength = (
        determine_institutional_strength(
            highest_probability=highest_probability,
            probability_confidence=(
                probability_confidence
            ),
            institutional_alignment=(
                decision_summary
                .institutional_alignment
            ),
        )
    )

    scenario_results = tuple(
        ScenarioProbability(
            scenario=scenario,
            probability=probability,
            rank=rank,
            explanation=build_scenario_explanation(
                scenario=scenario,
                decision_summary=decision_summary,
            ),
        )
        for rank, (
            scenario,
            probability,
        ) in enumerate(
            ordered_scenarios,
            start=1,
        )
    )

    explanation = build_overall_explanation(
        decision_summary=decision_summary,
        highest_scenario=highest_scenario,
        highest_probability=highest_probability,
        probability_confidence=probability_confidence,
    )

    return InstitutionalProbabilityResult(
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
        risk_level=decision_summary.risk_level,
        bullish_continuation_probability=(
            probabilities["BULLISH CONTINUATION"]
        ),
        bearish_continuation_probability=(
            probabilities["BEARISH CONTINUATION"]
        ),
        bullish_recovery_probability=(
            probabilities["BULLISH RECOVERY"]
        ),
        bearish_reversal_probability=(
            probabilities["BEARISH REVERSAL"]
        ),
        sideways_probability=(
            probabilities["SIDEWAYS CONSOLIDATION"]
        ),
        highest_probability_scenario=(
            highest_scenario
        ),
        highest_probability=(
            highest_probability
        ),
        institutional_strength=(
            institutional_strength
        ),
        probability_confidence=(
            probability_confidence
        ),
        expected_behaviour=(
            decision_summary.expected_behaviour
        ),
        explanation=explanation,
        scenarios=scenario_results,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: InstitutionalProbabilityResult,
) -> None:
    """
    Display the APD-011 terminal report.
    """

    print()
    print("=" * 90)
    print("AQSD INSTITUTIONAL PROBABILITY ENGINE")
    print("=" * 90)
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Requested Date             : {result.requested_date}")
    print(f"Analysis Date              : {result.analysis_date}")
    print("-" * 90)
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
    print(
        f"Risk Level                 : "
        f"{result.risk_level}"
    )
    print("=" * 90)
    print("SCENARIO PROBABILITIES")
    print("-" * 90)

    for scenario in result.scenarios:
        print(
            f"{scenario.rank}. "
            f"{scenario.scenario:<26} "
            f": {scenario.probability:>5.1f}%"
        )

        print(
            f"   Explanation              : "
            f"{scenario.explanation}"
        )

    print("-" * 90)
    print(
        f"Highest Probability        : "
        f"{result.highest_probability_scenario}"
    )
    print(
        f"Highest Probability Value  : "
        f"{result.highest_probability:.1f}%"
    )
    print(
        f"Institutional Strength     : "
        f"{result.institutional_strength}"
    )
    print(
        f"Probability Confidence     : "
        f"{result.probability_confidence}%"
    )
    print("-" * 90)
    print(
        f"Expected Behaviour         : "
        f"{result.expected_behaviour}"
    )
    print("-" * 90)
    print("EXPLANATION")
    print("-" * 90)
    print(result.explanation)
    print("-" * 90)
    print(
        "Method                     : "
        "RULE-BASED ANALYTICAL PROBABILITIES"
    )
    print(
        f"Status                     : "
        f"{result.status}"
    )
    print("=" * 90)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Calculate explainable institutional scenario "
            "probabilities from APD intelligence."
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
        result = run_institutional_probability_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 90)
        print("AQSD INSTITUTIONAL PROBABILITY ENGINE")
        print("=" * 90)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 90)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()