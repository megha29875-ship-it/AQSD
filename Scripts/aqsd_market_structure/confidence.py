"""
AQSD
Market Structure Engine

Module: confidence.py
Version: 1.0
Author: AQSD

Description:
Combines the AQSD Trend Engine and structural-analysis
results into one explainable Confidence Score.

Inputs:

- Trend Score
- Recent HH / HL / LH / LL swing structure
- Break of Structure (BOS)
- Change of Character (CHOCH)
- Agreement between trend and structure

Scoring:

- Trend Score component       : 40 points
- Swing Structure component   : 25 points
- BOS component               : 15 points
- CHOCH component             : 10 points
- Alignment component         : 10 points

Total                         : 100 points

Interpretation:

- Scores above 50 favour bullish structure.
- Scores below 50 favour bearish structure.
- Scores near 50 indicate uncertainty or conflicting evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Sequence

from .models import SwingPoint, TrendResult


TREND_WEIGHT = 40.0
SWING_WEIGHT = 25.0
BOS_WEIGHT = 15.0
CHOCH_WEIGHT = 10.0
ALIGNMENT_WEIGHT = 10.0

RECENT_SWING_LIMIT = 10


# =========================================================
# RESULT MODEL
# =========================================================


@dataclass
class ConfidenceResult:
    """
    Complete AQSD Market Structure Confidence result.

    confidence_score:
        Directional market-structure score from 0 to 100.

        100:
            Maximum bullish confidence.

        50:
            Neutral or conflicting evidence.

        0:
            Maximum bearish confidence.

    directional_confidence:
        Strength of conviction irrespective of direction.

        Formula:

            abs(confidence_score - 50) * 2
    """

    confidence_score: float = 50.0
    confidence_rating: str = "NEUTRAL"
    directional_bias: str = "NEUTRAL"
    directional_confidence: float = 0.0
    trade_quality: str = "NO TRADE"
    market_state: str = "UNCONFIRMED"

    trend_component: float = 20.0
    swing_component: float = 12.5
    bos_component: float = 7.5
    choch_component: float = 5.0
    alignment_component: float = 5.0

    bullish_swing_percent: float = 50.0
    bearish_swing_percent: float = 50.0
    structure_direction: str = "NEUTRAL"

    score_breakdown: Dict[str, float] = field(
        default_factory=dict
    )

    evidence: List[str] = field(
        default_factory=list
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ConfidenceResult to a dictionary.
        """

        return asdict(self)


