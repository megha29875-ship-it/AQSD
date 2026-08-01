"""
AQSD
Market Intelligence Daily Pipeline

Module : MIP-001
Version: 1.1.0
Author : AQSD

Description
-----------
Runs the major AQSD market-intelligence families in dependency order:

    Stage 1 — Participant Daily Pipeline
    Stage 2 — Market Breadth Decision Engine
    Stage 3 — Sector Intelligence Daily Pipeline
    Stage 4 — Market Regime Engine

The pipeline safely handles:

- Successful stages
- Limited historical data
- Partial inputs
- Optional unavailable engines
- Stage-level failures
- Compatible changes in function parameters

Future integration
------------------
This pipeline will later be called by the central AQSD Daily
Orchestrator. Individual intelligence engines will not require
manual execution.

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

from Scripts.aqsd_core.trading_calendar import latest_trading_day


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MIP-001"
MODULE_VERSION: Final[str] = "1.1.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[1]

DEFAULT_BREADTH_INPUT_FILE: Final[Path] = (
    BASE_DIR
    / "Data"
    / "Market_Breadth"
    / "market_breadth_snapshot.xlsx"
)

DEFAULT_WEEKLY_LOOKBACK_SESSIONS: Final[int] = 5

SUCCESS_STATUSES: Final[set[str]] = {
    "SUCCESS",
    "SUCCESS WITH LIMITED HISTORY",
    "SUCCESS WITH PARTIAL INPUTS",
    "PARTIAL SUCCESS",
    "INSUFFICIENT HISTORY",
}


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class PipelineStageResult:
    """
    Normalized result for one pipeline stage.
    """

    stage_number: int
    stage_name: str
    module_name: str

    attempted: bool
    completed: bool
    blocking_failure: bool

    status: str
    confidence: int

    bias: str
    direction: str
    environment: str
    risk: str
    quality: str

    concise_summary: str
    explanation: str
    message: str


@dataclass(frozen=True)
class MarketIntelligencePipelineResult:
    """
    Final output of the Market Intelligence Daily Pipeline.
    """

    requested_date: date | None
    selected_trade_date: date
    breadth_source_file: Path
    weekly_lookback_sessions: int

    participant_stage: PipelineStageResult
    breadth_stage: PipelineStageResult
    sector_stage: PipelineStageResult
    regime_stage: PipelineStageResult

    # Full Stage-4 result retained for downstream AQSD engines.
    # This prevents Market Regime from being executed a second time.
    regime_result: object | None

    completed_stages: int
    total_stages: int
    failed_stages: int
    limited_stages: int

    final_market_regime: str
    final_market_direction: str
    final_risk_environment: str
    final_confidence: int
    final_quality: str

    expected_behaviour: str
    analytical_posture: str
    master_conclusion: str
    concise_summary: str

    warnings: tuple[str, ...]
    overall_status: str
    message: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

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


def first_attribute(
    result: object,
    names: tuple[str, ...],
    default: object = None,
) -> object:
    """
    Return the first available attribute from a result object.
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


def is_limited_status(
    status: str,
) -> bool:
    """
    Return True for limited or partial completion.
    """

    normalized = normalize_text(
        status
    )

    return any(
        keyword in normalized
        for keyword in (
            "LIMITED",
            "PARTIAL",
            "INSUFFICIENT HISTORY",
        )
    )


def is_success_status(
    status: str,
) -> bool:
    """
    Return True for acceptable stage completion.
    """

    normalized = normalize_text(
        status
    )

    if normalized in SUCCESS_STATUSES:
        return True

    return normalized.startswith(
        "SUCCESS"
    )


# ==========================================================
# STAGE RESULT BUILDERS
# ==========================================================

def build_not_run_stage(
    *,
    stage_number: int,
    stage_name: str,
    module_name: str,
    message: str,
) -> PipelineStageResult:
    """
    Build a stage result when execution was skipped.
    """

    return PipelineStageResult(
        stage_number=stage_number,
        stage_name=stage_name,
        module_name=module_name,

        attempted=False,
        completed=False,
        blocking_failure=False,

        status="NOT RUN",
        confidence=0,

        bias="NOT AVAILABLE",
        direction="NOT AVAILABLE",
        environment="NOT AVAILABLE",
        risk="NOT AVAILABLE",
        quality="NOT AVAILABLE",

        concise_summary="NOT AVAILABLE",
        explanation="NOT AVAILABLE",
        message=message,
    )


