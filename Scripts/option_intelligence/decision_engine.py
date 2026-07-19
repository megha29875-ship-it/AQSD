"""
AQSD
Option Intelligence

Module: decision_engine.py
Version: 1.0
Author: AQSD

Description:
Converts Option Intelligence analytics into a transparent,
rule-based decision.

This engine does not place orders.

Possible decisions:
- BUY CALL
- BUY PUT
- WAIT
- NO TRADE

Inputs:
- Probability Engine
- PCR
- Option Walls
- Max Pain
- Volatility
- Market regime

Outputs:
- Final Decision
- Confidence
- Trade Grade
- Entry Zone
- Stop Level
- Target 1
- Target 2
- Risk-Reward Estimate
- Supporting Reasons
- Risk Warnings
"""

from __future__ import annotations

from dataclasses import dataclass

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

MINIMUM_TRADE_CONFIDENCE = 58.0
STRONG_TRADE_CONFIDENCE = 72.0
HIGH_REVERSAL_WARNING = 60.0

MINIMUM_DIRECTIONAL_EDGE = 12.0
STRONG_DIRECTIONAL_EDGE = 25.0

DEFAULT_STOP_BUFFER_PERCENT = 0.25
DEFAULT_TARGET_ONE_PERCENT = 0.40
DEFAULT_TARGET_TWO_PERCENT = 0.75


# ============================================================
# INPUT MODEL
# ============================================================

@dataclass(slots=True)
class DecisionInputs:
    """
    Consolidated inputs required by the Decision Engine.
    """

    underlying: str
    spot_price: float
    atm_strike: float
    strike_step: float
    timestamp: str

    bullish_probability: float
    bearish_probability: float

    continuation_probability: float
    reversal_probability: float

    confidence_score: float
    directional_edge: float

    directional_bias: str
    market_regime: str
    probability_action: str
    probability_grade: str

    modified_pcr: float | None
    pcr_trend: str
    pcr_bias: str
    reversal_watch: str

    positional_call_wall: float | None
    positional_put_wall: float | None

    fresh_call_wall: float | None
    fresh_put_wall: float | None

    combined_wall_shift: str
    breakout_watch: str
    breakdown_watch: str

    max_pain_strike: float | None
    pinning_probability: float | None
    expiry_bias: str
    magnet_strength: str

    atm_iv: float | None
    historical_volatility: float | None
    iv_rank: float | None
    iv_percentile: float | None

    volatility_trend: str
    volatility_regime: str
    volatility_signal: str
    skew_signal: str


# ============================================================
# OUTPUT MODEL
# ============================================================

@dataclass(slots=True)
class DecisionResult:
    """
    Final AQSD option decision.
    """

    underlying: str
    spot_price: float
    atm_strike: float

    final_decision: str
    decision_bias: str

    confidence_score: float
    trade_grade: str
    trade_quality: str

    market_regime: str
    risk_level: str

    entry_low: float | None
    entry_high: float | None

    stop_loss: float | None
    target_one: float | None
    target_two: float | None

    estimated_risk_points: float | None
    estimated_reward_one_points: float | None
    estimated_reward_two_points: float | None

    risk_reward_one: float | None
    risk_reward_two: float | None

    bullish_probability: float
    bearish_probability: float
    continuation_probability: float
    reversal_probability: float

    supporting_reasons: str
    risk_warnings: str
    interpretation: str

    timestamp: str


# ============================================================
# EVIDENCE MODEL
# ============================================================

@dataclass(slots=True)
class DecisionEvidence:
    """
    One Decision Engine scoring contribution.
    """

    category: str
    indicator: str
    reading: str

    bullish_points: float
    bearish_points: float

    supports_trade: bool
    warning: bool

    explanation: str


# ============================================================
# HELPERS
# ============================================================

def clean_text(
    value: str | None,
) -> str:
    """
    Normalize optional text.
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
    Restrict a number to a range.
    """

    return min(
        maximum,
        max(
            minimum,
            float(value),
        ),
    )


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float | None:
    """
    Divide safely.
    """

    if denominator == 0:
        return None

    return float(
        numerator / denominator
    )


def format_optional(
    value: float | None,
    decimals: int = 2,
) -> str:
    """
    Format an optional number.
    """

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}"


# ============================================================
# DECISION EVIDENCE
# ============================================================

