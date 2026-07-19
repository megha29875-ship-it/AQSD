"""
AQSD
Option Intelligence

Module: live_oi_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain from FYERS and runs the
AQSD Open Interest Intelligence Engine.

Workflow:
FYERS Live Option Chain
        ↓
AQSD Option Chain Loader
        ↓
OI Engine
        ↓
Shared Exporter
"""

from __future__ import annotations

from dataclasses import asdict

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
)

from Scripts.option_intelligence.oi_engine import (
    analyze_open_interest,
    print_oi_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"
STRIKE_COUNT = 15


# ============================================================
# LIVE OI RUNNER
# ============================================================

def run_live_oi() -> None:
    """
    Fetch the live BANKNIFTY option chain and run OI analytics.
    """

    print()
    print("=" * 76)
    print("AQSD — LIVE BANKNIFTY OI INTELLIGENCE")
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

    live_dataframe = live_result.raw_dataframe

    print(
        f"Spot Price          : "
        f"{live_result.spot_price:,.2f}"
    )

    print(
        f"Option Rows         : "
        f"{len(live_dataframe)}"
    )

    print(
        f"Number of Strikes   : "
        f"{live_result.option_chain_data.number_of_strikes}"
    )

    print()

    oi_result, strike_table = analyze_open_interest(
        live_dataframe
    )

    print_oi_summary(
        oi_result
    )

    metadata = ExportMetadata(
        engine="OI",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(live_dataframe),
        status="SUCCESS",
        source="FYERS Live Option Chain",
        notes=(
            "Live BANKNIFTY Open Interest Intelligence "
            "using FYERS market data."
        ),
    )

    history_row = {
        "timestamp": (
            live_result.option_chain_data.timestamp
        ),
        "spot_price": live_result.spot_price,
        "total_call_oi": oi_result.total_call_oi,
        "total_put_oi": oi_result.total_put_oi,
        "total_call_change_oi": (
            oi_result.total_call_change_oi
        ),
        "total_put_change_oi": (
            oi_result.total_put_change_oi
        ),
        "oi_pcr": oi_result.oi_pcr,
        "change_oi_pcr": oi_result.change_oi_pcr,
        "oi_imbalance": oi_result.oi_imbalance,
        "market_bias": oi_result.market_bias,
        "build_up_signal": oi_result.build_up_signal,
        "positional_call_wall": (
            oi_result.positional_call_wall
        ),
        "positional_put_wall": (
            oi_result.positional_put_wall
        ),
        "fresh_call_wall": (
            oi_result.fresh_call_wall
        ),
        "fresh_put_wall": (
            oi_result.fresh_put_wall
        ),
    }

    engine_result = EngineResult(
        summary=oi_result,
        table=strike_table,
        history=history_row,
        metadata=metadata,
        json_data={
            "spot_price": live_result.spot_price,
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "summary": asdict(oi_result),
            "strike_table": strike_table.to_dict(
                orient="records"
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_OI_INTELLIGENCE"
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
    Run the live OI module with clear error reporting.
    """

    try:
        run_live_oi()

    except Exception as error:
        print()
        print("=" * 76)
        print("AQSD LIVE OI ENGINE — FAILED")
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