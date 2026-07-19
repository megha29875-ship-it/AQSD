"""
AQSD
Option Intelligence

Module: common.py
Version: 1.0

Description:
Shared utility functions used across all AQSD
Option Intelligence engines.
"""

from __future__ import annotations

from datetime import date, datetime
from math import sqrt
from typing import Iterable, Sequence

import pandas as pd


# ============================================================
# BASIC NUMERIC UTILITIES
# ============================================================

def safe_divide(
    numerator: float | int | None,
    denominator: float | int | None,
    default: float | None = None,
) -> float | None:
    """
    Divide safely.

    Returns default when:
    - numerator is None
    - denominator is None
    - denominator is zero
    """

    if numerator is None or denominator is None:
        return default

    if float(denominator) == 0:
        return default

    return float(numerator) / float(denominator)


def percentage_change(
    current_value: float | int | None,
    previous_value: float | int | None,
    default: float | None = None,
) -> float | None:
    """
    Calculate percentage change.
    """

    ratio = safe_divide(
        numerator=(
            float(current_value) - float(previous_value)
            if current_value is not None
            and previous_value is not None
            else None
        ),
        denominator=previous_value,
        default=None,
    )

    if ratio is None:
        return default

    return float(ratio * 100.0)


def percentage_difference(
    value_1: float | int | None,
    value_2: float | int | None,
    default: float | None = None,
) -> float | None:
    """
    Calculate percentage difference between two values.
    """

    if value_1 is None or value_2 is None:
        return default

    first = float(value_1)
    second = float(value_2)

    average = (abs(first) + abs(second)) / 2.0

    if average == 0:
        return default

    return abs(first - second) / average * 100.0


def weighted_average(
    values_and_weights: Sequence[
        tuple[float | int | None, float | int]
    ],
    default: float | None = None,
) -> float | None:
    """
    Calculate weighted average while ignoring None values.
    """

    valid_values: list[tuple[float, float]] = []

    for value, weight in values_and_weights:
        if value is None:
            continue

        numeric_weight = float(weight)

        if numeric_weight <= 0:
            continue

        valid_values.append(
            (
                float(value),
                numeric_weight,
            )
        )

    if not valid_values:
        return default

    total_weight = sum(
        weight for _, weight in valid_values
    )

    if total_weight == 0:
        return default

    weighted_total = sum(
        value * weight
        for value, weight in valid_values
    )

    return float(weighted_total / total_weight)


def clamp(
    value: float | int,
    minimum: float | int,
    maximum: float | int,
) -> float:
    """
    Restrict a value between minimum and maximum.
    """

    numeric_value = float(value)
    minimum_value = float(minimum)
    maximum_value = float(maximum)

    if minimum_value > maximum_value:
        raise ValueError(
            "Minimum cannot be greater than maximum."
        )

    return max(
        minimum_value,
        min(maximum_value, numeric_value),
    )


def normalize_score(
    value: float | int,
    minimum: float | int,
    maximum: float | int,
    output_minimum: float = 0.0,
    output_maximum: float = 100.0,
) -> float:
    """
    Normalize a value into a selected output range.
    """

    numeric_value = float(value)
    minimum_value = float(minimum)
    maximum_value = float(maximum)

    if maximum_value == minimum_value:
        return output_minimum

    ratio = (
        numeric_value - minimum_value
    ) / (
        maximum_value - minimum_value
    )

    normalized = (
        output_minimum
        + ratio
        * (
            output_maximum - output_minimum
        )
    )

    return clamp(
        normalized,
        output_minimum,
        output_maximum,
    )


# ============================================================
# DISTANCE UTILITIES
# ============================================================

def calculate_distance(
    target: float | int | None,
    reference: float | int | None,
) -> float | None:
    """
    Return target minus reference.
    """

    if target is None or reference is None:
        return None

    return float(target) - float(reference)


def calculate_absolute_distance(
    target: float | int | None,
    reference: float | int | None,
) -> float | None:
    """
    Return absolute distance between two values.
    """

    distance = calculate_distance(
        target=target,
        reference=reference,
    )

    if distance is None:
        return None

    return abs(distance)


