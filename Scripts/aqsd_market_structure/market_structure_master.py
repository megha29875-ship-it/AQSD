"""
AQSD
Market Structure Master

Module : MSM-001
Version: 1.0.0
Author : AQSD

Description
-----------
Provides one stable entry point for AQSD Market Structure intelligence.

The master attempts to combine the currently available structure
components:

    Trend
    Swing Structure
    Break of Structure
    Change of Character
    Market Phase
    Market Regime
    Confidence
    Risk
    Expected Behaviour

The module is designed as a compatibility layer. It safely checks
different AQSD module and function names without stopping the broader
Market Intelligence Pipeline when an individual structure component
is unavailable.

Primary public function
-----------------------
def run_market_structure_components(
    *,
    requested_date: date,
    symbol: str,
) -> tuple[
    StructureComponentResult,
    StructureComponentResult,
    StructureComponentResult,
    StructureComponentResult,
    StructureComponentResult,
    StructureComponentResult,
]:
    """
    Download market data once and run the actual AQSD Market
    Structure functions already used by test_engine.py.
    """

    try:
        test_engine = importlib.import_module(
            "Scripts.aqsd_market_structure.test_engine"
        )

        fyers = test_engine.create_fyers_client()

        market_data = test_engine.download_fyers_history(
            fyers=fyers,
            symbol=symbol,
        )

        trend_result = test_engine.analyze_trend(
            market_data
        )

        swing_highs, swing_lows = (
            test_engine.detect_and_classify_swings(
                market_data
            )
        )

        bos_result = test_engine.detect_break_of_structure(
            market_data
        )

        choch_result = test_engine.detect_change_of_character(
            market_data
        )

        confidence_result = test_engine.calculate_confidence(
            trend_result=trend_result,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            bos_result=bos_result,
            choch_result=choch_result,
        )

        regime_result = test_engine.analyze_market_regime(
            trend_result=trend_result,
            confidence_result=confidence_result,
            bos_result=bos_result,
            choch_result=choch_result,
        )

        phase_result = test_engine.analyze_market_phase(
            trend_result=trend_result,
            confidence_result=confidence_result,
            regime_result=regime_result,
            bos_result=bos_result,
            choch_result=choch_result,
        )

        common_confidence = safe_int(
            first_value(
                confidence_result,
                (
                    "confidence",
                    "confidence_score",
                    "overall_confidence",
                    "score",
                ),
                50,
            )
        )

        trend_component = normalize_component_result(
            component_name="TREND ENGINE",
            result=trend_result,
            bias_fields=(
                "market_bias",
                "trend_bias",
                "trend",
                "direction",
            ),
            direction_fields=(
                "trend",
                "trend_direction",
                "direction",
            ),
            state_fields=(
                "trend",
                "trend_state",
                "state",
            ),
            quality_fields=(
                "trend_strength",
                "strength",
                "trend_quality",
                "quality",
            ),
            risk_fields=(
                "risk_level",
                "trend_risk",
            ),
            confidence_fields=(
                "confidence",
                "trend_confidence",
                "strength_score",
            ),
        )

        latest_high = (
            swing_highs[-1]
            if swing_highs
            else None
        )

        latest_low = (
            swing_lows[-1]
            if swing_lows
            else None
        )

        high_type = normalize_text(
            first_value(
                latest_high,
                (
                    "swing_type",
                    "type",
                    "classification",
                ),
                "NO HIGH",
            )
        )

        low_type = normalize_text(
            first_value(
                latest_low,
                (
                    "swing_type",
                    "type",
                    "classification",
                ),
                "NO LOW",
            )
        )

        swing_state = (
            f"{high_type} / {low_type}"
        )

        swing_bias = "NEUTRAL"

        if (
            "HH" in high_type
            and "HL" in low_type
        ):
            swing_bias = "BULLISH"

        elif (
            "LH" in high_type
            and "LL" in low_type
        ):
            swing_bias = "BEARISH"

        swing_component = StructureComponentResult(
            component_name="SWING STRUCTURE ENGINE",
            available=True,
            status="SUCCESS",
            bias=swing_bias,
            direction=swing_bias,
            state=swing_state,
            quality="AVAILABLE",
            risk="NOT AVAILABLE",
            confidence=common_confidence,
            expected_behaviour="STRUCTURAL SWING SEQUENCE",
            summary=swing_state,
            explanation=(
                f"Latest swing high is {high_type} and "
                f"latest swing low is {low_type}."
            ),
            warning=None,
        )

        bos_component = normalize_component_result(
            component_name="BREAK OF STRUCTURE ENGINE",
            result=bos_result,
            bias_fields=(
                "bias",
                "bos_bias",
                "market_bias",
                "direction",
            ),
            direction_fields=(
                "direction",
                "bos_direction",
                "break_direction",
            ),
            state_fields=(
                "bos_state",
                "break_of_structure",
                "signal",
                "state",
            ),
            quality_fields=(
                "quality",
                "bos_quality",
                "strength",
            ),
            risk_fields=(
                "risk_level",
                "bos_risk",
            ),
            confidence_fields=(
                "confidence",
                "bos_confidence",
            ),
        )

        choch_component = normalize_component_result(
            component_name="CHANGE OF CHARACTER ENGINE",
            result=choch_result,
            bias_fields=(
                "bias",
                "choch_bias",
                "market_bias",
                "direction",
            ),
            direction_fields=(
                "direction",
                "choch_direction",
                "change_direction",
            ),
            state_fields=(
                "choch_state",
                "change_of_character",
                "signal",
                "state",
            ),
            quality_fields=(
                "quality",
                "choch_quality",
                "strength",
            ),
            risk_fields=(
                "risk_level",
                "reversal_risk",
                "choch_risk",
            ),
            confidence_fields=(
                "confidence",
                "choch_confidence",
            ),
        )

        phase_component = normalize_component_result(
            component_name="MARKET PHASE ENGINE",
            result=phase_result,
            bias_fields=(
                "market_bias",
                "phase_bias",
                "bias",
                "direction",
            ),
            direction_fields=(
                "phase_direction",
                "market_direction",
                "direction",
            ),
            state_fields=(
                "market_phase",
                "phase",
                "state",
            ),
            quality_fields=(
                "phase_quality",
                "quality",
                "strength",
            ),
            risk_fields=(
                "risk_level",
                "phase_risk",
            ),
            confidence_fields=(
                "confidence",
                "phase_confidence",
            ),
        )

        legacy_component = normalize_component_result(
            component_name="MARKET REGIME ENGINE",
            result=regime_result,
            bias_fields=(
                "market_bias",
                "regime_bias",
                "bias",
                "direction",
            ),
            direction_fields=(
                "market_direction",
                "regime_direction",
                "direction",
            ),
            state_fields=(
                "market_regime",
                "regime",
                "state",
            ),
            quality_fields=(
                "regime_strength",
                "quality",
                "strength",
            ),
            risk_fields=(
                "risk_level",
                "regime_risk",
            ),
            confidence_fields=(
                "confidence",
                "regime_confidence",
            ),
        )

        # Apply the combined confidence where individual components
        # do not expose their own confidence value.

        def apply_confidence(
            component: StructureComponentResult,
        ) -> StructureComponentResult:
            if component.confidence > 0:
                return component

            return StructureComponentResult(
                component_name=component.component_name,
                available=component.available,
                status=component.status,
                bias=component.bias,
                direction=component.direction,
                state=component.state,
                quality=component.quality,
                risk=component.risk,
                confidence=common_confidence,
                expected_behaviour=(
                    component.expected_behaviour
                ),
                summary=component.summary,
                explanation=component.explanation,
                warning=component.warning,
            )

        return (
            apply_confidence(
                legacy_component
            ),
            apply_confidence(
                trend_component
            ),
            apply_confidence(
                swing_component
            ),
            apply_confidence(
                bos_component
            ),
            apply_confidence(
                choch_component
            ),
            apply_confidence(
                phase_component
            ),
        )

    except Exception as exc:
        warning = (
            "Integrated Market Structure analysis failed: "
            f"{type(exc).__name__}: {exc}"
        )

        return (
            empty_component(
                component_name="MARKET REGIME ENGINE",
                warning=warning,
            ),
            empty_component(
                component_name="TREND ENGINE",
                warning=warning,
            ),
            empty_component(
                component_name="SWING STRUCTURE ENGINE",
                warning=warning,
            ),
            empty_component(
                component_name="BREAK OF STRUCTURE ENGINE",
                warning=warning,
            ),
            empty_component(
                component_name="CHANGE OF CHARACTER ENGINE",
                warning=warning,
            ),
            empty_component(
                component_name="MARKET PHASE ENGINE",
                warning=warning,
            ),
        )
run_market_structure_master(...)

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

MODULE_ID: Final[str] = "MSM-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DEFAULT_SYMBOL: Final[str] = "NSE:NIFTYBANK-INDEX"
DEFAULT_LOOKBACK_DAYS: Final[int] = 450


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class StructureComponentResult:
    """
    Normalized result from one Market Structure component.
    """

    component_name: str
    available: bool
    status: str

    bias: str
    direction: str
    state: str
    quality: str
    risk: str
    confidence: int

    expected_behaviour: str
    summary: str
    explanation: str
    warning: str | None


@dataclass(frozen=True)
class MarketStructureMasterResult:
    """
    Final output of the AQSD Market Structure Master.
    """

    requested_date: date
    analysis_date: date
    symbol: str

    market_bias: str
    trend_direction: str
    trend_quality: str

    swing_structure: str
    structural_state: str

    bos_state: str
    choch_state: str

    market_phase: str
    market_regime: str
    market_environment: str

    structural_quality: str
    structure_risk: str

    bullish_probability: float
    bearish_probability: float
    neutral_probability: float

    confidence: int
    decision_quality: str

    expected_behaviour: str
    analytical_posture: str

    confirmation_conditions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    warnings: tuple[str, ...]

    concise_summary: str
    explanation: str
    master_conclusion: str

    trend_component: StructureComponentResult
    swing_component: StructureComponentResult
    bos_component: StructureComponentResult
    choch_component: StructureComponentResult
    phase_component: StructureComponentResult
    legacy_component: StructureComponentResult

    available_components: int
    total_components: int
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

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


def safe_int(
    value: object,
    default: int = 0,
) -> int:
    """
    Convert a value to integer safely.
    """

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


def first_value(
    result: object,
    names: tuple[str, ...],
    default: object = None,
) -> object:
    """
    Read the first available value from an object or dictionary.
    """

    for name in names:
        if isinstance(
            result,
            dict,
        ):
            if name in result:
                return result[name]

        if hasattr(
            result,
            "get",
        ):
            try:
                value = result.get(
                    name,
                    None,
                )

                if value is not None:
                    return value

            except Exception:
                pass

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
    Call a function using only supported keyword arguments.
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


def empty_component(
    *,
    component_name: str,
    warning: str,
) -> StructureComponentResult:
    """
    Create an unavailable component result.
    """

    return StructureComponentResult(
        component_name=component_name,
        available=False,
        status="NOT AVAILABLE",

        bias="UNKNOWN",
        direction="UNKNOWN",
        state="NOT AVAILABLE",
        quality="NOT AVAILABLE",
        risk="NOT AVAILABLE",
        confidence=0,

        expected_behaviour="NOT AVAILABLE",
        summary="NOT AVAILABLE",
        explanation="NOT AVAILABLE",
        warning=warning,
    )


def normalize_component_result(
    *,
    component_name: str,
    result: object,
    bias_fields: tuple[str, ...],
    direction_fields: tuple[str, ...],
    state_fields: tuple[str, ...],
    quality_fields: tuple[str, ...],
    risk_fields: tuple[str, ...],
    confidence_fields: tuple[str, ...],
) -> StructureComponentResult:
    """
    Normalize one structure-engine result.
    """

    bias = normalize_text(
        first_value(
            result,
            bias_fields,
            "UNKNOWN",
        )
    )

    direction = normalize_text(
        first_value(
            result,
            direction_fields,
            "UNKNOWN",
        )
    )

    state = normalize_text(
        first_value(
            result,
            state_fields,
            "NOT AVAILABLE",
        )
    )

    quality = normalize_text(
        first_value(
            result,
            quality_fields,
            "NOT AVAILABLE",
        )
    )

    risk = normalize_text(
        first_value(
            result,
            risk_fields,
            "NOT AVAILABLE",
        )
    )

    confidence = safe_int(
        first_value(
            result,
            confidence_fields,
            0,
        )
    )

    status = normalize_text(
        first_value(
            result,
            (
                "status",
                "overall_status",
            ),
            "SUCCESS",
        )
    )

    expected_behaviour = normalize_text(
        first_value(
            result,
            (
                "expected_behaviour",
                "expected_behavior",
                "interpretation",
            ),
            "NOT AVAILABLE",
        )
    )

    summary = str(
        first_value(
            result,
            (
                "concise_summary",
                "summary",
                "interpretation",
                "master_conclusion",
            ),
            (
                f"{bias} | {direction} | "
                f"{state} | {confidence}% CONFIDENCE"
            ),
        )
    )

    explanation = str(
        first_value(
            result,
            (
                "explanation",
                "interpretation",
                "summary",
                "master_conclusion",
            ),
            summary,
        )
    )

    return StructureComponentResult(
        component_name=component_name,
        available=True,
        status=status,

        bias=bias,
        direction=direction,
        state=state,
        quality=quality,
        risk=risk,
        confidence=confidence,

        expected_behaviour=expected_behaviour,
        summary=summary,
        explanation=explanation,
        warning=None,
    )


# ==========================================================
# GENERIC COMPONENT LOADER
# ==========================================================

def run_component_adapter(
    *,
    component_name: str,
    module_candidates: tuple[str, ...],
    runner_candidates: tuple[str, ...],
    arguments: dict[str, object],
    bias_fields: tuple[str, ...],
    direction_fields: tuple[str, ...],
    state_fields: tuple[str, ...],
    quality_fields: tuple[str, ...],
    risk_fields: tuple[str, ...],
    confidence_fields: tuple[str, ...],
) -> StructureComponentResult:
    """
    Run the first compatible component module.
    """

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
                    candidate = getattr(
                        module,
                        runner_name,
                    )

                    if callable(
                        candidate
                    ):
                        runner = candidate
                        break

            if runner is None:
                available_functions = [
                    name
                    for name in dir(module)
                    if (
                        not name.startswith("_")
                        and callable(
                            getattr(
                                module,
                                name,
                            )
                        )
                    )
                ]

                raise AttributeError(
                    "No supported runner was found. "
                    f"Available functions: {available_functions}"
                )

            result = call_with_supported_arguments(
                runner,
                arguments,
            )

            return normalize_component_result(
                component_name=component_name,
                result=result,
                bias_fields=bias_fields,
                direction_fields=direction_fields,
                state_fields=state_fields,
                quality_fields=quality_fields,
                risk_fields=risk_fields,
                confidence_fields=confidence_fields,
            )

        except Exception as exc:
            errors.append(
                f"{module_name}: {exc}"
            )

    return empty_component(
        component_name=component_name,
        warning=(
            f"{component_name} could not be connected: "
            + " | ".join(errors)
        ),
    )


# ==========================================================
# LEGACY MASTER ADAPTER
# ==========================================================

def run_legacy_structure_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to use the existing top-level AQSD structure engine.
    """

    return run_component_adapter(
        component_name="LEGACY MARKET STRUCTURE ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure_engine",
        ),
        runner_candidates=(
            "run_market_structure_engine",
            "run_market_structure",
            "analyze_market_structure",
            "analyze_structure",
            "calculate_market_structure",
            "calculate",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "date_value": requested_date,
            "symbol": symbol,
            "underlying": "BANKNIFTY",
            "lookback_days": lookback_days,
            "export": False,
            "save_output": False,
        },
        bias_fields=(
            "market_bias",
            "final_bias",
            "bias",
            "trend",
        ),
        direction_fields=(
            "trend_direction",
            "market_direction",
            "structure_direction",
            "direction",
        ),
        state_fields=(
            "structural_state",
            "market_structure",
            "structure",
            "market_phase",
            "market_regime",
        ),
        quality_fields=(
            "structural_quality",
            "trend_quality",
            "decision_quality",
            "structure_quality",
        ),
        risk_fields=(
            "risk_level",
            "structure_risk",
            "market_risk",
            "structural_risk",
        ),
        confidence_fields=(
            "confidence",
            "overall_confidence",
            "decision_confidence",
            "structure_confidence",
            "probability",
        ),
    )


