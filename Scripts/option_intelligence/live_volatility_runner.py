"""
AQSD
Option Intelligence

Module: live_volatility_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain and daily historical prices
from FYERS, then runs the AQSD Volatility Intelligence Engine.

Workflow:
FYERS Live Option Chain
        ↓
FYERS Daily Historical Prices
        ↓
Volatility Engine
        ↓
Shared Exporter

Important:
- FYERS may not provide IV in every option-chain response.
- Historical Volatility can still be calculated from daily closes.
- IV Rank and IV Percentile require saved historical IV observations.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    create_fyers_client,
    ensure_success_response,
    fetch_live_option_chain,
)

from Scripts.option_intelligence.volatility_engine import (
    analyze_volatility,
    print_volatility_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"

STRIKE_COUNT = 15

HISTORICAL_LOOKBACK_DAYS = 120
HV_LOOKBACK_DAYS = 20
EXPECTED_MOVE_DAYS = 7

VOLATILITY_OUTPUT_DIR = (
    BASE_DIR
    / "Output"
    / "Volatility"
)

IV_HISTORY_FILE = (
    VOLATILITY_OUTPUT_DIR
    / "BANKNIFTY_LIVE_IV_History.csv"
)

VOLATILITY_OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def safe_numeric(
    value: Any,
) -> float | None:
    """
    Convert a value into a float safely.
    """

    numeric_value = pd.to_numeric(
        pd.Series([value]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(numeric_value):
        return None

    return float(numeric_value)


def normalize_iv_value(
    value: Any,
) -> float | None:
    """
    Convert IV into percentage form.

    Examples:
        0.185 becomes 18.5
        18.5 remains 18.5
    """

    numeric_value = safe_numeric(value)

    if (
        numeric_value is None
        or numeric_value <= 0
    ):
        return None

    if numeric_value <= 3.0:
        return float(
            numeric_value * 100.0
        )

    return float(numeric_value)


# ============================================================
# FYERS HISTORICAL PRICE DATA
# ============================================================

def extract_candles(
    response: Mapping[str, Any],
) -> list[list[Any]]:
    """
    Extract candle rows from a FYERS history response.
    """

    candles = response.get("candles")

    if isinstance(candles, list):
        valid_rows = [
            row
            for row in candles
            if (
                isinstance(row, list)
                and len(row) >= 6
            )
        ]

        return valid_rows

    data = response.get("data")

    if isinstance(data, Mapping):
        nested_candles = data.get("candles")

        if isinstance(
            nested_candles,
            list,
        ):
            return [
                row
                for row in nested_candles
                if (
                    isinstance(row, list)
                    and len(row) >= 6
                )
            ]

    return []


def fetch_daily_close_prices(
    symbol: str = FYERS_SYMBOL,
    lookback_days: int = HISTORICAL_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """
    Fetch daily historical BANKNIFTY candles from FYERS.

    FYERS candle format:
        epoch, open, high, low, close, volume
    """

    if lookback_days < 30:
        raise ValueError(
            "lookback_days must be at least 30."
        )

    fyers = create_fyers_client()

    range_to = date.today()

    range_from = (
        range_to
        - timedelta(
            days=lookback_days,
        )
    )

    payload = {
        "symbol": symbol,
        "resolution": "D",
        "date_format": "1",
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "cont_flag": "1",
    }

    response = fyers.history(
        data=payload
    )

    validated_response = ensure_success_response(
        response=response,
        operation="FYERS Historical Data API",
    )

    candle_rows = extract_candles(
        validated_response
    )

    if not candle_rows:
        raise RuntimeError(
            "FYERS returned no daily historical candles "
            f"for {symbol}."
        )

    dataframe = pd.DataFrame(
        candle_rows,
        columns=[
            "epoch",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    numeric_columns = [
        "epoch",
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
            "epoch",
            "close",
        ]
    )

    dataframe = dataframe[
        dataframe["close"] > 0
    ].copy()

    dataframe["datetime"] = pd.to_datetime(
        dataframe["epoch"],
        unit="s",
        utc=True,
    ).dt.tz_convert(
        "Asia/Kolkata"
    )

    dataframe["datetime"] = (
        dataframe["datetime"]
        .dt.tz_localize(None)
    )

    dataframe = dataframe.sort_values(
        "datetime"
    ).reset_index(
        drop=True
    )

    if dataframe.empty:
        raise RuntimeError(
            "No valid closing prices were obtained "
            "from the FYERS historical response."
        )

    return dataframe


# ============================================================
# IV HISTORY
# ============================================================

def read_iv_history() -> pd.Series:
    """
    Read saved historical ATM-IV observations.
    """

    if not IV_HISTORY_FILE.exists():
        return pd.Series(
            dtype="float64",
            name="atm_iv",
        )

    try:
        history = pd.read_csv(
            IV_HISTORY_FILE
        )

    except (
        OSError,
        ValueError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ):
        return pd.Series(
            dtype="float64",
            name="atm_iv",
        )

    if (
        history.empty
        or "atm_iv" not in history.columns
    ):
        return pd.Series(
            dtype="float64",
            name="atm_iv",
        )

    values = pd.to_numeric(
        history["atm_iv"],
        errors="coerce",
    ).dropna()

    values = values[
        values > 0
    ]

    return values.reset_index(
        drop=True
    ).rename(
        "atm_iv"
    )


def append_iv_history(
    timestamp: str,
    spot_price: float,
    atm_strike: float,
    atm_iv: float | None,
) -> None:
    """
    Save the current ATM IV for future IV Rank and IV Percentile.
    """

    normalized_iv = normalize_iv_value(
        atm_iv
    )

    if normalized_iv is None:
        return

    new_row = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "atm_iv": normalized_iv,
            }
        ]
    )

    if IV_HISTORY_FILE.exists():
        try:
            existing = pd.read_csv(
                IV_HISTORY_FILE
            )

        except (
            OSError,
            ValueError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
        ):
            existing = pd.DataFrame()

        combined = pd.concat(
            [
                existing,
                new_row,
            ],
            ignore_index=True,
            sort=False,
        )

    else:
        combined = new_row

    combined = combined.drop_duplicates(
        subset=[
            "timestamp",
            "atm_strike",
            "atm_iv",
        ],
        keep="last",
    )

    combined.to_csv(
        IV_HISTORY_FILE,
        index=False,
    )


# ============================================================
# LIVE VOLATILITY RUNNER
# ============================================================

def run_live_volatility() -> None:
    """
    Fetch live and historical data and run Volatility analytics.
    """

    print()
    print("=" * 76)
    print(
        "AQSD — LIVE BANKNIFTY VOLATILITY INTELLIGENCE"
    )
    print("=" * 76)

    print(
        "Fetching live FYERS option-chain data..."
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

    print(
        "Fetching BANKNIFTY daily historical candles..."
    )

    price_history = fetch_daily_close_prices(
        symbol=FYERS_SYMBOL,
        lookback_days=HISTORICAL_LOOKBACK_DAYS,
    )

    close_prices = price_history[
        "close"
    ]

    historical_iv = read_iv_history()

    print()

    print(
        f"Spot Price          : "
        f"{live_result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike          : "
        f"{option_chain_data.atm_strike:,.2f}"
    )

    print(
        f"Option Rows         : "
        f"{len(live_result.raw_dataframe)}"
    )

    print(
        f"Historical Candles  : "
        f"{len(price_history)}"
    )

    print(
        f"Saved IV Readings   : "
        f"{len(historical_iv)}"
    )

    live_iv_count = int(
        pd.to_numeric(
            live_result.raw_dataframe.get(
                "IV",
                pd.Series(
                    dtype="float64"
                ),
            ),
            errors="coerce",
        ).notna().sum()
    )

    print(
        f"Live IV Contracts   : "
        f"{live_iv_count}"
    )

    print()

    result, strike_iv_table = (
        analyze_volatility(
            option_chain_data=option_chain_data,
            close_prices=close_prices,
            historical_iv=historical_iv,
            hv_lookback_days=HV_LOOKBACK_DAYS,
            expected_move_days=EXPECTED_MOVE_DAYS,
        )
    )

    print_volatility_summary(
        result
    )

    append_iv_history(
        timestamp=result.timestamp,
        spot_price=result.spot_price,
        atm_strike=result.atm_strike,
        atm_iv=result.atm_iv,
    )

    print("Strike-wise IV Table")
    print("-" * 76)

    display_columns = [
        "strike",
        "call_iv",
        "put_iv",
        "average_iv",
        "put_call_iv_skew",
        "distance_from_spot",
        "is_atm",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in strike_iv_table.columns
    ]

    print(
        strike_iv_table[
            available_columns
        ].to_string(
            index=False
        )
    )

    print()

    metadata = ExportMetadata(
        engine="VOLATILITY",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            live_result.raw_dataframe
        ),
        status="SUCCESS",
        source=(
            "FYERS Live Option Chain and "
            "FYERS Historical Data"
        ),
        notes=(
            "Live BANKNIFTY Volatility Intelligence. "
            "IV-dependent values remain unavailable when "
            "FYERS does not supply implied volatility."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "atm_strike": result.atm_strike,
        "atm_iv": result.atm_iv,
        "atm_call_iv": result.atm_call_iv,
        "atm_put_iv": result.atm_put_iv,
        "average_chain_iv": (
            result.average_chain_iv
        ),
        "historical_volatility": (
            result.historical_volatility
        ),
        "iv_rank": result.iv_rank,
        "iv_percentile": (
            result.iv_percentile
        ),
        "iv_hv_spread": (
            result.iv_hv_spread
        ),
        "iv_hv_ratio": result.iv_hv_ratio,
        "put_call_iv_skew": (
            result.put_call_iv_skew
        ),
        "expected_move_points": (
            result.expected_move_points
        ),
        "expected_move_percent": (
            result.expected_move_percent
        ),
        "expected_move_low": (
            result.expected_move_low
        ),
        "expected_move_high": (
            result.expected_move_high
        ),
        "volatility_trend": (
            result.volatility_trend
        ),
        "volatility_regime": (
            result.volatility_regime
        ),
        "volatility_signal": (
            result.volatility_signal
        ),
        "skew_signal": result.skew_signal,
        "valid_iv_contracts": (
            result.valid_iv_contracts
        ),
    }

    engine_result = EngineResult(
        summary=result,
        table=strike_iv_table,
        history=history_row,
        metadata=metadata,
        extra_tables={
            "Price History": price_history,
        },
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": (
                live_result.spot_price
            ),
            "volatility": {
                "atm_iv": result.atm_iv,
                "atm_call_iv": (
                    result.atm_call_iv
                ),
                "atm_put_iv": (
                    result.atm_put_iv
                ),
                "average_chain_iv": (
                    result.average_chain_iv
                ),
                "historical_volatility": (
                    result.historical_volatility
                ),
                "iv_rank": result.iv_rank,
                "iv_percentile": (
                    result.iv_percentile
                ),
                "iv_hv_spread": (
                    result.iv_hv_spread
                ),
                "iv_hv_ratio": (
                    result.iv_hv_ratio
                ),
                "put_call_iv_skew": (
                    result.put_call_iv_skew
                ),
                "skew_signal": (
                    result.skew_signal
                ),
                "expected_move_points": (
                    result.expected_move_points
                ),
                "expected_move_percent": (
                    result.expected_move_percent
                ),
                "expected_move_low": (
                    result.expected_move_low
                ),
                "expected_move_high": (
                    result.expected_move_high
                ),
                "volatility_trend": (
                    result.volatility_trend
                ),
                "volatility_regime": (
                    result.volatility_regime
                ),
                "volatility_signal": (
                    result.volatility_signal
                ),
                "valid_iv_contracts": (
                    result.valid_iv_contracts
                ),
                "interpretation": (
                    result.interpretation
                ),
            },
            "strike_iv_table": (
                strike_iv_table.to_dict(
                    orient="records"
                )
            ),
            "price_history": (
                price_history.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_VOLATILITY_INTELLIGENCE"
        ),
    )

    print_export_report(
        export_paths
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Run live Volatility analytics with clear error reporting.
    """

    try:
        run_live_volatility()

    except Exception as error:
        print()
        print("=" * 76)
        print(
            "AQSD LIVE VOLATILITY ENGINE — FAILED"
        )
        print("=" * 76)

        print(
            f"Error Type : "
            f"{type(error).__name__}"
        )

        print(
            f"Message    : "
            f"{error}"
        )

        print()
        print(
            "Check the FYERS access token, internet connection, "
            "historical-data response and option-chain response."
        )

        print("=" * 76)
        print()

        raise


if __name__ == "__main__":
    main()