"""
AQSD
Market History Recorder

Module : MHR-001
Version: 1.0.0
Author : AQSD

Description
-----------
Records one daily snapshot of the final AQSD Market Master Decision.

The recorder does NOT create a new market opinion.

It preserves the output of the existing intelligence chain:

Participant Intelligence
        ↓
Market Breadth
        ↓
Sector Intelligence
        ↓
Options Intelligence
        ↓
Market Structure
        ↓
Market Regime
        ↓
Market Master Decision
        ↓
Market History Recorder

Purpose
-------
Build a permanent historical intelligence dataset that can later
support:

- Day-over-day intelligence change
- Regime persistence analysis
- Probability trend analysis
- Confidence trend analysis
- Historical similarity
- Forward-return research
- Knowledge generation
- Decision validation

Important
---------
This module:

- Does not generate BUY / SELL / SHORT orders.
- Does not alter raw market data.
- Does not independently rerun lower intelligence engines.
- Calls the Market Master Decision Engine once.
- Prevents duplicate daily records.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

import pandas as pd

from Scripts.aqsd_intelligence.market_master_decision_engine import (
    MarketMasterDecisionResult,
    run_market_master_decision_engine,
)
from Scripts.aqsd_market_intelligence_pipeline import (
    DEFAULT_BREADTH_INPUT_FILE,
    DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MHR-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

OUTPUT_DIR: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_History"
)

HISTORY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "market_intelligence_history.csv"
)

LATEST_FILE: Final[Path] = (
    OUTPUT_DIR
    / "market_intelligence_latest.json"
)

ARCHIVE_DIR: Final[Path] = (
    OUTPUT_DIR
    / "Archive"
)


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD into a date object.
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


def clean_text(
    value: object,
) -> str:
    """
    Convert a value to safe plain text.
    """

    if value is None:
        return ""

    return str(value).strip()


def flatten_sequence(
    value: object,
) -> str:
    """
    Convert tuples/lists into one pipe-separated field.
    """

    if value is None:
        return ""

    if isinstance(
        value,
        (
            tuple,
            list,
            set,
        ),
    ):
        return " | ".join(
            clean_text(item)
            for item in value
            if clean_text(item)
        )

    return clean_text(
        value
    )


def json_safe(
    value: Any,
) -> Any:
    """
    Convert common Python objects into JSON-safe values.
    """

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        Path,
    ):
        return str(value)

    if isinstance(
        value,
        tuple,
    ):
        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        list,
    ):
        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    return value


# ==========================================================
# RESULT NORMALIZATION
# ==========================================================

def decision_to_record(
    result: MarketMasterDecisionResult,
) -> dict[str, object]:
    """
    Convert Market Master Decision output into one historical row.
    """

    return {
        # --------------------------------------------------
        # RECORD METADATA
        # --------------------------------------------------

        "recorded_at": datetime.now().isoformat(
            timespec="seconds"
        ),

        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,

        "requested_date": (
            result.requested_date.isoformat()
            if result.requested_date is not None
            else ""
        ),

        "analysis_date": (
            result.analysis_date.isoformat()
        ),

        # --------------------------------------------------
        # FINAL MARKET ASSESSMENT
        # --------------------------------------------------

        "final_market_bias": (
            result.final_market_bias
        ),

        "primary_regime": (
            result.primary_regime
        ),

        "secondary_regime": (
            result.secondary_regime
        ),

        # --------------------------------------------------
        # INTELLIGENCE FAMILY VIEWS
        # --------------------------------------------------

        "institutional_view": (
            result.institutional_view
        ),

        "breadth_view": (
            result.breadth_view
        ),

        "sector_view": (
            result.sector_view
        ),

        "trend_environment": (
            result.trend_environment
        ),

        "options_environment": (
            result.options_environment
        ),

        # --------------------------------------------------
        # QUALITY
        # --------------------------------------------------

        "structural_quality": (
            result.structural_quality
        ),

        "participation_quality": (
            result.participation_quality
        ),

        "institutional_alignment": (
            result.institutional_alignment
        ),

        # --------------------------------------------------
        # RISK
        # --------------------------------------------------

        "risk_level": (
            result.risk_level
        ),

        "risk_posture": (
            result.risk_posture
        ),

        # --------------------------------------------------
        # PROBABILITIES
        # --------------------------------------------------

        "bullish_probability": float(
            result.bullish_probability
        ),

        "bearish_probability": float(
            result.bearish_probability
        ),

        "neutral_probability": float(
            result.neutral_probability
        ),

        # --------------------------------------------------
        # DECISION QUALITY
        # --------------------------------------------------

        "confidence": int(
            result.confidence
        ),

        "decision_grade": (
            result.decision_grade
        ),

        "decision_status": (
            result.decision_status
        ),

        # --------------------------------------------------
        # EXPECTED MARKET BEHAVIOUR
        # --------------------------------------------------

        "expected_behaviour": (
            result.expected_behaviour
        ),

        "trading_environment": (
            result.trading_environment
        ),

        "analytical_posture": (
            result.analytical_posture
        ),

        # --------------------------------------------------
        # CONDITIONS
        # --------------------------------------------------

        "confirmation_conditions": (
            flatten_sequence(
                result.confirmation_conditions
            )
        ),

        "invalidation_conditions": (
            flatten_sequence(
                result.invalidation_conditions
            )
        ),

        "warnings": (
            flatten_sequence(
                result.warnings
            )
        ),

        "warning_count": len(
            result.warnings
        ),

        # --------------------------------------------------
        # EXPLANATION
        # --------------------------------------------------

        "concise_summary": (
            result.concise_summary
        ),

        "explanation": (
            result.explanation
        ),

        "final_conclusion": (
            result.final_conclusion
        ),

        # --------------------------------------------------
        # PIPELINE HEALTH
        # --------------------------------------------------

        "pipeline_status": (
            result.pipeline_status
        ),

        "market_regime_status": (
            result.market_regime_status
        ),

        "overall_status": (
            result.status
        ),
    }


# ==========================================================
# HISTORY STORAGE
# ==========================================================

def load_history() -> pd.DataFrame:
    """
    Load existing AQSD market intelligence history.
    """

    if not HISTORY_FILE.exists():
        return pd.DataFrame()

    try:
        history = pd.read_csv(
            HISTORY_FILE,
            low_memory=False,
        )

    except Exception as exc:
        raise RuntimeError(
            "Could not read existing Market History file: "
            f"{exc}"
        ) from exc

    return history


def upsert_history_record(
    record: dict[str, object],
) -> tuple[pd.DataFrame, str]:
    """
    Insert or replace one daily Market Intelligence record.

    One analysis date = one permanent current record.

    Re-running the same trading date replaces that date's earlier
    snapshot instead of creating duplicates.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    history = load_history()

    new_row = pd.DataFrame(
        [record]
    )

    analysis_date = clean_text(
        record.get(
            "analysis_date"
        )
    )

    action = "INSERTED"

    if not history.empty:
        if "analysis_date" in history.columns:
            existing_dates = (
                history["analysis_date"]
                .astype(str)
                .str.strip()
            )

            duplicate_mask = (
                existing_dates
                == analysis_date
            )

            if duplicate_mask.any():
                history = history.loc[
                    ~duplicate_mask
                ].copy()

                action = "UPDATED"

    history = pd.concat(
        [
            history,
            new_row,
        ],
        ignore_index=True,
    )

    if "analysis_date" in history.columns:
        history["_sort_date"] = pd.to_datetime(
            history["analysis_date"],
            errors="coerce",
        )

        history = (
            history
            .sort_values(
                "_sort_date"
            )
            .drop(
                columns=[
                    "_sort_date"
                ]
            )
            .reset_index(
                drop=True
            )
        )

    history.to_csv(
        HISTORY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return (
        history,
        action,
    )


# ==========================================================
# JSON STORAGE
# ==========================================================

def save_latest_json(
    result: MarketMasterDecisionResult,
    record: dict[str, object],
) -> Path:
    """
    Save the latest intelligence result as JSON.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload: dict[str, object] = {
        "module": {
            "id": MODULE_ID,
            "version": MODULE_VERSION,
        },

        "record": {
            key: json_safe(value)
            for key, value in record.items()
        },
    }

    if is_dataclass(
        result
    ):
        payload["master_decision"] = json_safe(
            asdict(
                result
            )
        )

    LATEST_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return LATEST_FILE


def save_archive_json(
    record: dict[str, object],
) -> Path:
    """
    Save a dated immutable-style JSON snapshot.
    """

    ARCHIVE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    analysis_date = clean_text(
        record.get(
            "analysis_date"
        )
    )

    archive_file = (
        ARCHIVE_DIR
        / (
            "market_intelligence_"
            f"{analysis_date.replace('-', '')}.json"
        )
    )

    archive_file.write_text(
        json.dumps(
            {
                key: json_safe(value)
                for key, value in record.items()
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return archive_file


# ==========================================================
# CHANGE ANALYSIS
# ==========================================================

def calculate_latest_change(
    history: pd.DataFrame,
) -> dict[str, object]:
    """
    Compare the latest stored session with the previous one.
    """

    if len(history) < 2:
        return {
            "available": False,
            "message": (
                "At least two recorded sessions are required "
                "for change analysis."
            ),
        }

    previous = history.iloc[-2]
    current = history.iloc[-1]

    current_bullish = float(
        current.get(
            "bullish_probability",
            0.0,
        )
    )

    previous_bullish = float(
        previous.get(
            "bullish_probability",
            0.0,
        )
    )

    current_bearish = float(
        current.get(
            "bearish_probability",
            0.0,
        )
    )

    previous_bearish = float(
        previous.get(
            "bearish_probability",
            0.0,
        )
    )

    current_neutral = float(
        current.get(
            "neutral_probability",
            0.0,
        )
    )

    previous_neutral = float(
        previous.get(
            "neutral_probability",
            0.0,
        )
    )

    current_confidence = float(
        current.get(
            "confidence",
            0.0,
        )
    )

    previous_confidence = float(
        previous.get(
            "confidence",
            0.0,
        )
    )

    return {
        "available": True,

        "previous_date": clean_text(
            previous.get(
                "analysis_date"
            )
        ),

        "current_date": clean_text(
            current.get(
                "analysis_date"
            )
        ),

        "previous_bias": clean_text(
            previous.get(
                "final_market_bias"
            )
        ),

        "current_bias": clean_text(
            current.get(
                "final_market_bias"
            )
        ),

        "previous_regime": clean_text(
            previous.get(
                "primary_regime"
            )
        ),

        "current_regime": clean_text(
            current.get(
                "primary_regime"
            )
        ),

        "bullish_probability_change": round(
            current_bullish
            - previous_bullish,
            1,
        ),

        "bearish_probability_change": round(
            current_bearish
            - previous_bearish,
            1,
        ),

        "neutral_probability_change": round(
            current_neutral
            - previous_neutral,
            1,
        ),

        "confidence_change": round(
            current_confidence
            - previous_confidence,
            1,
        ),
    }


# ==========================================================
# MAIN RECORDER
# ==========================================================

def run_market_history_recorder(
    *,
    requested_date: date | None = None,
    breadth_source_file: Path = (
        DEFAULT_BREADTH_INPUT_FILE
    ),
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
) -> dict[str, object]:
    """
    Run the AQSD Market Master Decision once and record it.
    """

    result = run_market_master_decision_engine(
        requested_date=requested_date,
        breadth_source_file=(
            breadth_source_file
            .expanduser()
            .resolve()
        ),
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    record = decision_to_record(
        result
    )

    (
        history,
        storage_action,
    ) = upsert_history_record(
        record
    )

    latest_json = save_latest_json(
        result,
        record,
    )

    archive_json = save_archive_json(
        record
    )

    change_analysis = calculate_latest_change(
        history
    )

    return {
        "result": result,
        "record": record,
        "history_rows": len(
            history
        ),
        "storage_action": storage_action,
        "history_file": HISTORY_FILE,
        "latest_json": latest_json,
        "archive_json": archive_json,
        "change_analysis": change_analysis,
        "status": "SUCCESS",
    }


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    recorder_result: dict[str, object],
) -> None:
    """
    Display concise Market History Recorder result.
    """

    record = recorder_result[
        "record"
    ]

    change = recorder_result[
        "change_analysis"
    ]

    print()
    print("=" * 100)
    print("AQSD MARKET HISTORY RECORDER")
    print("=" * 100)

    print(
        f"Module                  : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                 : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Analysis Date           : "
        f"{record['analysis_date']}"
    )

    print(
        f"Storage Action          : "
        f"{recorder_result['storage_action']}"
    )

    print(
        f"History Sessions        : "
        f"{recorder_result['history_rows']}"
    )

    print("-" * 100)

    print("RECORDED MARKET INTELLIGENCE")
    print("-" * 100)

    print(
        f"Final Market Bias       : "
        f"{record['final_market_bias']}"
    )

    print(
        f"Primary Regime          : "
        f"{record['primary_regime']}"
    )

    print(
        f"Secondary Regime        : "
        f"{record['secondary_regime']}"
    )

    print(
        f"Bullish Probability     : "
        f"{record['bullish_probability']:.1f}%"
    )

    print(
        f"Bearish Probability     : "
        f"{record['bearish_probability']:.1f}%"
    )

    print(
        f"Neutral Probability     : "
        f"{record['neutral_probability']:.1f}%"
    )

    print(
        f"Risk                    : "
        f"{record['risk_level']}"
    )

    print(
        f"Confidence              : "
        f"{record['confidence']}%"
    )

    print(
        f"Decision Grade          : "
        f"{record['decision_grade']}"
    )

    print("-" * 100)

    print("CHANGE FROM PREVIOUS RECORDED SESSION")
    print("-" * 100)

    if bool(
        change.get(
            "available"
        )
    ):
        print(
            f"Previous Date           : "
            f"{change['previous_date']}"
        )

        print(
            f"Previous Bias           : "
            f"{change['previous_bias']}"
        )

        print(
            f"Current Bias            : "
            f"{change['current_bias']}"
        )

        print(
            f"Previous Regime         : "
            f"{change['previous_regime']}"
        )

        print(
            f"Current Regime          : "
            f"{change['current_regime']}"
        )

        print(
            f"Bullish Probability Δ   : "
            f"{change['bullish_probability_change']:+.1f}"
        )

        print(
            f"Bearish Probability Δ   : "
            f"{change['bearish_probability_change']:+.1f}"
        )

        print(
            f"Neutral Probability Δ   : "
            f"{change['neutral_probability_change']:+.1f}"
        )

        print(
            f"Confidence Δ            : "
            f"{change['confidence_change']:+.1f}"
        )

    else:
        print(
            change.get(
                "message",
                "Change analysis not available.",
            )
        )

    print("-" * 100)

    print(
        f"History CSV             : "
        f"{recorder_result['history_file']}"
    )

    print(
        f"Latest JSON             : "
        f"{recorder_result['latest_json']}"
    )

    print(
        f"Archive JSON            : "
        f"{recorder_result['archive_json']}"
    )

    print(
        f"Status                  : "
        f"{recorder_result['status']}"
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
            "Record the AQSD daily Market Master Decision "
            "into permanent historical intelligence."
        )
    )

    parser.add_argument(
        "--date",
        required=False,
        help=(
            "Optional analysis date in YYYY-MM-DD format. "
            "When omitted, AQSD selects the latest trading day."
        ),
    )

    parser.add_argument(
        "--breadth-input",
        type=Path,
        default=DEFAULT_BREADTH_INPUT_FILE,
        help=(
            "Path to the enriched Market Breadth input file."
        ),
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
        help=(
            "Number of stored sessions used for weekly "
            "intelligence comparisons."
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
        result = run_market_history_recorder(
            requested_date=requested_date,
            breadth_source_file=(
                arguments.breadth_input
            ),
            weekly_lookback_sessions=(
                arguments.weekly_sessions
            ),
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print("AQSD MARKET HISTORY RECORDER")
        print("=" * 100)
        print("Status : FAILED")
        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )
        print("=" * 100)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()