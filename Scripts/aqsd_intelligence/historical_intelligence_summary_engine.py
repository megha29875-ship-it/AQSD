"""
AQSD
Historical Intelligence Summary Engine

Module : HIS-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Consolidate AQSD historical intelligence into one standardized
historical assessment.

Inputs
------
1. Market History Change Engine
2. Market History Trend / Persistence Engine

The engine combines:

- Session-to-session probability change
- Bias transition
- Regime transition
- Risk transition
- 5-session probability trend
- 10-session probability trend
- Bias persistence
- Regime persistence
- Directional consistency
- Historical maturity
- Historical quality
- Continuation evidence
- Reversal evidence

This engine does NOT:
- Call FYERS
- Download market data
- Re-run Market Master Decision
- Modify historical records
- Generate BUY / SELL / SHORT orders

Architecture
------------
Market History Recorder
        ↓
Market History Change Engine
        ↓
Market History Trend Engine
        ↓
Historical Intelligence Summary Engine
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from Scripts.aqsd_intelligence.market_history_change_engine import (
    MarketHistoryChangeResult,
    run_market_history_change_engine,
)

from Scripts.aqsd_intelligence.market_history_trend_engine import (
    MarketHistoryTrendResult,
    run_market_history_trend_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "HIS-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

HISTORY_FILE: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_History"
    / "market_intelligence_history.csv"
)


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class HistoricalIntelligenceSummaryResult:
    """
    Consolidated AQSD historical intelligence.
    """

    available: bool

    analysis_date: str
    total_sessions: int

    historical_bias: str
    historical_direction: str

    bias_transition: str
    regime_transition: str
    risk_transition: str

    directional_momentum: str
    intelligence_momentum: str

    bullish_trend: str
    bearish_trend: str
    neutral_trend: str
    confidence_trend: str

    bias_persistence_sessions: int
    regime_persistence_sessions: int

    bias_stability: str
    regime_stability: str
    directional_consistency: str

    continuation_evidence: str
    reversal_evidence: str

    continuation_score: int
    reversal_score: int

    historical_confidence: int
    historical_maturity: str
    historical_quality: str

    historical_environment: str

    concise_summary: str
    explanation: str

    warnings: tuple[str, ...]

    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def normalize_text(
    value: object,
) -> str:
    """
    Normalize text for rule-based comparison.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip().upper()


def clamp_score(
    value: float,
) -> int:
    """
    Restrict score to 0-100.
    """

    return max(
        0,
        min(
            100,
            int(
                round(
                    value
                )
            ),
        ),
    )


# ==========================================================
# DIRECTION HELPERS
# ==========================================================

def contains_bullish(
    value: object,
) -> bool:
    """
    Return True when text contains bullish characteristics.
    """

    text = normalize_text(
        value
    )

    bullish_terms = (
        "BULLISH",
        "RECOVERY",
        "IMPROVING",
        "RISING",
        "STRENGTHENING",
        "POSITIVE",
    )

    return any(
        term in text
        for term in bullish_terms
    )


def contains_bearish(
    value: object,
) -> bool:
    """
    Return True when text contains bearish characteristics.
    """

    text = normalize_text(
        value
    )

    bearish_terms = (
        "BEARISH",
        "DETERIORATING",
        "FALLING",
        "WEAKENING",
        "NEGATIVE",
    )

    return any(
        term in text
        for term in bearish_terms
    )


def contains_neutral(
    value: object,
) -> bool:
    """
    Return True when text is mixed/neutral.
    """

    text = normalize_text(
        value
    )

    neutral_terms = (
        "MIXED",
        "NEUTRAL",
        "STABLE",
        "TWO-SIDED",
    )

    return any(
        term in text
        for term in neutral_terms
    )


# ==========================================================
# HISTORICAL BIAS
# ==========================================================

