"""
AQSD
Option Intelligence

Module: fyers_option_chain_loader.py
Version: 1.0
Author: AQSD

Description:
Fetches live option-chain data from FYERS and converts it into the
standard AQSD OptionChainData format.

Architecture:
FYERS API
    ↓
fyers_option_chain_loader.py
    ↓
option_chain_loader.py
    ↓
OI / PCR / Max Pain / Walls / Volatility / Probability / Dashboard

Important:
- This module does not place orders.
- It reads credentials from the AQSD .env file.
- It keeps FYERS-specific logic outside the analytics engines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    load_option_chain,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / "Output" / "LiveOptionChain"

DEFAULT_UNDERLYING = "BANKNIFTY"
DEFAULT_SYMBOL = "NSE:NIFTYBANK-INDEX"
DEFAULT_STRIKE_COUNT = 15

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# RESULT MODEL
# ============================================================

@dataclass(slots=True)
class FyersOptionChainResult:
    """
    Complete result returned by the FYERS live loader.
    """

    underlying: str
    symbol: str
    spot_price: float
    raw_response: dict[str, Any]
    raw_dataframe: pd.DataFrame
    option_chain_data: OptionChainData


# ============================================================
# ENVIRONMENT
# ============================================================

def read_environment_value(
    *names: str,
) -> str:
    """
    Return the first available non-empty environment value.
    """

    for name in names:
        value = os.getenv(name)

        if value and value.strip():
            return value.strip()

    return ""


def load_fyers_credentials() -> tuple[str, str]:
    """
    Load FYERS client ID and access token from .env.

    Supported variable names:
    - FYERS_CLIENT_ID
    - FYERS_APP_ID
    - CLIENT_ID

    and:

    - FYERS_ACCESS_TOKEN
    - ACCESS_TOKEN
    """

    load_dotenv(
        ENV_FILE,
        override=False,
    )

    client_id = read_environment_value(
        "FYERS_CLIENT_ID",
        "FYERS_APP_ID",
        "CLIENT_ID",
    )

    access_token = read_environment_value(
        "FYERS_ACCESS_TOKEN",
        "ACCESS_TOKEN",
    )

    if not client_id:
        raise RuntimeError(
            "FYERS client ID was not found in .env. "
            "Add FYERS_CLIENT_ID=<your_client_id>."
        )

    if not access_token:
        raise RuntimeError(
            "FYERS access token was not found in .env. "
            "Add FYERS_ACCESS_TOKEN=<your_access_token>."
        )

    return client_id, access_token


# ============================================================
# FYERS CLIENT
# ============================================================

def create_fyers_client() -> Any:
    """
    Create an authenticated FYERS API client.
    """

    client_id, access_token = (
        load_fyers_credentials()
    )

    return fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path="",
    )


# ============================================================
# GENERIC RESPONSE HELPERS
# ============================================================

def normalize_key(
    value: Any,
) -> str:
    """
    Normalize dictionary keys for matching.
    """

    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )


def get_first_value(
    source: Mapping[str, Any],
    aliases: Sequence[str],
    default: Any = None,
) -> Any:
    """
    Return the first matching value using normalized aliases.
    """

    normalized_source = {
        normalize_key(key): value
        for key, value in source.items()
    }

    for alias in aliases:
        normalized_alias = normalize_key(
            alias
        )

        if normalized_alias in normalized_source:
            return normalized_source[
                normalized_alias
            ]

    return default


def ensure_success_response(
    response: Any,
    operation: str,
) -> dict[str, Any]:
    """
    Validate a FYERS API response.
    """

    if not isinstance(response, Mapping):
        raise RuntimeError(
            f"{operation} returned an invalid response type: "
            f"{type(response).__name__}"
        )

    result = dict(response)

    status = str(
        result.get(
            "s",
            result.get(
                "status",
                "",
            ),
        )
    ).strip().lower()

    code = result.get("code")

    message = (
        result.get("message")
        or result.get("msg")
        or result.get("error")
        or ""
    )

    failure_statuses = {
        "error",
        "failed",
        "failure",
        "not_ok",
    }

    if status in failure_statuses:
        raise RuntimeError(
            f"{operation} failed: {message or result}"
        )

    if isinstance(code, (int, float)) and int(code) < 0:
        raise RuntimeError(
            f"{operation} failed with code {code}: "
            f"{message or result}"
        )

    return result


def recursively_find_row_lists(
    value: Any,
) -> list[list[dict[str, Any]]]:
    """
    Find dictionary lists inside a nested API response.
    """

    candidates: list[
        list[dict[str, Any]]
    ] = []

    if isinstance(value, Mapping):
        for item in value.values():
            candidates.extend(
                recursively_find_row_lists(
                    item
                )
            )

    elif isinstance(value, list):
        dictionary_rows = [
            dict(item)
            for item in value
            if isinstance(item, Mapping)
        ]

        if dictionary_rows:
            candidates.append(
                dictionary_rows
            )

        for item in value:
            candidates.extend(
                recursively_find_row_lists(
                    item
                )
            )

    return candidates


def score_option_rows(
    rows: list[dict[str, Any]],
) -> int:
    """
    Score whether a list resembles an option chain.
    """

    score = 0

    for row in rows[:10]:
        normalized_keys = {
            normalize_key(key)
            for key in row.keys()
        }

        if normalized_keys.intersection(
            {
                "strikeprice",
                "strike",
            }
        ):
            score += 3

        if normalized_keys.intersection(
            {
                "optiontype",
                "right",
                "otype",
            }
        ):
            score += 3

        if normalized_keys.intersection(
            {
                "oi",
                "openinterest",
            }
        ):
            score += 2

        if normalized_keys.intersection(
            {
                "ltp",
                "lastprice",
            }
        ):
            score += 1

        symbol_value = get_first_value(
            row,
            [
                "symbol",
                "fyToken",
                "description",
            ],
            default="",
        )

        symbol_text = str(
            symbol_value
        ).upper()

        if (
            "CE" in symbol_text
            or "PE" in symbol_text
        ):
            score += 2

    return score


def extract_option_rows(
    response: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract the most likely option-chain row list.
    """

    candidates = recursively_find_row_lists(
        response
    )

    if not candidates:
        raise RuntimeError(
            "No option-chain rows were found in the FYERS response."
        )

    best_rows = max(
        candidates,
        key=score_option_rows,
    )

    if score_option_rows(best_rows) <= 0:
        raise RuntimeError(
            "FYERS returned data, but it could not be identified "
            "as an option chain."
        )

    return best_rows


