"""
AQSD
Option Intelligence Engine

Module: oi_engine.py
Version: 1.0
Author: AQSD

Description:
Calculates Call and Put Open Interest intelligence from an
option-chain DataFrame.

Outputs:
- Total Call OI
- Total Put OI
- Total Call Change in OI
- Total Put Change in OI
- OI PCR
- Call Wall
- Put Wall
- Fresh Call Wall
- Fresh Put Wall
- OI imbalance
- OI market bias
- Strike-wise OI table
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from Scripts.option_intelligence.common import (
    safe_divide,
)

from Scripts.option_intelligence.validators import (
    validate_option_chain,
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


# ============================================================
# COLUMN ALIASES
# ============================================================

COLUMN_ALIASES: dict[str, list[str]] = {
    "strike": [
        "strike",
        "strike_price",
        "strikeprice",
        "strike price",
    ],
    "option_type": [
        "option_type",
        "optiontype",
        "type",
        "right",
        "cp_type",
    ],
    "open_interest": [
        "open_interest",
        "openinterest",
        "oi",
        "open interest",
    ],
    "change_in_oi": [
        "change_in_oi",
        "changeinoi",
        "change_oi",
        "oi_change",
        "chg_in_oi",
        "change in oi",
    ],
    "volume": [
        "volume",
        "vol",
        "traded_volume",
        "total_traded_volume",
    ],
    "ltp": [
        "ltp",
        "last_price",
        "last_traded_price",
        "lastprice",
    ],
}


# ============================================================
# DATA MODELS
# ============================================================

@dataclass(slots=True)
class OIResult:
    total_call_oi: float
    total_put_oi: float

    total_call_change_oi: float
    total_put_change_oi: float

    oi_pcr: float | None
    change_oi_pcr: float | None

    call_oi_share_percent: float
    put_oi_share_percent: float

    oi_imbalance: float
    change_oi_imbalance: float

    positional_call_wall: float | None
    positional_put_wall: float | None

    fresh_call_wall: float | None
    fresh_put_wall: float | None

    market_bias: str
    build_up_signal: str
    interpretation: str

    number_of_strikes: int
    number_of_call_contracts: int
    number_of_put_contracts: int


# ============================================================
# HELPERS
# ============================================================

def normalise_column_name(column: Any) -> str:
    """
    Convert a column name into a standard comparison format.
    """

    return (
        str(column)
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def resolve_column(
    dataframe: pd.DataFrame,
    logical_name: str,
    required: bool = True,
) -> str | None:
    """
    Find the real DataFrame column corresponding to a logical field.
    """

    normalised_columns = {
        normalise_column_name(column): column
        for column in dataframe.columns
    }

    aliases = COLUMN_ALIASES.get(logical_name, [])

    for alias in aliases:
        normalised_alias = normalise_column_name(alias)

        if normalised_alias in normalised_columns:
            return normalised_columns[normalised_alias]

    if required:
        available = ", ".join(map(str, dataframe.columns))

        raise ValueError(
            f"Required column '{logical_name}' was not found.\n"
            f"Available columns: {available}"
        )

    return None


def safe_divide(
    numerator: float,
    denominator: float,
) -> float | None:
    """
    Safely divide two numbers.
    """

    if denominator == 0:
        return None

    return float(numerator / denominator)

def safe_percent(
    numerator: float,
    denominator: float,
) -> float:
    """
    Calculate percentage safely.
    """

    if denominator == 0:
        return 0.0

    return float((numerator / denominator) * 100.0)

def standardise_option_type(value: Any) -> str:
    """
    Convert different option-type formats into CE or PE.
    """

    text = str(value).strip().upper()

    call_values = {
        "CE",
        "CALL",
        "C",
        "CALL_OPTION",
    }

    put_values = {
        "PE",
        "PUT",
        "P",
        "PUT_OPTION",
    }

    if text in call_values:
        return "CE"

    if text in put_values:
        return "PE"

    return text


def strike_of_maximum(
    dataframe: pd.DataFrame,
    value_column: str,
    strike_column: str,
) -> float | None:
    """
    Return the strike containing the highest value.
    """

    if dataframe.empty:
        return None

    valid = dataframe.copy()

    valid[value_column] = pd.to_numeric(
        valid[value_column],
        errors="coerce",
    )

    valid[strike_column] = pd.to_numeric(
        valid[strike_column],
        errors="coerce",
    )

    valid = valid.dropna(
        subset=[value_column, strike_column],
    )

    if valid.empty:
        return None

    maximum_index = valid[value_column].idxmax()

    return float(valid.loc[maximum_index, strike_column])


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_option_chain(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean and standardise the option-chain DataFrame.
    """

    if dataframe is None:
        raise ValueError("Option-chain DataFrame cannot be None.")

    if dataframe.empty:
        raise ValueError("Option-chain DataFrame is empty.")

    df = dataframe.copy()

    strike_column = resolve_column(
        df,
        "strike",
        required=True,
    )

    option_type_column = resolve_column(
        df,
        "option_type",
        required=True,
    )

    oi_column = resolve_column(
        df,
        "open_interest",
        required=True,
    )

    change_oi_column = resolve_column(
        df,
        "change_in_oi",
        required=False,
    )

    volume_column = resolve_column(
        df,
        "volume",
        required=False,
    )

    ltp_column = resolve_column(
        df,
        "ltp",
        required=False,
    )

    rename_map: dict[str, str] = {
        strike_column: "strike",
        option_type_column: "option_type",
        oi_column: "open_interest",
    }

    if change_oi_column is not None:
        rename_map[change_oi_column] = "change_in_oi"

    if volume_column is not None:
        rename_map[volume_column] = "volume"

    if ltp_column is not None:
        rename_map[ltp_column] = "ltp"

    df = df.rename(columns=rename_map)

    if "change_in_oi" not in df.columns:
        df["change_in_oi"] = 0.0

    if "volume" not in df.columns:
        df["volume"] = 0.0

    if "ltp" not in df.columns:
        df["ltp"] = 0.0

    df["strike"] = pd.to_numeric(
        df["strike"],
        errors="coerce",
    )

    df["option_type"] = df["option_type"].apply(
        standardise_option_type
    )

    df["open_interest"] = pd.to_numeric(
        df["open_interest"],
        errors="coerce",
    ).fillna(0.0)

    df["change_in_oi"] = pd.to_numeric(
        df["change_in_oi"],
        errors="coerce",
    ).fillna(0.0)

    df["volume"] = pd.to_numeric(
        df["volume"],
        errors="coerce",
    ).fillna(0.0)

    df["ltp"] = pd.to_numeric(
        df["ltp"],
        errors="coerce",
    ).fillna(0.0)

    df = df.dropna(subset=["strike"])

    df = df[
        df["option_type"].isin(["CE", "PE"])
    ].copy()

    if df.empty:
        raise ValueError(
            "No valid CE or PE option rows were found."
        )

    return df.sort_values(
        by=["strike", "option_type"],
    ).reset_index(drop=True)


