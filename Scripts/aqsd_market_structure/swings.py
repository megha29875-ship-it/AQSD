"""
AQSD
Market Structure Engine

Module: swings.py
Version: 1.1
Author: AQSD

Description:
Detects swing highs and swing lows and classifies
market structure as:

- SH: Initial Swing High
- SL: Initial Swing Low
- HH: Higher High
- HL: Higher Low
- LH: Lower High
- LL: Lower Low

Equal highs and equal lows remain unclassified raw
swing points because they are neither higher nor lower.
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
    Validate market data required for swing detection.

    Args:
        df: OHLC market-data DataFrame.

    Raises:
        TypeError:
            If the input is not a pandas DataFrame.

        ValueError:
            If the DataFrame is empty, required columns
            are missing, or High/Low contain no usable
            numeric values.
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

    numeric_high = pd.to_numeric(
        df["High"],
        errors="coerce",
    )

    numeric_low = pd.to_numeric(
        df["Low"],
        errors="coerce",
    )

    if numeric_high.dropna().empty:
        raise ValueError(
            "High column contains no valid numeric values."
        )

    if numeric_low.dropna().empty:
        raise ValueError(
            "Low column contains no valid numeric values."
        )


def _resolve_timestamp(
    df: pd.DataFrame,
    index_position: int,
) -> datetime:
    """
    Resolve the timestamp of a detected swing point.

    The DataFrame index is used when it can be converted
    to a valid date and time. Otherwise, the current time
    is used as a fallback.

    Args:
        df: Market-data DataFrame.
        index_position: Integer row position.

    Returns:
        Python datetime object.
    """

    index_value = df.index[index_position]

    if isinstance(index_value, pd.Timestamp):
        return index_value.to_pydatetime()

    if isinstance(index_value, datetime):
        return index_value

    try:
        converted_timestamp = pd.to_datetime(
            index_value,
            errors="raise",
        )

        if isinstance(converted_timestamp, pd.Timestamp):
            return converted_timestamp.to_pydatetime()

    except (TypeError, ValueError, OverflowError):
        pass

    return datetime.now()


def detect_raw_swings(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect raw swing highs and swing lows.

    Swing High
    ----------
    The current High must be the unique highest High
    within the configured left-and-right swing window.

    Swing Low
    ---------
    The current Low must be the unique lowest Low
    within the configured left-and-right swing window.

    A swing is confirmed only after the required number
    of candles has formed to its right. This prevents
    using an incomplete swing point.

    Args:
        df: OHLC market-data DataFrame.
        config: Market Structure configuration.

    Returns:
        Tuple containing:

        1. Raw swing-high list.
        2. Raw swing-low list.

    Raises:
        ValueError:
            If there are insufficient rows for the
            configured swing window.
    """

    validate_price_data(df)
    config.validate()

    window = config.swing_window

    minimum_rows = (
        window * 2
    ) + 1

    if len(df) < minimum_rows:
        raise ValueError(
            "Not enough rows to detect swings. "
            f"Minimum required: {minimum_rows}. "
            f"Rows received: {len(df)}."
        )

    high_series = pd.to_numeric(
        df["High"],
        errors="coerce",
    )

    low_series = pd.to_numeric(
        df["Low"],
        errors="coerce",
    )

    swing_highs: List[SwingPoint] = []
    swing_lows: List[SwingPoint] = []

    first_position = window
    final_position = len(df) - window

    for position in range(
        first_position,
        final_position,
    ):
        current_high = high_series.iloc[position]
        current_low = low_series.iloc[position]

        if (
            pd.isna(current_high)
            or pd.isna(current_low)
        ):
            continue

        start_position = position - window
        end_position = position + window + 1

        neighbouring_highs = high_series.iloc[
            start_position:end_position
        ]

        neighbouring_lows = low_series.iloc[
            start_position:end_position
        ]

        if (
            neighbouring_highs.isna().any()
            or neighbouring_lows.isna().any()
        ):
            continue

        highest_value = neighbouring_highs.max()
        lowest_value = neighbouring_lows.min()

        highest_count = int(
            (neighbouring_highs == highest_value).sum()
        )

        lowest_count = int(
            (neighbouring_lows == lowest_value).sum()
        )

        is_swing_high = (
            current_high == highest_value
            and highest_count == 1
        )

        is_swing_low = (
            current_low == lowest_value
            and lowest_count == 1
        )

        timestamp = _resolve_timestamp(
            df=df,
            index_position=position,
        )

        if is_swing_high:
            swing_highs.append(
                SwingPoint(
                    index=position,
                    timestamp=timestamp,
                    price=float(current_high),
                    swing_type=SwingType.SWING_HIGH,
                )
            )

        if is_swing_low:
            swing_lows.append(
                SwingPoint(
                    index=position,
                    timestamp=timestamp,
                    price=float(current_low),
                    swing_type=SwingType.SWING_LOW,
                )
            )

    return swing_highs, swing_lows


