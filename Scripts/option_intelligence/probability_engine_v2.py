"""
AQSD
Normalized Probability Engine V2

Module: probability_engine_v2.py
Version: 2.0
Author: AQSD

Description:
Combines directional, positioning, volatility, wall, max-pain
and market-regime evidence to produce normalized scenario
probabilities whose total equals 100%.

Scenarios:
- Up Move
- Down Move
- Range Bound
- Bullish Breakout
- Bearish Breakdown
- Short Covering
- Long Build-up
- Mean Reversion
- Trend Continuation

Analytics only. No order placement.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import json

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIRECTORY = (
    BASE_DIR
    / "Output"
    / "Probability_V2"
)

SUMMARY_JSON_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_PROBABILITY_V2.json"
)

SUMMARY_CSV_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_PROBABILITY_V2.csv"
)

EVIDENCE_CSV_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_PROBABILITY_V2_EVIDENCE.csv"
)

HISTORY_CSV_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_PROBABILITY_V2_HISTORY.csv"
)

SCENARIOS = (
    "up_move",
    "down_move",
    "range_bound",
    "bullish_breakout",
    "bearish_breakdown",
    "short_covering",
    "long_build_up",
    "mean_reversion",
    "trend_continuation",
)


# ============================================================
# DATA MODELS
# ============================================================

@dataclass(frozen=True)
class ProbabilityInputs:
    """
    Inputs used by the normalized probability engine.
    """

    underlying: str
    spot_price: float
    atm_strike: float

    oi_pcr: float | None = None
    change_oi_pcr: float | None = None
    volume_pcr: float | None = None
    modified_pcr: float | None = None

    call_wall: float | None = None
    put_wall: float | None = None
    max_pain: float | None = None
    pinning_probability: float | None = None

    atm_iv: float | None = None
    iv_rank: float | None = None
    iv_percentile: float | None = None
    hv20: float | None = None
    volatility_premium_20: float | None = None
    volatility_heat_score: float | None = None

    volatility_regime: str = "N/A"
    volatility_signal: str = "N/A"
    mean_reversion_signal: str = "N/A"

    market_regime: str = "N/A"
    pcr_trend: str = "N/A"
    wall_shift: str = "N/A"
    skew_signal: str = "N/A"

    price_change_percent: float | None = None
    trend_signal: str = "N/A"


@dataclass(frozen=True)
class ProbabilitySummary:
    """
    Final normalized probability output.
    """

    underlying: str
    timestamp: str

    spot_price: float
    atm_strike: float

    probability_up: float
    probability_down: float
    probability_range_bound: float
    probability_bullish_breakout: float
    probability_bearish_breakdown: float
    probability_short_covering: float
    probability_long_build_up: float
    probability_mean_reversion: float
    probability_trend_continuation: float

    highest_probability_scenario: str
    highest_probability: float

    directional_bias: str
    market_state: str
    confidence: float
    probability_quality: str

    interpretation: str


@dataclass(frozen=True)
class ProbabilityResult:
    """
    Complete engine output.
    """

    summary: ProbabilitySummary
    probability_table: pd.DataFrame
    evidence_table: pd.DataFrame


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float safely.
    """

    if value is None:
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if math.isnan(number):
        return None

    if math.isinf(number):
        return None

    return number


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Restrict a number to a range.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def normalize_text(
    value: Any,
) -> str:
    """
    Normalize signal text.
    """

    return (
        str(value or "")
        .strip()
        .upper()
        .replace("-", " ")
        .replace("_", " ")
    )


def distance_percent(
    first_value: float | None,
    second_value: float | None,
) -> float | None:
    """
    Calculate percentage distance between two values.
    """

    if first_value is None:
        return None

    if second_value is None:
        return None

    if second_value == 0.0:
        return None

    return (
        abs(first_value - second_value)
        / abs(second_value)
        * 100.0
    )


# ============================================================
# SCORE MANAGEMENT
# ============================================================

def initial_scores() -> dict[str, float]:
    """
    Return neutral starting scores.
    """

    return {
        "up_move": 10.0,
        "down_move": 10.0,
        "range_bound": 10.0,
        "bullish_breakout": 6.0,
        "bearish_breakdown": 6.0,
        "short_covering": 5.0,
        "long_build_up": 5.0,
        "mean_reversion": 6.0,
        "trend_continuation": 7.0,
    }