def build_probability_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build evidence from normalized probabilities.
    """

    evidence: list[DecisionEvidence] = []

    if (
        inputs.bullish_probability
        > inputs.bearish_probability
    ):
        bullish_points = (
            inputs.bullish_probability
            / 10.0
        )

        bearish_points = 0.0

        explanation = (
            "Bullish probability exceeds bearish probability."
        )

    elif (
        inputs.bearish_probability
        > inputs.bullish_probability
    ):
        bullish_points = 0.0

        bearish_points = (
            inputs.bearish_probability
            / 10.0
        )

        explanation = (
            "Bearish probability exceeds bullish probability."
        )

    else:
        bullish_points = 0.0
        bearish_points = 0.0

        explanation = (
            "Directional probabilities are balanced."
        )

    evidence.append(
        DecisionEvidence(
            category="PROBABILITY",
            indicator="Directional Probability",
            reading=(
                f"Bull {inputs.bullish_probability:.1f}% | "
                f"Bear {inputs.bearish_probability:.1f}%"
            ),
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            supports_trade=(
                inputs.directional_edge
                >= MINIMUM_DIRECTIONAL_EDGE
            ),
            warning=False,
            explanation=explanation,
        )
    )

    evidence.append(
        DecisionEvidence(
            category="PROBABILITY",
            indicator="Continuation / Reversal",
            reading=(
                f"Continuation "
                f"{inputs.continuation_probability:.1f}% | "
                f"Reversal "
                f"{inputs.reversal_probability:.1f}%"
            ),
            bullish_points=0.0,
            bearish_points=0.0,
            supports_trade=(
                inputs.continuation_probability
                >= inputs.reversal_probability
            ),
            warning=(
                inputs.reversal_probability
                >= HIGH_REVERSAL_WARNING
            ),
            explanation=(
                "High continuation supports directional trades; "
                "high reversal probability requires caution."
            ),
        )
    )

    return evidence


def build_pcr_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build evidence from PCR analytics.
    """

    modified_pcr = inputs.modified_pcr

    if modified_pcr is None:
        bullish_points = 0.0
        bearish_points = 0.0

    elif modified_pcr >= 1.10:
        bullish_points = 6.0
        bearish_points = 0.0

    elif modified_pcr <= 0.80:
        bullish_points = 0.0
        bearish_points = 6.0

    else:
        bullish_points = 1.5
        bearish_points = 1.5

    trend = clean_text(
        inputs.pcr_trend
    )

    if trend == "RISING":
        bullish_points += 2.0

    elif trend == "FALLING":
        bearish_points += 2.0

    reversal_text = clean_text(
        inputs.reversal_watch
    )

    return [
        DecisionEvidence(
            category="PCR",
            indicator="Modified PCR",
            reading=(
                f"{format_optional(modified_pcr, 3)} | "
                f"{inputs.pcr_trend}"
            ),
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            supports_trade=True,
            warning=(
                "REVERSAL WATCH"
                in reversal_text
            ),
            explanation=(
                "Modified PCR and its trend indicate whether "
                "Put-side or Call-side positioning dominates."
            ),
        )
    ]