def classify_swing_highs(
    swing_highs: List[SwingPoint],
) -> List[SwingPoint]:
    """
    Classify swing highs as Higher High or Lower High.

    Rules
    -----
    Current high > previous high:
        HIGHER_HIGH

    Current high < previous high:
        LOWER_HIGH

    Current high == previous high:
        SWING_HIGH

    The first detected high remains SWING_HIGH because
    there is no earlier swing high for comparison.

    Args:
        swing_highs: Raw swing-high list.

    Returns:
        Classified swing-high list.
    """

    if not swing_highs:
        return []

    ordered_highs = sorted(
        swing_highs,
        key=lambda swing: swing.index,
    )

    classified_highs: List[SwingPoint] = [
        ordered_highs[0]
    ]

    for previous, current in zip(
        ordered_highs,
        ordered_highs[1:],
    ):
        if current.price > previous.price:
            swing_type = SwingType.HIGHER_HIGH

        elif current.price < previous.price:
            swing_type = SwingType.LOWER_HIGH

        else:
            swing_type = SwingType.SWING_HIGH

        classified_highs.append(
            SwingPoint(
                index=current.index,
                timestamp=current.timestamp,
                price=current.price,
                swing_type=swing_type,
            )
        )

    return classified_highs


def classify_swing_lows(
    swing_lows: List[SwingPoint],
) -> List[SwingPoint]:
    """
    Classify swing lows as Higher Low or Lower Low.

    Rules
    -----
    Current low > previous low:
        HIGHER_LOW

    Current low < previous low:
        LOWER_LOW

    Current low == previous low:
        SWING_LOW

    The first detected low remains SWING_LOW because
    there is no earlier swing low for comparison.

    Args:
        swing_lows: Raw swing-low list.

    Returns:
        Classified swing-low list.
    """

    if not swing_lows:
        return []

    ordered_lows = sorted(
        swing_lows,
        key=lambda swing: swing.index,
    )

    classified_lows: List[SwingPoint] = [
        ordered_lows[0]
    ]

    for previous, current in zip(
        ordered_lows,
        ordered_lows[1:],
    ):
        if current.price > previous.price:
            swing_type = SwingType.HIGHER_LOW

        elif current.price < previous.price:
            swing_type = SwingType.LOWER_LOW

        else:
            swing_type = SwingType.SWING_LOW

        classified_lows.append(
            SwingPoint(
                index=current.index,
                timestamp=current.timestamp,
                price=current.price,
                swing_type=swing_type,
            )
        )

    return classified_lows


def detect_and_classify_swings(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect and classify swing highs and swing lows.

    Args:
        df: OHLC market-data DataFrame.
        config: Market Structure configuration.

    Returns:
        Tuple containing:

        1. Classified swing-high list.
        2. Classified swing-low list.
    """

    raw_highs, raw_lows = detect_raw_swings(
        df=df,
        config=config,
    )

    classified_highs = classify_swing_highs(
        raw_highs
    )

    classified_lows = classify_swing_lows(
        raw_lows
    )

    return classified_highs, classified_lows


def get_latest_swing(
    swings: List[SwingPoint],
) -> Optional[SwingPoint]:
    """
    Return the most recent swing point.

    The function uses the swing index rather than
    assuming the input list is already sorted.

    Args:
        swings: SwingPoint list.

    Returns:
        Latest SwingPoint, or None if the list is empty.
    """

    if not swings:
        return None

    return max(
        swings,
        key=lambda swing: swing.index,
    )


def get_previous_swing(
    swings: List[SwingPoint],
) -> Optional[SwingPoint]:
    """
    Return the swing point immediately before the latest.

    Args:
        swings: SwingPoint list.

    Returns:
        Previous SwingPoint, or None when fewer than two
        swing points are available.
    """

    if len(swings) < 2:
        return None

    ordered_swings = sorted(
        swings,
        key=lambda swing: swing.index,
    )

    return ordered_swings[-2]


def has_latest_swing_type(
    swings: List[SwingPoint],
    swing_type: SwingType,
) -> bool:
    """
    Check whether the latest swing has a specified type.

    Args:
        swings: SwingPoint list.
        swing_type: SwingType to check.

    Returns:
        True when the latest swing matches the requested
        type; otherwise False.
    """

    latest = get_latest_swing(
        swings
    )

    if latest is None:
        return False

    return latest.swing_type == swing_type


def get_latest_structure_pair(
    swing_highs: List[SwingPoint],
    swing_lows: List[SwingPoint],
) -> Tuple[
    Optional[SwingPoint],
    Optional[SwingPoint],
]:
    """
    Return the latest classified swing high and swing low.

    This helper will later be used by the Break of
    Structure and Change of Character modules.

    Args:
        swing_highs: Classified swing-high list.
        swing_lows: Classified swing-low list.

    Returns:
        Tuple containing:

        1. Latest swing high.
        2. Latest swing low.
    """

    latest_high = get_latest_swing(
        swing_highs
    )

    latest_low = get_latest_swing(
        swing_lows
    )

    return latest_high, latest_low