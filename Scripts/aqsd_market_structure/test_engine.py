"""
AQSD
Market Structure Engine

Module: test_engine.py
Version: 1.0
Author: AQSD
Description:
Downloads daily BANKNIFTY historical candles from FYERS
and tests the AQSD Trend Engine.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from Scripts.aqsd_market_structure.trend import analyze_trend


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

SYMBOL = "NSE:NIFTYBANK-INDEX"
RESOLUTION = "D"
LOOKBACK_DAYS = 450


def read_environment_value(*names: str) -> str:
    """
    Read the first available environment variable.

    Args:
        names: Possible environment-variable names.

    Returns:
        Environment-variable value.

    Raises:
        RuntimeError: If none of the names are available.
    """

    for name in names:
        value = os.getenv(name)

        if value:
            return value.strip()

    accepted_names = ", ".join(names)

    raise RuntimeError(
        f"Missing environment variable. Expected one of: "
        f"{accepted_names}"
    )


def create_fyers_client() -> fyersModel.FyersModel:
    """
    Create an authenticated FYERS API client.
    """

    if not ENV_FILE.exists():
        raise FileNotFoundError(
            f".env file not found: {ENV_FILE}"
        )

    load_dotenv(ENV_FILE)

    client_id = read_environment_value(
        "FYERS_CLIENT_ID",
        "FYERS_APP_ID",
        "CLIENT_ID",
        "APP_ID",
    )

    access_token = read_environment_value(
        "FYERS_ACCESS_TOKEN",
        "ACCESS_TOKEN",
    )

    return fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path=str(BASE_DIR),
    )


def download_fyers_history(
    fyers: fyersModel.FyersModel,
    symbol: str,
) -> pd.DataFrame:
    """
    Download daily historical candles from FYERS.

    FYERS candles are returned in this sequence:

        timestamp, open, high, low, close, volume
    """

    range_to = date.today()
    range_from = range_to - timedelta(days=LOOKBACK_DAYS)

    request_data = {
        "symbol": symbol,
        "resolution": RESOLUTION,
        "date_format": "1",
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "cont_flag": "1",
    }

    response = fyers.history(data=request_data)

    if not isinstance(response, dict):
        raise RuntimeError(
            f"Unexpected FYERS response type: {type(response)}"
        )

    if response.get("s") != "ok":
        message = response.get(
            "message",
            "Unknown FYERS history error",
        )

        code = response.get("code")

        raise RuntimeError(
            f"FYERS history request failed. "
            f"Code: {code}; Message: {message}"
        )

    candles = response.get("candles", [])

    if not candles:
        raise RuntimeError(
            f"No historical candles returned for {symbol}."
        )

    df = pd.DataFrame(
        candles,
        columns=[
            "Timestamp",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ],
    )

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"],
        unit="s",
        errors="coerce",
    )

    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = (
        df.dropna(
            subset=[
                "Timestamp",
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )
        .drop_duplicates(subset=["Timestamp"])
        .sort_values("Timestamp")
        .set_index("Timestamp")
    )

    if len(df) < 200:
        raise RuntimeError(
            f"Only {len(df)} valid candles were returned. "
            "At least 200 candles are required for EMA200."
        )

    return df


def print_trend_result(
    symbol: str,
    df: pd.DataFrame,
) -> None:
    """
    Run the AQSD Trend Engine and print its result.
    """

    result = analyze_trend(df)

    print()
    print("=" * 60)
    print("AQSD MARKET STRUCTURE — TREND TEST")
    print("=" * 60)
    print(f"Symbol       : {symbol}")
    print(f"Candles      : {len(df)}")
    print(f"Last candle  : {df.index[-1]}")
    print("-" * 60)
    print(f"Direction    : {result.direction.value}")
    print(f"Strength     : {result.strength.value}")
    print(f"Close        : {result.close:.2f}")
    print(f"EMA20        : {result.ema20:.2f}")
    print(f"EMA50        : {result.ema50:.2f}")
    print(f"EMA200       : {result.ema200:.2f}")
    print("-" * 60)
    print("Evidence")

    for item in result.evidence:
        print(f"[OK] {item}")

    print("=" * 60)


def main() -> None:
    """
    Execute the FYERS BANKNIFTY Trend Engine test.
    """

    print()
    print(f"Connecting to FYERS for {SYMBOL}...")

    fyers = create_fyers_client()

    print("Downloading daily historical candles...")

    market_data = download_fyers_history(
        fyers=fyers,
        symbol=SYMBOL,
    )

    print_trend_result(
        symbol=SYMBOL,
        df=market_data,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print()
        print("=" * 60)
        print("AQSD TEST FAILED")
        print("=" * 60)
        print(f"{type(error).__name__}: {error}")
        print("=" * 60)

        raise SystemExit(1)