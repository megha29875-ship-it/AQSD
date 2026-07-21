"""
AQSD
Market Structure Engine

Module: phase.py
Version: 1.0
Author: AQSD

Description:
Classifies the current market phase using:

- Trend direction and strength
- Trend Score
- Swing structure
- BOS
- CHOCH
- Confidence
- Market regime

Supported phases:

- ACCUMULATION
- UPTREND
- DISTRIBUTION
- DOWNTREND
- CAPITULATION
- RECOVERY
- UNKNOWN
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from .confidence import ConfidenceResult
from .market_regime import MarketRegimeResult
from .models import (
    MarketPhase,
    TrendDirection,
    TrendResult,
)


# =========================================================
# RESULT MODEL
# =========================================================


@dataclass
class MarketPhaseResult:
    """
    Complete AQSD Market Phase result.
    """

    phase: MarketPhase = MarketPhase.UNKNOWN
    phase_score: float = 50.0
    phase_confidence: float = 0.0

    directional_bias: str = "NEUTRAL"
    transition_state: str = "UNCONFIRMED"
    phase_quality: str = "LOW"

    score_breakdown: Dict[str, float] = field(
        default_factory=dict
    )

    evidence: List[str] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        """
        Validate numerical values.
        """

        self.phase_score = max(
            0.0,
            min(100.0, float(self.phase_score)),
        )

        self.phase_confidence = max(
            0.0,
            min(100.0, float(self.phase_confidence)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the result to a dictionary.
        """

        result = asdict(self)

        result["phase"] = self.phase.value

        return result