# ==========================================================
# TREND ADAPTER
# ==========================================================

def run_trend_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to run the AQSD Trend Engine.
    """

    return run_component_adapter(
        component_name="TREND ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure.trend",
            "Scripts.aqsd_market_structure.trend_engine",
        ),
        runner_candidates=(
            "run_trend_engine",
            "analyze_trend",
            "calculate_trend",
            "determine_trend",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "symbol": symbol,
            "lookback_days": lookback_days,
        },
        bias_fields=(
            "market_bias",
            "trend_bias",
            "bias",
            "trend",
        ),
        direction_fields=(
            "trend_direction",
            "direction",
            "trend",
        ),
        state_fields=(
            "trend_state",
            "state",
            "market_phase",
        ),
        quality_fields=(
            "trend_quality",
            "quality",
            "trend_strength",
        ),
        risk_fields=(
            "risk_level",
            "trend_risk",
        ),
        confidence_fields=(
            "confidence",
            "trend_confidence",
            "overall_confidence",
        ),
    )


# ==========================================================
# SWING ADAPTER
# ==========================================================

def run_swing_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to run the AQSD Swing Structure Engine.
    """

    return run_component_adapter(
        component_name="SWING STRUCTURE ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure.swings",
            "Scripts.aqsd_market_structure.swing_engine",
        ),
        runner_candidates=(
            "run_swing_engine",
            "analyze_swings",
            "detect_swings",
            "calculate_swings",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "symbol": symbol,
            "lookback_days": lookback_days,
        },
        bias_fields=(
            "market_bias",
            "swing_bias",
            "bias",
        ),
        direction_fields=(
            "swing_direction",
            "structure_direction",
            "direction",
        ),
        state_fields=(
            "swing_structure",
            "structural_state",
            "structure",
            "state",
        ),
        quality_fields=(
            "swing_quality",
            "structural_quality",
            "quality",
        ),
        risk_fields=(
            "risk_level",
            "swing_risk",
            "structure_risk",
        ),
        confidence_fields=(
            "confidence",
            "swing_confidence",
            "structure_confidence",
        ),
    )