def determine_historical_bias(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
) -> str:
    """
    Determine consolidated historical market bias.
    """

    bullish_points = 0
    bearish_points = 0

    if contains_bullish(
        change_result.directional_momentum
    ):
        bullish_points += 2

    if contains_bearish(
        change_result.directional_momentum
    ):
        bearish_points += 2

    if contains_bullish(
        change_result.intelligence_momentum
    ):
        bullish_points += 2

    if contains_bearish(
        change_result.intelligence_momentum
    ):
        bearish_points += 2

    if contains_bullish(
        trend_result.bullish_5d_trend
    ):
        bullish_points += 1

    if contains_bearish(
        trend_result.bullish_5d_trend
    ):
        bearish_points += 1

    if contains_bullish(
        trend_result.bearish_5d_trend
    ):
        bearish_points += 1

    if contains_bearish(
        trend_result.bearish_5d_trend
    ):
        bullish_points += 1

    consistency = normalize_text(
        trend_result.directional_consistency
    )

    if "BULLISH" in consistency:
        bullish_points += 2

    if "BEARISH" in consistency:
        bearish_points += 2

    if bullish_points >= bearish_points + 3:
        return "BULLISH"

    if bearish_points >= bullish_points + 3:
        return "BEARISH"

    if bullish_points > bearish_points:
        return "MIXED WITH BULLISH TILT"

    if bearish_points > bullish_points:
        return "MIXED WITH BEARISH TILT"

    return "NEUTRAL / MIXED"


# ==========================================================
# HISTORICAL DIRECTION
# ==========================================================

def determine_historical_direction(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
) -> str:
    """
    Determine whether historical intelligence is improving,
    deteriorating or remaining mixed.
    """

    momentum = normalize_text(
        change_result.intelligence_momentum
    )

    if "STRENGTHENING" in momentum:
        if "BULLISH" in momentum:
            return "BULLISH IMPROVEMENT"

        if "BEARISH" in momentum:
            return "BEARISH DETERIORATION"

    if "DETERIORATING" in momentum:
        return "DETERIORATING"

    bullish_trend = normalize_text(
        trend_result.bullish_5d_trend
    )

    bearish_trend = normalize_text(
        trend_result.bearish_5d_trend
    )

    if (
        "RISING" in bullish_trend
        and "RISING" not in bearish_trend
    ):
        return "IMPROVING"

    if (
        "RISING" in bearish_trend
        and "RISING" not in bullish_trend
    ):
        return "DETERIORATING"

    if (
        "STABLE" in bullish_trend
        and "STABLE" in bearish_trend
    ):
        return "STABLE"

    return "MIXED"


# ==========================================================
# CONTINUATION SCORE
# ==========================================================

def calculate_continuation_score(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
) -> int:
    """
    Score evidence that the current intelligence state may persist.

    This is analytical evidence, not a trade probability.
    """

    score = 0

    regime_persistence = (
        trend_result.regime_persistence_sessions
    )

    bias_persistence = (
        trend_result.bias_persistence_sessions
    )

    if regime_persistence >= 2:
        score += 15

    if regime_persistence >= 3:
        score += 10

    if regime_persistence >= 5:
        score += 10

    if bias_persistence >= 2:
        score += 10

    if bias_persistence >= 3:
        score += 10

    regime_stability = normalize_text(
        trend_result.regime_stability
    )

    if regime_stability == "VERY STABLE":
        score += 15

    elif regime_stability == "STABLE":
        score += 10

    bias_stability = normalize_text(
        trend_result.bias_stability
    )

    if bias_stability == "VERY STABLE":
        score += 10

    elif bias_stability == "STABLE":
        score += 5

    confidence_trend = normalize_text(
        trend_result.confidence_5d_trend
    )

    if "RISING" in confidence_trend:
        score += 10

    if (
        normalize_text(
            change_result.regime_transition
        )
        == "UNCHANGED"
    ):
        score += 10

    return clamp_score(
        score
    )


# ==========================================================
# REVERSAL SCORE
# ==========================================================

