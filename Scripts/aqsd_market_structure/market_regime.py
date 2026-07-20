"""
AQSD
Market Structure Engine

Module: market_regime.py
Version: 1.0
Author: AQSD

Description:
Classifies the current market environment using:

- Trend direction
- Trend strength
- Trend Score
- Swing structure
- BOS
- CHOCH
- Confidence Score
- Directional Confidence

Possible regimes:

- STRONG BULL TREND
- BULL TREND
- WEAK BULL TREND
- STRONG BEAR TREND
- BEAR TREND
- WEAK BEAR TREND
- RANGE BOUND
- BULLISH TRANSITION
- BEARISH TRANSITION
- BULLISH REVERSAL WATCH
- BEARISH REVERSAL WATCH
- CONFLICTING STRUCTURE
- UNCONFIRMED
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from .confidence import ConfidenceResult
from .models import TrendResult


# =========================================================
# RESULT MODEL
# =========================================================


@dataclass
class MarketRegimeResult:
    """
    Complete AQSD Market Regime result.
    """

    market_regime: str = "UNCONFIRMED"
    regime_score: float = 50.0

    directional_bias: str = "NEUTRAL"
    regime_strength: str = "LOW"

    trend_state: str = "NEUTRAL"
    structure_state: str = "NEUTRAL"
    break_state: str = "NO STRUCTURAL BREAK"

    continuation_probability: float = 50.0
    reversal_probability: float = 50.0
    range_probability: float = 50.0

    strategy_environment: str = "WAIT"
    risk_state: str = "ELEVATED"

    score_breakdown: Dict[str, float] = field(
        default_factory=dict
    )

    evidence: List[str] = field(
        default_factory=list
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to a dictionary.
        """

        return asdict(self)