def build_failed_stage(
    *,
    stage_number: int,
    stage_name: str,
    module_name: str,
    error: Exception,
    blocking_failure: bool,
) -> PipelineStageResult:
    """
    Build a failed stage result.
    """

    return PipelineStageResult(
        stage_number=stage_number,
        stage_name=stage_name,
        module_name=module_name,

        attempted=True,
        completed=False,
        blocking_failure=blocking_failure,

        status="FAILED",
        confidence=0,

        bias="UNKNOWN",
        direction="UNKNOWN",
        environment="NOT AVAILABLE",
        risk="NOT AVAILABLE",
        quality="NOT AVAILABLE",

        concise_summary="NOT AVAILABLE",
        explanation=str(error),
        message=f"{stage_name} failed: {error}",
    )


def normalize_stage_result(
    *,
    stage_number: int,
    stage_name: str,
    module_name: str,
    result: object,
    bias_fields: tuple[str, ...],
    direction_fields: tuple[str, ...],
    environment_fields: tuple[str, ...],
    risk_fields: tuple[str, ...],
    confidence_fields: tuple[str, ...],
    quality_fields: tuple[str, ...],
) -> PipelineStageResult:
    """
    Normalize an AQSD engine or pipeline result.
    """

    status = normalize_text(
        first_attribute(
            result,
            (
                "overall_status",
                "status",
                "decision_status",
            ),
            "UNKNOWN",
        )
    )

    confidence = safe_int(
        first_attribute(
            result,
            confidence_fields,
            0,
        )
    )

    completed = (
        is_success_status(status)
        or is_limited_status(status)
    )

    return PipelineStageResult(
        stage_number=stage_number,
        stage_name=stage_name,
        module_name=module_name,

        attempted=True,
        completed=completed,
        blocking_failure=not completed,

        status=status,
        confidence=confidence,

        bias=normalize_text(
            first_attribute(
                result,
                bias_fields,
                "UNKNOWN",
            )
        ),
        direction=normalize_text(
            first_attribute(
                result,
                direction_fields,
                "UNKNOWN",
            )
        ),
        environment=normalize_text(
            first_attribute(
                result,
                environment_fields,
                "NOT AVAILABLE",
            )
        ),
        risk=normalize_text(
            first_attribute(
                result,
                risk_fields,
                "NOT AVAILABLE",
            )
        ),
        quality=normalize_text(
            first_attribute(
                result,
                quality_fields,
                "NOT AVAILABLE",
            )
        ),

        concise_summary=str(
            first_attribute(
                result,
                (
                    "concise_summary",
                    "master_conclusion",
                    "message",
                ),
                "NOT AVAILABLE",
            )
        ),
        explanation=str(
            first_attribute(
                result,
                (
                    "explanation",
                    "master_conclusion",
                    "message",
                ),
                "NOT AVAILABLE",
            )
        ),
        message=str(
            first_attribute(
                result,
                (
                    "message",
                    "master_conclusion",
                    "concise_summary",
                ),
                f"{stage_name} completed.",
            )
        ),
    )


# ==========================================================
# STAGE 1 — PARTICIPANT DAILY PIPELINE
# ==========================================================

def run_participant_stage(
    *,
    trade_date: date,
) -> PipelineStageResult:
    """
    Run the Participant Daily Pipeline.
    """

    stage_number = 1
    stage_name = "PARTICIPANT DAILY PIPELINE"
    module_name = "Scripts.aqsd_participant_daily_pipeline"

    print()
    print(
        "STAGE 1 — PARTICIPANT DAILY PIPELINE"
    )
    print("-" * 104)

    try:
        module = importlib.import_module(
            module_name
        )

        runner = getattr(
            module,
            "run_participant_pipeline",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": trade_date,
            },
        )
        stage_result = normalize_stage_result(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            result=result,

            bias_fields=(
                "institutional_change_bias",
                "institutional_bias",
                "current_positioning",
            ),
            direction_fields=(
                "change_status",
                "participant_direction",
                "momentum",
            ),
            environment_fields=(
                "participant_environment",
                "institutional_environment",
                "market_environment",
            ),
            risk_fields=(
                "risk_level",
                "participant_risk",
            ),
            confidence_fields=(
                "decision_confidence",
                "intelligence_confidence",
                "overall_confidence",
                "confidence",
            ),
            quality_fields=(
                "decision_quality",
                "change_conviction",
                "conviction",
            ),
        )

        display_stage_result(
            stage_result
        )

        return stage_result

    except Exception as exc:
        stage_result = build_failed_stage(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            error=exc,
            blocking_failure=False,
        )

        display_stage_result(
            stage_result
        )

        return stage_result


