"""
AQSD
Utility Functions

Module    : utils.py
Module ID : CORE-007
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Common utility functions used throughout AQSD.
"""

from __future__ import annotations

import time
import uuid
from functools import wraps
from typing import Any

import numpy as np
import pandas as pd


# ==========================================================
# AQSD ID
# ==========================================================

def generate_aqsd_id(prefix: str = "AQSD") -> str:
    """
    Generate a unique AQSD identifier.
    """

    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


# ==========================================================
# Safe Division
# ==========================================================

def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    """
    Divide safely.
    """

    if denominator in (0, None):
        return default

    return numerator / denominator


# ==========================================================
# Percentage Change
# ==========================================================

def percentage_change(
    old_value: float,
    new_value: float,
) -> float:

    if old_value == 0:
        return 0.0

    return ((new_value - old_value) / old_value) * 100


# ==========================================================
# Rolling Rank
# ==========================================================

def rolling_rank(series: pd.Series) -> pd.Series:
    """
    Return percentile rank.
    """

    return series.rank(pct=True)


# ==========================================================
# Normalize
# ==========================================================

def normalize_series(series: pd.Series) -> pd.Series:
    """
    Normalize between 0 and 1.
    """

    minimum = series.min()
    maximum = series.max()

    if minimum == maximum:
        return pd.Series(
            np.zeros(len(series)),
            index=series.index,
        )

    return (series - minimum) / (maximum - minimum)


# ==========================================================
# Formatting
# ==========================================================

def format_percentage(value: float) -> str:

    return f"{value:.2f}%"


def format_number(value: float) -> str:

    return f"{value:,.2f}"


# ==========================================================
# Timer Decorator
# ==========================================================

def timer(func):
    """
    Measure execution time.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        start = time.perf_counter()

        result = func(*args, **kwargs)

        elapsed = time.perf_counter() - start

        print(
            f"{func.__name__} completed "
            f"in {elapsed:.3f} sec"
        )

        return result

    return wrapper


# ==========================================================
# DataFrame Chunking
# ==========================================================

def chunk_dataframe(
    df: pd.DataFrame,
    size: int,
):
    """
    Yield DataFrame chunks.
    """

    for start in range(0, len(df), size):

        yield df.iloc[start:start + size]


# ==========================================================
# First Non-Null
# ==========================================================

def first_valid(*values: Any):

    for value in values:

        if value is not None:

            return value

    return None