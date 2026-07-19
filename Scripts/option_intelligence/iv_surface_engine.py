"""
AQSD
IV Surface Engine

Module: iv_surface_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates implied volatility for every valid option-chain row,
builds strike-wise CE/PE IV tables, identifies ATM IV, IV skew,
IV smile, average call IV and average put IV.

Analytics only. No order placement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import json
import math

import pandas as pd

from Scripts.option_intelligence.iv_calculator import (
    calculate_implied_volatility,
    days_to_years,
)


BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    BASE_DIR
    / "Output"
    / "IV_Surface"
)

DEFAULT_RISK_FREE_RATE = 0.065
DEFAULT_DIVIDEND_YIELD = 0.0
DEFAULT_DAYS_TO_EXPIRY = 5.0

REQUIRED_COLUMNS = {
    "strikePrice",
    "optionType",
    "LTP",
}


@dataclass(frozen=True)
class IVSurfaceSummary:
    """
    Summary of option-chain implied-volatility analytics.
    """

    underlying: str
    timestamp: str
    spot_price: float
    atm_strike: float
    strike_step: float
    days_to_expiry: float
    time_to_expiry_years: float

    atm_call_iv: float | None
    atm_put_iv: float | None
    atm_iv: float | None

    average_call_iv: float | None
    average_put_iv: float | None
    call_put_iv_spread: float | None

    lower_strike_iv: float | None
    upper_strike_iv: float | None
    iv_skew: float | None
    skew_signal: str

    smile_minimum_iv: float | None
    smile_minimum_strike: float | None
    smile_maximum_iv: float | None
    smile_maximum_strike: float | None

    valid_iv_rows: int
    failed_iv_rows: int
    total_option_rows: int

    volatility_signal: str
    interpretation: str


@dataclass(frozen=True)
class IVSurfaceResult:
    """
    Complete IV Surface Engine output.
    """

    summary: IVSurfaceSummary
    strike_iv_table: pd.DataFrame
    detailed_iv_table: pd.DataFrame
    failed_rows: pd.DataFrame


def safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float safely.
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


def normalize_option_type(
    value: Any,
) -> str | None:
    """
    Normalize option type to CE or PE.
    """

    text = str(value).strip().upper()

    aliases = {
        "CE": "CE",
        "CALL": "CE",
        "C": "CE",
        "PE": "PE",
        "PUT": "PE",
        "P": "PE",
    }

    return aliases.get(text)


def validate_option_chain(
    option_chain: pd.DataFrame,
) -> None:
    """
    Validate the minimum columns required by the engine.
    """

    missing_columns = (
        REQUIRED_COLUMNS
        - set(option_chain.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            "IV Surface Engine is missing required columns: "
            f"{missing_text}"
        )

    if option_chain.empty:
        raise ValueError(
            "Option-chain dataframe is empty."
        )


def nearest_strike(
    strikes: pd.Series,
    target: float,
) -> float:
    """
    Return the strike nearest to the supplied target.
    """

    numeric_strikes = pd.to_numeric(
        strikes,
        errors="coerce",
    ).dropna()

    if numeric_strikes.empty:
        raise ValueError(
            "No valid strike prices were available."
        )

    nearest_index = (
        numeric_strikes
        .sub(target)
        .abs()
        .idxmin()
    )

    return float(
        numeric_strikes.loc[
            nearest_index
        ]
    )


def determine_strike_step(
    strikes: pd.Series,
) -> float:
    """
    Estimate strike interval from available strikes.
    """

    unique_strikes = sorted(
        {
            float(value)
            for value in pd.to_numeric(
                strikes,
                errors="coerce",
            ).dropna()
        }
    )

    if len(unique_strikes) < 2:
        return 0.0

    differences = [
        current - previous
        for previous, current in zip(
            unique_strikes,
            unique_strikes[1:],
        )
        if current > previous
    ]

    if not differences:
        return 0.0

    difference_series = pd.Series(
        differences,
        dtype="float64",
    )

    mode_values = (
        difference_series
        .round(6)
        .mode()
    )

    if not mode_values.empty:
        return float(
            mode_values.iloc[0]
        )

    return float(
        difference_series.median()
    )


def calculate_row_iv(
    row: pd.Series,
    spot_price: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> dict[str, Any]:
    """
    Calculate implied volatility for one option-chain row.
    """

    strike_price = safe_float(
        row.get("strikePrice")
    )

    market_price = safe_float(
        row.get("LTP")
    )

    option_type = normalize_option_type(
        row.get("optionType")
    )

    result: dict[str, Any] = {
        "strikePrice": strike_price,
        "optionType": option_type,
        "LTP": market_price,
        "IV": None,
        "TheoreticalPrice": None,
        "IntrinsicValue": None,
        "TimeValue": None,
        "IVConverged": False,
        "IVIterations": 0,
        "IVMessage": "",
    }

    if strike_price is None:
        result["IVMessage"] = (
            "Invalid strike price."
        )
        return result

    if market_price is None:
        result["IVMessage"] = (
            "Invalid option market price."
        )
        return result

    if option_type is None:
        result["IVMessage"] = (
            "Invalid option type."
        )
        return result

    iv_result = calculate_implied_volatility(
        market_price=market_price,
        spot_price=spot_price,
        strike_price=strike_price,
        time_to_expiry_years=(
            time_to_expiry_years
        ),
        risk_free_rate=risk_free_rate,
        option_type=option_type,
        dividend_yield=dividend_yield,
    )

    result.update(
        {
            "IV": (
                iv_result
                .implied_volatility_percent
            ),
            "TheoreticalPrice": (
                iv_result
                .theoretical_price
            ),
            "IntrinsicValue": (
                iv_result
                .intrinsic_value
            ),
            "TimeValue": (
                iv_result
                .time_value
            ),
            "IVConverged": (
                iv_result
                .converged
            ),
            "IVIterations": (
                iv_result
                .iterations
            ),
            "IVMessage": (
                iv_result
                .message
            ),
        }
    )

    return result


def build_detailed_iv_table(
    option_chain: pd.DataFrame,
    spot_price: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    dividend_yield: float,
) -> pd.DataFrame:
    """
    Calculate IV for every option-chain row.
    """

    rows: list[dict[str, Any]] = []

    for _, row in option_chain.iterrows():
        calculated = calculate_row_iv(
            row=row,
            spot_price=spot_price,
            time_to_expiry_years=(
                time_to_expiry_years
            ),
            risk_free_rate=(
                risk_free_rate
            ),
            dividend_yield=(
                dividend_yield
            ),
        )

        for source_column in (
            "OI",
            "ChangeOI",
            "TotalVolume",
            "expiry",
            "symbol",
        ):
            if source_column in row.index:
                calculated[
                    source_column
                ] = row.get(
                    source_column
                )

        rows.append(
            calculated
        )

    dataframe = pd.DataFrame(
        rows
    )

    if not dataframe.empty:
        dataframe = dataframe.sort_values(
            by=[
                "strikePrice",
                "optionType",
            ],
            na_position="last",
        ).reset_index(
            drop=True
        )

    return dataframe


def build_strike_iv_table(
    detailed_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create one row per strike with CE and PE IV values.
    """

    valid = detailed_table.loc[
        detailed_table["IV"].notna()
    ].copy()

    if valid.empty:
        return pd.DataFrame(
            columns=[
                "strikePrice",
                "CallIV",
                "PutIV",
                "AverageIV",
                "IVDifference",
            ]
        )

    pivot = valid.pivot_table(
        index="strikePrice",
        columns="optionType",
        values="IV",
        aggfunc="mean",
    ).reset_index()

    pivot.columns.name = None

    if "CE" not in pivot.columns:
        pivot["CE"] = pd.NA

    if "PE" not in pivot.columns:
        pivot["PE"] = pd.NA

    pivot = pivot.rename(
        columns={
            "CE": "CallIV",
            "PE": "PutIV",
        }
    )

    pivot["AverageIV"] = pivot[
        [
            "CallIV",
            "PutIV",
        ]
    ].mean(
        axis=1,
        skipna=True,
    )

    pivot["IVDifference"] = (
        pivot["PutIV"]
        - pivot["CallIV"]
    )

    return pivot.sort_values(
        "strikePrice"
    ).reset_index(
        drop=True
    )


