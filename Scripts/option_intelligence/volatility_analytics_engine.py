"""
AQSD
Volatility Analytics Engine

Module: volatility_analytics_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates professional volatility analytics using current ATM IV,
historical IV observations and BANKNIFTY closing-price history.

Outputs:
- IV Rank
- IV Percentile
- Historical Volatility: 10, 20, 30, 60 and 252 sessions
- Volatility Premium
- Volatility Regime
- Volatility Heat Score
- Volatility Trading Signal
- Historical analytics database

Analytics only. No order placement.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIRECTORY = (
    BASE_DIR
    / "Output"
    / "Volatility_Analytics"
)

VOLATILITY_HISTORY_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_VOLATILITY_HISTORY.csv"
)

SUMMARY_JSON_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_VOLATILITY_ANALYTICS.json"
)

SUMMARY_CSV_FILE = (
    OUTPUT_DIRECTORY
    / "BANKNIFTY_VOLATILITY_ANALYTICS.csv"
)

DEFAULT_TRADING_DAYS = 252

IV_RANK_LOOKBACK = 252
IV_PERCENTILE_LOOKBACK = 252

HV_WINDOWS = (
    10,
    20,
    30,
    60,
    252,
)


# ============================================================
# RESULT MODELS
# ============================================================

@dataclass(frozen=True)
class VolatilityAnalyticsSummary:
    """
    Complete volatility analytics summary.
    """

    underlying: str
    timestamp: str

    spot_price: float
    current_atm_iv: float

    iv_history_observations: int
    iv_lookback_low: float | None
    iv_lookback_high: float | None
    iv_rank: float | None
    iv_percentile: float | None

    historical_volatility_10: float | None
    historical_volatility_20: float | None
    historical_volatility_30: float | None
    historical_volatility_60: float | None
    historical_volatility_252: float | None

    volatility_premium_20: float | None
    volatility_premium_60: float | None

    iv_hv_ratio_20: float | None
    iv_hv_ratio_60: float | None

    volatility_regime: str
    volatility_heat_score: float
    mean_reversion_signal: str
    volatility_signal: str

    interpretation: str


@dataclass(frozen=True)
class VolatilityAnalyticsResult:
    """
    Engine output.
    """

    summary: VolatilityAnalyticsSummary
    price_volatility_table: pd.DataFrame
    history_table: pd.DataFrame


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe_float(
    value: Any,
) -> float | None:
    """
    Safely convert a value to float.
    """

    if value is None:
        return None

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if math.isnan(number):
        return None

    if math.isinf(number):
        return None

    return number


def safe_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    """
    Divide safely.
    """

    if numerator is None:
        return None

    if denominator is None:
        return None

    if denominator == 0.0:
        return None

    return numerator / denominator


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """
    Restrict value to a range.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ============================================================
# PRICE HISTORY
# ============================================================

def find_close_column(
    dataframe: pd.DataFrame,
) -> str:
    """
    Identify the close-price column.
    """

    aliases = {
        "close",
        "closingprice",
        "closing_price",
        "last",
        "ltp",
    }

    for column in dataframe.columns:
        normalized = (
            str(column)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("-", "")
        )

        if normalized in aliases:
            return str(column)

    raise ValueError(
        "Could not locate a close-price column."
    )