def add_evidence(
    scores: dict[str, float],
    evidence_rows: list[dict[str, Any]],
    source: str,
    scenario: str,
    adjustment: float,
    reason: str,
) -> None:
    """
    Apply one evidence adjustment.
    """

    if scenario not in scores:
        raise KeyError(
            f"Unknown probability scenario: {scenario}"
        )

    scores[scenario] += adjustment

    evidence_rows.append(
        {
            "source": source,
            "scenario": scenario,
            "adjustment": adjustment,
            "reason": reason,
        }
    )


# ============================================================
# PCR EVIDENCE
# ============================================================

def apply_pcr_evidence(
    inputs: ProbabilityInputs,
    scores: dict[str, float],
    evidence: list[dict[str, Any]],
) -> None:
    """
    Apply PCR evidence.
    """

    oi_pcr = safe_float(
        inputs.oi_pcr
    )

    modified_pcr = safe_float(
        inputs.modified_pcr
    )

    change_oi_pcr = safe_float(
        inputs.change_oi_pcr
    )

    if oi_pcr is not None:
        if oi_pcr >= 1.20:
            add_evidence(
                scores,
                evidence,
                "OI PCR",
                "up_move",
                4.0,
                "High put open interest relative to calls.",
            )

            add_evidence(
                scores,
                evidence,
                "OI PCR",
                "short_covering",
                2.0,
                "High PCR may support short-covering risk.",
            )

        elif oi_pcr <= 0.80:
            add_evidence(
                scores,
                evidence,
                "OI PCR",
                "down_move",
                4.0,
                "Low put open interest relative to calls.",
            )

            add_evidence(
                scores,
                evidence,
                "OI PCR",
                "bearish_breakdown",
                2.0,
                "Low PCR supports downside pressure.",
            )

        else:
            add_evidence(
                scores,
                evidence,
                "OI PCR",
                "range_bound",
                2.0,
                "OI PCR is inside a neutral range.",
            )

    if modified_pcr is not None:
        if modified_pcr >= 1.10:
            add_evidence(
                scores,
                evidence,
                "Modified PCR",
                "up_move",
                4.0,
                "Modified PCR is bullish.",
            )

        elif modified_pcr <= 0.85:
            add_evidence(
                scores,
                evidence,
                "Modified PCR",
                "down_move",
                4.0,
                "Modified PCR is bearish.",
            )

        else:
            add_evidence(
                scores,
                evidence,
                "Modified PCR",
                "range_bound",
                1.5,
                "Modified PCR is neutral.",
            )

    if change_oi_pcr is not None:
        if change_oi_pcr >= 1.20:
            add_evidence(
                scores,
                evidence,
                "Change-OI PCR",
                "long_build_up",
                3.0,
                "Fresh put writing exceeds fresh call writing.",
            )

        elif change_oi_pcr <= 0.80:
            add_evidence(
                scores,
                evidence,
                "Change-OI PCR",
                "bearish_breakdown",
                3.0,
                "Fresh call writing dominates fresh put writing.",
            )


# ============================================================
# WALL AND MAX-PAIN EVIDENCE
# ============================================================

