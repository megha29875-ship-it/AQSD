"""
AQSD
Sector Rotation Decision Engine

Module : MBI-008
Version: 1.0.0
Author : AQSD

Description
-----------
Combines:

1. Sector Strength Engine
2. Sector Rotation Engine

into one consolidated, explainable sector-intelligence conclusion.

The engine produces:

- Sector Market Bias
- Sector Participation Quality
- Leadership Quality
- Rotation Quality
- Rotation Direction
- Rotation Breadth
- Rotation Speed
- Leadership Stability
- Dominant Sector Cycle
- Strongest Sector
- Weakest Sector
- New Leaders
- Persistent Leaders
- Emerging Sectors
- Losing Leadership
- Sector Risk
- Expected Behaviour
- Decision Confidence
- Decision Quality
- Master Conclusion
- Confirmation Conditions
- Invalidation Conditions
- Warnings
- Explanation

Important
---------
This module provides analytical decision support only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_intelligence.sector_rotation_engine import (
    DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
    SectorRotationEngineResult,
    run_sector_rotation_engine,
)
from Scripts.aqsd_intelligence.sector_strength_engine import (
    DEFAULT_INPUT_FILE,
    SectorStrengthEngineResult,
    run_sector_strength_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MBI-008"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class SectorRotationDecisionResult:
    """
    Final consolidated sector-intelligence decision result.
    """

    requested_date: date
    analysis_date: date
    source_file: Path

    sectors_analysed: int
    bullish_sectors: int
    bearish_sectors: int
    neutral_sectors: int

    strongest_sector: str | None
    weakest_sector: str | None

    sector_market_bias: str
    sector_participation_quality: str
    leadership_quality: str
    rotation_quality: str

    broad_rotation: str
    market_sector_health: str

    rotation_direction: str
    rotation_breadth: str
    rotation_speed: str
    leadership_stability: str
    dominant_sector_cycle: str

    new_leaders: tuple[str, ...]
    persistent_leaders: tuple[str, ...]
    emerging_sectors: tuple[str, ...]
    losing_leadership: tuple[str, ...]
    new_laggards: tuple[str, ...]
    persistent_laggards: tuple[str, ...]

    improving_sectors: int
    deteriorating_sectors: int
    stable_sectors: int

    rotation_risk_score: int
    rotation_risk_level: str
    sector_risk_level: str

    expected_behaviour: str
    analytical_posture: str
    market_environment: str

    strength_confidence: int
    rotation_confidence: int
    decision_confidence: int
    decision_quality: str

    master_conclusion: str
    concise_summary: str
    explanation: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    strength_status: str
    rotation_status: str
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
    Return True when the text contains any supplied keyword.
    """

    normalized = value.upper()

    return any(
        keyword.upper() in normalized
        for keyword in keywords
    )


def sector_names(
    records: tuple,
) -> tuple[str, ...]:
    """
    Extract sector names from rotation records.
    """

    return tuple(
        record.sector
        for record in records
    )


def join_sector_names(
    names: tuple[str, ...],
) -> str:
    """
    Format sector names for display.
    """

    if not names:
        return "NONE"

    return ", ".join(names)


# ==========================================================
# SECTOR MARKET BIAS
# ==========================================================