def build_wall_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build evidence from option walls.
    """

    evidence: list[DecisionEvidence] = []

    breakout = clean_text(
        inputs.breakout_watch
    )

    breakdown = clean_text(
        inputs.breakdown_watch
    )

    if "BREAKOUT ACTIVE" in breakout:
        bullish_points = 8.0
        bearish_points = 0.0
        supports_trade = True

    elif "BREAKDOWN ACTIVE" in breakdown:
        bullish_points = 0.0
        bearish_points = 8.0
        supports_trade = True

    else:
        bullish_points = 0.0
        bearish_points = 0.0
        supports_trade = False

    evidence.append(
        DecisionEvidence(
            category="WALLS",
            indicator="Breakout / Breakdown",
            reading=(
                f"{inputs.breakout_watch} | "
                f"{inputs.breakdown_watch}"
            ),
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            supports_trade=supports_trade,
            warning=(
                "TEST APPROACHING" in breakout
                or "TEST APPROACHING" in breakdown
                or "VERY CLOSE" in breakout
                or "VERY CLOSE" in breakdown
            ),
            explanation=(
                "Movement beyond a positional wall confirms "
                "direction; proximity to a wall increases rejection risk."
            ),
        )
    )

    wall_shift = clean_text(
        inputs.combined_wall_shift
    )

    if wall_shift == "RANGE SHIFTED UP":
        bullish_points = 5.0
        bearish_points = 0.0

    elif wall_shift == "RANGE SHIFTED DOWN":
        bullish_points = 0.0
        bearish_points = 5.0

    else:
        bullish_points = 0.0
        bearish_points = 0.0

    evidence.append(
        DecisionEvidence(
            category="WALLS",
            indicator="Wall Shift",
            reading=inputs.combined_wall_shift,
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            supports_trade=(
                wall_shift
                in {
                    "RANGE SHIFTED UP",
                    "RANGE SHIFTED DOWN",
                }
            ),
            warning=(
                wall_shift
                in {
                    "RANGE COMPRESSION",
                    "MIXED WALL SHIFT",
                }
            ),
            explanation=(
                "Coordinated wall migration indicates movement "
                "of the expected trading range."
            ),
        )
    )

    return evidence


def build_max_pain_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build evidence from Max Pain.
    """

    expiry_bias = clean_text(
        inputs.expiry_bias
    )

    pinning = (
        inputs.pinning_probability
        if inputs.pinning_probability is not None
        else 0.0
    )

    strength = clamp(
        pinning / 20.0,
        0.0,
        5.0,
    )

    if "BULLISH" in expiry_bias:
        bullish_points = strength
        bearish_points = 0.0

    elif "BEARISH" in expiry_bias:
        bullish_points = 0.0
        bearish_points = strength

    else:
        bullish_points = 0.0
        bearish_points = 0.0

    return [
        DecisionEvidence(
            category="MAX PAIN",
            indicator="Expiry Pull",
            reading=(
                f"{inputs.expiry_bias} | "
                f"Pinning {pinning:.1f}%"
            ),
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            supports_trade=(
                "BULLISH" in expiry_bias
                or "BEARISH" in expiry_bias
            ),
            warning=(
                pinning >= 70.0
                and inputs.market_regime == "TRENDING"
            ),
            explanation=(
                "Max Pain may pull price toward the expiry magnet, "
                "especially when pinning strength is high."
            ),
        )
    ]


def build_volatility_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build evidence from volatility.
    """

    regime = clean_text(
        inputs.volatility_regime
    )

    trend = clean_text(
        inputs.volatility_trend
    )

    warning = (
        "EXTREME" in regime
        or inputs.iv_rank is not None
        and inputs.iv_rank >= 80.0
    )

    supports_trade = (
        trend == "RISING"
        and not warning
    )

    return [
        DecisionEvidence(
            category="VOLATILITY",
            indicator="Volatility Regime",
            reading=(
                f"{inputs.volatility_trend} | "
                f"{inputs.volatility_regime} | "
                f"IV Rank {format_optional(inputs.iv_rank)}"
            ),
            bullish_points=0.0,
            bearish_points=0.0,
            supports_trade=supports_trade,
            warning=warning,
            explanation=(
                "Volatility expansion confirms movement, but "
                "extreme IV increases exhaustion and premium risk."
            ),
        )
    ]


def build_all_evidence(
    inputs: DecisionInputs,
) -> list[DecisionEvidence]:
    """
    Build all Decision Engine evidence.
    """

    evidence: list[DecisionEvidence] = []

    evidence.extend(
        build_probability_evidence(
            inputs
        )
    )

    evidence.extend(
        build_pcr_evidence(
            inputs
        )
    )

    evidence.extend(
        build_wall_evidence(
            inputs
        )
    )

    evidence.extend(
        build_max_pain_evidence(
            inputs
        )
    )

    evidence.extend(
        build_volatility_evidence(
            inputs
        )
    )

    return evidence


def evidence_to_dataframe(
    evidence: list[DecisionEvidence],
) -> pd.DataFrame:
    """
    Convert decision evidence into a table.
    """

    return pd.DataFrame(
        [
            {
                "category": item.category,
                "indicator": item.indicator,
                "reading": item.reading,
                "bullish_points": (
                    item.bullish_points
                ),
                "bearish_points": (
                    item.bearish_points
                ),
                "supports_trade": (
                    item.supports_trade
                ),
                "warning": item.warning,
                "explanation": (
                    item.explanation
                ),
            }
            for item in evidence
        ]
    )


# ============================================================
# FINAL DECISION
# ============================================================

def determine_final_decision(
    inputs: DecisionInputs,
    bullish_points: float,
    bearish_points: float,
    warning_count: int,
) -> tuple[str, str]:
    """
    Determine the final decision and bias.
    """

    if (
        inputs.confidence_score
        < MINIMUM_TRADE_CONFIDENCE
    ):
        return "WAIT", "LOW CONFIDENCE"

    if (
        inputs.directional_edge
        < MINIMUM_DIRECTIONAL_EDGE
    ):
        return "NO TRADE", "INSUFFICIENT EDGE"

    if (
        inputs.reversal_probability
        >= HIGH_REVERSAL_WARNING
        and warning_count >= 2
    ):
        return "WAIT", "HIGH REVERSAL RISK"

    if bullish_points > bearish_points:
        return "BUY CALL", "BULLISH"

    if bearish_points > bullish_points:
        return "BUY PUT", "BEARISH"

    return "NO TRADE", "BALANCED"


def determine_trade_grade(
    confidence_score: float,
    directional_edge: float,
    warning_count: int,
) -> str:
    """
    Assign the final decision grade.
    """

    adjusted_confidence = (
        confidence_score
        - warning_count * 5.0
    )

    if (
        adjusted_confidence >= 85.0
        and directional_edge >= 35.0
    ):
        return "A+"

    if (
        adjusted_confidence >= 75.0
        and directional_edge >= 25.0
    ):
        return "A"

    if (
        adjusted_confidence >= 68.0
        and directional_edge >= 18.0
    ):
        return "B+"

    if (
        adjusted_confidence >= 58.0
        and directional_edge >= 12.0
    ):
        return "B"

    if adjusted_confidence >= 50.0:
        return "C"

    return "D"


def determine_trade_quality(
    grade: str,
) -> str:
    """
    Convert grade to quality.
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
        grade,
        "UNKNOWN",
    )


