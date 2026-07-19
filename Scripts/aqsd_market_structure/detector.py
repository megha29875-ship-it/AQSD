"""
AQSD
Market Structure Engine

Module: detector.py
Version: 1.1
Author: AQSD

Description:
Detects:

- Break of Structure (BOS)
- Change of Character (CHOCH)

Bullish BOS:
    Price closes above the latest confirmed swing high.

Bearish BOS:
    Price closes below the latest confirmed swing low.

Bearish CHOCH:
    During bullish structure, price closes below the
    latest Higher Low.

Bullish CHOCH:
    During bearish structure, price closes above the
    latest Lower High.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd

from .config import DEFAULT_CONFIG, MarketStructureConfig
from .models import SwingPoint, SwingType
from .swings import detect_and_classify_swings


REQUIRED_COLUMNS = {"High", "Low", "Close"}


class BreakDirection(str, Enum):
    """
    Direction of a detected Break of Structure.
    """

    BULLISH = "BULLISH_BOS"
    BEARISH = "BEARISH_BOS"
    NONE = "NO_BOS"


class ChochDirection(str, Enum):
    """
    Direction of a detected Change of Character.
    """

    BULLISH = "BULLISH_CHOCH"
    BEARISH = "BEARISH_CHOCH"
    NONE = "NO_CHOCH"


@dataclass
class BreakOfStructureResult:
    """
    Result returned by the BOS detector.
    """

    direction: BreakDirection
    detected: bool
    close: float
    broken_level: Optional[float]
    break_timestamp: Optional[datetime]
    reference_swing: Optional[SwingPoint]
    evidence: list[str]


@dataclass
class ChangeOfCharacterResult:
    """
    Result returned by the CHOCH detector.
    """

    direction: ChochDirection
    detected: bool
    close: float
    broken_level: Optional[float]
    break_timestamp: Optional[datetime]
    reference_swing: Optional[SwingPoint]
    previous_structure: str
    evidence: list[str]


def validate_detector_data(
    df: pd.DataFrame,
) -> None:
    """
    Validate data required by BOS and CHOCH detectors.
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

    for column in REQUIRED_COLUMNS:
        numeric_values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        if numeric_values.dropna().empty:
            raise ValueError(
                f"{column} column contains no valid "
                "numeric values."
            )


def _resolve_latest_timestamp(
    df: pd.DataFrame,
) -> datetime:
    """
    Resolve the timestamp of the latest candle.
    """

    latest_index = df.index[-1]

    if isinstance(latest_index, pd.Timestamp):
        return latest_index.to_pydatetime()

    if isinstance(latest_index, datetime):
        return latest_index

    converted = pd.to_datetime(
        latest_index,
        errors="coerce",
    )

    if isinstance(converted, pd.Timestamp):
        return converted.to_pydatetime()

    return datetime.now()


def _get_latest_swing_of_type(
    swings: list[SwingPoint],
    swing_type: SwingType,
) -> Optional[SwingPoint]:
    """
    Return the latest swing matching a given SwingType.
    """

    matching_swings = [
        swing
        for swing in swings
        if swing.swing_type == swing_type
    ]

    if not matching_swings:
        return None

    return max(
        matching_swings,
        key=lambda swing: swing.index,
    )