def mean_or_none(
    values: pd.Series,
) -> float | None:
    """
    Return mean or None when no values exist.
    """

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric.empty:
        return None

    return float(
        numeric.mean()
    )


def value_at_strike(
    strike_table: pd.DataFrame,
    strike: float,
    column: str,
) -> float | None:
    """
    Return a strike-table value.
    """

    matching = strike_table.loc[
        strike_table[
            "strikePrice"
        ].eq(strike)
    ]

    if matching.empty:
        return None

    return safe_float(
        matching.iloc[0].get(
            column
        )
    )


def nearest_available_average_iv(
    strike_table: pd.DataFrame,
    target_strike: float,
) -> tuple[
    float | None,
    float | None,
]:
    """
    Return nearest strike and its average IV.
    """

    valid = strike_table.loc[
        strike_table[
            "AverageIV"
        ].notna()
    ].copy()

    if valid.empty:
        return None, None

    index = (
        valid["strikePrice"]
        .sub(target_strike)
        .abs()
        .idxmin()
    )

    row = valid.loc[index]

    return (
        safe_float(
            row["strikePrice"]
        ),
        safe_float(
            row["AverageIV"]
        ),
    )


def determine_skew_signal(
    iv_skew: float | None,
) -> str:
    """
    Classify put-call wing skew.
    """

    if iv_skew is None:
        return "NO IV DATA"

    if iv_skew >= 3.0:
        return "STRONG PUT SKEW"

    if iv_skew >= 1.0:
        return "PUT SKEW"

    if iv_skew <= -3.0:
        return "STRONG CALL SKEW"

    if iv_skew <= -1.0:
        return "CALL SKEW"

    return "BALANCED SKEW"