# ==========================================================
# BOS ADAPTER
# ==========================================================

def run_bos_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to run the Break of Structure Engine.
    """

    return run_component_adapter(
        component_name="BREAK OF STRUCTURE ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure.bos",
            "Scripts.aqsd_market_structure.bos_engine",
            "Scripts.aqsd_market_structure.break_of_structure",
        ),
        runner_candidates=(
            "run_bos_engine",
            "analyze_bos",
            "detect_bos",
            "detect_break_of_structure",
            "calculate_bos",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "symbol": symbol,
            "lookback_days": lookback_days,
        },
        bias_fields=(
            "market_bias",
            "bos_bias",
            "bias",
        ),
        direction_fields=(
            "bos_direction",
            "break_direction",
            "direction",
        ),
        state_fields=(
            "bos_state",
            "break_of_structure",
            "state",
        ),
        quality_fields=(
            "bos_quality",
            "structural_quality",
            "quality",
        ),
        risk_fields=(
            "risk_level",
            "bos_risk",
        ),
        confidence_fields=(
            "confidence",
            "bos_confidence",
            "structure_confidence",
        ),
    )


# ==========================================================
# CHOCH ADAPTER
# ==========================================================

def run_choch_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to run the Change of Character Engine.
    """

    return run_component_adapter(
        component_name="CHANGE OF CHARACTER ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure.choch",
            "Scripts.aqsd_market_structure.choch_engine",
            "Scripts.aqsd_market_structure.change_of_character",
        ),
        runner_candidates=(
            "run_choch_engine",
            "analyze_choch",
            "detect_choch",
            "detect_change_of_character",
            "calculate_choch",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "symbol": symbol,
            "lookback_days": lookback_days,
        },
        bias_fields=(
            "market_bias",
            "choch_bias",
            "bias",
        ),
        direction_fields=(
            "choch_direction",
            "change_direction",
            "direction",
        ),
        state_fields=(
            "choch_state",
            "change_of_character",
            "state",
        ),
        quality_fields=(
            "choch_quality",
            "structural_quality",
            "quality",
        ),
        risk_fields=(
            "risk_level",
            "choch_risk",
            "reversal_risk",
        ),
        confidence_fields=(
            "confidence",
            "choch_confidence",
            "structure_confidence",
        ),
    )