def determine_sector_market_bias(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Determine the consolidated sector-market bias.
    """

    bullish = strength.bullish_sectors
    bearish = strength.bearish_sectors
    total = strength.sectors_analysed

    rotation_direction = (
        rotation.rotation_direction.upper()
    )

    sector_health = (
        strength.market_sector_health.upper()
    )

    if total == 0:
        return "UNKNOWN"

    bullish_percentage = (
        bullish
        / total
        * 100
    )

    bearish_percentage = (
        bearish
        / total
        * 100
    )

    if (
        bullish_percentage >= 65
        and "BROAD POSITIVE" in rotation_direction
        and contains_any(
            sector_health,
            (
                "HEALTHY",
                "VERY HEALTHY",
            ),
        )
    ):
        return "STRONGLY BULLISH"

    if (
        bullish_percentage >= 50
        and contains_any(
            rotation_direction,
            (
                "POSITIVE",
                "MIXED",
            ),
        )
    ):
        return "BULLISH"

    if (
        bearish_percentage >= 65
        and "BROAD NEGATIVE" in rotation_direction
        and contains_any(
            sector_health,
            (
                "WEAK",
                "VERY WEAK",
            ),
        )
    ):
        return "STRONGLY BEARISH"

    if (
        bearish_percentage >= 50
        and contains_any(
            rotation_direction,
            (
                "NEGATIVE",
                "MIXED",
            ),
        )
    ):
        return "BEARISH"

    if (
        "POSITIVE" in rotation_direction
        and bullish_percentage < 50
    ):
        return "CONSTRUCTIVE ROTATION"

    if (
        "NEGATIVE" in rotation_direction
        and bearish_percentage < 50
    ):
        return "DETERIORATING ROTATION"

    return "NEUTRAL TO MIXED"


# ==========================================================
# PARTICIPATION QUALITY
# ==========================================================

def determine_participation_quality(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Determine sector-participation quality.
    """

    score = 0

    if strength.sectors_analysed >= 10:
        score += 2

    if strength.bullish_sectors >= 6:
        score += 3

    elif strength.bullish_sectors >= 4:
        score += 2

    elif strength.bullish_sectors >= 2:
        score += 1

    if strength.bearish_sectors <= 2:
        score += 2

    elif strength.bearish_sectors >= 6:
        score -= 2

    if "BROAD POSITIVE" in rotation.rotation_direction.upper():
        score += 3

    elif "SELECTIVE POSITIVE" in rotation.rotation_direction.upper():
        score += 2

    elif "BROAD NEGATIVE" in rotation.rotation_direction.upper():
        score -= 3

    elif "SELECTIVE NEGATIVE" in rotation.rotation_direction.upper():
        score -= 2

    if rotation.rotation_breadth == "VERY BROAD":
        score += 2

    elif rotation.rotation_breadth == "BROAD":
        score += 1

    if score >= 9:
        return "VERY HIGH"

    if score >= 6:
        return "HIGH"

    if score >= 3:
        return "MODERATE"

    if score >= 1:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# LEADERSHIP QUALITY
# ==========================================================

def determine_leadership_quality(
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Determine sector-leadership quality.
    """

    persistent = len(
        rotation.persistent_leaders
    )

    new = len(
        rotation.new_leaders
    )

    emerging = len(
        rotation.emerging_sectors
    )

    losing = len(
        rotation.losing_leadership
    )

    stability = (
        rotation.leadership_stability.upper()
    )

    score = 0

    score += persistent * 3
    score += new * 2
    score += min(
        emerging,
        4,
    )

    score -= losing * 3

    if stability == "VERY STABLE":
        score += 4

    elif stability == "STABLE":
        score += 3

    elif stability == "LEADERSHIP TRANSITION":
        score -= 1

    elif stability == "MIXED":
        score -= 2

    if score >= 10:
        return "VERY HIGH"

    if score >= 7:
        return "HIGH"

    if score >= 4:
        return "MODERATE"

    if score >= 1:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# ROTATION QUALITY
# ==========================================================

def determine_rotation_quality(
    *,
    rotation: SectorRotationEngineResult,
    participation_quality: str,
    leadership_quality: str,
) -> str:
    """
    Determine consolidated rotation quality.
    """

    score = 0

    if "BROAD POSITIVE" in rotation.rotation_direction.upper():
        score += 4

    elif "SELECTIVE POSITIVE" in rotation.rotation_direction.upper():
        score += 2

    elif "BROAD NEGATIVE" in rotation.rotation_direction.upper():
        score -= 4

    elif "SELECTIVE NEGATIVE" in rotation.rotation_direction.upper():
        score -= 2

    if rotation.rotation_breadth == "VERY BROAD":
        score += 3

    elif rotation.rotation_breadth == "BROAD":
        score += 2

    elif rotation.rotation_breadth == "MODERATE":
        score += 1

    if rotation.rotation_speed == "SLOW":
        score += 2

    elif rotation.rotation_speed == "MODERATE":
        score += 1

    elif rotation.rotation_speed == "VERY FAST":
        score -= 2

    if participation_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        score += 2

    if leadership_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        score += 2

    if rotation.rotation_risk_level == "VERY HIGH":
        score -= 4

    elif rotation.rotation_risk_level == "HIGH":
        score -= 3

    elif rotation.rotation_risk_level == "MODERATE":
        score -= 1

    if score >= 10:
        return "VERY HIGH"

    if score >= 7:
        return "HIGH"

    if score >= 4:
        return "MODERATE"

    if score >= 1:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# SECTOR RISK
# ==========================================================

def determine_sector_risk_level(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
    leadership_quality: str,
) -> str:
    """
    Determine the consolidated sector risk level.
    """

    risk_score = rotation.rotation_risk_score

    if strength.market_sector_health in {
        "VERY WEAK",
        "WEAK",
    }:
        risk_score += 15

    if strength.bearish_sectors > strength.bullish_sectors:
        risk_score += 10

    if leadership_quality == "LOW":
        risk_score += 15

    elif leadership_quality == "LOW TO MODERATE":
        risk_score += 8

    if rotation.rotation_speed == "VERY FAST":
        risk_score += 15

    elif rotation.rotation_speed == "FAST":
        risk_score += 8

    risk_score = clamp_score(
        risk_score
    )

    if risk_score >= 80:
        return "VERY HIGH"

    if risk_score >= 65:
        return "HIGH"

    if risk_score >= 45:
        return "MODERATE"

    if risk_score >= 25:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# DECISION CONFIDENCE
# ==========================================================

def calculate_decision_confidence(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
    participation_quality: str,
    leadership_quality: str,
    rotation_quality: str,
) -> int:
    """
    Calculate the final sector-decision confidence.
    """

    confidence = (
        strength.confidence * 0.50
        + rotation.confidence * 0.35
        + (
            100
            - rotation.rotation_risk_score
        ) * 0.15
    )

    if participation_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        confidence += 4

    if leadership_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        confidence += 4

    if rotation_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        confidence += 4

    if rotation.status == "INSUFFICIENT HISTORY":
        confidence -= 12

    if rotation.weekly_reference_date is None:
        confidence -= 5

    if rotation.rotation_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        confidence -= 7

    return clamp_score(
        confidence
    )


# ==========================================================
# DECISION QUALITY
# ==========================================================

def determine_decision_quality(
    *,
    confidence: int,
    participation_quality: str,
    leadership_quality: str,
    rotation_quality: str,
    sector_risk_level: str,
) -> str:
    """
    Convert the decision into an AQSD quality grade.
    """

    if (
        confidence >= 80
        and participation_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and leadership_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and rotation_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and sector_risk_level not in {
            "HIGH",
            "VERY HIGH",
        }
    ):
        return "A"

    if (
        confidence >= 68
        and participation_quality in {
            "HIGH",
            "MODERATE",
        }
        and rotation_quality in {
            "HIGH",
            "MODERATE",
        }
        and sector_risk_level != "VERY HIGH"
    ):
        return "B"

    if confidence >= 52:
        return "C"

    return "D"


# ==========================================================
# EXPECTED BEHAVIOUR
# ==========================================================

def determine_expected_behaviour(
    *,
    sector_market_bias: str,
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Determine expected sector-driven market behaviour.
    """

    if sector_market_bias in {
        "STRONGLY BULLISH",
        "BULLISH",
    }:
        return (
            "BROAD OR PERSISTENT SECTOR LEADERSHIP MAY SUPPORT "
            "A CONSTRUCTIVE MARKET ENVIRONMENT"
        )

    if sector_market_bias == "CONSTRUCTIVE ROTATION":
        return (
            "SELECTIVE SECTOR LEADERSHIP MAY SUPPORT ROTATIONAL "
            "STRENGTH, EVEN IF THE ENTIRE MARKET IS NOT YET BULLISH"
        )

    if sector_market_bias in {
        "STRONGLY BEARISH",
        "BEARISH",
    }:
        return (
            "BROAD SECTOR WEAKNESS MAY SUPPORT A DEFENSIVE OR "
            "RISK-OFF MARKET ENVIRONMENT"
        )

    if sector_market_bias == "DETERIORATING ROTATION":
        return (
            "SECTOR LEADERSHIP MAY NARROW AS WEAKNESS EXPANDS "
            "IN DETERIORATING GROUPS"
        )

    if rotation.rotation_speed in {
        "FAST",
        "VERY FAST",
    }:
        return (
            "RAPID ROTATION MAY CREATE VOLATILE AND SHORT-LIVED "
            "SECTOR MOVES"
        )

    return (
        "SECTOR LEADERSHIP REMAINS MIXED, SUPPORTING ROTATIONAL "
        "OR STOCK-SPECIFIC MARKET BEHAVIOUR"
    )


# ==========================================================
# ANALYTICAL POSTURE
# ==========================================================

def determine_analytical_posture(
    *,
    rotation_status: str,
    decision_quality: str,
    decision_confidence: int,
    sector_risk_level: str,
) -> str:
    """
    Determine how AQSD should use sector intelligence.
    """

    if rotation_status == "INSUFFICIENT HISTORY":
        return (
            "USE CURRENT SECTOR STRENGTH WITH MODERATE WEIGHT. "
            "SECTOR ROTATION HISTORY IS STILL BEING ACCUMULATED."
        )

    if sector_risk_level == "VERY HIGH":
        return (
            "USE SECTOR INTELLIGENCE PRIMARILY AS A RISK WARNING "
            "AND REQUIRE CONFIRMATION FROM PRICE, BREADTH, OPTIONS "
            "AND PARTICIPANT DATA."
        )

    if (
        decision_quality in {
            "A",
            "B",
        }
        and decision_confidence >= 68
    ):
        return (
            "SECTOR INTELLIGENCE CAN RECEIVE NORMAL TO HIGH WEIGHT "
            "IN THE AQSD MASTER DECISION ENGINE."
        )

    if decision_quality == "C":
        return (
            "USE SECTOR INTELLIGENCE WITH NORMAL CROSS-CHECKS FROM "
            "MARKET BREADTH, PRICE STRUCTURE AND PARTICIPANT DATA."
        )

    return (
        "SECTOR INTELLIGENCE SHOULD RECEIVE LOW WEIGHT UNTIL "
        "LEADERSHIP AND ROTATION CONFIDENCE IMPROVE."
    )


# ==========================================================
# MARKET ENVIRONMENT
# ==========================================================

def determine_market_environment(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Build a concise market-environment description.
    """

    return (
        f"{strength.market_sector_health} SECTOR HEALTH | "
        f"{rotation.rotation_direction} | "
        f"{rotation.rotation_breadth} ROTATION BREADTH | "
        f"{rotation.leadership_stability} LEADERSHIP"
    )


# ==========================================================
# MASTER CONCLUSION
# ==========================================================

def determine_master_conclusion(
    *,
    sector_market_bias: str,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> str:
    """
    Build the final consolidated sector conclusion.
    """

    if sector_market_bias == "STRONGLY BULLISH":
        return (
            "SECTOR PARTICIPATION IS BROADLY BULLISH, LEADERSHIP "
            "IS STRONG AND ROTATION SUPPORTS A CONSTRUCTIVE "
            "MARKET-INTERNAL ENVIRONMENT."
        )

    if sector_market_bias == "BULLISH":
        return (
            "SECTOR PARTICIPATION IS POSITIVE AND LEADERSHIP IS "
            "SUPPORTIVE. THE MARKET ENVIRONMENT REMAINS CONSTRUCTIVE "
            "WHILE SECTOR CONFIRMATION CONDITIONS REMAIN INTACT."
        )

    if sector_market_bias == "CONSTRUCTIVE ROTATION":
        return (
            "SECTOR ROTATION IS IMPROVING, BUT MARKET STRENGTH "
            "REMAINS SELECTIVE. LEADERS AND EMERGING SECTORS MAY "
            "OUTPERFORM WHILE BROADER CONFIRMATION DEVELOPS."
        )

    if sector_market_bias in {
        "STRONGLY BEARISH",
        "BEARISH",
    }:
        return (
            "SECTOR PARTICIPATION REMAINS WEAK AND LEADERSHIP IS "
            "DETERIORATING. THE MARKET MAY REMAIN DEFENSIVE UNTIL "
            "SECTOR BREADTH AND ROTATION IMPROVE."
        )

    if sector_market_bias == "DETERIORATING ROTATION":
        return (
            "SECTOR LEADERSHIP IS NARROWING AND DETERIORATION IS "
            "EXPANDING. MARKET-INTERNAL RISK MAY INCREASE UNLESS "
            "EMERGING SECTORS STRENGTHEN."
        )

    return (
        f"SECTOR CONDITIONS ARE MIXED. THE STRONGEST SECTOR IS "
        f"{strength.strongest_sector}, THE WEAKEST SECTOR IS "
        f"{strength.weakest_sector}, AND ROTATION IS CLASSIFIED AS "
        f"{rotation.rotation_direction}. THE VIEW REMAINS "
        f"CONDITIONAL ON ADDITIONAL ROTATION HISTORY."
    )


# ==========================================================
# CONFIRMATION CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    sector_market_bias: str,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> tuple[str, ...]:
    """
    Build confirmation conditions.
    """

    conditions: list[str] = []

    if contains_any(
        sector_market_bias,
        (
            "BULLISH",
            "CONSTRUCTIVE",
        ),
    ):
        conditions.extend(
            [
                (
                    "The strongest sectors should remain within the "
                    "leading group."
                ),
                (
                    "The number of bullish sectors should remain stable "
                    "or increase."
                ),
                (
                    "Positive rotation should remain broader than "
                    "negative rotation."
                ),
                (
                    "Emerging sectors should continue improving in "
                    "rank and breadth score."
                ),
                (
                    "The number of sectors losing leadership should "
                    "remain limited."
                ),
            ]
        )

    elif "BEARISH" in sector_market_bias:
        conditions.extend(
            [
                (
                    "The number of bearish sectors should remain "
                    "dominant or increase."
                ),
                (
                    "Negative rotation should remain broader than "
                    "positive rotation."
                ),
                (
                    "Leading sectors should continue losing rank or "
                    "breadth score."
                ),
                (
                    "New laggards should continue to appear."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "Sector participation should develop a clear "
                    "positive or negative majority."
                ),
                (
                    "Leadership stability should improve."
                ),
                (
                    "Rotation breadth should expand beyond narrow "
                    "or mixed conditions."
                ),
            ]
        )

    if rotation.previous_date is None:
        conditions.append(
            "At least one additional sector-strength session is "
            "required for daily rotation confirmation."
        )

    if rotation.weekly_reference_date is None:
        conditions.append(
            "A five-session sector-rotation comparison should confirm "
            "the current daily direction."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# INVALIDATION CONDITIONS
# ==========================================================

def build_invalidation_conditions(
    *,
    sector_market_bias: str,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
) -> tuple[str, ...]:
    """
    Build invalidation conditions.
    """

    conditions: list[str] = []

    if contains_any(
        sector_market_bias,
        (
            "BULLISH",
            "CONSTRUCTIVE",
        ),
    ):
        conditions.extend(
            [
                (
                    "The strongest sectors fall materially in rank "
                    "and breadth score."
                ),
                (
                    "Positive sector rotation changes to broad "
                    "negative rotation."
                ),
                (
                    "The number of bearish sectors becomes greater "
                    "than the number of bullish sectors."
                ),
                (
                    "Several leading sectors move into losing-leadership "
                    "or laggard classifications."
                ),
            ]
        )

    elif "BEARISH" in sector_market_bias:
        conditions.extend(
            [
                (
                    "Broad positive sector rotation develops."
                ),
                (
                    "The number of bullish sectors rises materially."
                ),
                (
                    "New leaders and emerging sectors begin to dominate."
                ),
                (
                    "Persistent laggards improve sharply in rank and score."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "A broad positive rotation invalidates the mixed "
                    "sector classification."
                ),
                (
                    "A broad negative rotation invalidates the mixed "
                    "sector classification."
                ),
            ]
        )

    if rotation.rotation_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        conditions.append(
            "A sharp leadership reversal invalidates the current "
            "sector conclusion."
        )

    return tuple(
        dict.fromkeys(conditions)
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
    decision_confidence: int,
) -> tuple[str, ...]:
    """
    Combine and deduplicate engine warnings.
    """

    warnings: list[str] = []

    warnings.extend(
        strength.warnings
    )

    warnings.extend(
        rotation.warnings
    )

    if rotation.status == "INSUFFICIENT HISTORY":
        warnings.append(
            "Sector rotation history is insufficient for a fully "
            "confirmed decision."
        )

    if rotation.previous_date is None:
        warnings.append(
            "Daily sector-rank confirmation is unavailable."
        )

    if rotation.weekly_reference_date is None:
        warnings.append(
            "Weekly sector-rotation confirmation is unavailable."
        )

    if decision_confidence < 55:
        warnings.append(
            "Sector decision confidence is below 55%."
        )

    if rotation.rotation_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        warnings.append(
            f"Sector rotation risk is "
            f"{rotation.rotation_risk_level.lower()}."
        )

    if (
        strength.bullish_sectors
        < strength.bearish_sectors
        and "POSITIVE" in rotation.rotation_direction.upper()
    ):
        warnings.append(
            "Positive rotation conflicts with a bearish sector majority."
        )

    if (
        strength.bullish_sectors
        > strength.bearish_sectors
        and "NEGATIVE" in rotation.rotation_direction.upper()
    ):
        warnings.append(
            "Negative rotation conflicts with a bullish sector majority."
        )

    if not warnings:
        warnings.append(
            "No major consolidated sector warning is active."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# SUMMARY AND EXPLANATION
# ==========================================================

def build_concise_summary(
    *,
    sector_market_bias: str,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
    decision_confidence: int,
    decision_quality: str,
    sector_risk_level: str,
) -> str:
    """
    Build a dashboard-ready sector summary.
    """

    return (
        f"{sector_market_bias} SECTORS | "
        f"STRONGEST {strength.strongest_sector} | "
        f"WEAKEST {strength.weakest_sector} | "
        f"{rotation.rotation_direction} | "
        f"{rotation.rotation_breadth} BREADTH | "
        f"{rotation.leadership_stability} LEADERSHIP | "
        f"{sector_risk_level} RISK | "
        f"{decision_confidence}% CONFIDENCE | "
        f"QUALITY {decision_quality}"
    )


def build_explanation(
    *,
    strength: SectorStrengthEngineResult,
    rotation: SectorRotationEngineResult,
    sector_market_bias: str,
    participation_quality: str,
    leadership_quality: str,
    rotation_quality: str,
    sector_risk_level: str,
    decision_confidence: int,
    decision_quality: str,
    master_conclusion: str,
) -> str:
    """
    Build the final consolidated explanation.
    """

    return (
        f"The Sector Strength Engine analysed "
        f"{strength.sectors_analysed} sectors using "
        f"{strength.valid_rows:,} valid classified stocks. "
        f"{strength.bullish_sectors} sectors are bullish, "
        f"{strength.bearish_sectors} are bearish and "
        f"{strength.neutral_sectors} are neutral. "
        f"The strongest sector is {strength.strongest_sector} and "
        f"the weakest sector is {strength.weakest_sector}. "
        f"Overall sector health is "
        f"{strength.market_sector_health.lower()}. "
        f"The Sector Rotation Engine classified rotation as "
        f"{rotation.rotation_direction.lower()}, with "
        f"{rotation.rotation_breadth.lower()} breadth, "
        f"{rotation.rotation_speed.lower()} speed and "
        f"{rotation.leadership_stability.lower()} leadership stability. "
        f"There are {len(rotation.new_leaders)} new leaders, "
        f"{len(rotation.persistent_leaders)} persistent leaders, "
        f"{len(rotation.emerging_sectors)} emerging sectors and "
        f"{len(rotation.losing_leadership)} sectors losing leadership. "
        f"The dominant sector cycle is "
        f"{rotation.dominant_sector_cycle.lower()}. "
        f"Rotation risk is {rotation.rotation_risk_level.lower()} "
        f"at {rotation.rotation_risk_score}%. "
        f"The consolidated sector bias is "
        f"{sector_market_bias.lower()}, participation quality is "
        f"{participation_quality.lower()}, leadership quality is "
        f"{leadership_quality.lower()}, rotation quality is "
        f"{rotation_quality.lower()} and sector risk is "
        f"{sector_risk_level.lower()}. "
        f"Decision confidence is {decision_confidence}% and decision "
        f"quality is grade {decision_quality}. "
        f"Final conclusion: {master_conclusion}"
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_sector_rotation_decision_engine(
    *,
    requested_date: date,
    source_file: Path = DEFAULT_INPUT_FILE,
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
    export_strength: bool = False,
    export_rotation: bool = False,
) -> SectorRotationDecisionResult:
    """
    Run the complete Sector Rotation Decision Engine.
    """

    strength_result = run_sector_strength_engine(
        requested_date=requested_date,
        source_file=source_file,
        export=export_strength,
    )

    rotation_result = run_sector_rotation_engine(
        requested_date=requested_date,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
        export=export_rotation,
    )

    sector_market_bias = determine_sector_market_bias(
        strength=strength_result,
        rotation=rotation_result,
    )

    participation_quality = (
        determine_participation_quality(
            strength=strength_result,
            rotation=rotation_result,
        )
    )

    leadership_quality = (
        determine_leadership_quality(
            rotation_result
        )
    )

    rotation_quality = determine_rotation_quality(
        rotation=rotation_result,
        participation_quality=(
            participation_quality
        ),
        leadership_quality=(
            leadership_quality
        ),
    )

    sector_risk_level = determine_sector_risk_level(
        strength=strength_result,
        rotation=rotation_result,
        leadership_quality=leadership_quality,
    )

    decision_confidence = (
        calculate_decision_confidence(
            strength=strength_result,
            rotation=rotation_result,
            participation_quality=(
                participation_quality
            ),
            leadership_quality=(
                leadership_quality
            ),
            rotation_quality=rotation_quality,
        )
    )

    decision_quality = determine_decision_quality(
        confidence=decision_confidence,
        participation_quality=(
            participation_quality
        ),
        leadership_quality=leadership_quality,
        rotation_quality=rotation_quality,
        sector_risk_level=sector_risk_level,
    )

    expected_behaviour = determine_expected_behaviour(
        sector_market_bias=sector_market_bias,
        rotation=rotation_result,
    )

    analytical_posture = determine_analytical_posture(
        rotation_status=rotation_result.status,
        decision_quality=decision_quality,
        decision_confidence=decision_confidence,
        sector_risk_level=sector_risk_level,
    )

    market_environment = determine_market_environment(
        strength=strength_result,
        rotation=rotation_result,
    )

    master_conclusion = determine_master_conclusion(
        sector_market_bias=sector_market_bias,
        strength=strength_result,
        rotation=rotation_result,
    )

    confirmation_conditions = (
        build_confirmation_conditions(
            sector_market_bias=sector_market_bias,
            strength=strength_result,
            rotation=rotation_result,
        )
    )

    invalidation_conditions = (
        build_invalidation_conditions(
            sector_market_bias=sector_market_bias,
            strength=strength_result,
            rotation=rotation_result,
        )
    )

    warnings = build_warnings(
        strength=strength_result,
        rotation=rotation_result,
        decision_confidence=decision_confidence,
    )

    concise_summary = build_concise_summary(
        sector_market_bias=sector_market_bias,
        strength=strength_result,
        rotation=rotation_result,
        decision_confidence=decision_confidence,
        decision_quality=decision_quality,
        sector_risk_level=sector_risk_level,
    )

    explanation = build_explanation(
        strength=strength_result,
        rotation=rotation_result,
        sector_market_bias=sector_market_bias,
        participation_quality=(
            participation_quality
        ),
        leadership_quality=leadership_quality,
        rotation_quality=rotation_quality,
        sector_risk_level=sector_risk_level,
        decision_confidence=decision_confidence,
        decision_quality=decision_quality,
        master_conclusion=master_conclusion,
    )

    if strength_result.status != "SUCCESS":
        overall_status = "FAILED"

    elif rotation_result.status == "FAILED":
        overall_status = "FAILED"

    elif rotation_result.status == "INSUFFICIENT HISTORY":
        overall_status = "SUCCESS WITH LIMITED HISTORY"

    else:
        overall_status = "SUCCESS"

    return SectorRotationDecisionResult(
        requested_date=requested_date,
        analysis_date=strength_result.analysis_date,
        source_file=source_file,

        sectors_analysed=(
            strength_result.sectors_analysed
        ),
        bullish_sectors=(
            strength_result.bullish_sectors
        ),
        bearish_sectors=(
            strength_result.bearish_sectors
        ),
        neutral_sectors=(
            strength_result.neutral_sectors
        ),

        strongest_sector=(
            strength_result.strongest_sector
        ),
        weakest_sector=(
            strength_result.weakest_sector
        ),

        sector_market_bias=sector_market_bias,
        sector_participation_quality=(
            participation_quality
        ),
        leadership_quality=leadership_quality,
        rotation_quality=rotation_quality,

        broad_rotation=(
            strength_result.broad_rotation
        ),
        market_sector_health=(
            strength_result.market_sector_health
        ),

        rotation_direction=(
            rotation_result.rotation_direction
        ),
        rotation_breadth=(
            rotation_result.rotation_breadth
        ),
        rotation_speed=(
            rotation_result.rotation_speed
        ),
        leadership_stability=(
            rotation_result.leadership_stability
        ),
        dominant_sector_cycle=(
            rotation_result.dominant_sector_cycle
        ),

        new_leaders=sector_names(
            rotation_result.new_leaders
        ),
        persistent_leaders=sector_names(
            rotation_result.persistent_leaders
        ),
        emerging_sectors=sector_names(
            rotation_result.emerging_sectors
        ),
        losing_leadership=sector_names(
            rotation_result.losing_leadership
        ),
        new_laggards=sector_names(
            rotation_result.new_laggards
        ),
        persistent_laggards=sector_names(
            rotation_result.persistent_laggards
        ),

        improving_sectors=(
            rotation_result.improving_sectors
        ),
        deteriorating_sectors=(
            rotation_result.deteriorating_sectors
        ),
        stable_sectors=(
            rotation_result.stable_sector_count
        ),

        rotation_risk_score=(
            rotation_result.rotation_risk_score
        ),
        rotation_risk_level=(
            rotation_result.rotation_risk_level
        ),
        sector_risk_level=sector_risk_level,

        expected_behaviour=expected_behaviour,
        analytical_posture=analytical_posture,
        market_environment=market_environment,

        strength_confidence=(
            strength_result.confidence
        ),
        rotation_confidence=(
            rotation_result.confidence
        ),
        decision_confidence=(
            decision_confidence
        ),
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

        strength_status=strength_result.status,
        rotation_status=rotation_result.status,
        status=overall_status,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: SectorRotationDecisionResult,
) -> None:
    """
    Display the complete MBI-008 result.
    """

    print()
    print("=" * 116)
    print("AQSD SECTOR ROTATION DECISION ENGINE")
    print("=" * 116)
    print(
        f"Module                              : "
        f"{MODULE_ID}"
    )
    print(
        f"Version                             : "
        f"{MODULE_VERSION}"
    )
    print(
        f"Requested Date                      : "
        f"{result.requested_date}"
    )
    print(
        f"Analysis Date                       : "
        f"{result.analysis_date}"
    )
    print(
        f"Source File                         : "
        f"{result.source_file}"
    )
    print("-" * 116)

    print("SECTOR MARKET STRUCTURE")
    print("-" * 116)
    print(
        f"Sectors Analysed                    : "
        f"{result.sectors_analysed}"
    )
    print(
        f"Bullish Sectors                     : "
        f"{result.bullish_sectors}"
    )
    print(
        f"Bearish Sectors                     : "
        f"{result.bearish_sectors}"
    )
    print(
        f"Neutral Sectors                     : "
        f"{result.neutral_sectors}"
    )
    print(
        f"Strongest Sector                    : "
        f"{result.strongest_sector}"
    )
    print(
        f"Weakest Sector                      : "
        f"{result.weakest_sector}"
    )
    print(
        f"Sector Market Bias                  : "
        f"{result.sector_market_bias}"
    )
    print(
        f"Sector Participation Quality        : "
        f"{result.sector_participation_quality}"
    )
    print(
        f"Leadership Quality                  : "
        f"{result.leadership_quality}"
    )
    print(
        f"Rotation Quality                    : "
        f"{result.rotation_quality}"
    )
    print("-" * 116)

    print("ROTATION STRUCTURE")
    print("-" * 116)
    print(
        f"Broad Rotation                      : "
        f"{result.broad_rotation}"
    )
    print(
        f"Market Sector Health                : "
        f"{result.market_sector_health}"
    )
    print(
        f"Rotation Direction                  : "
        f"{result.rotation_direction}"
    )
    print(
        f"Rotation Breadth                    : "
        f"{result.rotation_breadth}"
    )
    print(
        f"Rotation Speed                      : "
        f"{result.rotation_speed}"
    )
    print(
        f"Leadership Stability                : "
        f"{result.leadership_stability}"
    )
    print(
        f"Dominant Sector Cycle               : "
        f"{result.dominant_sector_cycle}"
    )
    print("-" * 116)

    print("LEADERSHIP GROUPS")
    print("-" * 116)
    print(
        f"New Leaders                         : "
        f"{join_sector_names(result.new_leaders)}"
    )
    print(
        f"Persistent Leaders                  : "
        f"{join_sector_names(result.persistent_leaders)}"
    )
    print(
        f"Emerging Sectors                    : "
        f"{join_sector_names(result.emerging_sectors)}"
    )
    print(
        f"Losing Leadership                   : "
        f"{join_sector_names(result.losing_leadership)}"
    )
    print(
        f"New Laggards                        : "
        f"{join_sector_names(result.new_laggards)}"
    )
    print(
        f"Persistent Laggards                 : "
        f"{join_sector_names(result.persistent_laggards)}"
    )
    print("-" * 116)

    print("ROTATION PARTICIPATION")
    print("-" * 116)
    print(
        f"Improving Sectors                   : "
        f"{result.improving_sectors}"
    )
    print(
        f"Deteriorating Sectors               : "
        f"{result.deteriorating_sectors}"
    )
    print(
        f"Stable Sectors                      : "
        f"{result.stable_sectors}"
    )
    print("-" * 116)

    print("SECTOR RISK")
    print("-" * 116)
    print(
        f"Rotation Risk Score                 : "
        f"{result.rotation_risk_score}%"
    )
    print(
        f"Rotation Risk Level                 : "
        f"{result.rotation_risk_level}"
    )
    print(
        f"Consolidated Sector Risk            : "
        f"{result.sector_risk_level}"
    )
    print("-" * 116)

    print("DECISION")
    print("-" * 116)
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
        f"Strength Confidence                 : "
        f"{result.strength_confidence}%"
    )
    print(
        f"Rotation Confidence                 : "
        f"{result.rotation_confidence}%"
    )
    print(
        f"Decision Confidence                 : "
        f"{result.decision_confidence}%"
    )
    print(
        f"Decision Quality                    : "
        f"{result.decision_quality}"
    )
    print("-" * 116)

    print("MASTER CONCLUSION")
    print("-" * 116)
    print(result.master_conclusion)

    print("-" * 116)
    print("CONCISE SUMMARY")
    print("-" * 116)
    print(result.concise_summary)

    print("-" * 116)
    print("CONFIRMATION CONDITIONS")
    print("-" * 116)

    for number, condition in enumerate(
        result.confirmation_conditions,
        start=1,
    ):
        print(
            f"{number}. {condition}"
        )

    print("-" * 116)
    print("INVALIDATION CONDITIONS")
    print("-" * 116)

    for number, condition in enumerate(
        result.invalidation_conditions,
        start=1,
    ):
        print(
            f"{number}. {condition}"
        )

    print("-" * 116)
    print("WARNINGS")
    print("-" * 116)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(
            f"{number}. {warning}"
        )

    print("-" * 116)
    print("EXPLANATION")
    print("-" * 116)
    print(result.explanation)

    print("-" * 116)
    print(
        "Method                              : "
        "RULE-BASED SECTOR ROTATION DECISION"
    )
    print(
        f"Strength Engine Status              : "
        f"{result.strength_status}"
    )
    print(
        f"Rotation Engine Status              : "
        f"{result.rotation_status}"
    )
    print(
        f"Overall Status                      : "
        f"{result.status}"
    )
    print("=" * 116)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD.
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
            "Run the AQSD Sector Rotation Decision Engine."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help=(
            "Requested analysis date in YYYY-MM-DD format."
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=(
            "Path to the enriched market-breadth snapshot. "
            f"Default: {DEFAULT_INPUT_FILE}"
        ),
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
        help=(
            "Saved sessions used for weekly sector rotation. "
            f"Default: {DEFAULT_WEEKLY_LOOKBACK_SESSIONS}."
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
        print(
            "Reason : --weekly-sessions must be at least 1."
        )
        raise SystemExit(1)

    try:
        result = run_sector_rotation_decision_engine(
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
            export_strength=False,
            export_rotation=False,
        )

    except Exception as exc:
        print()
        print("=" * 116)
        print(
            "AQSD SECTOR ROTATION DECISION ENGINE"
        )
        print("=" * 116)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 116)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()