def calculate_reversal_score(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
) -> int:
    """
    Score evidence of historical regime/bias transition.

    This is analytical evidence, not a trading signal.
    """

    score = 0

    bias_transition = normalize_text(
        change_result.bias_transition
    )

    regime_transition = normalize_text(
        change_result.regime_transition
    )

    if (
        bias_transition
        not in {
            "",
            "UNCHANGED",
            "INSUFFICIENT HISTORY",
        }
    ):
        score += 20

    if (
        regime_transition
        not in {
            "",
            "UNCHANGED",
            "INSUFFICIENT HISTORY",
        }
    ):
        score += 25

    bullish_change = (
        change_result.bullish_change
    )

    bearish_change = (
        change_result.bearish_change
    )

    if abs(
        bullish_change
    ) >= 5:
        score += 10

    if abs(
        bearish_change
    ) >= 5:
        score += 10

    if (
        bullish_change >= 5
        and bearish_change <= -3
    ):
        score += 10

    if (
        bearish_change >= 5
        and bullish_change <= -3
    ):
        score += 10

    if (
        trend_result.regime_persistence_sessions
        <= 1
    ):
        score += 10

    if (
        trend_result.bias_persistence_sessions
        <= 1
    ):
        score += 5

    if normalize_text(
        trend_result.regime_stability
    ) == "UNSTABLE":
        score += 10

    return clamp_score(
        score
    )


# ==========================================================
# EVIDENCE CLASSIFICATION
# ==========================================================

def classify_evidence(
    score: int,
) -> str:
    """
    Convert evidence score into a qualitative category.
    """

    if score >= 75:
        return "VERY STRONG"

    if score >= 60:
        return "STRONG"

    if score >= 40:
        return "MODERATE"

    if score >= 20:
        return "LIMITED"

    return "WEAK"


# ==========================================================
# HISTORICAL CONFIDENCE
# ==========================================================

def calculate_historical_confidence(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
) -> int:
    """
    Calculate confidence in historical assessment.

    Confidence depends primarily on history depth and consistency.
    """

    sessions = (
        trend_result.total_sessions
    )

    if sessions < 2:
        return 0

    score = 20

    if sessions >= 3:
        score += 10

    if sessions >= 5:
        score += 15

    if sessions >= 10:
        score += 15

    if sessions >= 20:
        score += 10

    if sessions >= 60:
        score += 10

    consistency = normalize_text(
        trend_result.directional_consistency
    )

    if "CONSISTENTLY" in consistency:
        score += 10

    elif "LEAN" in consistency:
        score += 5

    regime_stability = normalize_text(
        trend_result.regime_stability
    )

    if regime_stability == "VERY STABLE":
        score += 10

    elif regime_stability == "STABLE":
        score += 5

    if normalize_text(
        change_result.status
    ) == "SUCCESS":
        score += 5

    return clamp_score(
        score
    )


# ==========================================================
# HISTORICAL ENVIRONMENT
# ==========================================================

def determine_historical_environment(
    *,
    historical_bias: str,
    historical_direction: str,
    continuation_evidence: str,
    reversal_evidence: str,
    maturity: str,
) -> str:
    """
    Build concise historical environment description.
    """

    return (
        f"{historical_bias} | "
        f"{historical_direction} | "
        f"CONTINUATION {continuation_evidence} | "
        f"REVERSAL {reversal_evidence} | "
        f"{maturity}"
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    change_result: MarketHistoryChangeResult,
    trend_result: MarketHistoryTrendResult,
    historical_confidence: int,
) -> tuple[str, ...]:
    """
    Build evidence-quality warnings.
    """

    warnings: list[str] = []

    if not change_result.available:
        warnings.append(
            "Session-to-session historical change analysis "
            "is not yet available."
        )

    if not trend_result.available:
        warnings.append(
            "Multi-session historical trend analysis "
            "is not yet available."
        )

    if trend_result.total_sessions < 5:
        warnings.append(
            "Fewer than five Market Intelligence sessions "
            "are currently stored."
        )

    if trend_result.total_sessions < 10:
        warnings.append(
            "Ten-session historical confirmation "
            "is not yet available."
        )

    if historical_confidence < 50:
        warnings.append(
            "Historical Intelligence confidence is below 50%."
        )

    return tuple(
        warnings
    )


# ==========================================================
# ENGINE
# ==========================================================