# ============================================================
# FYERS FIELD CONVERSION
# ============================================================

def infer_option_type(
    row: Mapping[str, Any],
) -> str:
    """
    Infer CE or PE from explicit fields or the symbol.
    """

    explicit_value = get_first_value(
        row,
        [
            "optionType",
            "option_type",
            "right",
            "type",
            "otype",
        ],
        default="",
    )

    explicit_text = str(
        explicit_value
    ).strip().upper()

    if explicit_text in {
        "CE",
        "CALL",
        "C",
    }:
        return "CE"

    if explicit_text in {
        "PE",
        "PUT",
        "P",
    }:
        return "PE"

    symbol = str(
        get_first_value(
            row,
            [
                "symbol",
                "description",
            ],
            default="",
        )
    ).upper()

    if symbol.endswith("CE") or " CE" in symbol:
        return "CE"

    if symbol.endswith("PE") or " PE" in symbol:
        return "PE"

    return ""


def convert_fyers_rows(
    rows: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Convert FYERS option rows into AQSD loader-compatible columns.
    """

    converted_rows: list[
        dict[str, Any]
    ] = []

    for row in rows:
        option_type = infer_option_type(
            row
        )

        strike = get_first_value(
            row,
            [
                "strikePrice",
                "strike_price",
                "strike",
            ],
        )

        if (
            strike is None
            or option_type not in {"CE", "PE"}
        ):
            continue

        converted_rows.append(
            {
                "strikePrice": strike,
                "optionType": option_type,
                "OI": get_first_value(
                    row,
                    [
                        "openInterest",
                        "open_interest",
                        "oi",
                    ],
                    default=0.0,
                ),
                "ChangeOI": get_first_value(
                    row,
                    [
                        "changeInOI",
                        "change_in_oi",
                        "changeOI",
                        "oiChange",
                        "oich",
                    ],
                    default=0.0,
                ),
                "TotalVolume": get_first_value(
                    row,
                    [
                        "totalVolume",
                        "volume",
                        "vol",
                        "tradedVolume",
                    ],
                    default=0.0,
                ),
                "LTP": get_first_value(
                    row,
                    [
                        "ltp",
                        "lastPrice",
                        "last_price",
                    ],
                    default=0.0,
                ),
                "IV": get_first_value(
                    row,
                    [
                        "impliedVolatility",
                        "implied_volatility",
                        "iv",
                    ],
                    default=None,
                ),
                "symbol": get_first_value(
                    row,
                    [
                        "symbol",
                        "description",
                    ],
                    default="",
                ),
                "bid": get_first_value(
                    row,
                    [
                        "bid",
                        "bidPrice",
                    ],
                    default=None,
                ),
                "ask": get_first_value(
                    row,
                    [
                        "ask",
                        "askPrice",
                    ],
                    default=None,
                ),
            }
        )

    dataframe = pd.DataFrame(
        converted_rows
    )

    if dataframe.empty:
        raise RuntimeError(
            "No valid CE or PE contracts were obtained from FYERS."
        )

    numeric_columns = [
        "strikePrice",
        "OI",
        "ChangeOI",
        "TotalVolume",
        "LTP",
        "IV",
        "bid",
        "ask",
    ]

    for column in numeric_columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

    dataframe["OI"] = dataframe[
        "OI"
    ].fillna(0.0)

    dataframe["ChangeOI"] = dataframe[
        "ChangeOI"
    ].fillna(0.0)

    dataframe["TotalVolume"] = dataframe[
        "TotalVolume"
    ].fillna(0.0)

    dataframe["LTP"] = dataframe[
        "LTP"
    ].fillna(0.0)

    dataframe = dataframe.dropna(
        subset=["strikePrice"]
    )

    return dataframe.sort_values(
        by=[
            "strikePrice",
            "optionType",
        ]
    ).reset_index(drop=True)


# ============================================================
# SPOT PRICE
# ============================================================

def extract_spot_from_option_response(
    response: Mapping[str, Any],
) -> float | None:
    """
    Search the option-chain response for an underlying spot value.
    """

    spot_aliases = {
        "ltp",
        "spot",
        "spotprice",
        "underlyingvalue",
        "underlyingprice",
    }

    def search(
        value: Any,
    ) -> float | None:
        if isinstance(value, Mapping):
            normalized = {
                normalize_key(key): item
                for key, item in value.items()
            }

            for alias in spot_aliases:
                if alias in normalized:
                    candidate = pd.to_numeric(
                        pd.Series(
                            [normalized[alias]]
                        ),
                        errors="coerce",
                    ).iloc[0]

                    if pd.notna(candidate) and float(candidate) > 0:
                        return float(candidate)

            for item in value.values():
                found = search(item)

                if found is not None:
                    return found

        elif isinstance(value, list):
            for item in value:
                found = search(item)

                if found is not None:
                    return found

        return None

    return search(response)


def fetch_spot_price(
    fyers: Any,
    symbol: str,
) -> float:
    """
    Fetch the live underlying spot price using FYERS Quotes API.
    """

    response = fyers.quotes(
        data={
            "symbols": symbol,
        }
    )

    validated = ensure_success_response(
        response,
        operation="FYERS Quotes API",
    )

    candidates = recursively_find_row_lists(
        validated
    )

    for rows in candidates:
        for row in rows:
            ltp = get_first_value(
                row,
                [
                    "lp",
                    "ltp",
                    "lastPrice",
                ],
            )

            numeric_ltp = pd.to_numeric(
                pd.Series([ltp]),
                errors="coerce",
            ).iloc[0]

            if (
                pd.notna(numeric_ltp)
                and float(numeric_ltp) > 0
            ):
                return float(numeric_ltp)

    raise RuntimeError(
        f"Could not obtain spot price for {symbol}."
    )


# ============================================================
# LIVE OPTION CHAIN
# ============================================================

def call_fyers_option_chain(
    fyers: Any,
    symbol: str,
    strike_count: int,
    timestamp: str = "",
) -> dict[str, Any]:
    """
    Call the FYERS option-chain method.

    The method-name checks allow compatibility across SDK releases.
    """

    payload = {
        "symbol": symbol,
        "strikecount": int(
            strike_count
        ),
        "timestamp": timestamp,
    }

    supported_method_names = [
        "optionchain",
        "option_chain",
        "optionChain",
    ]

    for method_name in supported_method_names:
        method = getattr(
            fyers,
            method_name,
            None,
        )

        if callable(method):
            response = method(
                data=payload
            )

            return ensure_success_response(
                response,
                operation="FYERS Option Chain API",
            )

    available_methods = [
        name
        for name in dir(fyers)
        if "option" in name.lower()
    ]

    raise RuntimeError(
        "The installed fyers-apiv3 package does not expose an "
        "option-chain method. Available option-related methods: "
        f"{available_methods}. Update the package using: "
        "python -m pip install --upgrade fyers-apiv3"
    )


def fetch_live_option_chain(
    underlying: str = DEFAULT_UNDERLYING,
    symbol: str = DEFAULT_SYMBOL,
    strike_count: int = DEFAULT_STRIKE_COUNT,
    timestamp: str = "",
    save_raw_csv: bool = True,
) -> FyersOptionChainResult:
    """
    Fetch and standardize a live FYERS option chain.
    """

    if strike_count < 1:
        raise ValueError(
            "strike_count must be at least 1."
        )

    fyers = create_fyers_client()

    raw_response = call_fyers_option_chain(
        fyers=fyers,
        symbol=symbol,
        strike_count=strike_count,
        timestamp=timestamp,
    )

    raw_rows = extract_option_rows(
        raw_response
    )

    raw_dataframe = convert_fyers_rows(
        raw_rows
    )

    spot_price = extract_spot_from_option_response(
        raw_response
    )

    if spot_price is None:
        spot_price = fetch_spot_price(
            fyers=fyers,
            symbol=symbol,
        )

    option_chain_data = load_option_chain(
        source=raw_dataframe,
        spot_price=spot_price,
    )

    if save_raw_csv:
        raw_file = (
            OUTPUT_DIR
            / f"{underlying.upper()}_FYERS_Live_Option_Chain.csv"
        )

        raw_dataframe.to_csv(
            raw_file,
            index=False,
        )

    return FyersOptionChainResult(
        underlying=underlying.upper(),
        symbol=symbol,
        spot_price=spot_price,
        raw_response=raw_response,
        raw_dataframe=raw_dataframe,
        option_chain_data=option_chain_data,
    )


# ============================================================
# TERMINAL REPORT
# ============================================================

def print_live_chain_summary(
    result: FyersOptionChainResult,
) -> None:
    """
    Print a concise live-chain summary.
    """

    chain = result.option_chain_data

    separator = "=" * 76

    print()
    print(separator)
    print(
        "AQSD — FYERS LIVE OPTION CHAIN LOADER"
    )
    print(separator)

    print(
        f"Underlying           : "
        f"{result.underlying}"
    )

    print(
        f"FYERS Symbol         : "
        f"{result.symbol}"
    )

    print(
        f"Spot Price           : "
        f"{result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike           : "
        f"{chain.atm_strike:,.2f}"
    )

    print(
        f"Strike Step          : "
        f"{chain.strike_step:,.2f}"
    )

    print(
        f"Number of Strikes    : "
        f"{chain.number_of_strikes}"
    )

    print(
        f"Call Contracts       : "
        f"{len(chain.calls_df)}"
    )

    print(
        f"Put Contracts        : "
        f"{len(chain.puts_df)}"
    )

    print(
        f"Raw Rows             : "
        f"{len(result.raw_dataframe)}"
    )

    iv_count = int(
        pd.to_numeric(
            result.raw_dataframe.get(
                "IV",
                pd.Series(dtype="float64"),
            ),
            errors="coerce",
        ).notna().sum()
    )

    print(
        f"Contracts With IV    : "
        f"{iv_count}"
    )

    print(
        f"Timestamp            : "
        f"{chain.timestamp}"
    )

    print()
    print("Sample Contracts")
    print("-" * 76)

    display_columns = [
        "strikePrice",
        "optionType",
        "OI",
        "ChangeOI",
        "TotalVolume",
        "LTP",
        "IV",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in result.raw_dataframe.columns
    ]

    print(
        result.raw_dataframe[
            available_columns
        ].head(12).to_string(
            index=False
        )
    )

    print(separator)
    print()


# ============================================================
# INDEPENDENT TEST
# ============================================================

def main() -> None:
    """
    Fetch and test the live BANKNIFTY option chain.
    """

    result = fetch_live_option_chain(
        underlying="BANKNIFTY",
        symbol="NSE:NIFTYBANK-INDEX",
        strike_count=15,
        timestamp="",
        save_raw_csv=True,
    )

    print_live_chain_summary(
        result
    )


if __name__ == "__main__":
    main()