"""
AQSD
Market Structure Engine

Module: test_engine.py
Version: 2.0
Author: AQSD

Description:
Downloads daily BANKNIFTY historical candles from FYERS
and tests the complete AQSD Market Structure Engine:

- EMA20, EMA50 and EMA200
- ATR-based EMA tolerance
- EMA slope analysis
- Trend direction and strength
- Swing High / Swing Low detection
- HH / HL / LH / LL classification
- Break of Structure (BOS)
- Change of Character (CHOCH)
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from .market_regime import (
    MarketRegimeResult,
    analyze_market_regime,
)

from .confidence import (
    ConfidenceResult,
    calculate_confidence,
)

from Scripts.aqsd_market_structure.detector import (
    BreakOfStructureResult,
    ChangeOfCharacterResult,
    detect_break_of_structure,
    detect_change_of_character,
)
from Scripts.aqsd_market_structure.models import SwingPoint
from Scripts.aqsd_market_structure.swings import (
    detect_and_classify_swings,
    get_latest_swing,
    get_previous_swing,
)
from Scripts.aqsd_market_structure.trend import analyze_trend


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

SYMBOL = "NSE:NIFTYBANK-INDEX"
RESOLUTION = "1D"
LOOKBACK_DAYS = 365

SEPARATOR_WIDTH = 72


def print_main_separator() -> None:
    """Print the main terminal separator."""

    print("=" * SEPARATOR_WIDTH)


def print_section_separator() -> None:
    """Print a section separator."""

    print("-" * SEPARATOR_WIDTH)


def read_environment_value(*names: str) -> str:
    """
    Read the first available environment variable.

    Args:
        names: Possible environment-variable names.

    Returns:
        Environment-variable value.

    Raises:
        RuntimeError:
            If none of the requested variables exist.
    """

    for name in names:
        value = os.getenv(name)

        if value:
            return value.strip()

    accepted_names = ", ".join(names)

    raise RuntimeError(
        "Missing environment variable. "
        f"Expected one of: {accepted_names}"
    )


def create_fyers_client() -> fyersModel.FyersModel:
    """
    Create an authenticated FYERS API client.

    Returns:
        Authenticated FYERS client.
    """

    if not ENV_FILE.exists():
        raise FileNotFoundError(
            f".env file not found: {ENV_FILE}"
        )

    load_dotenv(
        dotenv_path=ENV_FILE,
        override=True,
    )

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
    Download and clean daily historical candles from FYERS.

    FYERS candle format:

        timestamp
        open
        high
        low
        close
        volume

    Args:
        fyers: Authenticated FYERS client.
        symbol: FYERS market symbol.

    Returns:
        OHLCV DataFrame indexed by Timestamp.
    """

    range_to = date.today() - timedelta(days=1)

    range_from = range_to - timedelta(
        days=LOOKBACK_DAYS
    )

    request_data = {
        "symbol": symbol,
        "resolution": RESOLUTION,
        "date_format": "1",
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "cont_flag": "0",
    }

    response = fyers.history(
        data=request_data
    )

    if not isinstance(response, dict):
        raise RuntimeError(
            "Unexpected FYERS response type: "
            f"{type(response)}"
        )

    if response.get("s") != "ok":
        message = response.get(
            "message",
            "Unknown FYERS history error",
        )

        code = response.get("code")

        raise RuntimeError(
            "FYERS history request failed. "
            f"Code: {code}; Message: {message}"
        )

    candles = response.get(
        "candles",
        [],
    )

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
        .drop_duplicates(
            subset=["Timestamp"]
        )
        .sort_values("Timestamp")
        .set_index("Timestamp")
    )

    if len(df) < 200:
        raise RuntimeError(
            f"Only {len(df)} valid candles were returned. "
            "At least 200 candles are required for EMA200."
        )

    return df


def format_optional_price(
    value: Optional[float],
) -> str:
    """Format an optional price value."""

    if value is None:
        return "Not applicable"

    return f"{value:,.2f}"


def format_optional_timestamp(
    value,
) -> str:
    """Format an optional datetime value."""

    if value is None:
        return "Not applicable"

    return value.strftime("%Y-%m-%d")


def format_swing_type(
    swing: Optional[SwingPoint],
) -> str:
    """Format a swing classification."""

    if swing is None:
        return "Not available"

    return swing.swing_type.value


def format_swing_price(
    swing: Optional[SwingPoint],
) -> str:
    """Format a swing price."""

    if swing is None:
        return "Not available"

    return f"{swing.price:,.2f}"


def format_swing_date(
    swing: Optional[SwingPoint],
) -> str:
    """Format a swing timestamp."""

    if swing is None:
        return "Not available"

    return swing.timestamp.strftime("%Y-%m-%d")


