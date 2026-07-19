"""
AQSD
Market Structure Engine

Module: trend.py
Version: 1.1
Author: AQSD
Description:
Calculates exponential moving averages, Average True Range,
trend direction, and trend strength.

EMA50 and EMA200 comparisons use an ATR-based tolerance
to avoid false trend classifications when the two averages
are extremely close.
"""

from __future__ import annotations

import pandas as pd

from .config import DEFAULT_CONFIG, MarketStructureConfig
from .models import TrendDirection, TrendResult, TrendStrength


REQUIRED_COLUMNS = {"High", "Low", "Close"}

ATR_PERIOD = 14
EMA_TOLERANCE_ATR_PERCENT = 0.05


def validate_trend_data(df: pd.DataFrame) -> None:
    """
    Validate market data required by the trend module.

    Args:
        df: OHLC market-data DataFrame.

    Raises:
        TypeError: If input is not a pandas DataFrame.
        ValueError: If required columns are missing or data is empty.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if df.empty:
        raise ValueError("Input DataFrame cannot be empty.")

    missing_columns = REQUIRED_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))

        raise ValueError(
            f"Missing required columns: {missing_text}"
        )


def calculate_ema(
    close_series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Calculate an exponential moving average.

    Args:
        close_series: Series containing closing prices.
        period: EMA lookback period.

    Returns:
        pandas Series containing EMA values.

    Raises:
        TypeError: If close_series is not a pandas Series.
        ValueError: If period is invalid or data is unusable.
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


def calculate_atr(
    df: pd.DataFrame,
    period: int = ATR_PERIOD,
) -> pd.Series:
    """
    Calculate Average True Range using Wilder-style smoothing.

    Args:
        df: OHLC market-data DataFrame.
        period: ATR lookback period.

    Returns:
        pandas Series containing ATR values.

    Raises:
        ValueError: If the period is invalid.
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


def calculate_all_emas(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Calculate all AQSD EMAs and append them to the DataFrame.

    Adds:
        EMA20
        EMA50
        EMA200

    Args:
        df: Market OHLC DataFrame.
        config: Market Structure configuration.

    Returns:
        DataFrame containing EMA columns.
    """

    validate_trend_data(df)

    result = df.copy()

    result["EMA20"] = calculate_ema(
        result["Close"],
        config.ema_fast_period,
    )

    result["EMA50"] = calculate_ema(
        result["Close"],
        config.ema_medium_period,
    )

    result["EMA200"] = calculate_ema(
        result["Close"],
        config.ema_slow_period,
    )

    return result


def determine_trend(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Determine the current AQSD trend direction.

    Bullish:
        Close is above EMA20.
        EMA20 is above EMA50.
        EMA50 is meaningfully above EMA200 or is within
        the permitted ATR tolerance.

    Bearish:
        Close is below EMA20.
        EMA20 is below EMA50.
        EMA50 is meaningfully below EMA200 or is within
        the permitted ATR tolerance.

    Otherwise:
        Neutral.

    Args:
        df: Market OHLC DataFrame.
        config: Market Structure configuration.

    Returns:
        TrendResult containing direction, strength,
        EMA values, and supporting evidence.
    """

    ema_data = calculate_all_emas(
        df=df,
        config=config,
    )

    latest = ema_data.iloc[-1]

    close = float(latest["Close"])
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
            f"At least {config.ema_slow_period} valid rows are required."
        )

    ema20 = float(ema20_value)
    ema50 = float(ema50_value)
    ema200 = float(ema200_value)

    atr_series = calculate_atr(
        df=df,
        period=ATR_PERIOD,
    )

    atr_value = atr_series.iloc[-1]

    if pd.isna(atr_value):
        raise ValueError(
            "Insufficient data to calculate ATR."
        )

    atr = float(atr_value)

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
        abs(ema50 - ema200) <= ema_tolerance
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


def calculate_trend_strength(
    trend: TrendResult,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Calculate AQSD Trend Strength based on EMA separation.

    Args:
        trend: TrendResult returned by determine_trend().
        config: Market Structure configuration.

    Returns:
        Updated TrendResult with trend strength.
    """

    if (
        trend.ema20 is None
        or trend.ema50 is None
    ):
        return trend

    if trend.ema50 == 0:
        raise ValueError(
            "EMA50 cannot be zero when calculating trend strength."
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

    return trend


def analyze_trend(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Complete AQSD Trend Analysis.

    Workflow
    --------
    1. Validate input data.
    2. Calculate EMA20, EMA50, and EMA200.
    3. Calculate ATR-based EMA tolerance.
    4. Determine trend direction.
    5. Calculate trend strength.

    Args:
        df: OHLC market data.
        config: Market Structure configuration.

    Returns:
        Completed TrendResult.
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

    return trend