# =========================================================
# HELPERS
# =========================================================


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Restrict a numerical value to a defined range.
    """

    return max(
        minimum,
        min(maximum, float(value)),
    )


def enum_text(
    value: Any,
) -> str:
    """
    Convert enum or plain value into uppercase text.
    """

    if value is None:
        return ""

    raw_value = getattr(
        value,
        "value",
        value,
    )

    return str(raw_value).strip().upper()


def object_direction(
    result: Any,
) -> str:
    """
    Read and normalize a direction field from BOS or CHOCH.
    """

    direction = enum_text(
        getattr(
            result,
            "direction",
            "",
        )
    )

    if direction in {
        "BULLISH",
        "BULLISH_BOS",
        "BULLISH_CHOCH",
        "UP",
        "UPWARD",
    }:
        return "BULLISH"

    if direction in {
        "BEARISH",
        "BEARISH_BOS",
        "BEARISH_CHOCH",
        "DOWN",
        "DOWNWARD",
    }:
        return "BEARISH"

    return "NEUTRAL"


def is_detected(
    result: Any,
) -> bool:
    """
    Safely read the detected field.
    """

    return bool(
        getattr(
            result,
            "detected",
            False,
        )
    )


# =========================================================
# PHASE CLASSIFICATION
# =========================================================


def classify_market_phase(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    regime_result: MarketRegimeResult,
    bos_result: Any,
    choch_result: Any,
) -> tuple[MarketPhase, str]:
    """
    Determine the current market phase.

    The classification follows this general cycle:

        ACCUMULATION
            →
        RECOVERY
            →
        UPTREND
            →
        DISTRIBUTION
            →
        DOWNTREND
            →
        CAPITULATION
            →
        ACCUMULATION
    """

    trend_direction = trend_result.direction

    structure_direction = (
        confidence_result.structure_direction
    )

    market_regime = (
        regime_result.market_regime
    )

    bullish_swings = (
        confidence_result.bullish_swing_percent
    )

    bearish_swings = (
        confidence_result.bearish_swing_percent
    )

    bos_detected = is_detected(
        bos_result
    )

    choch_detected = is_detected(
        choch_result
    )

    bos_direction = object_direction(
        bos_result
    )

    choch_direction = object_direction(
        choch_result
    )

    # -----------------------------------------------------
    # Bullish recovery
    # -----------------------------------------------------

    if (
        choch_detected
        and choch_direction == "BULLISH"
    ):
        return (
            MarketPhase.RECOVERY,
            "Bullish CHOCH indicates a possible recovery phase.",
        )

    # -----------------------------------------------------
    # Bearish transition / distribution
    # -----------------------------------------------------

    if (
        choch_detected
        and choch_direction == "BEARISH"
    ):
        return (
            MarketPhase.DISTRIBUTION,
            "Bearish CHOCH indicates possible distribution.",
        )

    # -----------------------------------------------------
    # Confirmed uptrend
    # -----------------------------------------------------

    if (
        trend_direction == TrendDirection.BULLISH
        and structure_direction == "BULLISH"
        and (
            (
                bos_detected
                and bos_direction == "BULLISH"
            )
            or market_regime in {
                "STRONG BULL TREND",
                "BULL TREND",
            }
        )
    ):
        return (
            MarketPhase.UPTREND,
            "Bullish trend and structure confirm an uptrend.",
        )

    # -----------------------------------------------------
    # Developing uptrend
    # -----------------------------------------------------

    if (
        trend_direction == TrendDirection.BULLISH
        and bullish_swings >= 55.0
    ):
        return (
            MarketPhase.RECOVERY,
            "Bullish trend is developing before full structural confirmation.",
        )

    # -----------------------------------------------------
    # Confirmed downtrend
    # -----------------------------------------------------

    if (
        trend_direction == TrendDirection.BEARISH
        and structure_direction == "BEARISH"
        and (
            (
                bos_detected
                and bos_direction == "BEARISH"
            )
            or market_regime in {
                "STRONG BEAR TREND",
                "BEAR TREND",
            }
        )
    ):
        return (
            MarketPhase.DOWNTREND,
            "Bearish trend and structure confirm a downtrend.",
        )

    # -----------------------------------------------------
    # Capitulation
    # -----------------------------------------------------

    if (
        trend_direction == TrendDirection.BEARISH
        and bearish_swings >= 75.0
        and confidence_result.directional_confidence >= 65.0
    ):
        return (
            MarketPhase.CAPITULATION,
            "Strong bearish structure indicates possible capitulation.",
        )

    # -----------------------------------------------------
    # Accumulation
    # -----------------------------------------------------

    if (
        market_regime == "RANGE BOUND"
        and bullish_swings >= 45.0
        and bearish_swings >= 45.0
        and trend_result.trend_score >= 45.0
    ):
        return (
            MarketPhase.ACCUMULATION,
            "Balanced structure with stabilising trend suggests accumulation.",
        )

    # -----------------------------------------------------
    # Distribution
    # -----------------------------------------------------

    if (
        trend_direction == TrendDirection.BULLISH
        and structure_direction == "BEARISH"
    ):
        return (
            MarketPhase.DISTRIBUTION,
            "Bullish trend with weakening structure suggests distribution.",
        )

    # -----------------------------------------------------
    # Weak bullish state
    # -----------------------------------------------------

    if market_regime == "WEAK BULL TREND":
        return (
            MarketPhase.RECOVERY,
            "Weak bullish regime suggests recovery without confirmation.",
        )

    # -----------------------------------------------------
    # Weak bearish state
    # -----------------------------------------------------

    if market_regime == "WEAK BEAR TREND":
        return (
            MarketPhase.DOWNTREND,
            "Weak bearish regime suggests an early downtrend.",
        )

    return (
        MarketPhase.UNKNOWN,
        "Available evidence does not confirm a recognised market phase.",
    )


# =========================================================
# PHASE SCORE
# =========================================================


def calculate_phase_score(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    regime_result: MarketRegimeResult,
) -> tuple[float, Dict[str, float]]:
    """
    Calculate a directional Market Phase Score.

    Higher values:
        More bullish phase.

    Lower values:
        More bearish phase.

    Values near 50:
        Accumulation, distribution or transition.
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
        * 0.30
    )

    structure_component = (
        clamp(
            confidence_result.bullish_swing_percent
        )
        * 0.20
    )

    regime_component = (
        clamp(
            regime_result.regime_score
        )
        * 0.15
    )

    phase_score = (
        trend_component
        + confidence_component
        + structure_component
        + regime_component
    )

    phase_score = clamp(
        phase_score
    )

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
        "regime_component": round(
            regime_component,
            2,
        ),
    }

    return (
        round(phase_score, 2),
        breakdown,
    )