# ==========================================================
# MARKET PHASE ADAPTER
# ==========================================================

def run_phase_adapter(
    *,
    requested_date: date,
    symbol: str,
    lookback_days: int,
) -> StructureComponentResult:
    """
    Attempt to run the Market Phase Engine.
    """

    return run_component_adapter(
        component_name="MARKET PHASE ENGINE",
        module_candidates=(
            "Scripts.aqsd_market_structure.market_phase",
            "Scripts.aqsd_market_structure.market_phase_engine",
            "Scripts.aqsd_market_structure.phase_engine",
        ),
        runner_candidates=(
            "run_market_phase_engine",
            "run_market_phase",
            "analyze_market_phase",
            "determine_market_phase",
            "calculate_market_phase",
            "run",
        ),
        arguments={
            "requested_date": requested_date,
            "trade_date": requested_date,
            "analysis_date": requested_date,
            "symbol": symbol,
            "lookback_days": lookback_days,
        },
        bias_fields=(
            "market_bias",
            "phase_bias",
            "bias",
        ),
        direction_fields=(
            "phase_direction",
            "market_direction",
            "direction",
        ),
        state_fields=(
            "market_phase",
            "phase",
            "market_regime",
            "state",
        ),
        quality_fields=(
            "phase_quality",
            "regime_strength",
            "quality",
        ),
        risk_fields=(
            "risk_level",
            "phase_risk",
            "regime_risk",
        ),
        confidence_fields=(
            "confidence",
            "phase_confidence",
            "regime_confidence",
        ),
    )


