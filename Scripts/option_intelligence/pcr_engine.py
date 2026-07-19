"""
AQSD
Option Intelligence

Module: pcr_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates Put-Call Ratio intelligence from standardized
option-chain data.

Outputs:
- OI PCR
- Change-in-OI PCR
- Volume PCR
- Modified PCR
- ATM-zone PCR
- PCR bias
- PCR trend
- PCR interpretation
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    get_atm_window,
    load_option_chain,
)

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "Output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = OUTPUT_DIR / "BANKNIFTY_PCR_History.csv"


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(slots=True)
class PCRResult:
    spot_price: float
    atm_strike: float

    total_call_oi: float
    total_put_oi: float

    total_call_change_oi: float
    total_put_change_oi: float

    total_call_volume: float
    total_put_volume: float

    oi_pcr: float | None
    change_oi_pcr: float | None
    volume_pcr: float | None
    modified_pcr: float | None
    atm_zone_pcr: float | None

    pcr_trend: str
    pcr_bias: str
    reversal_watch: str
    interpretation: str

    atm_window_strikes_each_side: int
    number_of_strikes: int
    timestamp: str


# ============================================================
# HELPERS
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


def weighted_average(
    values_and_weights: list[tuple[float | None, float]],
) -> float | None:
    """
    Calculate a weighted average while ignoring unavailable values.
    """

    valid_values = [
        (value, weight)
        for value, weight in values_and_weights
        if value is not None
    ]

    if not valid_values:
        return None

    total_weight = sum(
        weight for _, weight in valid_values
    )

    if total_weight == 0:
        return None

    weighted_total = sum(
        float(value) * weight
        for value, weight in valid_values
    )

    return float(weighted_total / total_weight)


def format_ratio(
    value: float | None,
) -> str:
    """
    Format a PCR value for terminal output.
    """

    if value is None:
        return "N/A"

    return f"{value:.3f}"


# ============================================================
# PCR CALCULATIONS
# ============================================================

def calculate_modified_pcr(
    oi_pcr: float | None,
    change_oi_pcr: float | None,
    volume_pcr: float | None,
) -> float | None:
    """
    Calculate AQSD Modified PCR.

    Weighting:
    - OI PCR: 50%
    - Change-in-OI PCR: 30%
    - Volume PCR: 20%
    """

    return weighted_average(
        [
            (oi_pcr, 0.50),
            (change_oi_pcr, 0.30),
            (volume_pcr, 0.20),
        ]
    )


def calculate_atm_zone_pcr(
    option_chain_data: OptionChainData,
    strikes_each_side: int = 3,
) -> float | None:
    """
    Calculate OI PCR near ATM.
    """

    atm_window = get_atm_window(
        option_chain_data=option_chain_data,
        strikes_each_side=strikes_each_side,
    )

    call_oi = float(
        atm_window.loc[
            atm_window["option_type"] == "CE",
            "open_interest",
        ].sum()
    )

    put_oi = float(
        atm_window.loc[
            atm_window["option_type"] == "PE",
            "open_interest",
        ].sum()
    )

    return safe_ratio(
        numerator=put_oi,
        denominator=call_oi,
    )


# ============================================================
# INTERPRETATION
# ============================================================

def determine_pcr_bias(
    modified_pcr: float | None,
) -> str:
    """
    Convert Modified PCR into a broad market bias.
    """

    if modified_pcr is None:
        return "INSUFFICIENT DATA"

    if modified_pcr >= 1.30:
        return "STRONGLY BULLISH"

    if modified_pcr >= 1.10:
        return "BULLISH"

    if modified_pcr > 0.85:
        return "NEUTRAL"

    if modified_pcr > 0.65:
        return "BEARISH"

    return "STRONGLY BEARISH"


def determine_reversal_watch(
    modified_pcr: float | None,
) -> str:
    """
    Detect extreme PCR conditions that may require contrarian caution.
    """

    if modified_pcr is None:
        return "NO SIGNAL"

    if modified_pcr >= 1.70:
        return "BULLISH EXTREME — BEARISH REVERSAL WATCH"

    if modified_pcr <= 0.45:
        return "BEARISH EXTREME — BULLISH REVERSAL WATCH"

    return "NO EXTREME PCR SIGNAL"


def determine_pcr_trend(
    current_modified_pcr: float | None,
    history_file: Path = HISTORY_FILE,
    flat_tolerance: float = 0.03,
) -> str:
    """
    Compare the current Modified PCR with the latest saved value.
    """

    if current_modified_pcr is None:
        return "INSUFFICIENT DATA"

    if not history_file.exists():
        return "NO HISTORY"

    try:
        history = pd.read_csv(history_file)
    except (OSError, ValueError, pd.errors.ParserError):
        return "NO HISTORY"

    if history.empty or "modified_pcr" not in history.columns:
        return "NO HISTORY"

    previous_values = pd.to_numeric(
        history["modified_pcr"],
        errors="coerce",
    ).dropna()

    if previous_values.empty:
        return "NO HISTORY"

    previous_pcr = float(previous_values.iloc[-1])

    change = current_modified_pcr - previous_pcr

    if abs(change) <= flat_tolerance:
        return "FLAT"

    if change > 0:
        return "RISING"

    return "FALLING"


def build_interpretation(
    result: PCRResult,
) -> str:
    """
    Build a concise PCR interpretation.
    """

    observations: list[str] = []

    observations.append(
        f"Modified PCR indicates a "
        f"{result.pcr_bias.lower()} market structure."
    )

    if result.pcr_trend == "RISING":
        observations.append(
            "PCR is rising, showing improving Put-side strength."
        )

    elif result.pcr_trend == "FALLING":
        observations.append(
            "PCR is falling, showing increasing Call-side pressure."
        )

    elif result.pcr_trend == "FLAT":
        observations.append(
            "PCR is broadly stable compared with the previous reading."
        )

    elif result.pcr_trend == "NO HISTORY":
        observations.append(
            "No earlier PCR reading is available for trend comparison."
        )

    if result.atm_zone_pcr is not None:
        if result.atm_zone_pcr > 1.10:
            observations.append(
                "Near-ATM positioning is Put-heavy."
            )
        elif result.atm_zone_pcr < 0.85:
            observations.append(
                "Near-ATM positioning is Call-heavy."
            )
        else:
            observations.append(
                "Near-ATM positioning is balanced."
            )

    if result.reversal_watch != "NO EXTREME PCR SIGNAL":
        observations.append(result.reversal_watch.title() + ".")

    return " ".join(observations)


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_pcr(
    option_chain_data: OptionChainData,
    atm_window_strikes_each_side: int = 3,
) -> PCRResult:
    """
    Run the AQSD PCR Intelligence Engine.
    """

    calls = option_chain_data.calls_df
    puts = option_chain_data.puts_df

    total_call_oi = float(
        calls["open_interest"].sum()
    )

    total_put_oi = float(
        puts["open_interest"].sum()
    )

    total_call_change_oi = float(
        calls["change_in_oi"].sum()
    )

    total_put_change_oi = float(
        puts["change_in_oi"].sum()
    )

    total_call_volume = float(
        calls["volume"].sum()
    )

    total_put_volume = float(
        puts["volume"].sum()
    )

    oi_pcr = safe_ratio(
        numerator=total_put_oi,
        denominator=total_call_oi,
    )

    change_oi_pcr = safe_ratio(
        numerator=total_put_change_oi,
        denominator=total_call_change_oi,
    )

    volume_pcr = safe_ratio(
        numerator=total_put_volume,
        denominator=total_call_volume,
    )

    modified_pcr = calculate_modified_pcr(
        oi_pcr=oi_pcr,
        change_oi_pcr=change_oi_pcr,
        volume_pcr=volume_pcr,
    )

    atm_zone_pcr = calculate_atm_zone_pcr(
        option_chain_data=option_chain_data,
        strikes_each_side=atm_window_strikes_each_side,
    )

    pcr_trend = determine_pcr_trend(
        current_modified_pcr=modified_pcr,
    )

    pcr_bias = determine_pcr_bias(
        modified_pcr=modified_pcr,
    )

    reversal_watch = determine_reversal_watch(
        modified_pcr=modified_pcr,
    )

    result = PCRResult(
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,
        total_call_oi=total_call_oi,
        total_put_oi=total_put_oi,
        total_call_change_oi=total_call_change_oi,
        total_put_change_oi=total_put_change_oi,
        total_call_volume=total_call_volume,
        total_put_volume=total_put_volume,
        oi_pcr=oi_pcr,
        change_oi_pcr=change_oi_pcr,
        volume_pcr=volume_pcr,
        modified_pcr=modified_pcr,
        atm_zone_pcr=atm_zone_pcr,
        pcr_trend=pcr_trend,
        pcr_bias=pcr_bias,
        reversal_watch=reversal_watch,
        interpretation="",
        atm_window_strikes_each_side=atm_window_strikes_each_side,
        number_of_strikes=option_chain_data.number_of_strikes,
        timestamp=option_chain_data.timestamp,
    )

    result.interpretation = build_interpretation(
        result
    )

    return result


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================

def result_to_dataframe(
    result: PCRResult,
) -> pd.DataFrame:
    """
    Convert the PCR result into a two-column DataFrame.
    """

    result_dictionary = asdict(result)

    return pd.DataFrame(
        {
            "metric": result_dictionary.keys(),
            "value": result_dictionary.values(),
        }
    )


def append_pcr_history(
    result: PCRResult,
    history_file: Path = HISTORY_FILE,
) -> Path:
    """
    Append the current PCR reading to the history CSV.
    """

    history_row = pd.DataFrame(
        [
            {
                "timestamp": result.timestamp,
                "spot_price": result.spot_price,
                "atm_strike": result.atm_strike,
                "oi_pcr": result.oi_pcr,
                "change_oi_pcr": result.change_oi_pcr,
                "volume_pcr": result.volume_pcr,
                "modified_pcr": result.modified_pcr,
                "atm_zone_pcr": result.atm_zone_pcr,
                "pcr_trend": result.pcr_trend,
                "pcr_bias": result.pcr_bias,
                "reversal_watch": result.reversal_watch,
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


def save_pcr_outputs(
    result: PCRResult,
    prefix: str = "BANKNIFTY",
) -> dict[str, Path]:
    """
    Save PCR summary, history and Excel outputs.
    """

    safe_prefix = (
        prefix.strip()
        .upper()
        .replace(" ", "_")
        .replace(":", "_")
    )

    summary_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_PCR_Summary.csv"
    )

    excel_file = (
        OUTPUT_DIR
        / f"{safe_prefix}_PCR.xlsx"
    )

    history_file = (
        OUTPUT_DIR
        / f"{safe_prefix}_PCR_History.csv"
    )

    summary_dataframe = result_to_dataframe(
        result
    )

    summary_dataframe.to_csv(
        summary_csv,
        index=False,
    )

    append_pcr_history(
        result=result,
        history_file=history_file,
    )

    history_dataframe = pd.read_csv(
        history_file
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="PCR Summary",
            index=False,
        )

        history_dataframe.to_excel(
            writer,
            sheet_name="PCR History",
            index=False,
        )

    return {
        "summary_csv": summary_csv,
        "history_csv": history_file,
        "excel": excel_file,
    }


def print_pcr_summary(
    result: PCRResult,
) -> None:
    """
    Print the PCR intelligence summary.
    """

    separator = "=" * 72

    print()
    print(separator)
    print("AQSD OPTION INTELLIGENCE — PCR ENGINE")
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
        f"OI PCR                   : "
        f"{format_ratio(result.oi_pcr)}"
    )

    print(
        f"Change-in-OI PCR         : "
        f"{format_ratio(result.change_oi_pcr)}"
    )

    print(
        f"Volume PCR               : "
        f"{format_ratio(result.volume_pcr)}"
    )

    print(
        f"Modified PCR             : "
        f"{format_ratio(result.modified_pcr)}"
    )

    print(
        f"ATM-Zone PCR             : "
        f"{format_ratio(result.atm_zone_pcr)}"
    )

    print(
        f"PCR Trend                : "
        f"{result.pcr_trend}"
    )

    print(
        f"PCR Bias                 : "
        f"{result.pcr_bias}"
    )

    print(
        f"Reversal Watch           : "
        f"{result.reversal_watch}"
    )

    print()
    print("Interpretation")
    print("-" * 72)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SAMPLE TEST
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample option-chain data.
    """

    return pd.DataFrame(
        [
            {
                "strikePrice": 57000,
                "optionType": "CE",
                "OI": 125000,
                "ChangeOI": 15000,
                "TotalVolume": 82000,
            },
            {
                "strikePrice": 57000,
                "optionType": "PE",
                "OI": 185000,
                "ChangeOI": 24000,
                "TotalVolume": 91000,
            },
            {
                "strikePrice": 57500,
                "optionType": "CE",
                "OI": 210000,
                "ChangeOI": 38000,
                "TotalVolume": 150000,
            },
            {
                "strikePrice": 57500,
                "optionType": "PE",
                "OI": 260000,
                "ChangeOI": 42000,
                "TotalVolume": 168000,
            },
            {
                "strikePrice": 58000,
                "optionType": "CE",
                "OI": 395000,
                "ChangeOI": 72000,
                "TotalVolume": 244000,
            },
            {
                "strikePrice": 58000,
                "optionType": "PE",
                "OI": 340000,
                "ChangeOI": 51000,
                "TotalVolume": 230000,
            },
            {
                "strikePrice": 58500,
                "optionType": "CE",
                "OI": 470000,
                "ChangeOI": 93000,
                "TotalVolume": 280000,
            },
            {
                "strikePrice": 58500,
                "optionType": "PE",
                "OI": 190000,
                "ChangeOI": 18000,
                "TotalVolume": 125000,
            },
            {
                "strikePrice": 59000,
                "optionType": "CE",
                "OI": 525000,
                "ChangeOI": 65000,
                "TotalVolume": 220000,
            },
            {
                "strikePrice": 59000,
                "optionType": "PE",
                "OI": 145000,
                "ChangeOI": 12000,
                "TotalVolume": 98000,
            },
        ]
    )

