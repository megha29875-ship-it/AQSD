"""
AQSD
Market Regime Engine

Module : MRE-001
Version: 1.0.1
Author : AQSD

Description
-----------
Combines the major AQSD intelligence families into one explainable
market-regime classification.

Current inputs
--------------
1. Market Breadth Decision Engine
2. Sector Rotation Decision Engine
3. Participant Master Decision Engine

Optional inputs
---------------
4. Options Intelligence
5. Market Structure Intelligence

Missing optional engines are handled safely and receive zero
directional weight.

Important
---------
This module provides analytical decision support only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MRE-001"
MODULE_VERSION: Final[str] = "1.0.1"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DEFAULT_BREADTH_INPUT_FILE: Final[Path] = (
    BASE_DIR
    / "Data"
    / "Market_Breadth"
    / "market_breadth_snapshot.xlsx"
)

DEFAULT_WEEKLY_LOOKBACK_SESSIONS: Final[int] = 5


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class EngineSnapshot:
    """
    Normalized intelligence received from one AQSD engine.
    """

    engine_name: str
    available: bool
    status: str

    bias: str
    direction: str
    environment: str
    strength: str
    risk: str
    expected_behaviour: str

    confidence: int
    bullish_score: int
    bearish_score: int
    neutral_score: int

    summary: str
    explanation: str
    warning: str | None


@dataclass(frozen=True)
class MarketRegimeResult:
    """
    Final output of the AQSD Market Regime Engine.
    """

    requested_date: date
    analysis_date: date

    primary_regime: str
    secondary_regime: str
    market_direction: str

    trend_environment: str
    breadth_environment: str
    sector_environment: str
    institutional_environment: str
    options_environment: str

    risk_environment: str
    regime_strength: str
    regime_maturity: str
    regime_alignment: str

    bullish_probability: float
    bearish_probability: float
    neutral_probability: float

    confidence: int
    decision_quality: str

    expected_behaviour: str
    analytical_posture: str
    market_environment: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    concise_summary: str
    explanation: str
    master_conclusion: str

    breadth_snapshot: EngineSnapshot
    sector_snapshot: EngineSnapshot
    participant_snapshot: EngineSnapshot
    options_snapshot: EngineSnapshot
    structure_snapshot: EngineSnapshot

    available_engines: int
    total_engines: int
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def clamp_score(
    value: float,
) -> int:
    """
    Restrict a score to the range 0-100.
    """

    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


def safe_int(
    value: object,
    default: int = 0,
) -> int:
    """
    Convert a value to integer safely.
    """

    if value is None:
        return default

    try:
        return int(
            round(
                float(value)
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return default


def normalize_text(
    value: object,
    default: str = "UNKNOWN",
) -> str:
    """
    Convert a value to normalized uppercase text.
    """

    if value is None:
        return default

    text = str(value).strip().upper()

    return text or default


def contains_any(
    value: str,
    keywords: tuple[str, ...],
) -> bool:
    """
    Return True when text contains any supplied keyword.
    """

    text = normalize_text(
        value,
        "",
    )

    return any(
        keyword.upper() in text
        for keyword in keywords
    )


def first_attribute(
    obj: object,
    names: tuple[str, ...],
    default: object = None,
) -> object:
    """
    Read the first available attribute from an object.
    """

    for name in names:
        if hasattr(
            obj,
            name,
        ):
            return getattr(
                obj,
                name,
            )

    return default


def call_with_supported_arguments(
    function: Any,
    arguments: dict[str, object],
) -> Any:
    """
    Call a function using only arguments supported by its signature.
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


def empty_snapshot(
    *,
    engine_name: str,
    warning: str,
) -> EngineSnapshot:
    """
    Create an unavailable engine snapshot.
    """

    return EngineSnapshot(
        engine_name=engine_name,
        available=False,
        status="NOT AVAILABLE",

        bias="UNKNOWN",
        direction="UNKNOWN",
        environment="NOT AVAILABLE",
        strength="NOT AVAILABLE",
        risk="NOT AVAILABLE",
        expected_behaviour="NOT AVAILABLE",

        confidence=0,
        bullish_score=0,
        bearish_score=0,
        neutral_score=100,

        summary="NOT AVAILABLE",
        explanation="NOT AVAILABLE",
        warning=warning,
    )


# ==========================================================
# DIRECTIONAL TEXT SCORING
# ==========================================================

def calculate_direction_scores(
    *values: object,
) -> tuple[int, int, int]:
    """
    Convert qualitative engine language into directional scores.

    Returns
    -------
    bullish_score, bearish_score, neutral_score
    """

    text = " | ".join(
        normalize_text(
            value,
            "",
        )
        for value in values
    )

    bullish_score = 0
    bearish_score = 0
    neutral_score = 10

    strongly_bullish_terms = (
        "STRONGLY BULLISH",
        "BROAD POSITIVE",
        "BULL MARKET",
        "RISK ON",
        "ACCUMULATION",
    )

    bullish_terms = (
        "BULLISH",
        "POSITIVE",
        "IMPROVING",
        "RECOVERY",
        "SHORT COVERING",
        "CONSTRUCTIVE",
        "LEADER",
    )

    strongly_bearish_terms = (
        "STRONGLY BEARISH",
        "BROAD NEGATIVE",
        "BEAR MARKET",
        "RISK OFF",
        "DISTRIBUTION",
        "CAPITULATION",
    )

    bearish_terms = (
        "BEARISH",
        "NEGATIVE",
        "DETERIORATING",
        "WEAK",
        "SHORT BUILD",
        "SELL-OFF",
        "LAGGARD",
    )

    neutral_terms = (
        "NEUTRAL",
        "MIXED",
        "SIDEWAYS",
        "RANGE",
        "CONSOLIDATION",
        "INSUFFICIENT HISTORY",
        "UNKNOWN",
    )

    for term in strongly_bullish_terms:
        if term in text:
            bullish_score += 30

    for term in bullish_terms:
        if term in text:
            bullish_score += 12

    for term in strongly_bearish_terms:
        if term in text:
            bearish_score += 30

    for term in bearish_terms:
        if term in text:
            bearish_score += 12

    for term in neutral_terms:
        if term in text:
            neutral_score += 12

    total = (
        bullish_score
        + bearish_score
        + neutral_score
    )

    if total <= 0:
        return (
            0,
            0,
            100,
        )

    return (
        clamp_score(
            bullish_score
            / total
            * 100
        ),
        clamp_score(
            bearish_score
            / total
            * 100
        ),
        clamp_score(
            neutral_score
            / total
            * 100
        ),
    )


def build_snapshot_from_result(
    *,
    engine_name: str,
    result: object,
    bias_fields: tuple[str, ...],
    direction_fields: tuple[str, ...],
    environment_fields: tuple[str, ...],
    strength_fields: tuple[str, ...],
    risk_fields: tuple[str, ...],
    confidence_fields: tuple[str, ...],
) -> EngineSnapshot:
    """
    Normalize an AQSD engine result into an EngineSnapshot.
    """

    bias = normalize_text(
        first_attribute(
            result,
            bias_fields,
        )
    )

    direction = normalize_text(
        first_attribute(
            result,
            direction_fields,
        )
    )

    environment = normalize_text(
        first_attribute(
            result,
            environment_fields,
        )
    )

    strength = normalize_text(
        first_attribute(
            result,
            strength_fields,
        )
    )

    risk = normalize_text(
        first_attribute(
            result,
            risk_fields,
        )
    )

    confidence = safe_int(
        first_attribute(
            result,
            confidence_fields,
            0,
        )
    )

    expected_behaviour = normalize_text(
        first_attribute(
            result,
            (
                "expected_behaviour",
                "expected_behavior",
            ),
            "NOT AVAILABLE",
        )
    )

    summary = str(
        first_attribute(
            result,
            (
                "concise_summary",
                "master_conclusion",
                "conclusion",
                "interpretation",
            ),
            "NOT AVAILABLE",
        )
    )

    explanation = str(
        first_attribute(
            result,
            (
                "explanation",
                "master_conclusion",
                "conclusion",
                "interpretation",
            ),
            "NOT AVAILABLE",
        )
    )

    status = normalize_text(
        first_attribute(
            result,
            (
                "status",
                "overall_status",
            ),
            "UNKNOWN",
        )
    )

    (
        bullish_score,
        bearish_score,
        neutral_score,
    ) = calculate_direction_scores(
        bias,
        direction,
        environment,
        expected_behaviour,
    )

    return EngineSnapshot(
        engine_name=engine_name,
        available=True,
        status=status,

        bias=bias,
        direction=direction,
        environment=environment,
        strength=strength,
        risk=risk,
        expected_behaviour=expected_behaviour,

        confidence=confidence,
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        neutral_score=neutral_score,

        summary=summary,
        explanation=explanation,
        warning=None,
    )