# ==========================================================
# DIRECTIONAL SCORING
# ==========================================================

def calculate_component_scores(
    component: StructureComponentResult,
) -> tuple[int, int, int]:
    """
    Convert one component into bullish, bearish and neutral scores.
    """

    if not component.available:
        return (
            0,
            0,
            100,
        )

    combined = " | ".join(
        (
            component.bias,
            component.direction,
            component.state,
            component.expected_behaviour,
        )
    )

    bullish = 0
    bearish = 0
    neutral = 10

    if contains_any(
        combined,
        (
            "STRONGLY BULLISH",
            "UPTREND",
            "HIGHER HIGH",
            "HIGHER LOW",
            "HH",
            "HL",
            "BULLISH BOS",
            "BULLISH CHOCH",
            "MARKUP",
            "ACCUMULATION",
        ),
    ):
        bullish += 45

    if contains_any(
        combined,
        (
            "BULLISH",
            "POSITIVE",
            "RECOVERY",
            "IMPROVING",
            "UP",
        ),
    ):
        bullish += 20

    if contains_any(
        combined,
        (
            "STRONGLY BEARISH",
            "DOWNTREND",
            "LOWER HIGH",
            "LOWER LOW",
            "LH",
            "LL",
            "BEARISH BOS",
            "BEARISH CHOCH",
            "MARKDOWN",
            "DISTRIBUTION",
        ),
    ):
        bearish += 45

    if contains_any(
        combined,
        (
            "BEARISH",
            "NEGATIVE",
            "DETERIORATING",
            "DOWN",
            "WEAK",
        ),
    ):
        bearish += 20

    if contains_any(
        combined,
        (
            "NEUTRAL",
            "MIXED",
            "SIDEWAYS",
            "RANGE",
            "CONSOLIDATION",
            "UNKNOWN",
            "INSUFFICIENT",
        ),
    ):
        neutral += 30

    total = (
        bullish
        + bearish
        + neutral
    )

    return (
        clamp_score(
            bullish
            / total
            * 100
        ),
        clamp_score(
            bearish
            / total
            * 100
        ),
        clamp_score(
            neutral
            / total
            * 100
        ),
    )