def determine_volatility_signal(
    atm_iv: float | None,
    average_call_iv: float | None,
    average_put_iv: float | None,
) -> str:
    """
    Generate a basic volatility signal.
    """

    if atm_iv is None:
        return "NO IV DATA"

    if atm_iv < 12.0:
        return "LOW VOLATILITY"

    if atm_iv < 18.0:
        return "NORMAL VOLATILITY"

    if atm_iv < 25.0:
        return "ELEVATED VOLATILITY"

    return "HIGH VOLATILITY"


def build_interpretation(
    atm_iv: float | None,
    average_call_iv: float | None,
    average_put_iv: float | None,
    iv_skew: float | None,
    skew_signal: str,
    volatility_signal: str,
) -> str:
    """
    Build human-readable IV interpretation.
    """

    if atm_iv is None:
        return (
            "Implied volatility could not be calculated "
            "reliably from the supplied option-chain prices."
        )

    call_text = (
        "N/A"
        if average_call_iv is None
        else f"{average_call_iv:.2f}%"
    )

    put_text = (
        "N/A"
        if average_put_iv is None
        else f"{average_put_iv:.2f}%"
    )

    skew_text = (
        "N/A"
        if iv_skew is None
        else f"{iv_skew:.2f} percentage points"
    )

    return (
        f"ATM implied volatility is {atm_iv:.2f}%. "
        f"Average call IV is {call_text} and average put IV "
        f"is {put_text}. The measured IV skew is {skew_text}, "
        f"classified as {skew_signal}. Overall volatility "
        f"condition is {volatility_signal}."
    )