def clean_price_history(
    price_history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean BANKNIFTY price-history data.
    """

    if price_history.empty:
        raise ValueError(
            "Price-history dataframe is empty."
        )

    close_column = find_close_column(
        price_history
    )

    cleaned = price_history.copy()

    cleaned["Close"] = pd.to_numeric(
        cleaned[close_column],
        errors="coerce",
    )

    cleaned = cleaned.dropna(
        subset=["Close"]
    )

    cleaned = cleaned.loc[
        cleaned["Close"] > 0.0
    ].copy()

    if cleaned.empty:
        raise ValueError(
            "No valid close prices remained."
        )

    if "datetime" in cleaned.columns:
        cleaned["datetime"] = pd.to_datetime(
            cleaned["datetime"],
            errors="coerce",
        )

        cleaned = cleaned.sort_values(
            "datetime"
        )

    elif "date" in cleaned.columns:
        cleaned["date"] = pd.to_datetime(
            cleaned["date"],
            errors="coerce",
        )

        cleaned = cleaned.sort_values(
            "date"
        )

    cleaned = cleaned.reset_index(
        drop=True
    )

    return cleaned


def calculate_log_returns(
    close_prices: pd.Series,
) -> pd.Series:
    """
    Calculate daily logarithmic returns.
    """

    numeric_close = pd.to_numeric(
        close_prices,
        errors="coerce",
    )

    return np.log(
        numeric_close
        / numeric_close.shift(1)
    )


def calculate_historical_volatility(
    log_returns: pd.Series,
    window: int,
    annualization_days: int = DEFAULT_TRADING_DAYS,
) -> float | None:
    """
    Calculate annualized historical volatility.
    """

    clean_returns = pd.to_numeric(
        log_returns,
        errors="coerce",
    ).dropna()

    if clean_returns.empty:
        return None

    if len(clean_returns) < 2:
        return None

    selected_returns = clean_returns.tail(
        window
    )

    if len(selected_returns) < 2:
        return None

    daily_standard_deviation = float(
        selected_returns.std(
            ddof=1
        )
    )

    annualized_volatility = (
        daily_standard_deviation
        * math.sqrt(
            annualization_days
        )
        * 100.0
    )

    return annualized_volatility


def build_price_volatility_table(
    price_history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add returns and rolling volatility columns.
    """

    cleaned = clean_price_history(
        price_history
    )

    cleaned["LogReturn"] = (
        calculate_log_returns(
            cleaned["Close"]
        )
    )

    for window in HV_WINDOWS:
        cleaned[
            f"HV{window}"
        ] = (
            cleaned["LogReturn"]
            .rolling(
                window=window,
                min_periods=2,
            )
            .std(
                ddof=1
            )
            * math.sqrt(
                DEFAULT_TRADING_DAYS
            )
            * 100.0
        )

    return cleaned


# ============================================================
# IV HISTORY
# ============================================================

def load_volatility_history(
    history_file: Path = VOLATILITY_HISTORY_FILE,
) -> pd.DataFrame:
    """
    Load existing volatility history.
    """

    if not history_file.exists():
        return pd.DataFrame()

    try:
        dataframe = pd.read_csv(
            history_file
        )

    except Exception:
        return pd.DataFrame()

    return dataframe


def extract_iv_history(
    history_table: pd.DataFrame,
    current_atm_iv: float,
    lookback: int = IV_RANK_LOOKBACK,
) -> pd.Series:
    """
    Return historical IV observations including current IV.
    """

    values: list[float] = []

    if (
        not history_table.empty
        and "current_atm_iv"
        in history_table.columns
    ):
        historical_values = pd.to_numeric(
            history_table[
                "current_atm_iv"
            ],
            errors="coerce",
        ).dropna()

        values.extend(
            historical_values.tolist()
        )

    values.append(
        float(current_atm_iv)
    )

    series = pd.Series(
        values,
        dtype="float64",
    )

    return series.tail(
        lookback
    ).reset_index(
        drop=True
    )


def calculate_iv_rank(
    current_iv: float,
    historical_iv: pd.Series,
) -> tuple[
    float | None,
    float | None,
    float | None,
]:
    """
    Calculate IV Rank.

    Returns:
        iv_rank, lowest_iv, highest_iv
    """

    clean_history = pd.to_numeric(
        historical_iv,
        errors="coerce",
    ).dropna()

    if clean_history.empty:
        return None, None, None

    lowest_iv = float(
        clean_history.min()
    )

    highest_iv = float(
        clean_history.max()
    )

    denominator = (
        highest_iv
        - lowest_iv
    )

    if denominator == 0.0:
        return 50.0, lowest_iv, highest_iv

    iv_rank = (
        (
            current_iv
            - lowest_iv
        )
        / denominator
        * 100.0
    )

    return (
        clamp(iv_rank),
        lowest_iv,
        highest_iv,
    )


def calculate_iv_percentile(
    current_iv: float,
    historical_iv: pd.Series,
) -> float | None:
    """
    Calculate IV Percentile.
    """

    clean_history = pd.to_numeric(
        historical_iv,
        errors="coerce",
    ).dropna()

    if clean_history.empty:
        return None

    below_current = int(
        (
            clean_history
            < current_iv
        ).sum()
    )

    percentile = (
        below_current
        / len(clean_history)
        * 100.0
    )

    return clamp(
        percentile
    )


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_volatility_regime(
    iv_rank: float | None,
    iv_percentile: float | None,
    current_iv: float,
    hv20: float | None,
) -> str:
    """
    Classify the volatility regime.
    """

    heat_inputs = [
        value
        for value in (
            iv_rank,
            iv_percentile,
        )
        if value is not None
    ]

    relative_score = (
        sum(heat_inputs)
        / len(heat_inputs)
        if heat_inputs
        else 50.0
    )

    if (
        hv20 is not None
        and current_iv
        > hv20 * 1.40
    ):
        relative_score += 10.0

    relative_score = clamp(
        relative_score
    )

    if relative_score < 15.0:
        return "VERY LOW"

    if relative_score < 35.0:
        return "LOW"

    if relative_score < 65.0:
        return "NORMAL"

    if relative_score < 85.0:
        return "HIGH"

    return "EXTREME"


def calculate_volatility_heat_score(
    iv_rank: float | None,
    iv_percentile: float | None,
    current_iv: float,
    hv20: float | None,
    hv60: float | None,
) -> float:
    """
    Calculate a 0–100 volatility heat score.
    """

    components: list[
        tuple[float, float]
    ] = []

    if iv_rank is not None:
        components.append(
            (
                iv_rank,
                0.35,
            )
        )

    if iv_percentile is not None:
        components.append(
            (
                iv_percentile,
                0.35,
            )
        )

    if hv20 is not None:
        premium_score_20 = clamp(
            (
                current_iv
                - hv20
                + 20.0
            )
            * 2.5
        )

        components.append(
            (
                premium_score_20,
                0.20,
            )
        )

    if hv60 is not None:
        premium_score_60 = clamp(
            (
                current_iv
                - hv60
                + 20.0
            )
            * 2.5
        )

        components.append(
            (
                premium_score_60,
                0.10,
            )
        )

    if not components:
        return 50.0

    total_weight = sum(
        weight
        for _, weight in components
    )

    weighted_score = sum(
        score * weight
        for score, weight in components
    )

    return round(
        weighted_score
        / total_weight,
        2,
    )


def determine_mean_reversion_signal(
    current_iv: float,
    iv_rank: float | None,
    iv_percentile: float | None,
    hv20: float | None,
) -> str:
    """
    Estimate volatility mean-reversion direction.
    """

    if (
        iv_rank is not None
        and iv_percentile is not None
    ):
        if (
            iv_rank >= 80.0
            and iv_percentile >= 80.0
        ):
            return "IV MEAN REVERSION DOWN"

        if (
            iv_rank <= 20.0
            and iv_percentile <= 20.0
        ):
            return "IV MEAN REVERSION UP"

    if hv20 is not None:
        if current_iv >= hv20 * 1.35:
            return "IV CONTRACTION WATCH"

        if current_iv <= hv20 * 0.80:
            return "IV EXPANSION WATCH"

    return "NO STRONG MEAN REVERSION"


def determine_volatility_signal(
    current_iv: float,
    iv_rank: float | None,
    iv_percentile: float | None,
    hv20: float | None,
    volatility_premium_20: float | None,
) -> str:
    """
    Generate a volatility strategy signal.
    """

    if (
        iv_rank is not None
        and iv_percentile is not None
    ):
        if (
            iv_rank <= 25.0
            and iv_percentile <= 30.0
        ):
            return "BUY VOLATILITY WATCH"

        if (
            iv_rank >= 75.0
            and iv_percentile >= 70.0
        ):
            return "SELL VOLATILITY WATCH"

    if volatility_premium_20 is not None:
        if volatility_premium_20 >= 8.0:
            return "EXPECT IV CRUSH"

        if volatility_premium_20 <= -5.0:
            return "EXPECT VOL EXPANSION"

    if (
        hv20 is not None
        and current_iv > hv20
    ):
        return "OPTIONS RELATIVELY EXPENSIVE"

    if (
        hv20 is not None
        and current_iv < hv20
    ):
        return "OPTIONS RELATIVELY CHEAP"

    return "NEUTRAL VOLATILITY"


# ============================================================
# INTERPRETATION
# ============================================================

def format_optional(
    value: float | None,
    suffix: str = "%",
) -> str:
    """
    Format an optional number.
    """

    if value is None:
        return "N/A"

    return f"{value:.2f}{suffix}"


def build_interpretation(
    current_iv: float,
    iv_rank: float | None,
    iv_percentile: float | None,
    hv20: float | None,
    volatility_premium_20: float | None,
    regime: str,
    signal: str,
    mean_reversion_signal: str,
) -> str:
    """
    Build a readable volatility interpretation.
    """

    return (
        f"Current ATM IV is {current_iv:.2f}%. "
        f"IV Rank is {format_optional(iv_rank)} and "
        f"IV Percentile is {format_optional(iv_percentile)}. "
        f"Twenty-session historical volatility is "
        f"{format_optional(hv20)}. "
        f"The IV minus HV20 premium is "
        f"{format_optional(volatility_premium_20)}. "
        f"The volatility regime is {regime}. "
        f"The current volatility signal is {signal}. "
        f"Mean-reversion assessment: {mean_reversion_signal}."
    )


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_volatility(
    current_atm_iv: float,
    spot_price: float,
    price_history: pd.DataFrame,
    underlying: str = "BANKNIFTY",
    timestamp: str | None = None,
    history_file: Path = VOLATILITY_HISTORY_FILE,
) -> VolatilityAnalyticsResult:
    """
    Run complete volatility analytics.
    """

    if current_atm_iv <= 0.0:
        raise ValueError(
            "current_atm_iv must be positive."
        )

    if spot_price <= 0.0:
        raise ValueError(
            "spot_price must be positive."
        )

    price_volatility_table = (
        build_price_volatility_table(
            price_history
        )
    )

    log_returns = (
        price_volatility_table[
            "LogReturn"
        ]
    )

    hv_values = {
        window: calculate_historical_volatility(
            log_returns=log_returns,
            window=window,
        )
        for window in HV_WINDOWS
    }

    existing_history = (
        load_volatility_history(
            history_file
        )
    )

    iv_history = extract_iv_history(
        history_table=existing_history,
        current_atm_iv=current_atm_iv,
    )

    (
        iv_rank,
        iv_low,
        iv_high,
    ) = calculate_iv_rank(
        current_iv=current_atm_iv,
        historical_iv=iv_history,
    )

    iv_percentile = calculate_iv_percentile(
        current_iv=current_atm_iv,
        historical_iv=iv_history,
    )

    hv20 = hv_values.get(20)
    hv60 = hv_values.get(60)

    volatility_premium_20 = (
        current_atm_iv - hv20
        if hv20 is not None
        else None
    )

    volatility_premium_60 = (
        current_atm_iv - hv60
        if hv60 is not None
        else None
    )

    iv_hv_ratio_20 = safe_divide(
        current_atm_iv,
        hv20,
    )

    iv_hv_ratio_60 = safe_divide(
        current_atm_iv,
        hv60,
    )

    volatility_regime = (
        classify_volatility_regime(
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            current_iv=current_atm_iv,
            hv20=hv20,
        )
    )

    volatility_heat_score = (
        calculate_volatility_heat_score(
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            current_iv=current_atm_iv,
            hv20=hv20,
            hv60=hv60,
        )
    )

    mean_reversion_signal = (
        determine_mean_reversion_signal(
            current_iv=current_atm_iv,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            hv20=hv20,
        )
    )

    volatility_signal = (
        determine_volatility_signal(
            current_iv=current_atm_iv,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            hv20=hv20,
            volatility_premium_20=(
                volatility_premium_20
            ),
        )
    )

    resolved_timestamp = (
        timestamp
        or datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    interpretation = build_interpretation(
        current_iv=current_atm_iv,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        hv20=hv20,
        volatility_premium_20=(
            volatility_premium_20
        ),
        regime=volatility_regime,
        signal=volatility_signal,
        mean_reversion_signal=(
            mean_reversion_signal
        ),
    )

    summary = VolatilityAnalyticsSummary(
        underlying=underlying,
        timestamp=resolved_timestamp,
        spot_price=float(
            spot_price
        ),
        current_atm_iv=float(
            current_atm_iv
        ),
        iv_history_observations=int(
            len(iv_history)
        ),
        iv_lookback_low=iv_low,
        iv_lookback_high=iv_high,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        historical_volatility_10=(
            hv_values.get(10)
        ),
        historical_volatility_20=hv20,
        historical_volatility_30=(
            hv_values.get(30)
        ),
        historical_volatility_60=hv60,
        historical_volatility_252=(
            hv_values.get(252)
        ),
        volatility_premium_20=(
            volatility_premium_20
        ),
        volatility_premium_60=(
            volatility_premium_60
        ),
        iv_hv_ratio_20=iv_hv_ratio_20,
        iv_hv_ratio_60=iv_hv_ratio_60,
        volatility_regime=(
            volatility_regime
        ),
        volatility_heat_score=(
            volatility_heat_score
        ),
        mean_reversion_signal=(
            mean_reversion_signal
        ),
        volatility_signal=(
            volatility_signal
        ),
        interpretation=interpretation,
    )

    history_row = pd.DataFrame(
        [
            asdict(
                summary
            )
        ]
    )

    if existing_history.empty:
        updated_history = (
            history_row.copy()
        )

    else:
        updated_history = pd.concat(
            [
                existing_history,
                history_row,
            ],
            ignore_index=True,
        )

    return VolatilityAnalyticsResult(
        summary=summary,
        price_volatility_table=(
            price_volatility_table
        ),
        history_table=updated_history,
    )


# ============================================================
# EXPORTS
# ============================================================

def export_volatility_analytics(
    result: VolatilityAnalyticsResult,
    output_directory: Path = OUTPUT_DIRECTORY,
) -> dict[str, Path]:
    """
    Export volatility analytics.
    """

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_row = pd.DataFrame(
        [
            asdict(
                result.summary
            )
        ]
    )

    summary_row.to_csv(
        SUMMARY_CSV_FILE,
        index=False,
    )

    with SUMMARY_JSON_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            asdict(
                result.summary
            ),
            file,
            indent=4,
            ensure_ascii=False,
        )

    result.history_table.to_csv(
        VOLATILITY_HISTORY_FILE,
        index=False,
    )

    price_table_file = (
        output_directory
        / "BANKNIFTY_PRICE_VOLATILITY_TABLE.csv"
    )

    result.price_volatility_table.to_csv(
        price_table_file,
        index=False,
    )

    return {
        "summary_csv": SUMMARY_CSV_FILE,
        "summary_json": SUMMARY_JSON_FILE,
        "history_csv": VOLATILITY_HISTORY_FILE,
        "price_volatility_csv": (
            price_table_file
        ),
    }


# ============================================================
# DISPLAY
# ============================================================

def print_volatility_summary(
    result: VolatilityAnalyticsResult,
) -> None:
    """
    Print volatility analytics.
    """

    summary = result.summary

    print()
    print("=" * 82)
    print(
        "AQSD VOLATILITY ANALYTICS ENGINE"
        .center(82)
    )
    print("=" * 82)

    print(
        f"Underlying              : "
        f"{summary.underlying}"
    )
    print(
        f"Spot Price              : "
        f"{summary.spot_price:,.2f}"
    )
    print(
        f"Current ATM IV          : "
        f"{summary.current_atm_iv:.2f}%"
    )
    print(
        f"IV Observations         : "
        f"{summary.iv_history_observations}"
    )
    print(
        f"IV Lookback Low         : "
        f"{format_optional(summary.iv_lookback_low)}"
    )
    print(
        f"IV Lookback High        : "
        f"{format_optional(summary.iv_lookback_high)}"
    )
    print(
        f"IV Rank                 : "
        f"{format_optional(summary.iv_rank)}"
    )
    print(
        f"IV Percentile           : "
        f"{format_optional(summary.iv_percentile)}"
    )

    print("-" * 82)

    print(
        f"HV 10                   : "
        f"{format_optional(summary.historical_volatility_10)}"
    )
    print(
        f"HV 20                   : "
        f"{format_optional(summary.historical_volatility_20)}"
    )
    print(
        f"HV 30                   : "
        f"{format_optional(summary.historical_volatility_30)}"
    )
    print(
        f"HV 60                   : "
        f"{format_optional(summary.historical_volatility_60)}"
    )
    print(
        f"HV 252                  : "
        f"{format_optional(summary.historical_volatility_252)}"
    )

    print("-" * 82)

    print(
        f"IV-HV20 Premium         : "
        f"{format_optional(summary.volatility_premium_20)}"
    )
    print(
        f"IV-HV60 Premium         : "
        f"{format_optional(summary.volatility_premium_60)}"
    )
    print(
        f"IV/HV20 Ratio           : "
        f"{format_optional(summary.iv_hv_ratio_20, '')}"
    )
    print(
        f"IV/HV60 Ratio           : "
        f"{format_optional(summary.iv_hv_ratio_60, '')}"
    )
    print(
        f"Volatility Regime       : "
        f"{summary.volatility_regime}"
    )
    print(
        f"Volatility Heat Score   : "
        f"{summary.volatility_heat_score:.2f}/100"
    )
    print(
        f"Mean Reversion Signal   : "
        f"{summary.mean_reversion_signal}"
    )
    print(
        f"Volatility Signal       : "
        f"{summary.volatility_signal}"
    )

    print()
    print("Interpretation")
    print("-" * 82)
    print(
        summary.interpretation
    )
    print("=" * 82)


# ============================================================
# SAMPLE TEST
# ============================================================

def build_sample_price_history(
    rows: int = 300,
) -> pd.DataFrame:
    """
    Build reproducible sample BANKNIFTY closes.
    """

    random_generator = (
        np.random.default_rng(
            seed=42
        )
    )

    daily_returns = (
        random_generator.normal(
            loc=0.0003,
            scale=0.0105,
            size=rows,
        )
    )

    close_prices = (
        50000.0
        * np.exp(
            np.cumsum(
                daily_returns
            )
        )
    )

    dates = pd.date_range(
        end=pd.Timestamp.today().normalize(),
        periods=rows,
        freq="B",
    )

    return pd.DataFrame(
        {
            "date": dates,
            "close": close_prices,
        }
    )


def main() -> None:
    """
    Run sample volatility analytics.
    """

    sample_prices = (
        build_sample_price_history()
    )

    result = analyze_volatility(
        current_atm_iv=22.93,
        spot_price=58521.40,
        price_history=sample_prices,
        underlying="BANKNIFTY",
    )

    exported_files = (
        export_volatility_analytics(
            result
        )
    )

    print_volatility_summary(
        result
    )

    print()
    print("Exported Files")
    print("-" * 82)

    for label, path in exported_files.items():
        print(
            f"{label:24} : {path}"
        )

    print()
    print("Status                  : SUCCESS")
    print("=" * 82)


if __name__ == "__main__":
    main()