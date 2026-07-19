"""
AQSD
Option Intelligence

Module: volatility_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates option-chain and historical volatility intelligence.

Outputs:
- ATM Implied Volatility
- Average Call IV
- Average Put IV
- Average Option-Chain IV
- Historical Volatility
- IV Rank
- IV Percentile
- IV-HV Spread
- Put-Call IV Skew
- Expected Move
- Volatility Trend
- Volatility Regime
- Volatility Signal
- Interpretation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    load_option_chain,
)


# ============================================================
# CONFIGURATION
# ============================================================

TRADING_DAYS_PER_YEAR = 252

DEFAULT_HV_LOOKBACK = 20
DEFAULT_EXPECTED_MOVE_DAYS = 7

LOW_IV_RANK_THRESHOLD = 20.0
ELEVATED_IV_RANK_THRESHOLD = 50.0
EXTREME_IV_RANK_THRESHOLD = 80.0

IV_EXPENSIVE_SPREAD_THRESHOLD = 5.0
IV_CHEAP_SPREAD_THRESHOLD = -5.0

IV_TREND_FLAT_TOLERANCE = 0.50


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(slots=True)
class VolatilityResult:
    """
    Standard AQSD volatility analytics result.
    """

    spot_price: float
    atm_strike: float

    atm_iv: float | None
    atm_call_iv: float | None
    atm_put_iv: float | None

    average_call_iv: float | None
    average_put_iv: float | None
    average_chain_iv: float | None

    minimum_chain_iv: float | None
    maximum_chain_iv: float | None

    historical_volatility: float | None

    iv_rank: float | None
    iv_percentile: float | None

    iv_hv_spread: float | None
    iv_hv_ratio: float | None

    put_call_iv_skew: float | None
    skew_signal: str

    expected_move_points: float | None
    expected_move_percent: float | None
    expected_move_low: float | None
    expected_move_high: float | None
    expected_move_days: int

    volatility_trend: str
    volatility_regime: str
    volatility_signal: str

    interpretation: str

    hv_lookback_days: int
    historical_iv_observations: int
    valid_iv_contracts: int
    number_of_strikes: int
    timestamp: str


# ============================================================
# GENERIC HELPERS
# ============================================================

def safe_ratio(
    numerator: float,
    denominator: float,
) -> float | None:
    """
    Divide safely and return None when denominator is zero.
    """

    if denominator == 0:
        return None

    return float(numerator / denominator)


def safe_mean(
    values: pd.Series,
) -> float | None:
    """
    Return the mean of valid numeric values.
    """

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return None

    return float(numeric_values.mean())


def safe_minimum(
    values: pd.Series,
) -> float | None:
    """
    Return the minimum valid numeric value.
    """

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return None

    return float(numeric_values.min())


def safe_maximum(
    values: pd.Series,
) -> float | None:
    """
    Return the maximum valid numeric value.
    """

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return None

    return float(numeric_values.max())


def format_optional_number(
    value: float | None,
    decimals: int = 2,
    suffix: str = "",
) -> str:
    """
    Format optional numeric values for terminal output.
    """

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}{suffix}"


# ============================================================
# IV COLUMN HANDLING
# ============================================================

def normalize_column_name(
    column: Any,
) -> str:
    """
    Normalize a DataFrame column name for comparison.
    """

    return (
        str(column)
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def resolve_iv_column(
    dataframe: pd.DataFrame,
) -> str | None:
    """
    Find the implied-volatility column in an option-chain DataFrame.
    """

    aliases = {
        "implied_volatility",
        "impliedvolatility",
        "implied_vol",
        "impliedvol",
        "iv",
        "option_iv",
        "optioniv",
        "volatility",
    }

    normalized_columns = {
        normalize_column_name(column): str(column)
        for column in dataframe.columns
    }

    for alias in aliases:
        normalized_alias = normalize_column_name(alias)

        if normalized_alias in normalized_columns:
            return normalized_columns[normalized_alias]

    return None


def normalize_iv_series(
    values: pd.Series,
) -> pd.Series:
    """
    Convert IV values into percentage form.

    Examples:
        0.185 becomes 18.5
        18.5 remains 18.5
    """

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    )

    numeric_values = numeric_values.where(
        numeric_values > 0
    )

    normalized = numeric_values.apply(
        lambda value: (
            float(value) * 100.0
            if pd.notna(value) and abs(float(value)) <= 3.0
            else float(value)
            if pd.notna(value)
            else math.nan
        )
    )

    return normalized


def prepare_iv_table(
    option_chain_data: OptionChainData,
) -> pd.DataFrame:
    """
    Create a standardized strike-wise IV table.

    The function returns an empty IV column when the source option chain
    does not contain implied volatility.
    """

    option_chain = option_chain_data.option_chain.copy()

    iv_column = resolve_iv_column(option_chain)

    required_columns = [
        "strike",
        "option_type",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in option_chain.columns
    ]

    if missing_columns:
        raise ValueError(
            "Option chain is missing required columns: "
            + ", ".join(missing_columns)
        )

    iv_table = option_chain.copy()

    iv_table["strike"] = pd.to_numeric(
        iv_table["strike"],
        errors="coerce",
    )

    iv_table["option_type"] = (
        iv_table["option_type"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if iv_column is None:
        iv_table["implied_volatility"] = math.nan

    else:
        iv_table["implied_volatility"] = normalize_iv_series(
            iv_table[iv_column]
        )

    iv_table = iv_table.dropna(
        subset=["strike"]
    )

    iv_table = iv_table[
        iv_table["option_type"].isin(
            ["CE", "PE"]
        )
    ].copy()

    return iv_table.sort_values(
        by=[
            "strike",
            "option_type",
        ]
    ).reset_index(drop=True)


# ============================================================
# HISTORICAL VOLATILITY
# ============================================================

def prepare_close_series(
    close_prices: (
        pd.Series
        | pd.DataFrame
        | Iterable[float]
        | None
    ),
) -> pd.Series:
    """
    Convert historical closing prices into a clean numeric Series.
    """

    if close_prices is None:
        return pd.Series(
            dtype="float64"
        )

    if isinstance(
        close_prices,
        pd.DataFrame,
    ):
        possible_columns = [
            "close",
            "Close",
            "closing_price",
            "price",
        ]

        selected_column = next(
            (
                column
                for column in possible_columns
                if column in close_prices.columns
            ),
            None,
        )

        if selected_column is None:
            if close_prices.shape[1] != 1:
                raise ValueError(
                    "Historical price DataFrame must contain a "
                    "'close' column or exactly one data column."
                )

            selected_column = str(
                close_prices.columns[0]
            )

        values = close_prices[
            selected_column
        ]

    elif isinstance(
        close_prices,
        pd.Series,
    ):
        values = close_prices

    else:
        values = pd.Series(
            list(close_prices),
            dtype="float64",
        )

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    numeric_values = numeric_values[
        numeric_values > 0
    ]

    return numeric_values.reset_index(
        drop=True
    )


def calculate_historical_volatility(
    close_prices: (
        pd.Series
        | pd.DataFrame
        | Iterable[float]
        | None
    ),
    lookback_days: int = DEFAULT_HV_LOOKBACK,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float | None:
    """
    Calculate annualized historical volatility using log returns.

    The result is returned as a percentage.
    """

    closes = prepare_close_series(
        close_prices
    )

    if lookback_days < 2:
        raise ValueError(
            "HV lookback must be at least 2 days."
        )

    required_prices = lookback_days + 1

    if len(closes) < required_prices:
        return None

    selected_closes = closes.tail(
        required_prices
    )

    log_returns = (
        selected_closes
        / selected_closes.shift(1)
    ).apply(
        lambda value: (
            math.log(float(value))
            if pd.notna(value) and value > 0
            else math.nan
        )
    ).dropna()

    if len(log_returns) < 2:
        return None

    daily_volatility = float(
        log_returns.std(
            ddof=1
        )
    )

    annualized_volatility = (
        daily_volatility
        * math.sqrt(
            trading_days_per_year
        )
        * 100.0
    )

    return float(
        annualized_volatility
    )


# ============================================================
# IMPLIED VOLATILITY ANALYTICS
# ============================================================

def find_atm_iv_values(
    iv_table: pd.DataFrame,
    atm_strike: float,
) -> tuple[
    float | None,
    float | None,
    float | None,
]:
    """
    Return ATM Call IV, ATM Put IV and combined ATM IV.
    """

    valid_iv = iv_table.dropna(
        subset=[
            "strike",
            "implied_volatility",
        ]
    ).copy()

    if valid_iv.empty:
        return None, None, None

    valid_iv["atm_distance"] = (
        valid_iv["strike"]
        - atm_strike
    ).abs()

    nearest_distance = float(
        valid_iv["atm_distance"].min()
    )

    nearest_rows = valid_iv[
        valid_iv["atm_distance"]
        == nearest_distance
    ].copy()

    call_rows = nearest_rows[
        nearest_rows["option_type"] == "CE"
    ]

    put_rows = nearest_rows[
        nearest_rows["option_type"] == "PE"
    ]

    atm_call_iv = safe_mean(
        call_rows["implied_volatility"]
    )

    atm_put_iv = safe_mean(
        put_rows["implied_volatility"]
    )

    available_values = [
        value
        for value in [
            atm_call_iv,
            atm_put_iv,
        ]
        if value is not None
    ]

    atm_iv = (
        float(
            sum(available_values)
            / len(available_values)
        )
        if available_values
        else None
    )

    return (
        atm_call_iv,
        atm_put_iv,
        atm_iv,
    )


def calculate_iv_rank(
    current_iv: float | None,
    historical_iv: pd.Series,
) -> float | None:
    """
    Calculate IV Rank.

    Formula:
        (Current IV - Historical Minimum)
        ---------------------------------
        (Historical Maximum - Historical Minimum)
    """

    if current_iv is None:
        return None

    valid_history = normalize_iv_series(
        historical_iv
    ).dropna()

    if valid_history.empty:
        return None

    historical_minimum = float(
        valid_history.min()
    )

    historical_maximum = float(
        valid_history.max()
    )

    range_width = (
        historical_maximum
        - historical_minimum
    )

    if range_width == 0:
        return 50.0

    rank = (
        current_iv
        - historical_minimum
    ) / range_width * 100.0

    return round(
        min(
            100.0,
            max(
                0.0,
                rank,
            ),
        ),
        2,
    )


def calculate_iv_percentile(
    current_iv: float | None,
    historical_iv: pd.Series,
) -> float | None:
    """
    Calculate the percentage of historical observations below current IV.
    """

    if current_iv is None:
        return None

    valid_history = normalize_iv_series(
        historical_iv
    ).dropna()

    if valid_history.empty:
        return None

    observations_below = int(
        (
            valid_history
            < current_iv
        ).sum()
    )

    percentile = (
        observations_below
        / len(valid_history)
        * 100.0
    )

    return round(
        float(percentile),
        2,
    )


def calculate_expected_move(
    spot_price: float,
    annualized_iv: float | None,
    days: int = DEFAULT_EXPECTED_MOVE_DAYS,
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
]:
    """
    Estimate a one-standard-deviation expected move.

    Formula:
        Spot × IV × sqrt(days / 365)
    """

    if (
        annualized_iv is None
        or annualized_iv <= 0
        or spot_price <= 0
        or days <= 0
    ):
        return None, None, None, None

    expected_move_points = (
        spot_price
        * annualized_iv
        / 100.0
        * math.sqrt(
            days / 365.0
        )
    )

    expected_move_percent = (
        expected_move_points
        / spot_price
        * 100.0
    )

    expected_move_low = (
        spot_price
        - expected_move_points
    )

    expected_move_high = (
        spot_price
        + expected_move_points
    )

    return (
        round(
            expected_move_points,
            2,
        ),
        round(
            expected_move_percent,
            2,
        ),
        round(
            expected_move_low,
            2,
        ),
        round(
            expected_move_high,
            2,
        ),
    )


# ============================================================
# VOLATILITY INTERPRETATION
# ============================================================

def determine_volatility_trend(
    current_iv: float | None,
    historical_iv: pd.Series,
    flat_tolerance: float = IV_TREND_FLAT_TOLERANCE,
) -> str:
    """
    Compare current IV with the latest historical IV observation.
    """

    if current_iv is None:
        return "NO IV DATA"

    valid_history = normalize_iv_series(
        historical_iv
    ).dropna()

    if valid_history.empty:
        return "NO HISTORY"

    previous_iv = float(
        valid_history.iloc[-1]
    )

    change = (
        current_iv
        - previous_iv
    )

    if abs(change) <= flat_tolerance:
        return "FLAT"

    if change > 0:
        return "RISING"

    return "FALLING"


def determine_volatility_regime(
    iv_rank: float | None,
    atm_iv: float | None,
    historical_volatility: float | None,
) -> str:
    """
    Classify the current volatility environment.
    """

    if iv_rank is not None:
        if iv_rank < LOW_IV_RANK_THRESHOLD:
            return "LOW VOLATILITY"

        if iv_rank < ELEVATED_IV_RANK_THRESHOLD:
            return "NORMAL VOLATILITY"

        if iv_rank < EXTREME_IV_RANK_THRESHOLD:
            return "ELEVATED VOLATILITY"

        return "EXTREME VOLATILITY"

    if (
        atm_iv is None
        or historical_volatility is None
    ):
        return "INSUFFICIENT DATA"

    iv_hv_ratio = safe_ratio(
        atm_iv,
        historical_volatility,
    )

    if iv_hv_ratio is None:
        return "INSUFFICIENT DATA"

    if iv_hv_ratio < 0.85:
        return "LOW VOLATILITY"

    if iv_hv_ratio < 1.20:
        return "NORMAL VOLATILITY"

    if iv_hv_ratio < 1.50:
        return "ELEVATED VOLATILITY"

    return "EXTREME VOLATILITY"


def determine_volatility_signal(
    iv_hv_spread: float | None,
    volatility_trend: str,
) -> str:
    """
    Interpret the relationship between implied and historical volatility.
    """

    if iv_hv_spread is None:
        return "INSUFFICIENT DATA"

    if iv_hv_spread >= IV_EXPENSIVE_SPREAD_THRESHOLD:
        if volatility_trend == "RISING":
            return "IV EXPENSIVE AND EXPANDING"

        return "IV EXPENSIVE"

    if iv_hv_spread <= IV_CHEAP_SPREAD_THRESHOLD:
        if volatility_trend == "FALLING":
            return "IV CHEAP AND CONTRACTING"

        return "IV CHEAP"

    if volatility_trend == "RISING":
        return "VOLATILITY EXPANSION"

    if volatility_trend == "FALLING":
        return "VOLATILITY CONTRACTION"

    return "IV FAIRLY PRICED"


def determine_skew_signal(
    put_call_iv_skew: float | None,
) -> str:
    """
    Interpret ATM Put IV minus ATM Call IV.
    """

    if put_call_iv_skew is None:
        return "NO SKEW DATA"

    if put_call_iv_skew >= 3.0:
        return "STRONG DOWNSIDE HEDGE DEMAND"

    if put_call_iv_skew >= 1.0:
        return "MODERATE DOWNSIDE HEDGE DEMAND"

    if put_call_iv_skew <= -3.0:
        return "STRONG UPSIDE SPECULATION"

    if put_call_iv_skew <= -1.0:
        return "MODERATE UPSIDE SPECULATION"

    return "BALANCED IV SKEW"


def build_interpretation(
    result: VolatilityResult,
) -> str:
    """
    Build a concise human-readable volatility interpretation.
    """

    observations: list[str] = []

    if result.atm_iv is None:
        observations.append(
            "Implied-volatility data is unavailable in the option chain."
        )

    else:
        observations.append(
            f"ATM implied volatility is "
            f"{result.atm_iv:.2f}%."
        )

    if result.historical_volatility is not None:
        observations.append(
            f"{result.hv_lookback_days}-day historical volatility is "
            f"{result.historical_volatility:.2f}%."
        )

    if result.iv_rank is not None:
        observations.append(
            f"IV Rank is {result.iv_rank:.1f}%."
        )

    if result.iv_percentile is not None:
        observations.append(
            f"IV Percentile is {result.iv_percentile:.1f}%."
        )

    observations.append(
        f"The volatility regime is "
        f"{result.volatility_regime.lower()}."
    )

    observations.append(
        f"Volatility signal: "
        f"{result.volatility_signal.lower()}."
    )

    if result.put_call_iv_skew is not None:
        observations.append(
            f"ATM Put minus Call IV skew is "
            f"{result.put_call_iv_skew:+.2f} percentage points, "
            f"indicating {result.skew_signal.lower()}."
        )

    if (
        result.expected_move_low is not None
        and result.expected_move_high is not None
    ):
        observations.append(
            f"The estimated {result.expected_move_days}-day "
            f"one-standard-deviation range is "
            f"{result.expected_move_low:,.0f} to "
            f"{result.expected_move_high:,.0f}."
        )

    return " ".join(
        observations
    )


# ============================================================
# STRIKE-WISE IV TABLE
# ============================================================

def build_strike_iv_table(
    iv_table: pd.DataFrame,
    spot_price: float,
    atm_strike: float,
) -> pd.DataFrame:
    """
    Build one row per strike with Call IV and Put IV.
    """

    calls = (
        iv_table[
            iv_table["option_type"] == "CE"
        ][
            [
                "strike",
                "implied_volatility",
            ]
        ]
        .rename(
            columns={
                "implied_volatility": "call_iv",
            }
        )
        .groupby(
            "strike",
            as_index=False,
        )
        .agg(
            call_iv=(
                "call_iv",
                "mean",
            )
        )
    )

    puts = (
        iv_table[
            iv_table["option_type"] == "PE"
        ][
            [
                "strike",
                "implied_volatility",
            ]
        ]
        .rename(
            columns={
                "implied_volatility": "put_iv",
            }
        )
        .groupby(
            "strike",
            as_index=False,
        )
        .agg(
            put_iv=(
                "put_iv",
                "mean",
            )
        )
    )

    strike_iv_table = pd.merge(
        calls,
        puts,
        on="strike",
        how="outer",
    )

    strike_iv_table["average_iv"] = (
        strike_iv_table[
            [
                "call_iv",
                "put_iv",
            ]
        ].mean(
            axis=1,
            skipna=True,
        )
    )

    strike_iv_table["put_call_iv_skew"] = (
        strike_iv_table["put_iv"]
        - strike_iv_table["call_iv"]
    )

    strike_iv_table["distance_from_spot"] = (
        strike_iv_table["strike"]
        - spot_price
    )

    strike_iv_table["distance_from_atm"] = (
        strike_iv_table["strike"]
        - atm_strike
    )

    strike_iv_table["is_atm"] = (
        strike_iv_table["strike"]
        == atm_strike
    )

    return strike_iv_table.sort_values(
        by="strike"
    ).reset_index(
        drop=True
    )


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_volatility(
    option_chain_data: OptionChainData,
    close_prices: (
        pd.Series
        | pd.DataFrame
        | Iterable[float]
        | None
    ) = None,
    historical_iv: (
        pd.Series
        | Iterable[float]
        | None
    ) = None,
    hv_lookback_days: int = DEFAULT_HV_LOOKBACK,
    expected_move_days: int = DEFAULT_EXPECTED_MOVE_DAYS,
) -> tuple[
    VolatilityResult,
    pd.DataFrame,
]:
    """
    Run the AQSD Volatility Intelligence Engine.
    """

    iv_table = prepare_iv_table(
        option_chain_data
    )

    strike_iv_table = build_strike_iv_table(
        iv_table=iv_table,
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,
    )

    valid_iv_rows = iv_table.dropna(
        subset=[
            "implied_volatility",
        ]
    )

    call_iv_values = valid_iv_rows.loc[
        valid_iv_rows["option_type"] == "CE",
        "implied_volatility",
    ]

    put_iv_values = valid_iv_rows.loc[
        valid_iv_rows["option_type"] == "PE",
        "implied_volatility",
    ]

    all_iv_values = valid_iv_rows[
        "implied_volatility"
    ]

    average_call_iv = safe_mean(
        call_iv_values
    )

    average_put_iv = safe_mean(
        put_iv_values
    )

    average_chain_iv = safe_mean(
        all_iv_values
    )

    minimum_chain_iv = safe_minimum(
        all_iv_values
    )

    maximum_chain_iv = safe_maximum(
        all_iv_values
    )

    (
        atm_call_iv,
        atm_put_iv,
        atm_iv,
    ) = find_atm_iv_values(
        iv_table=iv_table,
        atm_strike=option_chain_data.atm_strike,
    )

    historical_volatility = (
        calculate_historical_volatility(
            close_prices=close_prices,
            lookback_days=hv_lookback_days,
        )
    )

    if historical_iv is None:
        historical_iv_series = pd.Series(
            dtype="float64"
        )

    elif isinstance(
        historical_iv,
        pd.Series,
    ):
        historical_iv_series = historical_iv.copy()

    else:
        historical_iv_series = pd.Series(
            list(historical_iv),
            dtype="float64",
        )

    current_rank_iv = (
        atm_iv
        if atm_iv is not None
        else average_chain_iv
    )

    iv_rank = calculate_iv_rank(
        current_iv=current_rank_iv,
        historical_iv=historical_iv_series,
    )

    iv_percentile = calculate_iv_percentile(
        current_iv=current_rank_iv,
        historical_iv=historical_iv_series,
    )

    if (
        current_rank_iv is not None
        and historical_volatility is not None
    ):
        iv_hv_spread = (
            current_rank_iv
            - historical_volatility
        )

        iv_hv_ratio = safe_ratio(
            current_rank_iv,
            historical_volatility,
        )

    else:
        iv_hv_spread = None
        iv_hv_ratio = None

    if (
        atm_put_iv is not None
        and atm_call_iv is not None
    ):
        put_call_iv_skew = (
            atm_put_iv
            - atm_call_iv
        )

    else:
        put_call_iv_skew = None

    skew_signal = determine_skew_signal(
        put_call_iv_skew
    )

    (
        expected_move_points,
        expected_move_percent,
        expected_move_low,
        expected_move_high,
    ) = calculate_expected_move(
        spot_price=option_chain_data.spot_price,
        annualized_iv=current_rank_iv,
        days=expected_move_days,
    )

    volatility_trend = (
        determine_volatility_trend(
            current_iv=current_rank_iv,
            historical_iv=historical_iv_series,
        )
    )

    volatility_regime = (
        determine_volatility_regime(
            iv_rank=iv_rank,
            atm_iv=current_rank_iv,
            historical_volatility=historical_volatility,
        )
    )

    volatility_signal = (
        determine_volatility_signal(
            iv_hv_spread=iv_hv_spread,
            volatility_trend=volatility_trend,
        )
    )

    result = VolatilityResult(
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,

        atm_iv=atm_iv,
        atm_call_iv=atm_call_iv,
        atm_put_iv=atm_put_iv,

        average_call_iv=average_call_iv,
        average_put_iv=average_put_iv,
        average_chain_iv=average_chain_iv,

        minimum_chain_iv=minimum_chain_iv,
        maximum_chain_iv=maximum_chain_iv,

        historical_volatility=historical_volatility,

        iv_rank=iv_rank,
        iv_percentile=iv_percentile,

        iv_hv_spread=iv_hv_spread,
        iv_hv_ratio=iv_hv_ratio,

        put_call_iv_skew=put_call_iv_skew,
        skew_signal=skew_signal,

        expected_move_points=expected_move_points,
        expected_move_percent=expected_move_percent,
        expected_move_low=expected_move_low,
        expected_move_high=expected_move_high,
        expected_move_days=expected_move_days,

        volatility_trend=volatility_trend,
        volatility_regime=volatility_regime,
        volatility_signal=volatility_signal,

        interpretation="",

        hv_lookback_days=hv_lookback_days,
        historical_iv_observations=int(
            len(
                normalize_iv_series(
                    historical_iv_series
                ).dropna()
            )
        ),
        valid_iv_contracts=int(
            len(valid_iv_rows)
        ),
        number_of_strikes=(
            option_chain_data.number_of_strikes
        ),
        timestamp=option_chain_data.timestamp,
    )

    result.interpretation = build_interpretation(
        result
    )

    return result, strike_iv_table


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def print_volatility_summary(
    result: VolatilityResult,
) -> None:
    """
    Print volatility intelligence in the terminal.
    """

    separator = "=" * 76

    print()
    print(separator)
    print(
        "AQSD OPTION INTELLIGENCE — VOLATILITY ENGINE"
    )
    print(separator)

    print(
        f"Spot Price                 : "
        f"{result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike                 : "
        f"{result.atm_strike:,.2f}"
    )

    print(
        f"ATM IV                     : "
        f"{format_optional_number(result.atm_iv, suffix='%')}"
    )

    print(
        f"ATM Call IV                : "
        f"{format_optional_number(result.atm_call_iv, suffix='%')}"
    )

    print(
        f"ATM Put IV                 : "
        f"{format_optional_number(result.atm_put_iv, suffix='%')}"
    )

    print(
        f"Average Chain IV           : "
        f"{format_optional_number(result.average_chain_iv, suffix='%')}"
    )

    print(
        f"Historical Volatility      : "
        f"{format_optional_number(result.historical_volatility, suffix='%')}"
    )

    print(
        f"IV Rank                    : "
        f"{format_optional_number(result.iv_rank, suffix='%')}"
    )

    print(
        f"IV Percentile              : "
        f"{format_optional_number(result.iv_percentile, suffix='%')}"
    )

    print(
        f"IV-HV Spread               : "
        f"{format_optional_number(result.iv_hv_spread)}"
    )

    print(
        f"IV-HV Ratio                : "
        f"{format_optional_number(result.iv_hv_ratio)}"
    )

    print(
        f"Put-Call IV Skew           : "
        f"{format_optional_number(result.put_call_iv_skew)}"
    )

    print(
        f"Skew Signal                : "
        f"{result.skew_signal}"
    )

    print(
        f"Expected Move Points       : "
        f"{format_optional_number(result.expected_move_points)}"
    )

    print(
        f"Expected Move Percent      : "
        f"{format_optional_number(result.expected_move_percent, suffix='%')}"
    )

    print(
        f"Expected Move Range        : "
        f"{format_optional_number(result.expected_move_low)}"
        f" to "
        f"{format_optional_number(result.expected_move_high)}"
    )

    print(
        f"Volatility Trend           : "
        f"{result.volatility_trend}"
    )

    print(
        f"Volatility Regime          : "
        f"{result.volatility_regime}"
    )

    print(
        f"Volatility Signal          : "
        f"{result.volatility_signal}"
    )

    print(
        f"Valid IV Contracts         : "
        f"{result.valid_iv_contracts}"
    )

    print()
    print("Interpretation")
    print("-" * 76)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SAMPLE TEST DATA
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample option-chain data containing IV.
    """

    sample_data = {
        56500: {
            "ce_oi": 90000,
            "pe_oi": 300000,
            "ce_iv": 17.20,
            "pe_iv": 22.80,
        },
        57000: {
            "ce_oi": 125000,
            "pe_oi": 410000,
            "ce_iv": 16.80,
            "pe_iv": 21.50,
        },
        57500: {
            "ce_oi": 250000,
            "pe_oi": 350000,
            "ce_iv": 17.10,
            "pe_iv": 19.90,
        },
        58000: {
            "ce_oi": 520000,
            "pe_oi": 290000,
            "ce_iv": 18.20,
            "pe_iv": 19.10,
        },
        58500: {
            "ce_oi": 610000,
            "pe_oi": 185000,
            "ce_iv": 19.60,
            "pe_iv": 19.40,
        },
        59000: {
            "ce_oi": 480000,
            "pe_oi": 120000,
            "ce_iv": 21.30,
            "pe_iv": 20.10,
        },
    }

    rows: list[
        dict[str, float | str]
    ] = []

    for strike, values in sample_data.items():
        rows.append(
            {
                "strikePrice": strike,
                "optionType": "CE",
                "OI": values["ce_oi"],
                "ChangeOI": 25000,
                "TotalVolume": 100000,
                "IV": values["ce_iv"],
            }
        )

        rows.append(
            {
                "strikePrice": strike,
                "optionType": "PE",
                "OI": values["pe_oi"],
                "ChangeOI": 30000,
                "TotalVolume": 110000,
                "IV": values["pe_iv"],
            }
        )

    return pd.DataFrame(rows)


