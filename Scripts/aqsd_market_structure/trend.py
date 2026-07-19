"""
AQSD
Market Structure Engine

Module: trend.py
Version: 2.0
Author: AQSD

Description:
Calculates:

- EMA20
- EMA50
- EMA200
- ATR(14)
- ATR-based EMA tolerance
- EMA slopes
- Trend direction
- Trend strength
- Trend Score from 0 to 100
- Trend rating
- Directional strength
- Trend-score breakdown
- Supporting evidence
"""

from __future__ import annotations

import pandas as pd

from .config import DEFAULT_CONFIG, MarketStructureConfig
from .models import (
    TrendDirection,
    TrendResult,
    TrendStrength,
)


REQUIRED_COLUMNS = {
    "High",
    "Low",
    "Close",
}

ATR_PERIOD = 14

EMA_TOLERANCE_ATR_PERCENT = 0.05

EMA_SLOPE_LOOKBACK = 5

EMA_SLOPE_THRESHOLD_PERCENT = 0.05


# =========================================================
# DATA VALIDATION
# =========================================================


def validate_trend_data(
    df: pd.DataFrame,
) -> None:
    """
    Validate market data required by the trend module.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Input must be a pandas DataFrame."
        )

    if df.empty:
        raise ValueError(
            "Input DataFrame cannot be empty."
        )

    missing_columns = REQUIRED_COLUMNS.difference(
        df.columns
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            f"Missing required columns: {missing_text}"
        )


# =========================================================
# EMA CALCULATION
# =========================================================


def calculate_ema(
    close_series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Calculate an exponential moving average.
    """

    if not isinstance(close_series, pd.Series):
        raise TypeError(
            "close_series must be a pandas Series."
        )

    if period <= 0:
        raise ValueError(
            "EMA period must be greater than zero."
        )

    numeric_close = pd.to_numeric(
        close_series,
        errors="coerce",
    )

    if numeric_close.dropna().empty:
        raise ValueError(
            "Close series contains no valid numeric values."
        )

    return numeric_close.ewm(
        span=period,
        adjust=False,
        min_periods=period,
    ).mean()