# =========================================================
# GENERAL HELPERS
# =========================================================


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Restrict a numerical value to a specified range.
    """

    return max(
        minimum,
        min(maximum, float(value)),
    )


def get_enum_value(
    value: Any,
) -> str:
    """
    Safely extract a string from an enum or plain value.
    """

    if value is None:
        return ""

    enum_value = getattr(
        value,
        "value",
        value,
    )

    return str(enum_value).strip().upper()


def calculate_directional_confidence(
    confidence_score: float,
) -> float:
    """
    Calculate strength of conviction irrespective of direction.
    """

    normalized_score = clamp(
        confidence_score,
        0.0,
        100.0,
    )

    strength = abs(
        normalized_score - 50.0
    ) * 2.0

    return clamp(
        strength,
        0.0,
        100.0,
    )


# =========================================================
# RATING HELPERS
# =========================================================


def classify_directional_bias(
    score: float,
) -> str:
    """
    Classify the directional market bias.
    """

    if score >= 55.0:
        return "BULLISH"

    if score <= 45.0:
        return "BEARISH"

    return "NEUTRAL"


def classify_confidence_rating(
    directional_confidence: float,
) -> str:
    """
    Classify confidence strength irrespective of direction.
    """

    if directional_confidence >= 90.0:
        return "INSTITUTIONAL GRADE"

    if directional_confidence >= 80.0:
        return "VERY HIGH"

    if directional_confidence >= 65.0:
        return "HIGH"

    if directional_confidence >= 45.0:
        return "MODERATE"

    if directional_confidence >= 25.0:
        return "LOW"

    return "NEUTRAL / CONFLICTING"


def classify_trade_quality(
    directional_confidence: float,
) -> str:
    """
    Convert directional confidence into a trade-quality grade.

    This is an analytical grade only. It is not an instruction
    to enter a trade.
    """

    if directional_confidence >= 90.0:
        return "A+"

    if directional_confidence >= 80.0:
        return "A"

    if directional_confidence >= 65.0:
        return "B"

    if directional_confidence >= 50.0:
        return "C"

    return "NO TRADE"


# =========================================================
# TREND COMPONENT
# =========================================================


def calculate_trend_component(
    trend_result: TrendResult,
) -> float:
    """
    Convert the existing Trend Score into a maximum of 40 points.
    """

    trend_score = clamp(
        trend_result.trend_score,
        0.0,
        100.0,
    )

    return (
        trend_score / 100.0
    ) * TREND_WEIGHT


# =========================================================
# SWING STRUCTURE COMPONENT
# =========================================================


def combine_recent_swings(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
    limit: int = RECENT_SWING_LIMIT,
) -> List[SwingPoint]:
    """
    Combine swing highs and lows and retain the most recent swings.
    """

    combined = list(
        swing_highs
    ) + list(
        swing_lows
    )

    combined.sort(
        key=lambda swing: swing.timestamp
    )

    if limit <= 0:
        return combined

    return combined[-limit:]


def swing_direction_value(
    swing: SwingPoint,
) -> float:
    """
    Convert a swing classification to a directional value.

    HH and HL:
        1.0, bullish

    LH and LL:
        0.0, bearish

    Unknown or initial swings:
        0.5, neutral
    """

    swing_type = get_enum_value(
        swing.swing_type
    )

    if swing_type in {
        "HH",
        "HL",
        "HIGHER_HIGH",
        "HIGHER_LOW",
    }:
        return 1.0

    if swing_type in {
        "LH",
        "LL",
        "LOWER_HIGH",
        "LOWER_LOW",
    }:
        return 0.0

    return 0.5


def calculate_weighted_swing_ratio(
    recent_swings: Sequence[SwingPoint],
) -> float:
    """
    Calculate a recency-weighted bullish swing ratio.

    Older swings receive lower weights.
    Recent swings receive higher weights.

    Example with five swings:

        Oldest weight:
            1

        Latest weight:
            5
    """

    if not recent_swings:
        return 0.5

    weighted_total = 0.0
    total_weight = 0.0

    for position, swing in enumerate(
        recent_swings,
        start=1,
    ):
        weight = float(position)

        direction_value = swing_direction_value(
            swing
        )

        weighted_total += (
            direction_value * weight
        )

        total_weight += weight

    if total_weight == 0:
        return 0.5

    return weighted_total / total_weight


def classify_structure_direction(
    bullish_ratio: float,
) -> str:
    """
    Classify the weighted swing structure.
    """

    if bullish_ratio >= 0.60:
        return "BULLISH"

    if bullish_ratio <= 0.40:
        return "BEARISH"

    return "NEUTRAL"


def calculate_swing_component(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> tuple[
    float,
    float,
    float,
    str,
    List[SwingPoint],
]:
    """
    Calculate the adaptive swing-structure component.

    Returns:

        swing score
        bullish swing percent
        bearish swing percent
        structure direction
        recent swings used
    """

    recent_swings = combine_recent_swings(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        limit=RECENT_SWING_LIMIT,
    )

    bullish_ratio = calculate_weighted_swing_ratio(
        recent_swings=recent_swings
    )

    bullish_percent = (
        bullish_ratio * 100.0
    )

    bearish_percent = (
        100.0 - bullish_percent
    )

    swing_component = (
        bullish_ratio * SWING_WEIGHT
    )

    structure_direction = (
        classify_structure_direction(
            bullish_ratio=bullish_ratio
        )
    )

    return (
        swing_component,
        bullish_percent,
        bearish_percent,
        structure_direction,
        recent_swings,
    )


# =========================================================
# BOS COMPONENT
# =========================================================


def calculate_bos_component(
    bos_result: Any,
) -> tuple[float, str]:
    """
    Calculate the BOS component.

    Bullish BOS:
        15 points

    No BOS:
        7.5 points

    Bearish BOS:
        0 points
    """

    detected = bool(
        getattr(
            bos_result,
            "detected",
            False,
        )
    )

    direction = get_enum_value(
        getattr(
            bos_result,
            "direction",
            "",
        )
    )

    bullish_terms = {
        "BULLISH",
        "BULLISH_BOS",
        "UP",
        "UPWARD",
    }

    bearish_terms = {
        "BEARISH",
        "BEARISH_BOS",
        "DOWN",
        "DOWNWARD",
    }

    if detected and direction in bullish_terms:
        return BOS_WEIGHT, "BULLISH"

    if detected and direction in bearish_terms:
        return 0.0, "BEARISH"

    return BOS_WEIGHT / 2.0, "NEUTRAL"


# =========================================================
# CHOCH COMPONENT
# =========================================================


def calculate_choch_component(
    choch_result: Any,
) -> tuple[float, str]:
    """
    Calculate the CHOCH component.

    Bullish CHOCH:
        10 points

    No CHOCH:
        5 points

    Bearish CHOCH:
        0 points
    """

    detected = bool(
        getattr(
            choch_result,
            "detected",
            False,
        )
    )

    direction = get_enum_value(
        getattr(
            choch_result,
            "direction",
            "",
        )
    )

    bullish_terms = {
        "BULLISH",
        "BULLISH_CHOCH",
        "UP",
        "UPWARD",
    }

    bearish_terms = {
        "BEARISH",
        "BEARISH_CHOCH",
        "DOWN",
        "DOWNWARD",
    }

    if detected and direction in bullish_terms:
        return CHOCH_WEIGHT, "BULLISH"

    if detected and direction in bearish_terms:
        return 0.0, "BEARISH"

    return CHOCH_WEIGHT / 2.0, "NEUTRAL"


# =========================================================
# ALIGNMENT COMPONENT
# =========================================================


def calculate_alignment_component(
    trend_direction: str,
    structure_direction: str,
    bos_direction: str,
    choch_direction: str,
) -> tuple[float, str]:
    """
    Reward agreement between independent engine components.

    Full alignment:
        10 points bullish
        0 points bearish

    Neutral evidence:
        Approximately 5 points

    Conflicting evidence:
        Reduced score toward the opposite side
    """

    directional_inputs = [
        trend_direction,
        structure_direction,
        bos_direction,
        choch_direction,
    ]

    bullish_count = directional_inputs.count(
        "BULLISH"
    )

    bearish_count = directional_inputs.count(
        "BEARISH"
    )

    neutral_count = directional_inputs.count(
        "NEUTRAL"
    )

    total_votes = (
        bullish_count
        + bearish_count
        + neutral_count
    )

    if total_votes == 0:
        return ALIGNMENT_WEIGHT / 2.0, "NO DATA"

    directional_value = (
        bullish_count
        + (neutral_count * 0.5)
    ) / total_votes

    alignment_component = (
        directional_value * ALIGNMENT_WEIGHT
    )

    if bullish_count >= 3:
        state = "BULLISH ALIGNMENT"

    elif bearish_count >= 3:
        state = "BEARISH ALIGNMENT"

    elif (
        bullish_count > 0
        and bearish_count > 0
    ):
        state = "CONFLICTING SIGNALS"

    else:
        state = "PARTIAL ALIGNMENT"

    return alignment_component, state


# =========================================================
# MARKET-STATE CLASSIFICATION
# =========================================================


def classify_market_state(
    directional_bias: str,
    trend_direction: str,
    structure_direction: str,
    bos_direction: str,
    choch_direction: str,
) -> str:
    """
    Produce an explainable market-state classification.
    """

    if (
        trend_direction == "BULLISH"
        and structure_direction == "BULLISH"
        and bos_direction == "BULLISH"
    ):
        return "CONFIRMED BULLISH TREND"

    if (
        trend_direction == "BEARISH"
        and structure_direction == "BEARISH"
        and bos_direction == "BEARISH"
    ):
        return "CONFIRMED BEARISH TREND"

    if (
        trend_direction == "BULLISH"
        and structure_direction == "BEARISH"
    ):
        return "BULLISH TREND WITH WEAKENING STRUCTURE"

    if (
        trend_direction == "BEARISH"
        and structure_direction == "BULLISH"
    ):
        return "BEARISH TREND WITH IMPROVING STRUCTURE"

    if choch_direction == "BULLISH":
        return "POTENTIAL BULLISH REVERSAL"

    if choch_direction == "BEARISH":
        return "POTENTIAL BEARISH REVERSAL"

    if directional_bias == "NEUTRAL":
        return "CONFLICTING / TRANSITIONAL MARKET"

    if directional_bias == "BULLISH":
        return "UNCONFIRMED BULLISH BIAS"

    if directional_bias == "BEARISH":
        return "UNCONFIRMED BEARISH BIAS"

    return "UNCONFIRMED"


# =========================================================
# MAIN CONFIDENCE ENGINE
# =========================================================


def calculate_confidence(
    trend_result: TrendResult,
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
    bos_result: Any,
    choch_result: Any,
) -> ConfidenceResult:
    """
    Run the complete AQSD Confidence Engine.
    """

    if trend_result is None:
        raise ValueError(
            "trend_result is required."
        )

    trend_component = calculate_trend_component(
        trend_result=trend_result
    )

    (
        swing_component,
        bullish_swing_percent,
        bearish_swing_percent,
        structure_direction,
        recent_swings,
    ) = calculate_swing_component(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )

    (
        bos_component,
        bos_direction,
    ) = calculate_bos_component(
        bos_result=bos_result
    )

    (
        choch_component,
        choch_direction,
    ) = calculate_choch_component(
        choch_result=choch_result
    )

    trend_direction = get_enum_value(
        trend_result.direction
    )

    (
        alignment_component,
        alignment_state,
    ) = calculate_alignment_component(
        trend_direction=trend_direction,
        structure_direction=structure_direction,
        bos_direction=bos_direction,
        choch_direction=choch_direction,
    )

    score_breakdown = {
        "trend_component": round(
            trend_component,
            2,
        ),
        "swing_component": round(
            swing_component,
            2,
        ),
        "bos_component": round(
            bos_component,
            2,
        ),
        "choch_component": round(
            choch_component,
            2,
        ),
        "alignment_component": round(
            alignment_component,
            2,
        ),
    }

    confidence_score = sum(
        score_breakdown.values()
    )

    confidence_score = clamp(
        confidence_score,
        0.0,
        100.0,
    )

    directional_bias = classify_directional_bias(
        score=confidence_score
    )

    directional_confidence = (
        calculate_directional_confidence(
            confidence_score=confidence_score
        )
    )

    confidence_rating = (
        classify_confidence_rating(
            directional_confidence=directional_confidence
        )
    )

    trade_quality = classify_trade_quality(
        directional_confidence=directional_confidence
    )

    market_state = classify_market_state(
        directional_bias=directional_bias,
        trend_direction=trend_direction,
        structure_direction=structure_direction,
        bos_direction=bos_direction,
        choch_direction=choch_direction,
    )

    evidence: List[str] = []

    evidence.append(
        "Trend component is "
        f"{trend_component:.2f}/{TREND_WEIGHT:.0f}, "
        f"derived from Trend Score "
        f"{trend_result.trend_score:.2f}/100"
    )

    evidence.append(
        f"Swing structure used the latest "
        f"{len(recent_swings)} confirmed swings"
    )

    evidence.append(
        "Weighted swing structure is "
        f"{bullish_swing_percent:.2f}% bullish and "
        f"{bearish_swing_percent:.2f}% bearish"
    )

    evidence.append(
        f"Structure direction is {structure_direction}"
    )

    evidence.append(
        f"BOS direction contribution is {bos_direction}"
    )

    evidence.append(
        f"CHOCH direction contribution is {choch_direction}"
    )

    evidence.append(
        f"Engine alignment state is {alignment_state}"
    )

    evidence.append(
        f"Final directional bias is {directional_bias}"
    )

    evidence.append(
        f"Market state is {market_state}"
    )

    return ConfidenceResult(
        confidence_score=round(
            confidence_score,
            2,
        ),
        confidence_rating=confidence_rating,
        directional_bias=directional_bias,
        directional_confidence=round(
            directional_confidence,
            2,
        ),
        trade_quality=trade_quality,
        market_state=market_state,
        trend_component=round(
            trend_component,
            2,
        ),
        swing_component=round(
            swing_component,
            2,
        ),
        bos_component=round(
            bos_component,
            2,
        ),
        choch_component=round(
            choch_component,
            2,
        ),
        alignment_component=round(
            alignment_component,
            2,
        ),
        bullish_swing_percent=round(
            bullish_swing_percent,
            2,
        ),
        bearish_swing_percent=round(
            bearish_swing_percent,
            2,
        ),
        structure_direction=structure_direction,
        score_breakdown=score_breakdown,
        evidence=evidence,
    )