# ==========================================================
# STAGE 2 — MARKET BREADTH DECISION
# ==========================================================

def run_breadth_stage(
    *,
    trade_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> PipelineStageResult:
    """
    Run the Market Breadth Decision Engine.
    """

    stage_number = 2
    stage_name = "MARKET BREADTH DECISION ENGINE"
    module_name = (
        "Scripts.aqsd_intelligence."
        "market_breadth_decision_engine"
    )

    print()
    print(
        "STAGE 2 — MARKET BREADTH DECISION ENGINE"
    )
    print("-" * 104)

    try:
        module = importlib.import_module(
            module_name
        )

        runner = getattr(
            module,
            "run_market_breadth_decision_engine",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": trade_date,
                "source_file": source_file,
                "weekly_lookback_sessions": (
                    weekly_lookback_sessions
                ),
                "export_breadth": True,
                "export": True,
            },
        )

        stage_result = normalize_stage_result(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            result=result,

            bias_fields=(
                "breadth_bias",
                "consolidated_breadth_bias",
                "market_bias",
                "bias",
            ),
            direction_fields=(
                "breadth_direction",
                "change_direction",
                "direction",
            ),
            environment_fields=(
                "market_environment",
                "breadth_regime",
                "breadth_environment",
            ),
            risk_fields=(
                "reversal_risk_level",
                "breadth_risk_level",
                "risk_level",
            ),
            confidence_fields=(
                "decision_confidence",
                "confidence",
                "current_confidence",
            ),
            quality_fields=(
                "decision_quality",
                "breadth_quality",
                "participation_quality",
            ),
        )

        display_stage_result(
            stage_result
        )

        return stage_result

    except Exception as exc:
        stage_result = build_failed_stage(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            error=exc,
            blocking_failure=True,
        )

        display_stage_result(
            stage_result
        )

        return stage_result


# ==========================================================
# STAGE 3 — SECTOR INTELLIGENCE PIPELINE
# ==========================================================

def run_sector_stage(
    *,
    trade_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> PipelineStageResult:
    """
    Run the Sector Intelligence Daily Pipeline.
    """

    stage_number = 3
    stage_name = "SECTOR INTELLIGENCE DAILY PIPELINE"
    module_name = "Scripts.aqsd_sector_daily_pipeline"

    print()
    print(
        "STAGE 3 — SECTOR INTELLIGENCE DAILY PIPELINE"
    )
    print("-" * 104)

    try:
        module = importlib.import_module(
            module_name
        )

        runner = getattr(
            module,
            "run_sector_daily_pipeline",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": trade_date,
                "source_file": source_file,
                "weekly_lookback_sessions": (
                    weekly_lookback_sessions
                ),
            },
        )

        stage_result = normalize_stage_result(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            result=result,

            bias_fields=(
                "sector_market_bias",
                "market_bias",
            ),
            direction_fields=(
                "rotation_direction",
                "direction",
            ),
            environment_fields=(
                "market_environment",
                "sector_environment",
            ),
            risk_fields=(
                "sector_risk_level",
                "rotation_risk_level",
            ),
            confidence_fields=(
                "decision_confidence",
                "rotation_confidence",
                "strength_confidence",
            ),
            quality_fields=(
                "decision_quality",
                "rotation_quality",
                "participation_quality",
            ),
        )

        display_stage_result(
            stage_result
        )

        return stage_result

    except Exception as exc:
        stage_result = build_failed_stage(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            error=exc,
            blocking_failure=True,
        )

        display_stage_result(
            stage_result
        )

        return stage_result


# ==========================================================
# STAGE 4 — MARKET REGIME ENGINE
# ==========================================================

