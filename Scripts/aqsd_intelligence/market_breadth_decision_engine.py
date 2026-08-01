"""
AQSD
Market Breadth Decision Engine

Module : MBI-005
Version: 1.0.2
Author : AQSD

Description
-----------
Combines current NSE market breadth with breadth-change intelligence
to produce one consolidated and explainable market-internals result.

Input engines
-------------
- MBI-001 Market Breadth Engine
- MBI-004 Market Breadth Change Engine

Important
---------
This engine performs analytical decision support only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_intelligence.market_breadth_change_engine import (
    MarketBreadthChangeResult,
    run_market_breadth_change_engine,
)
from Scripts.aqsd_intelligence.market_breadth_engine import (
    DEFAULT_INPUT_FILE,
    MarketBreadthResult,
    run_market_breadth_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MBI-005"
MODULE_VERSION: Final[str] = "1.0.2"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class MarketBreadthDecisionResult:
    """
    Final consolidated market-breadth decision-support result.
    """

    requested_date: date
    analysis_date: date
    source_file: Path

    breadth_score: int
    breadth_bias: str
    breadth_quality: str

    breadth_momentum: str
    breadth_trend: str
    breadth_strength: str
    breadth_regime: str

    breadth_direction: str
    breadth_velocity: str
    breadth_acceleration: str

    risk_environment: str
    internal_market_health: str
    participation_quality: str
    divergence_risk: str

    sector_rotation: str
    sector_rotation_strength: str
    improving_sectors: int
    deteriorating_sectors: int

    daily_breadth_change: int | None
    weekly_breadth_score_change: int | None

    reversal_risk_score: int
    reversal_risk_level: str
    reversal_direction: str

    expected_behaviour: str
    market_environment: str
    analytical_posture: str

    current_confidence: int
    change_confidence: int
    decision_confidence: int
    decision_quality: str

    master_conclusion: str
    concise_summary: str
    explanation: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    current_status: str
    change_status: str
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def clamp_score(
    value: float,
) -> int:
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


def contains_any(
    value: str,
    keywords: tuple[str, ...],
) -> bool:
    """
    Return True when text contains any supplied keyword.
    """

    text = value.upper()

    return any(
        keyword.upper() in text
        for keyword in keywords
    )


def format_optional_change(
    value: int | None,
) -> str:
    """
    Format an optional signed integer.
    """

    if value is None:
        return "NOT AVAILABLE"

    return f"{value:+d}"


# ==========================================================
# BREADTH BIAS
# ==========================================================

def determine_breadth_bias(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
) -> str:
    """
    Determine the consolidated market-breadth bias.
    """

    score = current.breadth_score
    direction = change.breadth_direction.upper()
    regime = current.breadth_regime.upper()
    risk_environment = current.risk_environment.upper()

    if (
        score >= 65
        and "IMPROVING" in direction
        and "BULLISH" in regime
    ):
        return "STRONGLY BULLISH"

    if (
        score >= 55
        and (
            "IMPROVING" in direction
            or "BULLISH" in regime
            or "RISK ON" in risk_environment
        )
    ):
        return "BULLISH"

    if (
        score <= 35
        and "DETERIORATING" in direction
        and "BEARISH" in regime
    ):
        return "STRONGLY BEARISH"

    if (
        score <= 45
        and (
            "DETERIORATING" in direction
            or "BEARISH" in regime
            or "RISK OFF" in risk_environment
        )
    ):
        return "BEARISH"

    if (
        score < 50
        and "IMPROVING" in direction
    ):
        return "BEARISH WITH RECOVERY"

    if (
        score > 50
        and "DETERIORATING" in direction
    ):
        return "BULLISH WITH DETERIORATION"

    if (
        score >= 50
        and "IMPROVING" in direction
    ):
        return "CONSTRUCTIVE RECOVERY"

    return "NEUTRAL TO MIXED"


# ==========================================================
# BREADTH QUALITY
# ==========================================================

def determine_breadth_quality(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
) -> str:
    """
    Determine breadth-quality classification.
    """

    score = current.breadth_score
    confidence = current.confidence
    participation = current.participation_quality.upper()
    direction = change.breadth_direction.upper()
    sector_rotation = change.sector_rotation.upper()

    quality_score = 0

    if score >= 65:
        quality_score += 3

    elif score >= 55:
        quality_score += 2

    elif score >= 45:
        quality_score += 1

    if confidence >= 80:
        quality_score += 2

    elif confidence >= 65:
        quality_score += 1

    if contains_any(
        participation,
        (
            "BROAD BASED",
            "BROAD-BASED",
        ),
    ):
        quality_score += 2

    if "IMPROVING" in direction:
        quality_score += 2

    elif "DETERIORATING" in direction:
        quality_score -= 2

    if "POSITIVE" in sector_rotation:
        quality_score += 1

    elif "NEGATIVE" in sector_rotation:
        quality_score -= 1

    if quality_score >= 8:
        return "VERY HIGH"

    if quality_score >= 6:
        return "HIGH"

    if quality_score >= 3:
        return "MODERATE"

    if quality_score >= 1:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# DECISION CONFIDENCE
# ==========================================================

def calculate_decision_confidence(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    breadth_bias: str,
) -> int:
    """
    Calculate consolidated breadth-decision confidence.

    Weighting
    ---------
    Current breadth confidence : 55%
    Change confidence          : 35%
    Reversal-risk adjustment   : 10%
    """

    confidence = (
        current.confidence * 0.55
        + change.change_confidence * 0.35
        + (
            100
            - change.reversal_risk_score
        ) * 0.10
    )

    direction = change.breadth_direction.upper()
    regime = current.breadth_regime.upper()

    if (
        "BULLISH" in breadth_bias
        and "IMPROVING" in direction
        and "BULLISH" in regime
    ):
        confidence += 5

    if (
        "BEARISH" in breadth_bias
        and "DETERIORATING" in direction
        and "BEARISH" in regime
    ):
        confidence += 5

    if (
        "MIXED" in breadth_bias
        or "MIXED" in current.breadth_trend.upper()
    ):
        confidence -= 5

    # Corrected:
    # MarketBreadthChangeResult contains status, not change_status.
    if change.status == "INSUFFICIENT HISTORY":
        confidence -= 10

    if change.weekly_breadth_score_change is None:
        confidence -= 4

    if change.reversal_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        confidence -= 6

    return clamp_score(
        confidence
    )


# ==========================================================
# DECISION QUALITY
# ==========================================================

def determine_decision_quality(
    *,
    confidence: int,
    breadth_quality: str,
    reversal_risk_level: str,
) -> str:
    """
    Convert confidence and risk into a quality grade.
    """

    if (
        confidence >= 78
        and breadth_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and reversal_risk_level not in {
            "HIGH",
            "VERY HIGH",
        }
    ):
        return "A"

    if (
        confidence >= 68
        and breadth_quality in {
            "HIGH",
            "MODERATE",
        }
        and reversal_risk_level != "VERY HIGH"
    ):
        return "B"

    if (
        confidence >= 52
        and breadth_quality in {
            "MODERATE",
            "LOW TO MODERATE",
        }
    ):
        return "C"

    return "D"


# ==========================================================
# MARKET ENVIRONMENT
# ==========================================================

def determine_market_environment(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
) -> str:
    """
    Build the consolidated breadth environment.
    """

    return (
        f"{current.breadth_regime} | "
        f"{change.breadth_direction} | "
        f"{change.sector_rotation} | "
        f"{current.risk_environment}"
    )


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    breadth_bias: str,
) -> str:
    """
    Determine expected market behaviour from breadth.
    """

    if (
        breadth_bias in {
            "STRONGLY BULLISH",
            "BULLISH",
            "CONSTRUCTIVE RECOVERY",
        }
        and "POSITIVE" in change.sector_rotation.upper()
    ):
        return (
            "MARKET PARTICIPATION MAY CONTINUE TO BROADEN, WITH "
            "MORE SECTORS AND STOCKS SUPPORTING POSITIVE PRICE ACTION"
        )

    if breadth_bias == "BEARISH WITH RECOVERY":
        return (
            "RECOVERY MAY CONTINUE AS PARTICIPATION IMPROVES, BUT "
            "THE BROADER MARKET STRUCTURE HAS NOT YET TURNED BULLISH"
        )

    if breadth_bias == "BULLISH WITH DETERIORATION":
        return (
            "THE BROADER STRUCTURE REMAINS POSITIVE, BUT WEAKENING "
            "PARTICIPATION INCREASES PULLBACK AND REVERSAL RISK"
        )

    if breadth_bias in {
        "STRONGLY BEARISH",
        "BEARISH",
    }:
        return (
            "MARKET WEAKNESS MAY REMAIN BROAD, WITH RECOVERIES "
            "VULNERABLE UNTIL ADVANCE RATES AND SECTOR PARTICIPATION IMPROVE"
        )

    if "IMPROVING" in change.breadth_direction.upper():
        return (
            "MARKET PARTICIPATION IS IMPROVING, BUT ADDITIONAL "
            "SESSIONS ARE REQUIRED TO CONFIRM A SUSTAINABLE REGIME CHANGE"
        )

    return (
        "MARKET INTERNALS REMAIN MIXED, SUPPORTING ROTATIONAL, "
        "RANGE-BOUND OR SECTOR-SPECIFIC BEHAVIOUR"
    )


# ==========================================================
# ANALYTICAL POSTURE
# ==========================================================

def determine_analytical_posture(
    *,
    decision_quality: str,
    decision_confidence: int,
    reversal_risk_level: str,
    weekly_change_available: bool,
) -> str:
    """
    Determine how much weight breadth should receive.
    """

    if reversal_risk_level == "VERY HIGH":
        return (
            "USE BREADTH AS A WARNING SIGNAL. REQUIRE STRONG "
            "CONFIRMATION FROM PRICE, STRUCTURE, OPTIONS AND PARTICIPANT DATA."
        )

    if not weekly_change_available:
        return (
            "USE CURRENT AND DAILY BREADTH WITH MODERATE WEIGHT. "
            "WEEKLY CONFIRMATION IS NOT YET AVAILABLE."
        )

    if (
        decision_quality in {
            "A",
            "B",
        }
        and decision_confidence >= 68
    ):
        return (
            "MARKET BREADTH CAN RECEIVE NORMAL TO HIGH WEIGHT IN "
            "THE AQSD MASTER DECISION ENGINE."
        )

    if decision_quality == "C":
        return (
            "USE MARKET BREADTH WITH NORMAL CROSS-CHECKS FROM "
            "PRICE STRUCTURE, OPTIONS AND PARTICIPANT INTELLIGENCE."
        )

    return (
        "MARKET BREADTH SHOULD RECEIVE LOW WEIGHT UNTIL "
        "PARTICIPATION, CONFIDENCE AND ALIGNMENT IMPROVE."
    )


# ==========================================================
# MASTER CONCLUSION
# ==========================================================

def determine_master_conclusion(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    breadth_bias: str,
) -> str:
    """
    Create one final breadth conclusion.
    """

    if (
        breadth_bias in {
            "BEARISH WITH RECOVERY",
            "CONSTRUCTIVE RECOVERY",
        }
        and "IMPROVING" in change.breadth_direction.upper()
    ):
        return (
            "MARKET BREADTH IS RECOVERING SHARPLY FROM A WEAK BASE. "
            "SECTOR PARTICIPATION IS IMPROVING, BUT THE RECOVERY IS "
            "NOT YET A FULLY CONFIRMED BROAD-MARKET BULLISH REGIME."
        )

    if (
        breadth_bias in {
            "STRONGLY BULLISH",
            "BULLISH",
        }
        and "POSITIVE" in change.sector_rotation.upper()
    ):
        return (
            "MARKET INTERNALS ARE POSITIVE AND SECTOR PARTICIPATION "
            "IS BROADENING. BREADTH SUPPORTS A CONSTRUCTIVE MARKET "
            "ENVIRONMENT WHILE CONFIRMATION CONDITIONS REMAIN INTACT."
        )

    if breadth_bias == "BULLISH WITH DETERIORATION":
        return (
            "THE BROADER MARKET STRUCTURE REMAINS POSITIVE, BUT "
            "PARTICIPATION IS WEAKENING. THE MARKET IS VULNERABLE "
            "TO A NARROW ADVANCE OR SHARP PULLBACK."
        )

    if breadth_bias in {
        "STRONGLY BEARISH",
        "BEARISH",
    }:
        return (
            "MARKET INTERNALS REMAIN WEAK AND PARTICIPATION IS "
            "BEARISH. RECOVERIES SHOULD BE TREATED AS UNCONFIRMED "
            "UNTIL BREADTH AND SECTOR LEADERSHIP IMPROVE."
        )

    return (
        f"MARKET BREADTH IS {breadth_bias}. THE CURRENT REGIME IS "
        f"{current.breadth_regime}, WHILE THE DAILY BREADTH "
        f"DIRECTION IS {change.breadth_direction}. THE VIEW REMAINS "
        f"CONDITIONAL ON FURTHER PARTICIPATION CONFIRMATION."
    )


# ==========================================================
# CONFIRMATION CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    breadth_bias: str,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
) -> tuple[str, ...]:
    """
    Build breadth confirmation conditions.
    """

    conditions: list[str] = []

    if contains_any(
        breadth_bias,
        (
            "BULLISH",
            "RECOVERY",
            "CONSTRUCTIVE",
        ),
    ):
        conditions.extend(
            [
                (
                    "The breadth score should remain stable or improve "
                    "over the next trading sessions."
                ),
                (
                    "Advance participation should remain above the "
                    "previous session."
                ),
                (
                    "EMA20 and EMA50 participation should continue "
                    "to improve."
                ),
                (
                    "Positive sector rotation should remain broader "
                    "than negative sector rotation."
                ),
                (
                    "The risk environment should not return sharply "
                    "to broad risk-off conditions."
                ),
            ]
        )

    elif "BEARISH" in breadth_bias:
        conditions.extend(
            [
                (
                    "Declining participation should remain dominant."
                ),
                (
                    "EMA20 and EMA50 participation should remain weak "
                    "or deteriorate further."
                ),
                (
                    "Negative sector rotation should remain broader "
                    "than positive sector rotation."
                ),
                (
                    "Risk-off conditions should remain active."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "Breadth score should break decisively above 55 "
                    "or below 45 to establish directional control."
                ),
                (
                    "Sector participation should develop a clear "
                    "positive or negative rotation."
                ),
                (
                    "Breadth momentum and breadth trend should become aligned."
                ),
            ]
        )

    if change.weekly_breadth_score_change is None:
        conditions.append(
            "A five-session weekly breadth comparison should confirm "
            "the current daily direction."
        )

    if current.divergence_risk.upper().startswith("HIGH"):
        conditions.append(
            "The divergence between short-term and long-term breadth "
            "should reduce."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# INVALIDATION CONDITIONS
# ==========================================================

def build_invalidation_conditions(
    *,
    breadth_bias: str,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
) -> tuple[str, ...]:
    """
    Build breadth invalidation conditions.
    """

    conditions: list[str] = []

    if contains_any(
        breadth_bias,
        (
            "BULLISH",
            "RECOVERY",
            "CONSTRUCTIVE",
        ),
    ):
        conditions.extend(
            [
                (
                    "The breadth score falls materially below the "
                    "current level."
                ),
                (
                    "The daily breadth direction changes to strongly "
                    "deteriorating."
                ),
                (
                    "Positive sector rotation changes to broad negative "
                    "sector rotation."
                ),
                (
                    "Advance participation falls sharply while declines "
                    "again become dominant."
                ),
                (
                    "The risk environment returns to broad risk-off."
                ),
            ]
        )

    elif "BEARISH" in breadth_bias:
        conditions.extend(
            [
                (
                    "The breadth score rises materially above the "
                    "current bearish range."
                ),
                (
                    "Daily breadth changes to strongly improving."
                ),
                (
                    "Broad positive sector rotation develops."
                ),
                (
                    "EMA20 and EMA50 participation improve sharply."
                ),
                (
                    "The risk environment changes to risk-on."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "A decisive breadth expansion invalidates the "
                    "neutral or mixed classification."
                ),
                (
                    "A decisive breadth contraction invalidates the "
                    "neutral or mixed classification."
                ),
            ]
        )

    if change.reversal_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        conditions.append(
            "A confirmed reversal in the direction identified by the "
            "reversal-risk engine invalidates the present view."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    decision_confidence: int,
) -> tuple[str, ...]:
    """
    Combine and deduplicate market-breadth warnings.
    """

    warnings: list[str] = []

    warnings.extend(
        current.warnings
    )

    warnings.extend(
        change.warnings
    )

    if change.weekly_breadth_score_change is None:
        warnings.append(
            "Weekly breadth confirmation is not yet available."
        )

    if decision_confidence < 55:
        warnings.append(
            "Breadth decision confidence is below 55%."
        )

    if change.reversal_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        warnings.append(
            f"Breadth reversal risk is "
            f"{change.reversal_risk_level.lower()}."
        )

    if (
        "BULLISH" in current.breadth_regime.upper()
        and "DETERIORATING" in change.breadth_direction.upper()
    ):
        warnings.append(
            "The current bullish breadth regime conflicts with "
            "deteriorating daily breadth."
        )

    if (
        "BEARISH" in current.breadth_regime.upper()
        and "IMPROVING" in change.breadth_direction.upper()
    ):
        warnings.append(
            "The current bearish breadth regime conflicts with "
            "improving daily breadth."
        )

    if not warnings:
        warnings.append(
            "No major consolidated market-breadth warning is active."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# SUMMARY AND EXPLANATION
# ==========================================================

def build_concise_summary(
    *,
    breadth_bias: str,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    decision_confidence: int,
    decision_quality: str,
) -> str:
    """
    Build a dashboard-ready breadth summary.
    """

    return (
        f"{breadth_bias} BREADTH | "
        f"SCORE {current.breadth_score}% | "
        f"{change.breadth_direction} | "
        f"{change.sector_rotation} | "
        f"{current.risk_environment} | "
        f"{change.reversal_risk_level} REVERSAL RISK | "
        f"{decision_confidence}% CONFIDENCE | "
        f"QUALITY {decision_quality}"
    )


def build_explanation(
    *,
    current: MarketBreadthResult,
    change: MarketBreadthChangeResult,
    breadth_bias: str,
    breadth_quality: str,
    decision_confidence: int,
    decision_quality: str,
    master_conclusion: str,
) -> str:
    """
    Build the final explanation.
    """

    return (
        f"The current market breadth score is "
        f"{current.breadth_score}%, with "
        f"{current.advance_percentage:.2f}% of stocks advancing, "
        f"{current.above_ema20_percentage:.2f}% above EMA20, "
        f"{current.above_ema50_percentage:.2f}% above EMA50 and "
        f"{current.above_ema200_percentage:.2f}% above EMA200. "
        f"The breadth regime is "
        f"{current.breadth_regime.lower()}, the risk environment is "
        f"{current.risk_environment.lower()} and internal market "
        f"health is {current.internal_market_health.lower()}. "
        f"The daily breadth score changed by "
        f"{format_optional_change(change.daily_breadth_score_change)} "
        f"points and the weekly breadth score changed by "
        f"{format_optional_change(change.weekly_breadth_score_change)} "
        f"points. Breadth direction is "
        f"{change.breadth_direction.lower()}, with "
        f"{change.sector_rotation.lower()}. "
        f"{len(change.improving_sectors)} sectors are improving and "
        f"{len(change.deteriorating_sectors)} sectors are "
        f"deteriorating. Reversal risk is "
        f"{change.reversal_risk_level.lower()} at "
        f"{change.reversal_risk_score}%. The consolidated breadth "
        f"bias is {breadth_bias.lower()}, breadth quality is "
        f"{breadth_quality.lower()}, decision confidence is "
        f"{decision_confidence}% and decision quality is grade "
        f"{decision_quality}. Final conclusion: {master_conclusion}"
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_market_breadth_decision_engine(
    *,
    requested_date: date,
    source_file: Path = DEFAULT_INPUT_FILE,
    weekly_lookback_sessions: int = 5,
    export_breadth: bool = False,
) -> MarketBreadthDecisionResult:
    """
    Run the complete Market Breadth Decision Engine.
    """

    current_result = run_market_breadth_engine(
        requested_date=requested_date,
        source_file=source_file,
        export=export_breadth,
    )

    change_result = run_market_breadth_change_engine(
        requested_date=requested_date,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
        export=True,
    )

    breadth_bias = determine_breadth_bias(
        current=current_result,
        change=change_result,
    )

    breadth_quality = determine_breadth_quality(
        current=current_result,
        change=change_result,
    )

    decision_confidence = calculate_decision_confidence(
        current=current_result,
        change=change_result,
        breadth_bias=breadth_bias,
    )

    decision_quality = determine_decision_quality(
        confidence=decision_confidence,
        breadth_quality=breadth_quality,
        reversal_risk_level=(
            change_result.reversal_risk_level
        ),
    )

    market_environment = determine_market_environment(
        current=current_result,
        change=change_result,
    )

    expected_behaviour = determine_expected_behaviour(
        current=current_result,
        change=change_result,
        breadth_bias=breadth_bias,
    )

    analytical_posture = determine_analytical_posture(
        decision_quality=decision_quality,
        decision_confidence=decision_confidence,
        reversal_risk_level=(
            change_result.reversal_risk_level
        ),
        weekly_change_available=(
            change_result.weekly_breadth_score_change
            is not None
        ),
    )

    master_conclusion = determine_master_conclusion(
        current=current_result,
        change=change_result,
        breadth_bias=breadth_bias,
    )

    confirmation_conditions = build_confirmation_conditions(
        breadth_bias=breadth_bias,
        current=current_result,
        change=change_result,
    )

    invalidation_conditions = build_invalidation_conditions(
        breadth_bias=breadth_bias,
        current=current_result,
        change=change_result,
    )

    warnings = build_warnings(
        current=current_result,
        change=change_result,
        decision_confidence=decision_confidence,
    )

    concise_summary = build_concise_summary(
        breadth_bias=breadth_bias,
        current=current_result,
        change=change_result,
        decision_confidence=decision_confidence,
        decision_quality=decision_quality,
    )

    explanation = build_explanation(
        current=current_result,
        change=change_result,
        breadth_bias=breadth_bias,
        breadth_quality=breadth_quality,
        decision_confidence=decision_confidence,
        decision_quality=decision_quality,
        master_conclusion=master_conclusion,
    )

    if current_result.status != "SUCCESS":
        overall_status = "FAILED"

    elif change_result.status == "FAILED":
        overall_status = "FAILED"

    elif change_result.status == "INSUFFICIENT HISTORY":
        overall_status = "PARTIAL SUCCESS"

    else:
        overall_status = "SUCCESS"

    return MarketBreadthDecisionResult(
        requested_date=requested_date,
        analysis_date=current_result.analysis_date,
        source_file=source_file,

        breadth_score=current_result.breadth_score,
        breadth_bias=breadth_bias,
        breadth_quality=breadth_quality,

        breadth_momentum=current_result.breadth_momentum,
        breadth_trend=current_result.breadth_trend,
        breadth_strength=current_result.breadth_strength,
        breadth_regime=current_result.breadth_regime,

        breadth_direction=change_result.breadth_direction,
        breadth_velocity=change_result.breadth_velocity,
        breadth_acceleration=(
            change_result.breadth_acceleration
        ),

        risk_environment=current_result.risk_environment,
        internal_market_health=(
            current_result.internal_market_health
        ),
        participation_quality=(
            current_result.participation_quality
        ),
        divergence_risk=current_result.divergence_risk,

        sector_rotation=change_result.sector_rotation,
        sector_rotation_strength=(
            change_result.sector_rotation_strength
        ),
        improving_sectors=len(
            change_result.improving_sectors
        ),
        deteriorating_sectors=len(
            change_result.deteriorating_sectors
        ),

        daily_breadth_change=(
            change_result.daily_breadth_score_change
        ),
        weekly_breadth_score_change=(
            change_result.weekly_breadth_score_change
        ),

        reversal_risk_score=(
            change_result.reversal_risk_score
        ),
        reversal_risk_level=(
            change_result.reversal_risk_level
        ),
        reversal_direction=(
            change_result.reversal_direction
        ),

        expected_behaviour=expected_behaviour,
        market_environment=market_environment,
        analytical_posture=analytical_posture,

        current_confidence=current_result.confidence,
        change_confidence=change_result.change_confidence,
        decision_confidence=decision_confidence,
        decision_quality=decision_quality,

        master_conclusion=master_conclusion,
        concise_summary=concise_summary,
        explanation=explanation,

        confirmation_conditions=(
            confirmation_conditions
        ),
        invalidation_conditions=(
            invalidation_conditions
        ),
        warnings=warnings,

        current_status=current_result.status,

        # Corrected:
        # Use change_result.status.
        change_status=change_result.status,

        status=overall_status,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketBreadthDecisionResult,
) -> None:
    """
    Display the complete MBI-005 result.
    """

    print()
    print("=" * 108)
    print("AQSD MARKET BREADTH DECISION ENGINE")
    print("=" * 108)
    print(f"Module                              : {MODULE_ID}")
    print(f"Version                             : {MODULE_VERSION}")
    print(f"Requested Date                      : {result.requested_date}")
    print(f"Analysis Date                       : {result.analysis_date}")
    print(f"Source File                         : {result.source_file}")
    print("-" * 108)

    print("CURRENT BREADTH")
    print("-" * 108)
    print(
        f"Breadth Score                       : "
        f"{result.breadth_score}%"
    )
    print(
        f"Breadth Bias                        : "
        f"{result.breadth_bias}"
    )
    print(
        f"Breadth Quality                     : "
        f"{result.breadth_quality}"
    )
    print(
        f"Breadth Momentum                    : "
        f"{result.breadth_momentum}"
    )
    print(
        f"Breadth Trend                       : "
        f"{result.breadth_trend}"
    )
    print(
        f"Breadth Strength                    : "
        f"{result.breadth_strength}"
    )
    print(
        f"Breadth Regime                      : "
        f"{result.breadth_regime}"
    )
    print("-" * 108)

    print("BREADTH CHANGE")
    print("-" * 108)
    print(
        f"Daily Breadth Change                : "
        f"{format_optional_change(result.daily_breadth_change)}"
    )
    print(
        f"Weekly Breadth Change               : "
        f"{format_optional_change(result.weekly_breadth_score_change)}"
    )
    print(
        f"Breadth Direction                   : "
        f"{result.breadth_direction}"
    )
    print(
        f"Breadth Velocity                    : "
        f"{result.breadth_velocity}"
    )
    print(
        f"Breadth Acceleration                : "
        f"{result.breadth_acceleration}"
    )
    print("-" * 108)

    print("PARTICIPATION AND ROTATION")
    print("-" * 108)
    print(
        f"Participation Quality               : "
        f"{result.participation_quality}"
    )
    print(
        f"Sector Rotation                     : "
        f"{result.sector_rotation}"
    )
    print(
        f"Sector Rotation Strength            : "
        f"{result.sector_rotation_strength}"
    )
    print(
        f"Improving Sectors                   : "
        f"{result.improving_sectors}"
    )
    print(
        f"Deteriorating Sectors               : "
        f"{result.deteriorating_sectors}"
    )
    print("-" * 108)

    print("MARKET INTERNAL RISK")
    print("-" * 108)
    print(
        f"Risk Environment                    : "
        f"{result.risk_environment}"
    )
    print(
        f"Internal Market Health              : "
        f"{result.internal_market_health}"
    )
    print(
        f"Divergence Risk                     : "
        f"{result.divergence_risk}"
    )
    print(
        f"Reversal Risk Score                 : "
        f"{result.reversal_risk_score}%"
    )
    print(
        f"Reversal Risk Level                 : "
        f"{result.reversal_risk_level}"
    )
    print(
        f"Reversal Direction                  : "
        f"{result.reversal_direction}"
    )
    print("-" * 108)

    print("DECISION")
    print("-" * 108)
    print(
        f"Market Environment                  : "
        f"{result.market_environment}"
    )
    print(
        f"Expected Behaviour                  : "
        f"{result.expected_behaviour}"
    )
    print(
        f"Analytical Posture                  : "
        f"{result.analytical_posture}"
    )
    print(
        f"Current Breadth Confidence          : "
        f"{result.current_confidence}%"
    )
    print(
        f"Change Confidence                   : "
        f"{result.change_confidence}%"
    )
    print(
        f"Decision Confidence                 : "
        f"{result.decision_confidence}%"
    )
    print(
        f"Decision Quality                    : "
        f"{result.decision_quality}"
    )
    print("-" * 108)

    print("MASTER CONCLUSION")
    print("-" * 108)
    print(result.master_conclusion)
    print("-" * 108)

    print("CONCISE SUMMARY")
    print("-" * 108)
    print(result.concise_summary)
    print("-" * 108)

    print("CONFIRMATION CONDITIONS")
    print("-" * 108)

    for number, condition in enumerate(
        result.confirmation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 108)
    print("INVALIDATION CONDITIONS")
    print("-" * 108)

    for number, condition in enumerate(
        result.invalidation_conditions,
        start=1,
    ):
        print(f"{number}. {condition}")

    print("-" * 108)
    print("WARNINGS")
    print("-" * 108)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(f"{number}. {warning}")

    print("-" * 108)
    print("EXPLANATION")
    print("-" * 108)
    print(result.explanation)
    print("-" * 108)
    print(
        "Method                              : "
        "RULE-BASED MARKET BREADTH DECISION"
    )
    print(
        f"Current Engine Status               : "
        f"{result.current_status}"
    )
    print(
        f"Change Engine Status                : "
        f"{result.change_status}"
    )
    print(
        f"Overall Status                      : "
        f"{result.status}"
    )
    print("=" * 108)


# ==========================================================
# COMMAND LINE
# ==========================================================

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


def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the AQSD Market Breadth Decision Engine."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested analysis date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=(
            "Path to the market breadth snapshot. "
            f"Default: {DEFAULT_INPUT_FILE}"
        ),
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=5,
        help=(
            "Number of saved sessions used for weekly breadth change. "
            "Default: 5."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    if arguments.weekly_sessions < 1:
        print()
        print("Status : FAILED")
        print("Reason : --weekly-sessions must be at least 1.")
        raise SystemExit(1)

    try:
        result = run_market_breadth_decision_engine(
            requested_date=parse_date(
                arguments.date
            ),
            source_file=(
                arguments.input
                .expanduser()
                .resolve()
            ),
            weekly_lookback_sessions=(
                arguments.weekly_sessions
            ),
        )

    except Exception as exc:
        print()
        print("=" * 108)
        print("AQSD MARKET BREADTH DECISION ENGINE")
        print("=" * 108)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 108)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()