def apply_level_evidence(
    inputs: ProbabilityInputs,
    scores: dict[str, float],
    evidence: list[dict[str, Any]],
) -> None:
    """
    Apply call-wall, put-wall and max-pain evidence.
    """

    spot = inputs.spot_price

    call_wall = safe_float(
        inputs.call_wall
    )

    put_wall = safe_float(
        inputs.put_wall
    )

    max_pain = safe_float(
        inputs.max_pain
    )

    pinning_probability = safe_float(
        inputs.pinning_probability
    )

    call_distance = distance_percent(
        spot,
        call_wall,
    )

    put_distance = distance_percent(
        spot,
        put_wall,
    )

    max_pain_distance = distance_percent(
        spot,
        max_pain,
    )

    if (
        call_wall is not None
        and spot >= call_wall
    ):
        add_evidence(
            scores,
            evidence,
            "Call Wall",
            "bullish_breakout",
            5.0,
            "Spot is at or above the call wall.",
        )

        add_evidence(
            scores,
            evidence,
            "Call Wall",
            "short_covering",
            3.0,
            "Call-wall breach may force short covering.",
        )

    elif (
        call_distance is not None
        and call_distance <= 0.50
    ):
        add_evidence(
            scores,
            evidence,
            "Call Wall",
            "range_bound",
            3.0,
            "Spot is close to call resistance.",
        )

    if (
        put_wall is not None
        and spot <= put_wall
    ):
        add_evidence(
            scores,
            evidence,
            "Put Wall",
            "bearish_breakdown",
            5.0,
            "Spot is at or below the put wall.",
        )

    elif (
        put_distance is not None
        and put_distance <= 0.50
    ):
        add_evidence(
            scores,
            evidence,
            "Put Wall",
            "range_bound",
            3.0,
            "Spot is close to put support.",
        )

    if (
        max_pain_distance is not None
        and max_pain_distance <= 0.35
    ):
        pinning_adjustment = 4.0

        if pinning_probability is not None:
            pinning_adjustment += (
                clamp(
                    pinning_probability,
                    0.0,
                    100.0,
                )
                / 100.0
                * 4.0
            )

        add_evidence(
            scores,
            evidence,
            "Max Pain",
            "range_bound",
            pinning_adjustment,
            "Spot is close to max pain and may remain pinned.",
        )

        add_evidence(
            scores,
            evidence,
            "Max Pain",
            "mean_reversion",
            3.0,
            "Price may revert toward max pain.",
        )


# ============================================================
# VOLATILITY EVIDENCE
# ============================================================

def apply_volatility_evidence(
    inputs: ProbabilityInputs,
    scores: dict[str, float],
    evidence: list[dict[str, Any]],
) -> None:
    """
    Apply IV, IV Rank, IV Percentile and HV evidence.
    """

    iv_rank = safe_float(
        inputs.iv_rank
    )

    iv_percentile = safe_float(
        inputs.iv_percentile
    )

    premium = safe_float(
        inputs.volatility_premium_20
    )

    heat_score = safe_float(
        inputs.volatility_heat_score
    )

    volatility_signal = normalize_text(
        inputs.volatility_signal
    )

    mean_reversion_signal = normalize_text(
        inputs.mean_reversion_signal
    )

    if (
        iv_rank is not None
        and iv_percentile is not None
    ):
        if (
            iv_rank >= 75.0
            and iv_percentile >= 70.0
        ):
            add_evidence(
                scores,
                evidence,
                "IV Rank / Percentile",
                "mean_reversion",
                4.0,
                "IV is historically elevated.",
            )

            add_evidence(
                scores,
                evidence,
                "IV Rank / Percentile",
                "range_bound",
                2.0,
                "Elevated IV can favour premium contraction.",
            )

        elif (
            iv_rank <= 25.0
            and iv_percentile <= 30.0
        ):
            add_evidence(
                scores,
                evidence,
                "IV Rank / Percentile",
                "bullish_breakout",
                1.5,
                "Low IV can precede volatility expansion.",
            )

            add_evidence(
                scores,
                evidence,
                "IV Rank / Percentile",
                "bearish_breakdown",
                1.5,
                "Low IV can precede volatility expansion.",
            )

    if premium is not None:
        if premium >= 7.0:
            add_evidence(
                scores,
                evidence,
                "IV-HV Premium",
                "mean_reversion",
                4.0,
                "IV is materially above realized volatility.",
            )

            add_evidence(
                scores,
                evidence,
                "IV-HV Premium",
                "range_bound",
                2.0,
                "High volatility premium supports IV contraction.",
            )

        elif premium <= -4.0:
            add_evidence(
                scores,
                evidence,
                "IV-HV Premium",
                "bullish_breakout",
                2.0,
                "IV is below realized volatility.",
            )

            add_evidence(
                scores,
                evidence,
                "IV-HV Premium",
                "bearish_breakdown",
                2.0,
                "IV is below realized volatility.",
            )

    if heat_score is not None:
        if heat_score >= 75.0:
            add_evidence(
                scores,
                evidence,
                "Volatility Heat",
                "mean_reversion",
                3.0,
                "Volatility heat is high.",
            )

        elif heat_score <= 30.0:
            add_evidence(
                scores,
                evidence,
                "Volatility Heat",
                "trend_continuation",
                1.5,
                "Low volatility heat may permit trend continuation.",
            )

    if "CONTRACTION" in volatility_signal:
        add_evidence(
            scores,
            evidence,
            "Volatility Signal",
            "mean_reversion",
            3.0,
            "Volatility engine indicates contraction.",
        )

    if "EXPANSION" in volatility_signal:
        add_evidence(
            scores,
            evidence,
            "Volatility Signal",
            "bullish_breakout",
            2.0,
            "Volatility expansion may support an upside break.",
        )

        add_evidence(
            scores,
            evidence,
            "Volatility Signal",
            "bearish_breakdown",
            2.0,
            "Volatility expansion may support a downside break.",
        )

    if "MEAN REVERSION DOWN" in mean_reversion_signal:
        add_evidence(
            scores,
            evidence,
            "Mean Reversion",
            "mean_reversion",
            4.0,
            "IV is expected to mean revert lower.",
        )

    elif "MEAN REVERSION UP" in mean_reversion_signal:
        add_evidence(
            scores,
            evidence,
            "Mean Reversion",
            "bullish_breakout",
            1.5,
            "IV expansion risk is rising.",
        )

        add_evidence(
            scores,
            evidence,
            "Mean Reversion",
            "bearish_breakdown",
            1.5,
            "IV expansion risk is rising.",
        )