def run_regime_stage(
    *,
    trade_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> tuple[PipelineStageResult, object | None]:
    """
    Run the Market Regime Engine.

    Returns both:
    1. The normalized PipelineStageResult used by this pipeline.
    2. The complete MarketRegimeResult for downstream consumers.

    Retaining the full result ensures the Market Regime Engine is
    executed only once per Market Intelligence Pipeline run.
    """

    stage_number = 4
    stage_name = "MARKET REGIME ENGINE"
    module_name = (
        "Scripts.aqsd_intelligence."
        "market_regime_engine"
    )

    print()
    print(
        "STAGE 4 — MARKET REGIME ENGINE"
    )
    print("-" * 104)

    try:
        module = importlib.import_module(
            module_name
        )

        runner = getattr(
            module,
            "run_market_regime_engine",
        )

        result = call_with_supported_arguments(
            runner,
            {
                "requested_date": trade_date,
                "breadth_source_file": source_file,
                "weekly_lookback_sessions": (
                    weekly_lookback_sessions
                ),
            },
        )

        stage_result = normalize_stage_result(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            result=result,

            bias_fields=(
                "market_direction",
                "primary_regime",
            ),
            direction_fields=(
                "market_direction",
                "secondary_regime",
            ),
            environment_fields=(
                "market_environment",
                "primary_regime",
            ),
            risk_fields=(
                "risk_environment",
            ),
            confidence_fields=(
                "confidence",
            ),
            quality_fields=(
                "decision_quality",
                "regime_strength",
            ),
        )

        display_stage_result(
            stage_result
        )

        return (
            stage_result,
            result,
        )

    except Exception as exc:
        stage_result = build_failed_stage(
            stage_number=stage_number,
            stage_name=stage_name,
            module_name=module_name,
            error=exc,
            blocking_failure=True,
        )

        display_stage_result(
            stage_result
        )

        return (
            stage_result,
            None,
        )


# ==========================================================
# DISPLAY STAGE
# ==========================================================

def display_stage_result(
    result: PipelineStageResult,
) -> None:
    """
    Display one normalized pipeline stage.
    """

    print(
        f"Status                     : "
        f"{result.status}"
    )
    print(
        f"Completed                  : "
        f"{result.completed}"
    )
    print(
        f"Bias                       : "
        f"{result.bias}"
    )
    print(
        f"Direction                  : "
        f"{result.direction}"
    )
    print(
        f"Environment                : "
        f"{result.environment}"
    )
    print(
        f"Risk                       : "
        f"{result.risk}"
    )
    print(
        f"Quality                    : "
        f"{result.quality}"
    )
    print(
        f"Confidence                 : "
        f"{result.confidence}%"
    )

    if result.status == "FAILED":
        print(
            f"Reason                     : "
            f"{result.message}"
        )


# ==========================================================
# PIPELINE STATUS
# ==========================================================

def determine_overall_status(
    *,
    stages: tuple[PipelineStageResult, ...],
) -> tuple[str, str]:
    """
    Determine final Market Intelligence Pipeline status.
    """

    blocking_failures = [
        stage
        for stage in stages
        if (
            stage.status == "FAILED"
            and stage.blocking_failure
        )
    ]

    completed_stages = sum(
        stage.completed
        for stage in stages
    )

    limited_stages = sum(
        is_limited_status(
            stage.status
        )
        for stage in stages
    )

    if blocking_failures:
        failed_names = ", ".join(
            stage.stage_name
            for stage in blocking_failures
        )

        return (
            "FAILED",
            (
                "The Market Intelligence Pipeline stopped with "
                f"blocking failures in: {failed_names}."
            ),
        )

    if completed_stages == 0:
        return (
            "FAILED",
            (
                "No Market Intelligence stage completed "
                "successfully."
            ),
        )

    if (
        completed_stages < len(stages)
        or limited_stages > 0
    ):
        return (
            "SUCCESS WITH PARTIAL INPUTS",
            (
                "The Market Intelligence Pipeline completed with "
                "limited history or unavailable optional inputs."
            ),
        )

    return (
        "SUCCESS",
        (
            "All Market Intelligence stages completed "
            "successfully."
        ),
    )


def build_pipeline_warnings(
    stages: tuple[PipelineStageResult, ...],
) -> tuple[str, ...]:
    """
    Build final pipeline warnings.
    """

    warnings: list[str] = []

    for stage in stages:
        if stage.status == "FAILED":
            warnings.append(
                f"{stage.stage_name} failed: {stage.message}"
            )

        elif is_limited_status(
            stage.status
        ):
            warnings.append(
                f"{stage.stage_name} has limited or partial inputs."
            )

        elif not stage.completed:
            warnings.append(
                f"{stage.stage_name} did not complete."
            )

    if not warnings:
        warnings.append(
            "No major Market Intelligence Pipeline warning is active."
        )

    return tuple(
        dict.fromkeys(
            warnings
        )
    )


# ==========================================================
# MAIN PIPELINE
# ==========================================================

def run_market_intelligence_pipeline(
    *,
    requested_date: date | None = None,
    breadth_source_file: Path = (
        DEFAULT_BREADTH_INPUT_FILE
    ),
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
) -> MarketIntelligencePipelineResult:
    """
    Run the complete AQSD Market Intelligence Daily Pipeline.
    """

    selected_trade_date = select_trade_date(
        requested_date
    )

    source_file = (
        breadth_source_file
        .expanduser()
        .resolve()
    )

    print()
    print("=" * 104)
    print(
        "AQSD MARKET INTELLIGENCE DAILY PIPELINE"
    )
    print("=" * 104)
    print(
        f"Module                     : "
        f"{MODULE_ID}"
    )
    print(
        f"Version                    : "
        f"{MODULE_VERSION}"
    )
    print(
        f"Requested Date             : "
        f"{requested_date}"
    )
    print(
        f"Selected Trading Date      : "
        f"{selected_trade_date}"
    )
    print(
        f"Breadth Source File        : "
        f"{source_file}"
    )
    print(
        f"Weekly Sessions            : "
        f"{weekly_lookback_sessions}"
    )
    print("=" * 104)

    if weekly_lookback_sessions < 1:
        raise ValueError(
            "weekly_lookback_sessions must be at least 1."
        )

    if not source_file.exists():
        raise FileNotFoundError(
            f"Market breadth input file not found: {source_file}"
        )

    # Participant failure is non-blocking because the Market Regime
    # Engine already handles unavailable participant intelligence.

    participant_stage = run_participant_stage(
        trade_date=selected_trade_date,
    )

    breadth_stage = run_breadth_stage(
        trade_date=selected_trade_date,
        source_file=source_file,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    regime_result: object | None = None

    if breadth_stage.status == "FAILED":
        sector_stage = build_not_run_stage(
            stage_number=3,
            stage_name=(
                "SECTOR INTELLIGENCE DAILY PIPELINE"
            ),
            module_name=(
                "Scripts.aqsd_sector_daily_pipeline"
            ),
            message=(
                "Sector stage was not run because the "
                "Market Breadth stage failed."
            ),
        )

        regime_stage = build_not_run_stage(
            stage_number=4,
            stage_name="MARKET REGIME ENGINE",
            module_name=(
                "Scripts.aqsd_intelligence."
                "market_regime_engine"
            ),
            message=(
                "Market Regime stage was not run because "
                "the Market Breadth stage failed."
            ),
        )

    else:
        sector_stage = run_sector_stage(
            trade_date=selected_trade_date,
            source_file=source_file,
            weekly_lookback_sessions=(
                weekly_lookback_sessions
            ),
        )

        if sector_stage.status == "FAILED":
            regime_stage = build_not_run_stage(
                stage_number=4,
                stage_name="MARKET REGIME ENGINE",
                module_name=(
                    "Scripts.aqsd_intelligence."
                    "market_regime_engine"
                ),
                message=(
                    "Market Regime stage was not run because "
                    "the Sector Intelligence stage failed."
                ),
            )

        else:
            (
                regime_stage,
                regime_result,
            ) = run_regime_stage(
                trade_date=selected_trade_date,
                source_file=source_file,
                weekly_lookback_sessions=(
                    weekly_lookback_sessions
                ),
            )

    stages = (
        participant_stage,
        breadth_stage,
        sector_stage,
        regime_stage,
    )

    completed_stages = sum(
        stage.completed
        for stage in stages
    )

    failed_stages = sum(
        stage.status == "FAILED"
        for stage in stages
    )

    limited_stages = sum(
        is_limited_status(
            stage.status
        )
        for stage in stages
    )

    overall_status, message = determine_overall_status(
        stages=stages
    )

    warnings = build_pipeline_warnings(
        stages
    )

    if regime_stage.completed:
        final_market_regime = (
            regime_stage.environment
        )
        final_market_direction = (
            regime_stage.direction
        )
        final_risk_environment = (
            regime_stage.risk
        )
        final_confidence = (
            regime_stage.confidence
        )
        final_quality = (
            regime_stage.quality
        )

        expected_behaviour = (
            regime_stage.explanation
        )
        analytical_posture = (
            regime_stage.message
        )
        master_conclusion = (
            regime_stage.concise_summary
        )
        concise_summary = (
            regime_stage.concise_summary
        )

    else:
        final_market_regime = "NOT AVAILABLE"
        final_market_direction = "UNKNOWN"
        final_risk_environment = "NOT AVAILABLE"
        final_confidence = 0
        final_quality = "NOT AVAILABLE"

        expected_behaviour = "NOT AVAILABLE"
        analytical_posture = (
            "MARKET REGIME STAGE DID NOT COMPLETE."
        )
        master_conclusion = "NOT AVAILABLE"
        concise_summary = "NOT AVAILABLE"

    return MarketIntelligencePipelineResult(
        requested_date=requested_date,
        selected_trade_date=selected_trade_date,
        breadth_source_file=source_file,
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),

        participant_stage=participant_stage,
        breadth_stage=breadth_stage,
        sector_stage=sector_stage,
        regime_stage=regime_stage,
        regime_result=regime_result,

        completed_stages=completed_stages,
        total_stages=len(stages),
        failed_stages=failed_stages,
        limited_stages=limited_stages,

        final_market_regime=(
            final_market_regime
        ),
        final_market_direction=(
            final_market_direction
        ),
        final_risk_environment=(
            final_risk_environment
        ),
        final_confidence=final_confidence,
        final_quality=final_quality,

        expected_behaviour=(
            expected_behaviour
        ),
        analytical_posture=(
            analytical_posture
        ),
        master_conclusion=(
            master_conclusion
        ),
        concise_summary=concise_summary,

        warnings=warnings,
        overall_status=overall_status,
        message=message,
    )


# ==========================================================
# FINAL DISPLAY
# ==========================================================

def display_result(
    result: MarketIntelligencePipelineResult,
) -> None:
    """
    Display the complete Market Intelligence Pipeline result.
    """

    print()
    print("=" * 104)
    print(
        "AQSD MARKET INTELLIGENCE PIPELINE — FINAL SUMMARY"
    )
    print("=" * 104)
    print(
        f"Selected Trading Date      : "
        f"{result.selected_trade_date}"
    )
    print(
        f"Completed Stages           : "
        f"{result.completed_stages}/"
        f"{result.total_stages}"
    )
    print(
        f"Failed Stages              : "
        f"{result.failed_stages}"
    )
    print(
        f"Limited Stages             : "
        f"{result.limited_stages}"
    )
    print("-" * 104)

    for stage in (
        result.participant_stage,
        result.breadth_stage,
        result.sector_stage,
        result.regime_stage,
    ):
        print(
            f"Stage {stage.stage_number} — "
            f"{stage.stage_name}"
        )
        print("-" * 104)
        print(
            f"Status                     : "
            f"{stage.status}"
        )
        print(
            f"Bias                       : "
            f"{stage.bias}"
        )
        print(
            f"Direction                  : "
            f"{stage.direction}"
        )
        print(
            f"Environment                : "
            f"{stage.environment}"
        )
        print(
            f"Risk                       : "
            f"{stage.risk}"
        )
        print(
            f"Confidence                 : "
            f"{stage.confidence}%"
        )
        print("-" * 104)

    print("FINAL MARKET INTELLIGENCE")
    print("-" * 104)
    print(
        f"Market Regime              : "
        f"{result.final_market_regime}"
    )
    print(
        f"Market Direction           : "
        f"{result.final_market_direction}"
    )
    print(
        f"Risk Environment           : "
        f"{result.final_risk_environment}"
    )
    print(
        f"Confidence                 : "
        f"{result.final_confidence}%"
    )
    print(
        f"Quality                    : "
        f"{result.final_quality}"
    )

    print("-" * 104)
    print("CONCISE SUMMARY")
    print("-" * 104)
    print(
        result.concise_summary
    )

    print("-" * 104)
    print("WARNINGS")
    print("-" * 104)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(
            f"{number}. {warning}"
        )

    print("-" * 104)
    print(
        f"Overall Status             : "
        f"{result.overall_status}"
    )
    print(
        f"Message                    : "
        f"{result.message}"
    )
    print("=" * 104)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the AQSD Market Intelligence Daily Pipeline."
        )
    )

    parser.add_argument(
        "--date",
        required=False,
        help=(
            "Optional requested date in YYYY-MM-DD format. "
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
        result = run_market_intelligence_pipeline(
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
        print("=" * 104)
        print(
            "AQSD MARKET INTELLIGENCE DAILY PIPELINE"
        )
        print("=" * 104)
        print(
            "Status : FAILED"
        )
        print(
            f"Reason : {exc}"
        )
        print("=" * 104)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()