def print_market_data_summary(
    symbol: str,
    df: pd.DataFrame,
) -> None:
    """Print downloaded market-data information."""

    print_main_separator()
    print("AQSD MARKET STRUCTURE ENGINE — VERSION 2.0")
    print_main_separator()

    print(f"Symbol             : {symbol}")
    print(f"Resolution         : {RESOLUTION}")
    print(f"Candles            : {len(df)}")
    print(f"First candle       : {df.index[0]}")
    print(f"Last candle        : {df.index[-1]}")


def print_trend_analysis(
    trend_result,
) -> None:
    """Print trend analysis and evidence."""

    print_section_separator()
    print("TREND ANALYSIS")
    print_section_separator()

    print(
        f"Direction          : "
        f"{trend_result.direction.value}"
    )

    print(
        f"Strength           : "
        f"{trend_result.strength.value}"
    )

    print(
        f"Close              : "
        f"{trend_result.close:,.2f}"
    )

    print(
        f"EMA20              : "
        f"{trend_result.ema20:,.2f}"
    )

    print(
        f"EMA50              : "
        f"{trend_result.ema50:,.2f}"
    )

    print(
        f"EMA200             : "
        f"{trend_result.ema200:,.2f}"
    )

    print(
    f"Trend Score        : "
    f"{trend_result.trend_score:.2f} / 100"
    )

    print(
    f"Trend Rating       : "
    f"{trend_result.trend_rating}"
    )

    print(
    f"Directional Power  : "
    f"{trend_result.directional_strength:.2f}%"
    )

    print_section_separator()
    print("TREND SCORE BREAKDOWN")
    print_section_separator()

    for key, value in trend_result.score_breakdown.items():
        print(f"{key:<22}: {value:5.1f}")

    print_section_separator()
    print("TREND EVIDENCE")
    print_section_separator()

    for item in trend_result.evidence:
        print(f"[OK] {item}")


def print_swing_summary(
    swing_highs: List[SwingPoint],
    swing_lows: List[SwingPoint],
) -> None:
    """Print latest and previous swing structure."""

    latest_high = get_latest_swing(
        swing_highs
    )

    previous_high = get_previous_swing(
        swing_highs
    )

    latest_low = get_latest_swing(
        swing_lows
    )

    previous_low = get_previous_swing(
        swing_lows
    )

    print_section_separator()
    print("SWING STRUCTURE SUMMARY")
    print_section_separator()

    print(
        f"Swing highs found  : "
        f"{len(swing_highs)}"
    )

    print(
        f"Swing lows found   : "
        f"{len(swing_lows)}"
    )

    print()

    print(
        f"Latest high type   : "
        f"{format_swing_type(latest_high)}"
    )

    print(
        f"Latest high price  : "
        f"{format_swing_price(latest_high)}"
    )

    print(
        f"Latest high date   : "
        f"{format_swing_date(latest_high)}"
    )

    print()

    print(
        f"Previous high type : "
        f"{format_swing_type(previous_high)}"
    )

    print(
        f"Previous high      : "
        f"{format_swing_price(previous_high)}"
    )

    print(
        f"Previous high date : "
        f"{format_swing_date(previous_high)}"
    )

    print()

    print(
        f"Latest low type    : "
        f"{format_swing_type(latest_low)}"
    )

    print(
        f"Latest low price   : "
        f"{format_swing_price(latest_low)}"
    )

    print(
        f"Latest low date    : "
        f"{format_swing_date(latest_low)}"
    )

    print()

    print(
        f"Previous low type  : "
        f"{format_swing_type(previous_low)}"
    )

    print(
        f"Previous low       : "
        f"{format_swing_price(previous_low)}"
    )

    print(
        f"Previous low date  : "
        f"{format_swing_date(previous_low)}"
    )


def print_recent_swings(
    title: str,
    swings: List[SwingPoint],
    limit: int = 5,
) -> None:
    """Print recent classified swing points."""

    print(title)

    if not swings:
        print("  No swing points detected.")
        return

    for swing in swings[-limit:]:
        print(
            f"  {swing.timestamp.strftime('%Y-%m-%d')} | "
            f"{swing.swing_type.value:<12} | "
            f"{swing.price:,.2f}"
        )


def print_recent_swing_section(
    swing_highs: List[SwingPoint],
    swing_lows: List[SwingPoint],
) -> None:
    """Print recent swing highs and swing lows."""

    print_section_separator()
    print("RECENT CLASSIFIED SWINGS")
    print_section_separator()

    print_recent_swings(
        title="Recent Swing Highs:",
        swings=swing_highs,
        limit=5,
    )

    print()

    print_recent_swings(
        title="Recent Swing Lows:",
        swings=swing_lows,
        limit=5,
    )