def determine_risk_level(
    inputs: DecisionInputs,
    warning_count: int,
) -> str:
    """
    Determine the overall risk level.
    """

    if warning_count >= 3:
        return "HIGH"

    if (
        inputs.reversal_probability >= 60.0
        or clean_text(
            inputs.volatility_regime
        )
        == "EXTREME VOLATILITY"
    ):
        return "HIGH"

    if warning_count >= 1:
        return "MODERATE"

    return "LOW"


# ============================================================
# LEVEL CALCULATION
# ============================================================

def calculate_trade_levels(
    inputs: DecisionInputs,
    final_decision: str,
) -> dict[str, float | None]:
    """
    Calculate underlying-based decision levels.

    These are analytical reference levels for Tab-2.
    They are not option-premium order prices.
    """

    spot = inputs.spot_price

    if final_decision not in {
        "BUY CALL",
        "BUY PUT",
    }:
        return {
            "entry_low": None,
            "entry_high": None,
            "stop_loss": None,
            "target_one": None,
            "target_two": None,
        }

    entry_buffer = max(
        inputs.strike_step * 0.10,
        spot * 0.0005,
    )

    stop_buffer = max(
        inputs.strike_step * 0.50,
        spot
        * DEFAULT_STOP_BUFFER_PERCENT
        / 100.0,
    )

    target_one_buffer = max(
        inputs.strike_step,
        spot
        * DEFAULT_TARGET_ONE_PERCENT
        / 100.0,
    )

    target_two_buffer = max(
        inputs.strike_step * 1.75,
        spot
        * DEFAULT_TARGET_TWO_PERCENT
        / 100.0,
    )

    entry_low = (
        spot - entry_buffer
    )

    entry_high = (
        spot + entry_buffer
    )

    if final_decision == "BUY CALL":
        structural_stop = (
            inputs.positional_put_wall
        )

        stop_loss = (
            max(
                structural_stop,
                spot - stop_buffer,
            )
            if structural_stop is not None
            and structural_stop < spot
            else spot - stop_buffer
        )

        target_one = (
            inputs.positional_call_wall
            if inputs.positional_call_wall is not None
            and inputs.positional_call_wall > spot
            else spot + target_one_buffer
        )

        target_two = max(
            target_one + inputs.strike_step,
            spot + target_two_buffer,
        )

    else:
        structural_stop = (
            inputs.positional_call_wall
        )

        stop_loss = (
            min(
                structural_stop,
                spot + stop_buffer,
            )
            if structural_stop is not None
            and structural_stop > spot
            else spot + stop_buffer
        )

        target_one = (
            inputs.positional_put_wall
            if inputs.positional_put_wall is not None
            and inputs.positional_put_wall < spot
            else spot - target_one_buffer
        )

        target_two = min(
            target_one - inputs.strike_step,
            spot - target_two_buffer,
        )

    return {
        "entry_low": round(
            entry_low,
            2,
        ),
        "entry_high": round(
            entry_high,
            2,
        ),
        "stop_loss": round(
            stop_loss,
            2,
        ),
        "target_one": round(
            target_one,
            2,
        ),
        "target_two": round(
            target_two,
            2,
        ),
    }


