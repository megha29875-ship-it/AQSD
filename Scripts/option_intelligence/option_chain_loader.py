"""
AQSD
Option Intelligence

Module: option_chain_loader.py
Version: 1.0
Author: AQSD

Description:
Shared option-chain loading and standardisation module used by:

- OI Engine
- PCR Engine
- Max Pain Engine
- Wall Engine
- Volatility Engine
- Probability Engine
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "Output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# AQSD STANDARD COLUMN NAMES
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
        "option type",
        "right",
        "type",
        "cp_type",
        "instrument_type",
    ],
    "open_interest": [
        "open_interest",
        "openinterest",
        "open interest",
        "oi",
    ],
    "change_in_oi": [
        "change_in_oi",
        "changeinoi",
        "changeoi",
        "change in oi",
        "change_oi",
        "oi_change",
        "chg_in_oi",
        "oich",
    ],
    "volume": [
        "volume",
        "vol",
        "traded_volume",
        "total_traded_volume",
        "totalvolume",
    ],
    "iv": [
        "iv",
        "implied_volatility",
        "impliedvolatility",
        "implied volatility",
    ],
    "ltp": [
        "ltp",
        "last_price",
        "lastprice",
        "last_traded_price",
        "last traded price",
    ],
    "bid": [
        "bid",
        "bid_price",
        "bidprice",
    ],
    "ask": [
        "ask",
        "ask_price",
        "askprice",
    ],
    "symbol": [
        "symbol",
        "fy_symbol",
        "tradingsymbol",
        "trading_symbol",
    ],
    "expiry": [
        "expiry",
        "expiry_date",
        "expirydate",
    ],
}


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(slots=True)
class OptionChainData:
    """
    Standard AQSD option-chain structure.
    """

    spot_price: float
    atm_strike: float
    strike_step: float

    option_chain: pd.DataFrame
    calls_df: pd.DataFrame
    puts_df: pd.DataFrame

    number_of_strikes: int
    number_of_calls: int
    number_of_puts: int

    source: str
    timestamp: str


# ============================================================
# COLUMN HELPERS
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


def find_column(
    dataframe: pd.DataFrame,
    logical_name: str,
    required: bool = False,
) -> str | None:
    """
    Locate an incoming column using AQSD aliases.
    """

    available_columns = {
        normalise_column_name(column): column
        for column in dataframe.columns
    }

    aliases = COLUMN_ALIASES.get(logical_name, [])

    for alias in aliases:
        normalised_alias = normalise_column_name(alias)

        if normalised_alias in available_columns:
            return available_columns[normalised_alias]

    if required:
        available = ", ".join(map(str, dataframe.columns))

        raise ValueError(
            f"Required column '{logical_name}' was not found.\n"
            f"Available columns: {available}"
        )

    return None


def build_rename_map(
    dataframe: pd.DataFrame,
) -> dict[str, str]:
    """
    Build the incoming-column to AQSD-column rename mapping.
    """

    rename_map: dict[str, str] = {}

    required_columns = [
        "strike",
        "option_type",
        "open_interest",
    ]

    optional_columns = [
        "change_in_oi",
        "volume",
        "iv",
        "ltp",
        "bid",
        "ask",
        "symbol",
        "expiry",
    ]

    for logical_name in required_columns:
        real_column = find_column(
            dataframe=dataframe,
            logical_name=logical_name,
            required=True,
        )

        rename_map[real_column] = logical_name

    for logical_name in optional_columns:
        real_column = find_column(
            dataframe=dataframe,
            logical_name=logical_name,
            required=False,
        )

        if real_column is not None:
            rename_map[real_column] = logical_name

    return rename_map


# ============================================================
# OPTION TYPE STANDARDISATION
# ============================================================

def standardise_option_type(value: Any) -> str:
    """
    Convert option-type values to CE or PE.
    """

    text = str(value).strip().upper()

    call_values = {
        "CE",
        "CALL",
        "C",
        "CALL_OPTION",
        "CALL OPTION",
    }

    put_values = {
        "PE",
        "PUT",
        "P",
        "PUT_OPTION",
        "PUT OPTION",
    }

    if text in call_values:
        return "CE"

    if text in put_values:
        return "PE"

    if text.endswith("CE"):
        return "CE"

    if text.endswith("PE"):
        return "PE"

    return text


# ============================================================
# FILE LOADING
# ============================================================

def load_dataframe_from_file(
    file_path: str | Path,
) -> pd.DataFrame:
    """
    Load an option chain from CSV, Excel, JSON or Parquet.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Option-chain file was not found: {path}"
        )

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)

    if suffix == ".json":
        try:
            return pd.read_json(path)
        except ValueError:
            return pd.read_json(
                path,
                orient="records",
            )

    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(
        "Unsupported option-chain file format: "
        f"{suffix}. Use CSV, Excel, JSON or Parquet."
    )


