"""
AQSD
Market Master Decision Engine

Module : MMD-001
Version: 1.1.0
Author : AQSD

Description
-----------
Consumes the complete AQSD Market Intelligence Daily Pipeline and
produces one explainable final market assessment.

Inputs
------
1. Participant Daily Pipeline
2. Market Breadth Decision Engine
3. Sector Intelligence Daily Pipeline
4. Market Regime Engine

Outputs
-------
- Final Market Bias
- Market Regime
- Institutional View
- Breadth View
- Sector View
- Risk Level
- Expected Behaviour
- Trading Environment
- Analytical Posture
- Bullish Probability
- Bearish Probability
- Neutral Probability
- Confidence
- Decision Grade
- Confirmation Conditions
- Invalidation Conditions
- Warnings
- Explanation
- Final Conclusion

Important
---------
This engine provides analytical decision support only.

It does not generate BUY, SELL or SHORT orders.
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

from Scripts.aqsd_core.trading_calendar import latest_trading_day
from Scripts.aqsd_market_intelligence_pipeline import (
    DEFAULT_BREADTH_INPUT_FILE,
    DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
    MarketIntelligencePipelineResult,
    run_market_intelligence_pipeline,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MMD-001"
MODULE_VERSION: Final[str] = "1.1.0"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class MarketMasterDecisionResult:
    """
    Final AQSD market decision result.
    """

    requested_date: date | None
    analysis_date: date

    final_market_bias: str
    primary_regime: str
    secondary_regime: str

    institutional_view: str
    breadth_view: str
    sector_view: str

    trend_environment: str
    options_environment: str

    structural_quality: str
    participation_quality: str
    institutional_alignment: str

    risk_level: str
    risk_posture: str

    bullish_probability: float
    bearish_probability: float
    neutral_probability: float

    expected_behaviour: str
    trading_environment: str
    analytical_posture: str

    confidence: int
    decision_grade: str
    decision_status: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    concise_summary: str
    explanation: str
    final_conclusion: str

    pipeline_status: str
    market_regime_status: str
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


def normalize_text(
    value: object,
    default: str = "UNKNOWN",
) -> str:
    """
    Normalize text to uppercase.
    """

    if value is None:
        return default

    text = str(value).strip().upper()

    return text or default


def safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float safely.
    """

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def safe_int(
    value: object,
    default: int = 0,
) -> int:
    """
    Convert a value to integer safely.
    """

    return int(
        round(
            safe_float(
                value,
                float(default),
            )
        )
    )


def contains_any(
    value: str,
    keywords: tuple[str, ...],
) -> bool:
    """
    Return True when text contains any keyword.
    """

    normalized = normalize_text(
        value,
        "",
    )

    return any(
        keyword.upper() in normalized
        for keyword in keywords
    )


def first_attribute(
    result: object,
    names: tuple[str, ...],
    default: object = None,
) -> object:
    """
    Return the first available object attribute.
    """

    for name in names:
        if hasattr(
            result,
            name,
        ):
            return getattr(
                result,
                name,
            )

    return default


def call_with_supported_arguments(
    function: Any,
    arguments: dict[str, object],
) -> Any:
    """
    Call a function using supported keyword arguments only.
    """

    signature = inspect.signature(
        function
    )

    supported_arguments = {
        name: value
        for name, value in arguments.items()
        if name in signature.parameters
    }

    return function(
        **supported_arguments
    )


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


def select_trade_date(
    requested_date: date | None,
) -> date:
    """
    Select the latest valid trading day.
    """

    reference_date = (
        requested_date
        if requested_date is not None
        else date.today()
    )

    return latest_trading_day(
        reference_date
    )


# ==========================================================
# MARKET REGIME RESULT
# ==========================================================

def obtain_market_regime_result(
    *,
    pipeline_result: MarketIntelligencePipelineResult,
) -> object:
    """
    Return the complete Market Regime result already produced by
    the Market Intelligence Pipeline.

    The Market Regime Engine must execute only once. The pipeline
    retains its full Stage-4 result in ``regime_result`` specifically
    for downstream consumers such as this Master Decision Engine.
    """

    regime_result = getattr(
        pipeline_result,
        "regime_result",
        None,
    )

    if regime_result is None:
        raise RuntimeError(
            "The Market Intelligence Pipeline did not return a full "
            "Market Regime result. Stage 4 may not have completed."
        )

    return regime_result


# ==========================================================
# FINAL MARKET BIAS
# ==========================================================