def calculate_distance_percent(
    target: float | int | None,
    reference: float | int | None,
    default: float | None = None,
) -> float | None:
    """
    Return target-reference distance as percentage of reference.
    """

    distance = calculate_distance(
        target=target,
        reference=reference,
    )

    ratio = safe_divide(
        numerator=distance,
        denominator=reference,
        default=None,
    )

    if ratio is None:
        return default

    return float(ratio * 100.0)


# ============================================================
# STRIKE UTILITIES
# ============================================================

def nearest_strike(
    spot_price: float | int,
    available_strikes: Iterable[
        float | int
    ],
) -> float:
    """
    Find the available strike nearest to spot.
    """

    strikes = [
        float(strike)
        for strike in available_strikes
        if pd.notna(strike)
    ]

    if not strikes:
        raise ValueError(
            "No valid strikes were supplied."
        )

    return min(
        strikes,
        key=lambda strike: abs(
            strike - float(spot_price)
        ),
    )


def get_strike_interval(
    strikes: Iterable[float | int],
) -> float:
    """
    Detect the most common positive strike interval.
    """

    unique_strikes = sorted(
        {
            float(strike)
            for strike in strikes
            if pd.notna(strike)
        }
    )

    if len(unique_strikes) < 2:
        return 0.0

    differences = pd.Series(
        unique_strikes
    ).diff().dropna()

    differences = differences[
        differences > 0
    ]

    if differences.empty:
        return 0.0

    modes = differences.mode()

    if not modes.empty:
        return float(modes.iloc[0])

    return float(differences.median())


def round_to_strike(
    value: float | int,
    strike_interval: float | int,
) -> float:
    """
    Round a value to the nearest strike interval.
    """

    interval = float(strike_interval)

    if interval <= 0:
        raise ValueError(
            "Strike interval must be greater than zero."
        )

    return round(
        float(value) / interval
    ) * interval


def find_atm(
    spot_price: float | int,
    strikes: Iterable[float | int],
) -> float:
    """
    Return the nearest ATM strike.
    """

    return nearest_strike(
        spot_price=spot_price,
        available_strikes=strikes,
    )


def find_itm_strikes(
    spot_price: float | int,
    strikes: Iterable[float | int],
    option_type: str,
) -> list[float]:
    """
    Return ITM strikes for CE or PE.
    """

    normalized_type = normalize_option_type(
        option_type
    )

    valid_strikes = sorted(
        {
            float(strike)
            for strike in strikes
            if pd.notna(strike)
        }
    )

    spot = float(spot_price)

    if normalized_type == "CE":
        return [
            strike
            for strike in valid_strikes
            if strike < spot
        ]

    return [
        strike
        for strike in valid_strikes
        if strike > spot
    ]


def find_otm_strikes(
    spot_price: float | int,
    strikes: Iterable[float | int],
    option_type: str,
) -> list[float]:
    """
    Return OTM strikes for CE or PE.
    """

    normalized_type = normalize_option_type(
        option_type
    )

    valid_strikes = sorted(
        {
            float(strike)
            for strike in strikes
            if pd.notna(strike)
        }
    )

    spot = float(spot_price)

    if normalized_type == "CE":
        return [
            strike
            for strike in valid_strikes
            if strike > spot
        ]

    return [
        strike
        for strike in valid_strikes
        if strike < spot
    ]


# ============================================================
# OPTION-TYPE UTILITIES
# ============================================================

def normalize_option_type(
    value: object,
) -> str:
    """
    Convert different option-type values to CE or PE.
    """

    text = str(value).strip().upper()

    call_values = {
        "CE",
        "CALL",
        "C",
        "CALL OPTION",
        "CALL_OPTION",
    }

    put_values = {
        "PE",
        "PUT",
        "P",
        "PUT OPTION",
        "PUT_OPTION",
    }

    if text in call_values or text.endswith("CE"):
        return "CE"

    if text in put_values or text.endswith("PE"):
        return "PE"

    raise ValueError(
        f"Invalid option type: {value}"
    )


