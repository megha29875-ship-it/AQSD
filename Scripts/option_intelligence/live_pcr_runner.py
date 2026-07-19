"""
AQSD
Option Intelligence

Module: live_pcr_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain from FYERS and runs the
AQSD PCR Intelligence Engine.

Workflow:
FYERS Live Option Chain
        ↓
AQSD Option Chain Loader
        ↓
PCR Engine
        ↓
Shared Exporter
"""

from __future__ import annotations

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.fyers_option_chain_loader import (
    fetch_live_option_chain,
)

from Scripts.option_intelligence.pcr_engine import (
    analyze_pcr,
    print_pcr_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

UNDERLYING = "BANKNIFTY"
FYERS_SYMBOL = "NSE:NIFTYBANK-INDEX"
STRIKE_COUNT = 15
ATM_WINDOW_STRIKES_EACH_SIDE = 3


# ============================================================
# LIVE PCR RUNNER
# ============================================================

def run_live_pcr() -> None:
    """
    Fetch the live BANKNIFTY option chain and run PCR analytics.
    """

    print()
    print("=" * 76)
    print("AQSD — LIVE BANKNIFTY PCR INTELLIGENCE")
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
        f"Option Rows         : "
        f"{len(live_result.raw_dataframe)}"
    )

    print(
        f"Number of Strikes   : "
        f"{option_chain_data.number_of_strikes}"
    )

    print()

    pcr_result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=(
            ATM_WINDOW_STRIKES_EACH_SIDE
        ),
    )

    print_pcr_summary(
        pcr_result
    )

    metadata = ExportMetadata(
        engine="PCR",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            live_result.raw_dataframe
        ),
        status="SUCCESS",
        source="FYERS Live Option Chain",
        notes=(
            "Live BANKNIFTY PCR Intelligence "
            "using FYERS market data."
        ),
    )

    history_row = {
        "timestamp": pcr_result.timestamp,
        "spot_price": pcr_result.spot_price,
        "atm_strike": pcr_result.atm_strike,
        "oi_pcr": pcr_result.oi_pcr,
        "change_oi_pcr": (
            pcr_result.change_oi_pcr
        ),
        "volume_pcr": pcr_result.volume_pcr,
        "modified_pcr": (
            pcr_result.modified_pcr
        ),
        "atm_zone_pcr": (
            pcr_result.atm_zone_pcr
        ),
        "pcr_trend": pcr_result.pcr_trend,
        "pcr_bias": pcr_result.pcr_bias,
        "reversal_watch": (
            pcr_result.reversal_watch
        ),
    }

    engine_result = EngineResult(
        summary=pcr_result,
        table=None,
        history=history_row,
        metadata=metadata,
        json_data={
            "symbol": FYERS_SYMBOL,
            "underlying": UNDERLYING,
            "spot_price": live_result.spot_price,
            "atm_strike": (
                option_chain_data.atm_strike
            ),
            "pcr": {
                "oi_pcr": pcr_result.oi_pcr,
                "change_oi_pcr": (
                    pcr_result.change_oi_pcr
                ),
                "volume_pcr": (
                    pcr_result.volume_pcr
                ),
                "modified_pcr": (
                    pcr_result.modified_pcr
                ),
                "atm_zone_pcr": (
                    pcr_result.atm_zone_pcr
                ),
                "pcr_trend": (
                    pcr_result.pcr_trend
                ),
                "pcr_bias": pcr_result.pcr_bias,
                "reversal_watch": (
                    pcr_result.reversal_watch
                ),
                "interpretation": (
                    pcr_result.interpretation
                ),
            },
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_PCR_INTELLIGENCE"
        ),
        save_table=False,
    )

    print_export_report(
        export_paths
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Run the live PCR module with clear error reporting.
    """

    try:
        run_live_pcr()

    except Exception as error:
        print()
        print("=" * 76)
        print("AQSD LIVE PCR ENGINE — FAILED")
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