# ============================================================
# TREND AND REGIME EVIDENCE
# ============================================================

def apply_regime_evidence(
    inputs: ProbabilityInputs,
    scores: dict[str, float],
    evidence: list[dict[str, Any]],
) -> None:
    """
    Apply market-regime, trend and wall-shift evidence.
    """

    market_regime = normalize_text(
        inputs.market_regime
    )

    trend_signal = normalize_text(
        inputs.trend_signal
    )

    pcr_trend = normalize_text(
        inputs.pcr_trend
    )

    wall_shift = normalize_text(
        inputs.wall_shift
    )

    skew_signal = normalize_text(
        inputs.skew_signal
    )

    price_change = safe_float(
        inputs.price_change_percent
    )

    if (
        "RANGE" in market_regime
        or "MIXED" in market_regime
    ):
        add_evidence(
            scores,
            evidence,
            "Market Regime",
            "range_bound",
            6.0,
            "Market regime is mixed or range-bound.",
        )

        add_evidence(
            scores,
            evidence,
            "Market Regime",
            "mean_reversion",
            2.0,
            "Range-bound conditions support mean reversion.",
        )

    if "TREND" in market_regime:
        add_evidence(
            scores,
            evidence,
            "Market Regime",
            "trend_continuation",
            5.0,
            "Market regime is trending.",
        )

    if (
        "BULL" in trend_signal
        or "UPTREND" in trend_signal
    ):
        add_evidence(
            scores,
            evidence,
            "Trend",
            "up_move",
            5.0,
            "Price trend is bullish.",
        )

        add_evidence(
            scores,
            evidence,
            "Trend",
            "trend_continuation",
            3.0,
            "Bullish trend supports continuation.",
        )

        add_evidence(
            scores,
            evidence,
            "Trend",
            "long_build_up",
            2.0,
            "Bullish trend may reflect long build-up.",
        )

    elif (
        "BEAR" in trend_signal
        or "DOWNTREND" in trend_signal
    ):
        add_evidence(
            scores,
            evidence,
            "Trend",
            "down_move",
            5.0,
            "Price trend is bearish.",
        )

        add_evidence(
            scores,
            evidence,
            "Trend",
            "trend_continuation",
            3.0,
            "Bearish trend supports continuation.",
        )

        add_evidence(
            scores,
            evidence,
            "Trend",
            "bearish_breakdown",
            2.0,
            "Bearish trend supports breakdown risk.",
        )

    if "RISING" in pcr_trend:
        add_evidence(
            scores,
            evidence,
            "PCR Trend",
            "up_move",
            3.0,
            "PCR trend is rising.",
        )

    elif "FALLING" in pcr_trend:
        add_evidence(
            scores,
            evidence,
            "PCR Trend",
            "down_move",
            3.0,
            "PCR trend is falling.",
        )

    if "BULL" in wall_shift:
        add_evidence(
            scores,
            evidence,
            "Wall Shift",
            "up_move",
            3.0,
            "Wall movement is bullish.",
        )

        add_evidence(
            scores,
            evidence,
            "Wall Shift",
            "bullish_breakout",
            2.0,
            "Bullish wall movement supports breakout.",
        )

    elif "BEAR" in wall_shift:
        add_evidence(
            scores,
            evidence,
            "Wall Shift",
            "down_move",
            3.0,
            "Wall movement is bearish.",
        )

        add_evidence(
            scores,
            evidence,
            "Wall Shift",
            "bearish_breakdown",
            2.0,
            "Bearish wall movement supports breakdown.",
        )

    if "PUT SKEW" in skew_signal:
        add_evidence(
            scores,
            evidence,
            "IV Skew",
            "down_move",
            2.0,
            "Put IV skew shows downside hedging demand.",
        )

    elif "CALL SKEW" in skew_signal:
        add_evidence(
            scores,
            evidence,
            "IV Skew",
            "up_move",
            2.0,
            "Call IV skew shows upside demand.",
        )

    if price_change is not None:
        if price_change >= 0.75:
            add_evidence(
                scores,
                evidence,
                "Price Change",
                "up_move",
                4.0,
                "Spot has positive price momentum.",
            )

            add_evidence(
                scores,
                evidence,
                "Price Change",
                "trend_continuation",
                2.0,
                "Positive momentum supports continuation.",
            )

        elif price_change <= -0.75:
            add_evidence(
                scores,
                evidence,
                "Price Change",
                "down_move",
                4.0,
                "Spot has negative price momentum.",
            )

            add_evidence(
                scores,
                evidence,
                "Price Change",
                "trend_continuation",
                2.0,
                "Negative momentum supports continuation.",
            )


