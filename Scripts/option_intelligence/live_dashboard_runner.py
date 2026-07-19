"""
AQSD
Option Intelligence

Module: live_dashboard_runner.py
Version: 1.0
Author: AQSD

Description:
Runs the complete live BANKNIFTY Option Intelligence workflow
using FYERS market data.

Integrated engines:
- Open Interest
- PCR
- Max Pain
- Option Walls
- Volatility
- Probability
- Option Dashboard

Important:
- FYERS data is fetched once per dashboard run.
- All engines use the same option-chain snapshot.
- This module performs analytics only.
- It does not place orders.
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

from Scripts.option_intelligence.option_dashboard import (
    build_dashboard_result,
    create_dashboard_detail_table,
    print_dashboard,
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
# LIVE DASHBOARD WORKFLOW
# ============================================================

def run_live_dashboard() -> None:
    """
    Run the complete live AQSD Option Intelligence Dashboard.
    """

    print()
    print("=" * 108)
    print(
        "AQSD — LIVE BANKNIFTY OPTION INTELLIGENCE DASHBOARD"
        .center(108)
    )
    print("=" * 108)
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

    # --------------------------------------------------------
    # FETCH HISTORICAL PRICES
    # --------------------------------------------------------

    print(
        "2/8  Fetching BANKNIFTY historical candles..."
    )

    try:
        price_history = fetch_daily_close_prices(
            symbol=FYERS_SYMBOL,
            lookback_days=(
                HISTORICAL_LOOKBACK_DAYS
            ),
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
        f"{live_result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike           : "
        f"{option_chain_data.atm_strike:,.2f}"
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
        f"Number of Strikes    : "
        f"{option_chain_data.number_of_strikes}"
    )

    print(
        f"Historical Candles   : "
        f"{len(price_history)}"
    )

    print(
        f"Saved IV Readings    : "
        f"{len(historical_iv)}"
    )

    print()

    # --------------------------------------------------------
    # OPEN INTEREST
    # --------------------------------------------------------

    print(
        "3/8  Running Open Interest Engine..."
    )

    oi_result, oi_table = (
        analyze_open_interest(
            live_dataframe
        )
    )

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    print(
        "4/8  Running PCR Engine..."
    )

    pcr_result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=(
            ATM_WINDOW_STRIKES_EACH_SIDE
        ),
    )

    # --------------------------------------------------------
    # MAX PAIN
    # --------------------------------------------------------

    print(
        "5/8  Running Max Pain Engine..."
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
    # WALLS
    # --------------------------------------------------------

    print(
        "6/8  Running Wall Engine..."
    )

    wall_result, wall_table = (
        analyze_walls(
            option_chain_data=option_chain_data,
            history_file=WALL_HISTORY_FILE,
        )
    )

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    print(
        "7/8  Running Volatility Engine..."
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
    # PROBABILITY
    # --------------------------------------------------------

    print(
        "8/8  Running Probability Engine..."
    )

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

    probability_result, evidence_table = (
        analyze_probability(
            inputs=probability_inputs,
            timestamp=(
                option_chain_data.timestamp
            ),
        )
    )

    # --------------------------------------------------------
    # BUILD DASHBOARD
    # --------------------------------------------------------

    dashboard_result = build_dashboard_result(
        underlying=UNDERLYING,
        option_chain_data=option_chain_data,
        oi=oi_result,
        pcr=pcr_result,
        max_pain=max_pain_result,
        walls=wall_result,
        volatility=volatility_result,
        probability=probability_result,
    )

    detail_table = create_dashboard_detail_table(
        oi_result=oi_result,
        pcr_result=pcr_result,
        max_pain_result=max_pain_result,
        wall_result=wall_result,
        volatility_result=volatility_result,
        probability_result=probability_result,
    )

    # --------------------------------------------------------
    # DISPLAY DASHBOARD
    # --------------------------------------------------------

    print_dashboard(
        dashboard_result
    )

    # --------------------------------------------------------
    # EXPORT METADATA
    # --------------------------------------------------------

    metadata = ExportMetadata(
        engine="DASHBOARD",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            live_dataframe
        ),
        status="SUCCESS",
        source=(
            "FYERS Live Option Chain and "
            "FYERS Historical Data"
        ),
        notes=(
            "Live BANKNIFTY integrated Option "
            "Intelligence Dashboard."
        ),
    )

    # --------------------------------------------------------
    # DASHBOARD HISTORY
    # --------------------------------------------------------

    history_row = {
        "timestamp": (
            dashboard_result.timestamp
        ),
        "underlying": (
            dashboard_result.underlying
        ),
        "spot_price": (
            dashboard_result.spot_price
        ),
        "atm_strike": (
            dashboard_result.atm_strike
        ),

        "suggested_action": (
            dashboard_result.suggested_action
        ),
        "directional_bias": (
            dashboard_result.directional_bias
        ),
        "confidence_score": (
            dashboard_result.confidence_score
        ),
        "trade_grade": (
            dashboard_result.trade_grade
        ),
        "trade_quality": (
            dashboard_result.trade_quality
        ),
        "market_regime": (
            dashboard_result.market_regime
        ),

        "bullish_probability": (
            dashboard_result
            .bullish_probability
        ),
        "bearish_probability": (
            dashboard_result
            .bearish_probability
        ),
        "continuation_probability": (
            dashboard_result
            .continuation_probability
        ),
        "reversal_probability": (
            dashboard_result
            .reversal_probability
        ),

        "oi_pcr": dashboard_result.oi_pcr,
        "change_oi_pcr": (
            dashboard_result.change_oi_pcr
        ),
        "modified_pcr": (
            dashboard_result.modified_pcr
        ),
        "atm_zone_pcr": (
            dashboard_result.atm_zone_pcr
        ),
        "pcr_trend": (
            dashboard_result.pcr_trend
        ),
        "pcr_bias": (
            dashboard_result.pcr_bias
        ),

        "max_pain_strike": (
            dashboard_result.max_pain_strike
        ),
        "pinning_probability": (
            dashboard_result
            .pinning_probability
        ),
        "expiry_bias": (
            dashboard_result.expiry_bias
        ),

        "positional_call_wall": (
            dashboard_result
            .positional_call_wall
        ),
        "positional_put_wall": (
            dashboard_result
            .positional_put_wall
        ),
        "fresh_call_wall": (
            dashboard_result.fresh_call_wall
        ),
        "fresh_put_wall": (
            dashboard_result.fresh_put_wall
        ),
        "combined_wall_shift": (
            dashboard_result
            .combined_wall_shift
        ),

        "atm_iv": dashboard_result.atm_iv,
        "historical_volatility": (
            dashboard_result
            .historical_volatility
        ),
        "iv_rank": (
            dashboard_result.iv_rank
        ),
        "iv_percentile": (
            dashboard_result.iv_percentile
        ),
        "volatility_regime": (
            dashboard_result
            .volatility_regime
        ),
    }

    # --------------------------------------------------------
    # EXPORT OBJECT
    # --------------------------------------------------------

    extra_tables: dict[
        str,
        pd.DataFrame,
    ] = {
        "Probability Evidence": (
            evidence_table
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
        summary=dashboard_result,
        table=detail_table,
        history=history_row,
        metadata=metadata,
        extra_tables=extra_tables,
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": (
                live_result.spot_price
            ),
            "atm_strike": (
                option_chain_data.atm_strike
            ),
            "strike_step": (
                option_chain_data.strike_step
            ),

            "final_decision": {
                "suggested_action": (
                    dashboard_result
                    .suggested_action
                ),
                "directional_bias": (
                    dashboard_result
                    .directional_bias
                ),
                "confidence_score": (
                    dashboard_result
                    .confidence_score
                ),
                "trade_grade": (
                    dashboard_result
                    .trade_grade
                ),
                "trade_quality": (
                    dashboard_result
                    .trade_quality
                ),
                "market_regime": (
                    dashboard_result
                    .market_regime
                ),
            },

            "probabilities": {
                "bullish": (
                    dashboard_result
                    .bullish_probability
                ),
                "bearish": (
                    dashboard_result
                    .bearish_probability
                ),
                "continuation": (
                    dashboard_result
                    .continuation_probability
                ),
                "reversal": (
                    dashboard_result
                    .reversal_probability
                ),
            },

            "open_interest": {
                "oi_pcr": (
                    dashboard_result.oi_pcr
                ),
                "change_oi_pcr": (
                    dashboard_result
                    .change_oi_pcr
                ),
                "market_bias": (
                    dashboard_result
                    .oi_market_bias
                ),
                "build_up_signal": (
                    dashboard_result
                    .oi_build_up_signal
                ),
            },

            "pcr": {
                "modified_pcr": (
                    dashboard_result
                    .modified_pcr
                ),
                "atm_zone_pcr": (
                    dashboard_result
                    .atm_zone_pcr
                ),
                "volume_pcr": (
                    dashboard_result.volume_pcr
                ),
                "trend": (
                    dashboard_result.pcr_trend
                ),
                "bias": (
                    dashboard_result.pcr_bias
                ),
                "reversal_watch": (
                    dashboard_result
                    .reversal_watch
                ),
            },

            "max_pain": {
                "max_pain_strike": (
                    dashboard_result
                    .max_pain_strike
                ),
                "pinning_probability": (
                    dashboard_result
                    .pinning_probability
                ),
                "magnet_strength": (
                    dashboard_result
                    .magnet_strength
                ),
                "expiry_bias": (
                    dashboard_result
                    .expiry_bias
                ),
                "pain_shift": (
                    dashboard_result.pain_shift
                ),
            },

            "walls": {
                "positional_call_wall": (
                    dashboard_result
                    .positional_call_wall
                ),
                "positional_put_wall": (
                    dashboard_result
                    .positional_put_wall
                ),
                "fresh_call_wall": (
                    dashboard_result
                    .fresh_call_wall
                ),
                "fresh_put_wall": (
                    dashboard_result
                    .fresh_put_wall
                ),
                "expected_range_low": (
                    dashboard_result
                    .expected_range_low
                ),
                "expected_range_high": (
                    dashboard_result
                    .expected_range_high
                ),
                "combined_wall_shift": (
                    dashboard_result
                    .combined_wall_shift
                ),
                "breakout_watch": (
                    dashboard_result
                    .breakout_watch
                ),
                "breakdown_watch": (
                    dashboard_result
                    .breakdown_watch
                ),
            },

            "volatility": {
                "atm_iv": (
                    dashboard_result.atm_iv
                ),
                "historical_volatility": (
                    dashboard_result
                    .historical_volatility
                ),
                "iv_rank": (
                    dashboard_result.iv_rank
                ),
                "iv_percentile": (
                    dashboard_result
                    .iv_percentile
                ),
                "iv_hv_spread": (
                    dashboard_result
                    .iv_hv_spread
                ),
                "volatility_trend": (
                    dashboard_result
                    .volatility_trend
                ),
                "volatility_regime": (
                    dashboard_result
                    .volatility_regime
                ),
                "volatility_signal": (
                    dashboard_result
                    .volatility_signal
                ),
                "skew_signal": (
                    dashboard_result.skew_signal
                ),
                "expected_move_low": (
                    dashboard_result
                    .expected_move_low
                ),
                "expected_move_high": (
                    dashboard_result
                    .expected_move_high
                ),
            },

            "interpretation": (
                dashboard_result.interpretation
            ),

            "probability_evidence": (
                evidence_table.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_OPTION_DASHBOARD"
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
    Run the live Dashboard with clear error reporting.
    """

    try:
        run_live_dashboard()

    except Exception as error:
        print()
        print("=" * 108)
        print(
            "AQSD LIVE OPTION DASHBOARD — FAILED"
        )
        print("=" * 108)

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
            "connection, option-chain response and "
            "historical-data response."
        )

        print("=" * 108)
        print()

        raise


if __name__ == "__main__":
    main()