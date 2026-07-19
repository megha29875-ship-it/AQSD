"""
AQSD
Option Intelligence

Module: live_decision_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches one live BANKNIFTY option-chain snapshot from FYERS,
runs all supporting Option Intelligence engines, and produces
the final AQSD live decision.

Integrated engines:
- Open Interest
- PCR
- Max Pain
- Option Walls
- Volatility
- Probability
- Decision Engine

Important:
- This module performs analytics only.
- It does not place orders.
- Entry, stop and target values refer to the BANKNIFTY
  underlying, not the option premium.
"""

from __future__ import annotations

import os
import json

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

from pathlib import Path

import pandas as pd

from Scripts.option_intelligence.decision_engine import (
    DecisionInputs,
    analyze_decision,
    print_decision_summary,
)

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
)

from Scripts.option_intelligence.live_probability_runner import (
    build_live_probability_inputs,
)

from Scripts.option_intelligence.live_volatility_runner import (
    fetch_daily_close_prices,
    read_iv_history,
)

from Scripts.option_intelligence.max_pain_engine import (
    analyze_max_pain,
)

from Scripts.option_intelligence.oi_engine import (
    analyze_open_interest,
)

from Scripts.option_intelligence.pcr_engine import (
    analyze_pcr,
)

from Scripts.option_intelligence.probability_engine import (
    analyze_probability,
)

from Scripts.option_intelligence.volatility_engine import (
    analyze_volatility,
)