# ============================================================
# NORMALIZATION
# ============================================================

def softmax_probabilities(
    scores: dict[str, float],
    temperature: float = 12.0,
) -> dict[str, float]:
    """
    Convert scenario scores into probabilities using softmax.

    The final rounded probabilities are adjusted so the total
    equals exactly 100.00.
    """

    if temperature <= 0.0:
        raise ValueError(
            "temperature must be positive."
        )

    maximum_score = max(
        scores.values()
    )

    exponentials = {
        scenario: math.exp(
            (
                score
                - maximum_score
            )
            / temperature
        )
        for scenario, score in scores.items()
    }

    denominator = sum(
        exponentials.values()
    )

    if denominator <= 0.0:
        raise RuntimeError(
            "Probability normalization failed."
        )

    probabilities = {
        scenario: (
            exponential
            / denominator
            * 100.0
        )
        for scenario, exponential
        in exponentials.items()
    }

    rounded = {
        scenario: round(
            probability,
            2,
        )
        for scenario, probability
        in probabilities.items()
    }

    difference = round(
        100.0
        - sum(
            rounded.values()
        ),
        2,
    )

    highest_scenario = max(
        rounded,
        key=rounded.get,
    )

    rounded[
        highest_scenario
    ] = round(
        rounded[
            highest_scenario
        ]
        + difference,
        2,
    )

    return rounded


# ============================================================
# FINAL CLASSIFICATION
# ============================================================

def determine_directional_bias(
    probabilities: dict[str, float],
) -> str:
    """
    Determine the directional bias.
    """

    bullish_probability = (
        probabilities["up_move"]
        + probabilities["bullish_breakout"]
        + probabilities["short_covering"]
        + probabilities["long_build_up"]
    )

    bearish_probability = (
        probabilities["down_move"]
        + probabilities["bearish_breakdown"]
    )

    if (
        bullish_probability
        >= bearish_probability + 10.0
    ):
        return "BULLISH"

    if (
        bearish_probability
        >= bullish_probability + 10.0
    ):
        return "BEARISH"

    return "NEUTRAL"