def print_bos_analysis(
    bos_result: BreakOfStructureResult,
) -> None:
    """Print Break of Structure analysis."""

    print_section_separator()
    print("BREAK OF STRUCTURE — BOS")
    print_section_separator()

    print(
        f"BOS detected       : "
        f"{'YES' if bos_result.detected else 'NO'}"
    )

    print(
        f"BOS direction      : "
        f"{bos_result.direction.value}"
    )

    print(
        f"Latest close       : "
        f"{bos_result.close:,.2f}"
    )

    print(
        f"Broken level       : "
        f"{format_optional_price(bos_result.broken_level)}"
    )

    print(
        f"Break date         : "
        f"{format_optional_timestamp(bos_result.break_timestamp)}"
    )

    if bos_result.reference_swing is None:
        print(
            "Reference swing    : Not applicable"
        )

        print(
            "Reference date     : Not applicable"
        )

    else:
        print(
            f"Reference swing    : "
            f"{bos_result.reference_swing.swing_type.value}"
        )

        print(
            f"Reference date     : "
            f"{bos_result.reference_swing.timestamp.strftime('%Y-%m-%d')}"
        )

    print_section_separator()
    print("BOS EVIDENCE")
    print_section_separator()

    for item in bos_result.evidence:
        print(f"[OK] {item}")


def print_choch_analysis(
    choch_result: ChangeOfCharacterResult,
) -> None:
    """Print Change of Character analysis."""

    print_section_separator()
    print("CHANGE OF CHARACTER — CHOCH")
    print_section_separator()

    print(
        f"CHOCH detected     : "
        f"{'YES' if choch_result.detected else 'NO'}"
    )

    print(
        f"CHOCH direction    : "
        f"{choch_result.direction.value}"
    )

    print(
        f"Previous structure : "
        f"{choch_result.previous_structure}"
    )

    print(
        f"Latest close       : "
        f"{choch_result.close:,.2f}"
    )

    print(
        f"Broken level       : "
        f"{format_optional_price(choch_result.broken_level)}"
    )

    print(
        f"Break date         : "
        f"{format_optional_timestamp(choch_result.break_timestamp)}"
    )

    if choch_result.reference_swing is None:
        print(
            "Reference swing    : Not applicable"
        )

        print(
            "Reference date     : Not applicable"
        )

    else:
        print(
            f"Reference swing    : "
            f"{choch_result.reference_swing.swing_type.value}"
        )

        print(
            f"Reference date     : "
            f"{choch_result.reference_swing.timestamp.strftime('%Y-%m-%d')}"
        )

    print_section_separator()
    print("CHOCH EVIDENCE")
    print_section_separator()

    for item in choch_result.evidence:
        print(f"[OK] {item}")

def print_market_regime_analysis(
    regime_result: MarketRegimeResult,
) -> None:
    """
    Print AQSD Market Regime Engine.
    """

    print_section_separator()
    print("AQSD MARKET REGIME ENGINE")
    print_section_separator()

    print(
        f"Market Regime      : "
        f"{regime_result.market_regime}"
    )

    print(
        f"Regime Score       : "
        f"{regime_result.regime_score:.2f}/100"
    )

    print(
        f"Directional Bias   : "
        f"{regime_result.directional_bias}"
    )

    print(
        f"Regime Strength    : "
        f"{regime_result.regime_strength}"
    )

    print(
        f"Trend State        : "
        f"{regime_result.trend_state}"
    )

    print(
        f"Structure State    : "
        f"{regime_result.structure_state}"
    )

    print(
        f"Break State        : "
        f"{regime_result.break_state}"
    )

    print()

    print(
        f"Continuation Prob. : "
        f"{regime_result.continuation_probability:.2f}%"
    )

    print(
        f"Reversal Prob.     : "
        f"{regime_result.reversal_probability:.2f}%"
    )

    print(
        f"Range Probability  : "
        f"{regime_result.range_probability:.2f}%"
    )

    print()

    print(
        f"Strategy           : "
        f"{regime_result.strategy_environment}"
    )

    print(
        f"Risk               : "
        f"{regime_result.risk_state}"
    )

    print_section_separator()
    print("REGIME SCORE BREAKDOWN")
    print_section_separator()

    for key, value in regime_result.score_breakdown.items():

        print(
            f"{key:<25}"
            f"{value:>8.2f}"
        )

    print_section_separator()
    print("REGIME EVIDENCE")
    print_section_separator()

    for item in regime_result.evidence:

        print(
            f"[OK] {item}"
        )