# ==========================================================
# MARKET BREADTH ADAPTER
# ==========================================================

def run_breadth_adapter(
    *,
    requested_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> EngineSnapshot:
    """
    Run and normalize the Market Breadth Decision Engine.
    """

    engine_name = "MARKET BREADTH DECISION"

    try:
        module = importlib.import_module(
            "Scripts.aqsd_intelligence."
            "market_breadth_decision_engine"
        )

        runner = getattr(
            module,
            "run_market_breadth_decision_engine",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": requested_date,
                "source_file": source_file,
                "weekly_lookback_sessions": (
                    weekly_lookback_sessions
                ),
                "export_breadth": False,
            },
        )

        return build_snapshot_from_result(
            engine_name=engine_name,
            result=result,
            bias_fields=(
                "breadth_bias",
                "market_bias",
                "bias",
                "consolidated_breadth_bias",
            ),
            direction_fields=(
                "breadth_direction",
                "direction",
                "breadth_momentum",
                "change_direction",
            ),
            environment_fields=(
                "market_environment",
                "breadth_regime",
                "environment",
                "breadth_environment",
            ),
            strength_fields=(
                "breadth_quality",
                "breadth_strength",
                "decision_quality",
                "participation_quality",
            ),
            risk_fields=(
                "reversal_risk_level",
                "risk_environment",
                "risk_level",
                "breadth_risk_level",
            ),
            confidence_fields=(
                "decision_confidence",
                "confidence",
                "current_confidence",
                "breadth_confidence",
            ),
        )

    except Exception as exc:
        return empty_snapshot(
            engine_name=engine_name,
            warning=(
                "Market Breadth Decision Engine could not be used: "
                f"{exc}"
            ),
        )


# ==========================================================
# SECTOR ADAPTER
# ==========================================================

def run_sector_adapter(
    *,
    requested_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> EngineSnapshot:
    """
    Run and normalize the Sector Rotation Decision Engine.
    """

    engine_name = "SECTOR ROTATION DECISION"

    try:
        module = importlib.import_module(
            "Scripts.aqsd_intelligence."
            "sector_rotation_decision_engine"
        )

        runner = getattr(
            module,
            "run_sector_rotation_decision_engine",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": requested_date,
                "source_file": source_file,
                "weekly_lookback_sessions": (
                    weekly_lookback_sessions
                ),
                "export_strength": False,
                "export_rotation": False,
            },
        )

        return build_snapshot_from_result(
            engine_name=engine_name,
            result=result,
            bias_fields=(
                "sector_market_bias",
                "market_bias",
                "bias",
            ),
            direction_fields=(
                "rotation_direction",
                "broad_rotation",
                "direction",
            ),
            environment_fields=(
                "market_environment",
                "market_sector_health",
                "sector_environment",
            ),
            strength_fields=(
                "rotation_quality",
                "sector_participation_quality",
                "leadership_quality",
            ),
            risk_fields=(
                "sector_risk_level",
                "rotation_risk_level",
                "risk_level",
            ),
            confidence_fields=(
                "decision_confidence",
                "confidence",
                "rotation_confidence",
            ),
        )

    except Exception as exc:
        return empty_snapshot(
            engine_name=engine_name,
            warning=(
                "Sector Rotation Decision Engine could not be used: "
                f"{exc}"
            ),
        )


# ==========================================================
# PARTICIPANT ADAPTER
# ==========================================================

def run_participant_adapter(
    *,
    requested_date: date,
) -> EngineSnapshot:
    """
    Run and normalize the Participant Master Decision Engine.

    More than one module and runner name is supported because the
    participant system has evolved through several AQSD stages.
    """

    engine_name = "PARTICIPANT MASTER DECISION"

    module_candidates = (
        (
            "Scripts.aqsd_intelligence."
            "participant_master_decision_engine"
        ),
        (
            "Scripts.aqsd_intelligence."
            "participant_decision_summary"
        ),
    )

    runner_candidates = (
        "run_participant_master_decision_engine",
        "run_participant_master_decision",
        "run_participant_decision_summary",
    )

    errors: list[str] = []

    for module_name in module_candidates:
        try:
            module = importlib.import_module(
                module_name
            )

            runner = None

            for runner_name in runner_candidates:
                if hasattr(
                    module,
                    runner_name,
                ):
                    runner = getattr(
                        module,
                        runner_name,
                    )
                    break

            if runner is None:
                raise AttributeError(
                    "No supported participant runner was found."
                )

            result = call_with_supported_arguments(
                runner,
                {
                    "requested_date": requested_date,
                    "trade_date": requested_date,
                    "analysis_date": requested_date,
                },
            )

            return build_snapshot_from_result(
                engine_name=engine_name,
                result=result,
                bias_fields=(
                    "current_positioning",
                    "institutional_bias",
                    "participant_bias",
                    "market_bias",
                    "bias",
                    "primary_forecast",
                ),
                direction_fields=(
                    "momentum",
                    "regime_direction",
                    "participant_direction",
                    "direction",
                    "cycle_direction",
                ),
                environment_fields=(
                    "participant_environment",
                    "market_environment",
                    "structural_state",
                    "primary_regime",
                    "current_cycle",
                ),
                strength_fields=(
                    "institutional_strength",
                    "regime_strength",
                    "conviction",
                    "decision_quality",
                    "positioning_state",
                ),
                risk_fields=(
                    "risk_level",
                    "overall_risk_level",
                    "participant_risk",
                    "forecast_risk",
                ),
                confidence_fields=(
                    "confidence",
                    "overall_confidence",
                    "decision_confidence",
                    "probability_confidence",
                    "forecast_confidence",
                ),
            )

        except Exception as exc:
            errors.append(
                f"{module_name}: {exc}"
            )

    return empty_snapshot(
        engine_name=engine_name,
        warning=(
            "Participant Master Decision Engine could not be used: "
            + " | ".join(errors)
        ),
    )


# ==========================================================
# OPTIONS ADAPTER
# ==========================================================