def run_historical_intelligence_summary_engine(
    *,
    history_file: Path = HISTORY_FILE,
) -> HistoricalIntelligenceSummaryResult:
    """
    Run AQSD Historical Intelligence Summary Engine.
    """

    change_result = (
        run_market_history_change_engine(
            history_file=history_file,
        )
    )

    trend_result = (
        run_market_history_trend_engine(
            history_file=history_file,
        )
    )

    # ------------------------------------------------------
    # INSUFFICIENT HISTORY
    # ------------------------------------------------------

    if (
        not change_result.available
        or trend_result.total_sessions < 2
    ):
        warnings = build_warnings(
            change_result,
            trend_result,
            0,
        )

        explanation = (
            "AQSD Historical Intelligence is still accumulating "
            "evidence. At least two distinct recorded Market "
            "Intelligence sessions are required before historical "
            "direction, transition, continuation and reversal "
            "analysis can be produced."
        )

        return HistoricalIntelligenceSummaryResult(
            available=False,

            analysis_date=(
                trend_result.latest_date
            ),

            total_sessions=(
                trend_result.total_sessions
            ),

            historical_bias=(
                "INSUFFICIENT HISTORY"
            ),

            historical_direction=(
                "INSUFFICIENT HISTORY"
            ),

            bias_transition=(
                "INSUFFICIENT HISTORY"
            ),

            regime_transition=(
                "INSUFFICIENT HISTORY"
            ),

            risk_transition=(
                "INSUFFICIENT HISTORY"
            ),

            directional_momentum=(
                "INSUFFICIENT HISTORY"
            ),

            intelligence_momentum=(
                "INSUFFICIENT HISTORY"
            ),

            bullish_trend=(
                "INSUFFICIENT HISTORY"
            ),

            bearish_trend=(
                "INSUFFICIENT HISTORY"
            ),

            neutral_trend=(
                "INSUFFICIENT HISTORY"
            ),

            confidence_trend=(
                "INSUFFICIENT HISTORY"
            ),

            bias_persistence_sessions=(
                trend_result
                .bias_persistence_sessions
            ),

            regime_persistence_sessions=(
                trend_result
                .regime_persistence_sessions
            ),

            bias_stability=(
                trend_result.bias_stability
            ),

            regime_stability=(
                trend_result.regime_stability
            ),

            directional_consistency=(
                trend_result
                .directional_consistency
            ),

            continuation_evidence=(
                "INSUFFICIENT HISTORY"
            ),

            reversal_evidence=(
                "INSUFFICIENT HISTORY"
            ),

            continuation_score=0,
            reversal_score=0,

            historical_confidence=0,

            historical_maturity=(
                trend_result
                .historical_maturity
            ),

            historical_quality=(
                trend_result
                .trend_quality
            ),

            historical_environment=(
                "INSUFFICIENT HISTORY"
            ),

            concise_summary=(
                f"{trend_result.total_sessions} SESSION(S) | "
                "HISTORICAL INTELLIGENCE NOT YET AVAILABLE | "
                f"MATURITY "
                f"{trend_result.historical_maturity}"
            ),

            explanation=explanation,

            warnings=warnings,

            status=(
                "INSUFFICIENT HISTORY"
            ),
        )

    # ------------------------------------------------------
    # FULL HISTORICAL INTELLIGENCE
    # ------------------------------------------------------

    historical_bias = (
        determine_historical_bias(
            change_result,
            trend_result,
        )
    )

    historical_direction = (
        determine_historical_direction(
            change_result,
            trend_result,
        )
    )

    continuation_score = (
        calculate_continuation_score(
            change_result,
            trend_result,
        )
    )

    reversal_score = (
        calculate_reversal_score(
            change_result,
            trend_result,
        )
    )

    continuation_evidence = (
        classify_evidence(
            continuation_score
        )
    )

    reversal_evidence = (
        classify_evidence(
            reversal_score
        )
    )

    historical_confidence = (
        calculate_historical_confidence(
            change_result,
            trend_result,
        )
    )

    historical_environment = (
        determine_historical_environment(
            historical_bias=(
                historical_bias
            ),
            historical_direction=(
                historical_direction
            ),
            continuation_evidence=(
                continuation_evidence
            ),
            reversal_evidence=(
                reversal_evidence
            ),
            maturity=(
                trend_result
                .historical_maturity
            ),
        )
    )

    warnings = build_warnings(
        change_result,
        trend_result,
        historical_confidence,
    )

    concise_summary = (
        f"{trend_result.total_sessions} SESSION(S) | "
        f"{historical_bias} | "
        f"{historical_direction} | "
        f"CONTINUATION {continuation_evidence} "
        f"{continuation_score}% | "
        f"REVERSAL {reversal_evidence} "
        f"{reversal_score}% | "
        f"CONFIDENCE {historical_confidence}% | "
        f"MATURITY "
        f"{trend_result.historical_maturity}"
    )

    explanation = (
        f"AQSD analysed {trend_result.total_sessions} stored "
        f"Market Intelligence session(s). Historical bias is "
        f"{historical_bias} and historical direction is "
        f"{historical_direction}. "
        f"The latest bias transition is "
        f"{change_result.bias_transition}, while the latest "
        f"regime transition is "
        f"{change_result.regime_transition}. "
        f"Current regime persistence is "
        f"{trend_result.regime_persistence_sessions} session(s), "
        f"and bias persistence is "
        f"{trend_result.bias_persistence_sessions} session(s). "
        f"Five-session bullish probability trend is "
        f"{trend_result.bullish_5d_trend}, bearish trend is "
        f"{trend_result.bearish_5d_trend}, and confidence trend "
        f"is {trend_result.confidence_5d_trend}. "
        f"Continuation evidence is classified as "
        f"{continuation_evidence} with score "
        f"{continuation_score}%, while reversal evidence is "
        f"{reversal_evidence} with score "
        f"{reversal_score}%. "
        f"Historical maturity is "
        f"{trend_result.historical_maturity}, and final "
        f"Historical Intelligence confidence is "
        f"{historical_confidence}%."
    )

    return HistoricalIntelligenceSummaryResult(
        available=True,

        analysis_date=(
            trend_result.latest_date
        ),

        total_sessions=(
            trend_result.total_sessions
        ),

        historical_bias=(
            historical_bias
        ),

        historical_direction=(
            historical_direction
        ),

        bias_transition=(
            change_result.bias_transition
        ),

        regime_transition=(
            change_result.regime_transition
        ),

        risk_transition=(
            change_result.risk_transition
        ),

        directional_momentum=(
            change_result
            .directional_momentum
        ),

        intelligence_momentum=(
            change_result
            .intelligence_momentum
        ),

        bullish_trend=(
            trend_result
            .bullish_5d_trend
        ),

        bearish_trend=(
            trend_result
            .bearish_5d_trend
        ),

        neutral_trend=(
            trend_result
            .neutral_5d_trend
        ),

        confidence_trend=(
            trend_result
            .confidence_5d_trend
        ),

        bias_persistence_sessions=(
            trend_result
            .bias_persistence_sessions
        ),

        regime_persistence_sessions=(
            trend_result
            .regime_persistence_sessions
        ),

        bias_stability=(
            trend_result.bias_stability
        ),

        regime_stability=(
            trend_result.regime_stability
        ),

        directional_consistency=(
            trend_result
            .directional_consistency
        ),

        continuation_evidence=(
            continuation_evidence
        ),

        reversal_evidence=(
            reversal_evidence
        ),

        continuation_score=(
            continuation_score
        ),

        reversal_score=(
            reversal_score
        ),

        historical_confidence=(
            historical_confidence
        ),

        historical_maturity=(
            trend_result
            .historical_maturity
        ),

        historical_quality=(
            trend_result
            .trend_quality
        ),

        historical_environment=(
            historical_environment
        ),

        concise_summary=(
            concise_summary
        ),

        explanation=(
            explanation
        ),

        warnings=(
            warnings
        ),

        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: HistoricalIntelligenceSummaryResult,
) -> None:
    """
    Display consolidated historical intelligence.
    """

    print()
    print("=" * 100)
    print(
        "AQSD HISTORICAL INTELLIGENCE SUMMARY ENGINE"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Analysis Date             : "
        f"{result.analysis_date or 'NOT AVAILABLE'}"
    )

    print(
        f"Recorded Sessions         : "
        f"{result.total_sessions}"
    )

    print("-" * 100)

    print("HISTORICAL CLASSIFICATION")
    print("-" * 100)

    print(
        f"Historical Bias           : "
        f"{result.historical_bias}"
    )

    print(
        f"Historical Direction      : "
        f"{result.historical_direction}"
    )

    print(
        f"Historical Environment    : "
        f"{result.historical_environment}"
    )

    print("-" * 100)

    print("TRANSITIONS")
    print("-" * 100)

    print(
        f"Bias Transition           : "
        f"{result.bias_transition}"
    )

    print(
        f"Regime Transition         : "
        f"{result.regime_transition}"
    )

    print(
        f"Risk Transition           : "
        f"{result.risk_transition}"
    )

    print("-" * 100)

    print("MOMENTUM")
    print("-" * 100)

    print(
        f"Directional Momentum      : "
        f"{result.directional_momentum}"
    )

    print(
        f"Intelligence Momentum     : "
        f"{result.intelligence_momentum}"
    )

    print("-" * 100)

    print("HISTORICAL TRENDS")
    print("-" * 100)

    print(
        f"Bullish Trend             : "
        f"{result.bullish_trend}"
    )

    print(
        f"Bearish Trend             : "
        f"{result.bearish_trend}"
    )

    print(
        f"Neutral Trend             : "
        f"{result.neutral_trend}"
    )

    print(
        f"Confidence Trend          : "
        f"{result.confidence_trend}"
    )

    print("-" * 100)

    print("PERSISTENCE")
    print("-" * 100)

    print(
        f"Bias Persistence          : "
        f"{result.bias_persistence_sessions} session(s)"
    )

    print(
        f"Regime Persistence        : "
        f"{result.regime_persistence_sessions} session(s)"
    )

    print(
        f"Bias Stability            : "
        f"{result.bias_stability}"
    )

    print(
        f"Regime Stability          : "
        f"{result.regime_stability}"
    )

    print(
        f"Directional Consistency   : "
        f"{result.directional_consistency}"
    )

    print("-" * 100)

    print("CONTINUATION / REVERSAL EVIDENCE")
    print("-" * 100)

    print(
        f"Continuation Evidence     : "
        f"{result.continuation_evidence}"
    )

    print(
        f"Continuation Score        : "
        f"{result.continuation_score}%"
    )

    print(
        f"Reversal Evidence         : "
        f"{result.reversal_evidence}"
    )

    print(
        f"Reversal Score            : "
        f"{result.reversal_score}%"
    )

    print("-" * 100)

    print("HISTORICAL QUALITY")
    print("-" * 100)

    print(
        f"Historical Confidence     : "
        f"{result.historical_confidence}%"
    )

    print(
        f"Historical Maturity       : "
        f"{result.historical_maturity}"
    )

    print(
        f"Historical Quality        : "
        f"{result.historical_quality}"
    )

    print("-" * 100)

    print("CONCISE SUMMARY")
    print("-" * 100)

    print(
        result.concise_summary
    )

    print("-" * 100)

    if result.warnings:
        print("WARNINGS")
        print("-" * 100)

        for number, warning in enumerate(
            result.warnings,
            start=1,
        ):
            print(
                f"{number}. {warning}"
            )

        print("-" * 100)

    print("EXPLANATION")
    print("-" * 100)

    print(
        result.explanation
    )

    print("-" * 100)

    print(
        f"Status                    : "
        f"{result.status}"
    )

    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Consolidate AQSD Historical Intelligence."
        )
    )

    parser.add_argument(
        "--history",
        type=Path,
        default=HISTORY_FILE,
        help=(
            "Path to market_intelligence_history.csv"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = (
            run_historical_intelligence_summary_engine(
                history_file=(
                    arguments.history
                    .expanduser()
                    .resolve()
                )
            )
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print(
            "AQSD HISTORICAL INTELLIGENCE SUMMARY ENGINE"
        )
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 100)

        raise SystemExit(
            1
        ) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()