def _get_latest_close(
    df: pd.DataFrame,
) -> float:
    """
    Return the latest valid Close value.
    """

    latest_close_value = pd.to_numeric(
        pd.Series([df["Close"].iloc[-1]]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(latest_close_value):
        raise ValueError(
            "Latest Close value is invalid."
        )

    return float(
        latest_close_value
    )


def detect_break_of_structure(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> BreakOfStructureResult:
    """
    Detect the latest Break of Structure.

    Bullish BOS:
        Latest close is above the latest confirmed
        swing-high level.

    Bearish BOS:
        Latest close is below the latest confirmed
        swing-low level.
    """

    validate_detector_data(df)
    config.validate()

    swing_highs, swing_lows = (
        detect_and_classify_swings(
            df=df,
            config=config,
        )
    )

    latest_high = (
        max(
            swing_highs,
            key=lambda swing: swing.index,
        )
        if swing_highs
        else None
    )

    latest_low = (
        max(
            swing_lows,
            key=lambda swing: swing.index,
        )
        if swing_lows
        else None
    )

    latest_close = _get_latest_close(
        df
    )

    latest_timestamp = _resolve_latest_timestamp(
        df
    )

    evidence: list[str] = []

    if latest_high is not None:
        evidence.append(
            "Latest confirmed swing high is "
            f"{latest_high.price:.2f}"
        )

    if latest_low is not None:
        evidence.append(
            "Latest confirmed swing low is "
            f"{latest_low.price:.2f}"
        )

    if (
        latest_high is not None
        and latest_close > latest_high.price
    ):
        evidence.append(
            "Latest close is above the latest "
            "confirmed swing high"
        )

        evidence.append(
            f"Bullish BOS confirmed at "
            f"{latest_close:.2f}"
        )

        return BreakOfStructureResult(
            direction=BreakDirection.BULLISH,
            detected=True,
            close=latest_close,
            broken_level=latest_high.price,
            break_timestamp=latest_timestamp,
            reference_swing=latest_high,
            evidence=evidence,
        )

    if (
        latest_low is not None
        and latest_close < latest_low.price
    ):
        evidence.append(
            "Latest close is below the latest "
            "confirmed swing low"
        )

        evidence.append(
            f"Bearish BOS confirmed at "
            f"{latest_close:.2f}"
        )

        return BreakOfStructureResult(
            direction=BreakDirection.BEARISH,
            detected=True,
            close=latest_close,
            broken_level=latest_low.price,
            break_timestamp=latest_timestamp,
            reference_swing=latest_low,
            evidence=evidence,
        )

    evidence.append(
        "Latest close has not broken the latest "
        "confirmed swing high or swing low"
    )

    return BreakOfStructureResult(
        direction=BreakDirection.NONE,
        detected=False,
        close=latest_close,
        broken_level=None,
        break_timestamp=None,
        reference_swing=None,
        evidence=evidence,
    )


def detect_change_of_character(
    df: pd.DataFrame,
    config: MarketStructureConfig = DEFAULT_CONFIG,
) -> ChangeOfCharacterResult:
    """
    Detect the latest Change of Character.

    Bearish CHOCH
    -------------
    A Higher Low exists and the latest close breaks
    below that Higher Low.

    This signals that bullish market structure may be
    transitioning toward bearish structure.

    Bullish CHOCH
    -------------
    A Lower High exists and the latest close breaks
    above that Lower High.

    This signals that bearish market structure may be
    transitioning toward bullish structure.
    """

    validate_detector_data(df)
    config.validate()

    swing_highs, swing_lows = (
        detect_and_classify_swings(
            df=df,
            config=config,
        )
    )

    latest_higher_low = _get_latest_swing_of_type(
        swings=swing_lows,
        swing_type=SwingType.HIGHER_LOW,
    )

    latest_lower_high = _get_latest_swing_of_type(
        swings=swing_highs,
        swing_type=SwingType.LOWER_HIGH,
    )

    latest_close = _get_latest_close(
        df
    )

    latest_timestamp = _resolve_latest_timestamp(
        df
    )

    evidence: list[str] = []

    if latest_higher_low is not None:
        evidence.append(
            "Latest Higher Low is "
            f"{latest_higher_low.price:.2f}"
        )

    if latest_lower_high is not None:
        evidence.append(
            "Latest Lower High is "
            f"{latest_lower_high.price:.2f}"
        )

    bearish_choch = (
        latest_higher_low is not None
        and latest_close < latest_higher_low.price
    )

    bullish_choch = (
        latest_lower_high is not None
        and latest_close > latest_lower_high.price
    )

    if bearish_choch:
        evidence.append(
            "Latest close is below the latest "
            "Higher Low"
        )

        evidence.append(
            "Bullish structure may be changing "
            "to bearish structure"
        )

        return ChangeOfCharacterResult(
            direction=ChochDirection.BEARISH,
            detected=True,
            close=latest_close,
            broken_level=latest_higher_low.price,
            break_timestamp=latest_timestamp,
            reference_swing=latest_higher_low,
            previous_structure="BULLISH",
            evidence=evidence,
        )

    if bullish_choch:
        evidence.append(
            "Latest close is above the latest "
            "Lower High"
        )

        evidence.append(
            "Bearish structure may be changing "
            "to bullish structure"
        )

        return ChangeOfCharacterResult(
            direction=ChochDirection.BULLISH,
            detected=True,
            close=latest_close,
            broken_level=latest_lower_high.price,
            break_timestamp=latest_timestamp,
            reference_swing=latest_lower_high,
            previous_structure="BEARISH",
            evidence=evidence,
        )

    evidence.append(
        "Latest close has not broken the latest "
        "Higher Low or Lower High"
    )

    return ChangeOfCharacterResult(
        direction=ChochDirection.NONE,
        detected=False,
        close=latest_close,
        broken_level=None,
        break_timestamp=None,
        reference_swing=None,
        previous_structure="UNCONFIRMED",
        evidence=evidence,
    )


def has_bullish_bos(
    result: BreakOfStructureResult,
) -> bool:
    """
    Return True when bullish BOS is detected.
    """

    return (
        result.detected
        and result.direction
        == BreakDirection.BULLISH
    )


def has_bearish_bos(
    result: BreakOfStructureResult,
) -> bool:
    """
    Return True when bearish BOS is detected.
    """

    return (
        result.detected
        and result.direction
        == BreakDirection.BEARISH
    )


def has_bullish_choch(
    result: ChangeOfCharacterResult,
) -> bool:
    """
    Return True when bullish CHOCH is detected.
    """

    return (
        result.detected
        and result.direction
        == ChochDirection.BULLISH
    )


def has_bearish_choch(
    result: ChangeOfCharacterResult,
) -> bool:
    """
    Return True when bearish CHOCH is detected.
    """

    return (
        result.detected
        and result.direction
        == ChochDirection.BEARISH
    )