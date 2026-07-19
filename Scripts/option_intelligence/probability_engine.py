"""
AQSD
Option Intelligence

Module: probability_engine.py
Version: 1.0
Author: AQSD

Description:
Combines OI, PCR, Max Pain, Wall and Volatility intelligence
into transparent, normalized probability scores.

Important:
- Bullish Probability + Bearish Probability = 100%
- Continuation Probability + Reversal Probability = 100%
- The engine uses rule-based evidence scoring.
- Scores are analytical estimates, not guaranteed outcomes.

Outputs:
- Bullish Probability
- Bearish Probability
- Continuation Probability
- Reversal Probability
- Institutional Bull Score
- Institutional Bear Score
- Confidence Score
- Trade Grade
- Directional Bias
- Suggested Action
- Evidence Table
- Human-readable Interpretation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)


# ============================================================
# CONFIGURATION
# ============================================================

DIRECTIONAL_WEIGHT_OI = 25.0
DIRECTIONAL_WEIGHT_PCR = 25.0
DIRECTIONAL_WEIGHT_WALLS = 20.0
DIRECTIONAL_WEIGHT_MAX_PAIN = 15.0
DIRECTIONAL_WEIGHT_VOLATILITY = 15.0

CONTINUATION_WEIGHT_PCR_TREND = 25.0
CONTINUATION_WEIGHT_WALL_SHIFT = 25.0
CONTINUATION_WEIGHT_VOLATILITY = 20.0
CONTINUATION_WEIGHT_POSITIONING = 15.0
CONTINUATION_WEIGHT_EXTREMES = 15.0

MINIMUM_PROBABILITY = 5.0
MAXIMUM_PROBABILITY = 95.0


# ============================================================
# INPUT DATA MODEL
# ============================================================

@dataclass(slots=True)
class ProbabilityInputs:
    """
    Consolidated analytics inputs for the Probability Engine.

    All fields are optional so the engine can still run when one
    analytics module has insufficient data.
    """

    spot_price: float

    # OI Engine
    oi_pcr: float | None = None
    change_oi_pcr: float | None = None
    oi_imbalance: float | None = None
    oi_market_bias: str | None = None
    oi_build_up_signal: str | None = None

    # PCR Engine
    modified_pcr: float | None = None
    atm_zone_pcr: float | None = None
    pcr_trend: str | None = None
    pcr_bias: str | None = None
    reversal_watch: str | None = None

    # Max Pain Engine
    max_pain_strike: float | None = None
    expiry_bias: str | None = None
    pinning_probability: float | None = None
    magnet_strength: str | None = None
    pain_shift: str | None = None

    # Wall Engine
    positional_call_wall: float | None = None
    positional_put_wall: float | None = None
    fresh_call_wall: float | None = None
    fresh_put_wall: float | None = None
    combined_wall_shift: str | None = None
    range_bias: str | None = None
    breakout_watch: str | None = None
    breakdown_watch: str | None = None

    # Volatility Engine
    atm_iv: float | None = None
    historical_volatility: float | None = None
    iv_rank: float | None = None
    iv_percentile: float | None = None
    iv_hv_spread: float | None = None
    volatility_trend: str | None = None
    volatility_regime: str | None = None
    volatility_signal: str | None = None
    skew_signal: str | None = None


# ============================================================
# OUTPUT DATA MODEL
# ============================================================

@dataclass(slots=True)
class ProbabilityResult:
    """
    Final AQSD Probability Engine result.
    """

    bullish_probability: float
    bearish_probability: float

    continuation_probability: float
    reversal_probability: float

    institutional_bull_score: float
    institutional_bear_score: float

    directional_edge: float
    confidence_score: float

    directional_bias: str
    market_regime: str
    suggested_action: str
    trade_grade: str
    trade_quality: str

    bullish_evidence_count: int
    bearish_evidence_count: int
    neutral_evidence_count: int

    continuation_evidence_count: int
    reversal_evidence_count: int

    interpretation: str
    timestamp: str


# ============================================================
# EVIDENCE MODEL
# ============================================================

@dataclass(slots=True)
class Evidence:
    """
    One transparent scoring contribution.
    """

    category: str
    indicator: str
    reading: str
    direction: str

    bullish_score: float
    bearish_score: float

    continuation_score: float
    reversal_score: float

    weight: float
    explanation: str


# ============================================================
# GENERIC HELPERS
# ============================================================

def clean_text(
    value: str | None,
) -> str:
    """
    Normalize optional text for comparisons.
    """

    if value is None:
        return ""

    return str(value).strip().upper()


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Restrict a numeric value to a range.
    """

    return min(
        maximum,
        max(
            minimum,
            float(value),
        ),
    )