def analyze_iv_surface(
    option_chain: pd.DataFrame,
    spot_price: float,
    underlying: str = "BANKNIFTY",
    atm_strike: float | None = None,
    strike_step: float | None = None,
    days_to_expiry: float = (
        DEFAULT_DAYS_TO_EXPIRY
    ),
    risk_free_rate: float = (
        DEFAULT_RISK_FREE_RATE
    ),
    dividend_yield: float = (
        DEFAULT_DIVIDEND_YIELD
    ),
    timestamp: str | None = None,
) -> IVSurfaceResult:
    """
    Run the complete IV Surface Engine.
    """

    validate_option_chain(
        option_chain
    )

    if spot_price <= 0.0:
        raise ValueError(
            "spot_price must be positive."
        )

    working_chain = (
        option_chain.copy()
    )

    working_chain["strikePrice"] = (
        pd.to_numeric(
            working_chain[
                "strikePrice"
            ],
            errors="coerce",
        )
    )

    working_chain["LTP"] = (
        pd.to_numeric(
            working_chain[
                "LTP"
            ],
            errors="coerce",
        )
    )

    working_chain["optionType"] = (
        working_chain[
            "optionType"
        ].apply(
            normalize_option_type
        )
    )

    working_chain = working_chain.dropna(
        subset=[
            "strikePrice",
            "optionType",
            "LTP",
        ]
    ).reset_index(
        drop=True
    )

    if working_chain.empty:
        raise ValueError(
            "No valid option-chain rows remained "
            "after cleaning."
        )

    resolved_strike_step = (
        safe_float(
            strike_step
        )
    )

    if (
        resolved_strike_step is None
        or resolved_strike_step <= 0.0
    ):
        resolved_strike_step = (
            determine_strike_step(
                working_chain[
                    "strikePrice"
                ]
            )
        )

    resolved_atm_strike = (
        safe_float(
            atm_strike
        )
    )

    if resolved_atm_strike is None:
        resolved_atm_strike = (
            nearest_strike(
                working_chain[
                    "strikePrice"
                ],
                spot_price,
            )
        )

    time_to_expiry_years = (
        days_to_years(
            days_to_expiry
        )
    )

    detailed_table = (
        build_detailed_iv_table(
            option_chain=working_chain,
            spot_price=spot_price,
            time_to_expiry_years=(
                time_to_expiry_years
            ),
            risk_free_rate=(
                risk_free_rate
            ),
            dividend_yield=(
                dividend_yield
            ),
        )
    )

    strike_table = (
        build_strike_iv_table(
            detailed_table
        )
    )

    failed_rows = detailed_table.loc[
        detailed_table["IV"].isna()
    ].copy()

    valid_rows = detailed_table.loc[
        detailed_table["IV"].notna()
    ].copy()

    atm_call_iv = value_at_strike(
        strike_table=strike_table,
        strike=resolved_atm_strike,
        column="CallIV",
    )

    atm_put_iv = value_at_strike(
        strike_table=strike_table,
        strike=resolved_atm_strike,
        column="PutIV",
    )

    atm_values = [
        value
        for value in (
            atm_call_iv,
            atm_put_iv,
        )
        if value is not None
    ]

    atm_iv = (
        sum(atm_values)
        / len(atm_values)
        if atm_values
        else None
    )

    average_call_iv = mean_or_none(
        valid_rows.loc[
            valid_rows[
                "optionType"
            ].eq("CE"),
            "IV",
        ]
    )

    average_put_iv = mean_or_none(
        valid_rows.loc[
            valid_rows[
                "optionType"
            ].eq("PE"),
            "IV",
        ]
    )

    call_put_iv_spread = None

    if (
        average_call_iv is not None
        and average_put_iv is not None
    ):
        call_put_iv_spread = (
            average_put_iv
            - average_call_iv
        )

    lower_target = (
        resolved_atm_strike
        - resolved_strike_step * 3.0
    )

    upper_target = (
        resolved_atm_strike
        + resolved_strike_step * 3.0
    )

    _, lower_strike_iv = (
        nearest_available_average_iv(
            strike_table,
            lower_target,
        )
    )

    _, upper_strike_iv = (
        nearest_available_average_iv(
            strike_table,
            upper_target,
        )
    )

    iv_skew = None

    if (
        lower_strike_iv is not None
        and upper_strike_iv is not None
    ):
        iv_skew = (
            lower_strike_iv
            - upper_strike_iv
        )

    skew_signal = determine_skew_signal(
        iv_skew
    )

    volatility_signal = (
        determine_volatility_signal(
            atm_iv=atm_iv,
            average_call_iv=(
                average_call_iv
            ),
            average_put_iv=(
                average_put_iv
            ),
        )
    )

    smile_minimum_iv = None
    smile_minimum_strike = None
    smile_maximum_iv = None
    smile_maximum_strike = None

    valid_smile = strike_table.loc[
        strike_table[
            "AverageIV"
        ].notna()
    ]

    if not valid_smile.empty:
        minimum_index = (
            valid_smile[
                "AverageIV"
            ].idxmin()
        )

        maximum_index = (
            valid_smile[
                "AverageIV"
            ].idxmax()
        )

        minimum_row = (
            valid_smile.loc[
                minimum_index
            ]
        )

        maximum_row = (
            valid_smile.loc[
                maximum_index
            ]
        )

        smile_minimum_iv = safe_float(
            minimum_row[
                "AverageIV"
            ]
        )

        smile_minimum_strike = (
            safe_float(
                minimum_row[
                    "strikePrice"
                ]
            )
        )

        smile_maximum_iv = safe_float(
            maximum_row[
                "AverageIV"
            ]
        )

        smile_maximum_strike = (
            safe_float(
                maximum_row[
                    "strikePrice"
                ]
            )
        )

    interpretation = build_interpretation(
        atm_iv=atm_iv,
        average_call_iv=(
            average_call_iv
        ),
        average_put_iv=(
            average_put_iv
        ),
        iv_skew=iv_skew,
        skew_signal=skew_signal,
        volatility_signal=(
            volatility_signal
        ),
    )

    resolved_timestamp = (
        timestamp
        or datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
    )

    summary = IVSurfaceSummary(
        underlying=underlying,
        timestamp=resolved_timestamp,
        spot_price=float(
            spot_price
        ),
        atm_strike=float(
            resolved_atm_strike
        ),
        strike_step=float(
            resolved_strike_step
        ),
        days_to_expiry=float(
            days_to_expiry
        ),
        time_to_expiry_years=float(
            time_to_expiry_years
        ),
        atm_call_iv=atm_call_iv,
        atm_put_iv=atm_put_iv,
        atm_iv=atm_iv,
        average_call_iv=(
            average_call_iv
        ),
        average_put_iv=(
            average_put_iv
        ),
        call_put_iv_spread=(
            call_put_iv_spread
        ),
        lower_strike_iv=(
            lower_strike_iv
        ),
        upper_strike_iv=(
            upper_strike_iv
        ),
        iv_skew=iv_skew,
        skew_signal=skew_signal,
        smile_minimum_iv=(
            smile_minimum_iv
        ),
        smile_minimum_strike=(
            smile_minimum_strike
        ),
        smile_maximum_iv=(
            smile_maximum_iv
        ),
        smile_maximum_strike=(
            smile_maximum_strike
        ),
        valid_iv_rows=int(
            valid_rows.shape[0]
        ),
        failed_iv_rows=int(
            failed_rows.shape[0]
        ),
        total_option_rows=int(
            detailed_table.shape[0]
        ),
        volatility_signal=(
            volatility_signal
        ),
        interpretation=(
            interpretation
        ),
    )

    return IVSurfaceResult(
        summary=summary,
        strike_iv_table=(
            strike_table
        ),
        detailed_iv_table=(
            detailed_table
        ),
        failed_rows=failed_rows,
    )