# ============================================================
# STATISTICAL UTILITIES
# ============================================================

def clean_numeric_series(
    values: Iterable[
        float | int | None
    ],
) -> pd.Series:
    """
    Convert values into a clean numeric pandas Series.
    """

    series = pd.Series(
        list(values),
        dtype="object",
    )

    return pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()


def rolling_average(
    values: Iterable[
        float | int | None
    ],
    window: int,
) -> pd.Series:
    """
    Calculate rolling average.
    """

    if window <= 0:
        raise ValueError(
            "Rolling window must be greater than zero."
        )

    series = pd.to_numeric(
        pd.Series(list(values)),
        errors="coerce",
    )

    return series.rolling(
        window=window,
        min_periods=1,
    ).mean()


def mean(
    values: Iterable[
        float | int | None
    ],
) -> float | None:
    """
    Return arithmetic mean.
    """

    series = clean_numeric_series(values)

    if series.empty:
        return None

    return float(series.mean())


def median(
    values: Iterable[
        float | int | None
    ],
) -> float | None:
    """
    Return median.
    """

    series = clean_numeric_series(values)

    if series.empty:
        return None

    return float(series.median())


def standard_deviation(
    values: Iterable[
        float | int | None
    ],
    sample: bool = True,
) -> float | None:
    """
    Return standard deviation.
    """

    series = clean_numeric_series(values)

    if series.empty:
        return None

    degrees_of_freedom = 1 if sample else 0

    if (
        sample
        and len(series) < 2
    ):
        return None

    return float(
        series.std(
            ddof=degrees_of_freedom
        )
    )


def variance(
    values: Iterable[
        float | int | None
    ],
    sample: bool = True,
) -> float | None:
    """
    Return variance.
    """

    series = clean_numeric_series(values)

    if series.empty:
        return None

    degrees_of_freedom = 1 if sample else 0

    if (
        sample
        and len(series) < 2
    ):
        return None

    return float(
        series.var(
            ddof=degrees_of_freedom
        )
    )


def percentile(
    values: Iterable[
        float | int | None
    ],
    percentile_value: float,
) -> float | None:
    """
    Return selected percentile.

    percentile_value must be between 0 and 100.
    """

    if not 0 <= percentile_value <= 100:
        raise ValueError(
            "Percentile must be between 0 and 100."
        )

    series = clean_numeric_series(values)

    if series.empty:
        return None

    return float(
        series.quantile(
            percentile_value / 100.0
        )
    )


def percentile_rank(
    values: Iterable[
        float | int | None
    ],
    current_value: float | int,
) -> float | None:
    """
    Return percentage of observations below or equal
    to the current value.
    """

    series = clean_numeric_series(values)

    if series.empty:
        return None

    rank = (
        series <= float(current_value)
    ).mean() * 100.0

    return float(rank)


def z_score(
    value: float | int,
    values: Iterable[
        float | int | None
    ],
) -> float | None:
    """
    Calculate Z-score of a value.
    """

    series = clean_numeric_series(values)

    if len(series) < 2:
        return None

    average = float(series.mean())
    deviation = float(
        series.std(ddof=1)
    )

    if deviation == 0:
        return 0.0

    return (
        float(value) - average
    ) / deviation


# ============================================================
# TREND AND SHIFT UTILITIES
# ============================================================

def detect_trend(
    current_value: float | int | None,
    previous_value: float | int | None,
    flat_tolerance: float = 0.0,
) -> str:
    """
    Detect rising, falling or flat trend.
    """

    if (
        current_value is None
        or previous_value is None
    ):
        return "INSUFFICIENT DATA"

    difference = (
        float(current_value)
        - float(previous_value)
    )

    if abs(difference) <= float(
        flat_tolerance
    ):
        return "FLAT"

    if difference > 0:
        return "RISING"

    return "FALLING"