def calculate_risk_reward(
    final_decision: str,
    spot_price: float,
    stop_loss: float | None,
    target_one: float | None,
    target_two: float | None,
) -> dict[str, float | None]:
    """
    Calculate estimated underlying risk-reward.
    """

    if (
        final_decision
        not in {
            "BUY CALL",
            "BUY PUT",
        }
        or stop_loss is None
        or target_one is None
        or target_two is None
    ):
        return {
            "risk_points": None,
            "reward_one_points": None,
            "reward_two_points": None,
            "risk_reward_one": None,
            "risk_reward_two": None,
        }

    risk_points = abs(
        spot_price - stop_loss
    )

    reward_one_points = abs(
        target_one - spot_price
    )

    reward_two_points = abs(
        target_two - spot_price
    )

    return {
        "risk_points": round(
            risk_points,
            2,
        ),
        "reward_one_points": round(
            reward_one_points,
            2,
        ),
        "reward_two_points": round(
            reward_two_points,
            2,
        ),
        "risk_reward_one": (
            round(
                safe_ratio(
                    reward_one_points,
                    risk_points,
                ),
                2,
            )
            if risk_points > 0
            else None
        ),
        "risk_reward_two": (
            round(
                safe_ratio(
                    reward_two_points,
                    risk_points,
                ),
                2,
            )
            if risk_points > 0
            else None
        ),
    }


# ============================================================
# INTERPRETATION
# ============================================================

def join_reasons(
    evidence_table: pd.DataFrame,
) -> str:
    """
    Join supporting reasons.
    """

    supporting = evidence_table[
        evidence_table[
            "supports_trade"
        ]
    ]

    if supporting.empty:
        return "No strong supporting evidence."

    reasons = [
        (
            f"{row.indicator}: "
            f"{row.reading}"
        )
        for row in supporting.itertuples()
    ]

    return " | ".join(reasons)


def join_warnings(
    evidence_table: pd.DataFrame,
) -> str:
    """
    Join risk warnings.
    """

    warnings = evidence_table[
        evidence_table["warning"]
    ]

    if warnings.empty:
        return "No major warning detected."

    warning_text = [
        (
            f"{row.indicator}: "
            f"{row.reading}"
        )
        for row in warnings.itertuples()
    ]

    return " | ".join(
        warning_text
    )


