"""
AQSD
Live IV Surface Runner

Module: live_iv_surface_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain from FYERS, obtains the
actual BANKNIFTY index price, calculates the correct ATM strike,
runs the IV Surface Engine and exports live IV analytics.

Analytics only. No order placement.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
)
from Scripts.option_intelligence.iv_surface_engine import (
    IVSurfaceResult,
    analyze_iv_surface,
    export_iv_surface,
    print_iv_surface_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"

STRIKE_COUNT = 30

DEFAULT_DAYS_TO_EXPIRY = 5.0
DEFAULT_RISK_FREE_RATE = 0.065
DEFAULT_DIVIDEND_YIELD = 0.0

OUTPUT_DIRECTORY = (
    BASE_DIR
    / "Output"
    / "IV_Surface_Live"
)

OUTPUT_PREFIX = (
    "BANKNIFTY_LIVE_IV_SURFACE"
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
        BASE_DIR / ".env"
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
# LIVE SPOT
# ============================================================

def fetch_banknifty_spot_price() -> float:
    """
    Fetch the actual BANKNIFTY index LTP directly from FYERS.
    """

    fyers = build_fyers_client()

    response = fyers.quotes(
        {
            "symbols": FYERS_SYMBOL,
        }
    )

    if not isinstance(response, dict):
        raise RuntimeError(
            "Invalid FYERS BANKNIFTY quote response."
        )

    quote_rows = response.get(
        "d",
        [],
    )

    if not quote_rows:
        raise RuntimeError(
            f"FYERS returned no BANKNIFTY quote: {response}"
        )

    first_quote = quote_rows[0]

    quote_values = first_quote.get(
        "v",
        {},
    )

    spot_value = (
        quote_values.get("lp")
        or quote_values.get("ltp")
        or quote_values.get("last_price")
    )

    try:
        spot_price = float(
            spot_value
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "FYERS BANKNIFTY quote did not contain "
            f"a valid spot price: {response}"
        ) from error

    if spot_price <= 1000.0:
        raise RuntimeError(
            "FYERS returned an invalid BANKNIFTY spot price: "
            f"{spot_price}"
        )

    return spot_price


# ============================================================
# ATM STRIKE
# ============================================================

def calculate_atm_strike(
    spot_price: float,
    strike_step: float,
) -> float:
    """
    Round the actual spot price to the nearest strike interval.
    """

    if spot_price <= 0.0:
        raise ValueError(
            "spot_price must be positive."
        )

    if strike_step <= 0.0:
        raise ValueError(
            "strike_step must be positive."
        )

    return (
        round(
            spot_price / strike_step
        )
        * strike_step
    )


# ============================================================
# LIVE WORKFLOW
# ============================================================

def run_live_iv_surface() -> IVSurfaceResult:
    """
    Run the complete live BANKNIFTY IV Surface workflow.
    """

    print()
    print("=" * 82)
    print(
        "AQSD — LIVE BANKNIFTY IV SURFACE ENGINE"
        .center(82)
    )
    print("=" * 82)
    print()

    print(
        "1/4  Fetching live FYERS option-chain data..."
    )

    live_result = fetch_live_option_chain(
        underlying=UNDERLYING,
        symbol=FYERS_SYMBOL,
        strike_count=STRIKE_COUNT,
        timestamp="",
        save_raw_csv=True,
    )

    option_chain_data = (
        live_result.option_chain_data
    )

    live_dataframe = (
        live_result.raw_dataframe
    )

    if live_dataframe is None:
        raise RuntimeError(
            "Live option-chain dataframe was not returned."
        )

    if live_dataframe.empty:
        raise RuntimeError(
            "Live option-chain dataframe is empty."
        )

    print(
        "2/4  Fetching actual BANKNIFTY spot price..."
    )

    spot_price = (
        fetch_banknifty_spot_price()
    )

    strike_step = float(
        option_chain_data.strike_step
    )

    atm_strike = calculate_atm_strike(
        spot_price=spot_price,
        strike_step=strike_step,
    )

    print()
    print(
        f"Spot Price       : {spot_price:,.2f}"
    )
    print(
        f"ATM Strike       : {atm_strike:,.2f}"
    )
    print(
        f"Strike Step      : {strike_step:,.2f}"
    )
    print(
        f"Option Rows      : {len(live_dataframe)}"
    )
    print()

    print(
        "3/4  Calculating live implied-volatility surface..."
    )

    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    result = analyze_iv_surface(
        option_chain=live_dataframe,
        spot_price=spot_price,
        underlying=UNDERLYING,
        atm_strike=atm_strike,
        strike_step=strike_step,
        days_to_expiry=(
            DEFAULT_DAYS_TO_EXPIRY
        ),
        risk_free_rate=(
            DEFAULT_RISK_FREE_RATE
        ),
        dividend_yield=(
            DEFAULT_DIVIDEND_YIELD
        ),
        timestamp=timestamp,
    )

    print(
        "4/4  Exporting live IV Surface files..."
    )

    exported_files = export_iv_surface(
        result=result,
        output_directory=(
            OUTPUT_DIRECTORY
        ),
        filename_prefix=(
            OUTPUT_PREFIX
        ),
    )

    print_iv_surface_summary(
        result
    )

    print()
    print("Exported Files")
    print("-" * 82)

    for label, path in exported_files.items():
        print(
            f"{label:22} : {path}"
        )

    print()
    print(
        f"Output Folder         : "
        f"{OUTPUT_DIRECTORY}"
    )
    print(
        "Status                : SUCCESS"
    )
    print("=" * 82)

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Execute the live IV Surface runner.
    """

    try:
        run_live_iv_surface()

    except Exception as error:
        print()
        print("=" * 82)
        print(
            "AQSD LIVE IV SURFACE ENGINE — FAILED"
        )
        print("=" * 82)
        print(
            f"Error Type : "
            f"{type(error).__name__}"
        )
        print(
            f"Message    : {error}"
        )
        print("=" * 82)

        raise


if __name__ == "__main__":
    main()