def detect_shift(
    current_value: float | int | None,
    previous_value: float | int | None,
    tolerance: float = 0.0,
) -> str:
    """
    Detect upward, downward or stable shift.
    """

    trend = detect_trend(
        current_value=current_value,
        previous_value=previous_value,
        flat_tolerance=tolerance,
    )

    mapping = {
        "RISING": "SHIFTED UP",
        "FALLING": "SHIFTED DOWN",
        "FLAT": "STABLE",
        "INSUFFICIENT DATA": "NO HISTORY",
    }

    return mapping[trend]


def calculate_strength_ratio(
    primary_value: float | int | None,
    secondary_value: float | int | None,
) -> float | None:
    """
    Compare primary value with secondary value.
    """

    return safe_divide(
        numerator=primary_value,
        denominator=secondary_value,
        default=None,
    )


def classify_strength(
    ratio: float | int | None,
) -> str:
    """
    Classify concentration strength.
    """

    if ratio is None:
        return "INSUFFICIENT DATA"

    numeric_ratio = float(ratio)

    if numeric_ratio >= 1.75:
        return "VERY STRONG"

    if numeric_ratio >= 1.35:
        return "STRONG"

    if numeric_ratio >= 1.10:
        return "MODERATE"

    return "WEAK"


def calculate_probability_score(
    weighted_scores: Sequence[
        tuple[float | int | None, float | int]
    ],
    minimum: float = 5.0,
    maximum: float = 95.0,
) -> float:
    """
    Calculate a bounded probability-style score.
    """

    score = weighted_average(
        weighted_scores,
        default=50.0,
    )

    if score is None:
        score = 50.0

    return round(
        clamp(
            score,
            minimum,
            maximum,
        ),
        2,
    )


# ============================================================
# DATE AND EXPIRY UTILITIES
# ============================================================