from Scripts.option_intelligence.wall_engine import (
    analyze_walls,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"

STRIKE_COUNT = 15
ATM_WINDOW_STRIKES_EACH_SIDE = 3

HISTORICAL_LOOKBACK_DAYS = 120
HV_LOOKBACK_DAYS = 20
EXPECTED_MOVE_DAYS = 7

MAX_PAIN_HISTORY_FILE = (
    BASE_DIR
    / "Output"
    / "MaxPain"
    / "BANKNIFTY_LIVE_MAXPAIN_INTELLIGENCE_History.csv"
)

WALL_HISTORY_FILE = (
    BASE_DIR
    / "Output"
    / "Walls"
    / "BANKNIFTY_LIVE_WALL_INTELLIGENCE_History.csv"
)


# ============================================================
# DECISION INPUT BUILDER
# ============================================================

def fetch_banknifty_spot_from_fyers() -> float:
    """
    Fetch the actual BANKNIFTY index LTP directly from FYERS.
    """

    load_dotenv()

    client_id = (
        os.getenv("FYERS_CLIENT_ID")
        or os.getenv("FYERS_APP_ID")
        or os.getenv("CLIENT_ID")
    )

    access_token = (
        os.getenv("FYERS_ACCESS_TOKEN")
        or os.getenv("ACCESS_TOKEN")
    )

    if not client_id:
        raise RuntimeError(
            "FYERS client ID was not found in the .env file."
        )

    if not access_token:
        raise RuntimeError(
            "FYERS access token was not found in the .env file."
        )

    fyers = fyersModel.FyersModel(
        client_id=client_id,
        token=access_token,
        is_async=False,
        log_path="",
    )

    response = fyers.quotes(
        {
            "symbols": "NSE:NIFTYBANK-INDEX",
        }
    )

    if not isinstance(response, dict):
        raise RuntimeError(
            "Invalid FYERS quote response for BANKNIFTY."
        )

    quote_rows = response.get(
        "d",
        []
    )

    if not quote_rows:
        raise RuntimeError(
            f"FYERS returned no BANKNIFTY quote: {response}"
        )

    quote_values = quote_rows[0].get(
        "v",
        {}
    )

    spot_price = (
        quote_values.get("lp")
        or quote_values.get("ltp")
        or quote_values.get("last_price")
    )

    try:
        spot_price = float(
            spot_price
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            f"Invalid BANKNIFTY spot price in FYERS response: "
            f"{response}"
        ) from error

    if spot_price <= 1000.0:
        raise RuntimeError(
            f"FYERS returned an invalid BANKNIFTY spot price: "
            f"{spot_price}"
        )

    return spot_price

def resolve_banknifty_spot_price(
    live_result: object,
    option_chain_data: object,
) -> float:
    """
    Return the actual BANKNIFTY underlying price.

    ATM strike is used only to validate candidates.
    It is never returned as the spot price.
    """

    atm_strike = float(
        getattr(
            option_chain_data,
            "atm_strike",
            0.0,
        )
        or 0.0
    )

    possible_values = [
        getattr(
            live_result,
            "spot_price",
            None,
        ),
        getattr(
            live_result,
            "underlying_price",
            None,
        ),
        getattr(
            live_result,
            "index_price",
            None,
        ),
        getattr(
            option_chain_data,
            "spot_price",
            None,
        ),
        getattr(
            option_chain_data,
            "underlying_price",
            None,
        ),
        getattr(
            option_chain_data,
            "index_price",
            None,
        ),
    ]

    valid_candidates: list[float] = []

    for value in possible_values:
        try:
            number = float(value)

        except (
            TypeError,
            ValueError,
        ):
            continue

        if number <= 1000.0:
            continue

        if (
            atm_strike > 1000.0
            and abs(number - atm_strike) > 2000.0
        ):
            continue

        valid_candidates.append(
            number
        )

    if not valid_candidates:
        raise RuntimeError(
            "Actual BANKNIFTY spot price was not available. "
            "ATM strike will not be used as a substitute."
        )

    if atm_strike > 1000.0:
        return min(
            valid_candidates,
            key=lambda number: abs(
                number - atm_strike
            ),
        )

    return valid_candidates[0]

def build_live_decision_inputs(
    spot_price: float,
    atm_strike: float,
    strike_step: float,
    timestamp: str,
    probability_result: object,
    pcr_result: object,
    max_pain_result: object,
    wall_result: object,
    volatility_result: object,
) -> DecisionInputs:
    """
    Convert live analytics into DecisionInputs.
    """

    return DecisionInputs(
        underlying=UNDERLYING,
        spot_price=spot_price,
        atm_strike=atm_strike,
        strike_step=strike_step,
        timestamp=timestamp,

        bullish_probability=float(
            getattr(
                probability_result,
                "bullish_probability",
                50.0,
            )
        ),

        bearish_probability=float(
            getattr(
                probability_result,
                "bearish_probability",
                50.0,
            )
        ),

        continuation_probability=float(
            getattr(
                probability_result,
                "continuation_probability",
                50.0,
            )
        ),

        reversal_probability=float(
            getattr(
                probability_result,
                "reversal_probability",
                50.0,
            )
        ),

        confidence_score=float(
            getattr(
                probability_result,
                "confidence_score",
                0.0,
            )
        ),

        directional_edge=float(
            getattr(
                probability_result,
                "directional_edge",
                0.0,
            )
        ),

        directional_bias=str(
            getattr(
                probability_result,
                "directional_bias",
                "NEUTRAL",
            )
        ),

        market_regime=str(
            getattr(
                probability_result,
                "market_regime",
                "MIXED / RANGE-BOUND",
            )
        ),

        probability_action=str(
            getattr(
                probability_result,
                "suggested_action",
                "WAIT",
            )
        ),

        probability_grade=str(
            getattr(
                probability_result,
                "trade_grade",
                "D",
            )
        ),

        modified_pcr=getattr(
            pcr_result,
            "modified_pcr",
            None,
        ),

        pcr_trend=str(
            getattr(
                pcr_result,
                "pcr_trend",
                "NO DATA",
            )
        ),

        pcr_bias=str(
            getattr(
                pcr_result,
                "pcr_bias",
                "NEUTRAL",
            )
        ),

        reversal_watch=str(
            getattr(
                pcr_result,
                "reversal_watch",
                "NO DATA",
            )
        ),

        positional_call_wall=getattr(
            wall_result,
            "positional_call_wall",
            None,
        ),

        positional_put_wall=getattr(
            wall_result,
            "positional_put_wall",
            None,
        ),

        fresh_call_wall=getattr(
            wall_result,
            "fresh_call_wall",
            None,
        ),

        fresh_put_wall=getattr(
            wall_result,
            "fresh_put_wall",
            None,
        ),

        combined_wall_shift=str(
            getattr(
                wall_result,
                "combined_wall_shift",
                "NO DATA",
            )
        ),

        breakout_watch=str(
            getattr(
                wall_result,
                "breakout_watch",
                "NO DATA",
            )
        ),

        breakdown_watch=str(
            getattr(
                wall_result,
                "breakdown_watch",
                "NO DATA",
            )
        ),

        max_pain_strike=getattr(
            max_pain_result,
            "max_pain_strike",
            None,
        ),

        pinning_probability=getattr(
            max_pain_result,
            "pinning_probability",
            None,
        ),

        expiry_bias=str(
            getattr(
                max_pain_result,
                "expiry_bias",
                "NEUTRAL",
            )
        ),

        magnet_strength=str(
            getattr(
                max_pain_result,
                "magnet_strength",
                "NO DATA",
            )
        ),

        atm_iv=getattr(
            volatility_result,
            "atm_iv",
            None,
        ),

        historical_volatility=getattr(
            volatility_result,
            "historical_volatility",
            None,
        ),

        iv_rank=getattr(
            volatility_result,
            "iv_rank",
            None,
        ),

        iv_percentile=getattr(
            volatility_result,
            "iv_percentile",
            None,
        ),

        volatility_trend=str(
            getattr(
                volatility_result,
                "volatility_trend",
                "NO DATA",
            )
        ),

        volatility_regime=str(
            getattr(
                volatility_result,
                "volatility_regime",
                "INSUFFICIENT DATA",
            )
        ),

        volatility_signal=str(
            getattr(
                volatility_result,
                "volatility_signal",
                "INSUFFICIENT DATA",
            )
        ),

        skew_signal=str(
            getattr(
                volatility_result,
                "skew_signal",
                "NO SKEW DATA",
            )
        ),
    )


# ============================================================
# LIVE DECISION WORKFLOW
# ============================================================

def run_live_decision() -> None:
    """
    Run the complete live AQSD Decision Intelligence workflow.
    """

    print()
    print("=" * 88)
    print(
        "AQSD — LIVE BANKNIFTY OPTION DECISION ENGINE"
        .center(88)
    )
    print("=" * 88)
    print()

    # --------------------------------------------------------
    # FETCH LIVE OPTION CHAIN
    # --------------------------------------------------------

    print(
        "1/8  Fetching live FYERS option-chain data..."
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

    resolved_spot_price = (
        fetch_banknifty_spot_from_fyers()
    )

    correct_atm_strike = (
        round(
            resolved_spot_price
            / float(option_chain_data.strike_step)
        )
        * float(option_chain_data.strike_step)
    )

    # --------------------------------------------------------
    # FETCH HISTORICAL DATA
    # --------------------------------------------------------

    print(
        "2/8  Fetching BANKNIFTY historical candles..."
    )

    try:
        price_history = fetch_daily_close_prices(
            symbol=FYERS_SYMBOL,
            lookback_days=HISTORICAL_LOOKBACK_DAYS,
        )

        close_prices = price_history[
            "close"
        ]

    except Exception as error:
        print(
            f"Historical-data warning: {error}"
        )

        price_history = pd.DataFrame()

        close_prices = pd.Series(
            dtype="float64"
        )

    historical_iv = read_iv_history()

    print()
    print(
        f"Spot Price           : "
        f"{resolved_spot_price:,.2f}"
    )

    print(
        f"ATM Strike           : "
        f"{correct_atm_strike:,.2f}"
    )

    print(
        f"Strike Step          : "
        f"{option_chain_data.strike_step:,.2f}"
    )

    print(
        f"Option Rows          : "
        f"{len(live_dataframe)}"
    )

    print(
        f"Historical Candles   : "
        f"{len(price_history)}"
    )

    print()

    # --------------------------------------------------------
    # RUN SUPPORTING ENGINES
    # --------------------------------------------------------

    print(
        "3/8  Running Open Interest Engine..."
    )

    oi_result, oi_table = (
        analyze_open_interest(
            live_dataframe
        )
    )

    print(
        "4/8  Running PCR Engine..."
    )

    pcr_result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=(
            ATM_WINDOW_STRIKES_EACH_SIDE
        ),
    )

    print(
        "5/8  Running Max Pain Engine..."
    )

    max_pain_result, pain_table = (
        analyze_max_pain(
            option_chain_data=option_chain_data,
            history_file=MAX_PAIN_HISTORY_FILE,
        )
    )

    print(
        "6/8  Running Wall Engine..."
    )

    wall_result, wall_table = (
        analyze_walls(
            option_chain_data=option_chain_data,
            history_file=WALL_HISTORY_FILE,
        )
    )

    print(
        "7/8  Running Volatility Engine..."
    )

    volatility_result, strike_iv_table = (
        analyze_volatility(
            option_chain_data=option_chain_data,
            close_prices=close_prices,
            historical_iv=historical_iv,
            hv_lookback_days=HV_LOOKBACK_DAYS,
            expected_move_days=EXPECTED_MOVE_DAYS,
        )
    )

    # --------------------------------------------------------
    # RUN PROBABILITY ENGINE
    # --------------------------------------------------------

    probability_inputs = (
        build_live_probability_inputs(
            spot_price=resolved_spot_price,
            oi_result=oi_result,
            pcr_result=pcr_result,
            max_pain_result=max_pain_result,
            wall_result=wall_result,
            volatility_result=volatility_result,
        )
    )

    probability_result, probability_evidence = (
        analyze_probability(
            inputs=probability_inputs,
            timestamp=option_chain_data.timestamp,
        )
    )

    # --------------------------------------------------------
    # RUN DECISION ENGINE
    # --------------------------------------------------------

    print(
        "8/8  Running Decision Engine..."
    )

    decision_inputs = build_live_decision_inputs(
        spot_price=resolved_spot_price,
        atm_strike=correct_atm_strike,
        strike_step=option_chain_data.strike_step,
        timestamp=option_chain_data.timestamp,
        probability_result=probability_result,
        pcr_result=pcr_result,
        max_pain_result=max_pain_result,
        wall_result=wall_result,
        volatility_result=volatility_result,
    )

    decision_result, decision_evidence = (
        analyze_decision(
            decision_inputs
        )
    )

    print_decision_summary(
        decision_result
    )

    # --------------------------------------------------------
    # EXPORT METADATA
    # --------------------------------------------------------

    metadata = ExportMetadata(
        engine="DECISION",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            decision_evidence
        ),
        status="SUCCESS",
        source=(
            "FYERS Live Option Chain and "
            "FYERS Historical Data"
        ),
        notes=(
            "Live BANKNIFTY Decision Intelligence "
            "combining OI, PCR, Max Pain, Walls, "
            "Volatility and Probability."
        ),
    )

    history_row = {
        "timestamp": (
            decision_result.timestamp
        ),
        "underlying": (
            decision_result.underlying
        ),
        "spot_price": (
            decision_result.spot_price
        ),
        "atm_strike": (
            decision_result.atm_strike
        ),
        "final_decision": (
            decision_result.final_decision
        ),
        "decision_bias": (
            decision_result.decision_bias
        ),
        "confidence_score": (
            decision_result.confidence_score
        ),
        "trade_grade": (
            decision_result.trade_grade
        ),
        "trade_quality": (
            decision_result.trade_quality
        ),
        "market_regime": (
            decision_result.market_regime
        ),
        "risk_level": (
            decision_result.risk_level
        ),
        "entry_low": (
            decision_result.entry_low
        ),
        "entry_high": (
            decision_result.entry_high
        ),
        "stop_loss": (
            decision_result.stop_loss
        ),
        "target_one": (
            decision_result.target_one
        ),
        "target_two": (
            decision_result.target_two
        ),
        "risk_reward_one": (
            decision_result.risk_reward_one
        ),
        "risk_reward_two": (
            decision_result.risk_reward_two
        ),
        "bullish_probability": (
            decision_result.bullish_probability
        ),
        "bearish_probability": (
            decision_result.bearish_probability
        ),
        "continuation_probability": (
            decision_result
            .continuation_probability
        ),
        "reversal_probability": (
            decision_result.reversal_probability
        ),
    }

    extra_tables: dict[
        str,
        pd.DataFrame,
    ] = {
        "Probability Evidence": (
            probability_evidence
        ),
        "OI Table": oi_table,
        "Max Pain Table": pain_table,
        "Wall Table": wall_table,
        "Strike IV Table": (
            strike_iv_table
        ),
        "Live Option Chain": (
            live_dataframe
        ),
    }

    if not price_history.empty:
        extra_tables[
            "Price History"
        ] = price_history

    engine_result = EngineResult(
        summary=decision_result,
        table=decision_evidence,
        history=history_row,
        metadata=metadata,
        extra_tables=extra_tables,
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": (
                resolved_spot_price
            ),
            "atm_strike": (
                correct_atm_strike
            ),
            "strike_step": (
                option_chain_data.strike_step
            ),

            "decision": {
                "final_decision": (
                    decision_result.final_decision
                ),
                "decision_bias": (
                    decision_result.decision_bias
                ),
                "confidence_score": (
                    decision_result.confidence_score
                ),
                "trade_grade": (
                    decision_result.trade_grade
                ),
                "trade_quality": (
                    decision_result.trade_quality
                ),
                "risk_level": (
                    decision_result.risk_level
                ),
                "entry_low": (
                    decision_result.entry_low
                ),
                "entry_high": (
                    decision_result.entry_high
                ),
                "stop_loss": (
                    decision_result.stop_loss
                ),
                "target_one": (
                    decision_result.target_one
                ),
                "target_two": (
                    decision_result.target_two
                ),
                "risk_reward_one": (
                    decision_result.risk_reward_one
                ),
                "risk_reward_two": (
                    decision_result.risk_reward_two
                ),
                "supporting_reasons": (
                    decision_result.supporting_reasons
                ),
                "risk_warnings": (
                    decision_result.risk_warnings
                ),
                "interpretation": (
                    decision_result.interpretation
                ),
            },

            "probabilities": {
                "bullish": (
                    decision_result.bullish_probability
                ),
                "bearish": (
                    decision_result.bearish_probability
                ),
                "continuation": (
                    decision_result
                    .continuation_probability
                ),
                "reversal": (
                    decision_result.reversal_probability
                ),
            },

            "supporting_analytics": {
                "oi_pcr": getattr(
                    oi_result,
                    "oi_pcr",
                    None,
                ),
                "change_oi_pcr": getattr(
                    oi_result,
                    "change_oi_pcr",
                    None,
                ),
                "modified_pcr": getattr(
                    pcr_result,
                    "modified_pcr",
                    None,
                ),
                "pcr_trend": getattr(
                    pcr_result,
                    "pcr_trend",
                    None,
                ),
                "max_pain_strike": getattr(
                    max_pain_result,
                    "max_pain_strike",
                    None,
                ),
                "call_wall": getattr(
                    wall_result,
                    "positional_call_wall",
                    None,
                ),
                "put_wall": getattr(
                    wall_result,
                    "positional_put_wall",
                    None,
                ),
                "atm_iv": getattr(
                    volatility_result,
                    "atm_iv",
                    None,
                ),
                "historical_volatility": getattr(
                    volatility_result,
                    "historical_volatility",
                    None,
                ),
                "iv_rank": getattr(
                    volatility_result,
                    "iv_rank",
                    None,
                ),
            },

            "decision_evidence": (
                decision_evidence.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_DECISION_INTELLIGENCE"
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
    Run live Decision Intelligence with clear errors.
    """

    try:
        run_live_decision()

    except Exception as error:
        print()
        print("=" * 88)
        print(
            "AQSD LIVE DECISION ENGINE — FAILED"
        )
        print("=" * 88)

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
            "Check the FYERS access token, internet "
            "connection, option-chain data and "
            "historical-data response."
        )

        print("=" * 88)
        print()

        raise


if __name__ == "__main__":
    main()