"""
AQSD
Option Intelligence

Module: live_maxpain_runner.py
Version: 1.0
Author: AQSD

Description:
Fetches the live BANKNIFTY option chain from FYERS and runs the
AQSD Max Pain Intelligence Engine.

Workflow:
FYERS Live Option Chain
        ↓
AQSD Option Chain Loader
        ↓
Max Pain Engine
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

from Scripts.option_intelligence.max_pain_engine import (
    analyze_max_pain,
    print_max_pain_summary,
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
    / "MaxPain"
    / "BANKNIFTY_LIVE_MAXPAIN_INTELLIGENCE_History.csv"
)


# ============================================================
# LIVE MAX PAIN RUNNER
# ============================================================

def run_live_max_pain() -> None:
    """
    Fetch the live BANKNIFTY option chain and run Max Pain analytics.
    """

    print()
    print("=" * 76)
    print("AQSD — LIVE BANKNIFTY MAX PAIN INTELLIGENCE")
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

    result, pain_table = analyze_max_pain(
        option_chain_data=option_chain_data,
        history_file=LIVE_HISTORY_FILE,
    )

    print_max_pain_summary(
        result
    )

    print("Pain Table")
    print("-" * 76)

    print(
        pain_table[
            [
                "settlement_strike",
                "call_pain",
                "put_pain",
                "total_pain",
            ]
        ].to_string(
            index=False
        )
    )

    print()

    metadata = ExportMetadata(
        engine="MAX_PAIN",
        underlying=UNDERLYING,
        engine_version="1.0",
        rows_processed=len(
            live_result.raw_dataframe
        ),
        status="SUCCESS",
        source="FYERS Live Option Chain",
        notes=(
            "Live BANKNIFTY Max Pain Intelligence "
            "using FYERS market data."
        ),
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "atm_strike": result.atm_strike,
        "max_pain_strike": (
            result.max_pain_strike
        ),
        "distance_from_spot": (
            result.distance_from_spot
        ),
        "distance_from_spot_percent": (
            result.distance_from_spot_percent
        ),
        "minimum_total_pain": (
            result.minimum_total_pain
        ),
        "pain_gap_percent": (
            result.pain_gap_percent
        ),
        "pinning_probability": (
            result.pinning_probability
        ),
        "magnet_strength": (
            result.magnet_strength
        ),
        "expiry_bias": result.expiry_bias,
        "pain_shift": result.pain_shift,
    }

    engine_result = EngineResult(
        summary=result,
        table=pain_table,
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
            "max_pain": {
                "max_pain_strike": (
                    result.max_pain_strike
                ),
                "distance_from_spot": (
                    result.distance_from_spot
                ),
                "distance_from_spot_percent": (
                    result.distance_from_spot_percent
                ),
                "minimum_total_pain": (
                    result.minimum_total_pain
                ),
                "second_lowest_pain": (
                    result.second_lowest_pain
                ),
                "pain_gap_percent": (
                    result.pain_gap_percent
                ),
                "pinning_probability": (
                    result.pinning_probability
                ),
                "magnet_strength": (
                    result.magnet_strength
                ),
                "expiry_bias": (
                    result.expiry_bias
                ),
                "pain_shift": (
                    result.pain_shift
                ),
                "interpretation": (
                    result.interpretation
                ),
            },
            "pain_table": (
                pain_table.to_dict(
                    orient="records"
                )
            ),
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_LIVE_MAXPAIN_INTELLIGENCE"
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
    Run the live Max Pain module with clear error reporting.
    """

    try:
        run_live_max_pain()

    except Exception as error:
        print()
        print("=" * 76)
        print("AQSD LIVE MAX PAIN ENGINE — FAILED")
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