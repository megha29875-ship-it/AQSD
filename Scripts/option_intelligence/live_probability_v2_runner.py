"""
AQSD
Live Probability Engine V2 Runner

Module: live_probability_v2_runner.py
Version: 1.0
Author: AQSD

Description:
Reads the latest BANKNIFTY analytics from AQSD JSON outputs and
feeds them into the Normalized Probability Engine V2.

Inputs:
- Live Decision Intelligence
- Live IV Surface
- Volatility Analytics

Outputs:
- Normalized scenario probabilities totalling exactly 100%
- Probability evidence
- Probability history

Analytics only. No order placement.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from Scripts.option_intelligence.probability_engine_v2 import (
    ProbabilityInputs,
    ProbabilityResult,
    analyze_probabilities,
    export_probability_result,
    print_probability_summary,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DECISION_JSON_FILE = (
    BASE_DIR
    / "Output"
    / "DECISION"
    / "BANKNIFTY_LIVE_DECISION_INTELLIGENCE.json"
)

IV_SURFACE_JSON_FILE = (
    BASE_DIR
    / "Output"
    / "IV_Surface_Live"
    / "BANKNIFTY_LIVE_IV_SURFACE_Summary.json"
)

VOLATILITY_JSON_FILE = (
    BASE_DIR
    / "Output"
    / "Volatility_Analytics"
    / "BANKNIFTY_VOLATILITY_ANALYTICS.json"
)

UNDERLYING = "BANKNIFTY"


# ============================================================
# JSON HELPERS
# ============================================================

def load_json_file(
    file_path: Path,
    required: bool = True,
) -> dict[str, Any]:
    """
    Load a JSON object from disk.
    """

    if not file_path.exists():
        if required:
            raise FileNotFoundError(
                f"Required JSON file was not found: {file_path}"
            )

        return {}

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise RuntimeError(
            f"JSON file does not contain an object: {file_path}"
        )

    return data


def normalize_key(
    value: Any,
) -> str:
    """
    Normalize a JSON key for flexible matching.
    """

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


def find_nested_value(
    data: Any,
    *candidate_keys: str,
) -> Any:
    """
    Search recursively for the first matching key.

    Key matching ignores spaces, underscores, dashes and case.
    """

    normalized_candidates = {
        normalize_key(key)
        for key in candidate_keys
    }

    def search(
        value: Any,
    ) -> Any:
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    normalize_key(key)
                    in normalized_candidates
                ):
                    if item is not None:
                        return item

            for item in value.values():
                result = search(item)

                if result is not None:
                    return result

        elif isinstance(value, list):
            for item in value:
                result = search(item)

                if result is not None:
                    return result

        return None

    return search(data)


def first_available(
    sources: list[dict[str, Any]],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Return the first matching value from multiple JSON sources.
    """

    for source in sources:
        value = find_nested_value(
            source,
            *keys,
        )

        if value is not None:
            return value

    return default


# ============================================================
# VALUE CONVERSION
# ============================================================

def safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float safely.
    """

    if value is None:
        return None

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(",", "")
            .replace("%", "")
        )

        if not cleaned:
            return None

        value = cleaned

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if math.isnan(number):
        return None

    if math.isinf(number):
        return None

    return number


def safe_text(
    value: Any,
    default: str = "N/A",
) -> str:
    """
    Convert a value to useful text.
    """

    if value is None:
        return default

    text = str(value).strip()

    return text or default


# ============================================================
# INPUT RESOLUTION
# ============================================================

def resolve_probability_inputs(
    decision_data: dict[str, Any],
    iv_data: dict[str, Any],
    volatility_data: dict[str, Any],
) -> ProbabilityInputs:
    """
    Build ProbabilityInputs from live AQSD JSON files.
    """

    sources = [
        decision_data,
        iv_data,
        volatility_data,
    ]

    spot_price = safe_float(
        first_available(
            sources,
            "spot_price",
            "spotprice",
            "banknifty_spot",
            "underlying_price",
            "index_price",
        )
    )

    atm_strike = safe_float(
        first_available(
            sources,
            "atm_strike",
            "atmstrike",
        )
    )

    if spot_price is None or spot_price <= 1000.0:
        raise RuntimeError(
            "A valid BANKNIFTY spot price could not be resolved."
        )

    if atm_strike is None or atm_strike <= 1000.0:
        raise RuntimeError(
            "A valid BANKNIFTY ATM strike could not be resolved."
        )

    return ProbabilityInputs(
        underlying=UNDERLYING,
        spot_price=spot_price,
        atm_strike=atm_strike,

        oi_pcr=safe_float(
            first_available(
                sources,
                "oi_pcr",
                "oipcr",
                "pcr_oi",
            )
        ),

        change_oi_pcr=safe_float(
            first_available(
                sources,
                "change_oi_pcr",
                "changeoi_pcr",
                "changeinoipcr",
                "coi_pcr",
            )
        ),

        volume_pcr=safe_float(
            first_available(
                sources,
                "volume_pcr",
                "volumepcr",
                "vol_pcr",
            )
        ),

        modified_pcr=safe_float(
            first_available(
                sources,
                "modified_pcr",
                "modifiedpcr",
            )
        ),

        call_wall=safe_float(
            first_available(
                sources,
                "call_wall",
                "positional_call_wall",
                "positionalcallwall",
            )
        ),

        put_wall=safe_float(
            first_available(
                sources,
                "put_wall",
                "positional_put_wall",
                "positionalputwall",
            )
        ),

        max_pain=safe_float(
            first_available(
                sources,
                "max_pain",
                "maxpain",
            )
        ),

        pinning_probability=safe_float(
            first_available(
                sources,
                "pinning_probability",
                "pinningprobability",
                "pinning_probability_percent",
            )
        ),

        atm_iv=safe_float(
            first_available(
                sources,
                "atm_iv",
                "current_atm_iv",
                "atmcombinediv",
            )
        ),

        iv_rank=safe_float(
            first_available(
                sources,
                "iv_rank",
                "ivrank",
            )
        ),

        iv_percentile=safe_float(
            first_available(
                sources,
                "iv_percentile",
                "ivpercentile",
            )
        ),

        hv20=safe_float(
            first_available(
                sources,
                "historical_volatility_20",
                "hv20",
                "historicalvolatility20",
            )
        ),

        volatility_premium_20=safe_float(
            first_available(
                sources,
                "volatility_premium_20",
                "iv_hv20_premium",
                "ivhv20premium",
            )
        ),

        volatility_heat_score=safe_float(
            first_available(
                sources,
                "volatility_heat_score",
                "volatilityheatscore",
            )
        ),

        volatility_regime=safe_text(
            first_available(
                sources,
                "volatility_regime",
                "volatilityregime",
            )
        ),

        volatility_signal=safe_text(
            first_available(
                sources,
                "volatility_signal",
                "volatilitysignal",
            )
        ),

        mean_reversion_signal=safe_text(
            first_available(
                sources,
                "mean_reversion_signal",
                "meanreversionsignal",
            )
        ),

        market_regime=safe_text(
            first_available(
                sources,
                "market_regime",
                "marketregime",
            )
        ),

        pcr_trend=safe_text(
            first_available(
                sources,
                "pcr_trend",
                "pcrtrend",
            )
        ),

        wall_shift=safe_text(
            first_available(
                sources,
                "combined_wall_shift",
                "wall_shift",
                "wallshift",
            )
        ),

        skew_signal=safe_text(
            first_available(
                sources,
                "skew_signal",
                "skewsignal",
            )
        ),

        price_change_percent=safe_float(
            first_available(
                sources,
                "price_change_percent",
                "change_percent",
                "spot_change_percent",
                "percentage_change",
            )
        ),

        trend_signal=safe_text(
            first_available(
                sources,
                "trend_signal",
                "trend",
                "directional_bias",
                "decision_bias",
            )
        ),
    )


# ============================================================
# INPUT DISPLAY
# ============================================================

def format_optional_number(
    value: float | None,
    decimals: int = 3,
    suffix: str = "",
) -> str:
    """
    Format an optional numeric value.
    """

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}{suffix}"


def print_resolved_inputs(
    inputs: ProbabilityInputs,
) -> None:
    """
    Print the live values supplied to the engine.
    """

    print()
    print("Resolved Live Inputs")
    print("-" * 88)

    print(
        f"Spot Price              : "
        f"{inputs.spot_price:,.2f}"
    )
    print(
        f"ATM Strike              : "
        f"{inputs.atm_strike:,.2f}"
    )
    print(
        f"OI PCR                  : "
        f"{format_optional_number(inputs.oi_pcr)}"
    )
    print(
        f"Change-OI PCR           : "
        f"{format_optional_number(inputs.change_oi_pcr)}"
    )
    print(
        f"Volume PCR              : "
        f"{format_optional_number(inputs.volume_pcr)}"
    )
    print(
        f"Modified PCR            : "
        f"{format_optional_number(inputs.modified_pcr)}"
    )
    print(
        f"Call Wall               : "
        f"{format_optional_number(inputs.call_wall, 0)}"
    )
    print(
        f"Put Wall                : "
        f"{format_optional_number(inputs.put_wall, 0)}"
    )
    print(
        f"Max Pain                : "
        f"{format_optional_number(inputs.max_pain, 0)}"
    )
    print(
        f"Pinning Probability     : "
        f"{format_optional_number(inputs.pinning_probability, 2, '%')}"
    )
    print(
        f"ATM IV                  : "
        f"{format_optional_number(inputs.atm_iv, 2, '%')}"
    )
    print(
        f"IV Rank                 : "
        f"{format_optional_number(inputs.iv_rank, 2, '%')}"
    )
    print(
        f"IV Percentile           : "
        f"{format_optional_number(inputs.iv_percentile, 2, '%')}"
    )
    print(
        f"HV20                    : "
        f"{format_optional_number(inputs.hv20, 2, '%')}"
    )
    print(
        f"IV-HV20 Premium         : "
        f"{format_optional_number(inputs.volatility_premium_20, 2, '%')}"
    )
    print(
        f"Volatility Heat Score   : "
        f"{format_optional_number(inputs.volatility_heat_score, 2)}"
    )
    print(
        f"Volatility Regime       : "
        f"{inputs.volatility_regime}"
    )
    print(
        f"Volatility Signal       : "
        f"{inputs.volatility_signal}"
    )
    print(
        f"Mean Reversion Signal   : "
        f"{inputs.mean_reversion_signal}"
    )
    print(
        f"Market Regime           : "
        f"{inputs.market_regime}"
    )
    print(
        f"PCR Trend               : "
        f"{inputs.pcr_trend}"
    )
    print(
        f"Wall Shift              : "
        f"{inputs.wall_shift}"
    )
    print(
        f"Skew Signal             : "
        f"{inputs.skew_signal}"
    )
    print(
        f"Trend Signal            : "
        f"{inputs.trend_signal}"
    )


# ============================================================
# LIVE WORKFLOW
# ============================================================

def run_live_probability_v2() -> ProbabilityResult:
    """
    Run the complete live normalized probability workflow.
    """

    print()
    print("=" * 88)
    print(
        "AQSD — LIVE NORMALIZED PROBABILITY ENGINE V2"
        .center(88)
    )
    print("=" * 88)
    print()

    print(
        "1/5  Reading live Decision Intelligence JSON..."
    )

    decision_data = load_json_file(
        DECISION_JSON_FILE,
        required=True,
    )

    print(
        "2/5  Reading live IV Surface JSON..."
    )

    iv_data = load_json_file(
        IV_SURFACE_JSON_FILE,
        required=True,
    )

    print(
        "3/5  Reading Volatility Analytics JSON..."
    )

    volatility_data = load_json_file(
        VOLATILITY_JSON_FILE,
        required=True,
    )

    print(
        "4/5  Resolving live probability inputs..."
    )

    inputs = resolve_probability_inputs(
        decision_data=decision_data,
        iv_data=iv_data,
        volatility_data=volatility_data,
    )

    print_resolved_inputs(
        inputs
    )

    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    print()
    print(
        "5/5  Running and exporting Probability Engine V2..."
    )

    result = analyze_probabilities(
        inputs=inputs,
        timestamp=timestamp,
    )

    exported_files = export_probability_result(
        result
    )

    print_probability_summary(
        result
    )

    print()
    print("Exported Files")
    print("-" * 88)

    for label, path in exported_files.items():
        print(
            f"{label:30} : {path}"
        )

    print()
    print(
        "Status                        : SUCCESS"
    )
    print("=" * 88)

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Execute the live Probability Engine V2 runner.
    """

    try:
        run_live_probability_v2()

    except Exception as error:
        print()
        print("=" * 88)
        print(
            "AQSD LIVE PROBABILITY ENGINE V2 — FAILED"
        )
        print("=" * 88)
        print(
            f"Error Type : {type(error).__name__}"
        )
        print(
            f"Message    : {error}"
        )
        print("=" * 88)

        raise


if __name__ == "__main__":
    main()