# ============================================================
# DATA CLEANING
# ============================================================

def ensure_optional_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add optional AQSD columns when they are absent.
    """

    df = dataframe.copy()

    numeric_defaults = {
        "change_in_oi": 0.0,
        "volume": 0.0,
        "iv": 0.0,
        "ltp": 0.0,
        "bid": 0.0,
        "ask": 0.0,
    }

    text_defaults = {
        "symbol": "",
        "expiry": "",
    }

    for column, default_value in numeric_defaults.items():
        if column not in df.columns:
            df[column] = default_value

    for column, default_value in text_defaults.items():
        if column not in df.columns:
            df[column] = default_value

    return df


def convert_numeric_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert AQSD numeric columns to numeric values.
    """

    df = dataframe.copy()

    numeric_columns = [
        "strike",
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "ltp",
        "bid",
        "ask",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["strike"] = df["strike"].astype(float)

    fill_zero_columns = [
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "ltp",
        "bid",
        "ask",
    ]

    for column in fill_zero_columns:
        df[column] = df[column].fillna(0.0)

    return df


def standardise_option_chain(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert an incoming option chain into AQSD standard format.
    """

    if dataframe is None:
        raise ValueError(
            "Option-chain DataFrame cannot be None."
        )

    if dataframe.empty:
        raise ValueError(
            "Option-chain DataFrame is empty."
        )

    df = dataframe.copy()

    rename_map = build_rename_map(df)

    df = df.rename(columns=rename_map)

    df = ensure_optional_columns(df)

    df["option_type"] = df["option_type"].apply(
        standardise_option_type
    )

    df = convert_numeric_columns(df)

    df = df.dropna(subset=["strike"])

    df = df[
        df["option_type"].isin(["CE", "PE"])
    ].copy()

    if df.empty:
        raise ValueError(
            "No valid CE or PE rows were found "
            "after standardisation."
        )

    standard_columns = [
        "strike",
        "option_type",
        "open_interest",
        "change_in_oi",
        "volume",
        "iv",
        "ltp",
        "bid",
        "ask",
        "symbol",
        "expiry",
    ]

    remaining_columns = [
        column
        for column in df.columns
        if column not in standard_columns
    ]

    df = df[
        standard_columns + remaining_columns
    ]

    return df.sort_values(
        by=["strike", "option_type"],
    ).reset_index(drop=True)


# ============================================================
# ATM AND STRIKE STEP
# ============================================================

def calculate_strike_step(
    dataframe: pd.DataFrame,
) -> float:
    """
    Detect the most common strike interval.
    """

    strikes = sorted(
        dataframe["strike"]
        .dropna()
        .astype(float)
        .unique()
    )

    if len(strikes) < 2:
        return 0.0

    differences = pd.Series(strikes).diff().dropna()

    differences = differences[
        differences > 0
    ]

    if differences.empty:
        return 0.0

    modes = differences.mode()

    if not modes.empty:
        return float(modes.iloc[0])

    return float(differences.median())


def calculate_atm_strike(
    dataframe: pd.DataFrame,
    spot_price: float,
) -> float:
    """
    Return the available strike nearest to the spot price.
    """

    if spot_price <= 0:
        raise ValueError(
            "Spot price must be greater than zero."
        )

    strikes = (
        dataframe["strike"]
        .dropna()
        .astype(float)
        .unique()
    )

    if len(strikes) == 0:
        raise ValueError(
            "Cannot calculate ATM because no strikes exist."
        )

    nearest_strike = min(
        strikes,
        key=lambda strike: abs(strike - spot_price),
    )

    return float(nearest_strike)


# ============================================================
# MAIN LOADER
# ============================================================

def load_option_chain(
    source: pd.DataFrame | str | Path,
    spot_price: float,
) -> OptionChainData:
    """
    Load and standardise option-chain data.

    Args:
        source:
            DataFrame or path to CSV, Excel, JSON or Parquet.

        spot_price:
            Current underlying spot price.

    Returns:
        OptionChainData
    """

    if isinstance(source, pd.DataFrame):
        raw_dataframe = source.copy()
        source_description = "DATAFRAME"

    elif isinstance(source, (str, Path)):
        raw_dataframe = load_dataframe_from_file(source)
        source_description = str(Path(source))

    else:
        raise TypeError(
            "Source must be a pandas DataFrame or file path."
        )

    clean_dataframe = standardise_option_chain(
        raw_dataframe
    )

    atm_strike = calculate_atm_strike(
        dataframe=clean_dataframe,
        spot_price=float(spot_price),
    )

    strike_step = calculate_strike_step(
        clean_dataframe
    )

    calls_df = clean_dataframe[
        clean_dataframe["option_type"] == "CE"
    ].copy()

    puts_df = clean_dataframe[
        clean_dataframe["option_type"] == "PE"
    ].copy()

    return OptionChainData(
        spot_price=float(spot_price),
        atm_strike=atm_strike,
        strike_step=strike_step,
        option_chain=clean_dataframe,
        calls_df=calls_df,
        puts_df=puts_df,
        number_of_strikes=int(
            clean_dataframe["strike"].nunique()
        ),
        number_of_calls=int(len(calls_df)),
        number_of_puts=int(len(puts_df)),
        source=source_description,
        timestamp=datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
    )


# ============================================================
# ATM WINDOW
# ============================================================

def get_atm_window(
    option_chain_data: OptionChainData,
    strikes_each_side: int = 3,
) -> pd.DataFrame:
    """
    Return ATM plus the selected number of strikes on each side.
    """

    if strikes_each_side < 0:
        raise ValueError(
            "strikes_each_side cannot be negative."
        )

    strikes = sorted(
        option_chain_data.option_chain[
            "strike"
        ].unique()
    )

    atm_index = min(
        range(len(strikes)),
        key=lambda index: abs(
            strikes[index]
            - option_chain_data.atm_strike
        ),
    )

    start_index = max(
        0,
        atm_index - strikes_each_side,
    )

    end_index = min(
        len(strikes),
        atm_index + strikes_each_side + 1,
    )

    selected_strikes = strikes[
        start_index:end_index
    ]

    return option_chain_data.option_chain[
        option_chain_data.option_chain[
            "strike"
        ].isin(selected_strikes)
    ].copy().reset_index(drop=True)


# ============================================================
# SUMMARY PRINTING
# ============================================================

def print_option_chain_summary(
    option_chain_data: OptionChainData,
) -> None:
    """
    Print the standard option-chain summary.
    """

    separator = "=" * 72

    print()
    print(separator)
    print("AQSD OPTION CHAIN LOADER")
    print(separator)

    print(
        f"Spot Price               : "
        f"{option_chain_data.spot_price:,.2f}"
    )

    print(
        f"ATM Strike               : "
        f"{option_chain_data.atm_strike:,.2f}"
    )

    print(
        f"Strike Step              : "
        f"{option_chain_data.strike_step:,.2f}"
    )

    print(
        f"Number of Strikes        : "
        f"{option_chain_data.number_of_strikes}"
    )

    print(
        f"Call Rows                : "
        f"{option_chain_data.number_of_calls}"
    )

    print(
        f"Put Rows                 : "
        f"{option_chain_data.number_of_puts}"
    )

    print(
        f"Source                   : "
        f"{option_chain_data.source}"
    )

    print(
        f"Timestamp                : "
        f"{option_chain_data.timestamp}"
    )

    print(separator)
    print()


# ============================================================
# SAMPLE TEST
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample data for independent loader testing.
    """

    rows: list[dict[str, Any]] = []

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
                "ImpliedVolatility": 15.25,
                "LTP": 250.0,
            }
        )

        rows.append(
            {
                "strikePrice": strike,
                "optionType": "PE",
                "OI": values["pe_oi"],
                "ChangeOI": 18000,
                "TotalVolume": 92000,
                "ImpliedVolatility": 16.10,
                "LTP": 235.0,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    """
    Test the loader using sample option-chain data.
    """

    sample_dataframe = create_sample_option_chain()

    option_chain_data = load_option_chain(
        source=sample_dataframe,
        spot_price=57582.25,
    )

    print_option_chain_summary(
        option_chain_data
    )

    print("Standardised Option Chain")
    print("-" * 72)

    print(
        option_chain_data.option_chain[
            [
                "strike",
                "option_type",
                "open_interest",
                "change_in_oi",
                "volume",
                "iv",
                "ltp",
            ]
        ].to_string(index=False)
    )

    print()
    print("ATM Window")
    print("-" * 72)

    atm_window = get_atm_window(
        option_chain_data=option_chain_data,
        strikes_each_side=1,
    )

    print(
        atm_window[
            [
                "strike",
                "option_type",
                "open_interest",
                "iv",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()