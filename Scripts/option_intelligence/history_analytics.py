"""
AQSD
OPTION INTELLIGENCE HISTORY ANALYTICS

Module: history_analytics.py
Version: 1.0
Author: AQSD

Purpose:
Analyze the intraday Option Intelligence history stored in SQLite.

Database:
Output/Database/AQSD_Option_Intelligence.db

Outputs:
Output/HISTORY_ANALYTICS/BANKNIFTY_HISTORY_ANALYTICS.json

Analytics:
- PCR trend over 5, 15 and 30 minutes
- IV expansion or contraction
- Max Pain migration
- Call Wall and Put Wall movement
- Bullish and bearish probability trend
- Confidence trend
- Spot trend
- Compact market-development commentary
- Data-quality and sample-count checks

Examples:
    python -m Scripts.option_intelligence.history_analytics
    python -m Scripts.option_intelligence.history_analytics --minutes 60
    python -m Scripts.option_intelligence.history_analytics --show
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    BASE_DIR
    / "Output"
    / "Database"
    / "AQSD_Option_Intelligence.db"
)

OUTPUT_DIR = (
    BASE_DIR
    / "Output"
    / "HISTORY_ANALYTICS"
)

OUTPUT_JSON_FILE = (
    OUTPUT_DIR
    / "BANKNIFTY_HISTORY_ANALYTICS.json"
)

TABLE_NAME = "option_intelligence_history"


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_LOOKBACK_MINUTES = 180

TREND_WINDOWS_MINUTES = (
    5,
    15,
    30,
)

MINIMUM_WINDOW_SAMPLES = 2

PCR_FLAT_THRESHOLD = 0.02
IV_FLAT_THRESHOLD = 0.25
PROBABILITY_FLAT_THRESHOLD = 2.0
CONFIDENCE_FLAT_THRESHOLD = 2.0
SPOT_FLAT_THRESHOLD_PERCENT = 0.05

WALL_UNCHANGED_THRESHOLD = 0.0
MAX_PAIN_UNCHANGED_THRESHOLD = 0.0


# ============================================================
# DATA MODELS
# ============================================================

@dataclass(frozen=True)
class HistoryPoint:
    """One normalized database history row."""

    id: int
    timestamp: datetime
    source_timestamp: str

    spot_price: float | None
    atm_strike: float | None

    oi_pcr: float | None
    change_oi_pcr: float | None
    modified_pcr: float | None
    volume_pcr: float | None
    atm_zone_pcr: float | None

    max_pain_strike: float | None
    call_wall: float | None
    put_wall: float | None
    fresh_call_wall: float | None
    fresh_put_wall: float | None

    atm_iv: float | None
    historical_volatility: float | None
    iv_rank: float | None
    iv_percentile: float | None

    bullish_probability: float | None
    bearish_probability: float | None
    continuation_probability: float | None
    reversal_probability: float | None

    confidence_score: float | None

    final_decision: str | None
    decision_bias: str | None
    market_regime: str | None
    volatility_regime: str | None


@dataclass(frozen=True)
class MetricTrend:
    """Trend summary for one metric and one time window."""

    metric: str
    window_minutes: int
    sample_count: int

    start_value: float | None
    latest_value: float | None
    minimum_value: float | None
    maximum_value: float | None
    average_value: float | None

    absolute_change: float | None
    percentage_change: float | None
    change_per_minute: float | None

    direction: str
    strength: str
    interpretation: str


@dataclass(frozen=True)
class LevelMovement:
    """Movement summary for a discrete strike or wall level."""

    metric: str
    window_minutes: int
    sample_count: int

    start_level: float | None
    latest_level: float | None
    absolute_change: float | None

    direction: str
    number_of_changes: int
    interpretation: str


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_local() -> datetime:
    """Return the current local timezone-aware datetime."""

    return datetime.now().astimezone()


def parse_timestamp(
    value: Any,
) -> datetime | None:
    """Parse common ISO and database timestamp formats safely."""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    normalized = text.replace(
        "Z",
        "+00:00",
    )

    try:
        result = datetime.fromisoformat(
            normalized
        )

        if result.tzinfo is None:
            result = result.astimezone()

        return result

    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    )

    for date_format in formats:
        try:
            result = datetime.strptime(
                text,
                date_format,
            )

            return result.astimezone()

        except ValueError:
            continue

    return None


def to_float(
    value: Any,
) -> float | None:
    """Convert a value to a finite float safely."""

    if value is None:
        return None

    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        result
    ):
        return None

    return result


def percentage_change(
    start: float | None,
    end: float | None,
) -> float | None:
    """Calculate percentage change safely."""

    if (
        start is None
        or end is None
        or start == 0
    ):
        return None

    return (
        (end - start)
        / abs(start)
        * 100.0
    )


def round_optional(
    value: float | None,
    digits: int = 4,
) -> float | None:
    """Round an optional number."""

    if value is None:
        return None

    return round(
        float(value),
        digits,
    )


def clean_text(
    value: Any,
) -> str | None:
    """Return stripped optional text."""

    if value is None:
        return None

    text = str(value).strip()

    return text or None


# ============================================================
# DATABASE
# ============================================================

def connect_database() -> sqlite3.Connection:
    """Open the AQSD history database."""

    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            "AQSD history database was not found:\n"
            f"{DATABASE_FILE}\n\n"
            "Run the live pipeline first so at least one history "
            "snapshot is stored."
        )

    connection = sqlite3.connect(
        DATABASE_FILE,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


def verify_history_table(
    connection: sqlite3.Connection,
) -> None:
    """Confirm that the expected history table exists."""

    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (
            TABLE_NAME,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"Required table '{TABLE_NAME}' does not exist."
        )


def load_history_points(
    connection: sqlite3.Connection,
    lookback_minutes: int,
) -> list[HistoryPoint]:
    """
    Load recent history rows.

    Filtering is performed in Python because source timestamps may contain
    different ISO timezone formats.
    """

    rows = connection.execute(
        f"""
        SELECT
            id,
            source_timestamp,
            recorded_at,

            spot_price,
            atm_strike,

            oi_pcr,
            change_oi_pcr,
            modified_pcr,
            volume_pcr,
            atm_zone_pcr,

            max_pain_strike,
            call_wall,
            put_wall,
            fresh_call_wall,
            fresh_put_wall,

            atm_iv,
            historical_volatility,
            iv_rank,
            iv_percentile,

            bullish_probability,
            bearish_probability,
            continuation_probability,
            reversal_probability,

            confidence_score,

            final_decision,
            decision_bias,
            market_regime,
            volatility_regime

        FROM {TABLE_NAME}
        ORDER BY id ASC
        """
    ).fetchall()

    cutoff = (
        now_local()
        - timedelta(
            minutes=lookback_minutes
        )
    )

    points: list[HistoryPoint] = []

    for row in rows:
        timestamp = (
            parse_timestamp(
                row["recorded_at"]
            )
            or parse_timestamp(
                row["source_timestamp"]
            )
        )

        if timestamp is None:
            continue

        if timestamp < cutoff:
            continue

        points.append(
            HistoryPoint(
                id=int(row["id"]),
                timestamp=timestamp,
                source_timestamp=str(
                    row["source_timestamp"]
                ),

                spot_price=to_float(
                    row["spot_price"]
                ),
                atm_strike=to_float(
                    row["atm_strike"]
                ),

                oi_pcr=to_float(
                    row["oi_pcr"]
                ),
                change_oi_pcr=to_float(
                    row["change_oi_pcr"]
                ),
                modified_pcr=to_float(
                    row["modified_pcr"]
                ),
                volume_pcr=to_float(
                    row["volume_pcr"]
                ),
                atm_zone_pcr=to_float(
                    row["atm_zone_pcr"]
                ),

                max_pain_strike=to_float(
                    row["max_pain_strike"]
                ),
                call_wall=to_float(
                    row["call_wall"]
                ),
                put_wall=to_float(
                    row["put_wall"]
                ),
                fresh_call_wall=to_float(
                    row["fresh_call_wall"]
                ),
                fresh_put_wall=to_float(
                    row["fresh_put_wall"]
                ),

                atm_iv=to_float(
                    row["atm_iv"]
                ),
                historical_volatility=to_float(
                    row["historical_volatility"]
                ),
                iv_rank=to_float(
                    row["iv_rank"]
                ),
                iv_percentile=to_float(
                    row["iv_percentile"]
                ),

                bullish_probability=to_float(
                    row["bullish_probability"]
                ),
                bearish_probability=to_float(
                    row["bearish_probability"]
                ),
                continuation_probability=to_float(
                    row["continuation_probability"]
                ),
                reversal_probability=to_float(
                    row["reversal_probability"]
                ),

                confidence_score=to_float(
                    row["confidence_score"]
                ),

                final_decision=clean_text(
                    row["final_decision"]
                ),
                decision_bias=clean_text(
                    row["decision_bias"]
                ),
                market_regime=clean_text(
                    row["market_regime"]
                ),
                volatility_regime=clean_text(
                    row["volatility_regime"]
                ),
            )
        )

    return points


# ============================================================
# WINDOW HELPERS
# ============================================================

def points_in_window(
    points: Sequence[HistoryPoint],
    window_minutes: int,
) -> list[HistoryPoint]:
    """Return points within a trailing time window."""

    if not points:
        return []

    latest_time = points[-1].timestamp

    cutoff = (
        latest_time
        - timedelta(
            minutes=window_minutes
        )
    )

    return [
        point
        for point in points
        if point.timestamp >= cutoff
    ]


def metric_values(
    points: Iterable[HistoryPoint],
    attribute_name: str,
) -> list[tuple[datetime, float]]:
    """Return valid timestamp/value pairs for a metric."""

    values: list[tuple[datetime, float]] = []

    for point in points:
        value = to_float(
            getattr(
                point,
                attribute_name,
                None,
            )
        )

        if value is not None:
            values.append(
                (
                    point.timestamp,
                    value,
                )
            )

    return values


# ============================================================
# TREND LOGIC
# ============================================================

def threshold_for_metric(
    metric: str,
) -> float:
    """Return the flat/noise threshold for a metric."""

    thresholds = {
        "spot_price": 0.0,
        "oi_pcr": PCR_FLAT_THRESHOLD,
        "change_oi_pcr": PCR_FLAT_THRESHOLD,
        "modified_pcr": PCR_FLAT_THRESHOLD,
        "volume_pcr": PCR_FLAT_THRESHOLD,
        "atm_zone_pcr": PCR_FLAT_THRESHOLD,
        "atm_iv": IV_FLAT_THRESHOLD,
        "historical_volatility": IV_FLAT_THRESHOLD,
        "iv_rank": IV_FLAT_THRESHOLD,
        "iv_percentile": IV_FLAT_THRESHOLD,
        "bullish_probability": PROBABILITY_FLAT_THRESHOLD,
        "bearish_probability": PROBABILITY_FLAT_THRESHOLD,
        "continuation_probability": PROBABILITY_FLAT_THRESHOLD,
        "reversal_probability": PROBABILITY_FLAT_THRESHOLD,
        "confidence_score": CONFIDENCE_FLAT_THRESHOLD,
    }

    return thresholds.get(
        metric,
        0.0,
    )


def metric_label(
    metric: str,
) -> str:
    """Return a readable metric label."""

    labels = {
        "spot_price": "Spot",
        "oi_pcr": "OI PCR",
        "change_oi_pcr": "Change-OI PCR",
        "modified_pcr": "Modified PCR",
        "volume_pcr": "Volume PCR",
        "atm_zone_pcr": "ATM-Zone PCR",
        "atm_iv": "ATM IV",
        "historical_volatility": "Historical Volatility",
        "iv_rank": "IV Rank",
        "iv_percentile": "IV Percentile",
        "bullish_probability": "Bullish Probability",
        "bearish_probability": "Bearish Probability",
        "continuation_probability": "Continuation Probability",
        "reversal_probability": "Reversal Probability",
        "confidence_score": "Confidence",
    }

    return labels.get(
        metric,
        metric.replace(
            "_",
            " ",
        ).title(),
    )


def classify_strength(
    absolute_change: float,
    threshold: float,
) -> str:
    """Classify trend strength relative to the flat threshold."""

    magnitude = abs(
        absolute_change
    )

    if threshold <= 0:
        if magnitude == 0:
            return "FLAT"

        return "ACTIVE"

    ratio = magnitude / threshold

    if ratio < 1:
        return "FLAT"

    if ratio < 2:
        return "MILD"

    if ratio < 4:
        return "MODERATE"

    return "STRONG"


def analyze_metric_trend(
    points: Sequence[HistoryPoint],
    metric: str,
    window_minutes: int,
) -> MetricTrend:
    """Analyze one continuous metric over one trailing window."""

    window_points = points_in_window(
        points,
        window_minutes,
    )

    values = metric_values(
        window_points,
        metric,
    )

    label = metric_label(
        metric
    )

    if len(values) < MINIMUM_WINDOW_SAMPLES:
        return MetricTrend(
            metric=metric,
            window_minutes=window_minutes,
            sample_count=len(values),

            start_value=None,
            latest_value=(
                values[-1][1]
                if values
                else None
            ),
            minimum_value=None,
            maximum_value=None,
            average_value=None,

            absolute_change=None,
            percentage_change=None,
            change_per_minute=None,

            direction="INSUFFICIENT DATA",
            strength="INSUFFICIENT DATA",
            interpretation=(
                f"{label}: fewer than "
                f"{MINIMUM_WINDOW_SAMPLES} valid samples "
                f"in the last {window_minutes} minutes."
            ),
        )

    start_time, start_value = values[0]
    end_time, latest_value = values[-1]

    absolute_change = (
        latest_value
        - start_value
    )

    elapsed_minutes = max(
        (
            end_time
            - start_time
        ).total_seconds()
        / 60.0,
        0.0001,
    )

    change_per_minute = (
        absolute_change
        / elapsed_minutes
    )

    threshold = threshold_for_metric(
        metric
    )

    if metric == "spot_price":
        pct_change = percentage_change(
            start_value,
            latest_value,
        )

        if pct_change is None:
            direction = "FLAT"
        elif pct_change > SPOT_FLAT_THRESHOLD_PERCENT:
            direction = "RISING"
        elif pct_change < -SPOT_FLAT_THRESHOLD_PERCENT:
            direction = "FALLING"
        else:
            direction = "FLAT"

        strength = classify_strength(
            pct_change or 0.0,
            SPOT_FLAT_THRESHOLD_PERCENT,
        )

    else:
        pct_change = percentage_change(
            start_value,
            latest_value,
        )

        if absolute_change > threshold:
            direction = "RISING"
        elif absolute_change < -threshold:
            direction = "FALLING"
        else:
            direction = "FLAT"

        strength = classify_strength(
            absolute_change,
            threshold,
        )

    interpretation = build_metric_interpretation(
        metric=metric,
        direction=direction,
        strength=strength,
        window_minutes=window_minutes,
        start_value=start_value,
        latest_value=latest_value,
        absolute_change=absolute_change,
        percentage_change_value=pct_change,
    )

    numeric_values = [
        value
        for _, value in values
    ]

    return MetricTrend(
        metric=metric,
        window_minutes=window_minutes,
        sample_count=len(values),

        start_value=round_optional(
            start_value
        ),
        latest_value=round_optional(
            latest_value
        ),
        minimum_value=round_optional(
            min(numeric_values)
        ),
        maximum_value=round_optional(
            max(numeric_values)
        ),
        average_value=round_optional(
            mean(numeric_values)
        ),

        absolute_change=round_optional(
            absolute_change
        ),
        percentage_change=round_optional(
            pct_change
        ),
        change_per_minute=round_optional(
            change_per_minute
        ),

        direction=direction,
        strength=strength,
        interpretation=interpretation,
    )


def build_metric_interpretation(
    *,
    metric: str,
    direction: str,
    strength: str,
    window_minutes: int,
    start_value: float,
    latest_value: float,
    absolute_change: float,
    percentage_change_value: float | None,
) -> str:
    """Create concise readable commentary for a metric trend."""

    label = metric_label(
        metric
    )

    if direction == "FLAT":
        return (
            f"{label} is broadly stable over the last "
            f"{window_minutes} minutes "
            f"({start_value:.3f} to {latest_value:.3f})."
        )

    movement_word = (
        "increased"
        if direction == "RISING"
        else "decreased"
    )

    if metric == "spot_price":
        pct_text = (
            f", {percentage_change_value:+.2f}%"
            if percentage_change_value is not None
            else ""
        )

        return (
            f"{label} {movement_word} from "
            f"{start_value:.2f} to {latest_value:.2f} "
            f"over {window_minutes} minutes "
            f"({absolute_change:+.2f}{pct_text}); "
            f"trend strength is {strength.lower()}."
        )

    return (
        f"{label} {movement_word} from "
        f"{start_value:.3f} to {latest_value:.3f} "
        f"over {window_minutes} minutes "
        f"({absolute_change:+.3f}); "
        f"trend strength is {strength.lower()}."
    )


# ============================================================
# DISCRETE LEVEL MOVEMENT
# ============================================================

def analyze_level_movement(
    points: Sequence[HistoryPoint],
    metric: str,
    window_minutes: int,
) -> LevelMovement:
    """Analyze movement of Max Pain or option wall strikes."""

    window_points = points_in_window(
        points,
        window_minutes,
    )

    values = metric_values(
        window_points,
        metric,
    )

    label = metric_label(
        metric
    )

    if len(values) < MINIMUM_WINDOW_SAMPLES:
        return LevelMovement(
            metric=metric,
            window_minutes=window_minutes,
            sample_count=len(values),
            start_level=None,
            latest_level=(
                values[-1][1]
                if values
                else None
            ),
            absolute_change=None,
            direction="INSUFFICIENT DATA",
            number_of_changes=0,
            interpretation=(
                f"{label}: insufficient observations in the last "
                f"{window_minutes} minutes."
            ),
        )

    levels = [
        value
        for _, value in values
    ]

    start_level = levels[0]
    latest_level = levels[-1]

    absolute_change = (
        latest_level
        - start_level
    )

    number_of_changes = sum(
        1
        for previous, current in zip(
            levels,
            levels[1:],
        )
        if current != previous
    )

    if absolute_change > WALL_UNCHANGED_THRESHOLD:
        direction = "SHIFTED UP"
    elif absolute_change < -WALL_UNCHANGED_THRESHOLD:
        direction = "SHIFTED DOWN"
    else:
        direction = "UNCHANGED"

    if direction == "UNCHANGED":
        interpretation = (
            f"{label} remained at {latest_level:.0f} over the last "
            f"{window_minutes} minutes."
        )
    else:
        interpretation = (
            f"{label} {direction.lower()} from {start_level:.0f} "
            f"to {latest_level:.0f} over the last "
            f"{window_minutes} minutes "
            f"({absolute_change:+.0f}); "
            f"{number_of_changes} level change(s) were observed."
        )

    return LevelMovement(
        metric=metric,
        window_minutes=window_minutes,
        sample_count=len(values),
        start_level=round_optional(
            start_level,
            2,
        ),
        latest_level=round_optional(
            latest_level,
            2,
        ),
        absolute_change=round_optional(
            absolute_change,
            2,
        ),
        direction=direction,
        number_of_changes=number_of_changes,
        interpretation=interpretation,
    )


# ============================================================
# COMPOSITE MARKET LOGIC
# ============================================================

def latest_value(
    points: Sequence[HistoryPoint],
    attribute_name: str,
) -> Any:
    """Return the latest non-null attribute value."""

    for point in reversed(
        points
    ):
        value = getattr(
            point,
            attribute_name,
            None,
        )

        if value is not None:
            return value

    return None


def trend_lookup(
    trends: dict[str, dict[str, Any]],
    metric: str,
    window_minutes: int,
) -> dict[str, Any] | None:
    """Get one serialized metric trend."""

    return trends.get(
        metric,
        {},
    ).get(
        str(window_minutes)
    )


def build_market_commentary(
    *,
    points: Sequence[HistoryPoint],
    metric_trends: dict[str, dict[str, Any]],
    level_movements: dict[str, dict[str, Any]],
) -> list[str]:
    """Create compact market-development observations."""

    commentary: list[str] = []

    pcr_15 = trend_lookup(
        metric_trends,
        "modified_pcr",
        15,
    )

    iv_15 = trend_lookup(
        metric_trends,
        "atm_iv",
        15,
    )

    spot_15 = trend_lookup(
        metric_trends,
        "spot_price",
        15,
    )

    bullish_15 = trend_lookup(
        metric_trends,
        "bullish_probability",
        15,
    )

    bearish_15 = trend_lookup(
        metric_trends,
        "bearish_probability",
        15,
    )

    confidence_15 = trend_lookup(
        metric_trends,
        "confidence_score",
        15,
    )

    call_wall_30 = (
        level_movements
        .get(
            "call_wall",
            {},
        )
        .get(
            "30"
        )
    )

    put_wall_30 = (
        level_movements
        .get(
            "put_wall",
            {},
        )
        .get(
            "30"
        )
    )

    max_pain_30 = (
        level_movements
        .get(
            "max_pain_strike",
            {},
        )
        .get(
            "30"
        )
    )

    if (
        pcr_15
        and pcr_15["direction"]
        not in {
            "INSUFFICIENT DATA",
            "FLAT",
        }
    ):
        commentary.append(
            pcr_15["interpretation"]
        )

    if (
        iv_15
        and iv_15["direction"] == "RISING"
    ):
        commentary.append(
            "ATM IV is expanding, indicating that option premiums "
            "and expected movement are increasing."
        )
    elif (
        iv_15
        and iv_15["direction"] == "FALLING"
    ):
        commentary.append(
            "ATM IV is contracting, indicating declining option "
            "premium intensity."
        )

    if (
        spot_15
        and bullish_15
        and spot_15["direction"] == "RISING"
        and bullish_15["direction"] == "RISING"
    ):
        commentary.append(
            "Spot and bullish probability are rising together, "
            "which supports improving bullish confirmation."
        )

    if (
        spot_15
        and bearish_15
        and spot_15["direction"] == "FALLING"
        and bearish_15["direction"] == "RISING"
    ):
        commentary.append(
            "Spot is falling while bearish probability is rising, "
            "which supports improving bearish confirmation."
        )

    if (
        confidence_15
        and confidence_15["direction"] == "RISING"
    ):
        commentary.append(
            "Decision confidence is strengthening over the last "
            "15 minutes."
        )
    elif (
        confidence_15
        and confidence_15["direction"] == "FALLING"
    ):
        commentary.append(
            "Decision confidence is weakening over the last "
            "15 minutes."
        )

    for movement in (
        call_wall_30,
        put_wall_30,
        max_pain_30,
    ):
        if (
            movement
            and movement["direction"]
            not in {
                "INSUFFICIENT DATA",
                "UNCHANGED",
            }
        ):
            commentary.append(
                movement["interpretation"]
            )

    latest_decision = latest_value(
        points,
        "final_decision",
    )

    latest_regime = latest_value(
        points,
        "market_regime",
    )

    if latest_decision:
        statement = (
            f"Latest AQSD decision is {latest_decision}"
        )

        if latest_regime:
            statement += (
                f" in a {latest_regime} market regime"
            )

        commentary.append(
            statement + "."
        )

    if not commentary:
        commentary.append(
            "History is available, but no material short-term "
            "change has yet exceeded AQSD trend thresholds."
        )

    return commentary


def determine_composite_state(
    metric_trends: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce a non-trading composite description.

    This is descriptive analytics only and does not place or recommend orders.
    """

    bullish_score = 0
    bearish_score = 0

    evidence: list[str] = []

    checks = (
        (
            "spot_price",
            15,
            "RISING",
            "FALLING",
            2,
            "Spot",
        ),
        (
            "modified_pcr",
            15,
            "RISING",
            "FALLING",
            1,
            "Modified PCR",
        ),
        (
            "bullish_probability",
            15,
            "RISING",
            "FALLING",
            2,
            "Bullish probability",
        ),
        (
            "bearish_probability",
            15,
            "FALLING",
            "RISING",
            2,
            "Bearish probability",
        ),
        (
            "confidence_score",
            15,
            "RISING",
            "FALLING",
            1,
            "Confidence",
        ),
    )

    for (
        metric,
        window,
        bullish_direction,
        bearish_direction,
        weight,
        label,
    ) in checks:
        trend = trend_lookup(
            metric_trends,
            metric,
            window,
        )

        if not trend:
            continue

        direction = trend["direction"]

        if direction == bullish_direction:
            bullish_score += weight
            evidence.append(
                f"{label}: {direction}"
            )

        elif direction == bearish_direction:
            bearish_score += weight
            evidence.append(
                f"{label}: {direction}"
            )

    difference = (
        bullish_score
        - bearish_score
    )

    if difference >= 3:
        state = "BULLISH DEVELOPMENT"
    elif difference <= -3:
        state = "BEARISH DEVELOPMENT"
    else:
        state = "MIXED / DEVELOPING"

    return {
        "state": state,
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "score_difference": difference,
        "evidence": evidence,
        "note": (
            "Descriptive historical state only; not an order signal."
        ),
    }


