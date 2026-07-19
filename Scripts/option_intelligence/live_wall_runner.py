"""
AQSD
Option Intelligence

Module: live_wall_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain from FYERS and runs the
AQSD Wall Intelligence Engine.

Workflow:
FYERS Live Option Chain
        ↓
AQSD Option Chain Loader
        ↓
Wall Engine
        ↓
Shared Exporter
"""

from __future__ import annotations

from pathlib import Path

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
)

from Scripts.option_intelligence.wall_engine import (
    analyze_walls,
    print_wall_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"
STRIKE_COUNT = 15

LIVE_HISTORY_FILE = (
    BASE_DIR
    / "Output"
    / "Walls"
    / "BANKNIFTY_LIVE_WALL_INTELLIGENCE_History.csv"
)


# ============================================================
# LIVE WALL RUNNER
# ============================================================

def run_live_walls() -> None:
    """
    Fetch the live BANKNIFTY option chain and run Wall analytics.
    """

    print()
    print("=" * 76)
    print("AQSD — LIVE BANKNIFTY WALL INTELLIGENCE")
    print("=" * 76)
    print("Fetching live FYERS option-chain data...")
    print()

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
        f"Spot Price          : "
        f"{live_result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike          : "
        f"{option_chain_data.atm_strike:,.2f}"
    )

    print(
        f"Strike Step         : "
        f"{option_chain_data.strike_step:,.2f}"
    )

    print(
        f"Option Rows         : "
        f"{len(live_result.raw_dataframe)}"
    )

    print(
        f"Number of Strikes   : "
        f"{option_chain_data.number_of_strikes}"
    )

    print()

    result, wall_table = analyze_walls(
        option_chain_data=option_chain_data,
        history_file=LIVE_HISTORY_FILE,
    )

    print_wall_summary(
        result
    )

    print("Wall Table")
    print("-" * 76)

    display_columns = [
        "strike",
        "call_oi",
        "put_oi",
        "call_change_oi",
        "put_change_oi",
        "call_oi_share_percent",
        "put_oi_share_percent",
        "distance_from_spot",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in wall_table.columns
    ]

    print(
        wall_table[
            available_columns
        ].to_string(
            index=False
        )
    )

    print()

    metadata = ExportMetadata(
        engine="WALL",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            live_result.raw_dataframe
        ),
        status="SUCCESS",
        source="FYERS Live Option Chain",
        notes=(
            "Live BANKNIFTY Wall Intelligence "
            "using FYERS market data."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "atm_strike": result.atm_strike,
        "strike_step": result.strike_step,

        "positional_call_wall": (
            result.positional_call_wall
        ),
        "positional_call_wall_oi": (
            result.positional_call_wall_oi
        ),
        "secondary_call_wall": (
            result.secondary_call_wall
        ),
        "secondary_call_wall_oi": (
            result.secondary_call_wall_oi
        ),

        "positional_put_wall": (
            result.positional_put_wall
        ),
        "positional_put_wall_oi": (
            result.positional_put_wall_oi
        ),
        "secondary_put_wall": (
            result.secondary_put_wall
        ),
        "secondary_put_wall_oi": (
            result.secondary_put_wall_oi
        ),

        "fresh_call_wall": (
            result.fresh_call_wall
        ),
        "fresh_call_wall_change_oi": (
            result.fresh_call_wall_change_oi
        ),

        "fresh_put_wall": (
            result.fresh_put_wall
        ),
        "fresh_put_wall_change_oi": (
            result.fresh_put_wall_change_oi
        ),

        "expected_range_low": (
            result.expected_range_low
        ),
        "expected_range_high": (
            result.expected_range_high
        ),
        "expected_range_width": (
            result.expected_range_width
        ),

        "call_wall_strength": (
            result.call_wall_strength
        ),
        "put_wall_strength": (
            result.put_wall_strength
        ),

        "call_wall_shift": (
            result.call_wall_shift
        ),
        "put_wall_shift": (
            result.put_wall_shift
        ),
        "combined_wall_shift": (
            result.combined_wall_shift
        ),

        "range_bias": result.range_bias,
        "breakout_watch": (
            result.breakout_watch
        ),
        "breakdown_watch": (
            result.breakdown_watch
        ),
    }

    engine_result = EngineResult(
        summary=result,
        table=wall_table,
        history=history_row,
        metadata=metadata,
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": (
                live_result.spot_price
            ),
            "atm_strike": (
                option_chain_data.atm_strike
            ),
            "walls": {
                "positional_call_wall": (
                    result.positional_call_wall
                ),
                "positional_call_wall_oi": (
                    result.positional_call_wall_oi
                ),
                "secondary_call_wall": (
                    result.secondary_call_wall
                ),
                "secondary_call_wall_oi": (
                    result.secondary_call_wall_oi
                ),
                "positional_put_wall": (
                    result.positional_put_wall
                ),
                "positional_put_wall_oi": (
                    result.positional_put_wall_oi
                ),
                "secondary_put_wall": (
                    result.secondary_put_wall
                ),
                "secondary_put_wall_oi": (
                    result.secondary_put_wall_oi
                ),
                "fresh_call_wall": (
                    result.fresh_call_wall
                ),
                "fresh_call_wall_change_oi": (
                    result.fresh_call_wall_change_oi
                ),
                "fresh_put_wall": (
                    result.fresh_put_wall
                ),
                "fresh_put_wall_change_oi": (
                    result.fresh_put_wall_change_oi
                ),
                "expected_range_low": (
                    result.expected_range_low
                ),
                "expected_range_high": (
                    result.expected_range_high
                ),
                "expected_range_width": (
                    result.expected_range_width
                ),
                "call_wall_strength": (
                    result.call_wall_strength
                ),
                "put_wall_strength": (
                    result.put_wall_strength
                ),
                "call_wall_shift": (
                    result.call_wall_shift
                ),
                "put_wall_shift": (
                    result.put_wall_shift
                ),
                "combined_wall_shift": (
                    result.combined_wall_shift
                ),
                "range_bias": (
                    result.range_bias
                ),
                "breakout_watch": (
                    result.breakout_watch
                ),
                "breakdown_watch": (
                    result.breakdown_watch
                ),
                "interpretation": (
                    result.interpretation
                ),
            },
            "wall_table": (
                wall_table.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_WALL_INTELLIGENCE"
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
    Run the live Wall module with clear error reporting.
    """

    try:
        run_live_walls()

    except Exception as error:
        print()
        print("=" * 76)
        print("AQSD LIVE WALL ENGINE — FAILED")
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
            "and live option-chain response."
        )

        print("=" * 76)
        print()

        raise


if __name__ == "__main__":
    main()