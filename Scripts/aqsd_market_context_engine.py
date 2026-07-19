"""
AQSD Market Context Engine v1.0
===============================

Purpose
-------
Builds the market-context layer used by the AQSD options-buyer cockpit.

The engine reads the latest AQSD/FYERS output files and calculates:

- Spot
- Day Open / High / Low / Previous Close
- Yesterday High / Low / Close
- Average Traded Price (ATP)
- Daily Pivot
- R1 / R2 / R3
- S1 / S2 / S3
- CPR: BC / Pivot / TC
- Spot distance from ATP, Pivot, YH and YL
- Breakout / Breakdown state
- HH-HL / LH-LL / Sideways structure
- Strongest support and resistance logic
- Options-buyer market context score

Primary output
--------------
Output/AQSD_Market_Context.csv
Output/AQSD_Market_Context.json

Run
---
python Scripts\\aqsd_market_context_engine.py --status
python Scripts\\aqsd_market_context_engine.py --inspect
python Scripts\\aqsd_market_context_engine.py --run --underlying BANKNIFTY
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "Output"

INPUT_FILES = [
    OUTPUT / "AQSD_FYERS_Option_Chain_Summary.csv",
    OUTPUT / "AQSD_Options_Intelligence.csv",
    OUTPUT / "AQSD_AI_Master_Decision.csv",
    OUTPUT / "AQSD_Command_Center_v2.csv",
    OUTPUT / "AQSD_Market_Structure.csv",
    OUTPUT / "AQSD_FYERS_Live_Scanner.csv",
    OUTPUT / "AQSD_Live_Scanner.csv",
    OUTPUT / "Live_Scanner.csv",
    OUTPUT / "AQSD_Futures_Analytics.csv",
    OUTPUT / "BANKNIFTY_Futures_Analytics.csv",
]

OUTPUT_CSV = OUTPUT / "AQSD_Market_Context.csv"
OUTPUT_JSON = OUTPUT / "AQSD_Market_Context.json"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isnan(number):
            return default
        return number
    except Exception:
        return default


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return default
    return text


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def latest_row(path: Path) -> dict[str, Any]:
    frame = read_csv(path)

    if frame.empty:
        return {}

    return frame.iloc[-1].to_dict()


def normalize_key(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def pick(
    sources: list[dict[str, Any]],
    candidates: list[str],
    default: Any = None,
) -> Any:
    for source in sources:
        if not source:
            continue

        mapping = {
            normalize_key(key): value
            for key, value in source.items()
        }

        for candidate in candidates:
            key = normalize_key(candidate)

            if key in mapping:
                value = mapping[key]

                if safe_text(value):
                    return value

    return default


def detect_column(
    frame: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    mapping = {
        normalize_key(column): column
        for column in frame.columns
    }

    for candidate in candidates:
        key = normalize_key(candidate)

        if key in mapping:
            return mapping[key]

    return None


def load_sources() -> list[dict[str, Any]]:
    return [
        latest_row(path)
        for path in INPUT_FILES
        if path.exists()
    ]


def derive_from_scanner(
    underlying: str,
) -> dict[str, Any]:
    scanner_paths = [
        OUTPUT / "AQSD_FYERS_Live_Scanner.csv",
        OUTPUT / "AQSD_Live_Scanner.csv",
        OUTPUT / "Live_Scanner.csv",
    ]

    for path in scanner_paths:
        frame = read_csv(path)

        if frame.empty:
            continue

        symbol_col = detect_column(
            frame,
            [
                "underlying",
                "symbol",
                "ticker",
                "instrument",
                "tradingsymbol",
            ],
        )

        if symbol_col:
            selected = frame[
                frame[symbol_col]
                .astype(str)
                .str.upper()
                .str.contains(underlying, na=False)
            ]

            if not selected.empty:
                return selected.iloc[-1].to_dict()

    return {}


def calculate_atp(
    sources: list[dict[str, Any]],
    fallback_spot: float,
) -> tuple[float, str]:
    explicit_atp = safe_float(
        pick(
            sources,
            [
                "average_trade_price",
                "average_traded_price",
                "atp",
                "average_price",
                "vwap",
            ],
            0.0,
        )
    )

    if explicit_atp > 0:
        return explicit_atp, "DIRECT"

    turnover = safe_float(
        pick(
            sources,
            [
                "total_turnover",
                "turnover",
                "traded_value",
                "value",
            ],
            0.0,
        )
    )

    volume = safe_float(
        pick(
            sources,
            [
                "total_volume",
                "volume",
                "traded_volume",
            ],
            0.0,
        )
    )

    if turnover > 0 and volume > 0:
        return turnover / volume, "TURNOVER/VOLUME"

    return fallback_spot, "SPOT FALLBACK"


def calculate_pivots(
    high: float,
    low: float,
    close: float,
) -> dict[str, float]:
    if not all(
        value > 0
        for value in [high, low, close]
    ):
        return {
            "pivot": 0.0,
            "r1": 0.0,
            "r2": 0.0,
            "r3": 0.0,
            "s1": 0.0,
            "s2": 0.0,
            "s3": 0.0,
            "cpr_bc": 0.0,
            "cpr_tc": 0.0,
            "cpr_width": 0.0,
        }

    pivot = (high + low + close) / 3
    range_size = high - low

    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + range_size
    s2 = pivot - range_size
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)

    bc = (high + low) / 2
    tc = 2 * pivot - bc

    lower_cpr = min(bc, tc)
    upper_cpr = max(bc, tc)

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "r3": round(r3, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "s3": round(s3, 2),
        "cpr_bc": round(lower_cpr, 2),
        "cpr_tc": round(upper_cpr, 2),
        "cpr_width": round(
            upper_cpr - lower_cpr,
            2,
        ),
    }


def determine_structure(
    spot: float,
    atp: float,
    pivot: float,
    yesterday_high: float,
    yesterday_low: float,
    day_high: float,
    day_low: float,
) -> str:
    bullish_alignment = (
        spot > atp > pivot > 0
    )

    bearish_alignment = (
        spot < atp < pivot
        and pivot > 0
    )

    high_breakout = (
        yesterday_high > 0
        and spot > yesterday_high
    )

    low_breakdown = (
        yesterday_low > 0
        and spot < yesterday_low
    )

    higher_high = (
        yesterday_high > 0
        and day_high > yesterday_high
    )

    higher_low = (
        yesterday_low > 0
        and day_low > yesterday_low
    )

    lower_high = (
        yesterday_high > 0
        and day_high < yesterday_high
    )

    lower_low = (
        yesterday_low > 0
        and day_low < yesterday_low
    )

    if bullish_alignment and (
        high_breakout
        or (higher_high and higher_low)
    ):
        return "HH-HL"

    if bearish_alignment and (
        low_breakdown
        or (lower_high and lower_low)
    ):
        return "LH-LL"

    return "SIDEWAYS / MIXED"


def level_state(
    spot: float,
    level: float,
    tolerance_points: float,
) -> str:
    if level <= 0:
        return "NO DATA"

    distance = spot - level

    if abs(distance) <= tolerance_points:
        return "AT LEVEL"

    if distance > 0:
        return "ABOVE"

    return "BELOW"


def breakout_state(
    spot: float,
    yesterday_high: float,
    yesterday_low: float,
) -> str:
    if (
        yesterday_high > 0
        and spot > yesterday_high
    ):
        return "ABOVE YESTERDAY HIGH"

    if (
        yesterday_low > 0
        and spot < yesterday_low
    ):
        return "BELOW YESTERDAY LOW"

    if (
        yesterday_high > 0
        and yesterday_low > 0
    ):
        return "INSIDE YESTERDAY RANGE"

    return "NO YESTERDAY DATA"


def strongest_levels(
    structure: str,
    pivots: dict[str, float],
    yesterday_high: float,
    yesterday_low: float,
    atp: float,
) -> dict[str, Any]:
    if structure == "HH-HL":
        return {
            "strongest_support_name": "S1",
            "strongest_support": pivots["s1"],
            "secondary_support_name": "PIVOT / ATP",
            "secondary_support": max(
                pivots["pivot"],
                atp,
            ),
            "strongest_resistance_name": "YESTERDAY HIGH / R1",
            "strongest_resistance": max(
                yesterday_high,
                pivots["r1"],
            ),
            "level_logic": (
                "Bull structure: S1 is treated as the strongest "
                "buy-on-dip support. Pivot and ATP are trend-hold references."
            ),
        }

    if structure == "LH-LL":
        return {
            "strongest_support_name": "YESTERDAY LOW / S1",
            "strongest_support": min(
                value
                for value in [
                    yesterday_low,
                    pivots["s1"],
                ]
                if value > 0
            )
            if any(
                value > 0
                for value in [
                    yesterday_low,
                    pivots["s1"],
                ]
            )
            else 0.0,
            "secondary_support_name": "S2",
            "secondary_support": pivots["s2"],
            "strongest_resistance_name": "R1",
            "strongest_resistance": pivots["r1"],
            "level_logic": (
                "Bear structure: R1 is treated as the strongest "
                "sell-on-rise resistance. Pivot and ATP are rejection references."
            ),
        }

    return {
        "strongest_support_name": "YESTERDAY LOW",
        "strongest_support": yesterday_low,
        "secondary_support_name": "S1",
        "secondary_support": pivots["s1"],
        "strongest_resistance_name": "YESTERDAY HIGH",
        "strongest_resistance": yesterday_high,
        "level_logic": (
            "Sideways structure: Yesterday High and Yesterday Low "
            "are the primary range boundaries. Directional option buying is discouraged."
        ),
    }


def context_score(
    spot: float,
    atp: float,
    pivot: float,
    yesterday_high: float,
    yesterday_low: float,
    structure: str,
) -> dict[str, Any]:
    bullish = 0.0
    bearish = 0.0
    reasons: list[str] = []

    if spot > atp > 0:
        bullish += 25
        reasons.append("Spot above ATP")
    elif spot < atp and atp > 0:
        bearish += 25
        reasons.append("Spot below ATP")

    if spot > pivot > 0:
        bullish += 20
        reasons.append("Spot above Pivot")
    elif spot < pivot and pivot > 0:
        bearish += 20
        reasons.append("Spot below Pivot")

    if (
        yesterday_high > 0
        and spot > yesterday_high
    ):
        bullish += 25
        reasons.append("Yesterday High breakout")

    if (
        yesterday_low > 0
        and spot < yesterday_low
    ):
        bearish += 25
        reasons.append("Yesterday Low breakdown")

    if structure == "HH-HL":
        bullish += 30
        reasons.append("HH-HL structure")
    elif structure == "LH-LL":
        bearish += 30
        reasons.append("LH-LL structure")

    if bullish >= 65 and bullish > bearish:
        bias = "BULLISH"
        option_action = "CALL BIAS"
        score = bullish
    elif bearish >= 65 and bearish > bullish:
        bias = "BEARISH"
        option_action = "PUT BIAS"
        score = bearish
    else:
        bias = "SIDEWAYS"
        option_action = "WAIT"
        score = max(bullish, bearish)

    return {
        "market_context_bias": bias,
        "market_context_score": round(
            score,
            1,
        ),
        "bullish_context_score": round(
            bullish,
            1,
        ),
        "bearish_context_score": round(
            bearish,
            1,
        ),
        "option_context_action": option_action,
        "context_reasons": " | ".join(reasons),
    }


def run_engine(
    underlying: str,
) -> None:
    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    sources = load_sources()
    scanner_row = derive_from_scanner(
        underlying
    )

    if scanner_row:
        sources.insert(
            0,
            scanner_row,
        )

    if not sources:
        raise SystemExit(
            "No AQSD/FYERS source files were found in the Output folder."
        )

    spot = safe_float(
        pick(
            sources,
            [
                "spot_price",
                "spot",
                "ltp",
                "current_price",
                "last_price",
            ],
            0.0,
        )
    )

    day_open = safe_float(
        pick(
            sources,
            [
                "open",
                "day_open",
                "session_open",
                "today_open",
            ],
            0.0,
        )
    )

    day_high = safe_float(
        pick(
            sources,
            [
                "high",
                "day_high",
                "session_high",
                "today_high",
            ],
            0.0,
        )
    )

    day_low = safe_float(
        pick(
            sources,
            [
                "low",
                "day_low",
                "session_low",
                "today_low",
            ],
            0.0,
        )
    )

    previous_close = safe_float(
        pick(
            sources,
            [
                "previous_close",
                "prev_close",
                "yesterday_close",
                "close",
            ],
            0.0,
        )
    )

    yesterday_high = safe_float(
        pick(
            sources,
            [
                "previous_day_high",
                "yesterday_high",
                "prev_high",
                "previous_high",
            ],
            0.0,
        )
    )

    yesterday_low = safe_float(
        pick(
            sources,
            [
                "previous_day_low",
                "yesterday_low",
                "prev_low",
                "previous_low",
            ],
            0.0,
        )
    )

    yesterday_close = safe_float(
        pick(
            sources,
            [
                "previous_day_close",
                "yesterday_close",
                "prev_close",
                "previous_close",
            ],
            previous_close,
        )
    )

    atp, atp_source = calculate_atp(
        sources,
        spot,
    )

    pivots = calculate_pivots(
        yesterday_high,
        yesterday_low,
        yesterday_close,
    )

    structure = determine_structure(
        spot=spot,
        atp=atp,
        pivot=pivots["pivot"],
        yesterday_high=yesterday_high,
        yesterday_low=yesterday_low,
        day_high=day_high,
        day_low=day_low,
    )

    level_logic = strongest_levels(
        structure,
        pivots,
        yesterday_high,
        yesterday_low,
        atp,
    )

    context = context_score(
        spot=spot,
        atp=atp,
        pivot=pivots["pivot"],
        yesterday_high=yesterday_high,
        yesterday_low=yesterday_low,
        structure=structure,
    )

    tolerance = max(
        spot * 0.0005,
        10.0,
    )

    output = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "underlying": underlying,
        "spot": round(
            spot,
            2,
        ),
        "day_open": round(
            day_open,
            2,
        ),
        "day_high": round(
            day_high,
            2,
        ),
        "day_low": round(
            day_low,
            2,
        ),
        "previous_close": round(
            previous_close,
            2,
        ),
        "yesterday_high": round(
            yesterday_high,
            2,
        ),
        "yesterday_low": round(
            yesterday_low,
            2,
        ),
        "yesterday_close": round(
            yesterday_close,
            2,
        ),
        "average_traded_price": round(
            atp,
            2,
        ),
        "atp_source": atp_source,
        "spot_minus_atp": round(
            spot - atp,
            2,
        ),
        "spot_minus_yesterday_high": round(
            spot - yesterday_high,
            2,
        ),
        "spot_minus_yesterday_low": round(
            spot - yesterday_low,
            2,
        ),
        **pivots,
        "spot_minus_pivot": round(
            spot - pivots["pivot"],
            2,
        ),
        "spot_vs_atp": level_state(
            spot,
            atp,
            tolerance,
        ),
        "spot_vs_pivot": level_state(
            spot,
            pivots["pivot"],
            tolerance,
        ),
        "spot_vs_yesterday_high": level_state(
            spot,
            yesterday_high,
            tolerance,
        ),
        "spot_vs_yesterday_low": level_state(
            spot,
            yesterday_low,
            tolerance,
        ),
        "breakout_state": breakout_state(
            spot,
            yesterday_high,
            yesterday_low,
        ),
        "market_structure": structure,
        **level_logic,
        **context,
    }

    pd.DataFrame(
        [output]
    ).to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    OUTPUT_JSON.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        "\nAQSD MARKET CONTEXT ENGINE"
    )
    print(
        "=" * 92
    )
    print(
        f"Underlying:               {underlying}"
    )
    print(
        f"Spot:                     {spot:,.2f}"
    )
    print(
        f"ATP:                      {atp:,.2f} ({atp_source})"
    )
    print(
        f"Yesterday High:           {yesterday_high:,.2f}"
    )
    print(
        f"Yesterday Low:            {yesterday_low:,.2f}"
    )
    print(
        f"Yesterday Close:          {yesterday_close:,.2f}"
    )
    print(
        f"Pivot:                    {pivots['pivot']:,.2f}"
    )
    print(
        f"R1 / R2 / R3:            "
        f"{pivots['r1']:,.2f} / "
        f"{pivots['r2']:,.2f} / "
        f"{pivots['r3']:,.2f}"
    )
    print(
        f"S1 / S2 / S3:            "
        f"{pivots['s1']:,.2f} / "
        f"{pivots['s2']:,.2f} / "
        f"{pivots['s3']:,.2f}"
    )
    print(
        f"CPR BC / TC:              "
        f"{pivots['cpr_bc']:,.2f} / "
        f"{pivots['cpr_tc']:,.2f}"
    )
    print(
        "-" * 92
    )
    print(
        f"Structure:                {structure}"
    )
    print(
        f"Breakout State:           "
        f"{output['breakout_state']}"
    )
    print(
        f"Strongest Support:        "
        f"{output['strongest_support_name']} "
        f"{output['strongest_support']:,.2f}"
    )
    print(
        f"Strongest Resistance:     "
        f"{output['strongest_resistance_name']} "
        f"{output['strongest_resistance']:,.2f}"
    )
    print(
        "-" * 92
    )
    print(
        f"Context Bias:             "
        f"{context['market_context_bias']}"
    )
    print(
        f"Context Score:            "
        f"{context['market_context_score']:.1f}"
    )
    print(
        f"Options Context:          "
        f"{context['option_context_action']}"
    )
    print(
        f"Reasons:                  "
        f"{context['context_reasons']}"
    )
    print(
        "=" * 92
    )
    print(
        f"CSV:  {OUTPUT_CSV}"
    )
    print(
        f"JSON: {OUTPUT_JSON}"
    )


def show_status() -> None:
    print(
        "\nAQSD MARKET CONTEXT STATUS"
    )
    print(
        "=" * 92
    )

    for path in INPUT_FILES:
        print(
            f"{path.name:<42} "
            f"{'FOUND' if path.exists() else 'MISSING'}"
        )

    print(
        "=" * 92
    )


def inspect_sources() -> None:
    print(
        "\nAQSD MARKET CONTEXT SOURCE INSPECTION"
    )
    print(
        "=" * 92
    )

    for path in INPUT_FILES:
        if not path.exists():
            continue

        frame = read_csv(path)

        print(
            f"\nFILE: {path.name}"
        )
        print(
            f"COLUMNS: {list(frame.columns)}"
        )

        if not frame.empty:
            print(
                frame.tail(1).to_string(
                    index=False
                )
            )

    print(
        "=" * 92
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Market Context Engine"
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    parser.add_argument(
        "--inspect",
        action="store_true",
    )

    parser.add_argument(
        "--underlying",
        default="BANKNIFTY",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.inspect:
        inspect_sources()
        return

    if args.run:
        run_engine(
            args.underlying.strip().upper()
        )
        return

    raise SystemExit(
        "Use --status, --inspect, or "
        "--run --underlying BANKNIFTY"
    )


if __name__ == "__main__":
    main()