def parse_date(
    value: str | date | datetime,
) -> date:
    """
    Convert common date formats into a date object.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    parsed = pd.to_datetime(
        value,
        errors="raise",
        dayfirst=True,
    )

    return parsed.date()


def expiry_days(
    expiry_date: str | date | datetime,
    current_date: str | date | datetime | None = None,
) -> int:
    """
    Calculate calendar days until expiry.
    """

    expiry = parse_date(expiry_date)

    if current_date is None:
        current = date.today()
    else:
        current = parse_date(current_date)

    return int(
        (expiry - current).days
    )


def trading_days_to_expiry(
    expiry_date: str | date | datetime,
    current_date: str | date | datetime | None = None,
) -> int:
    """
    Estimate weekdays remaining until expiry.

    Exchange holidays are not excluded.
    """

    expiry = parse_date(expiry_date)

    if current_date is None:
        current = date.today()
    else:
        current = parse_date(current_date)

    if expiry < current:
        return 0

    business_days = pd.bdate_range(
        start=current,
        end=expiry,
    )

    return max(
        len(business_days) - 1,
        0,
    )


# ============================================================
# VOLATILITY UTILITIES
# ============================================================

def annualize_volatility(
    daily_standard_deviation: float | int,
    trading_days: int = 252,
) -> float:
    """
    Annualize daily volatility.
    """

    if trading_days <= 0:
        raise ValueError(
            "Trading days must be greater than zero."
        )

    return float(
        float(daily_standard_deviation)
        * sqrt(trading_days)
    )


def calculate_iv_rank(
    current_iv: float | int,
    historical_iv: Iterable[
        float | int | None
    ],
) -> float | None:
    """
    Calculate IV Rank.

    Formula:
    (Current IV - Minimum IV)
    / (Maximum IV - Minimum IV) * 100
    """

    series = clean_numeric_series(
        historical_iv
    )

    if series.empty:
        return None

    minimum_iv = float(series.min())
    maximum_iv = float(series.max())

    if maximum_iv == minimum_iv:
        return 0.0

    rank = (
        float(current_iv) - minimum_iv
    ) / (
        maximum_iv - minimum_iv
    ) * 100.0

    return round(
        clamp(rank, 0.0, 100.0),
        2,
    )


def calculate_iv_percentile(
    current_iv: float | int,
    historical_iv: Iterable[
        float | int | None
    ],
) -> float | None:
    """
    Calculate IV Percentile.
    """

    rank = percentile_rank(
        values=historical_iv,
        current_value=current_iv,
    )

    if rank is None:
        return None

    return round(rank, 2)


# ============================================================
# FORMATTING UTILITIES
# ============================================================

def format_price(
    value: float | int | None,
    decimals: int = 2,
) -> str:
    """
    Format price value.
    """

    if value is None:
        return "N/A"

    return f"{float(value):,.{decimals}f}"


def format_percent(
    value: float | int | None,
    decimals: int = 2,
) -> str:
    """
    Format percentage value.
    """

    if value is None:
        return "N/A"

    return f"{float(value):.{decimals}f}%"


def format_ratio(
    value: float | int | None,
    decimals: int = 3,
) -> str:
    """
    Format ratio value.
    """

    if value is None:
        return "N/A"

    return f"{float(value):.{decimals}f}"


def format_oi(
    value: float | int | None,
) -> str:
    """
    Format Open Interest.
    """

    if value is None:
        return "N/A"

    numeric_value = float(value)

    if abs(numeric_value) >= 10_000_000:
        return (
            f"{numeric_value / 10_000_000:.2f} Cr"
        )

    if abs(numeric_value) >= 100_000:
        return (
            f"{numeric_value / 100_000:.2f} L"
        )

    if abs(numeric_value) >= 1_000:
        return (
            f"{numeric_value / 1_000:.2f} K"
        )

    return f"{numeric_value:,.0f}"


def format_volume(
    value: float | int | None,
) -> str:
    """
    Format traded volume.
    """

    return format_oi(value)


def signal_colour(
    signal: str,
) -> str:
    """
    Return standard AQSD colour name for a signal.
    """

    normalized_signal = (
        str(signal)
        .strip()
        .upper()
    )

    bullish_words = {
        "BULLISH",
        "STRONGLY BULLISH",
        "RISING",
        "SHIFTED UP",
        "STRONG SUPPORT",
        "BUY",
    }

    bearish_words = {
        "BEARISH",
        "STRONGLY BEARISH",
        "FALLING",
        "SHIFTED DOWN",
        "STRONG RESISTANCE",
        "SELL",
    }

    neutral_words = {
        "NEUTRAL",
        "FLAT",
        "STABLE",
        "NO SIGNAL",
        "NO HISTORY",
        "INSUFFICIENT DATA",
    }

    if normalized_signal in bullish_words:
        return "GREEN"

    if normalized_signal in bearish_words:
        return "RED"

    if normalized_signal in neutral_words:
        return "GREY"

    return "AMBER"


# ============================================================
# TEST
# ============================================================

def main() -> None:
    """
    Test common utilities.
    """

    print()
    print("=" * 72)
    print("AQSD OPTION INTELLIGENCE — COMMON UTILITIES")
    print("=" * 72)

    print(
        f"Safe Divide              : "
        f"{safe_divide(120, 80)}"
    )

    print(
        f"Percentage Change        : "
        f"{percentage_change(110, 100):.2f}%"
    )

    print(
        f"Weighted Average         : "
        f"{weighted_average([(1.2, 0.5), (0.8, 0.5)]):.3f}"
    )

    print(
        f"Nearest Strike           : "
        f"{nearest_strike(57582.25, [57000, 57500, 58000])}"
    )

    print(
        f"Strike Interval          : "
        f"{get_strike_interval([57000, 57500, 58000])}"
    )

    print(
        f"Trend                    : "
        f"{detect_trend(1.10, 0.95, 0.03)}"
    )

    print(
        f"IV Rank                  : "
        f"{calculate_iv_rank(18, [12, 14, 16, 20, 24])}%"
    )

    print(
        f"IV Percentile            : "
        f"{calculate_iv_percentile(18, [12, 14, 16, 20, 24])}%"
    )

    print(
        f"Formatted OI             : "
        f"{format_oi(1_250_000)}"
    )

    print(
        f"Signal Colour            : "
        f"{signal_colour('BULLISH')}"
    )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()