# ============================================================
# REPORT BUILDING
# ============================================================

def serialize_dataclass(
    value: Any,
) -> dict[str, Any]:
    """Convert a dataclass to a JSON-compatible dictionary."""

    return asdict(
        value
    )


def build_report(
    points: Sequence[HistoryPoint],
    lookback_minutes: int,
) -> dict[str, Any]:
    """Build the complete History Analytics report."""

    if not points:
        raise RuntimeError(
            "No history rows were found inside the selected lookback "
            f"period of {lookback_minutes} minutes."
        )

    continuous_metrics = (
        "spot_price",
        "oi_pcr",
        "change_oi_pcr",
        "modified_pcr",
        "volume_pcr",
        "atm_zone_pcr",
        "atm_iv",
        "historical_volatility",
        "iv_rank",
        "iv_percentile",
        "bullish_probability",
        "bearish_probability",
        "continuation_probability",
        "reversal_probability",
        "confidence_score",
    )

    discrete_metrics = (
        "max_pain_strike",
        "call_wall",
        "put_wall",
        "fresh_call_wall",
        "fresh_put_wall",
    )

    metric_trends: dict[str, dict[str, Any]] = {}

    for metric in continuous_metrics:
        metric_trends[metric] = {}

        for window in TREND_WINDOWS_MINUTES:
            trend = analyze_metric_trend(
                points,
                metric,
                window,
            )

            metric_trends[metric][str(window)] = (
                serialize_dataclass(
                    trend
                )
            )

    level_movements: dict[str, dict[str, Any]] = {}

    for metric in discrete_metrics:
        level_movements[metric] = {}

        for window in TREND_WINDOWS_MINUTES:
            movement = analyze_level_movement(
                points,
                metric,
                window,
            )

            level_movements[metric][str(window)] = (
                serialize_dataclass(
                    movement
                )
            )

    commentary = build_market_commentary(
        points=points,
        metric_trends=metric_trends,
        level_movements=level_movements,
    )

    composite_state = determine_composite_state(
        metric_trends
    )

    latest_point = points[-1]

    return {
        "report_name": (
            "AQSD BANKNIFTY OPTION INTELLIGENCE "
            "HISTORY ANALYTICS"
        ),
        "version": "1.0",
        "generated_at": now_local().isoformat(
            timespec="seconds"
        ),

        "database_file": str(
            DATABASE_FILE
        ),
        "lookback_minutes": lookback_minutes,
        "total_samples": len(points),

        "data_period": {
            "first_timestamp": points[0].timestamp.isoformat(
                timespec="seconds"
            ),
            "latest_timestamp": points[-1].timestamp.isoformat(
                timespec="seconds"
            ),
            "elapsed_minutes": round(
                (
                    points[-1].timestamp
                    - points[0].timestamp
                ).total_seconds()
                / 60.0,
                2,
            ),
        },

        "latest_snapshot": {
            "source_timestamp": latest_point.source_timestamp,
            "spot_price": latest_point.spot_price,
            "atm_strike": latest_point.atm_strike,

            "oi_pcr": latest_point.oi_pcr,
            "change_oi_pcr": latest_point.change_oi_pcr,
            "modified_pcr": latest_point.modified_pcr,
            "volume_pcr": latest_point.volume_pcr,
            "atm_zone_pcr": latest_point.atm_zone_pcr,

            "max_pain_strike": latest_point.max_pain_strike,
            "call_wall": latest_point.call_wall,
            "put_wall": latest_point.put_wall,
            "fresh_call_wall": latest_point.fresh_call_wall,
            "fresh_put_wall": latest_point.fresh_put_wall,

            "atm_iv": latest_point.atm_iv,
            "historical_volatility": (
                latest_point.historical_volatility
            ),
            "iv_rank": latest_point.iv_rank,
            "iv_percentile": latest_point.iv_percentile,

            "bullish_probability": (
                latest_point.bullish_probability
            ),
            "bearish_probability": (
                latest_point.bearish_probability
            ),
            "continuation_probability": (
                latest_point.continuation_probability
            ),
            "reversal_probability": (
                latest_point.reversal_probability
            ),

            "confidence_score": latest_point.confidence_score,
            "final_decision": latest_point.final_decision,
            "decision_bias": latest_point.decision_bias,
            "market_regime": latest_point.market_regime,
            "volatility_regime": (
                latest_point.volatility_regime
            ),
        },

        "composite_history_state": composite_state,
        "commentary": commentary,
        "metric_trends": metric_trends,
        "level_movements": level_movements,

        "data_quality": {
            "minimum_samples_per_window": (
                MINIMUM_WINDOW_SAMPLES
            ),
            "available_samples": len(points),
            "status": (
                "SUFFICIENT"
                if len(points) >= MINIMUM_WINDOW_SAMPLES
                else "LIMITED"
            ),
            "note": (
                "Trend reliability improves as more automatic "
                "pipeline refreshes are stored."
            ),
        },
    }


