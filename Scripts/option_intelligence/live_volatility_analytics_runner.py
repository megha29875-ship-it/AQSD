"""
AQSD
Live Volatility Analytics Runner

Module: live_volatility_analytics_runner.py
Version: 1.0
Author: AQSD

Description:
Reads the latest live BANKNIFTY ATM IV from the IV Surface output,
downloads BANKNIFTY daily historical candles from FYERS, runs the
Volatility Analytics Engine and exports live volatility intelligence.

Analytics only. No order placement.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from Scripts.option_intelligence.volatility_analytics_engine import (
    VolatilityAnalyticsResult,
    analyze_volatility,
    export_volatility_analytics,
    print_volatility_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

ENV_FILE = BASE_DIR / ".env"

UNDERLYING = "BANKNIFTY"

FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"

RESOLUTION = "D"

HISTORICAL_LOOKBACK_DAYS = 360

LIVE_IV_SUMMARY_FILE = (
    BASE_DIR
    / "Output"
    / "IV_Surface_Live"
    / "BANKNIFTY_LIVE_IV_SURFACE_Summary.json"
)


# ============================================================
# ENVIRONMENT
# ============================================================

def read_environment_value(
    *names: str,
) -> str:
    """
    Return the first available environment variable.
    """

    for name in names:
        value = os.getenv(name)

        if value:
            return value.strip()

    return ""


def build_fyers_client() -> Any:
    """
    Build an authenticated FYERS client.
    """

    load_dotenv(
        ENV_FILE
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
            "FYERS client ID was not found in the .env file."
        )

    if not access_token:
        raise RuntimeError(
            "FYERS access token was not found in the .env file."
        )

    return fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path="",
    )


# ============================================================
# LIVE IV SUMMARY
# ============================================================

def load_json_file(
    file_path: Path,
) -> dict[str, Any]:
    """
    Load a JSON file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file was not found: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            f"JSON file did not contain an object: {file_path}"
        )

    return data


def read_live_iv_values() -> tuple[
    float,
    float,
    float,
    str,
]:
    """
    Read live ATM IV, spot, ATM strike and timestamp.
    """

    data = load_json_file(
        LIVE_IV_SUMMARY_FILE
    )

    atm_iv_value = data.get(
        "atm_iv"
    )

    spot_price_value = data.get(
        "spot_price"
    )

    atm_strike_value = data.get(
        "atm_strike"
    )

    timestamp = str(
        data.get(
            "timestamp",
            "",
        )
    )

    try:
        atm_iv = float(
            atm_iv_value
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "Live IV Surface summary does not contain "
            "a valid ATM IV."
        ) from error

    try:
        spot_price = float(
            spot_price_value
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "Live IV Surface summary does not contain "
            "a valid spot price."
        ) from error

    try:
        atm_strike = float(
            atm_strike_value
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "Live IV Surface summary does not contain "
            "a valid ATM strike."
        ) from error

    if atm_iv <= 0.0:
        raise RuntimeError(
            f"Invalid live ATM IV: {atm_iv}"
        )

    if spot_price <= 1000.0:
        raise RuntimeError(
            f"Invalid BANKNIFTY spot price: {spot_price}"
        )

    return (
        atm_iv,
        spot_price,
        atm_strike,
        timestamp,
    )


# ============================================================
# HISTORICAL CANDLES
# ============================================================

def parse_fyers_candles(
    response: dict[str, Any],
) -> pd.DataFrame:
    """
    Convert FYERS candle response into a dataframe.
    """

    candles = response.get(
        "candles",
        []
    )

    if not candles:
        raise RuntimeError(
            f"FYERS returned no historical candles: {response}"
        )

    dataframe = pd.DataFrame(
        candles,
        columns=[
            "epoch",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    dataframe["datetime"] = pd.to_datetime(
        dataframe["epoch"],
        unit="s",
        errors="coerce",
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe = dataframe.dropna(
        subset=[
            "datetime",
            "close",
        ]
    )

    dataframe = dataframe.loc[
        dataframe["close"] > 0.0
    ].copy()

    dataframe = dataframe.sort_values(
        "datetime"
    ).drop_duplicates(
        subset=["datetime"],
        keep="last",
    ).reset_index(
        drop=True
    )

    if dataframe.empty:
        raise RuntimeError(
            "No valid BANKNIFTY historical candles remained."
        )

    return dataframe


def fetch_banknifty_price_history(
    lookback_days: int = HISTORICAL_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """
    Fetch daily BANKNIFTY candles from FYERS.
    """

    fyers = build_fyers_client()

    end_date = date.today()

    start_date = (
        end_date
        - timedelta(
            days=lookback_days
        )
    )

    request_data = {
        "symbol": FYERS_SYMBOL,
        "resolution": RESOLUTION,
        "date_format": "1",
        "range_from": start_date.isoformat(),
        "range_to": end_date.isoformat(),
        "cont_flag": "1",
    }

    response = fyers.history(
        data=request_data
    )

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            "Invalid FYERS historical-data response."
        )

    response_status = str(
        response.get(
            "s",
            "",
        )
    ).lower()

    if response_status not in {
        "ok",
        "success",
    }:
        raise RuntimeError(
            f"FYERS historical-data request failed: {response}"
        )

    return parse_fyers_candles(
        response
    )


# ============================================================
# LIVE WORKFLOW
# ============================================================

def run_live_volatility_analytics(
) -> VolatilityAnalyticsResult:
    """
    Run live BANKNIFTY volatility analytics.
    """

    print()
    print("=" * 86)
    print(
        "AQSD — LIVE BANKNIFTY VOLATILITY ANALYTICS"
        .center(86)
    )
    print("=" * 86)
    print()

    print(
        "1/4  Reading latest live IV Surface summary..."
    )

    (
        current_atm_iv,
        spot_price,
        atm_strike,
        iv_timestamp,
    ) = read_live_iv_values()

    print()
    print(
        f"Spot Price          : {spot_price:,.2f}"
    )
    print(
        f"ATM Strike          : {atm_strike:,.2f}"
    )
    print(
        f"Current ATM IV      : {current_atm_iv:.2f}%"
    )

    if iv_timestamp:
        print(
            f"IV Timestamp        : {iv_timestamp}"
        )

    print()
    print(
        "2/4  Fetching BANKNIFTY historical candles..."
    )

    price_history = (
        fetch_banknifty_price_history()
    )

    print(
        f"Historical Candles  : {len(price_history)}"
    )

    print()
    print(
        "3/4  Running Volatility Analytics Engine..."
    )

    result = analyze_volatility(
        current_atm_iv=current_atm_iv,
        spot_price=spot_price,
        price_history=price_history,
        underlying=UNDERLYING,
        timestamp=iv_timestamp or None,
    )

    print(
        "4/4  Exporting live volatility analytics..."
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
    print("-" * 86)

    for label, path in exported_files.items():
        print(
            f"{label:26} : {path}"
        )

    print()
    print(
        "Status                    : SUCCESS"
    )
    print("=" * 86)

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Execute the live volatility runner.
    """

    try:
        run_live_volatility_analytics()

    except Exception as error:
        print()
        print("=" * 86)
        print(
            "AQSD LIVE VOLATILITY ANALYTICS — FAILED"
        )
        print("=" * 86)
        print(
            f"Error Type : {type(error).__name__}"
        )
        print(
            f"Message    : {error}"
        )
        print("=" * 86)

        raise


if __name__ == "__main__":
    main()