def determine_final_market_bias(
    *,
    market_direction: str,
    primary_regime: str,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> str:
    """
    Determine the final AQSD market bias.
    """

    direction = normalize_text(
        market_direction
    )

    regime = normalize_text(
        primary_regime
    )

    if (
        direction == "STRONGLY BULLISH"
        and bullish_probability >= 60
    ):
        return "STRONGLY BULLISH"

    if (
        direction == "BULLISH"
        and bullish_probability >= 45
    ):
        if contains_any(
            regime,
            (
                "RECOVERY",
                "SHORT COVERING",
            ),
        ):
            return "BULLISH RECOVERY"

        return "BULLISH"

    if (
        direction == "STRONGLY BEARISH"
        and bearish_probability >= 60
    ):
        return "STRONGLY BEARISH"

    if (
        direction == "BEARISH"
        and bearish_probability >= 45
    ):
        if contains_any(
            regime,
            (
                "RECOVERY",
                "SHORT COVERING",
            ),
        ):
            return "BEARISH WITH RECOVERY RISK"

        return "BEARISH"

    if neutral_probability >= 45:
        return "NEUTRAL"

    if bullish_probability > bearish_probability:
        return "MIXED WITH BULLISH TILT"

    if bearish_probability > bullish_probability:
        return "MIXED WITH BEARISH TILT"

    return "MIXED"


# ==========================================================
# QUALITY CLASSIFICATION
# ==========================================================

def determine_structural_quality(
    *,
    regime_strength: str,
    regime_alignment: str,
    regime_maturity: str,
) -> str:
    """
    Determine consolidated regime quality.
    """

    score = 0

    if regime_strength == "VERY STRONG":
        score += 4

    elif regime_strength == "STRONG":
        score += 3

    elif regime_strength == "MODERATE":
        score += 2

    elif regime_strength == "WEAK TO MODERATE":
        score += 1

    if regime_alignment == "VERY HIGH ALIGNMENT":
        score += 4

    elif regime_alignment == "HIGH ALIGNMENT":
        score += 3

    elif regime_alignment == "MODERATE ALIGNMENT":
        score += 2

    if regime_maturity in {
        "DEVELOPING",
        "MATURE",
    }:
        score += 2

    elif regime_maturity == "EARLY":
        score += 1

    if score >= 9:
        return "VERY HIGH"

    if score >= 7:
        return "HIGH"

    if score >= 5:
        return "MODERATE"

    if score >= 3:
        return "LOW TO MODERATE"

    return "LOW"


def determine_participation_quality(
    *,
    breadth_status: str,
    breadth_bias: str,
    sector_status: str,
    sector_bias: str,
) -> str:
    """
    Determine breadth and sector participation quality.
    """

    score = 0

    if breadth_status.startswith(
        "SUCCESS"
    ):
        score += 2

    if sector_status.startswith(
        "SUCCESS"
    ):
        score += 2

    if contains_any(
        breadth_bias,
        (
            "BULLISH",
            "CONSTRUCTIVE",
            "IMPROVING",
            "POSITIVE",
        ),
    ):
        score += 2

    elif contains_any(
        breadth_bias,
        (
            "BEARISH",
            "WEAK",
            "DETERIORATING",
            "NEGATIVE",
        ),
    ):
        score += 1

    if contains_any(
        sector_bias,
        (
            "BULLISH",
            "CONSTRUCTIVE",
            "POSITIVE",
        ),
    ):
        score += 2

    elif contains_any(
        sector_bias,
        (
            "BEARISH",
            "DETERIORATING",
            "NEGATIVE",
        ),
    ):
        score += 1

    if score >= 7:
        return "HIGH"

    if score >= 5:
        return "MODERATE"

    if score >= 3:
        return "LOW TO MODERATE"

    return "LOW"


def determine_institutional_alignment(
    *,
    institutional_view: str,
    final_market_bias: str,
) -> str:
    """
    Determine institutional alignment with the market conclusion.
    """

    institutional = normalize_text(
        institutional_view
    )

    market_bias = normalize_text(
        final_market_bias
    )

    institutional_bullish = contains_any(
        institutional,
        (
            "BULLISH",
            "LONG",
            "RECOVERY",
            "SHORT COVERING",
            "IMPROVING",
        ),
    )

    institutional_bearish = contains_any(
        institutional,
        (
            "BEARISH",
            "SHORT BUILD",
            "DISTRIBUTION",
            "DETERIORATING",
        ),
    )

    market_bullish = contains_any(
        market_bias,
        (
            "BULLISH",
        ),
    )

    market_bearish = contains_any(
        market_bias,
        (
            "BEARISH",
        ),
    )

    if (
        institutional_bullish
        and market_bullish
    ):
        return "BULLISH ALIGNMENT"

    if (
        institutional_bearish
        and market_bearish
    ):
        return "BEARISH ALIGNMENT"

    if (
        institutional_bullish
        and market_bearish
    ):
        return "CONFLICTING — INSTITUTIONAL RECOVERY"

    if (
        institutional_bearish
        and market_bullish
    ):
        return "CONFLICTING — BEARISH EXPOSURE REMAINS"

    return "MIXED INSTITUTIONAL ALIGNMENT"


# ==========================================================
# RISK POSTURE
# ==========================================================

def determine_risk_posture(
    *,
    risk_level: str,
    final_market_bias: str,
    confidence: int,
) -> str:
    """
    Determine how aggressively the conclusion should be used.
    """

    if risk_level == "VERY HIGH":
        return (
            "DEFENSIVE — REQUIRE STRONG MULTI-ENGINE "
            "CONFIRMATION"
        )

    if risk_level == "HIGH":
        return (
            "CAUTIOUS — EXPECT SHARP TWO-SIDED MOVES "
            "AND REVERSAL RISK"
        )

    if confidence < 55:
        return (
            "CONSERVATIVE — DIRECTIONAL CONFIDENCE "
            "REMAINS LIMITED"
        )

    if contains_any(
        final_market_bias,
        (
            "MIXED",
            "NEUTRAL",
        ),
    ):
        return (
            "SELECTIVE — PREFER CONFIRMED SECTOR OR "
            "STOCK-SPECIFIC OPPORTUNITIES"
        )

    if risk_level in {
        "LOW",
        "LOW TO MODERATE",
    }:
        return (
            "NORMAL — USE STANDARD AQSD CONFIRMATION "
            "AND RISK CONTROLS"
        )

    return (
        "MODERATE — CROSS-CHECK PRICE, BREADTH, "
        "PARTICIPANT AND OPTIONS DATA"
    )


# ==========================================================
# TRADING ENVIRONMENT
# ==========================================================

def determine_trading_environment(
    *,
    final_market_bias: str,
    primary_regime: str,
    risk_level: str,
    confidence: int,
) -> str:
    """
    Describe the analytical trading environment.

    This is not an order instruction.
    """

    if contains_any(
        final_market_bias,
        (
            "STRONGLY BULLISH",
        ),
    ):
        return (
            "HIGH-QUALITY POSITIVE ENVIRONMENT; "
            "PULLBACKS MAY REMAIN CONSTRUCTIVE"
        )

    if final_market_bias == "BULLISH":
        return (
            "POSITIVE ENVIRONMENT WITH NORMAL "
            "CONFIRMATION REQUIREMENTS"
        )

    if final_market_bias == "BULLISH RECOVERY":
        return (
            "RECOVERY ENVIRONMENT; POSITIVE MOMENTUM MAY "
            "CONTINUE BUT REVERSALS CAN REMAIN SHARP"
        )

    if contains_any(
        final_market_bias,
        (
            "STRONGLY BEARISH",
        ),
    ):
        return (
            "HIGH-QUALITY DEFENSIVE ENVIRONMENT; "
            "RECOVERIES MAY REMAIN VULNERABLE"
        )

    if final_market_bias == "BEARISH":
        return (
            "DEFENSIVE ENVIRONMENT WITH CONTINUATION "
            "RISK"
        )

    if contains_any(
        final_market_bias,
        (
            "MIXED",
            "NEUTRAL",
        ),
    ):
        return (
            "ROTATIONAL OR RANGE-BOUND ENVIRONMENT; "
            "SECTOR SELECTION IS MORE IMPORTANT THAN "
            "BROAD DIRECTION"
        )

    if risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        return (
            "UNSTABLE ENVIRONMENT WITH HIGH REVERSAL "
            "AND VOLATILITY RISK"
        )

    if confidence < 55:
        return (
            "LOW-CONFIDENCE ENVIRONMENT; WAIT FOR "
            "ADDITIONAL ALIGNMENT"
        )

    return (
        f"{primary_regime} WITH STANDARD AQSD "
        "CONFIRMATION REQUIREMENTS"
    )


# ==========================================================
# DECISION CONFIDENCE
# ==========================================================

def calculate_master_confidence(
    *,
    regime_confidence: int,
    pipeline_result: MarketIntelligencePipelineResult,
    structural_quality: str,
    participation_quality: str,
    institutional_alignment: str,
) -> int:
    """
    Calculate the final Master Decision confidence.
    """

    confidence = float(
        regime_confidence
    )

    if pipeline_result.completed_stages == (
        pipeline_result.total_stages
    ):
        confidence += 5

    if pipeline_result.failed_stages > 0:
        confidence -= (
            pipeline_result.failed_stages
            * 8
        )

    if pipeline_result.limited_stages > 0:
        confidence -= (
            pipeline_result.limited_stages
            * 3
        )

    if structural_quality in {
        "VERY HIGH",
        "HIGH",
    }:
        confidence += 6

    elif structural_quality == "LOW":
        confidence -= 6

    if participation_quality == "HIGH":
        confidence += 5

    elif participation_quality == "LOW":
        confidence -= 5

    if contains_any(
        institutional_alignment,
        (
            "BULLISH ALIGNMENT",
            "BEARISH ALIGNMENT",
        ),
    ):
        confidence += 5

    elif "CONFLICTING" in institutional_alignment:
        confidence -= 7

    return clamp_score(
        confidence
    )


def determine_decision_grade(
    *,
    confidence: int,
    structural_quality: str,
    participation_quality: str,
    risk_level: str,
    pipeline_status: str,
) -> str:
    """
    Convert the Master Decision into an AQSD grade.
    """

    if (
        confidence >= 82
        and structural_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and participation_quality == "HIGH"
        and risk_level not in {
            "HIGH",
            "VERY HIGH",
        }
        and pipeline_status == "SUCCESS"
    ):
        return "A"

    if (
        confidence >= 70
        and structural_quality in {
            "HIGH",
            "MODERATE",
        }
        and risk_level != "VERY HIGH"
    ):
        return "B"

    if confidence >= 55:
        return "C"

    return "D"


def determine_decision_status(
    *,
    final_market_bias: str,
    confidence: int,
    decision_grade: str,
) -> str:
    """
    Determine the usability of the final conclusion.
    """

    if decision_grade == "A":
        return "HIGH-CONFIDENCE ANALYTICAL DECISION"

    if decision_grade == "B":
        return "CONFIRMED ANALYTICAL DECISION"

    if decision_grade == "C":
        return "CONDITIONAL ANALYTICAL DECISION"

    if contains_any(
        final_market_bias,
        (
            "MIXED",
            "NEUTRAL",
        ),
    ):
        return "NO CLEAR DIRECTIONAL EDGE"

    if confidence < 45:
        return "INSUFFICIENT CONFIDENCE"

    return "LOW-CONFIDENCE ANALYTICAL DECISION"


# ==========================================================
# CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    final_market_bias: str,
    regime_conditions: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Build Master Decision confirmation conditions.
    """

    conditions = list(
        regime_conditions
    )

    if contains_any(
        final_market_bias,
        (
            "BULLISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "The bullish market-regime probability should "
                    "remain greater than the bearish probability."
                ),
                (
                    "Market breadth and sector participation should "
                    "not deteriorate materially."
                ),
                (
                    "Institutional recovery or positive positioning "
                    "should continue."
                ),
            ]
        )

    elif contains_any(
        final_market_bias,
        (
            "BEARISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "The bearish market-regime probability should "
                    "remain greater than the bullish probability."
                ),
                (
                    "Market breadth and sector participation should "
                    "remain weak."
                ),
                (
                    "Institutional bearish exposure should remain "
                    "dominant."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "A clear directional majority should develop "
                    "across market breadth, sectors and participants."
                ),
                (
                    "Market-regime confidence should rise above 60%."
                ),
            ]
        )

    return tuple(
        dict.fromkeys(
            conditions
        )
    )


def build_invalidation_conditions(
    *,
    final_market_bias: str,
    regime_conditions: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Build Master Decision invalidation conditions.
    """

    conditions = list(
        regime_conditions
    )

    if contains_any(
        final_market_bias,
        (
            "BULLISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "The final market direction changes to bearish."
                ),
                (
                    "Breadth reverses from improvement to broad "
                    "deterioration."
                ),
                (
                    "Institutional positioning changes materially "
                    "against the recovery."
                ),
            ]
        )

    elif contains_any(
        final_market_bias,
        (
            "BEARISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "The final market direction changes to bullish."
                ),
                (
                    "Breadth improves into broad positive "
                    "participation."
                ),
                (
                    "Institutional short exposure reduces sharply."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "A persistent bullish alignment invalidates the "
                    "mixed conclusion."
                ),
                (
                    "A persistent bearish alignment invalidates the "
                    "mixed conclusion."
                ),
            ]
        )

    return tuple(
        dict.fromkeys(
            conditions
        )
    )


