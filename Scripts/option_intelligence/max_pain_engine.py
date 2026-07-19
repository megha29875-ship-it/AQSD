"""
AQSD
Option Intelligence

Module: max_pain_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates Max Pain and option-expiry pinning intelligence.

Outputs:
- Max Pain Strike
- Call Pain
- Put Pain
- Total Pain
- Distance from Spot
- Pain Shift
- Magnet Strength
- Pinning Probability
- Expiry Bias
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    load_option_chain,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "Output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(slots=True)
class MaxPainResult:
    spot_price: float
    atm_strike: float
    max_pain_strike: float

    distance_from_spot: float
    distance_from_spot_percent: float
    distance_from_atm: float

    minimum_total_pain: float
    second_lowest_pain: float | None
    pain_gap_percent: float | None

    pinning_probability: float
    magnet_strength: str
    expiry_bias: str
    pain_shift: str

    interpretation: str
    number_of_strikes: int
    timestamp: str


# ============================================================
# PAIN CALCULATION
# ============================================================

def calculate_call_pain(
    settlement_strike: float,
    option_chain_data: OptionChainData,
) -> float:
    """
    Calculate total Call writer pain at a settlement strike.

    Call intrinsic value:
        max(settlement - call strike, 0)
    """

    calls = option_chain_data.calls_df.copy()

    intrinsic_value = (
        settlement_strike - calls["strike"]
    ).clip(lower=0.0)

    pain = intrinsic_value * calls["open_interest"]

    return float(pain.sum())


def calculate_put_pain(
    settlement_strike: float,
    option_chain_data: OptionChainData,
) -> float:
    """
    Calculate total Put writer pain at a settlement strike.

    Put intrinsic value:
        max(put strike - settlement, 0)
    """

    puts = option_chain_data.puts_df.copy()

    intrinsic_value = (
        puts["strike"] - settlement_strike
    ).clip(lower=0.0)

    pain = intrinsic_value * puts["open_interest"]

    return float(pain.sum())


def build_max_pain_table(
    option_chain_data: OptionChainData,
) -> pd.DataFrame:
    """
    Calculate Call Pain, Put Pain and Total Pain
    for every available settlement strike.
    """

    settlement_strikes = sorted(
        option_chain_data.option_chain[
            "strike"
        ].dropna().unique()
    )

    rows: list[dict[str, float]] = []

    for settlement_strike in settlement_strikes:
        settlement = float(settlement_strike)

        call_pain = calculate_call_pain(
            settlement_strike=settlement,
            option_chain_data=option_chain_data,
        )

        put_pain = calculate_put_pain(
            settlement_strike=settlement,
            option_chain_data=option_chain_data,
        )

        total_pain = call_pain + put_pain

        rows.append(
            {
                "settlement_strike": settlement,
                "call_pain": call_pain,
                "put_pain": put_pain,
                "total_pain": total_pain,
                "distance_from_spot": (
                    settlement
                    - option_chain_data.spot_price
                ),
                "absolute_distance_from_spot": abs(
                    settlement
                    - option_chain_data.spot_price
                ),
            }
        )

    pain_table = pd.DataFrame(rows)

    if pain_table.empty:
        raise ValueError(
            "Max Pain table could not be created."
        )

    minimum_pain = float(
        pain_table["total_pain"].min()
    )

    pain_table["pain_above_minimum"] = (
        pain_table["total_pain"] - minimum_pain
    )

    if minimum_pain > 0:
        pain_table["pain_above_minimum_percent"] = (
            pain_table["pain_above_minimum"]
            / minimum_pain
            * 100.0
        )
    else:
        pain_table["pain_above_minimum_percent"] = 0.0

    return pain_table.sort_values(
        "settlement_strike"
    ).reset_index(drop=True)


# ============================================================
# PINNING INTELLIGENCE
# ============================================================

def calculate_pain_gap_percent(
    pain_table: pd.DataFrame,
) -> tuple[float | None, float | None]:
    """
    Compare the minimum pain with the second-lowest pain.

    A larger gap indicates a stronger Max Pain magnet.
    """

    sorted_pain = (
        pain_table["total_pain"]
        .dropna()
        .sort_values()
        .reset_index(drop=True)
    )

    if sorted_pain.empty:
        return None, None

    minimum_pain = float(sorted_pain.iloc[0])

    if len(sorted_pain) < 2:
        return None, None

    second_lowest = float(sorted_pain.iloc[1])

    if minimum_pain == 0:
        return second_lowest, None

    gap_percent = (
        second_lowest - minimum_pain
    ) / minimum_pain * 100.0

    return second_lowest, float(gap_percent)


def calculate_pinning_probability(
    spot_price: float,
    max_pain_strike: float,
    strike_step: float,
    pain_gap_percent: float | None,
) -> float:
    """
    Estimate expiry pinning probability.

    Inputs:
    - Distance between spot and Max Pain.
    - Strike interval.
    - Separation between lowest and second-lowest pain.

    This is an AQSD analytical score, not a guaranteed probability.
    """

    if strike_step <= 0:
        strike_step = max(
            abs(spot_price - max_pain_strike),
            1.0,
        )

    distance_in_steps = (
        abs(spot_price - max_pain_strike)
        / strike_step
    )

    distance_score = max(
        0.0,
        100.0 - distance_in_steps * 22.0,
    )

    if pain_gap_percent is None:
        gap_score = 35.0
    else:
        gap_score = min(
            100.0,
            max(0.0, pain_gap_percent * 4.0),
        )

    probability = (
        distance_score * 0.65
        + gap_score * 0.35
    )

    return round(
        min(95.0, max(5.0, probability)),
        2,
    )


def determine_magnet_strength(
    pinning_probability: float,
) -> str:
    """
    Convert pinning probability into magnet strength.
    """

    if pinning_probability >= 75:
        return "VERY STRONG"

    if pinning_probability >= 60:
        return "STRONG"

    if pinning_probability >= 45:
        return "MODERATE"

    if pinning_probability >= 30:
        return "WEAK"

    return "VERY WEAK"


def determine_expiry_bias(
    spot_price: float,
    max_pain_strike: float,
    strike_step: float,
) -> str:
    """
    Determine directional pull toward Max Pain.
    """

    difference = max_pain_strike - spot_price

    tolerance = (
        strike_step * 0.25
        if strike_step > 0
        else max(abs(spot_price) * 0.001, 1.0)
    )

    if abs(difference) <= tolerance:
        return "NEUTRAL PINNING"

    if difference > 0:
        return "BULLISH PINNING PULL"

    return "BEARISH PINNING PULL"


# ============================================================
# PAIN SHIFT
# ============================================================

def determine_pain_shift(
    max_pain_strike: float,
    history_file: Path,
) -> str:
    """
    Compare current Max Pain with the latest historical value.
    """

    if not history_file.exists():
        return "NO HISTORY"

    try:
        history = pd.read_csv(history_file)
    except (
        OSError,
        ValueError,
        pd.errors.ParserError,
    ):
        return "NO HISTORY"

    if (
        history.empty
        or "max_pain_strike"
        not in history.columns
    ):
        return "NO HISTORY"

    previous_values = pd.to_numeric(
        history["max_pain_strike"],
        errors="coerce",
    ).dropna()

    if previous_values.empty:
        return "NO HISTORY"

    previous_max_pain = float(
        previous_values.iloc[-1]
    )

    if max_pain_strike > previous_max_pain:
        return "SHIFTED UP"

    if max_pain_strike < previous_max_pain:
        return "SHIFTED DOWN"

    return "STABLE"


# ============================================================
# INTERPRETATION
# ============================================================

def build_interpretation(
    result: MaxPainResult,
) -> str:
    """
    Build a concise Max Pain interpretation.
    """

    observations: list[str] = []

    observations.append(
        f"Max Pain is located at "
        f"{result.max_pain_strike:,.0f}."
    )

    if result.expiry_bias == "BULLISH PINNING PULL":
        observations.append(
            "The Max Pain level is above spot, creating an upward expiry pull."
        )

    elif result.expiry_bias == "BEARISH PINNING PULL":
        observations.append(
            "The Max Pain level is below spot, creating a downward expiry pull."
        )

    else:
        observations.append(
            "Spot is already close to Max Pain, supporting neutral pinning."
        )

    observations.append(
        f"Pinning probability is "
        f"{result.pinning_probability:.1f}% "
        f"with {result.magnet_strength.lower()} magnet strength."
    )

    if result.pain_shift == "SHIFTED UP":
        observations.append(
            "Max Pain has shifted upward from the previous reading."
        )

    elif result.pain_shift == "SHIFTED DOWN":
        observations.append(
            "Max Pain has shifted downward from the previous reading."
        )

    elif result.pain_shift == "STABLE":
        observations.append(
            "Max Pain is stable compared with the previous reading."
        )

    else:
        observations.append(
            "No previous Max Pain reading is available."
        )

    return " ".join(observations)


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_max_pain(
    option_chain_data: OptionChainData,
    history_file: Path | None = None,
) -> tuple[MaxPainResult, pd.DataFrame]:
    """
    Run the AQSD Max Pain Engine.
    """

    if history_file is None:
        history_file = (
            OUTPUT_DIR
            / "BANKNIFTY_MaxPain_History.csv"
        )

    pain_table = build_max_pain_table(
        option_chain_data
    )

    minimum_row = pain_table.loc[
        pain_table["total_pain"].idxmin()
    ]

    max_pain_strike = float(
        minimum_row["settlement_strike"]
    )

    minimum_total_pain = float(
        minimum_row["total_pain"]
    )

    second_lowest_pain, pain_gap_percent = (
        calculate_pain_gap_percent(
            pain_table
        )
    )

    distance_from_spot = (
        max_pain_strike
        - option_chain_data.spot_price
    )

    if option_chain_data.spot_price != 0:
        distance_from_spot_percent = (
            distance_from_spot
            / option_chain_data.spot_price
            * 100.0
        )
    else:
        distance_from_spot_percent = 0.0

    distance_from_atm = (
        max_pain_strike
        - option_chain_data.atm_strike
    )

    pinning_probability = (
        calculate_pinning_probability(
            spot_price=option_chain_data.spot_price,
            max_pain_strike=max_pain_strike,
            strike_step=option_chain_data.strike_step,
            pain_gap_percent=pain_gap_percent,
        )
    )

    magnet_strength = determine_magnet_strength(
        pinning_probability
    )

    expiry_bias = determine_expiry_bias(
        spot_price=option_chain_data.spot_price,
        max_pain_strike=max_pain_strike,
        strike_step=option_chain_data.strike_step,
    )

    pain_shift = determine_pain_shift(
        max_pain_strike=max_pain_strike,
        history_file=history_file,
    )

    result = MaxPainResult(
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,
        max_pain_strike=max_pain_strike,
        distance_from_spot=float(
            distance_from_spot
        ),
        distance_from_spot_percent=float(
            distance_from_spot_percent
        ),
        distance_from_atm=float(
            distance_from_atm
        ),
        minimum_total_pain=minimum_total_pain,
        second_lowest_pain=second_lowest_pain,
        pain_gap_percent=pain_gap_percent,
        pinning_probability=pinning_probability,
        magnet_strength=magnet_strength,
        expiry_bias=expiry_bias,
        pain_shift=pain_shift,
        interpretation="",
        number_of_strikes=(
            option_chain_data.number_of_strikes
        ),
        timestamp=option_chain_data.timestamp,
    )

    result.interpretation = build_interpretation(
        result
    )

    return result, pain_table


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================

def result_to_dataframe(
    result: MaxPainResult,
) -> pd.DataFrame:
    """
    Convert Max Pain result into a two-column table.
    """

    result_dictionary = asdict(result)

    return pd.DataFrame(
        {
            "metric": result_dictionary.keys(),
            "value": result_dictionary.values(),
        }
    )


def append_max_pain_history(
    result: MaxPainResult,
    history_file: Path,
) -> Path:
    """
    Append Max Pain result to history.
    """

    history_row = pd.DataFrame(
        [
            {
                "timestamp": result.timestamp,
                "spot_price": result.spot_price,
                "atm_strike": result.atm_strike,
                "max_pain_strike": (
                    result.max_pain_strike
                ),
                "distance_from_spot": (
                    result.distance_from_spot
                ),
                "pinning_probability": (
                    result.pinning_probability
                ),
                "magnet_strength": (
                    result.magnet_strength
                ),
                "expiry_bias": result.expiry_bias,
                "pain_shift": result.pain_shift,
            }
        ]
    )

    if history_file.exists():
        history_row.to_csv(
            history_file,
            mode="a",
            header=False,
            index=False,
        )
    else:
        history_row.to_csv(
            history_file,
            index=False,
        )

    return history_file


def save_max_pain_outputs(
    result: MaxPainResult,
    pain_table: pd.DataFrame,
    prefix: str = "BANKNIFTY",
) -> dict[str, Path]:
    """
    Save Max Pain outputs to CSV and Excel.
    """

    safe_prefix = (
        prefix.strip()
        .upper()
        .replace(" ", "_")
        .replace(":", "_")
    )

    summary_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_MaxPain_Summary.csv"
    )

    pain_table_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_MaxPain_Table.csv"
    )

    history_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_MaxPain_History.csv"
    )

    excel_file = (
        OUTPUT_DIR
        / f"{safe_prefix}_MaxPain.xlsx"
    )

    summary_dataframe = result_to_dataframe(
        result
    )

    summary_dataframe.to_csv(
        summary_csv,
        index=False,
    )

    pain_table.to_csv(
        pain_table_csv,
        index=False,
    )

    append_max_pain_history(
        result=result,
        history_file=history_csv,
    )

    history_dataframe = pd.read_csv(
        history_csv
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="Max Pain Summary",
            index=False,
        )

        pain_table.to_excel(
            writer,
            sheet_name="Pain Table",
            index=False,
        )

        history_dataframe.to_excel(
            writer,
            sheet_name="Max Pain History",
            index=False,
        )

    return {
        "summary_csv": summary_csv,
        "pain_table_csv": pain_table_csv,
        "history_csv": history_csv,
        "excel": excel_file,
    }


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def format_optional_number(
    value: float | None,
    decimals: int = 2,
) -> str:
    """
    Format an optional numeric value.
    """

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}"


def print_max_pain_summary(
    result: MaxPainResult,
) -> None:
    """
    Print Max Pain intelligence.
    """

    separator = "=" * 72

    print()
    print(separator)
    print(
        "AQSD OPTION INTELLIGENCE — MAX PAIN ENGINE"
    )
    print(separator)

    print(
        f"Spot Price               : "
        f"{result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike               : "
        f"{result.atm_strike:,.2f}"
    )

    print(
        f"Max Pain Strike          : "
        f"{result.max_pain_strike:,.2f}"
    )

    print(
        f"Distance from Spot       : "
        f"{result.distance_from_spot:,.2f}"
    )

    print(
        f"Distance from Spot %     : "
        f"{result.distance_from_spot_percent:.3f}%"
    )

    print(
        f"Distance from ATM        : "
        f"{result.distance_from_atm:,.2f}"
    )

    print(
        f"Minimum Total Pain       : "
        f"{result.minimum_total_pain:,.2f}"
    )

    print(
        f"Second-Lowest Pain       : "
        f"{format_optional_number(result.second_lowest_pain)}"
    )

    print(
        f"Pain Gap %               : "
        f"{format_optional_number(result.pain_gap_percent)}"
    )

    print(
        f"Pinning Probability      : "
        f"{result.pinning_probability:.2f}%"
    )

    print(
        f"Magnet Strength          : "
        f"{result.magnet_strength}"
    )

    print(
        f"Expiry Bias              : "
        f"{result.expiry_bias}"
    )

    print(
        f"Pain Shift               : "
        f"{result.pain_shift}"
    )

    print()
    print("Interpretation")
    print("-" * 72)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SAMPLE TEST DATA
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample option-chain data.
    """

    rows: list[dict[str, float | str]] = []

    sample_data = {
        57000: {
            "ce_oi": 125000,
            "pe_oi": 185000,
        },
        57500: {
            "ce_oi": 210000,
            "pe_oi": 260000,
        },
        58000: {
            "ce_oi": 395000,
            "pe_oi": 340000,
        },
        58500: {
            "ce_oi": 470000,
            "pe_oi": 190000,
        },
        59000: {
            "ce_oi": 525000,
            "pe_oi": 145000,
        },
    }

    for strike, values in sample_data.items():
        rows.append(
            {
                "strikePrice": strike,
                "optionType": "CE",
                "OI": values["ce_oi"],
                "ChangeOI": 15000,
                "TotalVolume": 85000,
            }
        )

        rows.append(
            {
                "strikePrice": strike,
                "optionType": "PE",
                "OI": values["pe_oi"],
                "ChangeOI": 18000,
                "TotalVolume": 92000,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    """
    Run an independent sample test.
    """

    sample_dataframe = create_sample_option_chain()

    option_chain_data = load_option_chain(
        source=sample_dataframe,
        spot_price=57582.25,
    )

    history_file = (
        OUTPUT_DIR
        / "BANKNIFTY_SAMPLE_MaxPain_History.csv"
    )

    result, pain_table = analyze_max_pain(
        option_chain_data=option_chain_data,
        history_file=history_file,
    )

    print_max_pain_summary(result)

    print("Pain Table")
    print("-" * 72)

    print(
        pain_table[
            [
                "settlement_strike",
                "call_pain",
                "put_pain",
                "total_pain",
            ]
        ].to_string(index=False)
    )

    print()

    output_files = save_max_pain_outputs(
        result=result,
        pain_table=pain_table,
        prefix="BANKNIFTY_SAMPLE",
    )

    print("Files created:")

    for name, path in output_files.items():
        print(f"{name:<18}: {path}")


if __name__ == "__main__":
    main()