def save_report(
    report: dict[str, Any],
) -> None:
    """Save the History Analytics report as JSON."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_JSON_FILE.with_suffix(
        ".json.tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            report,
            handle,
            indent=4,
            ensure_ascii=False,
            allow_nan=False,
        )

    temporary_file.replace(
        OUTPUT_JSON_FILE
    )


# ============================================================
# TERMINAL DISPLAY
# ============================================================

def display_report_summary(
    report: dict[str, Any],
) -> None:
    """Print a compact History Analytics summary."""

    latest = report["latest_snapshot"]
    composite = report["composite_history_state"]

    print()
    print("=" * 84)
    print("AQSD OPTION INTELLIGENCE HISTORY ANALYTICS")
    print("=" * 84)
    print(
        f"Samples              : {report['total_samples']}"
    )
    print(
        f"Lookback             : {report['lookback_minutes']} minutes"
    )
    print(
        f"Latest Timestamp     : "
        f"{report['data_period']['latest_timestamp']}"
    )
    print(
        f"Spot                 : {latest['spot_price']}"
    )
    print(
        f"Modified PCR         : {latest['modified_pcr']}"
    )
    print(
        f"ATM IV               : {latest['atm_iv']}"
    )
    print(
        f"Max Pain             : {latest['max_pain_strike']}"
    )
    print(
        f"Call Wall            : {latest['call_wall']}"
    )
    print(
        f"Put Wall             : {latest['put_wall']}"
    )
    print(
        f"Final Decision       : {latest['final_decision']}"
    )
    print(
        f"Confidence           : {latest['confidence_score']}"
    )
    print(
        f"Composite State      : {composite['state']}"
    )
    print(
        f"Bull / Bear Score    : "
        f"{composite['bullish_score']} / "
        f"{composite['bearish_score']}"
    )

    print()
    print("-" * 84)
    print("MARKET DEVELOPMENT COMMENTARY")
    print("-" * 84)

    for number, statement in enumerate(
        report["commentary"],
        start=1,
    ):
        print(
            f"{number}. {statement}"
        )

    print()
    print("-" * 84)
    print("KEY 15-MINUTE TRENDS")
    print("-" * 84)

    key_metrics = (
        "spot_price",
        "modified_pcr",
        "atm_iv",
        "bullish_probability",
        "bearish_probability",
        "confidence_score",
    )

    for metric in key_metrics:
        trend = (
            report["metric_trends"]
            [metric]
            ["15"]
        )

        print(
            f"{metric_label(metric):<24}: "
            f"{trend['direction']:<18} "
            f"{trend['strength']:<12} "
            f"Samples={trend['sample_count']}"
        )

    print()
    print("=" * 84)
    print(
        f"JSON SAVED: {OUTPUT_JSON_FILE}"
    )
    print("=" * 84)


# ============================================================
# COMMAND-LINE INTERFACE
# ============================================================

def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyze AQSD Option Intelligence history stored "
            "in SQLite."
        )
    )

    parser.add_argument(
        "--minutes",
        type=int,
        default=DEFAULT_LOOKBACK_MINUTES,
        help=(
            "Total database lookback in minutes. "
            f"Default: {DEFAULT_LOOKBACK_MINUTES}"
        ),
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help=(
            "Print the complete generated JSON after the summary."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run AQSD History Analytics."""

    args = parse_arguments()

    if args.minutes < 1:
        raise SystemExit(
            "--minutes must be at least 1."
        )

    with connect_database() as connection:
        verify_history_table(
            connection
        )

        points = load_history_points(
            connection,
            args.minutes,
        )

    report = build_report(
        points,
        args.minutes,
    )

    save_report(
        report
    )

    display_report_summary(
        report
    )

    if args.show:
        print()
        print(
            json.dumps(
                report,
                indent=4,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