def run_options_adapter(
    *,
    requested_date: date,
) -> EngineSnapshot:
    """
    Run and normalize AQSD Options Intelligence.

    The Options Intelligence calculate() function returns:

        summary_frame, walls_frame

    summary_frame is normally a one-row pandas DataFrame.

    This adapter converts that DataFrame to a single row before
    reading individual fields. This prevents pandas Series text
    such as:

        Name: reversal_signal, dtype: str

    from leaking into the Market Regime Engine output.
    """

    engine_name = "OPTIONS INTELLIGENCE"

    try:
        module = importlib.import_module(
            "Scripts.aqsd_options_intelligence"
        )

        calculate_options = getattr(
            module,
            "calculate",
        )

        calculation_result = calculate_options(
            "BANKNIFTY",
            5,
        )

        # --------------------------------------------------
        # VALIDATE RESULT
        # --------------------------------------------------

        if not isinstance(
            calculation_result,
            tuple,
        ):
            raise TypeError(
                "Options calculate() did not return a tuple."
            )

        if len(calculation_result) < 1:
            raise ValueError(
                "Options calculate() returned an empty tuple."
            )

        summary = calculation_result[0]

        # --------------------------------------------------
        # IMPORTANT FIX
        # --------------------------------------------------
        # Options Intelligence returns a one-row DataFrame.
        # Convert it to a pandas Series representing that row.
        # This ensures .get() returns scalar values rather
        # than whole pandas Series/columns.
        # --------------------------------------------------

        if hasattr(summary, "iloc"):
            if getattr(summary, "empty", False):
                raise ValueError(
                    "Options Intelligence returned an empty "
                    "summary DataFrame."
                )

            # DataFrame -> first row Series.
            if getattr(summary, "ndim", 1) == 2:
                summary = summary.iloc[0]

        # --------------------------------------------------
        # SAFE FIELD READER
        # --------------------------------------------------

        def read_summary_value(
            names: tuple[str, ...],
            default: object = None,
        ) -> object:
            """
            Read one scalar value from a dictionary,
            pandas Series, dataclass or ordinary object.
            """

            for name in names:

                # Dictionary
                if isinstance(
                    summary,
                    dict,
                ):
                    if name in summary:
                        value = summary[name]

                        if value is not None:
                            return value

                # pandas Series / dictionary-like object
                if hasattr(
                    summary,
                    "get",
                ):
                    try:
                        value = summary.get(
                            name,
                            None,
                        )

                        if value is not None:
                            return value

                    except Exception:
                        pass

                # Dataclass / ordinary object
                if hasattr(
                    summary,
                    name,
                ):
                    value = getattr(
                        summary,
                        name,
                    )

                    if value is not None:
                        return value

            return default

        # --------------------------------------------------
        # CORE OPTIONS CLASSIFICATION
        # --------------------------------------------------

        bias = normalize_text(
            read_summary_value(
                (
                    "options_bias",
                    "market_bias",
                    "bias",
                    "reversal_signal",
                    "suggested_action",
                    "direction",
                    "Options Bias",
                    "Market Bias",
                    "Reversal Signal",
                ),
                "UNKNOWN",
            )
        )

        direction = normalize_text(
            read_summary_value(
                (
                    "pcr_trend",
                    "direction",
                    "wall_shift",
                    "options_direction",
                    "expected_direction",
                    "PCR Trend",
                    "Wall Shift",
                ),
                "UNKNOWN",
            )
        )

        environment = normalize_text(
            read_summary_value(
                (
                    "iv_regime",
                    "options_environment",
                    "market_environment",
                    "volatility_regime",
                    "IV Regime",
                    "Volatility Regime",
                ),
                "NOT AVAILABLE",
            )
        )

        strength = normalize_text(
            read_summary_value(
                (
                    "signal_strength",
                    "trade_quality",
                    "confidence_grade",
                    "options_quality",
                    "decision_quality",
                    "Signal Strength",
                    "Trade Quality",
                ),
                "NOT AVAILABLE",
            )
        )

        risk = normalize_text(
            read_summary_value(
                (
                    "risk_level",
                    "options_risk",
                    "iv_risk",
                    "volatility_risk",
                    "Risk Level",
                    "Options Risk",
                ),
                "NOT AVAILABLE",
            )
        )

        confidence = safe_int(
            read_summary_value(
                (
                    "confidence",
                    "overall_confidence",
                    "probability_confidence",
                    "options_confidence",
                    "decision_confidence",
                    "Confidence",
                    "Overall Confidence",
                ),
                0,
            )
        )

        expected_behaviour = normalize_text(
            read_summary_value(
                (
                    "expected_behaviour",
                    "expected_behavior",
                    "interpretation",
                    "Expected Behaviour",
                    "Interpretation",
                ),
                "NOT AVAILABLE",
            )
        )

        status = normalize_text(
            read_summary_value(
                (
                    "status",
                    "overall_status",
                    "Status",
                    "Overall Status",
                ),
                "SUCCESS",
            )
        )

        # --------------------------------------------------
        # OPTIONS PROBABILITIES
        # --------------------------------------------------
        # Prefer actual probabilities supplied by the
        # Options Intelligence Engine.
        # --------------------------------------------------

        bullish_probability_value = read_summary_value(
            (
                "bullish_reversal_probability",
                "bullish_probability",
                "probability_up",
                "Bullish Reversal Probability",
                "Bullish Probability",
            ),
            None,
        )

        bearish_probability_value = read_summary_value(
            (
                "bearish_reversal_probability",
                "bearish_probability",
                "probability_down",
                "Bearish Reversal Probability",
                "Bearish Probability",
            ),
            None,
        )

        continuation_probability_value = read_summary_value(
            (
                "continuation_probability",
                "neutral_probability",
                "Continuation Probability",
                "Neutral Probability",
            ),
            None,
        )

        # --------------------------------------------------
        # USE REAL OPTIONS PROBABILITIES WHEN AVAILABLE
        # --------------------------------------------------

        if (
            bullish_probability_value is not None
            and bearish_probability_value is not None
        ):
            bullish_score = safe_int(
                bullish_probability_value,
                0,
            )

            bearish_score = safe_int(
                bearish_probability_value,
                0,
            )

            if continuation_probability_value is not None:
                neutral_score = safe_int(
                    continuation_probability_value,
                    0,
                )
            else:
                neutral_score = max(
                    0,
                    100
                    - bullish_score
                    - bearish_score,
                )

            total_score = (
                bullish_score
                + bearish_score
                + neutral_score
            )

            # Normalize because Options probabilities may
            # represent independent probabilities rather
            # than mutually exclusive percentages.
            if total_score > 0:
                bullish_score = clamp_score(
                    bullish_score
                    / total_score
                    * 100
                )

                bearish_score = clamp_score(
                    bearish_score
                    / total_score
                    * 100
                )

                neutral_score = clamp_score(
                    neutral_score
                    / total_score
                    * 100
                )

        else:
            (
                bullish_score,
                bearish_score,
                neutral_score,
            ) = calculate_direction_scores(
                bias,
                direction,
                environment,
                expected_behaviour,
            )

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        concise_summary = str(
            read_summary_value(
                (
                    "concise_summary",
                    "summary",
                    "interpretation",
                    "Concise Summary",
                    "Interpretation",
                ),
                (
                    f"{bias} | "
                    f"{direction} | "
                    f"{environment} | "
                    f"{confidence}% CONFIDENCE"
                ),
            )
        )

        explanation = str(
            read_summary_value(
                (
                    "explanation",
                    "interpretation",
                    "summary",
                    "Explanation",
                    "Interpretation",
                ),
                concise_summary,
            )
        )

        # --------------------------------------------------
        # FINAL NORMALIZED SNAPSHOT
        # --------------------------------------------------

        return EngineSnapshot(
            engine_name=engine_name,
            available=True,
            status=status,

            bias=bias,
            direction=direction,
            environment=environment,
            strength=strength,
            risk=risk,
            expected_behaviour=expected_behaviour,

            confidence=confidence,

            bullish_score=bullish_score,
            bearish_score=bearish_score,
            neutral_score=neutral_score,

            summary=concise_summary,
            explanation=explanation,

            warning=None,
        )

    except Exception as exc:
        return empty_snapshot(
            engine_name=engine_name,
            warning=(
                "Options Intelligence could not be connected: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
# ==========================================================
# MARKET STRUCTURE ADAPTER
# ==========================================================

def run_structure_adapter(
    *,
    requested_date: date,
) -> EngineSnapshot:
    """
    Run the AQSD Market Structure Master and convert its result
    into a normalized Market Regime Engine snapshot.

    Source engine
    -------------
    Scripts.aqsd_market_structure.market_structure_master

    This adapter does not perform its own market-structure
    calculations. It consumes the completed Market Structure
    Master result.
    """

    engine_name = "MARKET STRUCTURE"

    try:
        module = importlib.import_module(
            "Scripts.aqsd_market_structure."
            "market_structure_master"
        )

        runner = None

        runner_candidates = (
            "run_market_structure_master",
            "run_market_structure",
        )

        for runner_name in runner_candidates:
            if hasattr(
                module,
                runner_name,
            ):
                candidate = getattr(
                    module,
                    runner_name,
                )

                if callable(candidate):
                    runner = candidate
                    break

        if runner is None:
            raise AttributeError(
                "Market Structure Master runner was not found."
            )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": requested_date,
            },
        )

        # --------------------------------------------------
        # CORE CLASSIFICATION
        # --------------------------------------------------

        bias = normalize_text(
            first_attribute(
                result,
                (
                    "market_bias",
                    "bias",
                ),
                "UNKNOWN",
            )
        )

        direction = normalize_text(
            first_attribute(
                result,
                (
                    "trend_direction",
                    "market_direction",
                    "direction",
                ),
                "UNKNOWN",
            )
        )

        market_phase = normalize_text(
            first_attribute(
                result,
                (
                    "market_phase",
                    "phase",
                ),
                "NOT AVAILABLE",
            )
        )

        structural_state = normalize_text(
            first_attribute(
                result,
                (
                    "structural_state",
                    "swing_structure",
                ),
                "NOT AVAILABLE",
            )
        )

        bos_state = normalize_text(
            first_attribute(
                result,
                (
                    "bos_state",
                ),
                "NONE",
            )
        )

        choch_state = normalize_text(
            first_attribute(
                result,
                (
                    "choch_state",
                ),
                "NONE",
            )
        )

        # --------------------------------------------------
        # ENVIRONMENT
        # --------------------------------------------------

        environment = normalize_text(
            first_attribute(
                result,
                (
                    "market_environment",
                    "market_regime",
                    "market_phase",
                ),
                "NOT AVAILABLE",
            )
        )

        strength = normalize_text(
            first_attribute(
                result,
                (
                    "structural_quality",
                    "trend_quality",
                ),
                "NOT AVAILABLE",
            )
        )

        risk = normalize_text(
            first_attribute(
                result,
                (
                    "structure_risk",
                    "risk_level",
                ),
                "NOT AVAILABLE",
            )
        )

        confidence = safe_int(
            first_attribute(
                result,
                (
                    "confidence",
                    "overall_confidence",
                ),
                0,
            )
        )

        expected_behaviour = normalize_text(
            first_attribute(
                result,
                (
                    "expected_behaviour",
                    "expected_behavior",
                ),
                "NOT AVAILABLE",
            )
        )

        status = normalize_text(
            first_attribute(
                result,
                (
                    "status",
                    "overall_status",
                ),
                "UNKNOWN",
            )
        )

        # --------------------------------------------------
        # PROBABILITIES
        # --------------------------------------------------

        structure_bullish_probability = first_attribute(
            result,
            (
                "bullish_probability",
            ),
            None,
        )

        structure_bearish_probability = first_attribute(
            result,
            (
                "bearish_probability",
            ),
            None,
        )

        structure_neutral_probability = first_attribute(
            result,
            (
                "neutral_probability",
            ),
            None,
        )

        if (
            structure_bullish_probability is not None
            and structure_bearish_probability is not None
            and structure_neutral_probability is not None
        ):
            bullish = safe_int(
                structure_bullish_probability,
                0,
            )

            bearish = safe_int(
                structure_bearish_probability,
                0,
            )

            neutral = safe_int(
                structure_neutral_probability,
                0,
            )

        else:
            (
                bullish,
                bearish,
                neutral,
            ) = calculate_direction_scores(
                bias,
                direction,
                environment,
                expected_behaviour,
            )

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        summary = str(
            first_attribute(
                result,
                (
                    "concise_summary",
                    "master_conclusion",
                ),
                (
                    f"{bias} | "
                    f"TREND {direction} | "
                    f"STRUCTURE {structural_state} | "
                    f"BOS {bos_state} | "
                    f"CHOCH {choch_state} | "
                    f"PHASE {market_phase}"
                ),
            )
        )

        explanation = str(
            first_attribute(
                result,
                (
                    "explanation",
                    "master_conclusion",
                    "concise_summary",
                ),
                summary,
            )
        )

        return EngineSnapshot(
            engine_name=engine_name,
            available=True,
            status=status,

            bias=bias,
            direction=direction,
            environment=environment,
            strength=strength,
            risk=risk,
            expected_behaviour=expected_behaviour,

            confidence=confidence,

            bullish_score=bullish,
            bearish_score=bearish,
            neutral_score=neutral,

            summary=summary,
            explanation=explanation,

            warning=None,
        )

    except Exception as exc:
        return empty_snapshot(
            engine_name=engine_name,
            warning=(
                "Market Structure Master could not be connected "
                "to the Market Regime Engine: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

# ==========================================================
# CONSOLIDATED PROBABILITY ENGINE
# ==========================================================

def calculate_regime_probabilities(
    snapshots: tuple[EngineSnapshot, ...],
) -> tuple[float, float, float]:
    """
    Calculate weighted bullish, bearish and neutral probabilities.
    """

    available_snapshots = tuple(
        snapshot
        for snapshot in snapshots
        if snapshot.available
    )

    if not available_snapshots:
        return (
            0.0,
            0.0,
            100.0,
        )

    weighted_bullish = 0.0
    weighted_bearish = 0.0
    weighted_neutral = 0.0
    total_weight = 0.0

    for snapshot in available_snapshots:
        confidence_weight = max(
            snapshot.confidence,
            35,
        )

        status_weight = 1.0

        if contains_any(
            snapshot.status,
            (
                "LIMITED HISTORY",
                "INSUFFICIENT HISTORY",
                "PARTIAL",
            ),
        ):
            status_weight = 0.70

        weight = (
            confidence_weight
            * status_weight
        )

        weighted_bullish += (
            snapshot.bullish_score
            * weight
        )

        weighted_bearish += (
            snapshot.bearish_score
            * weight
        )

        weighted_neutral += (
            snapshot.neutral_score
            * weight
        )

        total_weight += weight

    if total_weight <= 0:
        return (
            0.0,
            0.0,
            100.0,
        )

    bullish_probability = (
        weighted_bullish
        / total_weight
    )

    bearish_probability = (
        weighted_bearish
        / total_weight
    )

    neutral_probability = (
        weighted_neutral
        / total_weight
    )

    total_probability = (
        bullish_probability
        + bearish_probability
        + neutral_probability
    )

    if total_probability <= 0:
        return (
            0.0,
            0.0,
            100.0,
        )

    return (
        round(
            bullish_probability
            / total_probability
            * 100,
            1,
        ),
        round(
            bearish_probability
            / total_probability
            * 100,
            1,
        ),
        round(
            neutral_probability
            / total_probability
            * 100,
            1,
        ),
    )
# ==========================================================
# REGIME CLASSIFICATION
# ==========================================================

def determine_market_direction(
    *,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> str:
    """
    Determine the dominant market direction.
    """

    if (
        bullish_probability >= 60
        and bullish_probability
        >= bearish_probability + 20
    ):
        return "STRONGLY BULLISH"

    if (
        bullish_probability >= 45
        and bullish_probability
        >= bearish_probability + 10
    ):
        return "BULLISH"

    if (
        bearish_probability >= 60
        and bearish_probability
        >= bullish_probability + 20
    ):
        return "STRONGLY BEARISH"

    if (
        bearish_probability >= 45
        and bearish_probability
        >= bullish_probability + 10
    ):
        return "BEARISH"

    if neutral_probability >= 45:
        return "NEUTRAL"

    return "MIXED"


def determine_primary_regime(
    *,
    market_direction: str,
    snapshots: tuple[EngineSnapshot, ...],
) -> str:
    """
    Determine the primary market regime.
    """

    combined_environment = " | ".join(
        (
            snapshot.direction
            + " "
            + snapshot.environment
            + " "
            + snapshot.expected_behaviour
        )
        for snapshot in snapshots
        if snapshot.available
    )

    if market_direction == "STRONGLY BULLISH":
        if contains_any(
            combined_environment,
            (
                "RECOVERY",
                "SHORT COVERING",
            ),
        ):
            return "STRONG BULLISH RECOVERY"

        return "STRONG BULL MARKET"

    if market_direction == "BULLISH":
        if contains_any(
            combined_environment,
            (
                "RECOVERY",
                "SHORT COVERING",
            ),
        ):
            return "BULLISH RECOVERY"

        if contains_any(
            combined_environment,
            (
                "ACCUMULATION",
                "IMPROVING",
            ),
        ):
            return "BULLISH ACCUMULATION"

        return "MODERATE BULL MARKET"

    if market_direction == "STRONGLY BEARISH":
        if contains_any(
            combined_environment,
            (
                "CAPITULATION",
                "BREAKDOWN",
            ),
        ):
            return "BEARISH CAPITULATION"

        return "STRONG BEAR MARKET"

    if market_direction == "BEARISH":
        if contains_any(
            combined_environment,
            (
                "DISTRIBUTION",
                "DETERIORATING",
            ),
        ):
            return "BEARISH DISTRIBUTION"

        return "MODERATE BEAR MARKET"

    if contains_any(
        combined_environment,
        (
            "RECOVERY",
            "SHORT COVERING",
        ),
    ):
        return "MIXED RECOVERY REGIME"

    if contains_any(
        combined_environment,
        (
            "DISTRIBUTION",
            "DETERIORATING",
        ),
    ):
        return "MIXED DETERIORATION REGIME"

    return "SIDEWAYS / MIXED REGIME"


def determine_secondary_regime(
    snapshots: tuple[EngineSnapshot, ...],
) -> str:
    """
    Determine the supporting secondary regime.
    """

    combined_environment = " | ".join(
        (
            snapshot.bias
            + " "
            + snapshot.direction
            + " "
            + snapshot.environment
        )
        for snapshot in snapshots
        if snapshot.available
    )

    if contains_any(
        combined_environment,
        (
            "SHORT COVERING",
            "RECOVERY",
        ),
    ):
        return "SHORT COVERING / RECOVERY"

    if contains_any(
        combined_environment,
        (
            "ACCUMULATION",
            "RE-ACCUMULATION",
        ),
    ):
        return "INSTITUTIONAL ACCUMULATION"

    if contains_any(
        combined_environment,
        (
            "DISTRIBUTION",
            "LEADERSHIP LOSS",
        ),
    ):
        return "INSTITUTIONAL DISTRIBUTION"

    if contains_any(
        combined_environment,
        (
            "CAPITULATION",
            "BREAKDOWN",
        ),
    ):
        return "CAPITULATION / BREAKDOWN"

    if contains_any(
        combined_environment,
        (
            "ROTATION",
            "STOCK-SPECIFIC",
        ),
    ):
        return "SECTOR ROTATION"

    return "UNCONFIRMED TRANSITION"


# ==========================================================
# RISK CLASSIFICATION
# ==========================================================

def determine_risk_environment(
    snapshots: tuple[EngineSnapshot, ...],
) -> str:
    """
    Determine consolidated market-regime risk.
    """

    available_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.available
    ]

    if not available_snapshots:
        return "VERY HIGH"

    risk_score = 20.0

    for snapshot in available_snapshots:
        risk = snapshot.risk.upper()

        if "VERY HIGH" in risk:
            risk_score += 25

        elif "HIGH" in risk:
            risk_score += 18

        elif "MODERATE" in risk:
            risk_score += 10

        elif "LOW TO MODERATE" in risk:
            risk_score += 5

        elif risk == "LOW":
            risk_score -= 4

        if contains_any(
            snapshot.status,
            (
                "INSUFFICIENT HISTORY",
                "LIMITED HISTORY",
                "PARTIAL",
            ),
        ):
            risk_score += 5

    risk_score = (
        risk_score
        / len(available_snapshots)
        + 20
    )

    final_score = clamp_score(
        risk_score
    )

    if final_score >= 75:
        return "VERY HIGH"

    if final_score >= 60:
        return "HIGH"

    if final_score >= 45:
        return "MODERATE"

    if final_score >= 30:
        return "LOW TO MODERATE"

    return "LOW"


# ==========================================================
# REGIME STRENGTH
# ==========================================================

def determine_regime_strength(
    *,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> str:
    """
    Determine regime strength from probability separation.
    """

    probabilities = sorted(
        (
            bullish_probability,
            bearish_probability,
            neutral_probability,
        ),
        reverse=True,
    )

    dominant_probability = probabilities[0]
    second_probability = probabilities[1]

    separation = (
        dominant_probability
        - second_probability
    )

    if (
        dominant_probability >= 70
        and separation >= 30
    ):
        return "VERY STRONG"

    if (
        dominant_probability >= 58
        and separation >= 20
    ):
        return "STRONG"

    if (
        dominant_probability >= 45
        and separation >= 10
    ):
        return "MODERATE"

    if dominant_probability >= 38:
        return "WEAK TO MODERATE"

    return "WEAK"


# ==========================================================
# ENGINE ALIGNMENT
# ==========================================================

def determine_regime_alignment(
    snapshots: tuple[EngineSnapshot, ...],
) -> str:
    """
    Determine whether the available engines agree directionally.
    """

    available_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.available
    ]

    if len(available_snapshots) < 2:
        return "INSUFFICIENT INPUTS"

    bullish_engines = sum(
        (
            snapshot.bullish_score
            > snapshot.bearish_score + 10
        )
        for snapshot in available_snapshots
    )

    bearish_engines = sum(
        (
            snapshot.bearish_score
            > snapshot.bullish_score + 10
        )
        for snapshot in available_snapshots
    )

    directional_engines = max(
        bullish_engines,
        bearish_engines,
    )

    alignment_percentage = (
        directional_engines
        / len(available_snapshots)
        * 100
    )

    if alignment_percentage >= 80:
        return "VERY HIGH ALIGNMENT"

    if alignment_percentage >= 65:
        return "HIGH ALIGNMENT"

    if alignment_percentage >= 50:
        return "MODERATE ALIGNMENT"

    return "MIXED ALIGNMENT"


# ==========================================================
# REGIME MATURITY
# ==========================================================

def determine_regime_maturity(
    *,
    primary_regime: str,
    snapshots: tuple[EngineSnapshot, ...],
) -> str:
    """
    Determine whether the regime is early, developing or mature.
    """

    combined_environment = " | ".join(
        (
            snapshot.direction
            + " "
            + snapshot.environment
            + " "
            + snapshot.expected_behaviour
        )
        for snapshot in snapshots
        if snapshot.available
    )

    if contains_any(
        combined_environment,
        (
            "EARLY",
            "EMERGING",
            "NEW LEADER",
        ),
    ):
        return "EARLY"

    if contains_any(
        combined_environment,
        (
            "IMPROVING",
            "EXPANDING",
            "DEVELOPING",
            "RECOVERY",
        ),
    ):
        return "DEVELOPING"

    if contains_any(
        combined_environment,
        (
            "MATURE",
            "PERSISTENT",
            "ESTABLISHED",
        ),
    ):
        return "MATURE"

    if contains_any(
        primary_regime,
        (
            "TRANSITION",
            "MIXED",
            "SIDEWAYS",
        ),
    ):
        return "TRANSITIONAL"

    return "UNCONFIRMED"


# ==========================================================
# CONFIDENCE
# ==========================================================

def calculate_regime_confidence(
    *,
    snapshots: tuple[EngineSnapshot, ...],
    regime_alignment: str,
    regime_strength: str,
) -> int:
    """
    Calculate the final Market Regime confidence.
    """

    available_snapshots = [
        snapshot
        for snapshot in snapshots
        if snapshot.available
    ]

    if not available_snapshots:
        return 0

    confidence = (
        sum(
            snapshot.confidence
            for snapshot in available_snapshots
        )
        / len(available_snapshots)
    )

    if regime_alignment == "VERY HIGH ALIGNMENT":
        confidence += 12

    elif regime_alignment == "HIGH ALIGNMENT":
        confidence += 8

    elif regime_alignment == "MODERATE ALIGNMENT":
        confidence += 3

    elif regime_alignment == "MIXED ALIGNMENT":
        confidence -= 8

    if regime_strength == "VERY STRONG":
        confidence += 8

    elif regime_strength == "STRONG":
        confidence += 5

    elif regime_strength == "WEAK":
        confidence -= 8

    unavailable_count = (
        len(snapshots)
        - len(available_snapshots)
    )

    confidence -= (
        unavailable_count
        * 4
    )

    limited_history_count = sum(
        contains_any(
            snapshot.status,
            (
                "INSUFFICIENT HISTORY",
                "LIMITED HISTORY",
                "PARTIAL",
            ),
        )
        for snapshot in available_snapshots
    )

    confidence -= (
        limited_history_count
        * 4
    )

    return clamp_score(
        confidence
    )


# ==========================================================
# DECISION QUALITY
# ==========================================================

def determine_decision_quality(
    *,
    confidence: int,
    regime_strength: str,
    regime_alignment: str,
    risk_environment: str,
) -> str:
    """
    Convert the regime result into an AQSD quality grade.
    """

    if (
        confidence >= 80
        and regime_strength in {
            "VERY STRONG",
            "STRONG",
        }
        and regime_alignment in {
            "VERY HIGH ALIGNMENT",
            "HIGH ALIGNMENT",
        }
        and risk_environment not in {
            "HIGH",
            "VERY HIGH",
        }
    ):
        return "A"

    if (
        confidence >= 68
        and regime_strength in {
            "STRONG",
            "MODERATE",
        }
        and regime_alignment
        != "MIXED ALIGNMENT"
        and risk_environment
        != "VERY HIGH"
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
    primary_regime: str,
    market_direction: str,
    risk_environment: str,
) -> str:
    """
    Determine regime-driven expected market behaviour.
    """

    if primary_regime == "STRONG BULL MARKET":
        return (
            "POSITIVE CONTINUATION AND BUYING ON PULLBACKS MAY "
            "REMAIN THE DOMINANT MARKET BEHAVIOUR"
        )

    if primary_regime in {
        "BULLISH RECOVERY",
        "STRONG BULLISH RECOVERY",
        "MIXED RECOVERY REGIME",
    }:
        return (
            "RECOVERY OR SHORT COVERING MAY CONTINUE, BUT "
            "PULLBACKS CAN REMAIN SHARP UNTIL THE REGIME IS "
            "FULLY CONFIRMED"
        )

    if primary_regime == "BULLISH ACCUMULATION":
        return (
            "SELECTIVE POSITIVE PARTICIPATION MAY BROADEN AS "
            "INSTITUTIONAL ACCUMULATION DEVELOPS"
        )

    if primary_regime in {
        "STRONG BEAR MARKET",
        "MODERATE BEAR MARKET",
        "BEARISH DISTRIBUTION",
    }:
        return (
            "SELLING PRESSURE MAY REMAIN DOMINANT AND "
            "RECOVERIES MAY STAY VULNERABLE"
        )

    if primary_regime == "BEARISH CAPITULATION":
        return (
            "VOLATILITY MAY REMAIN EXTREME, WITH SHARP "
            "DECLINES AND VIOLENT SHORT-COVERING RECOVERIES "
            "POSSIBLE"
        )

    if risk_environment in {
        "HIGH",
        "VERY HIGH",
    }:
        return (
            "MARKET MOVES MAY REMAIN UNSTABLE, TWO-SIDED "
            "AND VULNERABLE TO RAPID REVERSALS"
        )

    if market_direction == "NEUTRAL":
        return (
            "RANGE-BOUND, ROTATIONAL OR STOCK-SPECIFIC "
            "BEHAVIOUR MAY CONTINUE"
        )

    return (
        "THE MARKET REGIME REMAINS MIXED AND REQUIRES "
        "ADDITIONAL CONFIRMATION BEFORE A STRONG "
        "DIRECTIONAL VIEW IS FORMED"
    )


# ==========================================================
# ANALYTICAL POSTURE
# ==========================================================

def determine_analytical_posture(
    *,
    decision_quality: str,
    confidence: int,
    risk_environment: str,
    available_engines: int,
) -> str:
    """
    Determine how the Market Regime result should be used.
    """

    if available_engines < 3:
        return (
            "USE THE MARKET REGIME AS A PRELIMINARY VIEW. "
            "IMPORTANT INTELLIGENCE FAMILIES ARE NOT YET "
            "AVAILABLE."
        )

    if risk_environment == "VERY HIGH":
        return (
            "USE THE REGIME PRIMARILY AS A RISK WARNING AND "
            "REQUIRE STRONG CONFIRMATION FROM PRICE, "
            "STRUCTURE AND OPTIONS."
        )

    if (
        decision_quality in {
            "A",
            "B",
        }
        and confidence >= 68
    ):
        return (
            "THE MARKET REGIME CAN RECEIVE NORMAL TO HIGH "
            "WEIGHT IN THE AQSD MASTER INTELLIGENCE ENGINE."
        )

    if decision_quality == "C":
        return (
            "USE THE MARKET REGIME WITH MODERATE WEIGHT AND "
            "CROSS-CHECK CONFLICTING ENGINE SIGNALS."
        )

    return (
        "USE THE MARKET REGIME WITH LOW WEIGHT UNTIL "
        "ENGINE ALIGNMENT AND CONFIDENCE IMPROVE."
    )


# ==========================================================
# CONFIRMATION CONDITIONS
# ==========================================================

def build_confirmation_conditions(
    *,
    market_direction: str,
    snapshots: tuple[EngineSnapshot, ...],
) -> tuple[str, ...]:
    """
    Build market-regime confirmation conditions.
    """

    conditions: list[str] = []

    if contains_any(
        market_direction,
        (
            "BULLISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "Market breadth should remain stable or "
                    "continue to improve."
                ),
                (
                    "Positive sector participation should remain "
                    "broader than negative participation."
                ),
                (
                    "Institutional positioning should remain "
                    "supportive or improve further."
                ),
                (
                    "Price structure should confirm higher highs, "
                    "higher lows or sustained recovery."
                ),
                (
                    "Options positioning should not develop a "
                    "strong bearish reversal signal."
                ),
            ]
        )

    elif contains_any(
        market_direction,
        (
            "BEARISH",
        ),
    ):
        conditions.extend(
            [
                (
                    "Market breadth should remain weak or "
                    "deteriorate further."
                ),
                (
                    "Negative sector participation should remain "
                    "broader than positive participation."
                ),
                (
                    "Institutional short or bearish exposure "
                    "should remain dominant."
                ),
                (
                    "Price structure should confirm lower highs, "
                    "lower lows or breakdown continuation."
                ),
                (
                    "Options positioning should continue to "
                    "support bearish pressure."
                ),
            ]
        )

    else:
        conditions.extend(
            [
                (
                    "Market breadth should break decisively from "
                    "the current mixed range."
                ),
                (
                    "Sector participation should develop a clear "
                    "directional majority."
                ),
                (
                    "Institutional positioning and price structure "
                    "should become aligned."
                ),
            ]
        )

    unavailable_engines = [
        snapshot.engine_name
        for snapshot in snapshots
        if not snapshot.available
    ]

    if unavailable_engines:
        conditions.append(
            "The currently unavailable intelligence families "
            "should be connected before assigning full regime "
            "confidence."
        )

    return tuple(
        dict.fromkeys(
            conditions
        )
    )


# ==========================================================
# INVALIDATION CONDITIONS
# ==========================================================

def build_invalidation_conditions(
    *,
    market_direction: str,
) -> tuple[str, ...]:
    """
    Build market-regime invalidation conditions.
    """

    if contains_any(
        market_direction,
        (
            "BULLISH",
        ),
    ):
        return (
            (
                "Market breadth reverses sharply and declining "
                "stocks again become dominant."
            ),
            (
                "Leading sectors lose rank while broad negative "
                "sector rotation develops."
            ),
            (
                "Institutional daily positioning turns "
                "materially bearish."
            ),
            (
                "Price structure confirms a bearish reversal "
                "or breakdown."
            ),
            (
                "Options Intelligence develops a strong bearish "
                "continuation signal."
            ),
        )

    if contains_any(
        market_direction,
        (
            "BEARISH",
        ),
    ):
        return (
            (
                "Market breadth improves sharply and advancing "
                "stocks become dominant."
            ),
            (
                "Broad positive sector rotation develops."
            ),
            (
                "Institutional short exposure reduces materially."
            ),
            (
                "Price structure confirms a bullish reversal."
            ),
            (
                "Options Intelligence develops a strong bullish "
                "continuation signal."
            ),
        )

    return (
        (
            "A broad and persistent bullish alignment invalidates "
            "the mixed regime."
        ),
        (
            "A broad and persistent bearish alignment invalidates "
            "the mixed regime."
        ),
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    *,
    snapshots: tuple[EngineSnapshot, ...],
    confidence: int,
    regime_alignment: str,
    risk_environment: str,
) -> tuple[str, ...]:
    """
    Build consolidated Market Regime Engine warnings.
    """

    warnings: list[str] = []

    for snapshot in snapshots:
        if snapshot.warning:
            warnings.append(
                snapshot.warning
            )

        if (
            snapshot.available
            and contains_any(
                snapshot.status,
                (
                    "INSUFFICIENT HISTORY",
                    "LIMITED HISTORY",
                    "PARTIAL",
                ),
            )
        ):
            warnings.append(
                f"{snapshot.engine_name} has limited "
                "historical confirmation."
            )

    if confidence < 55:
        warnings.append(
            "Market-regime confidence is below 55%."
        )

    if regime_alignment == "MIXED ALIGNMENT":
        warnings.append(
            "Major AQSD intelligence families are "
            "directionally mixed."
        )

    if risk_environment in {
        "HIGH",
        "VERY HIGH",
    }:
        warnings.append(
            f"Consolidated market-regime risk is "
            f"{risk_environment.lower()}."
        )

    if not warnings:
        warnings.append(
            "No major Market Regime Engine warning is active."
        )

    return tuple(
        dict.fromkeys(
            warnings
        )
    )
# ==========================================================
# SUMMARY AND EXPLANATION
# ==========================================================

def build_concise_summary(
    *,
    primary_regime: str,
    secondary_regime: str,
    market_direction: str,
    regime_strength: str,
    regime_alignment: str,
    risk_environment: str,
    bullish_probability: float,
    bearish_probability: float,
    confidence: int,
    decision_quality: str,
) -> str:
    """
    Build a dashboard-ready regime summary.
    """

    return (
        f"{primary_regime} | "
        f"{secondary_regime} | "
        f"{market_direction} | "
        f"{regime_strength} STRENGTH | "
        f"{regime_alignment} | "
        f"{risk_environment} RISK | "
        f"BULL {bullish_probability:.1f}% | "
        f"BEAR {bearish_probability:.1f}% | "
        f"{confidence}% CONFIDENCE | "
        f"QUALITY {decision_quality}"
    )


def build_explanation(
    *,
    snapshots: tuple[EngineSnapshot, ...],
    primary_regime: str,
    secondary_regime: str,
    market_direction: str,
    regime_strength: str,
    regime_maturity: str,
    regime_alignment: str,
    risk_environment: str,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
    confidence: int,
    decision_quality: str,
) -> str:
    """
    Build the final explainable Market Regime conclusion.
    """

    engine_descriptions: list[str] = []

    for snapshot in snapshots:
        if snapshot.available:
            engine_descriptions.append(
                (
                    f"{snapshot.engine_name} reports bias "
                    f"{snapshot.bias.lower()}, direction "
                    f"{snapshot.direction.lower()}, environment "
                    f"{snapshot.environment.lower()}, risk "
                    f"{snapshot.risk.lower()} and confidence "
                    f"{snapshot.confidence}%."
                )
            )

        else:
            engine_descriptions.append(
                (
                    f"{snapshot.engine_name} is currently unavailable "
                    "and has received zero directional weight."
                )
            )

    return (
        " ".join(
            engine_descriptions
        )
        + " "
        + f"The consolidated market direction is "
        f"{market_direction.lower()}. "
        f"The primary regime is {primary_regime.lower()} and "
        f"the secondary regime is {secondary_regime.lower()}. "
        f"Regime strength is {regime_strength.lower()}, "
        f"maturity is {regime_maturity.lower()}, and engine "
        f"alignment is {regime_alignment.lower()}. "
        f"Bullish probability is {bullish_probability:.1f}%, "
        f"bearish probability is {bearish_probability:.1f}% "
        f"and neutral probability is "
        f"{neutral_probability:.1f}%. "
        f"Consolidated risk is {risk_environment.lower()}. "
        f"Final confidence is {confidence}% and decision "
        f"quality is grade {decision_quality}."
    )


def determine_master_conclusion(
    *,
    primary_regime: str,
    market_direction: str,
    regime_strength: str,
    regime_alignment: str,
    risk_environment: str,
) -> str:
    """
    Build one final institutional-style regime conclusion.
    """

    if market_direction == "STRONGLY BULLISH":
        return (
            "THE MARKET IS IN A HIGH-QUALITY BULLISH REGIME. "
            "MULTIPLE AQSD INTELLIGENCE FAMILIES SUPPORT "
            "POSITIVE CONTINUATION WHILE CONFIRMATION "
            "CONDITIONS REMAIN INTACT."
        )

    if market_direction == "BULLISH":
        return (
            f"THE MARKET IS IN A {primary_regime}. "
            "THE DIRECTIONAL BIAS IS POSITIVE, BUT THE REGIME "
            "SHOULD REMAIN CONDITIONAL ON BREADTH, SECTOR AND "
            "INSTITUTIONAL CONFIRMATION."
        )

    if market_direction == "STRONGLY BEARISH":
        return (
            "THE MARKET IS IN A HIGH-QUALITY BEARISH REGIME. "
            "MULTIPLE AQSD INTELLIGENCE FAMILIES SUPPORT "
            "CONTINUED PRESSURE AND ELEVATED DEFENSIVE RISK."
        )

    if market_direction == "BEARISH":
        return (
            f"THE MARKET IS IN A {primary_regime}. "
            "BEARISH EXPOSURE REMAINS DOMINANT, ALTHOUGH "
            "RECOVERY AND SHORT-COVERING RISK MUST CONTINUE "
            "TO BE MONITORED."
        )

    return (
        f"THE MARKET IS IN A {primary_regime}. "
        f"REGIME STRENGTH IS {regime_strength}, "
        f"ENGINE ALIGNMENT IS {regime_alignment}, "
        f"AND RISK IS {risk_environment}. "
        "THE MARKET SHOULD BE TREATED AS ROTATIONAL OR "
        "TRANSITIONAL UNTIL STRONGER DIRECTIONAL ALIGNMENT "
        "DEVELOPS."
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_market_regime_engine(
    *,
    requested_date: date,
    breadth_source_file: Path = DEFAULT_BREADTH_INPUT_FILE,
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
) -> MarketRegimeResult:
    """
    Run the complete AQSD Market Regime Engine.
    """

    if weekly_lookback_sessions < 1:
        raise ValueError(
            "weekly_lookback_sessions must be at least 1."
        )

    breadth_snapshot = run_breadth_adapter(
        requested_date=requested_date,
        source_file=breadth_source_file,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    sector_snapshot = run_sector_adapter(
        requested_date=requested_date,
        source_file=breadth_source_file,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    participant_snapshot = run_participant_adapter(
        requested_date=requested_date,
    )

    options_snapshot = run_options_adapter(
        requested_date=requested_date,
    )

    structure_snapshot = run_structure_adapter(
        requested_date=requested_date,
    )

    snapshots = (
        breadth_snapshot,
        sector_snapshot,
        participant_snapshot,
        options_snapshot,
        structure_snapshot,
    )

    available_engines = sum(
        snapshot.available
        for snapshot in snapshots
    )

    total_engines = len(
        snapshots
    )

    (
        bullish_probability,
        bearish_probability,
        neutral_probability,
    ) = calculate_regime_probabilities(
        snapshots
    )

    market_direction = determine_market_direction(
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
    )

    primary_regime = determine_primary_regime(
        market_direction=market_direction,
        snapshots=snapshots,
    )

    secondary_regime = determine_secondary_regime(
        snapshots
    )

    risk_environment = determine_risk_environment(
        snapshots
    )

    regime_strength = determine_regime_strength(
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
    )

    regime_alignment = determine_regime_alignment(
        snapshots
    )

    regime_maturity = determine_regime_maturity(
        primary_regime=primary_regime,
        snapshots=snapshots,
    )

    confidence = calculate_regime_confidence(
        snapshots=snapshots,
        regime_alignment=regime_alignment,
        regime_strength=regime_strength,
    )

    decision_quality = determine_decision_quality(
        confidence=confidence,
        regime_strength=regime_strength,
        regime_alignment=regime_alignment,
        risk_environment=risk_environment,
    )

    expected_behaviour = determine_expected_behaviour(
        primary_regime=primary_regime,
        market_direction=market_direction,
        risk_environment=risk_environment,
    )

    analytical_posture = determine_analytical_posture(
        decision_quality=decision_quality,
        confidence=confidence,
        risk_environment=risk_environment,
        available_engines=available_engines,
    )

    confirmation_conditions = build_confirmation_conditions(
        market_direction=market_direction,
        snapshots=snapshots,
    )

    invalidation_conditions = build_invalidation_conditions(
        market_direction=market_direction,
    )

    warnings = build_warnings(
        snapshots=snapshots,
        confidence=confidence,
        regime_alignment=regime_alignment,
        risk_environment=risk_environment,
    )

    trend_environment = (
        structure_snapshot.environment
        if structure_snapshot.available
        else "NOT YET CONNECTED"
    )

    breadth_environment = (
        breadth_snapshot.environment
        if breadth_snapshot.available
        else "NOT AVAILABLE"
    )

    sector_environment = (
        sector_snapshot.environment
        if sector_snapshot.available
        else "NOT AVAILABLE"
    )

    institutional_environment = (
        participant_snapshot.environment
        if participant_snapshot.available
        else "NOT AVAILABLE"
    )

    options_environment = (
        options_snapshot.environment
        if options_snapshot.available
        else "NOT YET CONNECTED"
    )

    market_environment = (
        f"{primary_regime} | "
        f"{market_direction} | "
        f"{regime_strength} STRENGTH | "
        f"{regime_alignment} | "
        f"{risk_environment} RISK"
    )

    concise_summary = build_concise_summary(
        primary_regime=primary_regime,
        secondary_regime=secondary_regime,
        market_direction=market_direction,
        regime_strength=regime_strength,
        regime_alignment=regime_alignment,
        risk_environment=risk_environment,
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        confidence=confidence,
        decision_quality=decision_quality,
    )

    explanation = build_explanation(
        snapshots=snapshots,
        primary_regime=primary_regime,
        secondary_regime=secondary_regime,
        market_direction=market_direction,
        regime_strength=regime_strength,
        regime_maturity=regime_maturity,
        regime_alignment=regime_alignment,
        risk_environment=risk_environment,
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
        confidence=confidence,
        decision_quality=decision_quality,
    )

    master_conclusion = determine_master_conclusion(
        primary_regime=primary_regime,
        market_direction=market_direction,
        regime_strength=regime_strength,
        regime_alignment=regime_alignment,
        risk_environment=risk_environment,
    )

    if available_engines == 0:
        status = "FAILED"

    elif available_engines < total_engines:
        status = "SUCCESS WITH PARTIAL INPUTS"

    else:
        status = "SUCCESS"

    return MarketRegimeResult(
        requested_date=requested_date,
        analysis_date=requested_date,

        primary_regime=primary_regime,
        secondary_regime=secondary_regime,
        market_direction=market_direction,

        trend_environment=trend_environment,
        breadth_environment=breadth_environment,
        sector_environment=sector_environment,
        institutional_environment=(
            institutional_environment
        ),
        options_environment=options_environment,

        risk_environment=risk_environment,
        regime_strength=regime_strength,
        regime_maturity=regime_maturity,
        regime_alignment=regime_alignment,

        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,

        confidence=confidence,
        decision_quality=decision_quality,

        expected_behaviour=expected_behaviour,
        analytical_posture=analytical_posture,
        market_environment=market_environment,

        confirmation_conditions=(
            confirmation_conditions
        ),
        invalidation_conditions=(
            invalidation_conditions
        ),
        warnings=warnings,

        concise_summary=concise_summary,
        explanation=explanation,
        master_conclusion=master_conclusion,

        breadth_snapshot=breadth_snapshot,
        sector_snapshot=sector_snapshot,
        participant_snapshot=participant_snapshot,
        options_snapshot=options_snapshot,
        structure_snapshot=structure_snapshot,

        available_engines=available_engines,
        total_engines=total_engines,
        status=status,
    )


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def display_snapshot(
    snapshot: EngineSnapshot,
) -> None:
    """
    Display one normalized engine snapshot.
    """

    print(
        f"Engine                              : "
        f"{snapshot.engine_name}"
    )
    print(
        f"Available                           : "
        f"{snapshot.available}"
    )
    print(
        f"Status                              : "
        f"{snapshot.status}"
    )
    print(
        f"Bias                                : "
        f"{snapshot.bias}"
    )
    print(
        f"Direction                           : "
        f"{snapshot.direction}"
    )
    print(
        f"Environment                         : "
        f"{snapshot.environment}"
    )
    print(
        f"Strength                            : "
        f"{snapshot.strength}"
    )
    print(
        f"Risk                                : "
        f"{snapshot.risk}"
    )
    print(
        f"Confidence                          : "
        f"{snapshot.confidence}%"
    )
    print(
        f"Bullish Score                       : "
        f"{snapshot.bullish_score}%"
    )
    print(
        f"Bearish Score                       : "
        f"{snapshot.bearish_score}%"
    )
    print(
        f"Neutral Score                       : "
        f"{snapshot.neutral_score}%"
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketRegimeResult,
) -> None:
    """
    Display the complete Market Regime result.
    """

    print()
    print("=" * 116)
    print("AQSD MARKET REGIME ENGINE")
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
        f"Available Engines                   : "
        f"{result.available_engines}/"
        f"{result.total_engines}"
    )
    print("-" * 116)

    print("REGIME CLASSIFICATION")
    print("-" * 116)
    print(
        f"Primary Regime                      : "
        f"{result.primary_regime}"
    )
    print(
        f"Secondary Regime                    : "
        f"{result.secondary_regime}"
    )
    print(
        f"Market Direction                    : "
        f"{result.market_direction}"
    )
    print(
        f"Regime Strength                     : "
        f"{result.regime_strength}"
    )
    print(
        f"Regime Maturity                     : "
        f"{result.regime_maturity}"
    )
    print(
        f"Regime Alignment                    : "
        f"{result.regime_alignment}"
    )
    print("-" * 116)

    print("INTELLIGENCE ENVIRONMENT")
    print("-" * 116)
    print(
        f"Trend Environment                   : "
        f"{result.trend_environment}"
    )
    print(
        f"Breadth Environment                 : "
        f"{result.breadth_environment}"
    )
    print(
        f"Sector Environment                  : "
        f"{result.sector_environment}"
    )
    print(
        f"Institutional Environment           : "
        f"{result.institutional_environment}"
    )
    print(
        f"Options Environment                 : "
        f"{result.options_environment}"
    )
    print(
        f"Risk Environment                    : "
        f"{result.risk_environment}"
    )
    print("-" * 116)

    print("REGIME PROBABILITIES")
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
    print(
        f"Confidence                          : "
        f"{result.confidence}%"
    )
    print(
        f"Decision Quality                    : "
        f"{result.decision_quality}"
    )
    print("-" * 116)

    print("EXPECTED BEHAVIOUR")
    print("-" * 116)
    print(
        result.expected_behaviour
    )

    print("-" * 116)
    print("ANALYTICAL POSTURE")
    print("-" * 116)
    print(
        result.analytical_posture
    )

    print("-" * 116)
    print("MARKET ENVIRONMENT")
    print("-" * 116)
    print(
        result.market_environment
    )

    print("-" * 116)
    print("MASTER CONCLUSION")
    print("-" * 116)
    print(
        result.master_conclusion
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
    print("ENGINE INPUTS")
    print("-" * 116)

    for snapshot in (
        result.breadth_snapshot,
        result.sector_snapshot,
        result.participant_snapshot,
        result.options_snapshot,
        result.structure_snapshot,
    ):
        display_snapshot(
            snapshot
        )

        print("-" * 116)

    print("EXPLANATION")
    print("-" * 116)
    print(
        result.explanation
    )

    print("-" * 116)
    print(
        "Method                              : "
        "RULE-BASED MULTI-ENGINE MARKET REGIME"
    )
    print(
        f"Status                              : "
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
            "Run the AQSD Market Regime Engine."
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

    if arguments.weekly_sessions < 1:
        print()
        print("Status : FAILED")
        print(
            "Reason : --weekly-sessions must be at least 1."
        )

        raise SystemExit(1)

    try:
        result = run_market_regime_engine(
            requested_date=parse_date(
                arguments.date
            ),
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
        print("AQSD MARKET REGIME ENGINE")
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