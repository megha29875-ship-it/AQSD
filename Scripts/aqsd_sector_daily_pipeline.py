"""
AQSD
Sector Intelligence Daily Pipeline

Module : SIP-001
Version: 1.1.0
Author : AQSD

Description
-----------
Automatically runs the complete AQSD Sector Intelligence system
in the correct dependency order:

    Stage 1 — Sector Strength Engine
    Stage 2 — Sector Rotation Engine
    Stage 3 — Sector Rotation Decision Engine

The pipeline provides one consolidated daily sector-intelligence
workflow. Individual sector engines no longer need to be run manually.

Future integration
------------------
This pipeline will later be connected to the central:

    AQSD Daily Orchestrator

Important
---------
This module provides analytical decision support only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_core.trading_calendar import latest_trading_day
from Scripts.aqsd_intelligence.sector_rotation_decision_engine import (
    SectorRotationDecisionResult,
    run_sector_rotation_decision_engine,
)
from Scripts.aqsd_intelligence.sector_rotation_engine import (
    SectorRotationEngineResult,
    run_sector_rotation_engine,
)
from Scripts.aqsd_intelligence.sector_strength_engine import (
    DEFAULT_INPUT_FILE,
    SectorStrengthEngineResult,
    run_sector_strength_engine,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "SIP-001"
MODULE_VERSION: Final[str] = "1.1.0"

DEFAULT_WEEKLY_LOOKBACK_SESSIONS: Final[int] = 5


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class SectorDailyPipelineResult:
    """
    Complete result of the Sector Intelligence Daily Pipeline.
    """

    requested_date: date | None
    selected_trade_date: date
    source_file: Path

    # Stage 1 — Sector Strength
    strength_status: str
    strength_sectors_analysed: int
    bullish_sectors: int
    bearish_sectors: int
    neutral_sectors: int
    strongest_sector: str | None
    weakest_sector: str | None
    strength_confidence: int
    strength_csv_file: Path | None
    strength_excel_file: Path | None

    # Stage 2 — Sector Rotation
    rotation_status: str
    rotation_direction: str
    rotation_breadth: str
    rotation_speed: str
    leadership_stability: str
    dominant_sector_cycle: str
    improving_sectors: int
    deteriorating_sectors: int
    stable_sectors: int
    rotation_risk_score: int
    rotation_risk_level: str
    rotation_confidence: int
    rotation_csv_file: Path | None
    rotation_excel_file: Path | None

    # Stage 3 — Sector Decision
    decision_status: str
    sector_market_bias: str
    participation_quality: str
    leadership_quality: str
    rotation_quality: str
    sector_risk_level: str
    decision_confidence: int
    decision_quality: str
    expected_behaviour: str
    analytical_posture: str
    market_environment: str
    master_conclusion: str
    concise_summary: str

    # Pipeline
    overall_status: str
    message: str


# ==========================================================
# DATE HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse a YYYY-MM-DD date.
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
    Select the latest valid trading date.

    When no date is supplied, the latest trading day on or before
    the current calendar date is used.
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
# STAGE 1 — SECTOR STRENGTH
# ==========================================================

def run_strength_stage(
    *,
    trade_date: date,
    source_file: Path,
) -> SectorStrengthEngineResult:
    """
    Run the Sector Strength Engine.
    """

    print()
    print("STAGE 1 — SECTOR STRENGTH ENGINE")
    print("-" * 100)

    result = run_sector_strength_engine(
        requested_date=trade_date,
        source_file=source_file,
        export=True,
    )

    print(
        f"Status                     : "
        f"{result.status}"
    )
    print(
        f"Sectors Analysed           : "
        f"{result.sectors_analysed}"
    )
    print(
        f"Bullish Sectors            : "
        f"{result.bullish_sectors}"
    )
    print(
        f"Bearish Sectors            : "
        f"{result.bearish_sectors}"
    )
    print(
        f"Neutral Sectors            : "
        f"{result.neutral_sectors}"
    )
    print(
        f"Strongest Sector           : "
        f"{result.strongest_sector}"
    )
    print(
        f"Weakest Sector             : "
        f"{result.weakest_sector}"
    )
    print(
        f"Confidence                 : "
        f"{result.confidence}%"
    )

    return result


# ==========================================================
# STAGE 2 — SECTOR ROTATION
# ==========================================================

def run_rotation_stage(
    *,
    trade_date: date,
    weekly_lookback_sessions: int,
) -> SectorRotationEngineResult:
    """
    Run the Sector Rotation Engine.
    """

    print()
    print("STAGE 2 — SECTOR ROTATION ENGINE")
    print("-" * 100)

    result = run_sector_rotation_engine(
        requested_date=trade_date,
        weekly_lookback_sessions=weekly_lookback_sessions,
        export=True,
    )

    print(
        f"Status                     : "
        f"{result.status}"
    )
    print(
        f"Rotation Direction         : "
        f"{result.rotation_direction}"
    )
    print(
        f"Rotation Breadth           : "
        f"{result.rotation_breadth}"
    )
    print(
        f"Rotation Speed             : "
        f"{result.rotation_speed}"
    )
    print(
        f"Leadership Stability       : "
        f"{result.leadership_stability}"
    )
    print(
        f"Dominant Sector Cycle      : "
        f"{result.dominant_sector_cycle}"
    )
    print(
        f"Improving Sectors          : "
        f"{result.improving_sectors}"
    )
    print(
        f"Deteriorating Sectors      : "
        f"{result.deteriorating_sectors}"
    )
    print(
        f"Rotation Risk              : "
        f"{result.rotation_risk_level} "
        f"({result.rotation_risk_score}%)"
    )
    print(
        f"Confidence                 : "
        f"{result.confidence}%"
    )

    return result


# ==========================================================
# STAGE 3 — SECTOR DECISION
# ==========================================================

def run_decision_stage(
    *,
    trade_date: date,
    source_file: Path,
    weekly_lookback_sessions: int,
) -> SectorRotationDecisionResult:
    """
    Run the Sector Rotation Decision Engine.

    The underlying strength and rotation exports have already been
    created by Stages 1 and 2. Therefore, additional exports are
    disabled in this stage.
    """

    print()
    print("STAGE 3 — SECTOR ROTATION DECISION ENGINE")
    print("-" * 100)

    result = run_sector_rotation_decision_engine(
        requested_date=trade_date,
        source_file=source_file,
        weekly_lookback_sessions=weekly_lookback_sessions,
        export_strength=False,
        export_rotation=False,
    )

    print(
        f"Status                     : "
        f"{result.status}"
    )
    print(
        f"Sector Market Bias         : "
        f"{result.sector_market_bias}"
    )
    print(
        f"Participation Quality      : "
        f"{result.sector_participation_quality}"
    )
    print(
        f"Leadership Quality         : "
        f"{result.leadership_quality}"
    )
    print(
        f"Rotation Quality           : "
        f"{result.rotation_quality}"
    )
    print(
        f"Sector Risk                : "
        f"{result.sector_risk_level}"
    )
    print(
        f"Decision Confidence        : "
        f"{result.decision_confidence}%"
    )
    print(
        f"Decision Quality           : "
        f"{result.decision_quality}"
    )

    return result


# ==========================================================
# STATUS LOGIC
# ==========================================================

def determine_overall_status(
    *,
    strength_status: str,
    rotation_status: str,
    decision_status: str,
) -> tuple[str, str]:
    """
    Determine the final pipeline status.
    """

    if strength_status != "SUCCESS":
        return (
            "FAILED",
            (
                "Sector Strength Engine did not complete successfully. "
                "Dependent sector stages could not be completed."
            ),
        )

    if rotation_status == "FAILED":
        return (
            "FAILED",
            (
                "Sector Strength Engine succeeded, but the "
                "Sector Rotation Engine failed."
            ),
        )

    if decision_status == "FAILED":
        return (
            "FAILED",
            (
                "Sector Strength and Rotation engines completed, but "
                "the Sector Rotation Decision Engine failed."
            ),
        )

    limited_statuses = {
        "INSUFFICIENT HISTORY",
        "SUCCESS WITH LIMITED HISTORY",
        "PARTIAL SUCCESS",
    }

    if (
        rotation_status in limited_statuses
        or decision_status in limited_statuses
    ):
        return (
            "SUCCESS WITH LIMITED HISTORY",
            (
                "Sector Strength, Sector Rotation and Sector Decision "
                "stages completed. Historical rotation confirmation is "
                "still being accumulated."
            ),
        )

    return (
        "SUCCESS",
        (
            "All Sector Intelligence stages completed successfully."
        ),
    )


# ==========================================================
# FAILED RESULT HELPERS
# ==========================================================

def build_strength_failure_result(
    *,
    requested_date: date | None,
    selected_trade_date: date,
    source_file: Path,
    strength_result: SectorStrengthEngineResult,
) -> SectorDailyPipelineResult:
    """
    Build the final result when Stage 1 prevents continuation.
    """

    return SectorDailyPipelineResult(
        requested_date=requested_date,
        selected_trade_date=selected_trade_date,
        source_file=source_file,

        strength_status=strength_result.status,
        strength_sectors_analysed=(
            strength_result.sectors_analysed
        ),
        bullish_sectors=strength_result.bullish_sectors,
        bearish_sectors=strength_result.bearish_sectors,
        neutral_sectors=strength_result.neutral_sectors,
        strongest_sector=strength_result.strongest_sector,
        weakest_sector=strength_result.weakest_sector,
        strength_confidence=strength_result.confidence,
        strength_csv_file=strength_result.csv_file,
        strength_excel_file=strength_result.excel_file,

        rotation_status="NOT RUN",
        rotation_direction="NOT AVAILABLE",
        rotation_breadth="NOT AVAILABLE",
        rotation_speed="NOT AVAILABLE",
        leadership_stability="NOT AVAILABLE",
        dominant_sector_cycle="NOT AVAILABLE",
        improving_sectors=0,
        deteriorating_sectors=0,
        stable_sectors=0,
        rotation_risk_score=0,
        rotation_risk_level="NOT AVAILABLE",
        rotation_confidence=0,
        rotation_csv_file=None,
        rotation_excel_file=None,

        decision_status="NOT RUN",
        sector_market_bias="UNKNOWN",
        participation_quality="NOT AVAILABLE",
        leadership_quality="NOT AVAILABLE",
        rotation_quality="NOT AVAILABLE",
        sector_risk_level="NOT AVAILABLE",
        decision_confidence=0,
        decision_quality="NOT AVAILABLE",
        expected_behaviour="NOT AVAILABLE",
        analytical_posture="NOT AVAILABLE",
        market_environment="NOT AVAILABLE",
        master_conclusion="NOT AVAILABLE",
        concise_summary="NOT AVAILABLE",

        overall_status="FAILED",
        message=(
            "Sector Strength Engine failed. "
            "Sector Rotation and Decision stages were not run."
        ),
    )


def build_rotation_failure_result(
    *,
    requested_date: date | None,
    selected_trade_date: date,
    source_file: Path,
    strength_result: SectorStrengthEngineResult,
    rotation_result: SectorRotationEngineResult,
) -> SectorDailyPipelineResult:
    """
    Build the final result when Stage 2 prevents continuation.
    """

    return SectorDailyPipelineResult(
        requested_date=requested_date,
        selected_trade_date=selected_trade_date,
        source_file=source_file,

        strength_status=strength_result.status,
        strength_sectors_analysed=(
            strength_result.sectors_analysed
        ),
        bullish_sectors=strength_result.bullish_sectors,
        bearish_sectors=strength_result.bearish_sectors,
        neutral_sectors=strength_result.neutral_sectors,
        strongest_sector=strength_result.strongest_sector,
        weakest_sector=strength_result.weakest_sector,
        strength_confidence=strength_result.confidence,
        strength_csv_file=strength_result.csv_file,
        strength_excel_file=strength_result.excel_file,

        rotation_status=rotation_result.status,
        rotation_direction=rotation_result.rotation_direction,
        rotation_breadth=rotation_result.rotation_breadth,
        rotation_speed=rotation_result.rotation_speed,
        leadership_stability=(
            rotation_result.leadership_stability
        ),
        dominant_sector_cycle=(
            rotation_result.dominant_sector_cycle
        ),
        improving_sectors=rotation_result.improving_sectors,
        deteriorating_sectors=(
            rotation_result.deteriorating_sectors
        ),
        stable_sectors=rotation_result.stable_sector_count,
        rotation_risk_score=(
            rotation_result.rotation_risk_score
        ),
        rotation_risk_level=(
            rotation_result.rotation_risk_level
        ),
        rotation_confidence=rotation_result.confidence,
        rotation_csv_file=rotation_result.csv_file,
        rotation_excel_file=rotation_result.excel_file,

        decision_status="NOT RUN",
        sector_market_bias="UNKNOWN",
        participation_quality="NOT AVAILABLE",
        leadership_quality="NOT AVAILABLE",
        rotation_quality="NOT AVAILABLE",
        sector_risk_level="NOT AVAILABLE",
        decision_confidence=0,
        decision_quality="NOT AVAILABLE",
        expected_behaviour="NOT AVAILABLE",
        analytical_posture="NOT AVAILABLE",
        market_environment="NOT AVAILABLE",
        master_conclusion="NOT AVAILABLE",
        concise_summary="NOT AVAILABLE",

        overall_status="FAILED",
        message=(
            "Sector Rotation Engine failed. "
            "Sector Rotation Decision Engine was not run."
        ),
    )


# ==========================================================
# MAIN PIPELINE
# ==========================================================

def run_sector_daily_pipeline(
    *,
    requested_date: date | None = None,
    source_file: Path = DEFAULT_INPUT_FILE,
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
) -> SectorDailyPipelineResult:
    """
    Run the complete AQSD Sector Intelligence Daily Pipeline.
    """

    selected_trade_date = select_trade_date(
        requested_date
    )

    print()
    print("=" * 100)
    print("AQSD SECTOR INTELLIGENCE DAILY PIPELINE")
    print("=" * 100)
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
        f"Source File                : "
        f"{source_file}"
    )
    print("=" * 100)

    if weekly_lookback_sessions < 1:
        raise ValueError(
            "weekly_lookback_sessions must be at least 1."
        )

    if not source_file.exists():
        raise FileNotFoundError(
            f"Sector breadth input file not found: {source_file}"
        )

    # ======================================================
    # STAGE 1 — SECTOR STRENGTH
    # ======================================================

    strength_result = run_strength_stage(
        trade_date=selected_trade_date,
        source_file=source_file,
    )

    if strength_result.status != "SUCCESS":
        print()
        print("PIPELINE STOPPED AFTER STAGE 1")
        print(
            "Reason: Sector Strength Engine did not "
            "complete successfully."
        )

        return build_strength_failure_result(
            requested_date=requested_date,
            selected_trade_date=selected_trade_date,
            source_file=source_file,
            strength_result=strength_result,
        )

    # ======================================================
    # STAGE 2 — SECTOR ROTATION
    # ======================================================

    rotation_result = run_rotation_stage(
        trade_date=selected_trade_date,
        weekly_lookback_sessions=weekly_lookback_sessions,
    )

    if rotation_result.status == "FAILED":
        print()
        print("PIPELINE STOPPED AFTER STAGE 2")
        print(
            "Reason: Sector Rotation Engine did not "
            "complete successfully."
        )

        return build_rotation_failure_result(
            requested_date=requested_date,
            selected_trade_date=selected_trade_date,
            source_file=source_file,
            strength_result=strength_result,
            rotation_result=rotation_result,
        )

    # ======================================================
    # STAGE 3 — SECTOR ROTATION DECISION
    # ======================================================

    decision_result = run_decision_stage(
        trade_date=selected_trade_date,
        source_file=source_file,
        weekly_lookback_sessions=weekly_lookback_sessions,
    )

    overall_status, message = determine_overall_status(
        strength_status=strength_result.status,
        rotation_status=rotation_result.status,
        decision_status=decision_result.status,
    )

    return SectorDailyPipelineResult(
        requested_date=requested_date,
        selected_trade_date=selected_trade_date,
        source_file=source_file,

        strength_status=strength_result.status,
        strength_sectors_analysed=(
            strength_result.sectors_analysed
        ),
        bullish_sectors=strength_result.bullish_sectors,
        bearish_sectors=strength_result.bearish_sectors,
        neutral_sectors=strength_result.neutral_sectors,
        strongest_sector=strength_result.strongest_sector,
        weakest_sector=strength_result.weakest_sector,
        strength_confidence=strength_result.confidence,
        strength_csv_file=strength_result.csv_file,
        strength_excel_file=strength_result.excel_file,

        rotation_status=rotation_result.status,
        rotation_direction=rotation_result.rotation_direction,
        rotation_breadth=rotation_result.rotation_breadth,
        rotation_speed=rotation_result.rotation_speed,
        leadership_stability=(
            rotation_result.leadership_stability
        ),
        dominant_sector_cycle=(
            rotation_result.dominant_sector_cycle
        ),
        improving_sectors=rotation_result.improving_sectors,
        deteriorating_sectors=(
            rotation_result.deteriorating_sectors
        ),
        stable_sectors=rotation_result.stable_sector_count,
        rotation_risk_score=(
            rotation_result.rotation_risk_score
        ),
        rotation_risk_level=(
            rotation_result.rotation_risk_level
        ),
        rotation_confidence=rotation_result.confidence,
        rotation_csv_file=rotation_result.csv_file,
        rotation_excel_file=rotation_result.excel_file,

        decision_status=decision_result.status,
        sector_market_bias=(
            decision_result.sector_market_bias
        ),
        participation_quality=(
            decision_result.sector_participation_quality
        ),
        leadership_quality=(
            decision_result.leadership_quality
        ),
        rotation_quality=decision_result.rotation_quality,
        sector_risk_level=decision_result.sector_risk_level,
        decision_confidence=(
            decision_result.decision_confidence
        ),
        decision_quality=decision_result.decision_quality,
        expected_behaviour=decision_result.expected_behaviour,
        analytical_posture=decision_result.analytical_posture,
        market_environment=decision_result.market_environment,
        master_conclusion=decision_result.master_conclusion,
        concise_summary=decision_result.concise_summary,

        overall_status=overall_status,
        message=message,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: SectorDailyPipelineResult,
) -> None:
    """
    Display the final pipeline result.
    """

    print()
    print("=" * 100)
    print("AQSD SECTOR INTELLIGENCE PIPELINE — FINAL SUMMARY")
    print("=" * 100)
    print(
        f"Selected Trading Date      : "
        f"{result.selected_trade_date}"
    )
    print("-" * 100)

    print("STAGE 1 — SECTOR STRENGTH")
    print("-" * 100)
    print(
        f"Strength Status            : "
        f"{result.strength_status}"
    )
    print(
        f"Sectors Analysed           : "
        f"{result.strength_sectors_analysed}"
    )
    print(
        f"Bullish Sectors            : "
        f"{result.bullish_sectors}"
    )
    print(
        f"Bearish Sectors            : "
        f"{result.bearish_sectors}"
    )
    print(
        f"Neutral Sectors            : "
        f"{result.neutral_sectors}"
    )
    print(
        f"Strongest Sector           : "
        f"{result.strongest_sector}"
    )
    print(
        f"Weakest Sector             : "
        f"{result.weakest_sector}"
    )
    print(
        f"Strength Confidence        : "
        f"{result.strength_confidence}%"
    )
    print("-" * 100)

    print("STAGE 2 — SECTOR ROTATION")
    print("-" * 100)
    print(
        f"Rotation Status            : "
        f"{result.rotation_status}"
    )
    print(
        f"Rotation Direction         : "
        f"{result.rotation_direction}"
    )
    print(
        f"Rotation Breadth           : "
        f"{result.rotation_breadth}"
    )
    print(
        f"Rotation Speed             : "
        f"{result.rotation_speed}"
    )
    print(
        f"Leadership Stability       : "
        f"{result.leadership_stability}"
    )
    print(
        f"Dominant Sector Cycle      : "
        f"{result.dominant_sector_cycle}"
    )
    print(
        f"Improving Sectors          : "
        f"{result.improving_sectors}"
    )
    print(
        f"Deteriorating Sectors      : "
        f"{result.deteriorating_sectors}"
    )
    print(
        f"Stable Sectors             : "
        f"{result.stable_sectors}"
    )
    print(
        f"Rotation Risk              : "
        f"{result.rotation_risk_level} "
        f"({result.rotation_risk_score}%)"
    )
    print(
        f"Rotation Confidence        : "
        f"{result.rotation_confidence}%"
    )
    print("-" * 100)

    print("STAGE 3 — SECTOR DECISION")
    print("-" * 100)
    print(
        f"Decision Status            : "
        f"{result.decision_status}"
    )
    print(
        f"Sector Market Bias         : "
        f"{result.sector_market_bias}"
    )
    print(
        f"Participation Quality      : "
        f"{result.participation_quality}"
    )
    print(
        f"Leadership Quality         : "
        f"{result.leadership_quality}"
    )
    print(
        f"Rotation Quality           : "
        f"{result.rotation_quality}"
    )
    print(
        f"Sector Risk                : "
        f"{result.sector_risk_level}"
    )
    print(
        f"Decision Confidence        : "
        f"{result.decision_confidence}%"
    )
    print(
        f"Decision Quality           : "
        f"{result.decision_quality}"
    )
    print("-" * 100)

    print("MARKET ENVIRONMENT")
    print("-" * 100)
    print(result.market_environment)

    print("-" * 100)
    print("EXPECTED BEHAVIOUR")
    print("-" * 100)
    print(result.expected_behaviour)

    print("-" * 100)
    print("ANALYTICAL POSTURE")
    print("-" * 100)
    print(result.analytical_posture)

    print("-" * 100)
    print("MASTER CONCLUSION")
    print("-" * 100)
    print(result.master_conclusion)

    print("-" * 100)
    print("CONCISE SUMMARY")
    print("-" * 100)
    print(result.concise_summary)

    print("-" * 100)
    print("OUTPUT FILES")
    print("-" * 100)
    print(
        f"Strength CSV               : "
        f"{result.strength_csv_file}"
    )
    print(
        f"Strength Excel             : "
        f"{result.strength_excel_file}"
    )
    print(
        f"Rotation CSV               : "
        f"{result.rotation_csv_file}"
    )
    print(
        f"Rotation Excel             : "
        f"{result.rotation_excel_file}"
    )

    print("-" * 100)
    print(
        f"Overall Status             : "
        f"{result.overall_status}"
    )
    print(
        f"Message                    : "
        f"{result.message}"
    )
    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete AQSD Sector Intelligence Daily Pipeline."
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
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=(
            "Path to the enriched market-breadth snapshot. "
            f"Default: {DEFAULT_INPUT_FILE}"
        ),
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
        help=(
            "Saved sessions used for weekly sector rotation. "
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
        parse_date(arguments.date)
        if arguments.date
        else None
    )

    try:
        result = run_sector_daily_pipeline(
            requested_date=requested_date,
            source_file=(
                arguments.input
                .expanduser()
                .resolve()
            ),
            weekly_lookback_sessions=(
                arguments.weekly_sessions
            ),
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print("AQSD SECTOR INTELLIGENCE DAILY PIPELINE")
        print("=" * 100)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 100)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()