def main() -> None:
    """
    Run an independent sample test using the shared AQSD exporter.
    """

    sample_dataframe = create_sample_option_chain()

    option_chain_data = load_option_chain(
        source=sample_dataframe,
        spot_price=57582.25,
    )

    result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=2,
    )

    print_pcr_summary(result)

    metadata = ExportMetadata(
        engine="PCR",
        underlying="BANKNIFTY_SAMPLE",
        engine_version="1.0",
        rows_processed=len(sample_dataframe),
        status="SUCCESS",
        source="AQSD Sample Option Chain",
        notes="Independent pcr_engine.py module test.",
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "atm_strike": result.atm_strike,
        "oi_pcr": result.oi_pcr,
        "change_oi_pcr": result.change_oi_pcr,
        "volume_pcr": result.volume_pcr,
        "modified_pcr": result.modified_pcr,
        "atm_zone_pcr": result.atm_zone_pcr,
        "pcr_trend": result.pcr_trend,
        "pcr_bias": result.pcr_bias,
        "reversal_watch": result.reversal_watch,
    }

    engine_result = EngineResult(
        summary=result,
        table=None,
        history=history_row,
        metadata=metadata,
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename="BANKNIFTY_SAMPLE_PCR",
        save_table=False,
    )

    print_export_report(export_paths)

if __name__ == "__main__":
    main()