# ============================================================
# OI INTERPRETATION
# ============================================================

def determine_market_bias(
    oi_pcr: float | None,
    change_oi_pcr: float | None,
    oi_imbalance: float,
) -> str:
    """
    Determine broad OI market bias.
    """

    if oi_pcr is None:
        return "INSUFFICIENT DATA"

    if oi_pcr >= 1.20:
        bias = "BULLISH"
    elif oi_pcr <= 0.80:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    if change_oi_pcr is not None:
        if change_oi_pcr >= 1.25:
            bias = "BULLISH"
        elif change_oi_pcr <= 0.75:
            bias = "BEARISH"

    if abs(oi_imbalance) < 5.0:
        return "NEUTRAL"

    return bias


def determine_build_up_signal(
    call_change_oi: float,
    put_change_oi: float,
) -> str:
    """
    Interpret fresh Call and Put OI changes.
    """

    if call_change_oi > 0 and put_change_oi > 0:
        if put_change_oi > call_change_oi:
            return "PUT WRITING DOMINANT"

        if call_change_oi > put_change_oi:
            return "CALL WRITING DOMINANT"

        return "BALANCED WRITING"

    if call_change_oi < 0 and put_change_oi < 0:
        return "BROAD OI UNWINDING"

    if call_change_oi < 0 and put_change_oi > 0:
        return "CALL UNWINDING WITH PUT WRITING"

    if call_change_oi > 0 and put_change_oi < 0:
        return "CALL WRITING WITH PUT UNWINDING"

    return "NO CLEAR FRESH OI SIGNAL"


