"""
AQSD
Participant Historical Change Engine

Module : APD-009
Version: 1.0.0
Author : AQSD

Description
-----------
Analyses participant Index Futures Open Interest across multiple
historical comparison periods.

Comparison periods
------------------
- Previous available trading date
- Approximately one trading week earlier
- Approximately one trading month earlier

Outputs
-------
- Current Long, Short, Net and Gross positions
- Daily changes
- Weekly changes
- Monthly changes
- Percentage changes
- Positioning behaviour
- Directional effect
- Trend consistency
- Conviction score
- Institutional alignment
- Explainable interpretation

Data protection
---------------
- Future APD dates are excluded.
- Saturday and Sunday dates are excluded.
- Analysis never uses data later than the requested date.
- The engine does not generate BUY or SELL orders.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

from Scripts.aqsd_database.database import AQSDDatabase
from Scripts.aqsd_intelligence.participant_intelligence import (
    ParticipantSnapshot,
    load_index_futures_snapshot,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

APD_DATABASE_FILE: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "APD"
    / "participant_database.db"
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-009"
MODULE_VERSION: Final[str] = "1.0.0"

PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
    "CLIENT",
)

INSTITUTIONAL_PARTICIPANTS: Final[tuple[str, ...]] = (
    "FII",
    "PRO",
    "DII",
)

WEEK_LOOKBACK_CALENDAR_DAYS: Final[int] = 7
MONTH_LOOKBACK_CALENDAR_DAYS: Final[int] = 30


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class PeriodChange:
    """
    Position change between the current date and one comparison date.
    """

    comparison_date: date | None

    long_change: float | None
    long_change_percent: float | None

    short_change: float | None
    short_change_percent: float | None

    net_change: float | None
    net_change_percent: float | None

    gross_change: float | None
    gross_change_percent: float | None

    behaviour: str
    directional_effect: str


@dataclass(frozen=True)
class ParticipantHistoricalIntelligence:
    """
    Multi-period historical intelligence for one participant.
    """

    participant: str
    current_date: date

    current_long: float
    current_short: float
    current_net: float
    current_gross: float

    current_long_percentage: float
    current_short_percentage: float
    current_bias: str

    daily: PeriodChange
    weekly: PeriodChange
    monthly: PeriodChange

    trend_consistency: str
    positioning_state: str
    conviction_score: int
    interpretation: str


@dataclass(frozen=True)
class ParticipantHistoricalResult:
    """
    Complete APD-009 output.
    """

    requested_date: date
    current_date: date

    previous_date: date | None
    weekly_reference_date: date | None
    monthly_reference_date: date | None

    participant_results: tuple[
        ParticipantHistoricalIntelligence,
        ...,
    ]

    institutional_current_net: float
    institutional_daily_net_change: float | None
    institutional_weekly_net_change: float | None
    institutional_monthly_net_change: float | None

    institutional_bias: str
    institutional_trend: str
    institutional_alignment: str
    overall_conviction: int
    status: str


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def safe_percentage(
    numerator: float,
    denominator: float,
) -> float | None:
    """
    Calculate a percentage safely.

    Returns None when the denominator is zero.
    """

    if denominator == 0:
        return None

    return round(
        (numerator / abs(denominator)) * 100,
        2,
    )


def position_percentage(
    position: float,
    gross: float,
) -> float:
    """
    Calculate position as a percentage of gross exposure.
    """

    if gross == 0:
        return 0.0

    return round(
        (position / gross) * 100,
        2,
    )


def format_optional_number(
    value: float | None,
) -> str:
    """
    Format an optional number.
    """

    if value is None:
        return "N/A"

    return f"{value:+,.0f}"


def format_optional_percentage(
    value: float | None,
) -> str:
    """
    Format an optional percentage.
    """

    if value is None:
        return "N/A"

    return f"{value:+,.2f}%"


# ==========================================================
# DATE VALIDATION
# ==========================================================

def is_weekend(
    check_date: date,
) -> bool:
    """
    Return True for Saturday or Sunday.
    """

    return check_date.weekday() >= 5


def get_valid_apd_dates(
    database: AQSDDatabase,
    requested_date: date,
) -> list[date]:
    """
    Return unique valid APD dates on or before the requested date.

    Weekend rows and future rows are excluded.
    """

    rows = database.query(
        """
        SELECT DISTINCT trade_date
        FROM participant_positions
        WHERE trade_date <= ?
        ORDER BY trade_date
        """,
        (
            requested_date.isoformat(),
        ),
    )

    valid_dates: list[date] = []

    for row in rows:
        raw_value = row["trade_date"]

        if raw_value is None:
            continue

        try:
            parsed_date = date.fromisoformat(
                str(raw_value)
            )

        except ValueError:
            continue

        if parsed_date > requested_date:
            continue

        if is_weekend(parsed_date):
            continue

        valid_dates.append(
            parsed_date
        )

    return sorted(
        set(valid_dates)
    )


def latest_date_on_or_before(
    valid_dates: list[date],
    target_date: date,
) -> date | None:
    """
    Return the latest valid date on or before a target date.
    """

    eligible_dates = [
        available_date
        for available_date in valid_dates
        if available_date <= target_date
    ]

    if not eligible_dates:
        return None

    return max(eligible_dates)


def previous_available_date(
    valid_dates: list[date],
    current_date: date,
) -> date | None:
    """
    Return the latest valid APD date before the current date.
    """

    eligible_dates = [
        available_date
        for available_date in valid_dates
        if available_date < current_date
    ]

    if not eligible_dates:
        return None

    return max(eligible_dates)


def comparison_date_for_lookback(
    valid_dates: list[date],
    current_date: date,
    calendar_days: int,
) -> date | None:
    """
    Find the latest valid APD date on or before a lookback target.
    """

    target_date = (
        current_date
        - timedelta(days=calendar_days)
    )

    return latest_date_on_or_before(
        valid_dates,
        target_date,
    )


# ==========================================================
# POSITION CLASSIFICATION
# ==========================================================

def determine_current_bias(
    net_position: float,
    gross_exposure: float,
) -> str:
    """
    Determine current directional positioning.
    """

    if gross_exposure == 0:
        return "NEUTRAL"

    ratio = (
        net_position
        / gross_exposure
    )

    if ratio >= 0.25:
        return "STRONGLY BULLISH"

    if ratio >= 0.08:
        return "BULLISH"

    if ratio <= -0.25:
        return "STRONGLY BEARISH"

    if ratio <= -0.08:
        return "BEARISH"

    return "NEUTRAL"


def determine_behaviour(
    long_change: float | None,
    short_change: float | None,
    net_change: float | None,
) -> str:
    """
    Classify changes in Long and Short positions.
    """

    if (
        long_change is None
        or short_change is None
        or net_change is None
    ):
        return "INSUFFICIENT HISTORY"

    if long_change > 0 and short_change < 0:
        return "LONG ADDITION WITH SHORT COVERING"

    if long_change < 0 and short_change > 0:
        return "LONG REDUCTION WITH SHORT ADDITION"

    if long_change > 0 and short_change > 0:
        if net_change > 0:
            return "GROSS EXPANSION WITH BULLISH TILT"

        if net_change < 0:
            return "GROSS EXPANSION WITH BEARISH TILT"

        return "GROSS EXPANSION"

    if long_change < 0 and short_change < 0:
        if net_change > 0:
            return "POSITION REDUCTION WITH BULLISH TILT"

        if net_change < 0:
            return "POSITION REDUCTION WITH BEARISH TILT"

        return "POSITION REDUCTION"

    if long_change > 0:
        return "FRESH LONG ADDITION"

    if long_change < 0:
        return "LONG REDUCTION"

    if short_change > 0:
        return "FRESH SHORT ADDITION"

    if short_change < 0:
        return "SHORT COVERING"

    return "UNCHANGED"


def determine_directional_effect(
    net_change: float | None,
    current_gross: float,
) -> str:
    """
    Determine directional effect of the net-position change.
    """

    if net_change is None:
        return "INSUFFICIENT HISTORY"

    if current_gross == 0:
        return "NEUTRAL"

    ratio = (
        net_change
        / current_gross
    )

    if ratio >= 0.15:
        return "STRONGLY BULLISH"

    if ratio >= 0.04:
        return "BULLISH"

    if ratio <= -0.15:
        return "STRONGLY BEARISH"

    if ratio <= -0.04:
        return "BEARISH"

    return "NEUTRAL"


# ==========================================================
# PERIOD ANALYSIS
# ==========================================================

def build_empty_period_change() -> PeriodChange:
    """
    Return an insufficient-history period result.
    """

    return PeriodChange(
        comparison_date=None,
        long_change=None,
        long_change_percent=None,
        short_change=None,
        short_change_percent=None,
        net_change=None,
        net_change_percent=None,
        gross_change=None,
        gross_change_percent=None,
        behaviour="INSUFFICIENT HISTORY",
        directional_effect="INSUFFICIENT HISTORY",
    )


def analyse_period_change(
    *,
    current: ParticipantSnapshot,
    comparison: ParticipantSnapshot | None,
) -> PeriodChange:
    """
    Compare a current participant snapshot with another period.
    """

    if comparison is None:
        return build_empty_period_change()

    long_change = (
        current.long_position
        - comparison.long_position
    )

    short_change = (
        current.short_position
        - comparison.short_position
    )

    net_change = (
        current.net_position
        - comparison.net_position
    )

    gross_change = (
        current.gross_exposure
        - comparison.gross_exposure
    )

    behaviour = determine_behaviour(
        long_change=long_change,
        short_change=short_change,
        net_change=net_change,
    )

    directional_effect = determine_directional_effect(
        net_change=net_change,
        current_gross=current.gross_exposure,
    )

    return PeriodChange(
        comparison_date=comparison.trade_date,
        long_change=long_change,
        long_change_percent=safe_percentage(
            long_change,
            comparison.long_position,
        ),
        short_change=short_change,
        short_change_percent=safe_percentage(
            short_change,
            comparison.short_position,
        ),
        net_change=net_change,
        net_change_percent=safe_percentage(
            net_change,
            comparison.net_position,
        ),
        gross_change=gross_change,
        gross_change_percent=safe_percentage(
            gross_change,
            comparison.gross_exposure,
        ),
        behaviour=behaviour,
        directional_effect=directional_effect,
    )


# ==========================================================
# TREND ANALYSIS
# ==========================================================

def directional_score(
    directional_effect: str,
) -> int:
    """
    Convert a directional label into a signed score.
    """

    score_map = {
        "STRONGLY BULLISH": 2,
        "BULLISH": 1,
        "NEUTRAL": 0,
        "BEARISH": -1,
        "STRONGLY BEARISH": -2,
        "INSUFFICIENT HISTORY": 0,
    }

    return score_map.get(
        directional_effect,
        0,
    )


def determine_trend_consistency(
    daily: PeriodChange,
    weekly: PeriodChange,
    monthly: PeriodChange,
) -> str:
    """
    Determine whether daily, weekly and monthly changes agree.
    """

    available_effects = [
        period.directional_effect
        for period in (
            daily,
            weekly,
            monthly,
        )
        if period.directional_effect
        != "INSUFFICIENT HISTORY"
    ]

    if not available_effects:
        return "INSUFFICIENT HISTORY"

    scores = [
        directional_score(effect)
        for effect in available_effects
    ]

    bullish_count = sum(
        score > 0
        for score in scores
    )

    bearish_count = sum(
        score < 0
        for score in scores
    )

    if bullish_count == len(scores):
        return "CONSISTENTLY BULLISH"

    if bearish_count == len(scores):
        return "CONSISTENTLY BEARISH"

    if bullish_count > bearish_count:
        return "BULLISH WITH MIXED PERIODS"

    if bearish_count > bullish_count:
        return "BEARISH WITH MIXED PERIODS"

    return "MIXED"


def determine_positioning_state(
    current_bias: str,
    trend_consistency: str,
) -> str:
    """
    Combine current positioning and multi-period trend.
    """

    if (
        "BULLISH" in current_bias
        and "BULLISH" in trend_consistency
    ):
        return "BULLISH POSITIONING CONFIRMED"

    if (
        "BEARISH" in current_bias
        and "BEARISH" in trend_consistency
    ):
        return "BEARISH POSITIONING CONFIRMED"

    if (
        "BULLISH" in current_bias
        and "BEARISH" in trend_consistency
    ):
        return "BULLISH POSITION WITH DETERIORATING TREND"

    if (
        "BEARISH" in current_bias
        and "BULLISH" in trend_consistency
    ):
        return "BEARISH POSITION WITH IMPROVING TREND"

    if current_bias == "NEUTRAL":
        return "NEUTRAL POSITIONING"

    return "MIXED POSITIONING"


# ==========================================================
# CONVICTION
# ==========================================================

def calculate_conviction(
    *,
    current: ParticipantSnapshot,
    daily: PeriodChange,
    weekly: PeriodChange,
    monthly: PeriodChange,
    trend_consistency: str,
) -> int:
    """
    Calculate an explainable conviction score from 0 to 100.
    """

    if current.gross_exposure == 0:
        return 0

    score = 25

    current_net_strength = abs(
        current.net_position
        / current.gross_exposure
    )

    score += int(
        min(current_net_strength, 1.0)
        * 30
    )

    for period in (
        daily,
        weekly,
        monthly,
    ):
        if period.net_change is None:
            continue

        period_strength = abs(
            period.net_change
            / current.gross_exposure
        )

        score += int(
            min(period_strength, 0.25)
            * 40
        )

    if trend_consistency in {
        "CONSISTENTLY BULLISH",
        "CONSISTENTLY BEARISH",
    }:
        score += 15

    elif trend_consistency in {
        "BULLISH WITH MIXED PERIODS",
        "BEARISH WITH MIXED PERIODS",
    }:
        score += 7

    return max(
        0,
        min(score, 100),
    )


# ==========================================================
# INTERPRETATION
# ==========================================================

def build_interpretation(
    *,
    participant: str,
    current: ParticipantSnapshot,
    daily: PeriodChange,
    weekly: PeriodChange,
    monthly: PeriodChange,
    trend_consistency: str,
    positioning_state: str,
) -> str:
    """
    Build a readable multi-period interpretation.
    """

    return (
        f"{participant} currently holds "
        f"{current.long_percentage:.2f}% Long and "
        f"{current.short_percentage:.2f}% Short exposure, "
        f"with a net position of {current.net_position:+,.0f}. "
        f"Daily net change is "
        f"{format_optional_number(daily.net_change)}, "
        f"weekly net change is "
        f"{format_optional_number(weekly.net_change)}, and "
        f"monthly net change is "
        f"{format_optional_number(monthly.net_change)}. "
        f"The multi-period trend is "
        f"{trend_consistency.lower()}. "
        f"Overall positioning is classified as "
        f"{positioning_state.lower()}."
    )


# ==========================================================
# PARTICIPANT ANALYSIS
# ==========================================================

def load_optional_snapshot(
    *,
    database: AQSDDatabase,
    comparison_date: date | None,
    participant: str,
) -> ParticipantSnapshot | None:
    """
    Load a participant snapshot when a comparison date exists.
    """

    if comparison_date is None:
        return None

    return load_index_futures_snapshot(
        database=database,
        trade_date=comparison_date,
        participant=participant,
    )


def analyse_participant(
    *,
    database: AQSDDatabase,
    participant: str,
    current_date: date,
    previous_date: date | None,
    weekly_date: date | None,
    monthly_date: date | None,
) -> ParticipantHistoricalIntelligence:
    """
    Run multi-period analysis for one participant.
    """

    current = load_index_futures_snapshot(
        database=database,
        trade_date=current_date,
        participant=participant,
    )

    previous = load_optional_snapshot(
        database=database,
        comparison_date=previous_date,
        participant=participant,
    )

    weekly_snapshot = load_optional_snapshot(
        database=database,
        comparison_date=weekly_date,
        participant=participant,
    )

    monthly_snapshot = load_optional_snapshot(
        database=database,
        comparison_date=monthly_date,
        participant=participant,
    )

    daily = analyse_period_change(
        current=current,
        comparison=previous,
    )

    weekly = analyse_period_change(
        current=current,
        comparison=weekly_snapshot,
    )

    monthly = analyse_period_change(
        current=current,
        comparison=monthly_snapshot,
    )

    trend_consistency = determine_trend_consistency(
        daily=daily,
        weekly=weekly,
        monthly=monthly,
    )

    current_bias = determine_current_bias(
        net_position=current.net_position,
        gross_exposure=current.gross_exposure,
    )

    positioning_state = determine_positioning_state(
        current_bias=current_bias,
        trend_consistency=trend_consistency,
    )

    conviction_score = calculate_conviction(
        current=current,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        trend_consistency=trend_consistency,
    )

    interpretation = build_interpretation(
        participant=participant,
        current=current,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        trend_consistency=trend_consistency,
        positioning_state=positioning_state,
    )

    return ParticipantHistoricalIntelligence(
        participant=participant,
        current_date=current_date,
        current_long=current.long_position,
        current_short=current.short_position,
        current_net=current.net_position,
        current_gross=current.gross_exposure,
        current_long_percentage=current.long_percentage,
        current_short_percentage=current.short_percentage,
        current_bias=current_bias,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        trend_consistency=trend_consistency,
        positioning_state=positioning_state,
        conviction_score=conviction_score,
        interpretation=interpretation,
    )


# ==========================================================
# INSTITUTIONAL SUMMARY
# ==========================================================

def sum_optional_values(
    values: list[float | None],
) -> float | None:
    """
    Sum optional values when at least one value exists.
    """

    available_values = [
        value
        for value in values
        if value is not None
    ]

    if not available_values:
        return None

    return sum(available_values)


def determine_institutional_alignment(
    participant_results: tuple[
        ParticipantHistoricalIntelligence,
        ...,
    ],
) -> str:
    """
    Determine alignment among FII, PRO and DII.
    """

    institutional_results = [
        item
        for item in participant_results
        if item.participant
        in INSTITUTIONAL_PARTICIPANTS
    ]

    bullish_count = sum(
        "BULLISH" in item.current_bias
        for item in institutional_results
    )

    bearish_count = sum(
        "BEARISH" in item.current_bias
        for item in institutional_results
    )

    if bullish_count == len(institutional_results):
        return "FULL BULLISH ALIGNMENT"

    if bearish_count == len(institutional_results):
        return "FULL BEARISH ALIGNMENT"

    if bullish_count >= 2:
        return "MAJORITY BULLISH ALIGNMENT"

    if bearish_count >= 2:
        return "MAJORITY BEARISH ALIGNMENT"

    return "MIXED INSTITUTIONAL ALIGNMENT"


def determine_institutional_trend(
    daily_change: float | None,
    weekly_change: float | None,
    monthly_change: float | None,
) -> str:
    """
    Determine the combined institutional multi-period trend.
    """

    changes = [
        value
        for value in (
            daily_change,
            weekly_change,
            monthly_change,
        )
        if value is not None
    ]

    if not changes:
        return "INSUFFICIENT HISTORY"

    positive_count = sum(
        value > 0
        for value in changes
    )

    negative_count = sum(
        value < 0
        for value in changes
    )

    if positive_count == len(changes):
        return "CONSISTENTLY IMPROVING"

    if negative_count == len(changes):
        return "CONSISTENTLY DETERIORATING"

    if positive_count > negative_count:
        return "IMPROVING WITH MIXED PERIODS"

    if negative_count > positive_count:
        return "DETERIORATING WITH MIXED PERIODS"

    return "MIXED"


def calculate_overall_conviction(
    participant_results: tuple[
        ParticipantHistoricalIntelligence,
        ...,
    ],
) -> int:
    """
    Average conviction for FII, PRO and DII.
    """

    scores = [
        item.conviction_score
        for item in participant_results
        if item.participant
        in INSTITUTIONAL_PARTICIPANTS
    ]

    if not scores:
        return 0

    return round(
        sum(scores)
        / len(scores)
    )


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_historical_change_engine(
    requested_date: date,
) -> ParticipantHistoricalResult:
    """
    Run APD-009 for the latest valid date on or before
    the requested date.
    """

    if not APD_DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"APD database not found: {APD_DATABASE_FILE}"
        )

    with AQSDDatabase(
        database_file=APD_DATABASE_FILE
    ) as database:
        valid_dates = get_valid_apd_dates(
            database=database,
            requested_date=requested_date,
        )

        if not valid_dates:
            raise RuntimeError(
                "No valid weekday APD dates are available "
                "on or before the requested date."
            )

        current_date = max(valid_dates)

        previous_date = previous_available_date(
            valid_dates=valid_dates,
            current_date=current_date,
        )

        weekly_date = comparison_date_for_lookback(
            valid_dates=valid_dates,
            current_date=current_date,
            calendar_days=WEEK_LOOKBACK_CALENDAR_DAYS,
        )

        monthly_date = comparison_date_for_lookback(
            valid_dates=valid_dates,
            current_date=current_date,
            calendar_days=MONTH_LOOKBACK_CALENDAR_DAYS,
        )

        participant_results = tuple(
            analyse_participant(
                database=database,
                participant=participant,
                current_date=current_date,
                previous_date=previous_date,
                weekly_date=weekly_date,
                monthly_date=monthly_date,
            )
            for participant in PARTICIPANTS
        )

    institutional_results = [
        item
        for item in participant_results
        if item.participant
        in INSTITUTIONAL_PARTICIPANTS
    ]

    institutional_current_net = sum(
        item.current_net
        for item in institutional_results
    )

    institutional_daily_net_change = sum_optional_values(
        [
            item.daily.net_change
            for item in institutional_results
        ]
    )

    institutional_weekly_net_change = sum_optional_values(
        [
            item.weekly.net_change
            for item in institutional_results
        ]
    )

    institutional_monthly_net_change = sum_optional_values(
        [
            item.monthly.net_change
            for item in institutional_results
        ]
    )

    institutional_current_gross = sum(
        item.current_gross
        for item in institutional_results
    )

    institutional_bias = determine_current_bias(
        net_position=institutional_current_net,
        gross_exposure=institutional_current_gross,
    )

    institutional_trend = determine_institutional_trend(
        daily_change=institutional_daily_net_change,
        weekly_change=institutional_weekly_net_change,
        monthly_change=institutional_monthly_net_change,
    )

    institutional_alignment = determine_institutional_alignment(
        participant_results
    )

    overall_conviction = calculate_overall_conviction(
        participant_results
    )

    return ParticipantHistoricalResult(
        requested_date=requested_date,
        current_date=current_date,
        previous_date=previous_date,
        weekly_reference_date=weekly_date,
        monthly_reference_date=monthly_date,
        participant_results=participant_results,
        institutional_current_net=institutional_current_net,
        institutional_daily_net_change=
            institutional_daily_net_change,
        institutional_weekly_net_change=
            institutional_weekly_net_change,
        institutional_monthly_net_change=
            institutional_monthly_net_change,
        institutional_bias=institutional_bias,
        institutional_trend=institutional_trend,
        institutional_alignment=institutional_alignment,
        overall_conviction=overall_conviction,
        status="SUCCESS",
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_period(
    title: str,
    period: PeriodChange,
) -> None:
    """
    Print one comparison period.
    """

    print(f"{title} Reference          : {period.comparison_date}")
    print(
        f"{title} Long Change        : "
        f"{format_optional_number(period.long_change)} "
        f"({format_optional_percentage(period.long_change_percent)})"
    )
    print(
        f"{title} Short Change       : "
        f"{format_optional_number(period.short_change)} "
        f"({format_optional_percentage(period.short_change_percent)})"
    )
    print(
        f"{title} Net Change         : "
        f"{format_optional_number(period.net_change)} "
        f"({format_optional_percentage(period.net_change_percent)})"
    )
    print(
        f"{title} Gross Change       : "
        f"{format_optional_number(period.gross_change)} "
        f"({format_optional_percentage(period.gross_change_percent)})"
    )
    print(f"{title} Behaviour          : {period.behaviour}")
    print(
        f"{title} Directional Effect : "
        f"{period.directional_effect}"
    )


def display_result(
    result: ParticipantHistoricalResult,
) -> None:
    """
    Display the APD-009 terminal report.
    """

    print()
    print("=" * 92)
    print("AQSD PARTICIPANT HISTORICAL CHANGE ENGINE")
    print("=" * 92)
    print(f"Module                    : {MODULE_ID}")
    print(f"Version                   : {MODULE_VERSION}")
    print(f"Requested Date            : {result.requested_date}")
    print(f"Current Valid APD Date    : {result.current_date}")
    print(f"Previous Date             : {result.previous_date}")
    print(f"Weekly Reference Date     : {result.weekly_reference_date}")
    print(f"Monthly Reference Date    : {result.monthly_reference_date}")
    print("=" * 92)

    for item in result.participant_results:
        print()
        print(f"PARTICIPANT               : {item.participant}")
        print("-" * 92)
        print(f"Current Long              : {item.current_long:,.0f}")
        print(f"Current Short             : {item.current_short:,.0f}")
        print(f"Current Net               : {item.current_net:+,.0f}")
        print(f"Current Gross             : {item.current_gross:,.0f}")
        print(
            f"Long / Short %            : "
            f"{item.current_long_percentage:.2f}% / "
            f"{item.current_short_percentage:.2f}%"
        )
        print(f"Current Bias              : {item.current_bias}")
        print("-" * 92)

        display_period(
            "Daily",
            item.daily,
        )

        print("-" * 92)

        display_period(
            "Weekly",
            item.weekly,
        )

        print("-" * 92)

        display_period(
            "Monthly",
            item.monthly,
        )

        print("-" * 92)
        print(
            f"Trend Consistency         : "
            f"{item.trend_consistency}"
        )
        print(
            f"Positioning State         : "
            f"{item.positioning_state}"
        )
        print(
            f"Conviction                : "
            f"{item.conviction_score}%"
        )
        print(
            f"Interpretation            : "
            f"{item.interpretation}"
        )
        print("=" * 92)

    print()
    print("INSTITUTIONAL SUMMARY")
    print("-" * 92)
    print(
        f"Current Institutional Net : "
        f"{result.institutional_current_net:+,.0f}"
    )
    print(
        f"Daily Institutional Change: "
        f"{format_optional_number(result.institutional_daily_net_change)}"
    )
    print(
        f"Weekly Institutional Chg  : "
        f"{format_optional_number(result.institutional_weekly_net_change)}"
    )
    print(
        f"Monthly Institutional Chg : "
        f"{format_optional_number(result.institutional_monthly_net_change)}"
    )
    print(
        f"Institutional Bias        : "
        f"{result.institutional_bias}"
    )
    print(
        f"Institutional Trend       : "
        f"{result.institutional_trend}"
    )
    print(
        f"Institutional Alignment   : "
        f"{result.institutional_alignment}"
    )
    print(
        f"Overall Conviction        : "
        f"{result.overall_conviction}%"
    )
    print(f"Status                    : {result.status}")
    print("=" * 92)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Analyse participant Index Futures positions across "
            "daily, weekly and monthly comparison periods."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Requested analysis date in YYYY-MM-DD format.",
    )

    return parser.parse_args()


def parse_date(
    value: str,
) -> date:
    """
    Convert YYYY-MM-DD text into a date.
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


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = run_historical_change_engine(
            parse_date(arguments.date)
        )

    except Exception as exc:
        print()
        print("=" * 92)
        print("AQSD PARTICIPANT HISTORICAL CHANGE ENGINE")
        print("=" * 92)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 92)
        raise SystemExit(1) from exc

    display_result(result)


if __name__ == "__main__":
    main()