def normalized_pair(
    first_score: float,
    second_score: float,
    minimum_probability: float = MINIMUM_PROBABILITY,
    maximum_probability: float = MAXIMUM_PROBABILITY,
) -> tuple[float, float]:
    """
    Convert two raw scores into normalized probabilities totaling 100%.
    """

    first = max(
        0.0,
        float(first_score),
    )

    second = max(
        0.0,
        float(second_score),
    )

    total = first + second

    if total == 0:
        return 50.0, 50.0

    first_probability = (
        first
        / total
        * 100.0
    )

    first_probability = clamp(
        first_probability,
        minimum_probability,
        maximum_probability,
    )

    second_probability = (
        100.0
        - first_probability
    )

    return (
        round(
            first_probability,
            2,
        ),
        round(
            second_probability,
            2,
        ),
    )


def directional_score_from_ratio(
    ratio: float | None,
    bullish_level: float,
    bearish_level: float,
) -> tuple[float, float, str]:
    """
    Convert a Put-Call-style ratio into bullish and bearish evidence.
    """

    if ratio is None:
        return 0.0, 0.0, "NO DATA"

    if ratio >= bullish_level + 0.30:
        return 1.0, 0.0, "STRONGLY BULLISH"

    if ratio >= bullish_level:
        return 0.75, 0.10, "BULLISH"

    if ratio <= bearish_level - 0.20:
        return 0.0, 1.0, "STRONGLY BEARISH"

    if ratio <= bearish_level:
        return 0.10, 0.75, "BEARISH"

    return 0.30, 0.30, "NEUTRAL"


def format_optional(
    value: Any,
) -> str:
    """
    Format optional evidence values.
    """

    if value is None:
        return "N/A"

    if isinstance(
        value,
        float,
    ):
        return f"{value:.3f}"

    return str(value)


# ============================================================
# OI EVIDENCE
# ============================================================

def build_oi_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build directional evidence from OI analytics.
    """

    evidence: list[Evidence] = []

    bull, bear, direction = (
        directional_score_from_ratio(
            ratio=inputs.oi_pcr,
            bullish_level=1.10,
            bearish_level=0.80,
        )
    )

    evidence.append(
        Evidence(
            category="OI",
            indicator="OI PCR",
            reading=format_optional(
                inputs.oi_pcr
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=10.0,
            explanation=(
                "Higher Put OI relative to Call OI supports "
                "bullish positioning; lower PCR supports bearish positioning."
            ),
        )
    )

    bull, bear, direction = (
        directional_score_from_ratio(
            ratio=inputs.change_oi_pcr,
            bullish_level=1.15,
            bearish_level=0.75,
        )
    )

    evidence.append(
        Evidence(
            category="OI",
            indicator="Change-in-OI PCR",
            reading=format_optional(
                inputs.change_oi_pcr
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=10.0,
            explanation=(
                "Fresh Put-side OI supports bullish evidence, while "
                "fresh Call-side dominance supports bearish evidence."
            ),
        )
    )

    imbalance = inputs.oi_imbalance

    if imbalance is None:
        bull = 0.0
        bear = 0.0
        direction = "NO DATA"

    elif imbalance >= 10.0:
        bull = 0.80
        bear = 0.05
        direction = "BULLISH"

    elif imbalance <= -10.0:
        bull = 0.05
        bear = 0.80
        direction = "BEARISH"

    else:
        bull = 0.25
        bear = 0.25
        direction = "NEUTRAL"

    evidence.append(
        Evidence(
            category="OI",
            indicator="OI Imbalance",
            reading=format_optional(
                imbalance
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=5.0,
            explanation=(
                "Positive imbalance indicates relatively stronger Put OI; "
                "negative imbalance indicates relatively stronger Call OI."
            ),
        )
    )

    return evidence


# ============================================================
# PCR EVIDENCE
# ============================================================

def build_pcr_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build evidence from PCR analytics.
    """

    evidence: list[Evidence] = []

    bull, bear, direction = (
        directional_score_from_ratio(
            ratio=inputs.modified_pcr,
            bullish_level=1.10,
            bearish_level=0.80,
        )
    )

    evidence.append(
        Evidence(
            category="PCR",
            indicator="Modified PCR",
            reading=format_optional(
                inputs.modified_pcr
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=15.0,
            explanation=(
                "Modified PCR combines OI, fresh OI and volume positioning."
            ),
        )
    )

    bull, bear, direction = (
        directional_score_from_ratio(
            ratio=inputs.atm_zone_pcr,
            bullish_level=1.10,
            bearish_level=0.85,
        )
    )

    evidence.append(
        Evidence(
            category="PCR",
            indicator="ATM-Zone PCR",
            reading=format_optional(
                inputs.atm_zone_pcr
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=10.0,
            explanation=(
                "Near-ATM positioning is more relevant to immediate "
                "directional pressure."
            ),
        )
    )

    trend = clean_text(
        inputs.pcr_trend
    )

    if trend == "RISING":
        continuation = 0.75
        reversal = 0.15
        direction = "CONTINUATION"

    elif trend == "FALLING":
        continuation = 0.75
        reversal = 0.15
        direction = "CONTINUATION"

    elif trend == "FLAT":
        continuation = 0.30
        reversal = 0.30
        direction = "NEUTRAL"

    else:
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="PCR",
            indicator="PCR Trend",
            reading=format_optional(
                inputs.pcr_trend
            ),
            direction=direction,
            bullish_score=0.0,
            bearish_score=0.0,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=CONTINUATION_WEIGHT_PCR_TREND,
            explanation=(
                "A persistent PCR trend supports continuation; "
                "flat PCR provides weaker directional confirmation."
            ),
        )
    )

    reversal_watch = clean_text(
        inputs.reversal_watch
    )

    if (
        "REVERSAL WATCH"
        in reversal_watch
    ):
        continuation = 0.10
        reversal = 1.0
        direction = "REVERSAL"

    elif reversal_watch:
        continuation = 0.45
        reversal = 0.20
        direction = "NO EXTREME"

    else:
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="PCR",
            indicator="PCR Extreme",
            reading=format_optional(
                inputs.reversal_watch
            ),
            direction=direction,
            bullish_score=0.0,
            bearish_score=0.0,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=CONTINUATION_WEIGHT_EXTREMES,
            explanation=(
                "Extreme PCR conditions increase contrarian reversal risk."
            ),
        )
    )

    return evidence


