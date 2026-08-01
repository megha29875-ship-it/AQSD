"""
AQSD
Market Breadth Change Engine

Module : MBI-004
Version: 1.0.0
Author : AQSD

Description
-----------
Compares the current market-breadth condition with previous trading
sessions and identifies improvement, deterioration, acceleration,
rotation and possible breadth reversals.

Inputs
------
Output/Market_Breadth/market_breadth_summary_YYYYMMDD.csv
Output/Market_Breadth/market_breadth_report_YYYYMMDD.xlsx

The files are created by:

    Scripts.aqsd_intelligence.market_breadth_engine

Analytics
---------
- Daily breadth change
- Weekly breadth change
- Advance-rate change
- EMA20 participation change
- EMA50 participation change
- EMA200 participation change
- Breadth-score change
- Breadth momentum shift
- Breadth trend shift
- Risk-on / risk-off transition
- Improving sectors
- Deteriorating sectors
- Sector rotation
- Breadth acceleration
- Breadth reversal risk
- Explainable conclusion

Important
---------
This engine does not generate BUY, SELL or SHORT instructions.

It produces analytical market-breadth change intelligence for the
AQSD Master Decision Engine.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MBI-004"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

BREADTH_OUTPUT_DIRECTORY: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_Breadth"
)

CHANGE_OUTPUT_DIRECTORY: Final[Path] = (
    BREADTH_OUTPUT_DIRECTORY
    / "Change"
)

DEFAULT_WEEKLY_LOOKBACK_SESSIONS: Final[int] = 5


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class BreadthSnapshot:
    """
    Normalized breadth summary for one trading session.
    """

    analysis_date: date

    valid_stocks: int
    advances: int
    declines: int
    unchanged: int

    advance_percentage: float
    decline_percentage: float
    advance_decline_ratio: float | None

    above_ema20_percentage: float
    above_ema50_percentage: float
    above_ema200_percentage: float

    bullish_sectors: int
    bearish_sectors: int

    breadth_score: int
    breadth_momentum: str
    breadth_trend: str
    breadth_strength: str
    breadth_regime: str

    risk_environment: str
    internal_market_health: str
    participation_quality: str
    confidence: int


@dataclass(frozen=True)
class SectorChange:
    """
    Change in one sector's breadth score.
    """

    sector: str
    current_score: int
    previous_score: int
    score_change: int

    current_classification: str
    previous_classification: str

    direction: str


@dataclass(frozen=True)
class MarketBreadthChangeResult:
    """
    Complete market-breadth change result.
    """

    requested_date: date
    analysis_date: date
    previous_date: date | None
    weekly_reference_date: date | None

    current_breadth_score: int
    previous_breadth_score: int | None
    weekly_breadth_score: int | None

    daily_breadth_score_change: int | None
    weekly_breadth_score_change: int | None

    daily_advance_change: float | None
    weekly_advance_change: float | None

    daily_ema20_change: float | None
    daily_ema50_change: float | None
    daily_ema200_change: float | None

    weekly_ema20_change: float | None
    weekly_ema50_change: float | None
    weekly_ema200_change: float | None

    breadth_direction: str
    breadth_velocity: str
    breadth_acceleration: str

    momentum_shift: str
    trend_shift: str
    regime_transition: str
    risk_transition: str
    health_transition: str

    improving_sectors: tuple[SectorChange, ...]
    deteriorating_sectors: tuple[SectorChange, ...]
    stable_sectors: tuple[SectorChange, ...]

    sector_rotation: str
    sector_rotation_strength: str

    reversal_risk_score: int
    reversal_risk_level: str
    reversal_direction: str

    change_confidence: int
    expected_behaviour: str
    concise_summary: str
    explanation: str

    warnings: tuple[str, ...]
    status: str


# ==========================================================
# GENERAL HELPERS
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


def safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    """
    Convert a value into float safely.
    """

    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


def safe_int(
    value: object,
    default: int = 0,
) -> int:
    """
    Convert a value into integer safely.
    """

    return int(
        round(
            safe_float(
                value,
                default=float(default),
            )
        )
    )


def optional_difference(
    current: float,
    previous: float | None,
) -> float | None:
    """
    Calculate an optional difference.
    """

    if previous is None:
        return None

    return round(
        current - previous,
        2,
    )


def format_optional_number(
    value: float | int | None,
    decimals: int = 2,
    suffix: str = "",
) -> str:
    """
    Format an optional signed value.
    """

    if value is None:
        return "NOT AVAILABLE"

    if isinstance(value, int):
        return f"{value:+d}{suffix}"

    return f"{value:+.{decimals}f}{suffix}"


# ==========================================================
# FILE DISCOVERY
# ==========================================================

def extract_date_from_filename(
    file_path: Path,
) -> date | None:
    """
    Extract YYYYMMDD from a breadth output filename.
    """

    match = re.search(
        r"(\d{8})",
        file_path.stem,
    )

    if match is None:
        return None

    try:
        return datetime.strptime(
            match.group(1),
            "%Y%m%d",
        ).date()

    except ValueError:
        return None


def discover_summary_files() -> dict[date, Path]:
    """
    Discover all breadth summary CSV files.
    """

    files: dict[date, Path] = {}

    if not BREADTH_OUTPUT_DIRECTORY.exists():
        return files

    for file_path in BREADTH_OUTPUT_DIRECTORY.glob(
        "market_breadth_summary_*.csv"
    ):
        file_date = extract_date_from_filename(
            file_path
        )

        if file_date is not None:
            files[file_date] = file_path

    return files


def discover_report_files() -> dict[date, Path]:
    """
    Discover all breadth report Excel files.
    """

    files: dict[date, Path] = {}

    if not BREADTH_OUTPUT_DIRECTORY.exists():
        return files

    for file_path in BREADTH_OUTPUT_DIRECTORY.glob(
        "market_breadth_report_*.xlsx"
    ):
        file_date = extract_date_from_filename(
            file_path
        )

        if file_date is not None:
            files[file_date] = file_path

    return files


def select_analysis_dates(
    *,
    requested_date: date,
    available_dates: list[date],
    weekly_lookback_sessions: int,
) -> tuple[date, date | None, date | None]:
    """
    Select current, previous and weekly reference dates.
    """

    eligible_dates = sorted(
        value
        for value in available_dates
        if value <= requested_date
    )

    if not eligible_dates:
        raise RuntimeError(
            "No market-breadth summary is available on or before "
            f"{requested_date}."
        )

    analysis_date = eligible_dates[-1]

    previous_date = (
        eligible_dates[-2]
        if len(eligible_dates) >= 2
        else None
    )

    weekly_reference_date: date | None = None

    weekly_position = (
        len(eligible_dates)
        - 1
        - weekly_lookback_sessions
    )

    if weekly_position >= 0:
        weekly_reference_date = eligible_dates[
            weekly_position
        ]

    return (
        analysis_date,
        previous_date,
        weekly_reference_date,
    )


# ==========================================================
# SUMMARY READING
# ==========================================================

def first_available_value(
    row: pd.Series,
    aliases: tuple[str, ...],
    default: object = None,
) -> object:
    """
    Return the first available value from known column aliases.
    """

    normalized_columns = {
        str(column).strip().upper(): column
        for column in row.index
    }

    for alias in aliases:
        column = normalized_columns.get(
            alias.upper()
        )

        if column is not None:
            return row[column]

    return default


def read_breadth_snapshot(
    summary_file: Path,
    analysis_date: date,
) -> BreadthSnapshot:
    """
    Read one breadth summary CSV.
    """

    dataframe = pd.read_csv(
        summary_file,
        low_memory=False,
    )

    if dataframe.empty:
        raise RuntimeError(
            f"Breadth summary is empty: {summary_file}"
        )

    row = dataframe.iloc[-1]

    return BreadthSnapshot(
        analysis_date=analysis_date,

        valid_stocks=safe_int(
            first_available_value(
                row,
                (
                    "Valid_Stocks",
                    "Total_Stocks",
                    "Input_Rows",
                ),
            )
        ),

        advances=safe_int(
            first_available_value(
                row,
                ("Advances",),
            )
        ),

        declines=safe_int(
            first_available_value(
                row,
                ("Declines",),
            )
        ),

        unchanged=safe_int(
            first_available_value(
                row,
                ("Unchanged",),
            )
        ),

        advance_percentage=safe_float(
            first_available_value(
                row,
                ("Advance_Percentage",),
            )
        ),

        decline_percentage=safe_float(
            first_available_value(
                row,
                ("Decline_Percentage",),
            )
        ),

        advance_decline_ratio=(
            safe_float(
                first_available_value(
                    row,
                    ("Advance_Decline_Ratio",),
                )
            )
            if pd.notna(
                first_available_value(
                    row,
                    ("Advance_Decline_Ratio",),
                )
            )
            else None
        ),

        above_ema20_percentage=safe_float(
            first_available_value(
                row,
                ("Above_EMA20_Percentage",),
            )
        ),

        above_ema50_percentage=safe_float(
            first_available_value(
                row,
                ("Above_EMA50_Percentage",),
            )
        ),

        above_ema200_percentage=safe_float(
            first_available_value(
                row,
                ("Above_EMA200_Percentage",),
            )
        ),

        bullish_sectors=safe_int(
            first_available_value(
                row,
                ("Bullish_Sectors",),
            )
        ),

        bearish_sectors=safe_int(
            first_available_value(
                row,
                ("Bearish_Sectors",),
            )
        ),

        breadth_score=safe_int(
            first_available_value(
                row,
                ("Breadth_Score",),
            )
        ),

        breadth_momentum=str(
            first_available_value(
                row,
                ("Breadth_Momentum",),
                "UNKNOWN",
            )
        ).strip().upper(),

        breadth_trend=str(
            first_available_value(
                row,
                ("Breadth_Trend",),
                "UNKNOWN",
            )
        ).strip().upper(),

        breadth_strength=str(
            first_available_value(
                row,
                ("Breadth_Strength",),
                "UNKNOWN",
            )
        ).strip().upper(),

        breadth_regime=str(
            first_available_value(
                row,
                ("Breadth_Regime",),
                "UNKNOWN",
            )
        ).strip().upper(),

        risk_environment=str(
            first_available_value(
                row,
                ("Risk_Environment",),
                "UNKNOWN",
            )
        ).strip().upper(),

        internal_market_health=str(
            first_available_value(
                row,
                ("Internal_Market_Health",),
                "UNKNOWN",
            )
        ).strip().upper(),

        participation_quality=str(
            first_available_value(
                row,
                ("Participation_Quality",),
                "UNKNOWN",
            )
        ).strip().upper(),

        confidence=safe_int(
            first_available_value(
                row,
                ("Confidence",),
            )
        ),
    )


# ==========================================================
# SECTOR READING
# ==========================================================

def read_sector_report(
    report_file: Path | None,
) -> pd.DataFrame:
    """
    Read the Sectors worksheet from a breadth report.
    """

    expected_columns = [
        "Sector",
        "Score",
        "Classification",
    ]

    if report_file is None:
        return pd.DataFrame(
            columns=expected_columns
        )

    if not report_file.exists():
        return pd.DataFrame(
            columns=expected_columns
        )

    try:
        dataframe = pd.read_excel(
            report_file,
            sheet_name="Sectors",
            engine="openpyxl",
        )

    except (ValueError, FileNotFoundError):
        return pd.DataFrame(
            columns=expected_columns
        )

    if dataframe.empty:
        return pd.DataFrame(
            columns=expected_columns
        )

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    for column in expected_columns:
        if column not in dataframe.columns:
            if column == "Score":
                dataframe[column] = 0
            else:
                dataframe[column] = "UNKNOWN"

    dataframe["Sector"] = (
        dataframe["Sector"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe["Score"] = pd.to_numeric(
        dataframe["Score"],
        errors="coerce",
    ).fillna(0)

    dataframe["Classification"] = (
        dataframe["Classification"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe = dataframe.loc[
        dataframe["Sector"].ne("UNKNOWN")
    ].copy()

    return dataframe[
        expected_columns
    ].drop_duplicates(
        subset=["Sector"],
        keep="last",
    )


# ==========================================================
# CHANGE CLASSIFICATION
# ==========================================================

def determine_breadth_direction(
    *,
    daily_score_change: int | None,
    daily_advance_change: float | None,
    daily_ema20_change: float | None,
) -> str:
    """
    Determine the immediate breadth direction.
    """

    if (
        daily_score_change is None
        or daily_advance_change is None
        or daily_ema20_change is None
    ):
        return "INSUFFICIENT HISTORY"

    positive_signals = sum(
        (
            daily_score_change > 0,
            daily_advance_change > 0,
            daily_ema20_change > 0,
        )
    )

    negative_signals = sum(
        (
            daily_score_change < 0,
            daily_advance_change < 0,
            daily_ema20_change < 0,
        )
    )

    if (
        positive_signals == 3
        and daily_score_change >= 3
    ):
        return "STRONGLY IMPROVING"

    if positive_signals >= 2:
        return "IMPROVING"

    if (
        negative_signals == 3
        and daily_score_change <= -3
    ):
        return "STRONGLY DETERIORATING"

    if negative_signals >= 2:
        return "DETERIORATING"

    return "MIXED"


def determine_velocity(
    daily_score_change: int | None,
) -> str:
    """
    Determine breadth-change velocity.
    """

    if daily_score_change is None:
        return "INSUFFICIENT HISTORY"

    absolute_change = abs(
        daily_score_change
    )

    if absolute_change >= 10:
        return "VERY HIGH"

    if absolute_change >= 6:
        return "HIGH"

    if absolute_change >= 3:
        return "MODERATE"

    return "LOW"


def determine_acceleration(
    *,
    daily_score_change: int | None,
    weekly_score_change: int | None,
) -> str:
    """
    Compare daily change with the average weekly change.
    """

    if (
        daily_score_change is None
        or weekly_score_change is None
    ):
        return "INSUFFICIENT HISTORY"

    average_daily_weekly_change = (
        weekly_score_change
        / DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    )

    if (
        daily_score_change > 0
        and daily_score_change
        > average_daily_weekly_change + 2
    ):
        return "POSITIVE ACCELERATION"

    if (
        daily_score_change < 0
        and daily_score_change
        < average_daily_weekly_change - 2
    ):
        return "NEGATIVE ACCELERATION"

    if (
        weekly_score_change < 0
        and daily_score_change > 0
    ):
        return "EARLY POSITIVE TURN"

    if (
        weekly_score_change > 0
        and daily_score_change < 0
    ):
        return "EARLY NEGATIVE TURN"

    return "STABLE VELOCITY"


def determine_label_shift(
    *,
    current: str,
    previous: str | None,
    label_name: str,
) -> str:
    """
    Describe a label transition.
    """

    if previous is None:
        return "INSUFFICIENT HISTORY"

    if current == previous:
        return f"UNCHANGED — {current}"

    return (
        f"{previous} TO {current} "
        f"{label_name.upper()} SHIFT"
    )


# ==========================================================
# SECTOR CHANGE ANALYSIS
# ==========================================================

def compare_sectors(
    *,
    current_sectors: pd.DataFrame,
    previous_sectors: pd.DataFrame,
) -> tuple[
    tuple[SectorChange, ...],
    tuple[SectorChange, ...],
    tuple[SectorChange, ...],
]:
    """
    Compare current and previous sector scores.
    """

    if (
        current_sectors.empty
        or previous_sectors.empty
    ):
        return (
            tuple(),
            tuple(),
            tuple(),
        )

    current_map = current_sectors.set_index(
        "Sector"
    )

    previous_map = previous_sectors.set_index(
        "Sector"
    )

    common_sectors = sorted(
        set(current_map.index)
        & set(previous_map.index)
    )

    improving: list[SectorChange] = []
    deteriorating: list[SectorChange] = []
    stable: list[SectorChange] = []

    for sector in common_sectors:
        current_score = safe_int(
            current_map.at[
                sector,
                "Score",
            ]
        )

        previous_score = safe_int(
            previous_map.at[
                sector,
                "Score",
            ]
        )

        score_change = (
            current_score
            - previous_score
        )

        current_classification = str(
            current_map.at[
                sector,
                "Classification",
            ]
        ).strip().upper()

        previous_classification = str(
            previous_map.at[
                sector,
                "Classification",
            ]
        ).strip().upper()

        if score_change >= 3:
            direction = "IMPROVING"

        elif score_change <= -3:
            direction = "DETERIORATING"

        else:
            direction = "STABLE"

        result = SectorChange(
            sector=sector,
            current_score=current_score,
            previous_score=previous_score,
            score_change=score_change,
            current_classification=(
                current_classification
            ),
            previous_classification=(
                previous_classification
            ),
            direction=direction,
        )

        if direction == "IMPROVING":
            improving.append(
                result
            )

        elif direction == "DETERIORATING":
            deteriorating.append(
                result
            )

        else:
            stable.append(
                result
            )

    improving.sort(
        key=lambda item: item.score_change,
        reverse=True,
    )

    deteriorating.sort(
        key=lambda item: item.score_change,
    )

    stable.sort(
        key=lambda item: abs(
            item.score_change
        )
    )

    return (
        tuple(improving),
        tuple(deteriorating),
        tuple(stable),
    )


def determine_sector_rotation(
    *,
    improving_sectors: tuple[SectorChange, ...],
    deteriorating_sectors: tuple[SectorChange, ...],
) -> tuple[str, str]:
    """
    Determine the breadth of sector rotation.
    """

    improving_count = len(
        improving_sectors
    )

    deteriorating_count = len(
        deteriorating_sectors
    )

    total_moving_sectors = (
        improving_count
        + deteriorating_count
    )

    if total_moving_sectors == 0:
        return (
            "NO CLEAR ROTATION",
            "LOW",
        )

    difference = (
        improving_count
        - deteriorating_count
    )

    if (
        improving_count >= 8
        and difference >= 4
    ):
        return (
            "BROAD POSITIVE SECTOR ROTATION",
            "STRONG",
        )

    if difference >= 2:
        return (
            "SELECTIVE POSITIVE SECTOR ROTATION",
            "MODERATE",
        )

    if (
        deteriorating_count >= 8
        and difference <= -4
    ):
        return (
            "BROAD NEGATIVE SECTOR ROTATION",
            "STRONG",
        )

    if difference <= -2:
        return (
            "SELECTIVE NEGATIVE SECTOR ROTATION",
            "MODERATE",
        )

    return (
        "MIXED SECTOR ROTATION",
        "LOW TO MODERATE",
    )


# ==========================================================
# REVERSAL RISK
# ==========================================================

def calculate_reversal_risk(
    *,
    current: BreadthSnapshot,
    previous: BreadthSnapshot | None,
    daily_score_change: int | None,
    weekly_score_change: int | None,
    acceleration: str,
) -> tuple[int, str, str]:
    """
    Calculate breadth-reversal risk.
    """

    if previous is None:
        return (
            50,
            "MODERATE",
            "INSUFFICIENT HISTORY",
        )

    risk_score = 20.0
    reversal_direction = "TWO-SIDED"

    if (
        current.breadth_score <= 40
        and daily_score_change is not None
        and daily_score_change >= 4
    ):
        risk_score += 25
        reversal_direction = "BULLISH REVERSAL RISK"

    if (
        current.breadth_score >= 60
        and daily_score_change is not None
        and daily_score_change <= -4
    ):
        risk_score += 25
        reversal_direction = "BEARISH REVERSAL RISK"

    if acceleration == "EARLY POSITIVE TURN":
        risk_score += 20
        reversal_direction = "BULLISH REVERSAL RISK"

    elif acceleration == "EARLY NEGATIVE TURN":
        risk_score += 20
        reversal_direction = "BEARISH REVERSAL RISK"

    elif acceleration in {
        "POSITIVE ACCELERATION",
        "NEGATIVE ACCELERATION",
    }:
        risk_score += 10

    if (
        weekly_score_change is not None
        and daily_score_change is not None
        and (
            weekly_score_change
            * daily_score_change
            < 0
        )
    ):
        risk_score += 15

    if (
        current.breadth_momentum
        != previous.breadth_momentum
    ):
        risk_score += 10

    if (
        current.risk_environment
        != previous.risk_environment
    ):
        risk_score += 10

    final_score = clamp_score(
        risk_score
    )

    if final_score >= 80:
        risk_level = "VERY HIGH"

    elif final_score >= 65:
        risk_level = "HIGH"

    elif final_score >= 45:
        risk_level = "MODERATE"

    elif final_score >= 25:
        risk_level = "LOW TO MODERATE"

    else:
        risk_level = "LOW"

    return (
        final_score,
        risk_level,
        reversal_direction,
    )


# ==========================================================
# CONFIDENCE
# ==========================================================

def calculate_change_confidence(
    *,
    current: BreadthSnapshot,
    previous: BreadthSnapshot | None,
    weekly: BreadthSnapshot | None,
    sector_comparison_available: bool,
) -> int:
    """
    Calculate change-engine confidence.
    """

    score = current.confidence * 0.65

    if previous is not None:
        score += 15

    else:
        score -= 20

    if weekly is not None:
        score += 10

    else:
        score -= 8

    if sector_comparison_available:
        score += 10

    else:
        score -= 5

    return clamp_score(
        score
    )


# ==========================================================
# INTERPRETATION
# ==========================================================

def determine_expected_behaviour(
    *,
    direction: str,
    acceleration: str,
    sector_rotation: str,
    current: BreadthSnapshot,
) -> str:
    """
    Determine expected breadth-driven behaviour.
    """

    if (
        direction == "STRONGLY IMPROVING"
        and "POSITIVE" in acceleration
    ):
        return (
            "BROAD MARKET PARTICIPATION MAY IMPROVE FURTHER, "
            "SUPPORTING RECOVERY OR CONTINUATION ACROSS MORE STOCKS"
        )

    if direction == "IMPROVING":
        return (
            "MARKET PARTICIPATION IS IMPROVING, BUT CONFIRMATION "
            "FROM SECTOR ROTATION AND LONGER-TERM BREADTH IS REQUIRED"
        )

    if (
        direction == "STRONGLY DETERIORATING"
        and "NEGATIVE" in acceleration
    ):
        return (
            "MARKET WEAKNESS MAY BROADEN FURTHER, WITH RECOVERIES "
            "REMAINING VULNERABLE"
        )

    if direction == "DETERIORATING":
        return (
            "PARTICIPATION IS WEAKENING AND MARKET MOVES MAY BECOME "
            "MORE SELECTIVE OR DEFENSIVE"
        )

    if "POSITIVE" in sector_rotation:
        return (
            "SECTOR LEADERSHIP IS IMPROVING EVEN THOUGH OVERALL "
            "BREADTH REMAINS MIXED"
        )

    if "NEGATIVE" in sector_rotation:
        return (
            "SECTOR DETERIORATION MAY CREATE BROADER RISK-OFF "
            "CONDITIONS"
        )

    return (
        f"BREADTH CHANGE IS MIXED WHILE THE CURRENT REGIME REMAINS "
        f"{current.breadth_regime}"
    )


def build_concise_summary(
    *,
    direction: str,
    daily_score_change: int | None,
    weekly_score_change: int | None,
    acceleration: str,
    sector_rotation: str,
    reversal_risk_level: str,
    confidence: int,
) -> str:
    """
    Build a dashboard-ready summary.
    """

    return (
        f"{direction} BREADTH | "
        f"DAILY {format_optional_number(daily_score_change)} | "
        f"WEEKLY {format_optional_number(weekly_score_change)} | "
        f"{acceleration} | "
        f"{sector_rotation} | "
        f"{reversal_risk_level} REVERSAL RISK | "
        f"{confidence}% CONFIDENCE"
    )


def build_explanation(
    *,
    current: BreadthSnapshot,
    previous: BreadthSnapshot | None,
    weekly: BreadthSnapshot | None,
    direction: str,
    acceleration: str,
    sector_rotation: str,
    improving_sectors: tuple[SectorChange, ...],
    deteriorating_sectors: tuple[SectorChange, ...],
    reversal_risk_score: int,
    reversal_risk_level: str,
) -> str:
    """
    Build the final breadth-change explanation.
    """

    if previous is None:
        return (
            "Only one breadth session is currently available. "
            "The engine requires at least two sessions for daily "
            "change analysis and approximately six sessions for a "
            "five-session weekly comparison."
        )

    daily_score_change = (
        current.breadth_score
        - previous.breadth_score
    )

    daily_advance_change = (
        current.advance_percentage
        - previous.advance_percentage
    )

    weekly_text = (
        "Weekly comparison is not yet available."
        if weekly is None
        else (
            f"Compared with {weekly.analysis_date}, the breadth score "
            f"changed by "
            f"{current.breadth_score - weekly.breadth_score:+d} points."
        )
    )

    return (
        f"The current breadth score is {current.breadth_score}% compared "
        f"with {previous.breadth_score}% on {previous.analysis_date}, "
        f"a daily change of {daily_score_change:+d} points. "
        f"The advance rate changed by {daily_advance_change:+.2f} "
        f"percentage points. Breadth direction is "
        f"{direction.lower()} and acceleration is "
        f"{acceleration.lower()}. {weekly_text} "
        f"{len(improving_sectors)} sectors are improving and "
        f"{len(deteriorating_sectors)} sectors are deteriorating, "
        f"creating {sector_rotation.lower()}. Breadth reversal risk is "
        f"{reversal_risk_level.lower()} at {reversal_risk_score}%."
    )


def build_warnings(
    *,
    previous: BreadthSnapshot | None,
    weekly: BreadthSnapshot | None,
    sector_comparison_available: bool,
    reversal_risk_level: str,
    acceleration: str,
) -> tuple[str, ...]:
    """
    Build breadth-change warnings.
    """

    warnings: list[str] = []

    if previous is None:
        warnings.append(
            "Daily breadth comparison is unavailable because only one "
            "breadth summary exists."
        )

    if weekly is None:
        warnings.append(
            "Weekly breadth comparison requires at least six saved "
            "breadth sessions."
        )

    if not sector_comparison_available:
        warnings.append(
            "Sector change comparison is unavailable because matching "
            "sector reports were not found."
        )

    if reversal_risk_level in {
        "HIGH",
        "VERY HIGH",
    }:
        warnings.append(
            f"Breadth reversal risk is {reversal_risk_level.lower()}."
        )

    if acceleration in {
        "EARLY POSITIVE TURN",
        "EARLY NEGATIVE TURN",
    }:
        warnings.append(
            "The latest daily breadth direction conflicts with the "
            "five-session breadth direction."
        )

    if not warnings:
        warnings.append(
            "No major breadth-change warning is active."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# EXPORT
# ==========================================================

def export_result(
    result: MarketBreadthChangeResult,
) -> tuple[Path, Path]:
    """
    Export breadth-change results to CSV and Excel.
    """

    CHANGE_OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    date_text = result.analysis_date.strftime(
        "%Y%m%d"
    )

    csv_file = (
        CHANGE_OUTPUT_DIRECTORY
        / f"market_breadth_change_summary_{date_text}.csv"
    )

    excel_file = (
        CHANGE_OUTPUT_DIRECTORY
        / f"market_breadth_change_report_{date_text}.xlsx"
    )

    summary_dataframe = pd.DataFrame(
        [
            {
                "Requested_Date": result.requested_date,
                "Analysis_Date": result.analysis_date,
                "Previous_Date": result.previous_date,
                "Weekly_Reference_Date": (
                    result.weekly_reference_date
                ),
                "Current_Breadth_Score": (
                    result.current_breadth_score
                ),
                "Previous_Breadth_Score": (
                    result.previous_breadth_score
                ),
                "Weekly_Breadth_Score": (
                    result.weekly_breadth_score
                ),
                "Daily_Breadth_Score_Change": (
                    result.daily_breadth_score_change
                ),
                "Weekly_Breadth_Score_Change": (
                    result.weekly_breadth_score_change
                ),
                "Daily_Advance_Change": (
                    result.daily_advance_change
                ),
                "Weekly_Advance_Change": (
                    result.weekly_advance_change
                ),
                "Daily_EMA20_Change": (
                    result.daily_ema20_change
                ),
                "Daily_EMA50_Change": (
                    result.daily_ema50_change
                ),
                "Daily_EMA200_Change": (
                    result.daily_ema200_change
                ),
                "Weekly_EMA20_Change": (
                    result.weekly_ema20_change
                ),
                "Weekly_EMA50_Change": (
                    result.weekly_ema50_change
                ),
                "Weekly_EMA200_Change": (
                    result.weekly_ema200_change
                ),
                "Breadth_Direction": (
                    result.breadth_direction
                ),
                "Breadth_Velocity": (
                    result.breadth_velocity
                ),
                "Breadth_Acceleration": (
                    result.breadth_acceleration
                ),
                "Momentum_Shift": (
                    result.momentum_shift
                ),
                "Trend_Shift": result.trend_shift,
                "Regime_Transition": (
                    result.regime_transition
                ),
                "Risk_Transition": (
                    result.risk_transition
                ),
                "Health_Transition": (
                    result.health_transition
                ),
                "Sector_Rotation": (
                    result.sector_rotation
                ),
                "Sector_Rotation_Strength": (
                    result.sector_rotation_strength
                ),
                "Reversal_Risk_Score": (
                    result.reversal_risk_score
                ),
                "Reversal_Risk_Level": (
                    result.reversal_risk_level
                ),
                "Reversal_Direction": (
                    result.reversal_direction
                ),
                "Change_Confidence": (
                    result.change_confidence
                ),
                "Expected_Behaviour": (
                    result.expected_behaviour
                ),
                "Concise_Summary": (
                    result.concise_summary
                ),
                "Status": result.status,
            }
        ]
    )

    def sector_dataframe(
        sectors: tuple[SectorChange, ...],
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Sector": sector.sector,
                    "Previous_Score": (
                        sector.previous_score
                    ),
                    "Current_Score": (
                        sector.current_score
                    ),
                    "Score_Change": (
                        sector.score_change
                    ),
                    "Previous_Classification": (
                        sector.previous_classification
                    ),
                    "Current_Classification": (
                        sector.current_classification
                    ),
                    "Direction": sector.direction,
                }
                for sector in sectors
            ]
        )

    warnings_dataframe = pd.DataFrame(
        {
            "Warning": list(
                result.warnings
            )
        }
    )

    summary_dataframe.to_csv(
        csv_file,
        index=False,
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        sector_dataframe(
            result.improving_sectors
        ).to_excel(
            writer,
            sheet_name="Improving Sectors",
            index=False,
        )

        sector_dataframe(
            result.deteriorating_sectors
        ).to_excel(
            writer,
            sheet_name="Weakening Sectors",
            index=False,
        )

        sector_dataframe(
            result.stable_sectors
        ).to_excel(
            writer,
            sheet_name="Stable Sectors",
            index=False,
        )

        warnings_dataframe.to_excel(
            writer,
            sheet_name="Warnings",
            index=False,
        )

    return (
        csv_file,
        excel_file,
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_market_breadth_change_engine(
    *,
    requested_date: date,
    weekly_lookback_sessions: int = (
        DEFAULT_WEEKLY_LOOKBACK_SESSIONS
    ),
    export: bool = True,
) -> MarketBreadthChangeResult:
    """
    Run MBI-004.
    """

    summary_files = discover_summary_files()

    if not summary_files:
        raise FileNotFoundError(
            "No market breadth summary CSV files were found in: "
            f"{BREADTH_OUTPUT_DIRECTORY}"
        )

    report_files = discover_report_files()

    (
        analysis_date,
        previous_date,
        weekly_reference_date,
    ) = select_analysis_dates(
        requested_date=requested_date,
        available_dates=list(
            summary_files.keys()
        ),
        weekly_lookback_sessions=(
            weekly_lookback_sessions
        ),
    )

    current = read_breadth_snapshot(
        summary_files[analysis_date],
        analysis_date,
    )

    previous = (
        read_breadth_snapshot(
            summary_files[previous_date],
            previous_date,
        )
        if previous_date is not None
        else None
    )

    weekly = (
        read_breadth_snapshot(
            summary_files[weekly_reference_date],
            weekly_reference_date,
        )
        if weekly_reference_date is not None
        else None
    )

    previous_score = (
        previous.breadth_score
        if previous is not None
        else None
    )

    weekly_score = (
        weekly.breadth_score
        if weekly is not None
        else None
    )

    daily_score_change = (
        current.breadth_score
        - previous.breadth_score
        if previous is not None
        else None
    )

    weekly_score_change = (
        current.breadth_score
        - weekly.breadth_score
        if weekly is not None
        else None
    )

    daily_advance_change = optional_difference(
        current.advance_percentage,
        (
            previous.advance_percentage
            if previous is not None
            else None
        ),
    )

    weekly_advance_change = optional_difference(
        current.advance_percentage,
        (
            weekly.advance_percentage
            if weekly is not None
            else None
        ),
    )

    daily_ema20_change = optional_difference(
        current.above_ema20_percentage,
        (
            previous.above_ema20_percentage
            if previous is not None
            else None
        ),
    )

    daily_ema50_change = optional_difference(
        current.above_ema50_percentage,
        (
            previous.above_ema50_percentage
            if previous is not None
            else None
        ),
    )

    daily_ema200_change = optional_difference(
        current.above_ema200_percentage,
        (
            previous.above_ema200_percentage
            if previous is not None
            else None
        ),
    )

    weekly_ema20_change = optional_difference(
        current.above_ema20_percentage,
        (
            weekly.above_ema20_percentage
            if weekly is not None
            else None
        ),
    )

    weekly_ema50_change = optional_difference(
        current.above_ema50_percentage,
        (
            weekly.above_ema50_percentage
            if weekly is not None
            else None
        ),
    )

    weekly_ema200_change = optional_difference(
        current.above_ema200_percentage,
        (
            weekly.above_ema200_percentage
            if weekly is not None
            else None
        ),
    )

    breadth_direction = determine_breadth_direction(
        daily_score_change=daily_score_change,
        daily_advance_change=daily_advance_change,
        daily_ema20_change=daily_ema20_change,
    )

    breadth_velocity = determine_velocity(
        daily_score_change
    )

    breadth_acceleration = determine_acceleration(
        daily_score_change=daily_score_change,
        weekly_score_change=weekly_score_change,
    )

    momentum_shift = determine_label_shift(
        current=current.breadth_momentum,
        previous=(
            previous.breadth_momentum
            if previous is not None
            else None
        ),
        label_name="momentum",
    )

    trend_shift = determine_label_shift(
        current=current.breadth_trend,
        previous=(
            previous.breadth_trend
            if previous is not None
            else None
        ),
        label_name="trend",
    )

    regime_transition = determine_label_shift(
        current=current.breadth_regime,
        previous=(
            previous.breadth_regime
            if previous is not None
            else None
        ),
        label_name="regime",
    )

    risk_transition = determine_label_shift(
        current=current.risk_environment,
        previous=(
            previous.risk_environment
            if previous is not None
            else None
        ),
        label_name="risk environment",
    )

    health_transition = determine_label_shift(
        current=current.internal_market_health,
        previous=(
            previous.internal_market_health
            if previous is not None
            else None
        ),
        label_name="internal health",
    )

    current_sector_data = read_sector_report(
        report_files.get(
            analysis_date
        )
    )

    previous_sector_data = read_sector_report(
        (
            report_files.get(
                previous_date
            )
            if previous_date is not None
            else None
        )
    )

    (
        improving_sectors,
        deteriorating_sectors,
        stable_sectors,
    ) = compare_sectors(
        current_sectors=current_sector_data,
        previous_sectors=previous_sector_data,
    )

    sector_rotation, rotation_strength = (
        determine_sector_rotation(
            improving_sectors=improving_sectors,
            deteriorating_sectors=(
                deteriorating_sectors
            ),
        )
    )

    (
        reversal_risk_score,
        reversal_risk_level,
        reversal_direction,
    ) = calculate_reversal_risk(
        current=current,
        previous=previous,
        daily_score_change=daily_score_change,
        weekly_score_change=weekly_score_change,
        acceleration=breadth_acceleration,
    )

    sector_comparison_available = bool(
        improving_sectors
        or deteriorating_sectors
        or stable_sectors
    )

    change_confidence = calculate_change_confidence(
        current=current,
        previous=previous,
        weekly=weekly,
        sector_comparison_available=(
            sector_comparison_available
        ),
    )

    expected_behaviour = determine_expected_behaviour(
        direction=breadth_direction,
        acceleration=breadth_acceleration,
        sector_rotation=sector_rotation,
        current=current,
    )

    concise_summary = build_concise_summary(
        direction=breadth_direction,
        daily_score_change=daily_score_change,
        weekly_score_change=weekly_score_change,
        acceleration=breadth_acceleration,
        sector_rotation=sector_rotation,
        reversal_risk_level=reversal_risk_level,
        confidence=change_confidence,
    )

    explanation = build_explanation(
        current=current,
        previous=previous,
        weekly=weekly,
        direction=breadth_direction,
        acceleration=breadth_acceleration,
        sector_rotation=sector_rotation,
        improving_sectors=improving_sectors,
        deteriorating_sectors=(
            deteriorating_sectors
        ),
        reversal_risk_score=(
            reversal_risk_score
        ),
        reversal_risk_level=(
            reversal_risk_level
        ),
    )

    warnings = build_warnings(
        previous=previous,
        weekly=weekly,
        sector_comparison_available=(
            sector_comparison_available
        ),
        reversal_risk_level=(
            reversal_risk_level
        ),
        acceleration=breadth_acceleration,
    )

    result = MarketBreadthChangeResult(
        requested_date=requested_date,
        analysis_date=analysis_date,
        previous_date=previous_date,
        weekly_reference_date=(
            weekly_reference_date
        ),

        current_breadth_score=(
            current.breadth_score
        ),
        previous_breadth_score=(
            previous_score
        ),
        weekly_breadth_score=weekly_score,

        daily_breadth_score_change=(
            daily_score_change
        ),
        weekly_breadth_score_change=(
            weekly_score_change
        ),

        daily_advance_change=(
            daily_advance_change
        ),
        weekly_advance_change=(
            weekly_advance_change
        ),

        daily_ema20_change=daily_ema20_change,
        daily_ema50_change=daily_ema50_change,
        daily_ema200_change=(
            daily_ema200_change
        ),

        weekly_ema20_change=(
            weekly_ema20_change
        ),
        weekly_ema50_change=(
            weekly_ema50_change
        ),
        weekly_ema200_change=(
            weekly_ema200_change
        ),

        breadth_direction=breadth_direction,
        breadth_velocity=breadth_velocity,
        breadth_acceleration=(
            breadth_acceleration
        ),

        momentum_shift=momentum_shift,
        trend_shift=trend_shift,
        regime_transition=regime_transition,
        risk_transition=risk_transition,
        health_transition=health_transition,

        improving_sectors=improving_sectors,
        deteriorating_sectors=(
            deteriorating_sectors
        ),
        stable_sectors=stable_sectors,

        sector_rotation=sector_rotation,
        sector_rotation_strength=(
            rotation_strength
        ),

        reversal_risk_score=(
            reversal_risk_score
        ),
        reversal_risk_level=(
            reversal_risk_level
        ),
        reversal_direction=(
            reversal_direction
        ),

        change_confidence=change_confidence,
        expected_behaviour=expected_behaviour,
        concise_summary=concise_summary,
        explanation=explanation,

        warnings=warnings,
        status=(
            "SUCCESS"
            if previous is not None
            else "INSUFFICIENT HISTORY"
        ),
    )

    if export:
        export_result(
            result
        )

    return result


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def display_sector_changes(
    *,
    heading: str,
    sectors: tuple[SectorChange, ...],
    limit: int = 8,
) -> None:
    """
    Display sector changes.
    """

    print(heading)
    print("-" * 104)

    if not sectors:
        print("No sector comparison is available.")
        return

    for sector in sectors[:limit]:
        print(
            f"{sector.sector:<35}: "
            f"{sector.previous_score:>3}% -> "
            f"{sector.current_score:>3}% | "
            f"Change {sector.score_change:+d} | "
            f"{sector.current_classification}"
        )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketBreadthChangeResult,
) -> None:
    """
    Display the complete MBI-004 result.
    """

    print()
    print("=" * 104)
    print("AQSD MARKET BREADTH CHANGE ENGINE")
    print("=" * 104)
    print(f"Module                           : {MODULE_ID}")
    print(f"Version                          : {MODULE_VERSION}")
    print(f"Requested Date                   : {result.requested_date}")
    print(f"Analysis Date                    : {result.analysis_date}")
    print(f"Previous Date                    : {result.previous_date}")
    print(
        f"Weekly Reference Date            : "
        f"{result.weekly_reference_date}"
    )
    print("-" * 104)

    print("BREADTH SCORE CHANGE")
    print("-" * 104)
    print(
        f"Current Breadth Score             : "
        f"{result.current_breadth_score}%"
    )
    print(
        f"Previous Breadth Score            : "
        f"{result.previous_breadth_score}"
    )
    print(
        f"Weekly Breadth Score              : "
        f"{result.weekly_breadth_score}"
    )
    print(
        f"Daily Breadth Change              : "
        f"{format_optional_number(result.daily_breadth_score_change)}"
    )
    print(
        f"Weekly Breadth Change             : "
        f"{format_optional_number(result.weekly_breadth_score_change)}"
    )
    print("-" * 104)

    print("PARTICIPATION CHANGE")
    print("-" * 104)
    print(
        f"Daily Advance-Rate Change         : "
        f"{format_optional_number(result.daily_advance_change, suffix='%')}"
    )
    print(
        f"Weekly Advance-Rate Change        : "
        f"{format_optional_number(result.weekly_advance_change, suffix='%')}"
    )
    print(
        f"Daily EMA20 Participation Change  : "
        f"{format_optional_number(result.daily_ema20_change, suffix='%')}"
    )
    print(
        f"Daily EMA50 Participation Change  : "
        f"{format_optional_number(result.daily_ema50_change, suffix='%')}"
    )
    print(
        f"Daily EMA200 Participation Change : "
        f"{format_optional_number(result.daily_ema200_change, suffix='%')}"
    )
    print(
        f"Weekly EMA20 Participation Change : "
        f"{format_optional_number(result.weekly_ema20_change, suffix='%')}"
    )
    print(
        f"Weekly EMA50 Participation Change : "
        f"{format_optional_number(result.weekly_ema50_change, suffix='%')}"
    )
    print(
        f"Weekly EMA200 Participation Change: "
        f"{format_optional_number(result.weekly_ema200_change, suffix='%')}"
    )
    print("-" * 104)

    print("CHANGE CLASSIFICATION")
    print("-" * 104)
    print(
        f"Breadth Direction                 : "
        f"{result.breadth_direction}"
    )
    print(
        f"Breadth Velocity                  : "
        f"{result.breadth_velocity}"
    )
    print(
        f"Breadth Acceleration              : "
        f"{result.breadth_acceleration}"
    )
    print(
        f"Momentum Shift                    : "
        f"{result.momentum_shift}"
    )
    print(
        f"Trend Shift                       : "
        f"{result.trend_shift}"
    )
    print(
        f"Regime Transition                 : "
        f"{result.regime_transition}"
    )
    print(
        f"Risk Transition                   : "
        f"{result.risk_transition}"
    )
    print(
        f"Health Transition                 : "
        f"{result.health_transition}"
    )
    print("-" * 104)

    print("SECTOR ROTATION")
    print("-" * 104)
    print(
        f"Sector Rotation                   : "
        f"{result.sector_rotation}"
    )
    print(
        f"Rotation Strength                 : "
        f"{result.sector_rotation_strength}"
    )
    print(
        f"Improving Sectors                 : "
        f"{len(result.improving_sectors)}"
    )
    print(
        f"Deteriorating Sectors             : "
        f"{len(result.deteriorating_sectors)}"
    )
    print(
        f"Stable Sectors                    : "
        f"{len(result.stable_sectors)}"
    )
    print("-" * 104)

    display_sector_changes(
        heading="TOP IMPROVING SECTORS",
        sectors=result.improving_sectors,
    )

    print("-" * 104)

    display_sector_changes(
        heading="TOP DETERIORATING SECTORS",
        sectors=result.deteriorating_sectors,
    )

    print("-" * 104)
    print("REVERSAL RISK")
    print("-" * 104)
    print(
        f"Reversal Risk Score               : "
        f"{result.reversal_risk_score}%"
    )
    print(
        f"Reversal Risk Level               : "
        f"{result.reversal_risk_level}"
    )
    print(
        f"Reversal Direction                : "
        f"{result.reversal_direction}"
    )
    print(
        f"Change Confidence                 : "
        f"{result.change_confidence}%"
    )
    print("-" * 104)

    print("EXPECTED BEHAVIOUR")
    print("-" * 104)
    print(result.expected_behaviour)
    print("-" * 104)

    print("CONCISE SUMMARY")
    print("-" * 104)
    print(result.concise_summary)
    print("-" * 104)

    print("WARNINGS")
    print("-" * 104)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(f"{number}. {warning}")

    print("-" * 104)
    print("EXPLANATION")
    print("-" * 104)
    print(result.explanation)
    print("-" * 104)
    print(
        "Method                           : "
        "RULE-BASED MARKET BREADTH CHANGE ANALYSIS"
    )
    print(
        f"Status                           : "
        f"{result.status}"
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
            "Compare current NSE market breadth with previous "
            "AQSD breadth sessions."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested analysis date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--weekly-sessions",
        type=int,
        default=DEFAULT_WEEKLY_LOOKBACK_SESSIONS,
        help=(
            "Number of saved breadth sessions used for the weekly "
            f"comparison. Default: {DEFAULT_WEEKLY_LOOKBACK_SESSIONS}"
        ),
    )

    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Run without creating CSV and Excel output files.",
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    if arguments.weekly_sessions < 1:
        raise ValueError(
            "--weekly-sessions must be at least 1."
        )

    try:
        result = run_market_breadth_change_engine(
            requested_date=parse_date(
                arguments.date
            ),
            weekly_lookback_sessions=(
                arguments.weekly_sessions
            ),
            export=not arguments.no_export,
        )

    except Exception as exc:
        print()
        print("=" * 104)
        print("AQSD MARKET BREADTH CHANGE ENGINE")
        print("=" * 104)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 104)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()