# =========================================================
# SUPPORTING CLASSIFICATIONS
# =========================================================


def calculate_phase_confidence(
    confidence_result: ConfidenceResult,
    regime_result: MarketRegimeResult,
) -> float:
    """
    Calculate confidence in the phase classification.
    """

    regime_strength_map = {
        "VERY STRONG": 90.0,
        "STRONG": 75.0,
        "MODERATE": 55.0,
        "WEAK": 35.0,
        "VERY WEAK": 20.0,
    }

    regime_strength_score = (
        regime_strength_map.get(
            regime_result.regime_strength,
            35.0,
        )
    )

    phase_confidence = (
        confidence_result.directional_confidence
        * 0.60
        + regime_strength_score
        * 0.40
    )

    return round(
        clamp(phase_confidence),
        2,
    )


def classify_phase_quality(
    phase_confidence: float,
) -> str:
    """
    Classify confidence in the phase result.
    """

    if phase_confidence >= 80.0:
        return "VERY HIGH"

    if phase_confidence >= 65.0:
        return "HIGH"

    if phase_confidence >= 45.0:
        return "MODERATE"

    if phase_confidence >= 25.0:
        return "LOW"

    return "VERY LOW"


def classify_transition_state(
    phase: MarketPhase,
) -> str:
    """
    Describe whether the phase is established or transitional.
    """

    if phase in {
        MarketPhase.UPTREND,
        MarketPhase.DOWNTREND,
    }:
        return "ESTABLISHED"

    if phase in {
        MarketPhase.RECOVERY,
        MarketPhase.DISTRIBUTION,
    }:
        return "TRANSITION"

    if phase in {
        MarketPhase.ACCUMULATION,
        MarketPhase.CAPITULATION,
    }:
        return "POTENTIAL TURNING PHASE"

    return "UNCONFIRMED"


# =========================================================
# MAIN ENGINE
# =========================================================


def analyze_market_phase(
    trend_result: TrendResult,
    confidence_result: ConfidenceResult,
    regime_result: MarketRegimeResult,
    bos_result: Any,
    choch_result: Any,
) -> MarketPhaseResult:
    """
    Run the complete AQSD Market Phase Engine.
    """

    if trend_result is None:
        raise ValueError(
            "trend_result is required."
        )

    if confidence_result is None:
        raise ValueError(
            "confidence_result is required."
        )

    if regime_result is None:
        raise ValueError(
            "regime_result is required."
        )

    phase, phase_reason = classify_market_phase(
        trend_result=trend_result,
        confidence_result=confidence_result,
        regime_result=regime_result,
        bos_result=bos_result,
        choch_result=choch_result,
    )

    (
        phase_score,
        score_breakdown,
    ) = calculate_phase_score(
        trend_result=trend_result,
        confidence_result=confidence_result,
        regime_result=regime_result,
    )

    phase_confidence = calculate_phase_confidence(
        confidence_result=confidence_result,
        regime_result=regime_result,
    )

    phase_quality = classify_phase_quality(
        phase_confidence=phase_confidence
    )

    transition_state = classify_transition_state(
        phase=phase
    )

    evidence = [
        phase_reason,
        (
            "Trend direction is "
            f"{trend_result.direction.value}"
        ),
        (
            "Trend Score is "
            f"{trend_result.trend_score:.2f}/100"
        ),
        (
            "Swing structure is "
            f"{confidence_result.structure_direction}"
        ),
        (
            "Bullish swings are "
            f"{confidence_result.bullish_swing_percent:.2f}%"
        ),
        (
            "Market regime is "
            f"{regime_result.market_regime}"
        ),
        (
            "Phase confidence is "
            f"{phase_confidence:.2f}%"
        ),
    ]

    return MarketPhaseResult(
        phase=phase,
        phase_score=phase_score,
        phase_confidence=phase_confidence,
        directional_bias=(
            confidence_result.directional_bias
        ),
        transition_state=transition_state,
        phase_quality=phase_quality,
        score_breakdown=score_breakdown,
        evidence=evidence,
    )