def build_interpretation(
    result: OIResult,
) -> str:
    """
    Build a concise human-readable OI interpretation.
    """

    observations: list[str] = []

    if result.market_bias == "BULLISH":
        observations.append(
            "Put-side open interest is relatively stronger."
        )

    elif result.market_bias == "BEARISH":
        observations.append(
            "Call-side open interest is relatively stronger."
        )

    else:
        observations.append(
            "Call and Put open interest are broadly balanced."
        )

    observations.append(
        f"Fresh OI signal: {result.build_up_signal.lower()}."
    )

    if result.positional_call_wall is not None:
        observations.append(
            "The positional Call Wall is at "
            f"{result.positional_call_wall:,.2f}."
        )

    if result.positional_put_wall is not None:
        observations.append(
            "The positional Put Wall is at "
            f"{result.positional_put_wall:,.2f}."
        )

    return " ".join(observations)


# ============================================================
# STRIKE-WISE TABLE
# ============================================================

def build_strike_oi_table(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one row per strike with Call and Put OI statistics.
    """

    df = prepare_option_chain(dataframe)

    calls = (
        df[df["option_type"] == "CE"]
        .groupby("strike", as_index=False)
        .agg(
            call_oi=("open_interest", "sum"),
            call_change_oi=("change_in_oi", "sum"),
            call_volume=("volume", "sum"),
        )
    )

    puts = (
        df[df["option_type"] == "PE"]
        .groupby("strike", as_index=False)
        .agg(
            put_oi=("open_interest", "sum"),
            put_change_oi=("change_in_oi", "sum"),
            put_volume=("volume", "sum"),
        )
    )

    strike_table = pd.merge(
        calls,
        puts,
        on="strike",
        how="outer",
    )

    numeric_columns = [
        "call_oi",
        "call_change_oi",
        "call_volume",
        "put_oi",
        "put_change_oi",
        "put_volume",
    ]

    for column in numeric_columns:
        if column not in strike_table.columns:
            strike_table[column] = 0.0

        strike_table[column] = pd.to_numeric(
            strike_table[column],
            errors="coerce",
        ).fillna(0.0)

    strike_table["net_oi"] = (
        strike_table["put_oi"]
        - strike_table["call_oi"]
    )

    strike_table["net_change_oi"] = (
        strike_table["put_change_oi"]
        - strike_table["call_change_oi"]
    )

    strike_table["strike_oi_pcr"] = strike_table.apply(
        lambda row: safe_divide(
            float(row["put_oi"]),
            float(row["call_oi"]),
        ),
        axis=1,
    )

    return strike_table.sort_values(
        by="strike"
    ).reset_index(drop=True)


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_open_interest(
    dataframe: pd.DataFrame,
) -> tuple[OIResult, pd.DataFrame]:
    """
    Run the AQSD Open Interest Intelligence Engine.

    Returns:
        Tuple containing:
        1. OIResult summary
        2. Strike-wise OI DataFrame
    """

    df = prepare_option_chain(dataframe)

    calls = df[df["option_type"] == "CE"].copy()
    puts = df[df["option_type"] == "PE"].copy()

    total_call_oi = float(calls["open_interest"].sum())
    total_put_oi = float(puts["open_interest"].sum())

    total_call_change_oi = float(
        calls["change_in_oi"].sum()
    )

    total_put_change_oi = float(
        puts["change_in_oi"].sum()
    )

    total_combined_oi = total_call_oi + total_put_oi

    call_oi_share_percent = safe_percent(
        total_call_oi,
        total_combined_oi,
    )

    put_oi_share_percent = safe_percent(
        total_put_oi,
        total_combined_oi,
    )

    oi_pcr = safe_divide(
        total_put_oi,
        total_call_oi,
    )

    change_oi_pcr = safe_divide(
        total_put_change_oi,
        total_call_change_oi,
    )

    oi_imbalance = safe_percent(
        total_put_oi - total_call_oi,
        total_combined_oi,
    )

    total_absolute_change = (
        abs(total_call_change_oi)
        + abs(total_put_change_oi)
    )

    change_oi_imbalance = safe_percent(
        total_put_change_oi - total_call_change_oi,
        total_absolute_change,
    )

    positional_call_wall = strike_of_maximum(
        dataframe=calls,
        value_column="open_interest",
        strike_column="strike",
    )

    positional_put_wall = strike_of_maximum(
        dataframe=puts,
        value_column="open_interest",
        strike_column="strike",
    )

    fresh_call_wall = strike_of_maximum(
        dataframe=calls[calls["change_in_oi"] > 0],
        value_column="change_in_oi",
        strike_column="strike",
    )

    fresh_put_wall = strike_of_maximum(
        dataframe=puts[puts["change_in_oi"] > 0],
        value_column="change_in_oi",
        strike_column="strike",
    )

    market_bias = determine_market_bias(
        oi_pcr=oi_pcr,
        change_oi_pcr=change_oi_pcr,
        oi_imbalance=oi_imbalance,
    )

    build_up_signal = determine_build_up_signal(
        call_change_oi=total_call_change_oi,
        put_change_oi=total_put_change_oi,
    )

    result = OIResult(
        total_call_oi=total_call_oi,
        total_put_oi=total_put_oi,
        total_call_change_oi=total_call_change_oi,
        total_put_change_oi=total_put_change_oi,
        oi_pcr=oi_pcr,
        change_oi_pcr=change_oi_pcr,
        call_oi_share_percent=call_oi_share_percent,
        put_oi_share_percent=put_oi_share_percent,
        oi_imbalance=oi_imbalance,
        change_oi_imbalance=change_oi_imbalance,
        positional_call_wall=positional_call_wall,
        positional_put_wall=positional_put_wall,
        fresh_call_wall=fresh_call_wall,
        fresh_put_wall=fresh_put_wall,
        market_bias=market_bias,
        build_up_signal=build_up_signal,
        interpretation="",
        number_of_strikes=int(df["strike"].nunique()),
        number_of_call_contracts=int(len(calls)),
        number_of_put_contracts=int(len(puts)),
    )

    result.interpretation = build_interpretation(result)

    strike_table = build_strike_oi_table(df)

    return result, strike_table


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================

def result_to_dataframe(
    result: OIResult,
) -> pd.DataFrame:
    """
    Convert the OI summary result to a two-column DataFrame.
    """

    result_dictionary = asdict(result)

    return pd.DataFrame(
        {
            "metric": result_dictionary.keys(),
            "value": result_dictionary.values(),
        }
    )


def save_oi_outputs(
    result: OIResult,
    strike_table: pd.DataFrame,
    prefix: str = "BANKNIFTY",
) -> dict[str, Path]:
    """
    Save OI intelligence output files.
    """

    safe_prefix = (
        prefix.strip()
        .upper()
        .replace(" ", "_")
        .replace(":", "_")
    )

    summary_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_OI_Intelligence_Summary.csv"
    )

    strikes_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_OI_Intelligence_Strikes.csv"
    )

    excel_file = (
        OUTPUT_DIR
        / f"{safe_prefix}_OI_Intelligence.xlsx"
    )

    summary_dataframe = result_to_dataframe(result)

    summary_dataframe.to_csv(
        summary_csv,
        index=False,
    )

    strike_table.to_csv(
        strikes_csv,
        index=False,
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="OI Summary",
            index=False,
        )

        strike_table.to_excel(
            writer,
            sheet_name="Strike OI",
            index=False,
        )

    return {
        "summary_csv": summary_csv,
        "strikes_csv": strikes_csv,
        "excel": excel_file,
    }


def print_oi_summary(
    result: OIResult,
) -> None:
    """
    Print OI intelligence in the terminal.
    """

    separator = "=" * 72

    print()
    print(separator)
    print("AQSD OPTION INTELLIGENCE — OPEN INTEREST")
    print(separator)

    print(
        f"Total Call OI             : "
        f"{result.total_call_oi:,.0f}"
    )

    print(
        f"Total Put OI              : "
        f"{result.total_put_oi:,.0f}"
    )

    print(
        f"Call Change in OI         : "
        f"{result.total_call_change_oi:,.0f}"
    )

    print(
        f"Put Change in OI          : "
        f"{result.total_put_change_oi:,.0f}"
    )

    print(
        f"OI PCR                    : "
        f"{result.oi_pcr:.3f}"
        if result.oi_pcr is not None
        else "OI PCR                    : N/A"
    )

    print(
        f"Change-in-OI PCR          : "
        f"{result.change_oi_pcr:.3f}"
        if result.change_oi_pcr is not None
        else "Change-in-OI PCR          : N/A"
    )

    print(
        f"Call OI Share             : "
        f"{result.call_oi_share_percent:.2f}%"
    )

    print(
        f"Put OI Share              : "
        f"{result.put_oi_share_percent:.2f}%"
    )

    print(
        f"OI Imbalance              : "
        f"{result.oi_imbalance:+.2f}%"
    )

    print(
        f"Positional Call Wall      : "
        f"{result.positional_call_wall}"
    )

    print(
        f"Positional Put Wall       : "
        f"{result.positional_put_wall}"
    )

    print(
        f"Fresh Call Wall           : "
        f"{result.fresh_call_wall}"
    )

    print(
        f"Fresh Put Wall            : "
        f"{result.fresh_put_wall}"
    )

    print(
        f"Market Bias               : "
        f"{result.market_bias}"
    )

    print(
        f"Fresh OI Signal           : "
        f"{result.build_up_signal}"
    )

    print(
        f"Number of Strikes         : "
        f"{result.number_of_strikes}"
    )

    print()
    print("Interpretation")
    print("-" * 72)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SIMPLE TEST
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample data to test the engine independently.
    """

    return pd.DataFrame(
        [
            {
                "strike": 57000,
                "option_type": "CE",
                "open_interest": 125000,
                "change_in_oi": 15000,
                "volume": 82000,
            },
            {
                "strike": 57000,
                "option_type": "PE",
                "open_interest": 185000,
                "change_in_oi": 24000,
                "volume": 91000,
            },
            {
                "strike": 57500,
                "option_type": "CE",
                "open_interest": 210000,
                "change_in_oi": 38000,
                "volume": 150000,
            },
            {
                "strike": 57500,
                "option_type": "PE",
                "open_interest": 260000,
                "change_in_oi": 42000,
                "volume": 168000,
            },
            {
                "strike": 58000,
                "option_type": "CE",
                "open_interest": 395000,
                "change_in_oi": 72000,
                "volume": 244000,
            },
            {
                "strike": 58000,
                "option_type": "PE",
                "open_interest": 340000,
                "change_in_oi": 51000,
                "volume": 230000,
            },
            {
                "strike": 58500,
                "option_type": "CE",
                "open_interest": 470000,
                "change_in_oi": 93000,
                "volume": 280000,
            },
            {
                "strike": 58500,
                "option_type": "PE",
                "open_interest": 190000,
                "change_in_oi": -18000,
                "volume": 125000,
            },
            {
                "strike": 59000,
                "option_type": "CE",
                "open_interest": 525000,
                "change_in_oi": 65000,
                "volume": 220000,
            },
            {
                "strike": 59000,
                "option_type": "PE",
                "open_interest": 145000,
                "change_in_oi": -26000,
                "volume": 98000,
            },
        ]
    )

def main() -> None:
    """
    Run an independent sample test using the shared AQSD exporter.
    """

    sample_dataframe = create_sample_option_chain()

    result, strike_table = analyze_open_interest(
        sample_dataframe
    )

    print_oi_summary(result)

    metadata = ExportMetadata(
        engine="OI",
        underlying="BANKNIFTY_SAMPLE",
        engine_version="1.0",
        rows_processed=len(sample_dataframe),
        status="SUCCESS",
        source="AQSD Sample Option Chain",
        notes="Independent oi_engine.py module test.",
    )

    engine_result = EngineResult(
        summary=result,
        table=strike_table,
        history=asdict(result),
        metadata=metadata,
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename="BANKNIFTY_SAMPLE_OI_Intelligence",
    )

    print_export_report(export_paths)

if __name__ == "__main__":
    main()