def build_warnings(
    *,
    pipeline_result: MarketIntelligencePipelineResult,
    regime_warnings: tuple[str, ...],
    institutional_alignment: str,
    confidence: int,
) -> tuple[str, ...]:
    """
    Build final Master Decision warnings.
    """

    warnings: list[str] = []

    warnings.extend(
        pipeline_result.warnings
    )

    warnings.extend(
        regime_warnings
    )

    if "CONFLICTING" in institutional_alignment:
        warnings.append(
            "Institutional positioning conflicts with the final "
            "market direction."
        )

    if confidence < 55:
        warnings.append(
            "Master Decision confidence is below 55%."
        )

    if pipeline_result.failed_stages > 0:
        warnings.append(
            "One or more Market Intelligence stages failed."
        )

    if pipeline_result.limited_stages > 0:
        warnings.append(
            "Historical confirmation remains limited in one or "
            "more intelligence stages."
        )

    if not warnings:
        warnings.append(
            "No major AQSD Master Decision warning is active."
        )

    return tuple(
        dict.fromkeys(
            warnings
        )
    )


# ==========================================================
# FINAL CONCLUSION
# ==========================================================

def determine_final_conclusion(
    *,
    final_market_bias: str,
    primary_regime: str,
    institutional_alignment: str,
    structural_quality: str,
    risk_level: str,
    confidence: int,
    decision_grade: str,
) -> str:
    """
    Build the final AQSD analytical conclusion.
    """

    if (
        final_market_bias == "STRONGLY BULLISH"
        and decision_grade in {
            "A",
            "B",
        }
    ):
        return (
            "HIGH-QUALITY BULLISH MARKET ENVIRONMENT. "
            "REGIME, PARTICIPATION AND INSTITUTIONAL "
            "INTELLIGENCE ARE SUFFICIENTLY ALIGNED."
        )

    if final_market_bias in {
        "BULLISH",
        "BULLISH RECOVERY",
    }:
        return (
            f"CONDITIONAL POSITIVE MARKET ENVIRONMENT. "
            f"THE PRIMARY REGIME IS {primary_regime}, "
            f"STRUCTURAL QUALITY IS {structural_quality}, "
            f"INSTITUTIONAL ALIGNMENT IS "
            f"{institutional_alignment}, AND RISK IS "
            f"{risk_level}. THE VIEW REQUIRES CONTINUED "
            f"CONFIRMATION."
        )

    if (
        final_market_bias == "STRONGLY BEARISH"
        and decision_grade in {
            "A",
            "B",
        }
    ):
        return (
            "HIGH-QUALITY BEARISH MARKET ENVIRONMENT. "
            "REGIME, PARTICIPATION AND INSTITUTIONAL "
            "INTELLIGENCE SUPPORT DEFENSIVE CONDITIONS."
        )

    if contains_any(
        final_market_bias,
        (
            "BEARISH",
        ),
    ):
        return (
            f"CONDITIONAL DEFENSIVE MARKET ENVIRONMENT. "
            f"THE PRIMARY REGIME IS {primary_regime}, "
            f"STRUCTURAL QUALITY IS {structural_quality}, "
            f"AND RISK IS {risk_level}. RECOVERY RISK "
            f"SHOULD CONTINUE TO BE MONITORED."
        )

    return (
        f"THE MARKET ENVIRONMENT IS {final_market_bias}. "
        f"THE PRIMARY REGIME IS {primary_regime}, "
        f"CONFIDENCE IS {confidence}% AND DECISION GRADE "
        f"IS {decision_grade}. NO STRONG BROAD-MARKET "
        f"DIRECTIONAL EDGE IS CONFIRMED."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_market_master_decision_engine(
    *,
    requested_date: date | None = None,
    breadth_source_file: Path = (
        DEFAULT_BREADTH_INPUT_FILE
    ),
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
) -> MarketMasterDecisionResult:
    """
    Run the complete AQSD Market Master Decision Engine.
    """

    selected_trade_date = select_trade_date(
        requested_date
    )

    source_file = (
        breadth_source_file
        .expanduser()
        .resolve()
    )

    if weekly_lookback_sessions < 1:
        raise ValueError(
            "weekly_lookback_sessions must be at least 1."
        )

    if not source_file.exists():
        raise FileNotFoundError(
            f"Market breadth input file not found: {source_file}"
        )

    pipeline_result = run_market_intelligence_pipeline(
        requested_date=selected_trade_date,
        breadth_source_file=source_file,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    regime_result = obtain_market_regime_result(
        pipeline_result=pipeline_result,
    )

    primary_regime = normalize_text(
        first_attribute(
            regime_result,
            (
                "primary_regime",
            ),
            "UNKNOWN",
        )
    )

    secondary_regime = normalize_text(
        first_attribute(
            regime_result,
            (
                "secondary_regime",
            ),
            "UNKNOWN",
        )
    )

    market_direction = normalize_text(
        first_attribute(
            regime_result,
            (
                "market_direction",
            ),
            "UNKNOWN",
        )
    )

    regime_strength = normalize_text(
        first_attribute(
            regime_result,
            (
                "regime_strength",
            ),
            "UNKNOWN",
        )
    )

    regime_alignment = normalize_text(
        first_attribute(
            regime_result,
            (
                "regime_alignment",
            ),
            "UNKNOWN",
        )
    )

    regime_maturity = normalize_text(
        first_attribute(
            regime_result,
            (
                "regime_maturity",
            ),
            "UNKNOWN",
        )
    )

    risk_level = normalize_text(
        first_attribute(
            regime_result,
            (
                "risk_environment",
            ),
            "NOT AVAILABLE",
        )
    )

    regime_confidence = safe_int(
        first_attribute(
            regime_result,
            (
                "confidence",
            ),
            0,
        )
    )

    bullish_probability = safe_float(
        first_attribute(
            regime_result,
            (
                "bullish_probability",
            ),
            0.0,
        )
    )

    bearish_probability = safe_float(
        first_attribute(
            regime_result,
            (
                "bearish_probability",
            ),
            0.0,
        )
    )

    neutral_probability = safe_float(
        first_attribute(
            regime_result,
            (
                "neutral_probability",
            ),
            0.0,
        )
    )

    final_market_bias = determine_final_market_bias(
        market_direction=market_direction,
        primary_regime=primary_regime,
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
    )

    institutional_view = (
        pipeline_result.participant_stage.bias
    )

    breadth_view = (
        pipeline_result.breadth_stage.bias
    )

    sector_view = (
        pipeline_result.sector_stage.bias
    )

    trend_environment = normalize_text(
        first_attribute(
            regime_result,
            (
                "trend_environment",
            ),
            "NOT YET CONNECTED",
        )
    )

    options_environment = normalize_text(
        first_attribute(
            regime_result,
            (
                "options_environment",
            ),
            "NOT YET CONNECTED",
        )
    )

    structural_quality = determine_structural_quality(
        regime_strength=regime_strength,
        regime_alignment=regime_alignment,
        regime_maturity=regime_maturity,
    )

    participation_quality = determine_participation_quality(
        breadth_status=(
            pipeline_result.breadth_stage.status
        ),
        breadth_bias=breadth_view,
        sector_status=(
            pipeline_result.sector_stage.status
        ),
        sector_bias=sector_view,
    )

    institutional_alignment = (
        determine_institutional_alignment(
            institutional_view=institutional_view,
            final_market_bias=final_market_bias,
        )
    )

    confidence = calculate_master_confidence(
        regime_confidence=regime_confidence,
        pipeline_result=pipeline_result,
        structural_quality=structural_quality,
        participation_quality=participation_quality,
        institutional_alignment=(
            institutional_alignment
        ),
    )

    decision_grade = determine_decision_grade(
        confidence=confidence,
        structural_quality=structural_quality,
        participation_quality=participation_quality,
        risk_level=risk_level,
        pipeline_status=(
            pipeline_result.overall_status
        ),
    )

    decision_status = determine_decision_status(
        final_market_bias=final_market_bias,
        confidence=confidence,
        decision_grade=decision_grade,
    )

    risk_posture = determine_risk_posture(
        risk_level=risk_level,
        final_market_bias=final_market_bias,
        confidence=confidence,
    )

    expected_behaviour = normalize_text(
        first_attribute(
            regime_result,
            (
                "expected_behaviour",
            ),
            "NOT AVAILABLE",
        )
    )

    trading_environment = determine_trading_environment(
        final_market_bias=final_market_bias,
        primary_regime=primary_regime,
        risk_level=risk_level,
        confidence=confidence,
    )

    analytical_posture = normalize_text(
        first_attribute(
            regime_result,
            (
                "analytical_posture",
            ),
            risk_posture,
        )
    )

    regime_confirmation_conditions = tuple(
        first_attribute(
            regime_result,
            (
                "confirmation_conditions",
            ),
            (),
        )
    )

    regime_invalidation_conditions = tuple(
        first_attribute(
            regime_result,
            (
                "invalidation_conditions",
            ),
            (),
        )
    )

    regime_warnings = tuple(
        first_attribute(
            regime_result,
            (
                "warnings",
            ),
            (),
        )
    )

    confirmation_conditions = (
        build_confirmation_conditions(
            final_market_bias=final_market_bias,
            regime_conditions=(
                regime_confirmation_conditions
            ),
        )
    )

    invalidation_conditions = (
        build_invalidation_conditions(
            final_market_bias=final_market_bias,
            regime_conditions=(
                regime_invalidation_conditions
            ),
        )
    )

    warnings = build_warnings(
        pipeline_result=pipeline_result,
        regime_warnings=regime_warnings,
        institutional_alignment=(
            institutional_alignment
        ),
        confidence=confidence,
    )

    final_conclusion = determine_final_conclusion(
        final_market_bias=final_market_bias,
        primary_regime=primary_regime,
        institutional_alignment=(
            institutional_alignment
        ),
        structural_quality=structural_quality,
        risk_level=risk_level,
        confidence=confidence,
        decision_grade=decision_grade,
    )

    concise_summary = (
        f"{final_market_bias} | "
        f"{primary_regime} | "
        f"{institutional_alignment} | "
        f"{structural_quality} STRUCTURE | "
        f"{participation_quality} PARTICIPATION | "
        f"{risk_level} RISK | "
        f"BULL {bullish_probability:.1f}% | "
        f"BEAR {bearish_probability:.1f}% | "
        f"{confidence}% CONFIDENCE | "
        f"GRADE {decision_grade}"
    )

    explanation = (
        f"The AQSD Market Intelligence Pipeline completed with "
        f"status {pipeline_result.overall_status.lower()}. "
        f"The Market Regime Engine classified the market as "
        f"{primary_regime.lower()}, with secondary regime "
        f"{secondary_regime.lower()} and direction "
        f"{market_direction.lower()}. Bullish probability is "
        f"{bullish_probability:.1f}%, bearish probability is "
        f"{bearish_probability:.1f}% and neutral probability is "
        f"{neutral_probability:.1f}%. Institutional positioning is "
        f"classified as {institutional_view.lower()}, market breadth "
        f"as {breadth_view.lower()} and sector intelligence as "
        f"{sector_view.lower()}. Structural quality is "
        f"{structural_quality.lower()}, participation quality is "
        f"{participation_quality.lower()} and institutional alignment "
        f"is {institutional_alignment.lower()}. Consolidated risk is "
        f"{risk_level.lower()}. The final market bias is "
        f"{final_market_bias.lower()}, confidence is {confidence}% "
        f"and decision grade is {decision_grade}."
    )

    market_regime_status = normalize_text(
        first_attribute(
            regime_result,
            (
                "status",
            ),
            "UNKNOWN",
        )
    )

    if (
        pipeline_result.overall_status == "FAILED"
        or market_regime_status == "FAILED"
    ):
        overall_status = "FAILED"

    elif (
        "PARTIAL" in pipeline_result.overall_status
        or "PARTIAL" in market_regime_status
        or pipeline_result.limited_stages > 0
    ):
        overall_status = "SUCCESS WITH PARTIAL INPUTS"

    else:
        overall_status = "SUCCESS"

    return MarketMasterDecisionResult(
        requested_date=requested_date,
        analysis_date=selected_trade_date,

        final_market_bias=final_market_bias,
        primary_regime=primary_regime,
        secondary_regime=secondary_regime,

        institutional_view=institutional_view,
        breadth_view=breadth_view,
        sector_view=sector_view,

        trend_environment=trend_environment,
        options_environment=options_environment,

        structural_quality=structural_quality,
        participation_quality=participation_quality,
        institutional_alignment=(
            institutional_alignment
        ),

        risk_level=risk_level,
        risk_posture=risk_posture,

        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,

        expected_behaviour=expected_behaviour,
        trading_environment=trading_environment,
        analytical_posture=analytical_posture,

        confidence=confidence,
        decision_grade=decision_grade,
        decision_status=decision_status,

        confirmation_conditions=(
            confirmation_conditions
        ),
        invalidation_conditions=(
            invalidation_conditions
        ),
        warnings=warnings,

        concise_summary=concise_summary,
        explanation=explanation,
        final_conclusion=final_conclusion,

        pipeline_status=(
            pipeline_result.overall_status
        ),
        market_regime_status=(
            market_regime_status
        ),
        status=overall_status,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketMasterDecisionResult,
) -> None:
    """
    Display the complete AQSD Market Master Decision.
    """

    print()
    print("=" * 116)
    print("AQSD MARKET MASTER DECISION ENGINE")
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
    print("-" * 116)

    print("FINAL MARKET ASSESSMENT")
    print("-" * 116)
    print(
        f"Final Market Bias                   : "
        f"{result.final_market_bias}"
    )
    print(
        f"Primary Regime                      : "
        f"{result.primary_regime}"
    )
    print(
        f"Secondary Regime                    : "
        f"{result.secondary_regime}"
    )
    print(
        f"Institutional View                  : "
        f"{result.institutional_view}"
    )
    print(
        f"Market Breadth View                 : "
        f"{result.breadth_view}"
    )
    print(
        f"Sector View                         : "
        f"{result.sector_view}"
    )
    print("-" * 116)

    print("QUALITY AND ALIGNMENT")
    print("-" * 116)
    print(
        f"Structural Quality                  : "
        f"{result.structural_quality}"
    )
    print(
        f"Participation Quality               : "
        f"{result.participation_quality}"
    )
    print(
        f"Institutional Alignment             : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Trend Environment                   : "
        f"{result.trend_environment}"
    )
    print(
        f"Options Environment                 : "
        f"{result.options_environment}"
    )
    print("-" * 116)

    print("PROBABILITIES")
    print("-" * 116)
    print(
        f"Bullish Probability                 : "
        f"{result.bullish_probability:.1f}%"
    )
    print(
        f"Bearish Probability                 : "
        f"{result.bearish_probability:.1f}%"
    )
    print(
        f"Neutral Probability                 : "
        f"{result.neutral_probability:.1f}%"
    )
    print("-" * 116)

    print("RISK AND DECISION")
    print("-" * 116)
    print(
        f"Risk Level                          : "
        f"{result.risk_level}"
    )
    print(
        f"Risk Posture                        : "
        f"{result.risk_posture}"
    )
    print(
        f"Confidence                          : "
        f"{result.confidence}%"
    )
    print(
        f"Decision Grade                      : "
        f"{result.decision_grade}"
    )
    print(
        f"Decision Status                     : "
        f"{result.decision_status}"
    )
    print("-" * 116)

    print("EXPECTED BEHAVIOUR")
    print("-" * 116)
    print(
        result.expected_behaviour
    )

    print("-" * 116)
    print("TRADING ENVIRONMENT")
    print("-" * 116)
    print(
        result.trading_environment
    )

    print("-" * 116)
    print("ANALYTICAL POSTURE")
    print("-" * 116)
    print(
        result.analytical_posture
    )

    print("-" * 116)
    print("FINAL CONCLUSION")
    print("-" * 116)
    print(
        result.final_conclusion
    )

    print("-" * 116)
    print("CONCISE SUMMARY")
    print("-" * 116)
    print(
        result.concise_summary
    )

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
    print(
        result.explanation
    )

    print("-" * 116)
    print(
        f"Market Intelligence Status          : "
        f"{result.pipeline_status}"
    )
    print(
        f"Market Regime Status                : "
        f"{result.market_regime_status}"
    )
    print(
        f"Overall Status                      : "
        f"{result.status}"
    )
    print(
        "Method                              : "
        "RULE-BASED AQSD MARKET MASTER DECISION"
    )
    print("=" * 116)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the AQSD Market Master Decision Engine."
        )
    )

    parser.add_argument(
        "--date",
        required=False,
        help=(
            "Optional analysis date in YYYY-MM-DD format. "
            "When omitted, the latest trading day is selected."
        ),
    )

    parser.add_argument(
        "--breadth-input",
        type=Path,
        default=DEFAULT_BREADTH_INPUT_FILE,
        help=(
            "Path to the enriched market-breadth snapshot. "
            f"Default: {DEFAULT_BREADTH_INPUT_FILE}"
        ),
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
        help=(
            "Saved sessions used for weekly comparisons. "
            f"Default: {DEFAULT_WEEKLY_LOOKBACK_SESSIONS}."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    requested_date = (
        parse_date(
            arguments.date
        )
        if arguments.date
        else None
    )

    try:
        result = run_market_master_decision_engine(
            requested_date=requested_date,
            breadth_source_file=(
                arguments.breadth_input
                .expanduser()
                .resolve()
            ),
            weekly_lookback_sessions=(
                arguments.weekly_sessions
            ),
        )

    except Exception as exc:
        print()
        print("=" * 116)
        print("AQSD MARKET MASTER DECISION ENGINE")
        print("=" * 116)
        print("Status : FAILED")
        print(
            f"Reason : {exc}"
        )
        print("=" * 116)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()