# =========================================================
# HELPERS
# =========================================================


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Restrict a value to a defined range.
    """

    return max(
        minimum,
        min(maximum, float(value)),
    )


def get_enum_value(
    value: Any,
) -> str:
    """
    Safely convert enum or plain value to uppercase text.
    """

    if value is None:
        return ""

    enum_value = getattr(
        value,
        "value",
        value,
    )

    return str(enum_value).strip().upper()


def normalize_direction(
    value: Any,
) -> str:
    """
    Convert different directional labels into:

    - BULLISH
    - BEARISH
    - NEUTRAL
    """

    text = get_enum_value(value)

    bullish_terms = {
        "BULLISH",
        "BULL",
        "UP",
        "UPWARD",
        "BULLISH_BOS",
        "BULLISH_CHOCH",
    }

    bearish_terms = {
        "BEARISH",
        "BEAR",
        "DOWN",
        "DOWNWARD",
        "BEARISH_BOS",
        "BEARISH_CHOCH",
    }

    if text in bullish_terms:
        return "BULLISH"

    if text in bearish_terms:
        return "BEARISH"

    return "NEUTRAL"


# =========================================================
# TREND CLASSIFICATION
# =========================================================


def classify_trend_state(
    trend_result: TrendResult,
) -> str:
    """
    Classify the Trend Engine result.
    """

    direction = normalize_direction(
        trend_result.direction
    )

    strength = get_enum_value(
        trend_result.strength
    )

    score = clamp(
        trend_result.trend_score
    )

    if direction == "BULLISH":

        if score >= 80.0 and strength == "STRONG":
            return "STRONG BULLISH"

        if score >= 60.0:
            return "BULLISH"

        return "WEAK BULLISH"

    if direction == "BEARISH":

        if score <= 20.0 and strength == "STRONG":
            return "STRONG BEARISH"

        if score <= 40.0:
            return "BEARISH"

        return "WEAK BEARISH"

    if strength == "STRONG":
        return "STRONG BUT DIRECTIONALLY NEUTRAL"

    return "NEUTRAL"


# =========================================================
# BREAK CLASSIFICATION
# =========================================================


def classify_break_state(
    bos_result: Any,
    choch_result: Any,
) -> str:
    """
    Classify BOS and CHOCH together.
    """

    bos_detected = bool(
        getattr(
            bos_result,
            "detected",
            False,
        )
    )

    choch_detected = bool(
        getattr(
            choch_result,
            "detected",
            False,
        )
    )

    bos_direction = normalize_direction(
        getattr(
            bos_result,
            "direction",
            None,
        )
    )

    choch_direction = normalize_direction(
        getattr(
            choch_result,
            "direction",
            None,
        )
    )

    if choch_detected:

        if choch_direction == "BULLISH":
            return "BULLISH CHOCH"

        if choch_direction == "BEARISH":
            return "BEARISH CHOCH"

    if bos_detected:

        if bos_direction == "BULLISH":
            return "BULLISH BOS"

        if bos_direction == "BEARISH":
            return "BEARISH BOS"

    return "NO STRUCTURAL BREAK"


# =========================================================
# PROBABILITY CALCULATIONS
# =========================================================


def calculate_probabilities(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    bos_result: Any,
    choch_result: Any,
) -> tuple[float, float, float]:
    """
    Estimate continuation, reversal and range probabilities.

    These values are analytical scores, not statistical forecasts.
    """

    trend_score = clamp(
        trend_result.trend_score
    )

    confidence_power = clamp(
        confidence_result.directional_confidence
    )

    structure_bullish = clamp(
        confidence_result.bullish_swing_percent
    )

    structure_bearish = clamp(
        confidence_result.bearish_swing_percent
    )

    trend_direction = normalize_direction(
        trend_result.direction
    )

    confidence_direction = normalize_direction(
        confidence_result.directional_bias
    )

    bos_detected = bool(
        getattr(
            bos_result,
            "detected",
            False,
        )
    )

    choch_detected = bool(
        getattr(
            choch_result,
            "detected",
            False,
        )
    )

    bos_direction = normalize_direction(
        getattr(
            bos_result,
            "direction",
            None,
        )
    )

    choch_direction = normalize_direction(
        getattr(
            choch_result,
            "direction",
            None,
        )
    )

    continuation = 35.0
    reversal = 20.0
    range_probability = 35.0

    if trend_direction == confidence_direction:

        if trend_direction in {
            "BULLISH",
            "BEARISH",
        }:
            continuation += (
                confidence_power * 0.30
            )

    else:
        reversal += 15.0
        range_probability += 10.0

    if trend_direction == "BULLISH":
        continuation += (
            trend_score * 0.20
        )

    elif trend_direction == "BEARISH":
        continuation += (
            (100.0 - trend_score) * 0.20
        )

    else:
        range_probability += 20.0

    if bos_detected:

        if bos_direction == trend_direction:
            continuation += 15.0
            range_probability -= 10.0

        else:
            reversal += 15.0

    if choch_detected:

        reversal += 25.0
        continuation -= 15.0
        range_probability -= 5.0

        if choch_direction == confidence_direction:
            reversal += 5.0

    structure_difference = abs(
        structure_bullish - structure_bearish
    )

    if structure_difference < 10.0:
        range_probability += 15.0

    elif structure_difference > 30.0:
        continuation += 10.0
        range_probability -= 5.0

    continuation = clamp(
        continuation
    )

    reversal = clamp(
        reversal
    )

    range_probability = clamp(
        range_probability
    )

    total = (
        continuation
        + reversal
        + range_probability
    )

    if total <= 0:
        return 33.33, 33.33, 33.34

    continuation = (
        continuation / total
    ) * 100.0

    reversal = (
        reversal / total
    ) * 100.0

    range_probability = (
        range_probability / total
    ) * 100.0

    return (
        round(continuation, 2),
        round(reversal, 2),
        round(range_probability, 2),
    )


# =========================================================
# REGIME CLASSIFICATION
# =========================================================


def classify_market_regime(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    break_state: str,
    continuation_probability: float,
    reversal_probability: float,
    range_probability: float,
) -> str:
    """
    Determine the final AQSD Market Regime.
    """

    trend_direction = normalize_direction(
        trend_result.direction
    )

    confidence_direction = normalize_direction(
        confidence_result.directional_bias
    )

    confidence_power = clamp(
        confidence_result.directional_confidence
    )

    structure_direction = normalize_direction(
        confidence_result.structure_direction
    )

    if break_state == "BULLISH CHOCH":
        return "BULLISH REVERSAL WATCH"

    if break_state == "BEARISH CHOCH":
        return "BEARISH REVERSAL WATCH"

    if (
        trend_direction == "BULLISH"
        and structure_direction == "BULLISH"
        and break_state == "BULLISH BOS"
        and confidence_power >= 65.0
    ):
        return "STRONG BULL TREND"

    if (
        trend_direction == "BEARISH"
        and structure_direction == "BEARISH"
        and break_state == "BEARISH BOS"
        and confidence_power >= 65.0
    ):
        return "STRONG BEAR TREND"

    if (
        trend_direction == "BULLISH"
        and confidence_direction == "BULLISH"
        and structure_direction != "BEARISH"
    ):

        if confidence_power >= 45.0:
            return "BULL TREND"

        return "WEAK BULL TREND"

    if (
        trend_direction == "BEARISH"
        and confidence_direction == "BEARISH"
        and structure_direction != "BULLISH"
    ):

        if confidence_power >= 45.0:
            return "BEAR TREND"

        return "WEAK BEAR TREND"

    if (
        trend_direction == "BULLISH"
        and structure_direction == "BEARISH"
    ):
        return "BEARISH TRANSITION"

    if (
        trend_direction == "BEARISH"
        and structure_direction == "BULLISH"
    ):
        return "BULLISH TRANSITION"

    if range_probability >= 45.0:
        return "RANGE BOUND"

    if reversal_probability > continuation_probability:
        return "CONFLICTING STRUCTURE"

    return "UNCONFIRMED"


# =========================================================
# REGIME SCORE
# =========================================================


def calculate_regime_score(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    continuation_probability: float,
    reversal_probability: float,
    range_probability: float,
) -> tuple[float, Dict[str, float]]:
    """
    Calculate a 0–100 regime score.

    Higher score:
        Stronger bullish environment.

    Lower score:
        Stronger bearish environment.

    Around 50:
        Neutral, ranging or conflicting environment.
    """

    trend_component = (
        clamp(
            trend_result.trend_score
        )
        * 0.35
    )

    confidence_component = (
        clamp(
            confidence_result.confidence_score
        )
        * 0.35
    )

    structure_component = (
        clamp(
            confidence_result.bullish_swing_percent
        )
        * 0.20
    )

    probability_component = (
        continuation_probability * 0.10
    )

    score = (
        trend_component
        + confidence_component
        + structure_component
        + probability_component
    )

    confidence_direction = normalize_direction(
        confidence_result.directional_bias
    )

    if confidence_direction == "BEARISH":
        score = 100.0 - score

    if range_probability >= 45.0:
        score = (
            score + 50.0
        ) / 2.0

    if reversal_probability >= 45.0:
        score = (
            score + 50.0
        ) / 2.0

    score = clamp(score)

    breakdown = {
        "trend_component": round(
            trend_component,
            2,
        ),
        "confidence_component": round(
            confidence_component,
            2,
        ),
        "structure_component": round(
            structure_component,
            2,
        ),
        "probability_component": round(
            probability_component,
            2,
        ),
    }

    return round(score, 2), breakdown


# =========================================================
# SUPPORTING CLASSIFICATIONS
# =========================================================


def classify_regime_strength(
    continuation_probability: float,
    confidence_result: ConfidenceResult,
) -> str:
    """
    Classify regime strength.
    """

    combined_strength = (
        continuation_probability
        + confidence_result.directional_confidence
    ) / 2.0

    if combined_strength >= 75.0:
        return "VERY STRONG"

    if combined_strength >= 60.0:
        return "STRONG"

    if combined_strength >= 45.0:
        return "MODERATE"

    if combined_strength >= 25.0:
        return "WEAK"

    return "VERY WEAK"


def classify_strategy_environment(
    market_regime: str,
) -> str:
    """
    Describe the suitable analytical environment.
    """

    if market_regime in {
        "STRONG BULL TREND",
        "BULL TREND",
    }:
        return "BULLISH TREND FOLLOWING"

    if market_regime in {
        "STRONG BEAR TREND",
        "BEAR TREND",
    }:
        return "BEARISH TREND FOLLOWING"

    if market_regime == "RANGE BOUND":
        return "RANGE / MEAN REVERSION"

    if market_regime in {
        "BULLISH REVERSAL WATCH",
        "BEARISH REVERSAL WATCH",
        "BULLISH TRANSITION",
        "BEARISH TRANSITION",
    }:
        return "WAIT FOR CONFIRMATION"

    return "WAIT"


def classify_risk_state(
    market_regime: str,
    confidence_result: ConfidenceResult,
    reversal_probability: float,
) -> str:
    """
    Classify structural risk.
    """

    if market_regime in {
        "STRONG BULL TREND",
        "STRONG BEAR TREND",
    } and confidence_result.directional_confidence >= 65.0:
        return "LOW"

    if reversal_probability >= 45.0:
        return "HIGH"

    if market_regime in {
        "CONFLICTING STRUCTURE",
        "UNCONFIRMED",
        "BULLISH TRANSITION",
        "BEARISH TRANSITION",
    }:
        return "HIGH"

    return "MODERATE"


# =========================================================
# MAIN ENGINE
# =========================================================


def analyze_market_regime(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    bos_result: Any,
    choch_result: Any,
) -> MarketRegimeResult:
    """
    Run the complete AQSD Market Regime Engine.
    """

    if trend_result is None:
        raise ValueError(
            "trend_result is required."
        )

    if confidence_result is None:
        raise ValueError(
            "confidence_result is required."
        )

    trend_state = classify_trend_state(
        trend_result=trend_result
    )

    structure_state = (
        confidence_result.structure_direction
    )

    break_state = classify_break_state(
        bos_result=bos_result,
        choch_result=choch_result,
    )

    (
        continuation_probability,
        reversal_probability,
        range_probability,
    ) = calculate_probabilities(
        trend_result=trend_result,
        confidence_result=confidence_result,
        bos_result=bos_result,
        choch_result=choch_result,
    )

    market_regime = classify_market_regime(
        trend_result=trend_result,
        confidence_result=confidence_result,
        break_state=break_state,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        range_probability=range_probability,
    )

    (
        regime_score,
        score_breakdown,
    ) = calculate_regime_score(
        trend_result=trend_result,
        confidence_result=confidence_result,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        range_probability=range_probability,
    )

    regime_strength = classify_regime_strength(
        continuation_probability=continuation_probability,
        confidence_result=confidence_result,
    )

    strategy_environment = (
        classify_strategy_environment(
            market_regime=market_regime
        )
    )

    risk_state = classify_risk_state(
        market_regime=market_regime,
        confidence_result=confidence_result,
        reversal_probability=reversal_probability,
    )

    directional_bias = (
        confidence_result.directional_bias
    )

    evidence: List[str] = []

    evidence.append(
        f"Trend state is {trend_state}"
    )

    evidence.append(
        f"Swing structure state is {structure_state}"
    )

    evidence.append(
        f"Structural break state is {break_state}"
    )

    evidence.append(
        "Confidence Score is "
        f"{confidence_result.confidence_score:.2f}/100"
    )

    evidence.append(
        "Directional confidence is "
        f"{confidence_result.directional_confidence:.2f}%"
    )

    evidence.append(
        "Continuation probability is "
        f"{continuation_probability:.2f}%"
    )

    evidence.append(
        "Reversal probability is "
        f"{reversal_probability:.2f}%"
    )

    evidence.append(
        "Range probability is "
        f"{range_probability:.2f}%"
    )

    evidence.append(
        f"Final market regime is {market_regime}"
    )

    evidence.append(
        f"Risk state is {risk_state}"
    )

    return MarketRegimeResult(
        market_regime=market_regime,
        regime_score=regime_score,
        directional_bias=directional_bias,
        regime_strength=regime_strength,
        trend_state=trend_state,
        structure_state=structure_state,
        break_state=break_state,
        continuation_probability=continuation_probability,
        reversal_probability=reversal_probability,
        range_probability=range_probability,
        strategy_environment=strategy_environment,
        risk_state=risk_state,
        score_breakdown=score_breakdown,
        evidence=evidence,
    )