# ============================================================
# MAX PAIN EVIDENCE
# ============================================================

def build_max_pain_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build evidence from Max Pain analytics.
    """

    evidence: list[Evidence] = []

    expiry_bias = clean_text(
        inputs.expiry_bias
    )

    pinning_probability = (
        inputs.pinning_probability
        if inputs.pinning_probability is not None
        else 0.0
    )

    pin_weight = clamp(
        pinning_probability
        / 100.0,
        0.0,
        1.0,
    )

    if "BULLISH" in expiry_bias:
        bull = pin_weight
        bear = 0.05
        direction = "BULLISH"

    elif "BEARISH" in expiry_bias:
        bull = 0.05
        bear = pin_weight
        direction = "BEARISH"

    elif "NEUTRAL" in expiry_bias:
        bull = 0.25
        bear = 0.25
        direction = "NEUTRAL"

    else:
        bull = 0.0
        bear = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="MAX PAIN",
            indicator="Expiry Bias",
            reading=format_optional(
                inputs.expiry_bias
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=DIRECTIONAL_WEIGHT_MAX_PAIN,
            explanation=(
                "Max Pain above spot creates upward expiry pull; "
                "Max Pain below spot creates downward expiry pull."
            ),
        )
    )

    magnet = clean_text(
        inputs.magnet_strength
    )

    if magnet in {
        "VERY STRONG",
        "STRONG",
    }:
        continuation = 0.25
        reversal = 0.75
        direction = "PINNING / MEAN REVERSION"

    elif magnet == "MODERATE":
        continuation = 0.35
        reversal = 0.45
        direction = "MODERATE PINNING"

    elif magnet:
        continuation = 0.50
        reversal = 0.20
        direction = "WEAK PINNING"

    else:
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="MAX PAIN",
            indicator="Magnet Strength",
            reading=format_optional(
                inputs.magnet_strength
            ),
            direction=direction,
            bullish_score=0.0,
            bearish_score=0.0,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=10.0,
            explanation=(
                "Stronger pinning increases the chance of movement "
                "back toward Max Pain rather than clean continuation."
            ),
        )
    )

    return evidence


# ============================================================
# WALL EVIDENCE
# ============================================================

def build_wall_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build evidence from option wall analytics.
    """

    evidence: list[Evidence] = []

    call_wall = inputs.positional_call_wall
    put_wall = inputs.positional_put_wall
    spot = inputs.spot_price

    if (
        call_wall is not None
        and put_wall is not None
        and call_wall > put_wall
    ):
        range_width = (
            call_wall
            - put_wall
        )

        location = (
            spot
            - put_wall
        ) / range_width

        if location >= 0.70:
            bull = 0.25
            bear = 0.75
            direction = "NEAR CALL RESISTANCE"

        elif location <= 0.30:
            bull = 0.75
            bear = 0.25
            direction = "NEAR PUT SUPPORT"

        else:
            bull = 0.35
            bear = 0.35
            direction = "MID-RANGE"

    else:
        bull = 0.0
        bear = 0.0
        direction = "NO VALID RANGE"

    evidence.append(
        Evidence(
            category="WALLS",
            indicator="Spot in Wall Range",
            reading=direction,
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=10.0,
            explanation=(
                "Put Walls provide support and Call Walls provide resistance."
            ),
        )
    )

    wall_shift = clean_text(
        inputs.combined_wall_shift
    )

    if wall_shift == "RANGE SHIFTED UP":
        bull = 0.85
        bear = 0.05
        continuation = 0.80
        reversal = 0.10
        direction = "BULLISH CONTINUATION"

    elif wall_shift == "RANGE SHIFTED DOWN":
        bull = 0.05
        bear = 0.85
        continuation = 0.80
        reversal = 0.10
        direction = "BEARISH CONTINUATION"

    elif wall_shift == "RANGE EXPANSION":
        bull = 0.35
        bear = 0.35
        continuation = 0.70
        reversal = 0.20
        direction = "RANGE EXPANSION"

    elif wall_shift == "RANGE COMPRESSION":
        bull = 0.30
        bear = 0.30
        continuation = 0.20
        reversal = 0.70
        direction = "COMPRESSION"

    elif wall_shift == "STABLE RANGE":
        bull = 0.30
        bear = 0.30
        continuation = 0.35
        reversal = 0.35
        direction = "STABLE"

    else:
        bull = 0.0
        bear = 0.0
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="WALLS",
            indicator="Combined Wall Shift",
            reading=format_optional(
                inputs.combined_wall_shift
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=10.0,
            explanation=(
                "Coordinated movement of Call and Put Walls indicates "
                "whether the expected trading range is migrating."
            ),
        )
    )

    breakout = clean_text(
        inputs.breakout_watch
    )

    breakdown = clean_text(
        inputs.breakdown_watch
    )

    if "BREAKOUT ACTIVE" in breakout:
        bull = 1.0
        bear = 0.0
        continuation = 0.85
        reversal = 0.15
        direction = "BULLISH BREAKOUT"

    elif "BREAKDOWN ACTIVE" in breakdown:
        bull = 0.0
        bear = 1.0
        continuation = 0.85
        reversal = 0.15
        direction = "BEARISH BREAKDOWN"

    elif (
        "VERY CLOSE" in breakout
        or "TEST APPROACHING" in breakout
    ):
        bull = 0.40
        bear = 0.55
        continuation = 0.40
        reversal = 0.55
        direction = "CALL WALL TEST"

    elif (
        "VERY CLOSE" in breakdown
        or "TEST APPROACHING" in breakdown
    ):
        bull = 0.55
        bear = 0.40
        continuation = 0.40
        reversal = 0.55
        direction = "PUT WALL TEST"

    else:
        bull = 0.20
        bear = 0.20
        continuation = 0.30
        reversal = 0.25
        direction = "NO ACTIVE BREAK"

    evidence.append(
        Evidence(
            category="WALLS",
            indicator="Breakout / Breakdown",
            reading=(
                f"{inputs.breakout_watch} | "
                f"{inputs.breakdown_watch}"
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=CONTINUATION_WEIGHT_WALL_SHIFT,
            explanation=(
                "Confirmed movement beyond a major option wall supports "
                "continuation; an approaching wall increases rejection risk."
            ),
        )
    )

    return evidence


# ============================================================
# VOLATILITY EVIDENCE
# ============================================================

def build_volatility_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build evidence from volatility analytics.
    """

    evidence: list[Evidence] = []

    skew = clean_text(
        inputs.skew_signal
    )

    if "DOWNSIDE HEDGE" in skew:
        bull = 0.10
        bear = 0.70
        direction = "BEARISH HEDGE DEMAND"

    elif "UPSIDE SPECULATION" in skew:
        bull = 0.70
        bear = 0.10
        direction = "BULLISH SPECULATION"

    elif "BALANCED" in skew:
        bull = 0.30
        bear = 0.30
        direction = "BALANCED"

    else:
        bull = 0.0
        bear = 0.0
        direction = "NO DATA"

    evidence.append(
        Evidence(
            category="VOLATILITY",
            indicator="IV Skew",
            reading=format_optional(
                inputs.skew_signal
            ),
            direction=direction,
            bullish_score=bull,
            bearish_score=bear,
            continuation_score=0.0,
            reversal_score=0.0,
            weight=10.0,
            explanation=(
                "Put IV above Call IV indicates downside hedge demand; "
                "Call IV above Put IV indicates upside speculation."
            ),
        )
    )

    trend = clean_text(
        inputs.volatility_trend
    )

    regime = clean_text(
        inputs.volatility_regime
    )

    if trend == "RISING":
        continuation = 0.75
        reversal = 0.25
        direction = "VOLATILITY EXPANSION"

    elif trend == "FALLING":
        continuation = 0.35
        reversal = 0.55
        direction = "VOLATILITY CONTRACTION"

    elif trend == "FLAT":
        continuation = 0.35
        reversal = 0.35
        direction = "FLAT"

    else:
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    if regime == "EXTREME VOLATILITY":
        reversal += 0.25

    elif regime == "LOW VOLATILITY":
        continuation += 0.15

    evidence.append(
        Evidence(
            category="VOLATILITY",
            indicator="Volatility Trend / Regime",
            reading=(
                f"{inputs.volatility_trend} | "
                f"{inputs.volatility_regime}"
            ),
            direction=direction,
            bullish_score=0.0,
            bearish_score=0.0,
            continuation_score=clamp(
                continuation,
                0.0,
                1.0,
            ),
            reversal_score=clamp(
                reversal,
                0.0,
                1.0,
            ),
            weight=CONTINUATION_WEIGHT_VOLATILITY,
            explanation=(
                "Rising volatility confirms directional expansion, while "
                "extreme volatility increases exhaustion and reversal risk."
            ),
        )
    )

    iv_rank = inputs.iv_rank

    if iv_rank is None:
        continuation = 0.0
        reversal = 0.0
        direction = "NO DATA"

    elif iv_rank >= 80.0:
        continuation = 0.25
        reversal = 0.85
        direction = "EXTREME IV"

    elif iv_rank >= 50.0:
        continuation = 0.55
        reversal = 0.40
        direction = "ELEVATED IV"

    elif iv_rank <= 20.0:
        continuation = 0.65
        reversal = 0.20
        direction = "LOW IV"

    else:
        continuation = 0.45
        reversal = 0.35
        direction = "NORMAL IV"

    evidence.append(
        Evidence(
            category="VOLATILITY",
            indicator="IV Rank",
            reading=format_optional(
                inputs.iv_rank
            ),
            direction=direction,
            bullish_score=0.0,
            bearish_score=0.0,
            continuation_score=continuation,
            reversal_score=reversal,
            weight=10.0,
            explanation=(
                "Extreme IV Rank increases exhaustion risk; low IV Rank "
                "provides more room for expansion."
            ),
        )
    )

    return evidence


# ============================================================
# AGGREGATION
# ============================================================

def build_all_evidence(
    inputs: ProbabilityInputs,
) -> list[Evidence]:
    """
    Build the complete evidence set.
    """

    evidence: list[Evidence] = []

    evidence.extend(
        build_oi_evidence(inputs)
    )

    evidence.extend(
        build_pcr_evidence(inputs)
    )

    evidence.extend(
        build_max_pain_evidence(inputs)
    )

    evidence.extend(
        build_wall_evidence(inputs)
    )

    evidence.extend(
        build_volatility_evidence(inputs)
    )

    return evidence


def evidence_to_dataframe(
    evidence: list[Evidence],
) -> pd.DataFrame:
    """
    Convert evidence objects into a detailed table.
    """

    rows = [
        {
            "category": item.category,
            "indicator": item.indicator,
            "reading": item.reading,
            "direction": item.direction,
            "weight": item.weight,
            "bullish_contribution": (
                item.bullish_score
                * item.weight
            ),
            "bearish_contribution": (
                item.bearish_score
                * item.weight
            ),
            "continuation_contribution": (
                item.continuation_score
                * item.weight
            ),
            "reversal_contribution": (
                item.reversal_score
                * item.weight
            ),
            "explanation": item.explanation,
        }
        for item in evidence
    ]

    return pd.DataFrame(rows)


def determine_directional_bias(
    bullish_probability: float,
    bearish_probability: float,
) -> str:
    """
    Classify the directional probability difference.
    """

    difference = (
        bullish_probability
        - bearish_probability
    )

    if difference >= 30.0:
        return "STRONGLY BULLISH"

    if difference >= 12.0:
        return "BULLISH"

    if difference <= -30.0:
        return "STRONGLY BEARISH"

    if difference <= -12.0:
        return "BEARISH"

    return "NEUTRAL"


def determine_market_regime(
    continuation_probability: float,
    reversal_probability: float,
) -> str:
    """
    Classify continuation versus reversal conditions.
    """

    difference = (
        continuation_probability
        - reversal_probability
    )

    if difference >= 20.0:
        return "TRENDING"

    if difference <= -20.0:
        return "REVERSAL-PRONE"

    return "MIXED / RANGE-BOUND"


def determine_suggested_action(
    directional_bias: str,
    confidence_score: float,
) -> str:
    """
    Produce a conservative analytical action label.
    """

    if confidence_score < 55.0:
        return "WAIT"

    if directional_bias in {
        "STRONGLY BULLISH",
        "BULLISH",
    }:
        return "BUY BIAS"

    if directional_bias in {
        "STRONGLY BEARISH",
        "BEARISH",
    }:
        return "SELL BIAS"

    return "WAIT"


def determine_trade_grade(
    confidence_score: float,
    directional_edge: float,
) -> str:
    """
    Convert confidence and directional edge into a trade grade.
    """

    if (
        confidence_score >= 85.0
        and directional_edge >= 35.0
    ):
        return "A+"

    if (
        confidence_score >= 75.0
        and directional_edge >= 25.0
    ):
        return "A"

    if (
        confidence_score >= 68.0
        and directional_edge >= 18.0
    ):
        return "B+"

    if (
        confidence_score >= 60.0
        and directional_edge >= 12.0
    ):
        return "B"

    if confidence_score >= 50.0:
        return "C"

    return "D"


def determine_trade_quality(
    trade_grade: str,
) -> str:
    """
    Describe the trade grade.
    """

    quality_map = {
        "A+": "EXCEPTIONAL",
        "A": "HIGH",
        "B+": "GOOD",
        "B": "MODERATE",
        "C": "LOW",
        "D": "AVOID",
    }

    return quality_map.get(
        trade_grade,
        "UNKNOWN",
    )


def calculate_confidence_score(
    bullish_probability: float,
    bearish_probability: float,
    evidence_table: pd.DataFrame,
) -> float:
    """
    Calculate confidence from directional edge and evidence coverage.
    """

    directional_edge = abs(
        bullish_probability
        - bearish_probability
    )

    if evidence_table.empty:
        return 0.0

    directional_rows = evidence_table[
        (
            evidence_table["bullish_contribution"] > 0
        )
        | (
            evidence_table["bearish_contribution"] > 0
        )
    ]

    if directional_rows.empty:
        coverage_score = 0.0

    else:
        maximum_weight = float(
            directional_rows["weight"].sum()
        )

        active_weight = float(
            directional_rows.loc[
                directional_rows["direction"]
                != "NO DATA",
                "weight",
            ].sum()
        )

        coverage_score = (
            active_weight
            / maximum_weight
            * 100.0
            if maximum_weight > 0
            else 0.0
        )

    confidence = (
        directional_edge * 0.70
        + coverage_score * 0.30
    )

    return round(
        clamp(
            confidence,
            0.0,
            100.0,
        ),
        2,
    )


# ============================================================
# INTERPRETATION
# ============================================================

def build_interpretation(
    result: ProbabilityResult,
) -> str:
    """
    Build the final Probability Engine interpretation.
    """

    observations: list[str] = []

    observations.append(
        f"Directional evidence is "
        f"{result.directional_bias.lower()}, with "
        f"{result.bullish_probability:.1f}% bullish probability "
        f"and {result.bearish_probability:.1f}% bearish probability."
    )

    observations.append(
        f"The market regime is "
        f"{result.market_regime.lower()}, with "
        f"{result.continuation_probability:.1f}% continuation probability "
        f"and {result.reversal_probability:.1f}% reversal probability."
    )

    observations.append(
        f"Model confidence is "
        f"{result.confidence_score:.1f}%."
    )

    observations.append(
        f"The resulting analytical grade is "
        f"{result.trade_grade} "
        f"({result.trade_quality.lower()} quality)."
    )

    observations.append(
        f"Suggested action: "
        f"{result.suggested_action.lower()}."
    )

    return " ".join(
        observations
    )


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_probability(
    inputs: ProbabilityInputs,
    timestamp: str,
) -> tuple[
    ProbabilityResult,
    pd.DataFrame,
]:
    """
    Run the AQSD Probability Engine.
    """

    evidence = build_all_evidence(
        inputs
    )

    evidence_table = evidence_to_dataframe(
        evidence
    )

    bullish_raw = float(
        evidence_table[
            "bullish_contribution"
        ].sum()
    )

    bearish_raw = float(
        evidence_table[
            "bearish_contribution"
        ].sum()
    )

    continuation_raw = float(
        evidence_table[
            "continuation_contribution"
        ].sum()
    )

    reversal_raw = float(
        evidence_table[
            "reversal_contribution"
        ].sum()
    )

    (
        bullish_probability,
        bearish_probability,
    ) = normalized_pair(
        bullish_raw,
        bearish_raw,
    )

    (
        continuation_probability,
        reversal_probability,
    ) = normalized_pair(
        continuation_raw,
        reversal_raw,
    )

    directional_edge = round(
        abs(
            bullish_probability
            - bearish_probability
        ),
        2,
    )

    confidence_score = (
        calculate_confidence_score(
            bullish_probability=bullish_probability,
            bearish_probability=bearish_probability,
            evidence_table=evidence_table,
        )
    )

    directional_bias = (
        determine_directional_bias(
            bullish_probability=bullish_probability,
            bearish_probability=bearish_probability,
        )
    )

    market_regime = (
        determine_market_regime(
            continuation_probability=continuation_probability,
            reversal_probability=reversal_probability,
        )
    )

    suggested_action = (
        determine_suggested_action(
            directional_bias=directional_bias,
            confidence_score=confidence_score,
        )
    )

    trade_grade = determine_trade_grade(
        confidence_score=confidence_score,
        directional_edge=directional_edge,
    )

    trade_quality = (
        determine_trade_quality(
            trade_grade
        )
    )

    direction_series = evidence_table[
        "direction"
    ].astype(str)

    bullish_evidence_count = int(
        direction_series.str.contains(
            "BULLISH",
            case=False,
            na=False,
        ).sum()
    )

    bearish_evidence_count = int(
        direction_series.str.contains(
            "BEARISH",
            case=False,
            na=False,
        ).sum()
    )

    neutral_evidence_count = int(
        direction_series.str.contains(
            "NEUTRAL|BALANCED|STABLE",
            case=False,
            na=False,
            regex=True,
        ).sum()
    )

    continuation_evidence_count = int(
        (
            evidence_table[
                "continuation_contribution"
            ]
            > evidence_table[
                "reversal_contribution"
            ]
        ).sum()
    )

    reversal_evidence_count = int(
        (
            evidence_table[
                "reversal_contribution"
            ]
            > evidence_table[
                "continuation_contribution"
            ]
        ).sum()
    )

    result = ProbabilityResult(
        bullish_probability=(
            bullish_probability
        ),
        bearish_probability=(
            bearish_probability
        ),
        continuation_probability=(
            continuation_probability
        ),
        reversal_probability=(
            reversal_probability
        ),
        institutional_bull_score=round(
            bullish_raw,
            2,
        ),
        institutional_bear_score=round(
            bearish_raw,
            2,
        ),
        directional_edge=directional_edge,
        confidence_score=confidence_score,
        directional_bias=directional_bias,
        market_regime=market_regime,
        suggested_action=suggested_action,
        trade_grade=trade_grade,
        trade_quality=trade_quality,
        bullish_evidence_count=(
            bullish_evidence_count
        ),
        bearish_evidence_count=(
            bearish_evidence_count
        ),
        neutral_evidence_count=(
            neutral_evidence_count
        ),
        continuation_evidence_count=(
            continuation_evidence_count
        ),
        reversal_evidence_count=(
            reversal_evidence_count
        ),
        interpretation="",
        timestamp=timestamp,
    )

    result.interpretation = (
        build_interpretation(
            result
        )
    )

    return result, evidence_table


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def print_probability_summary(
    result: ProbabilityResult,
) -> None:
    """
    Print probability intelligence in the terminal.
    """

    separator = "=" * 76

    print()
    print(separator)
    print(
        "AQSD OPTION INTELLIGENCE — PROBABILITY ENGINE"
    )
    print(separator)

    print(
        f"Bullish Probability        : "
        f"{result.bullish_probability:.2f}%"
    )

    print(
        f"Bearish Probability        : "
        f"{result.bearish_probability:.2f}%"
    )

    print(
        f"Continuation Probability   : "
        f"{result.continuation_probability:.2f}%"
    )

    print(
        f"Reversal Probability       : "
        f"{result.reversal_probability:.2f}%"
    )

    print(
        f"Institutional Bull Score   : "
        f"{result.institutional_bull_score:.2f}"
    )

    print(
        f"Institutional Bear Score   : "
        f"{result.institutional_bear_score:.2f}"
    )

    print(
        f"Directional Edge           : "
        f"{result.directional_edge:.2f}%"
    )

    print(
        f"Confidence Score           : "
        f"{result.confidence_score:.2f}%"
    )

    print(
        f"Directional Bias           : "
        f"{result.directional_bias}"
    )

    print(
        f"Market Regime              : "
        f"{result.market_regime}"
    )

    print(
        f"Suggested Action           : "
        f"{result.suggested_action}"
    )

    print(
        f"Trade Grade                : "
        f"{result.trade_grade}"
    )

    print(
        f"Trade Quality              : "
        f"{result.trade_quality}"
    )

    print()
    print("Interpretation")
    print("-" * 76)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SAMPLE INPUT
# ============================================================

def create_sample_probability_inputs() -> ProbabilityInputs:
    """
    Create sample integrated analytics inputs.
    """

    return ProbabilityInputs(
        spot_price=57582.25,

        oi_pcr=0.75,
        change_oi_pcr=0.68,
        oi_imbalance=-14.30,
        oi_market_bias="BEARISH",
        oi_build_up_signal="CALL WRITING DOMINANT",

        modified_pcr=0.72,
        atm_zone_pcr=0.78,
        pcr_trend="FALLING",
        pcr_bias="BEARISH",
        reversal_watch="NO EXTREME PCR SIGNAL",

        max_pain_strike=58000.0,
        expiry_bias="BULLISH PINNING PULL",
        pinning_probability=62.0,
        magnet_strength="STRONG",
        pain_shift="SHIFTED UP",

        positional_call_wall=58500.0,
        positional_put_wall=57000.0,
        fresh_call_wall=58000.0,
        fresh_put_wall=57000.0,
        combined_wall_shift="STABLE RANGE",
        range_bias="MID-RANGE — BALANCED",
        breakout_watch="CALL WALL TEST APPROACHING",
        breakdown_watch="NO IMMEDIATE BREAKDOWN TEST",

        atm_iv=18.50,
        historical_volatility=14.25,
        iv_rank=58.0,
        iv_percentile=72.0,
        iv_hv_spread=4.25,
        volatility_trend="RISING",
        volatility_regime="ELEVATED VOLATILITY",
        volatility_signal="VOLATILITY EXPANSION",
        skew_signal="MODERATE DOWNSIDE HEDGE DEMAND",
    )


# ============================================================
# INDEPENDENT TEST
# ============================================================

def main() -> None:
    """
    Run the independent Probability Engine test.
    """

    sample_inputs = (
        create_sample_probability_inputs()
    )

    timestamp = (
        pd.Timestamp.now(
            tz="Asia/Kolkata"
        ).isoformat()
    )

    result, evidence_table = (
        analyze_probability(
            inputs=sample_inputs,
            timestamp=timestamp,
        )
    )

    print_probability_summary(
        result
    )

    print("Evidence Table")
    print("-" * 76)

    display_columns = [
        "category",
        "indicator",
        "reading",
        "direction",
        "bullish_contribution",
        "bearish_contribution",
        "continuation_contribution",
        "reversal_contribution",
    ]

    print(
        evidence_table[
            display_columns
        ].to_string(
            index=False
        )
    )

    print()

    metadata = ExportMetadata(
        engine="PROBABILITY",
        underlying="BANKNIFTY_SAMPLE",
        engine_version="1.0",
        rows_processed=len(
            evidence_table
        ),
        status="SUCCESS",
        source=(
            "AQSD Sample Integrated Analytics"
        ),
        notes=(
            "Independent probability_engine.py "
            "module test."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "bullish_probability": (
            result.bullish_probability
        ),
        "bearish_probability": (
            result.bearish_probability
        ),
        "continuation_probability": (
            result.continuation_probability
        ),
        "reversal_probability": (
            result.reversal_probability
        ),
        "confidence_score": (
            result.confidence_score
        ),
        "directional_bias": (
            result.directional_bias
        ),
        "market_regime": (
            result.market_regime
        ),
        "suggested_action": (
            result.suggested_action
        ),
        "trade_grade": (
            result.trade_grade
        ),
    }

    engine_result = EngineResult(
        summary=result,
        table=evidence_table,
        history=history_row,
        metadata=metadata,
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_SAMPLE_PROBABILITY"
        ),
    )

    print_export_report(
        export_paths
    )


if __name__ == "__main__":
    main()