def export_iv_surface(
    result: IVSurfaceResult,
    output_directory: Path = OUTPUT_DIR,
    filename_prefix: str = (
        "BANKNIFTY_IV_SURFACE"
    ),
) -> dict[str, Path]:
    """
    Export IV surface outputs.
    """

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    strike_file = (
        output_directory
        / f"{filename_prefix}_Strike_IV.csv"
    )

    detailed_file = (
        output_directory
        / f"{filename_prefix}_Detailed_IV.csv"
    )

    failed_file = (
        output_directory
        / f"{filename_prefix}_Failed_IV.csv"
    )

    summary_file = (
        output_directory
        / f"{filename_prefix}_Summary.json"
    )

    result.strike_iv_table.to_csv(
        strike_file,
        index=False,
    )

    result.detailed_iv_table.to_csv(
        detailed_file,
        index=False,
    )

    result.failed_rows.to_csv(
        failed_file,
        index=False,
    )

    with summary_file.open(
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

    return {
        "strike_iv_csv": strike_file,
        "detailed_iv_csv": (
            detailed_file
        ),
        "failed_iv_csv": failed_file,
        "summary_json": summary_file,
    }


def build_sample_option_chain() -> pd.DataFrame:
    """
    Build sample BANKNIFTY option-chain rows for testing.
    """

    return pd.DataFrame(
        [
            {
                "strikePrice": 58200,
                "optionType": "CE",
                "LTP": 560.00,
                "OI": 125000,
                "ChangeOI": 18000,
                "TotalVolume": 310000,
            },
            {
                "strikePrice": 58200,
                "optionType": "PE",
                "LTP": 225.00,
                "OI": 165000,
                "ChangeOI": 24000,
                "TotalVolume": 390000,
            },
            {
                "strikePrice": 58300,
                "optionType": "CE",
                "LTP": 495.00,
                "OI": 145000,
                "ChangeOI": 22000,
                "TotalVolume": 350000,
            },
            {
                "strikePrice": 58300,
                "optionType": "PE",
                "LTP": 260.00,
                "OI": 180000,
                "ChangeOI": 27000,
                "TotalVolume": 420000,
            },
            {
                "strikePrice": 58400,
                "optionType": "CE",
                "LTP": 435.00,
                "OI": 190000,
                "ChangeOI": 30000,
                "TotalVolume": 475000,
            },
            {
                "strikePrice": 58400,
                "optionType": "PE",
                "LTP": 305.00,
                "OI": 220000,
                "ChangeOI": 35000,
                "TotalVolume": 510000,
            },
            {
                "strikePrice": 58500,
                "optionType": "CE",
                "LTP": 380.00,
                "OI": 260000,
                "ChangeOI": 42000,
                "TotalVolume": 620000,
            },
            {
                "strikePrice": 58500,
                "optionType": "PE",
                "LTP": 355.00,
                "OI": 275000,
                "ChangeOI": 46000,
                "TotalVolume": 650000,
            },
            {
                "strikePrice": 58600,
                "optionType": "CE",
                "LTP": 325.00,
                "OI": 230000,
                "ChangeOI": 31000,
                "TotalVolume": 540000,
            },
            {
                "strikePrice": 58600,
                "optionType": "PE",
                "LTP": 415.00,
                "OI": 245000,
                "ChangeOI": 39000,
                "TotalVolume": 580000,
            },
            {
                "strikePrice": 58700,
                "optionType": "CE",
                "LTP": 280.00,
                "OI": 205000,
                "ChangeOI": 28000,
                "TotalVolume": 490000,
            },
            {
                "strikePrice": 58700,
                "optionType": "PE",
                "LTP": 480.00,
                "OI": 215000,
                "ChangeOI": 33000,
                "TotalVolume": 525000,
            },
            {
                "strikePrice": 58800,
                "optionType": "CE",
                "LTP": 240.00,
                "OI": 175000,
                "ChangeOI": 21000,
                "TotalVolume": 430000,
            },
            {
                "strikePrice": 58800,
                "optionType": "PE",
                "LTP": 550.00,
                "OI": 185000,
                "ChangeOI": 26000,
                "TotalVolume": 470000,
            },
        ]
    )


def print_iv_surface_summary(
    result: IVSurfaceResult,
) -> None:
    """
    Print IV surface summary.
    """

    summary = result.summary

    def formatted(
        value: float | None,
        suffix: str = "%",
    ) -> str:
        if value is None:
            return "N/A"

        return f"{value:.2f}{suffix}"

    print()
    print("=" * 76)
    print("AQSD IV SURFACE ENGINE")
    print("=" * 76)
    print(
        f"Underlying          : "
        f"{summary.underlying}"
    )
    print(
        f"Spot Price          : "
        f"{summary.spot_price:,.2f}"
    )
    print(
        f"ATM Strike          : "
        f"{summary.atm_strike:,.2f}"
    )
    print(
        f"Strike Step         : "
        f"{summary.strike_step:,.2f}"
    )
    print(
        f"Days to Expiry      : "
        f"{summary.days_to_expiry:.2f}"
    )
    print(
        f"ATM Call IV         : "
        f"{formatted(summary.atm_call_iv)}"
    )
    print(
        f"ATM Put IV          : "
        f"{formatted(summary.atm_put_iv)}"
    )
    print(
        f"ATM Combined IV     : "
        f"{formatted(summary.atm_iv)}"
    )
    print(
        f"Average Call IV     : "
        f"{formatted(summary.average_call_iv)}"
    )
    print(
        f"Average Put IV      : "
        f"{formatted(summary.average_put_iv)}"
    )
    print(
        f"Put-Call IV Spread  : "
        f"{formatted(summary.call_put_iv_spread)}"
    )
    print(
        f"IV Skew             : "
        f"{formatted(summary.iv_skew)}"
    )
    print(
        f"Skew Signal         : "
        f"{summary.skew_signal}"
    )
    print(
        f"Volatility Signal   : "
        f"{summary.volatility_signal}"
    )
    print(
        f"Valid IV Rows       : "
        f"{summary.valid_iv_rows}"
    )
    print(
        f"Failed IV Rows      : "
        f"{summary.failed_iv_rows}"
    )
    print()
    print("Interpretation")
    print("-" * 76)
    print(
        summary.interpretation
    )
    print("=" * 76)


def main() -> None:
    """
    Run IV Surface Engine sample test.
    """

    sample_chain = (
        build_sample_option_chain()
    )

    result = analyze_iv_surface(
        option_chain=sample_chain,
        spot_price=58521.40,
        underlying="BANKNIFTY",
        atm_strike=58500.00,
        strike_step=100.00,
        days_to_expiry=5.0,
        risk_free_rate=0.065,
    )

    files = export_iv_surface(
        result
    )

    print_iv_surface_summary(
        result
    )

    print()
    print("Exported Files")
    print("-" * 76)

    for label, path in files.items():
        print(
            f"{label:20} : {path}"
        )

    print()
    print("Status               : SUCCESS")
    print("=" * 76)


if __name__ == "__main__":
    main()