def build_interpretation(
    result: DecisionResult,
) -> str:
    """
    Build the final decision interpretation.
    """

    text = (
        f"AQSD decision is {result.final_decision}. "
        f"The directional bias is "
        f"{result.decision_bias.lower()} with "
        f"{result.confidence_score:.1f}% confidence. "
        f"Trade grade is {result.trade_grade} "
        f"and risk is {result.risk_level.lower()}. "
        f"Bullish probability is "
        f"{result.bullish_probability:.1f}% versus "
        f"{result.bearish_probability:.1f}% bearish. "
        f"Continuation probability is "
        f"{result.continuation_probability:.1f}% and "
        f"reversal probability is "
        f"{result.reversal_probability:.1f}%."
    )

    if result.entry_low is not None:
        text += (
            f" Analytical entry zone is "
            f"{result.entry_low:,.0f} to "
            f"{result.entry_high:,.0f}, "
            f"with stop at "
            f"{result.stop_loss:,.0f}, "
            f"target one at "
            f"{result.target_one:,.0f} and "
            f"target two at "
            f"{result.target_two:,.0f}."
        )

    return text


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_decision(
    inputs: DecisionInputs,
) -> tuple[
    DecisionResult,
    pd.DataFrame,
]:
    """
    Run the AQSD Option Decision Engine.
    """

    evidence = build_all_evidence(
        inputs
    )

    evidence_table = evidence_to_dataframe(
        evidence
    )

    bullish_points = float(
        evidence_table[
            "bullish_points"
        ].sum()
    )

    bearish_points = float(
        evidence_table[
            "bearish_points"
        ].sum()
    )

    warning_count = int(
        evidence_table[
            "warning"
        ].sum()
    )

    final_decision, decision_bias = (
        determine_final_decision(
            inputs=inputs,
            bullish_points=bullish_points,
            bearish_points=bearish_points,
            warning_count=warning_count,
        )
    )

    trade_grade = determine_trade_grade(
        confidence_score=(
            inputs.confidence_score
        ),
        directional_edge=(
            inputs.directional_edge
        ),
        warning_count=warning_count,
    )

    trade_quality = determine_trade_quality(
        trade_grade
    )

    risk_level = determine_risk_level(
        inputs=inputs,
        warning_count=warning_count,
    )

    levels = calculate_trade_levels(
        inputs=inputs,
        final_decision=final_decision,
    )

    risk_reward = calculate_risk_reward(
        final_decision=final_decision,
        spot_price=inputs.spot_price,
        stop_loss=levels["stop_loss"],
        target_one=levels["target_one"],
        target_two=levels["target_two"],
    )

    supporting_reasons = join_reasons(
        evidence_table
    )

    risk_warnings = join_warnings(
        evidence_table
    )

    result = DecisionResult(
        underlying=inputs.underlying,
        spot_price=inputs.spot_price,
        atm_strike=inputs.atm_strike,

        final_decision=final_decision,
        decision_bias=decision_bias,

        confidence_score=(
            inputs.confidence_score
        ),
        trade_grade=trade_grade,
        trade_quality=trade_quality,

        market_regime=(
            inputs.market_regime
        ),
        risk_level=risk_level,

        entry_low=levels["entry_low"],
        entry_high=levels["entry_high"],

        stop_loss=levels["stop_loss"],
        target_one=levels["target_one"],
        target_two=levels["target_two"],

        estimated_risk_points=(
            risk_reward["risk_points"]
        ),
        estimated_reward_one_points=(
            risk_reward[
                "reward_one_points"
            ]
        ),
        estimated_reward_two_points=(
            risk_reward[
                "reward_two_points"
            ]
        ),

        risk_reward_one=(
            risk_reward[
                "risk_reward_one"
            ]
        ),
        risk_reward_two=(
            risk_reward[
                "risk_reward_two"
            ]
        ),

        bullish_probability=(
            inputs.bullish_probability
        ),
        bearish_probability=(
            inputs.bearish_probability
        ),
        continuation_probability=(
            inputs.continuation_probability
        ),
        reversal_probability=(
            inputs.reversal_probability
        ),

        supporting_reasons=(
            supporting_reasons
        ),
        risk_warnings=risk_warnings,
        interpretation="",

        timestamp=inputs.timestamp,
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

def print_decision_summary(
    result: DecisionResult,
) -> None:
    """
    Print the final decision.
    """

    separator = "=" * 76

    print()
    print(separator)
    print(
        "AQSD OPTION INTELLIGENCE — DECISION ENGINE"
    )
    print(separator)

    print(
        f"Underlying                 : "
        f"{result.underlying}"
    )

    print(
        f"Spot Price                 : "
        f"{result.spot_price:,.2f}"
    )

    print(
        f"FINAL DECISION             : "
        f"{result.final_decision}"
    )

    print(
        f"Decision Bias              : "
        f"{result.decision_bias}"
    )

    print(
        f"Confidence                 : "
        f"{result.confidence_score:.2f}%"
    )

    print(
        f"Trade Grade                : "
        f"{result.trade_grade}"
    )

    print(
        f"Trade Quality              : "
        f"{result.trade_quality}"
    )

    print(
        f"Market Regime              : "
        f"{result.market_regime}"
    )

    print(
        f"Risk Level                 : "
        f"{result.risk_level}"
    )

    print(
        f"Entry Zone                 : "
        f"{format_optional(result.entry_low)}"
        f" to "
        f"{format_optional(result.entry_high)}"
    )

    print(
        f"Stop Loss                  : "
        f"{format_optional(result.stop_loss)}"
    )

    print(
        f"Target 1                   : "
        f"{format_optional(result.target_one)}"
    )

    print(
        f"Target 2                   : "
        f"{format_optional(result.target_two)}"
    )

    print(
        f"Risk-Reward 1              : "
        f"1 : "
        f"{format_optional(result.risk_reward_one)}"
    )

    print(
        f"Risk-Reward 2              : "
        f"1 : "
        f"{format_optional(result.risk_reward_two)}"
    )

    print()
    print("Supporting Reasons")
    print("-" * 76)
    print(result.supporting_reasons)

    print()
    print("Risk Warnings")
    print("-" * 76)
    print(result.risk_warnings)

    print()
    print("Interpretation")
    print("-" * 76)
    print(result.interpretation)

    print(separator)
    print()


# ============================================================
# SAMPLE TEST
# ============================================================

def create_sample_decision_inputs() -> DecisionInputs:
    """
    Create sample Decision Engine inputs.
    """

    return DecisionInputs(
        underlying="BANKNIFTY_SAMPLE",
        spot_price=57582.25,
        atm_strike=57600.0,
        strike_step=100.0,
        timestamp=pd.Timestamp.now(
            tz="Asia/Kolkata"
        ).isoformat(),

        bullish_probability=34.0,
        bearish_probability=66.0,

        continuation_probability=64.0,
        reversal_probability=36.0,

        confidence_score=72.0,
        directional_edge=32.0,

        directional_bias="STRONGLY BEARISH",
        market_regime="TRENDING",
        probability_action="SELL BIAS",
        probability_grade="A",

        modified_pcr=0.72,
        pcr_trend="FALLING",
        pcr_bias="BEARISH",
        reversal_watch=(
            "NO EXTREME PCR SIGNAL"
        ),

        positional_call_wall=58500.0,
        positional_put_wall=57000.0,

        fresh_call_wall=58000.0,
        fresh_put_wall=57000.0,

        combined_wall_shift=(
            "RANGE SHIFTED DOWN"
        ),
        breakout_watch=(
            "NO IMMEDIATE BREAKOUT TEST"
        ),
        breakdown_watch=(
            "PUT WALL TEST APPROACHING"
        ),

        max_pain_strike=58000.0,
        pinning_probability=52.0,
        expiry_bias=(
            "BULLISH PINNING PULL"
        ),
        magnet_strength="MODERATE",

        atm_iv=18.5,
        historical_volatility=14.2,
        iv_rank=58.0,
        iv_percentile=72.0,

        volatility_trend="RISING",
        volatility_regime=(
            "ELEVATED VOLATILITY"
        ),
        volatility_signal=(
            "VOLATILITY EXPANSION"
        ),
        skew_signal=(
            "MODERATE DOWNSIDE HEDGE DEMAND"
        ),
    )


def main() -> None:
    """
    Run the independent Decision Engine test.
    """

    inputs = create_sample_decision_inputs()

    result, evidence_table = (
        analyze_decision(
            inputs
        )
    )

    print_decision_summary(
        result
    )

    metadata = ExportMetadata(
        engine="DECISION",
        underlying=inputs.underlying,
        engine_version="1.0",
        rows_processed=len(
            evidence_table
        ),
        status="SUCCESS",
        source=(
            "AQSD Sample Option Intelligence"
        ),
        notes=(
            "Independent decision_engine.py test."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "underlying": result.underlying,
        "spot_price": result.spot_price,
        "final_decision": (
            result.final_decision
        ),
        "decision_bias": (
            result.decision_bias
        ),
        "confidence_score": (
            result.confidence_score
        ),
        "trade_grade": (
            result.trade_grade
        ),
        "trade_quality": (
            result.trade_quality
        ),
        "risk_level": (
            result.risk_level
        ),
        "entry_low": result.entry_low,
        "entry_high": result.entry_high,
        "stop_loss": result.stop_loss,
        "target_one": result.target_one,
        "target_two": result.target_two,
        "risk_reward_one": (
            result.risk_reward_one
        ),
        "risk_reward_two": (
            result.risk_reward_two
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
            "BANKNIFTY_SAMPLE_DECISION"
        ),
    )

    print_export_report(
        export_paths
    )


if __name__ == "__main__":
    main()