def create_sample_close_prices() -> pd.Series:
    """
    Create sample daily closing prices for HV calculation.
    """

    closes = [
        56120.00,
        56240.00,
        56080.00,
        56310.00,
        56520.00,
        56410.00,
        56680.00,
        56820.00,
        56710.00,
        56950.00,
        57120.00,
        57040.00,
        57280.00,
        57410.00,
        57330.00,
        57560.00,
        57620.00,
        57480.00,
        57710.00,
        57820.00,
        57690.00,
        57582.25,
    ]

    return pd.Series(
        closes,
        name="close",
        dtype="float64",
    )


def create_sample_iv_history() -> pd.Series:
    """
    Create sample historical ATM-IV observations.
    """

    iv_history = [
        14.2,
        14.8,
        15.1,
        15.6,
        16.0,
        15.4,
        16.3,
        17.1,
        17.8,
        18.4,
        19.0,
        18.6,
        17.9,
        18.8,
        19.5,
        20.1,
        21.3,
        20.5,
        19.7,
        18.9,
        18.1,
        17.6,
        18.0,
        18.4,
        18.7,
    ]

    return pd.Series(
        iv_history,
        name="atm_iv",
        dtype="float64",
    )


# ============================================================
# INDEPENDENT TEST
# ============================================================

def main() -> None:
    """
    Run an independent Volatility Engine test.
    """

    sample_dataframe = (
        create_sample_option_chain()
    )

    close_prices = (
        create_sample_close_prices()
    )

    historical_iv = (
        create_sample_iv_history()
    )

    option_chain_data = load_option_chain(
        source=sample_dataframe,
        spot_price=57582.25,
    )

    result, strike_iv_table = analyze_volatility(
        option_chain_data=option_chain_data,
        close_prices=close_prices,
        historical_iv=historical_iv,
        hv_lookback_days=20,
        expected_move_days=7,
    )

    print_volatility_summary(
        result
    )

    print("Strike-wise IV Table")
    print("-" * 76)

    print(
        strike_iv_table.to_string(
            index=False
        )
    )

    print()

    metadata = ExportMetadata(
        engine="VOLATILITY",
        underlying="BANKNIFTY_SAMPLE",
        engine_version="1.0",
        rows_processed=len(sample_dataframe),
        status="SUCCESS",
        source="AQSD Sample Option Chain",
        notes=(
            "Independent volatility_engine.py "
            "module test."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "atm_strike": result.atm_strike,
        "atm_iv": result.atm_iv,
        "historical_volatility": (
            result.historical_volatility
        ),
        "iv_rank": result.iv_rank,
        "iv_percentile": (
            result.iv_percentile
        ),
        "iv_hv_spread": (
            result.iv_hv_spread
        ),
        "volatility_trend": (
            result.volatility_trend
        ),
        "volatility_regime": (
            result.volatility_regime
        ),
        "volatility_signal": (
            result.volatility_signal
        ),
    }

    engine_result = EngineResult(
        summary=result,
        table=strike_iv_table,
        history=history_row,
        metadata=metadata,
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_SAMPLE_VOLATILITY"
        ),
    )

    print_export_report(
        export_paths
    )


if __name__ == "__main__":
    main()