def print_confidence_analysis(
    confidence_result: ConfidenceResult,
) -> None:
    """
    Print the complete AQSD Confidence Engine result.
    """

    print_section_separator()
    print("AQSD CONFIDENCE ENGINE")
    print_section_separator()

    print(
        f"Confidence Score   : "
        f"{confidence_result.confidence_score:.2f} / 100"
    )

    print(
        f"Directional Bias   : "
        f"{confidence_result.directional_bias}"
    )

    print(
        f"Directional Power  : "
        f"{confidence_result.directional_confidence:.2f}%"
    )

    print(
        f"Confidence Rating  : "
        f"{confidence_result.confidence_rating}"
    )

    print(
        f"Trade Quality      : "
        f"{confidence_result.trade_quality}"
    )

    print(
        f"Market State       : "
        f"{confidence_result.market_state}"
    )

    print(
        f"Structure Direction: "
        f"{confidence_result.structure_direction}"
    )

    print(
        f"Bullish Swings     : "
        f"{confidence_result.bullish_swing_percent:.2f}%"
    )

    print(
        f"Bearish Swings     : "
        f"{confidence_result.bearish_swing_percent:.2f}%"
    )

    print_section_separator()
    print("CONFIDENCE SCORE BREAKDOWN")
    print_section_separator()

    print(
        f"Trend Component    : "
        f"{confidence_result.trend_component:.2f} / 40"
    )

    print(
        f"Swing Component    : "
        f"{confidence_result.swing_component:.2f} / 25"
    )

    print(
        f"BOS Component      : "
        f"{confidence_result.bos_component:.2f} / 15"
    )

    print(
        f"CHOCH Component    : "
        f"{confidence_result.choch_component:.2f} / 10"
    )

    print(
        f"Alignment Component: "
        f"{confidence_result.alignment_component:.2f} / 10"
    )

    print_section_separator()
    print("CONFIDENCE EVIDENCE")
    print_section_separator()

    for item in confidence_result.evidence:
        print(f"[OK] {item}")

def print_engine_summary(
    trend_result,
    bos_result: BreakOfStructureResult,
    choch_result: ChangeOfCharacterResult,
) -> None:
    """Print compact final Market Structure summary."""

    print_section_separator()
    print("AQSD MARKET STRUCTURE SUMMARY")
    print_section_separator()

    print(
        f"Trend direction    : "
        f"{trend_result.direction.value}"
    )

    print(
        f"Trend strength     : "
        f"{trend_result.strength.value}"
    )

    print(
        f"BOS status         : "
        f"{bos_result.direction.value}"
    )

    print(
        f"CHOCH status       : "
        f"{choch_result.direction.value}"
    )

    if choch_result.detected:
        interpretation = (
            "POTENTIAL STRUCTURAL REVERSAL"
        )

    elif bos_result.detected:
        interpretation = (
            "STRUCTURAL BREAK CONFIRMED"
        )

    else:
        interpretation = (
            "NO NEW STRUCTURAL BREAK"
        )

    print(
        f"Interpretation     : "
        f"{interpretation}"
    )

    print_main_separator()

def run_engine_analysis(
    symbol: str,
    df: pd.DataFrame,
) -> None:
    """
    Run the complete AQSD Market Structure Engine.
    """

    trend_result = analyze_trend(
        df
    )

    swing_highs, swing_lows = (
        detect_and_classify_swings(
            df
        )
    )

    bos_result = detect_break_of_structure(
        df
    )

    choch_result = detect_change_of_character(
        df
    )

    confidence_result = calculate_confidence(
        trend_result=trend_result,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        bos_result=bos_result,
        choch_result=choch_result,
    )

    regime_result = analyze_market_regime(
        trend_result=trend_result,
        confidence_result=confidence_result,
        bos_result=bos_result,
        choch_result=choch_result,
    )

    print()

    print_market_data_summary(
        symbol=symbol,
        df=df,
    )

    print_trend_analysis(
        trend_result=trend_result,
    )

    print_swing_summary(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )

    print_recent_swing_section(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
    )

    print_bos_analysis(
        bos_result=bos_result,
    )

    print_choch_analysis(
        choch_result=choch_result,
    )

    print_confidence_analysis(
        confidence_result=confidence_result,
    )

    print_market_regime_analysis(
        regime_result=regime_result,
    )

    print_engine_summary(
        trend_result=trend_result,
        bos_result=bos_result,
        choch_result=choch_result,
    )


def main() -> None:
    """
    Execute the FYERS BANKNIFTY Market Structure test.
    """

    print()

    print(
        f"Connecting to FYERS for {SYMBOL}..."
    )

    fyers = create_fyers_client()

    print(
        "Downloading daily historical candles..."
    )

    market_data = download_fyers_history(
        fyers=fyers,
        symbol=SYMBOL,
    )

    run_engine_analysis(
        symbol=SYMBOL,
        df=market_data,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print()

        print_main_separator()
        print("AQSD MARKET STRUCTURE TEST FAILED")
        print_main_separator()

        print(
            f"{type(error).__name__}: {error}"
        )

        print_main_separator()

        raise SystemExit(1)