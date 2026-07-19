"""
AQSD
Market Structure Engine

Module: swings.py
Version: 1.0
Author: AQSD
Description:
Detects swing highs, swing lows, and classifies
market structure as HH, HL, LH, and LL.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd

from .config import DEFAULT_CONFIG, MarketStructureConfig
from .models import SwingPoint, SwingType


REQUIRED_COLUMNS = {"High", "Low"}


def validate_price_data(df: pd.DataFrame) -> None:
    """
    Validate the input DataFrame.

    Args:
        df: OHLC market-data DataFrame.

    Raises:
        TypeError: If the input is not a DataFrame.
        ValueError: If required columns or rows are missing.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    missing_columns = REQUIRED_COLUMNS.difference(df.columns)

    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Missing required columns: {missing_text}"
        )

    if df.empty:
        raise ValueError("Input DataFrame cannot be empty.")


def _resolve_timestamp(
    df: pd.DataFrame,
    index_position: int,
) -> datetime:
    """
    Resolve a timestamp for a detected swing point.

    Uses the DataFrame index when it is date-like.
    Otherwise, it uses the current time.
    """

    index_value = df.index[index_position]

    if isinstance(index_value, pd.Timestamp):
        return index_value.to_pydatetime()

    if isinstance(index_value, datetime):
        return index_value

    return datetime.now()


def detect_raw_swings(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect raw swing highs and swing lows.

    A swing high is higher than all neighbouring highs
    inside the configured swing window.

    A swing low is lower than all neighbouring lows
    inside the configured swing window.

    Args:
        df: OHLC market-data DataFrame.
        config: Market Structure Engine configuration.

    Returns:
        A tuple containing:
            - list of swing highs
            - list of swing lows
    """

    validate_price_data(df)
    config.validate()

    window = config.swing_window

    if len(df) < (window * 2) + 1:
        raise ValueError(
            "Not enough rows to detect swings. "
            f"Minimum required: {(window * 2) + 1}"
        )

    highs: List[SwingPoint] = []
    lows: List[SwingPoint] = []

    high_series = pd.to_numeric(
        df["High"],
        errors="coerce",
    )

    low_series = pd.to_numeric(
        df["Low"],
        errors="coerce",
    )

    for position in range(window, len(df) - window):
        current_high = high_series.iloc[position]
        current_low = low_series.iloc[position]

        if pd.isna(current_high) or pd.isna(current_low):
            continue

        neighbouring_highs = high_series.iloc[
            position - window : position + window + 1
        ]

        neighbouring_lows = low_series.iloc[
            position - window : position + window + 1
        ]

        is_swing_high = (
            current_high == neighbouring_highs.max()
            and (neighbouring_highs == current_high).sum() == 1
        )

        is_swing_low = (
            current_low == neighbouring_lows.min()
            and (neighbouring_lows == current_low).sum() == 1
        )

        timestamp = _resolve_timestamp(df, position)

        if is_swing_high:
            highs.append(
                SwingPoint(
                    index=position,
                    timestamp=timestamp,
                    price=float(current_high),
                    swing_type=SwingType.SWING_HIGH,
                )
            )

        if is_swing_low:
            lows.append(
                SwingPoint(
                    index=position,
                    timestamp=timestamp,
                    price=float(current_low),
                    swing_type=SwingType.SWING_LOW,
                )
            )

    return highs, lows


def classify_swing_highs(
    swing_highs: List[SwingPoint],
) -> List[SwingPoint]:
    """
    Classify swing highs as HH or LH.

    The first swing high remains SH because there is no
    previous swing high available for comparison.
    """

    if not swing_highs:
        return []

    classified = [swing_highs[0]]

    for previous, current in zip(
        swing_highs,
        swing_highs[1:],
    ):
        swing_type = (
            SwingType.HIGHER_HIGH
            if current.price > previous.price
            else SwingType.LOWER_HIGH
        )

        classified.append(
            SwingPoint(
                index=current.index,
                timestamp=current.timestamp,
                price=current.price,
                swing_type=swing_type,
            )
        )

    return classified


def classify_swing_lows(
    swing_lows: List[SwingPoint],
) -> List[SwingPoint]:
    """
    Classify swing lows as HL or LL.

    The first swing low remains SL because there is no
    previous swing low available for comparison.
    """

    if not swing_lows:
        return []

    classified = [swing_lows[0]]

    for previous, current in zip(
        swing_lows,
        swing_lows[1:],
    ):
        swing_type = (
            SwingType.HIGHER_LOW
            if current.price > previous.price
            else SwingType.LOWER_LOW
        )

        classified.append(
            SwingPoint(
                index=current.index,
                timestamp=current.timestamp,
                price=current.price,
                swing_type=swing_type,
            )
        )

    return classified


def detect_and_classify_swings(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect and classify all swing highs and swing lows.

    Returns:
        A tuple containing:
            - classified swing highs
            - classified swing lows
    """

    raw_highs, raw_lows = detect_raw_swings(
        df=df,
        config=config,
    )

    classified_highs = classify_swing_highs(raw_highs)
    classified_lows = classify_swing_lows(raw_lows)

    return classified_highs, classified_lows


def get_latest_swing(
    swings: List[SwingPoint],
) -> Optional[SwingPoint]:
    """
    Return the latest swing point from a swing list.
    """

    if not swings:
        return None

    return swings[-1]


def has_latest_swing_type(
    swings: List[SwingPoint],
    swing_type: SwingType,
) -> bool:
    """
    Check whether the latest swing matches a given type.
    """

    latest = get_latest_swing(swings)

    if latest is None:
        return False

    return latest.swing_type == swing_type