def calculate_probabilities(
    components: tuple[StructureComponentResult, ...],
) -> tuple[float, float, float]:
    """
    Calculate structure probabilities from available components.
    """

    available_components = [
        component
        for component in components
        if component.available
    ]

    if not available_components:
        return (
            0.0,
            0.0,
            100.0,
        )

    bullish_total = 0.0
    bearish_total = 0.0
    neutral_total = 0.0
    weight_total = 0.0

    for component in available_components:
        bullish, bearish, neutral = (
            calculate_component_scores(
                component
            )
        )

        weight = max(
            component.confidence,
            35,
        )

        if contains_any(
            component.status,
            (
                "PARTIAL",
                "LIMITED",
                "INSUFFICIENT",
            ),
        ):
            weight *= 0.70

        bullish_total += (
            bullish
            * weight
        )
        bearish_total += (
            bearish
            * weight
        )
        neutral_total += (
            neutral
            * weight
        )
        weight_total += weight

    bullish_probability = (
        bullish_total
        / weight_total
    )

    bearish_probability = (
        bearish_total
        / weight_total
    )

    neutral_probability = (
        neutral_total
        / weight_total
    )

    total_probability = (
        bullish_probability
        + bearish_probability
        + neutral_probability
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
# MASTER CLASSIFICATION
# ==========================================================

def determine_market_bias(
    *,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> str:
    """
    Determine the final Market Structure bias.
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

    if bullish_probability > bearish_probability:
        return "MIXED WITH BULLISH TILT"

    if bearish_probability > bullish_probability:
        return "MIXED WITH BEARISH TILT"

    return "MIXED"


def determine_structural_state(
    *,
    trend_component: StructureComponentResult,
    swing_component: StructureComponentResult,
    legacy_component: StructureComponentResult,
) -> str:
    """
    Determine the main structural state.
    """

    if swing_component.available:
        return swing_component.state

    if legacy_component.available:
        return legacy_component.state

    if trend_component.available:
        return trend_component.state

    return "NOT AVAILABLE"


def determine_structural_quality(
    *,
    components: tuple[StructureComponentResult, ...],
    available_components: int,
) -> str:
    """
    Determine consolidated structure quality.
    """

    if available_components == 0:
        return "NOT AVAILABLE"

    confidences = [
        component.confidence
        for component in components
        if component.available
    ]

    average_confidence = (
        sum(confidences)
        / len(confidences)
    )

    if (
        available_components >= 5
        and average_confidence >= 78
    ):
        return "VERY HIGH"

    if (
        available_components >= 4
        and average_confidence >= 65
    ):
        return "HIGH"

    if (
        available_components >= 3
        and average_confidence >= 52
    ):
        return "MODERATE"

    if available_components >= 2:
        return "LOW TO MODERATE"

    return "LOW"


def determine_structure_risk(
    *,
    market_bias: str,
    choch_component: StructureComponentResult,
    available_components: int,
) -> str:
    """
    Determine consolidated Market Structure risk.
    """

    risk_score = 25

    if available_components < 3:
        risk_score += 25

    if choch_component.available:
        if contains_any(
            choch_component.state,
            (
                "CHOCH",
                "REVERSAL",
                "CHANGE",
            ),
        ):
            risk_score += 20

    if contains_any(
        market_bias,
        (
            "MIXED",
            "NEUTRAL",
        ),
    ):
        risk_score += 15

    if risk_score >= 75:
        return "VERY HIGH"

    if risk_score >= 60:
        return "HIGH"

    if risk_score >= 45:
        return "MODERATE"

    if risk_score >= 30:
        return "LOW TO MODERATE"

    return "LOW"


def calculate_master_confidence(
    *,
    components: tuple[StructureComponentResult, ...],
    structural_quality: str,
) -> int:
    """
    Calculate final structure confidence.
    """

    available_components = [
        component
        for component in components
        if component.available
    ]

    if not available_components:
        return 0

    confidence = (
        sum(
            component.confidence
            for component in available_components
        )
        / len(available_components)
    )

    confidence -= (
        len(components)
        - len(available_components)
    ) * 5

    if structural_quality == "VERY HIGH":
        confidence += 10

    elif structural_quality == "HIGH":
        confidence += 6

    elif structural_quality == "LOW":
        confidence -= 8

    return clamp_score(
        confidence
    )


def determine_decision_quality(
    *,
    confidence: int,
    structural_quality: str,
    structure_risk: str,
) -> str:
    """
    Determine AQSD structure decision grade.
    """

    if (
        confidence >= 82
        and structural_quality in {
            "VERY HIGH",
            "HIGH",
        }
        and structure_risk not in {
            "HIGH",
            "VERY HIGH",
        }
    ):
        return "A"

    if (
        confidence >= 68
        and structural_quality in {
            "HIGH",
            "MODERATE",
        }
        and structure_risk != "VERY HIGH"
    ):
        return "B"

    if confidence >= 52:
        return "C"

    return "D"


def determine_expected_behaviour(
    *,
    market_bias: str,
    market_phase: str,
    structure_risk: str,
) -> str:
    """
    Determine expected price behaviour.
    """

    if market_bias == "STRONGLY BULLISH":
        return (
            "POSITIVE STRUCTURAL CONTINUATION MAY REMAIN "
            "DOMINANT WHILE HIGHER-LOW STRUCTURE HOLDS"
        )

    if market_bias == "BULLISH":
        return (
            "POSITIVE CONTINUATION OR CONSTRUCTIVE PULLBACKS "
            "MAY CONTINUE"
        )

    if market_bias == "STRONGLY BEARISH":
        return (
            "NEGATIVE STRUCTURAL CONTINUATION MAY REMAIN "
            "DOMINANT WHILE LOWER-HIGH STRUCTURE HOLDS"
        )

    if market_bias == "BEARISH":
        return (
            "BEARISH CONTINUATION MAY REMAIN ACTIVE, "
            "ALTHOUGH SHORT-COVERING RECOVERIES ARE POSSIBLE"
        )

    if structure_risk in {
        "HIGH",
        "VERY HIGH",
    }:
        return (
            "STRUCTURE IS UNSTABLE AND RAPID REVERSALS "
            "OR FALSE BREAKOUTS MAY OCCUR"
        )

    if contains_any(
        market_phase,
        (
            "ACCUMULATION",
            "DISTRIBUTION",
            "CONSOLIDATION",
            "RANGE",
        ),
    ):
        return (
            "RANGE-BOUND OR ROTATIONAL PRICE BEHAVIOUR "
            "MAY CONTINUE"
        )

    return (
        "MARKET STRUCTURE REMAINS MIXED AND REQUIRES "
        "ADDITIONAL CONFIRMATION"
    )


# ==========================================================
# CONDITIONS AND WARNINGS
# ==========================================================

def build_confirmation_conditions(
    market_bias: str,
) -> tuple[str, ...]:
    """
    Build structure confirmation conditions.
    """

    if contains_any(
        market_bias,
        (
            "BULLISH",
        ),
    ):
        return (
            "Higher highs and higher lows should remain intact.",
            "A bullish Break of Structure should remain valid.",
            "A bearish Change of Character should not be confirmed.",
            "Price should remain above the latest protected swing low.",
        )

    if contains_any(
        market_bias,
        (
            "BEARISH",
        ),
    ):
        return (
            "Lower highs and lower lows should remain intact.",
            "A bearish Break of Structure should remain valid.",
            "A bullish Change of Character should not be confirmed.",
            "Price should remain below the latest protected swing high.",
        )

    return (
        "A confirmed directional Break of Structure should develop.",
        "Swing structure should develop a clear HH-HL or LH-LL sequence.",
        "Trend direction and market phase should become aligned.",
    )


def build_invalidation_conditions(
    market_bias: str,
) -> tuple[str, ...]:
    """
    Build structure invalidation conditions.
    """

    if contains_any(
        market_bias,
        (
            "BULLISH",
        ),
    ):
        return (
            "Price breaks the latest protected swing low.",
            "A bearish Change of Character is confirmed.",
            "The structure changes from HH-HL to LH-LL.",
        )

    if contains_any(
        market_bias,
        (
            "BEARISH",
        ),
    ):
        return (
            "Price breaks the latest protected swing high.",
            "A bullish Change of Character is confirmed.",
            "The structure changes from LH-LL to HH-HL.",
        )

    return (
        "A confirmed bullish structure invalidates the mixed state.",
        "A confirmed bearish structure invalidates the mixed state.",
    )


def build_warnings(
    components: tuple[StructureComponentResult, ...],
    confidence: int,
) -> tuple[str, ...]:
    """
    Build Market Structure warnings.
    """

    warnings: list[str] = []

    for component in components:
        if component.warning:
            warnings.append(
                component.warning
            )

        if (
            component.available
            and contains_any(
                component.status,
                (
                    "PARTIAL",
                    "LIMITED",
                    "INSUFFICIENT",
                ),
            )
        ):
            warnings.append(
                f"{component.component_name} has limited "
                "historical confirmation."
            )

    if confidence < 55:
        warnings.append(
            "Market Structure confidence is below 55%."
        )

    if not warnings:
        warnings.append(
            "No major Market Structure warning is active."
        )

    return tuple(
        dict.fromkeys(
            warnings
        )
    )


# ==========================================================
# MAIN MASTER
# ==========================================================

def run_market_structure_master(
    *,
    requested_date: date,
    symbol: str = DEFAULT_SYMBOL,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> MarketStructureMasterResult:
    """
    Run the complete AQSD Market Structure Master.
    """

    if lookback_days < 50:
        raise ValueError(
            "lookback_days must be at least 50."
        )

    (
        legacy_component,
        trend_component,
        swing_component,
        bos_component,
        choch_component,
        phase_component,
    ) = run_market_structure_components(
        requested_date=requested_date,
        symbol=symbol,
    )

    components = (
        legacy_component,
        trend_component,
        swing_component,
        bos_component,
        choch_component,
        phase_component,
    )
    components = (
        legacy_component,
        trend_component,
        swing_component,
        bos_component,
        choch_component,
        phase_component,
    )

    available_components = sum(
        component.available
        for component in components
    )

    total_components = len(
        components
    )

    (
        bullish_probability,
        bearish_probability,
        neutral_probability,
    ) = calculate_probabilities(
        components
    )

    market_bias = determine_market_bias(
        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,
    )

    trend_direction = (
        trend_component.direction
        if trend_component.available
        else legacy_component.direction
    )

    trend_quality = (
        trend_component.quality
        if trend_component.available
        else legacy_component.quality
    )

    swing_structure = (
        swing_component.state
        if swing_component.available
        else "NOT AVAILABLE"
    )

    structural_state = determine_structural_state(
        trend_component=trend_component,
        swing_component=swing_component,
        legacy_component=legacy_component,
    )

    bos_state = (
        bos_component.state
        if bos_component.available
        else "NOT AVAILABLE"
    )

    choch_state = (
        choch_component.state
        if choch_component.available
        else "NOT AVAILABLE"
    )

    market_phase = (
        phase_component.state
        if phase_component.available
        else "NOT AVAILABLE"
    )

    market_regime = (
        phase_component.direction
        if phase_component.available
        else structural_state
    )

    structural_quality = determine_structural_quality(
        components=components,
        available_components=available_components,
    )

    structure_risk = determine_structure_risk(
        market_bias=market_bias,
        choch_component=choch_component,
        available_components=available_components,
    )

    confidence = calculate_master_confidence(
        components=components,
        structural_quality=structural_quality,
    )

    decision_quality = determine_decision_quality(
        confidence=confidence,
        structural_quality=structural_quality,
        structure_risk=structure_risk,
    )

    expected_behaviour = determine_expected_behaviour(
        market_bias=market_bias,
        market_phase=market_phase,
        structure_risk=structure_risk,
    )

    analytical_posture = (
        "USE MARKET STRUCTURE WITH NORMAL WEIGHT"
        if confidence >= 65
        else (
            "USE MARKET STRUCTURE WITH MODERATE WEIGHT"
            if confidence >= 50
            else "REQUIRE ADDITIONAL STRUCTURAL CONFIRMATION"
        )
    )

    market_environment = (
        f"{market_bias} | "
        f"{trend_direction} | "
        f"{structural_state} | "
        f"{market_phase} | "
        f"{structure_risk} RISK"
    )

    confirmation_conditions = (
        build_confirmation_conditions(
            market_bias
        )
    )

    invalidation_conditions = (
        build_invalidation_conditions(
            market_bias
        )
    )

    warnings = build_warnings(
        components,
        confidence,
    )

    concise_summary = (
        f"{market_bias} | "
        f"TREND {trend_direction} | "
        f"STRUCTURE {structural_state} | "
        f"BOS {bos_state} | "
        f"CHOCH {choch_state} | "
        f"PHASE {market_phase} | "
        f"{structural_quality} QUALITY | "
        f"{structure_risk} RISK | "
        f"BULL {bullish_probability:.1f}% | "
        f"BEAR {bearish_probability:.1f}% | "
        f"{confidence}% CONFIDENCE | "
        f"GRADE {decision_quality}"
    )

    explanation = (
        f"The AQSD Market Structure Master found "
        f"{available_components} of {total_components} structure "
        f"components available. The final market bias is "
        f"{market_bias.lower()}, trend direction is "
        f"{trend_direction.lower()}, structural state is "
        f"{structural_state.lower()}, Break of Structure is "
        f"{bos_state.lower()}, Change of Character is "
        f"{choch_state.lower()}, and market phase is "
        f"{market_phase.lower()}. Bullish probability is "
        f"{bullish_probability:.1f}%, bearish probability is "
        f"{bearish_probability:.1f}% and neutral probability is "
        f"{neutral_probability:.1f}%. Structural quality is "
        f"{structural_quality.lower()}, risk is "
        f"{structure_risk.lower()}, confidence is {confidence}% "
        f"and decision grade is {decision_quality}."
    )

    master_conclusion = (
        f"MARKET STRUCTURE IS {market_bias}. "
        f"TREND IS {trend_direction}, STRUCTURAL STATE IS "
        f"{structural_state}, MARKET PHASE IS {market_phase}, "
        f"AND STRUCTURAL RISK IS {structure_risk}. "
        f"THE VIEW HAS {confidence}% CONFIDENCE."
    )

    if available_components == 0:
        status = "FAILED"

    elif available_components < total_components:
        status = "SUCCESS WITH PARTIAL INPUTS"

    else:
        status = "SUCCESS"

    return MarketStructureMasterResult(
        requested_date=requested_date,
        analysis_date=requested_date,
        symbol=symbol,

        market_bias=market_bias,
        trend_direction=trend_direction,
        trend_quality=trend_quality,

        swing_structure=swing_structure,
        structural_state=structural_state,

        bos_state=bos_state,
        choch_state=choch_state,

        market_phase=market_phase,
        market_regime=market_regime,
        market_environment=market_environment,

        structural_quality=structural_quality,
        structure_risk=structure_risk,

        bullish_probability=bullish_probability,
        bearish_probability=bearish_probability,
        neutral_probability=neutral_probability,

        confidence=confidence,
        decision_quality=decision_quality,

        expected_behaviour=expected_behaviour,
        analytical_posture=analytical_posture,

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

        trend_component=trend_component,
        swing_component=swing_component,
        bos_component=bos_component,
        choch_component=choch_component,
        phase_component=phase_component,
        legacy_component=legacy_component,

        available_components=available_components,
        total_components=total_components,
        status=status,
    )


# Compatible alias for other AQSD modules.
def run_market_structure(
    *,
    requested_date: date,
    symbol: str = DEFAULT_SYMBOL,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> MarketStructureMasterResult:
    """
    Compatibility alias for the Market Structure Master.
    """

    return run_market_structure_master(
        requested_date=requested_date,
        symbol=symbol,
        lookback_days=lookback_days,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketStructureMasterResult,
) -> None:
    """
    Display the complete Market Structure result.
    """

    print()
    print("=" * 110)
    print("AQSD MARKET STRUCTURE MASTER")
    print("=" * 110)
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Analysis Date              : {result.analysis_date}")
    print(f"Symbol                     : {result.symbol}")
    print(
        f"Available Components       : "
        f"{result.available_components}/"
        f"{result.total_components}"
    )
    print("-" * 110)

    print("STRUCTURE CLASSIFICATION")
    print("-" * 110)
    print(f"Market Bias                : {result.market_bias}")
    print(f"Trend Direction            : {result.trend_direction}")
    print(f"Trend Quality              : {result.trend_quality}")
    print(f"Swing Structure            : {result.swing_structure}")
    print(f"Structural State           : {result.structural_state}")
    print(f"Break of Structure         : {result.bos_state}")
    print(f"Change of Character        : {result.choch_state}")
    print(f"Market Phase               : {result.market_phase}")
    print(f"Market Regime              : {result.market_regime}")
    print("-" * 110)

    print("PROBABILITIES")
    print("-" * 110)
    print(
        f"Bullish Probability        : "
        f"{result.bullish_probability:.1f}%"
    )
    print(
        f"Bearish Probability        : "
        f"{result.bearish_probability:.1f}%"
    )
    print(
        f"Neutral Probability        : "
        f"{result.neutral_probability:.1f}%"
    )
    print("-" * 110)

    print("QUALITY AND RISK")
    print("-" * 110)
    print(
        f"Structural Quality         : "
        f"{result.structural_quality}"
    )
    print(
        f"Structure Risk             : "
        f"{result.structure_risk}"
    )
    print(f"Confidence                 : {result.confidence}%")
    print(f"Decision Quality           : {result.decision_quality}")
    print("-" * 110)

    print("EXPECTED BEHAVIOUR")
    print("-" * 110)
    print(result.expected_behaviour)

    print("-" * 110)
    print("ANALYTICAL POSTURE")
    print("-" * 110)
    print(result.analytical_posture)

    print("-" * 110)
    print("CONCISE SUMMARY")
    print("-" * 110)
    print(result.concise_summary)

    print("-" * 110)
    print("WARNINGS")
    print("-" * 110)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(f"{number}. {warning}")

    print("-" * 110)
    print("EXPLANATION")
    print("-" * 110)
    print(result.explanation)

    print("-" * 110)
    print("MASTER CONCLUSION")
    print("-" * 110)
    print(result.master_conclusion)

    print("-" * 110)
    print(
        "Method                     : "
        "RULE-BASED MARKET STRUCTURE MASTER"
    )
    print(f"Status                     : {result.status}")
    print("=" * 110)


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
            "Run the AQSD Market Structure Master."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Analysis date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=(
            "Market symbol. "
            f"Default: {DEFAULT_SYMBOL}"
        ),
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=(
            "Historical lookback days. "
            f"Default: {DEFAULT_LOOKBACK_DAYS}."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = run_market_structure_master(
            requested_date=parse_date(
                arguments.date
            ),
            symbol=arguments.symbol,
            lookback_days=arguments.lookback_days,
        )

    except Exception as exc:
        print()
        print("=" * 110)
        print("AQSD MARKET STRUCTURE MASTER")
        print("=" * 110)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 110)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()