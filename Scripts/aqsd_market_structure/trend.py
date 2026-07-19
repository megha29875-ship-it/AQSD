"""
AQSD
Market Structure Engine

Module: trend.py
Version: 1.0
Author: AQSD
Description:
Calculates exponential moving averages and determines
trend direction and trend strength.
"""

from __future__ import annotations

import pandas as pd

from .config import DEFAULT_CONFIG, MarketStructureConfig


REQUIRED_COLUMNS = {"Close"}


def validate_trend_data(df: pd.DataFrame) -> None:
    """
    Validate market data required by the trend module.

    Args:
        df: OHLC market-data DataFrame.

    Raises:
        TypeError: If input is not a pandas DataFrame.
        ValueError: If Close column is missing or data is empty.
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
        ValueError: If period is invalid.
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

from .models import TrendDirection, TrendResult, TrendStrength

def determine_trend(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> TrendResult:
    """
    Determine the current AQSD trend direction.

    Bullish:
        Close > EMA20
        EMA20 > EMA50
        EMA50 > EMA200

    Bearish:
        Close < EMA20
        EMA20 < EMA50
        EMA50 < EMA200

    Otherwise:
        Neutral

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
    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]
    ema200 = latest["EMA200"]

    if pd.isna(ema20) or pd.isna(ema50) or pd.isna(ema200):
        raise ValueError(
            "Insufficient data to calculate all required EMAs. "
            f"At least {config.ema_slow_period} valid rows are required."
        )

    ema20 = float(ema20)
    ema50 = float(ema50)
    ema200 = float(ema200)

    evidence = []

    if close > ema20:
        evidence.append("Price is above EMA20")

    if close < ema20:
        evidence.append("Price is below EMA20")

    if ema20 > ema50:
        evidence.append("EMA20 is above EMA50")

    if ema20 < ema50:
        evidence.append("EMA20 is below EMA50")

    if ema50 > ema200:
        evidence.append("EMA50 is above EMA200")

    if ema50 < ema200:
        evidence.append("EMA50 is below EMA200")

    bullish = (
        close > ema20
        and ema20 > ema50
        and ema50 > ema200
    )

    bearish = (
        close < ema20
        and ema20 < ema50
        and ema50 < ema200
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
    Calculate AQSD Trend Strength based on
    EMA separation.

    Returns:
        Updated TrendResult with strength.
    """

    if (
        trend.ema20 is None
        or trend.ema50 is None
    ):
        return trend

    ema_gap = abs(trend.ema20 - trend.ema50)

    gap_percent = (
        ema_gap / trend.ema50
    ) * 100

    if gap_percent >= config.strong_trend_ema_gap_percent:
        trend.strength = TrendStrength.STRONG
        trend.evidence.append(
            "Strong EMA separation"
        )

    elif gap_percent >= config.moderate_trend_ema_gap_percent:
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
    1. Validate input data
    2. Calculate EMA20, EMA50, EMA200
    3. Determine trend direction
    4. Calculate trend strength

    Args:
        df: OHLC market data.

    Returns:
        TrendResult
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