def determine_market_state(
    probabilities: dict[str, float],
) -> str:
    """
    Determine the dominant market state.
    """

    if (
        probabilities["range_bound"]
        >= 20.0
    ):
        return "RANGE-BOUND"

    if (
        probabilities["trend_continuation"]
        >= 18.0
    ):
        return "TREND CONTINUATION"

    if (
        probabilities["mean_reversion"]
        >= 18.0
    ):
        return "MEAN REVERSION"

    if (
        probabilities["bullish_breakout"]
        >= 15.0
    ):
        return "BULLISH BREAKOUT WATCH"

    if (
        probabilities["bearish_breakdown"]
        >= 15.0
    ):
        return "BEARISH BREAKDOWN WATCH"

    return "MIXED"


def determine_probability_quality(
    evidence_count: int,
    highest_probability: float,
) -> str:
    """
    Grade the probability output.
    """

    if (
        evidence_count >= 18
        and highest_probability >= 20.0
    ):
        return "A"

    if (
        evidence_count >= 12
        and highest_probability >= 17.0
    ):
        return "B"

    if evidence_count >= 7:
        return "C"

    return "LOW DATA"


def calculate_confidence(
    probabilities: dict[str, float],
    evidence_count: int,
) -> float:
    """
    Calculate confidence from probability concentration and evidence.
    """

    sorted_probabilities = sorted(
        probabilities.values(),
        reverse=True,
    )

    highest = sorted_probabilities[0]
    second_highest = sorted_probabilities[1]

    concentration_gap = (
        highest
        - second_highest
    )

    evidence_score = min(
        evidence_count / 20.0,
        1.0,
    ) * 35.0

    probability_score = min(
        highest / 30.0,
        1.0,
    ) * 45.0

    separation_score = min(
        concentration_gap / 15.0,
        1.0,
    ) * 20.0

    return round(
        clamp(
            evidence_score
            + probability_score
            + separation_score
        ),
        2,
    )