def calculate_all_emas(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Calculate EMA20, EMA50 and EMA200.
    """

    validate_trend_data(df)

    result = df.copy()

    result["EMA20"] = calculate_ema(
        close_series=result["Close"],
        period=config.ema_fast_period,
    )

    result["EMA50"] = calculate_ema(
        close_series=result["Close"],
        period=config.ema_medium_period,
    )

    result["EMA200"] = calculate_ema(
        close_series=result["Close"],
        period=config.ema_slow_period,
    )

    return result


# =========================================================
# ATR CALCULATION
# =========================================================


def calculate_atr(
    df: pd.DataFrame,
    period: int = ATR_PERIOD,
) -> pd.Series:
    """
    Calculate Average True Range using Wilder smoothing.
    """

    validate_trend_data(df)

    if period <= 0:
        raise ValueError(
            "ATR period must be greater than zero."
        )

    high = pd.to_numeric(
        df["High"],
        errors="coerce",
    )

    low = pd.to_numeric(
        df["Low"],
        errors="coerce",
    )

    close = pd.to_numeric(
        df["Close"],
        errors="coerce",
    )

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


# =========================================================
# EMA SLOPE CALCULATION
# =========================================================


def calculate_ema_slope_percent(
    ema_series: pd.Series,
    lookback: int = EMA_SLOPE_LOOKBACK,
) -> float:
    """
    Calculate the percentage slope of an EMA.

    The current EMA is compared with the EMA value
    a specified number of candles earlier.

    Positive:
        EMA is rising.

    Negative:
        EMA is falling.

    Near zero:
        EMA is flat.
    """

    if not isinstance(ema_series, pd.Series):
        raise TypeError(
            "ema_series must be a pandas Series."
        )

    if lookback <= 0:
        raise ValueError(
            "EMA slope lookback must be greater than zero."
        )

    valid_values = ema_series.dropna()

    if len(valid_values) <= lookback:
        raise ValueError(
            "Insufficient EMA data to calculate slope."
        )

    current_value = float(
        valid_values.iloc[-1]
    )

    previous_value = float(
        valid_values.iloc[-1 - lookback]
    )

    if previous_value == 0:
        raise ValueError(
            "Previous EMA value cannot be zero."
        )

    slope_percent = (
        (current_value - previous_value)
        / abs(previous_value)
    ) * 100

    return float(slope_percent)


def classify_ema_slope(
    slope_percent: float,
    threshold_percent: float = (
        EMA_SLOPE_THRESHOLD_PERCENT
    ),
) -> str:
    """
    Classify an EMA slope.

    Returns:
        RISING
        FALLING
        FLAT
    """

    if slope_percent > threshold_percent:
        return "RISING"

    if slope_percent < -threshold_percent:
        return "FALLING"

    return "FLAT"


# =========================================================
# TREND DIRECTION
# =========================================================


def determine_trend(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Determine AQSD trend direction and supporting evidence.
    """

    ema_data = calculate_all_emas(
        df=df,
        config=config,
    )

    latest = ema_data.iloc[-1]

    close = float(
        latest["Close"]
    )

    ema20_value = latest["EMA20"]
    ema50_value = latest["EMA50"]
    ema200_value = latest["EMA200"]

    if (
        pd.isna(ema20_value)
        or pd.isna(ema50_value)
        or pd.isna(ema200_value)
    ):
        raise ValueError(
            "Insufficient data to calculate all required EMAs. "
            f"At least {config.ema_slow_period} valid rows "
            "are required."
        )

    ema20 = float(
        ema20_value
    )

    ema50 = float(
        ema50_value
    )

    ema200 = float(
        ema200_value
    )

    atr_series = calculate_atr(
        df=df,
        period=ATR_PERIOD,
    )

    atr_value = atr_series.iloc[-1]

    if pd.isna(atr_value):
        raise ValueError(
            "Insufficient data to calculate ATR."
        )

    atr = float(
        atr_value
    )

    if atr <= 0:
        raise ValueError(
            "Unable to calculate a valid ATR value."
        )

    ema_tolerance = (
        atr * EMA_TOLERANCE_ATR_PERCENT
    )

    ema50_above_ema200 = (
        ema50 > ema200 + ema_tolerance
    )

    ema50_below_ema200 = (
        ema50 < ema200 - ema_tolerance
    )

    ema50_near_ema200 = (
        abs(ema50 - ema200)
        <= ema_tolerance
    )

    ema20_slope_percent = (
        calculate_ema_slope_percent(
            ema_series=ema_data["EMA20"],
            lookback=EMA_SLOPE_LOOKBACK,
        )
    )

    ema50_slope_percent = (
        calculate_ema_slope_percent(
            ema_series=ema_data["EMA50"],
            lookback=EMA_SLOPE_LOOKBACK,
        )
    )

    ema200_slope_percent = (
        calculate_ema_slope_percent(
            ema_series=ema_data["EMA200"],
            lookback=EMA_SLOPE_LOOKBACK,
        )
    )

    ema20_slope = classify_ema_slope(
        slope_percent=ema20_slope_percent
    )

    ema50_slope = classify_ema_slope(
        slope_percent=ema50_slope_percent
    )

    ema200_slope = classify_ema_slope(
        slope_percent=ema200_slope_percent
    )

    evidence: list[str] = []

    if close > ema20:
        evidence.append(
            "Price is above EMA20"
        )

    elif close < ema20:
        evidence.append(
            "Price is below EMA20"
        )

    else:
        evidence.append(
            "Price is equal to EMA20"
        )

    if ema20 > ema50:
        evidence.append(
            "EMA20 is above EMA50"
        )

    elif ema20 < ema50:
        evidence.append(
            "EMA20 is below EMA50"
        )

    else:
        evidence.append(
            "EMA20 is equal to EMA50"
        )

    if ema50_above_ema200:
        evidence.append(
            "EMA50 is meaningfully above EMA200"
        )

    elif ema50_below_ema200:
        evidence.append(
            "EMA50 is meaningfully below EMA200"
        )

    elif ema50_near_ema200:
        evidence.append(
            "EMA50 and EMA200 are within ATR tolerance "
            f"({ema_tolerance:.2f} points)"
        )

    evidence.append(
        f"EMA20 slope is {ema20_slope} "
        f"({ema20_slope_percent:+.3f}% over "
        f"{EMA_SLOPE_LOOKBACK} candles)"
    )

    evidence.append(
        f"EMA50 slope is {ema50_slope} "
        f"({ema50_slope_percent:+.3f}% over "
        f"{EMA_SLOPE_LOOKBACK} candles)"
    )

    evidence.append(
        f"EMA200 slope is {ema200_slope} "
        f"({ema200_slope_percent:+.3f}% over "
        f"{EMA_SLOPE_LOOKBACK} candles)"
    )

    bullish = (
        close > ema20
        and ema20 > ema50
        and (
            ema50_above_ema200
            or ema50_near_ema200
        )
    )

    bearish = (
        close < ema20
        and ema20 < ema50
        and (
            ema50_below_ema200
            or ema50_near_ema200
        )
    )

    if bullish:
        direction = TrendDirection.BULLISH

    elif bearish:
        direction = TrendDirection.BEARISH

    else:
        direction = TrendDirection.NEUTRAL

    return TrendResult(
        direction=direction,
        strength=TrendStrength.NEUTRAL,
        close=close,
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        evidence=evidence,
    )


# =========================================================
# TREND STRENGTH
# =========================================================


def calculate_trend_strength(
    trend: TrendResult,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Calculate trend strength from EMA20-EMA50 separation.
    """

    if (
        trend.ema20 is None
        or trend.ema50 is None
    ):
        return trend

    if trend.ema50 == 0:
        raise ValueError(
            "EMA50 cannot be zero when calculating "
            "trend strength."
        )

    ema_gap = abs(
        trend.ema20 - trend.ema50
    )

    gap_percent = (
        ema_gap / abs(trend.ema50)
    ) * 100

    if (
        gap_percent
        >= config.strong_trend_ema_gap_percent
    ):
        trend.strength = TrendStrength.STRONG

        trend.evidence.append(
            "Strong EMA separation"
        )

    elif (
        gap_percent
        >= config.moderate_trend_ema_gap_percent
    ):
        trend.strength = TrendStrength.MODERATE

        trend.evidence.append(
            "Moderate EMA separation"
        )

    else:
        trend.strength = TrendStrength.WEAK

        trend.evidence.append(
            "Weak EMA separation"
        )

    trend.evidence.append(
        f"EMA20-EMA50 separation is "
        f"{gap_percent:.3f}%"
    )

    return trend


# =========================================================
# TREND SCORE HELPERS
# =========================================================


def classify_trend_score(
    score: float,
) -> str:
    """
    Convert a numerical Trend Score into a rating.

    Score interpretation:

        80-100:
            VERY STRONG BULLISH

        65-79:
            BULLISH

        55-64:
            WEAK BULLISH

        45-54:
            NEUTRAL

        35-44:
            WEAK BEARISH

        20-34:
            BEARISH

        0-19:
            VERY STRONG BEARISH
    """

    normalized_score = max(
        0.0,
        min(100.0, float(score)),
    )

    if normalized_score >= 80:
        return "VERY STRONG BULLISH"

    if normalized_score >= 65:
        return "BULLISH"

    if normalized_score >= 55:
        return "WEAK BULLISH"

    if normalized_score >= 45:
        return "NEUTRAL"

    if normalized_score >= 35:
        return "WEAK BEARISH"

    if normalized_score >= 20:
        return "BEARISH"

    return "VERY STRONG BEARISH"


def calculate_directional_strength(
    trend_score: float,
) -> float:
    """
    Calculate trend intensity irrespective of direction.

    Formula:

        abs(Trend Score - 50) * 2

    Examples:

        Score 85:
            Directional strength = 70

        Score 50:
            Directional strength = 0

        Score 15:
            Directional strength = 70
    """

    normalized_score = max(
        0.0,
        min(100.0, float(trend_score)),
    )

    directional_strength = (
        abs(normalized_score - 50.0) * 2.0
    )

    return max(
        0.0,
        min(100.0, directional_strength),
    )


# =========================================================
# TREND SCORE COMPONENTS
# =========================================================


def score_price_position(
    close: float,
    ema20: float,
    tolerance: float,
) -> float:
    """
    Score the position of price relative to EMA20.

    Maximum points:
        20
    """

    if close > ema20 + tolerance:
        return 20.0

    if close < ema20 - tolerance:
        return 0.0

    return 10.0


def score_ema_alignment(
    ema20: float,
    ema50: float,
    ema200: float,
    tolerance: float,
) -> float:
    """
    Score EMA20, EMA50 and EMA200 alignment.

    Maximum points:
        30

    Higher scores represent bullish alignment.
    Lower scores represent bearish alignment.
    """

    fully_bullish = (
        ema20 > ema50 + tolerance
        and ema50 > ema200 + tolerance
    )

    fully_bearish = (
        ema20 < ema50 - tolerance
        and ema50 < ema200 - tolerance
    )

    compressed = (
        abs(ema20 - ema50) <= tolerance
        and abs(ema50 - ema200) <= tolerance
    )

    if fully_bullish:
        return 30.0

    if fully_bearish:
        return 0.0

    if compressed:
        return 15.0

    if (
        ema20 > ema50
        and ema50 >= ema200
    ):
        return 25.0

    if (
        ema20 > ema50
        and ema20 > ema200
    ):
        return 22.5

    if ema20 > ema50:
        return 20.0

    if (
        ema20 < ema50
        and ema50 <= ema200
    ):
        return 5.0

    if (
        ema20 < ema50
        and ema20 < ema200
    ):
        return 7.5

    if ema20 < ema50:
        return 10.0

    return 15.0


def score_ema20_slope(
    slope_classification: str,
) -> float:
    """
    Score EMA20 slope.

    Maximum points:
        15
    """

    if slope_classification == "RISING":
        return 15.0

    if slope_classification == "FALLING":
        return 0.0

    return 7.5


def score_ema50_slope(
    slope_classification: str,
) -> float:
    """
    Score EMA50 slope.

    Maximum points:
        10
    """

    if slope_classification == "RISING":
        return 10.0

    if slope_classification == "FALLING":
        return 0.0

    return 5.0


def score_trend_strength(
    direction: TrendDirection,
    strength: TrendStrength,
) -> float:
    """
    Score the existing trend-strength classification.

    Maximum points:
        10

    Strong bullish trends receive high points.
    Strong bearish trends receive low points.
    Weak trends remain closer to neutral.
    """

    if direction == TrendDirection.BULLISH:
        bullish_scores = {
            TrendStrength.STRONG: 10.0,
            TrendStrength.MODERATE: 7.0,
            TrendStrength.WEAK: 3.0,
            TrendStrength.NEUTRAL: 5.0,
        }

        return bullish_scores.get(
            strength,
            5.0,
        )

    if direction == TrendDirection.BEARISH:
        bearish_scores = {
            TrendStrength.STRONG: 0.0,
            TrendStrength.MODERATE: 3.0,
            TrendStrength.WEAK: 7.0,
            TrendStrength.NEUTRAL: 5.0,
        }

        return bearish_scores.get(
            strength,
            5.0,
        )

    return 5.0


def score_trend_direction(
    direction: TrendDirection,
) -> float:
    """
    Score the calculated trend direction.

    Maximum points:
        15
    """

    if direction == TrendDirection.BULLISH:
        return 15.0

    if direction == TrendDirection.BEARISH:
        return 0.0

    return 7.5


# =========================================================
# TREND SCORE CALCULATION
# =========================================================


def calculate_trend_score(
    df: pd.DataFrame,
    trend: TrendResult,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Calculate the AQSD Trend Score.

    Score components
    ----------------

    Price vs EMA20:
        20 points

    EMA alignment:
        30 points

    EMA20 slope:
        15 points

    EMA50 slope:
        10 points

    Trend strength:
        10 points

    Trend direction:
        15 points

    Total:
        100 points
    """

    validate_trend_data(df)

    if (
        trend.ema20 is None
        or trend.ema50 is None
        or trend.ema200 is None
    ):
        raise ValueError(
            "EMA20, EMA50 and EMA200 are required "
            "to calculate Trend Score."
        )

    ema_data = calculate_all_emas(
        df=df,
        config=config,
    )

    atr_series = calculate_atr(
        df=df,
        period=ATR_PERIOD,
    )

    atr_value = atr_series.iloc[-1]

    if pd.isna(atr_value):
        raise ValueError(
            "Insufficient data to calculate ATR "
            "for Trend Score."
        )

    atr = float(
        atr_value
    )

    if atr <= 0:
        raise ValueError(
            "ATR must be greater than zero "
            "for Trend Score."
        )

    ema_tolerance = (
        atr * EMA_TOLERANCE_ATR_PERCENT
    )

    ema20_slope_percent = (
        calculate_ema_slope_percent(
            ema_series=ema_data["EMA20"],
            lookback=EMA_SLOPE_LOOKBACK,
        )
    )

    ema50_slope_percent = (
        calculate_ema_slope_percent(
            ema_series=ema_data["EMA50"],
            lookback=EMA_SLOPE_LOOKBACK,
        )
    )

    ema20_slope = classify_ema_slope(
        slope_percent=ema20_slope_percent
    )

    ema50_slope = classify_ema_slope(
        slope_percent=ema50_slope_percent
    )

    price_points = score_price_position(
        close=trend.close,
        ema20=trend.ema20,
        tolerance=ema_tolerance,
    )

    alignment_points = score_ema_alignment(
        ema20=trend.ema20,
        ema50=trend.ema50,
        ema200=trend.ema200,
        tolerance=ema_tolerance,
    )

    ema20_slope_points = score_ema20_slope(
        slope_classification=ema20_slope
    )

    ema50_slope_points = score_ema50_slope(
        slope_classification=ema50_slope
    )

    strength_points = score_trend_strength(
        direction=trend.direction,
        strength=trend.strength,
    )

    direction_points = score_trend_direction(
        direction=trend.direction
    )

    score_breakdown = {
        "price_vs_ema20": price_points,
        "ema_alignment": alignment_points,
        "ema20_slope": ema20_slope_points,
        "ema50_slope": ema50_slope_points,
        "trend_strength": strength_points,
        "trend_direction": direction_points,
    }

    trend_score = sum(
        score_breakdown.values()
    )

    trend_score = max(
        0.0,
        min(100.0, trend_score),
    )

    trend_rating = classify_trend_score(
        score=trend_score
    )

    directional_strength = (
        calculate_directional_strength(
            trend_score=trend_score
        )
    )

    trend.trend_score = round(
        trend_score,
        2,
    )

    trend.trend_rating = trend_rating

    trend.directional_strength = round(
        directional_strength,
        2,
    )

    trend.score_breakdown = score_breakdown

    trend.evidence.append(
        f"Trend Score is {trend.trend_score:.2f}/100"
    )

    trend.evidence.append(
        f"Trend rating is {trend.trend_rating}"
    )

    trend.evidence.append(
        "Directional strength is "
        f"{trend.directional_strength:.2f}%"
    )

    trend.evidence.append(
        "Trend Score breakdown: "
        f"Price {price_points:.1f}/20, "
        f"EMA alignment {alignment_points:.1f}/30, "
        f"EMA20 slope {ema20_slope_points:.1f}/15, "
        f"EMA50 slope {ema50_slope_points:.1f}/10, "
        f"Trend strength {strength_points:.1f}/10, "
        f"Trend direction {direction_points:.1f}/15"
    )

    return trend


# =========================================================
# COMPLETE TREND ANALYSIS
# =========================================================


def analyze_trend(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Complete AQSD Trend Analysis.

    Workflow
    --------

    1. Validate market data.
    2. Calculate EMA20, EMA50 and EMA200.
    3. Calculate ATR-based tolerance.
    4. Calculate EMA slopes.
    5. Determine trend direction.
    6. Calculate trend strength.
    7. Calculate Trend Score.
    8. Calculate trend rating.
    9. Calculate directional strength.
    """

    validate_trend_data(df)

    trend = determine_trend(
        df=df,
        config=config,
    )

    trend = calculate_trend_strength(
        trend=trend,
        config=config,
    )

    trend = calculate_trend_score(
        df=df,
        trend=trend,
        config=config,
    )

    return trend