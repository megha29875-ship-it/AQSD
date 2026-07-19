"""
AQSD
Option Intelligence

Module: live_probability_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches live BANKNIFTY data from FYERS, runs all supporting
Option Intelligence engines, and generates normalized live
directional and market-regime probabilities.

Integrated engines:
- Open Interest
- PCR
- Max Pain
- Option Walls
- Volatility
- Probability

Important:
- Bullish Probability + Bearish Probability = 100%
- Continuation Probability + Reversal Probability = 100%
- This module does not place trades.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
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
    ProbabilityInputs,
    analyze_probability,
    print_probability_summary,
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
# PROBABILITY INPUT BUILDER
# ============================================================

def build_live_probability_inputs(
    spot_price: float,
    oi_result: object,
    pcr_result: object,
    max_pain_result: object,
    wall_result: object,
    volatility_result: object,
) -> ProbabilityInputs:
    """
    Convert live engine results into ProbabilityInputs.
    """

    return ProbabilityInputs(
        spot_price=spot_price,

        # Open Interest
        oi_pcr=getattr(
            oi_result,
            "oi_pcr",
            None,
        ),
        change_oi_pcr=getattr(
            oi_result,
            "change_oi_pcr",
            None,
        ),
        oi_imbalance=getattr(
            oi_result,
            "oi_imbalance",
            None,
        ),
        oi_market_bias=getattr(
            oi_result,
            "market_bias",
            None,
        ),
        oi_build_up_signal=getattr(
            oi_result,
            "build_up_signal",
            None,
        ),

        # PCR
        modified_pcr=getattr(
            pcr_result,
            "modified_pcr",
            None,
        ),
        atm_zone_pcr=getattr(
            pcr_result,
            "atm_zone_pcr",
            None,
        ),
        pcr_trend=getattr(
            pcr_result,
            "pcr_trend",
            None,
        ),
        pcr_bias=getattr(
            pcr_result,
            "pcr_bias",
            None,
        ),
        reversal_watch=getattr(
            pcr_result,
            "reversal_watch",
            None,
        ),

        # Max Pain
        max_pain_strike=getattr(
            max_pain_result,
            "max_pain_strike",
            None,
        ),
        expiry_bias=getattr(
            max_pain_result,
            "expiry_bias",
            None,
        ),
        pinning_probability=getattr(
            max_pain_result,
            "pinning_probability",
            None,
        ),
        magnet_strength=getattr(
            max_pain_result,
            "magnet_strength",
            None,
        ),
        pain_shift=getattr(
            max_pain_result,
            "pain_shift",
            None,
        ),

        # Walls
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
        combined_wall_shift=getattr(
            wall_result,
            "combined_wall_shift",
            None,
        ),
        range_bias=getattr(
            wall_result,
            "range_bias",
            None,
        ),
        breakout_watch=getattr(
            wall_result,
            "breakout_watch",
            None,
        ),
        breakdown_watch=getattr(
            wall_result,
            "breakdown_watch",
            None,
        ),

        # Volatility
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
        iv_hv_spread=getattr(
            volatility_result,
            "iv_hv_spread",
            None,
        ),
        volatility_trend=getattr(
            volatility_result,
            "volatility_trend",
            None,
        ),
        volatility_regime=getattr(
            volatility_result,
            "volatility_regime",
            None,
        ),
        volatility_signal=getattr(
            volatility_result,
            "volatility_signal",
            None,
        ),
        skew_signal=getattr(
            volatility_result,
            "skew_signal",
            None,
        ),
    )


# ============================================================
# LIVE PROBABILITY RUNNER
# ============================================================

def run_live_probability() -> None:
    """
    Run the complete live AQSD Probability Intelligence workflow.
    """

    print()
    print("=" * 76)
    print(
        "AQSD — LIVE BANKNIFTY PROBABILITY INTELLIGENCE"
    )
    print("=" * 76)

    # --------------------------------------------------------
    # FETCH LIVE OPTION CHAIN
    # --------------------------------------------------------

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

    live_dataframe = (
        live_result.raw_dataframe
    )

    # --------------------------------------------------------
    # FETCH PRICE HISTORY
    # --------------------------------------------------------

    print(
        "Fetching BANKNIFTY historical candles..."
    )

    try:
        price_history = (
            fetch_daily_close_prices(
                symbol=FYERS_SYMBOL,
                lookback_days=(
                    HISTORICAL_LOOKBACK_DAYS
                ),
            )
        )

        close_prices = price_history[
            "close"
        ]

    except Exception as error:
        print(
            "Historical-price warning: "
            f"{error}"
        )

        price_history = pd.DataFrame()
        close_prices = pd.Series(
            dtype="float64"
        )

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
        f"{len(live_dataframe)}"
    )

    print(
        f"Number of Strikes   : "
        f"{option_chain_data.number_of_strikes}"
    )

    print(
        f"Historical Candles  : "
        f"{len(price_history)}"
    )

    print(
        f"Saved IV Readings   : "
        f"{len(historical_iv)}"
    )

    print()

    # --------------------------------------------------------
    # RUN OPEN INTEREST ENGINE
    # --------------------------------------------------------

    print(
        "Running Open Interest Engine..."
    )

    oi_result, oi_table = (
        analyze_open_interest(
            live_dataframe
        )
    )

    # --------------------------------------------------------
    # RUN PCR ENGINE
    # --------------------------------------------------------

    print(
        "Running PCR Engine..."
    )

    pcr_result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=(
            ATM_WINDOW_STRIKES_EACH_SIDE
        ),
    )

    # --------------------------------------------------------
    # RUN MAX PAIN ENGINE
    # --------------------------------------------------------

    print(
        "Running Max Pain Engine..."
    )

    max_pain_result, pain_table = (
        analyze_max_pain(
            option_chain_data=option_chain_data,
            history_file=(
                MAX_PAIN_HISTORY_FILE
            ),
        )
    )

    # --------------------------------------------------------
    # RUN WALL ENGINE
    # --------------------------------------------------------

    print(
        "Running Wall Engine..."
    )

    wall_result, wall_table = (
        analyze_walls(
            option_chain_data=option_chain_data,
            history_file=WALL_HISTORY_FILE,
        )
    )

    # --------------------------------------------------------
    # RUN VOLATILITY ENGINE
    # --------------------------------------------------------

    print(
        "Running Volatility Engine..."
    )

    volatility_result, strike_iv_table = (
        analyze_volatility(
            option_chain_data=option_chain_data,
            close_prices=close_prices,
            historical_iv=historical_iv,
            hv_lookback_days=(
                HV_LOOKBACK_DAYS
            ),
            expected_move_days=(
                EXPECTED_MOVE_DAYS
            ),
        )
    )

    # --------------------------------------------------------
    # BUILD PROBABILITY INPUTS
    # --------------------------------------------------------

    probability_inputs = (
        build_live_probability_inputs(
            spot_price=(
                live_result.spot_price
            ),
            oi_result=oi_result,
            pcr_result=pcr_result,
            max_pain_result=(
                max_pain_result
            ),
            wall_result=wall_result,
            volatility_result=(
                volatility_result
            ),
        )
    )

    # --------------------------------------------------------
    # RUN PROBABILITY ENGINE
    # --------------------------------------------------------

    print(
        "Running Probability Engine..."
    )

    probability_result, evidence_table = (
        analyze_probability(
            inputs=probability_inputs,
            timestamp=(
                option_chain_data.timestamp
            ),
        )
    )

    print_probability_summary(
        probability_result
    )

    # --------------------------------------------------------
    # DISPLAY EVIDENCE
    # --------------------------------------------------------

    print("Probability Evidence")
    print("-" * 76)

    display_columns = [
        "category",
        "indicator",
        "reading",
        "direction",
        "bullish_contribution",
        "bearish_contribution",
        "continuation_contribution",
        "reversal_contribution",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in evidence_table.columns
    ]

    print(
        evidence_table[
            available_columns
        ].to_string(
            index=False
        )
    )

    print()

    # --------------------------------------------------------
    # EXPORT METADATA
    # --------------------------------------------------------

    metadata = ExportMetadata(
        engine="PROBABILITY",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            evidence_table
        ),
        status="SUCCESS",
        source=(
            "FYERS Live Option Chain and "
            "FYERS Historical Data"
        ),
        notes=(
            "Live BANKNIFTY Probability "
            "Intelligence combining OI, PCR, "
            "Max Pain, Walls and Volatility."
        ),
    )

    # --------------------------------------------------------
    # HISTORY ROW
    # --------------------------------------------------------

    history_row = {
        "timestamp": (
            probability_result.timestamp
        ),
        "spot_price": (
            live_result.spot_price
        ),

        "bullish_probability": (
            probability_result
            .bullish_probability
        ),
        "bearish_probability": (
            probability_result
            .bearish_probability
        ),

        "continuation_probability": (
            probability_result
            .continuation_probability
        ),
        "reversal_probability": (
            probability_result
            .reversal_probability
        ),

        "institutional_bull_score": (
            probability_result
            .institutional_bull_score
        ),
        "institutional_bear_score": (
            probability_result
            .institutional_bear_score
        ),

        "directional_edge": (
            probability_result
            .directional_edge
        ),
        "confidence_score": (
            probability_result
            .confidence_score
        ),

        "directional_bias": (
            probability_result
            .directional_bias
        ),
        "market_regime": (
            probability_result
            .market_regime
        ),
        "suggested_action": (
            probability_result
            .suggested_action
        ),

        "trade_grade": (
            probability_result
            .trade_grade
        ),
        "trade_quality": (
            probability_result
            .trade_quality
        ),

        "oi_pcr": oi_result.oi_pcr,
        "modified_pcr": (
            pcr_result.modified_pcr
        ),
        "max_pain_strike": (
            max_pain_result
            .max_pain_strike
        ),
        "positional_call_wall": (
            wall_result
            .positional_call_wall
        ),
        "positional_put_wall": (
            wall_result
            .positional_put_wall
        ),
        "historical_volatility": (
            volatility_result
            .historical_volatility
        ),
        "atm_iv": (
            volatility_result.atm_iv
        ),
    }

    # --------------------------------------------------------
    # STANDARD EXPORT OBJECT
    # --------------------------------------------------------

    engine_result = EngineResult(
        summary=probability_result,
        table=evidence_table,
        history=history_row,
        metadata=metadata,
        extra_tables={
            "OI Table": oi_table,
            "Max Pain Table": pain_table,
            "Wall Table": wall_table,
            "Strike IV Table": (
                strike_iv_table
            ),
        },
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": (
                live_result.spot_price
            ),
            "atm_strike": (
                option_chain_data.atm_strike
            ),
            "probability": {
                "bullish_probability": (
                    probability_result
                    .bullish_probability
                ),
                "bearish_probability": (
                    probability_result
                    .bearish_probability
                ),
                "continuation_probability": (
                    probability_result
                    .continuation_probability
                ),
                "reversal_probability": (
                    probability_result
                    .reversal_probability
                ),
                "institutional_bull_score": (
                    probability_result
                    .institutional_bull_score
                ),
                "institutional_bear_score": (
                    probability_result
                    .institutional_bear_score
                ),
                "directional_edge": (
                    probability_result
                    .directional_edge
                ),
                "confidence_score": (
                    probability_result
                    .confidence_score
                ),
                "directional_bias": (
                    probability_result
                    .directional_bias
                ),
                "market_regime": (
                    probability_result
                    .market_regime
                ),
                "suggested_action": (
                    probability_result
                    .suggested_action
                ),
                "trade_grade": (
                    probability_result
                    .trade_grade
                ),
                "trade_quality": (
                    probability_result
                    .trade_quality
                ),
                "interpretation": (
                    probability_result
                    .interpretation
                ),
            },
            "engine_snapshots": {
                "oi": {
                    "oi_pcr": (
                        oi_result.oi_pcr
                    ),
                    "change_oi_pcr": (
                        oi_result.change_oi_pcr
                    ),
                    "market_bias": (
                        oi_result.market_bias
                    ),
                    "build_up_signal": (
                        oi_result.build_up_signal
                    ),
                },
                "pcr": {
                    "modified_pcr": (
                        pcr_result.modified_pcr
                    ),
                    "atm_zone_pcr": (
                        pcr_result.atm_zone_pcr
                    ),
                    "pcr_trend": (
                        pcr_result.pcr_trend
                    ),
                    "pcr_bias": (
                        pcr_result.pcr_bias
                    ),
                },
                "max_pain": {
                    "max_pain_strike": (
                        max_pain_result
                        .max_pain_strike
                    ),
                    "pinning_probability": (
                        max_pain_result
                        .pinning_probability
                    ),
                    "expiry_bias": (
                        max_pain_result
                        .expiry_bias
                    ),
                },
                "walls": {
                    "positional_call_wall": (
                        wall_result
                        .positional_call_wall
                    ),
                    "positional_put_wall": (
                        wall_result
                        .positional_put_wall
                    ),
                    "combined_wall_shift": (
                        wall_result
                        .combined_wall_shift
                    ),
                },
                "volatility": {
                    "atm_iv": (
                        volatility_result.atm_iv
                    ),
                    "historical_volatility": (
                        volatility_result
                        .historical_volatility
                    ),
                    "iv_rank": (
                        volatility_result.iv_rank
                    ),
                    "volatility_regime": (
                        volatility_result
                        .volatility_regime
                    ),
                },
            },
            "evidence": (
                evidence_table.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_PROBABILITY_INTELLIGENCE"
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
    Run the live Probability module with clear error reporting.
    """

    try:
        run_live_probability()

    except Exception as error:
        print()
        print("=" * 76)
        print(
            "AQSD LIVE PROBABILITY ENGINE — FAILED"
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
            "Check the FYERS access token, "
            "internet connection, live option-chain "
            "response and historical-data response."
        )

        print("=" * 76)
        print()

        raise


if __name__ == "__main__":
    main()