def build_interpretation(
    probabilities: dict[str, float],
    directional_bias: str,
    market_state: str,
    confidence: float,
) -> str:
    """
    Build a readable interpretation.
    """

    ordered = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    first_scenario, first_value = (
        ordered[0]
    )

    second_scenario, second_value = (
        ordered[1]
    )

    first_label = first_scenario.replace(
        "_",
        " ",
    ).upper()

    second_label = second_scenario.replace(
        "_",
        " ",
    ).upper()

    return (
        f"The dominant normalized scenario is {first_label} "
        f"at {first_value:.2f}%, followed by {second_label} "
        f"at {second_value:.2f}%. The combined directional "
        f"assessment is {directional_bias}. The market state is "
        f"classified as {market_state}. Model confidence is "
        f"{confidence:.2f}%. These are analytical model "
        f"probabilities and are not yet empirically calibrated."
    )


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_probabilities(
    inputs: ProbabilityInputs,
    timestamp: str | None = None,
) -> ProbabilityResult:
    """
    Run the complete normalized probability engine.
    """

    if inputs.spot_price <= 0.0:
        raise ValueError(
            "spot_price must be positive."
        )

    if inputs.atm_strike <= 0.0:
        raise ValueError(
            "atm_strike must be positive."
        )

    scores = initial_scores()

    evidence_rows: list[
        dict[str, Any]
    ] = []

    apply_pcr_evidence(
        inputs,
        scores,
        evidence_rows,
    )

    apply_level_evidence(
        inputs,
        scores,
        evidence_rows,
    )

    apply_volatility_evidence(
        inputs,
        scores,
        evidence_rows,
    )

    apply_regime_evidence(
        inputs,
        scores,
        evidence_rows,
    )

    probabilities = softmax_probabilities(
        scores
    )

    highest_scenario = max(
        probabilities,
        key=probabilities.get,
    )

    highest_probability = (
        probabilities[
            highest_scenario
        ]
    )

    directional_bias = (
        determine_directional_bias(
            probabilities
        )
    )

    market_state = (
        determine_market_state(
            probabilities
        )
    )

    confidence = calculate_confidence(
        probabilities=probabilities,
        evidence_count=len(
            evidence_rows
        ),
    )

    probability_quality = (
        determine_probability_quality(
            evidence_count=len(
                evidence_rows
            ),
            highest_probability=(
                highest_probability
            ),
        )
    )

    resolved_timestamp = (
        timestamp
        or datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    interpretation = (
        build_interpretation(
            probabilities=probabilities,
            directional_bias=(
                directional_bias
            ),
            market_state=market_state,
            confidence=confidence,
        )
    )

    summary = ProbabilitySummary(
        underlying=inputs.underlying,
        timestamp=resolved_timestamp,
        spot_price=float(
            inputs.spot_price
        ),
        atm_strike=float(
            inputs.atm_strike
        ),
        probability_up=(
            probabilities[
                "up_move"
            ]
        ),
        probability_down=(
            probabilities[
                "down_move"
            ]
        ),
        probability_range_bound=(
            probabilities[
                "range_bound"
            ]
        ),
        probability_bullish_breakout=(
            probabilities[
                "bullish_breakout"
            ]
        ),
        probability_bearish_breakdown=(
            probabilities[
                "bearish_breakdown"
            ]
        ),
        probability_short_covering=(
            probabilities[
                "short_covering"
            ]
        ),
        probability_long_build_up=(
            probabilities[
                "long_build_up"
            ]
        ),
        probability_mean_reversion=(
            probabilities[
                "mean_reversion"
            ]
        ),
        probability_trend_continuation=(
            probabilities[
                "trend_continuation"
            ]
        ),
        highest_probability_scenario=(
            highest_scenario
            .replace("_", " ")
            .upper()
        ),
        highest_probability=(
            highest_probability
        ),
        directional_bias=(
            directional_bias
        ),
        market_state=market_state,
        confidence=confidence,
        probability_quality=(
            probability_quality
        ),
        interpretation=interpretation,
    )

    probability_table = pd.DataFrame(
        [
            {
                "scenario": (
                    scenario
                    .replace("_", " ")
                    .upper()
                ),
                "raw_score": round(
                    scores[scenario],
                    4,
                ),
                "probability_percent": (
                    probabilities[
                        scenario
                    ]
                ),
            }
            for scenario in SCENARIOS
        ]
    ).sort_values(
        "probability_percent",
        ascending=False,
    ).reset_index(
        drop=True
    )

    evidence_table = pd.DataFrame(
        evidence_rows
    )

    return ProbabilityResult(
        summary=summary,
        probability_table=(
            probability_table
        ),
        evidence_table=(
            evidence_table
        ),
    )


# ============================================================
# EXPORTS
# ============================================================

def export_probability_result(
    result: ProbabilityResult,
    output_directory: Path = OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """
    Export probability outputs.
    """

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_row = pd.DataFrame(
        [
            asdict(
                result.summary
            )
        ]
    )

    summary_row.to_csv(
        SUMMARY_CSV_FILE,
        index=False,
    )

    with SUMMARY_JSON_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            asdict(
                result.summary
            ),
            file,
            indent=4,
            ensure_ascii=False,
        )

    result.evidence_table.to_csv(
        EVIDENCE_CSV_FILE,
        index=False,
    )

    existing_history = pd.DataFrame()

    if HISTORY_CSV_FILE.exists():
        try:
            existing_history = (
                pd.read_csv(
                    HISTORY_CSV_FILE
                )
            )

        except Exception:
            existing_history = (
                pd.DataFrame()
            )

    if existing_history.empty:
        updated_history = (
            summary_row.copy()
        )

    else:
        updated_history = pd.concat(
            [
                existing_history,
                summary_row,
            ],
            ignore_index=True,
        )

    updated_history.to_csv(
        HISTORY_CSV_FILE,
        index=False,
    )

    probability_table_file = (
        output_directory
        / "BANKNIFTY_PROBABILITY_V2_TABLE.csv"
    )

    result.probability_table.to_csv(
        probability_table_file,
        index=False,
    )

    return {
        "summary_csv": SUMMARY_CSV_FILE,
        "summary_json": SUMMARY_JSON_FILE,
        "probability_table_csv": (
            probability_table_file
        ),
        "evidence_csv": EVIDENCE_CSV_FILE,
        "history_csv": HISTORY_CSV_FILE,
    }


# ============================================================
# DISPLAY
# ============================================================

def print_probability_summary(
    result: ProbabilityResult,
) -> None:
    """
    Print probability summary.
    """

    summary = result.summary

    print()
    print("=" * 86)
    print(
        "AQSD NORMALIZED PROBABILITY ENGINE V2"
        .center(86)
    )
    print("=" * 86)

    print(
        f"Underlying                 : "
        f"{summary.underlying}"
    )
    print(
        f"Spot Price                 : "
        f"{summary.spot_price:,.2f}"
    )
    print(
        f"ATM Strike                 : "
        f"{summary.atm_strike:,.2f}"
    )

    print("-" * 86)

    print(
        f"Probability Up             : "
        f"{summary.probability_up:.2f}%"
    )
    print(
        f"Probability Down           : "
        f"{summary.probability_down:.2f}%"
    )
    print(
        f"Probability Range-bound    : "
        f"{summary.probability_range_bound:.2f}%"
    )
    print(
        f"Bullish Breakout           : "
        f"{summary.probability_bullish_breakout:.2f}%"
    )
    print(
        f"Bearish Breakdown          : "
        f"{summary.probability_bearish_breakdown:.2f}%"
    )
    print(
        f"Short Covering             : "
        f"{summary.probability_short_covering:.2f}%"
    )
    print(
        f"Long Build-up              : "
        f"{summary.probability_long_build_up:.2f}%"
    )
    print(
        f"Mean Reversion             : "
        f"{summary.probability_mean_reversion:.2f}%"
    )
    print(
        f"Trend Continuation         : "
        f"{summary.probability_trend_continuation:.2f}%"
    )

    total_probability = sum(
        result.probability_table[
            "probability_percent"
        ]
    )

    print("-" * 86)

    print(
        f"Probability Total          : "
        f"{total_probability:.2f}%"
    )
    print(
        f"Highest Scenario           : "
        f"{summary.highest_probability_scenario}"
    )
    print(
        f"Highest Probability        : "
        f"{summary.highest_probability:.2f}%"
    )
    print(
        f"Directional Bias           : "
        f"{summary.directional_bias}"
    )
    print(
        f"Market State               : "
        f"{summary.market_state}"
    )
    print(
        f"Confidence                 : "
        f"{summary.confidence:.2f}%"
    )
    print(
        f"Probability Quality        : "
        f"{summary.probability_quality}"
    )

    print()
    print("Interpretation")
    print("-" * 86)
    print(
        summary.interpretation
    )
    print("=" * 86)


# ============================================================
# SAMPLE TEST
# ============================================================

def build_sample_inputs() -> ProbabilityInputs:
    """
    Build sample BANKNIFTY inputs.
    """

    return ProbabilityInputs(
        underlying="BANKNIFTY",
        spot_price=58521.40,
        atm_strike=58500.00,
        oi_pcr=0.746,
        change_oi_pcr=0.82,
        volume_pcr=0.98,
        modified_pcr=0.91,
        call_wall=59000.00,
        put_wall=58000.00,
        max_pain=58500.00,
        pinning_probability=32.0,
        atm_iv=22.93,
        iv_rank=68.0,
        iv_percentile=61.0,
        hv20=16.37,
        volatility_premium_20=6.56,
        volatility_heat_score=72.27,
        volatility_regime="HIGH",
        volatility_signal=(
            "OPTIONS RELATIVELY EXPENSIVE"
        ),
        mean_reversion_signal=(
            "IV CONTRACTION WATCH"
        ),
        market_regime="MIXED / RANGE-BOUND",
        pcr_trend="FALLING",
        wall_shift="STABLE / MIXED",
        skew_signal="BALANCED SKEW",
        price_change_percent=-0.65,
        trend_signal="BEARISH",
    )


def main() -> None:
    """
    Run sample probability analysis.
    """

    inputs = build_sample_inputs()

    result = analyze_probabilities(
        inputs
    )

    exported_files = (
        export_probability_result(
            result
        )
    )

    print_probability_summary(
        result
    )

    print()
    print("Exported Files")
    print("-" * 86)

    for label, path in exported_files.items():
        print(
            f"{label:28} : {path}"
        )

    print()
    print("Status                      : SUCCESS")
    print("=" * 86)


if __name__ == "__main__":
    main()