"""
AQSD Market Structure Engine v1.1
Supports both LONG and WIDE FYERS option-chain CSV formats.
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

OPTION_CHAIN = OUTPUT / "AQSD_FYERS_Option_Chain.csv"
SUMMARY_FILES = [
    OUTPUT / "AQSD_FYERS_Option_Chain_Summary.csv",
    OUTPUT / "AQSD_Options_Intelligence.csv",
    OUTPUT / "AQSD_AI_Master_Decision.csv",
    OUTPUT / "AQSD_Command_Center_v2.csv",
]

OUTPUT_CSV = OUTPUT / "AQSD_Market_Structure.csv"
OUTPUT_JSON = OUTPUT / "AQSD_Market_Structure.json"
PCR_HISTORY = OUTPUT / "AQSD_PCR_History.csv"
WALL_HISTORY = OUTPUT / "AQSD_Wall_History.csv"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if math.isnan(number) else number
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
    return pd.read_csv(path, low_memory=False)


def latest_row(path: Path) -> dict[str, Any]:
    frame = read_csv(path)
    return {} if frame.empty else frame.iloc[-1].to_dict()


def column_map(frame: pd.DataFrame) -> dict[str, str]:
    return {
        str(col).strip().lower().replace(" ", "_"): col
        for col in frame.columns
    }


def find_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    mapping = column_map(frame)
    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in mapping:
            return mapping[key]
    return None


def pick(
    sources: list[dict[str, Any]],
    candidates: list[str],
    default: Any = None,
) -> Any:
    for source in sources:
        lowered = {
            str(k).strip().lower().replace(" ", "_"): v
            for k, v in source.items()
        }
        for candidate in candidates:
            key = candidate.strip().lower().replace(" ", "_")
            if key in lowered and safe_text(lowered[key]):
                return lowered[key]
    return default


def numeric(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if not column:
        return pd.Series([0.0] * len(frame), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def normalize_long_format(frame: pd.DataFrame) -> pd.DataFrame | None:
    strike_col = find_col(
        frame,
        ["strike", "strike_price", "strikeprice", "strike_price_value"],
    )
    type_col = find_col(
        frame,
        ["option_type", "type", "right", "cp_type", "optiontype"],
    )

    if not strike_col or not type_col:
        return None

    result = pd.DataFrame(index=frame.index)
    result["strike"] = pd.to_numeric(frame[strike_col], errors="coerce")
    result["option_type"] = (
        frame[type_col]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace(
            {
                "CALL": "CE",
                "C": "CE",
                "CALLS": "CE",
                "PUT": "PE",
                "P": "PE",
                "PUTS": "PE",
            }
        )
    )
    result["oi"] = numeric(
        frame,
        find_col(frame, ["open_interest", "oi", "openinterest"]),
    )
    result["change_oi"] = numeric(
        frame,
        find_col(
            frame,
            [
                "change_in_oi",
                "oi_change",
                "change_oi",
                "chg_oi",
                "changeinoi",
            ],
        ),
    )
    result["volume"] = numeric(
        frame,
        find_col(frame, ["volume", "traded_volume", "vol"]),
    )
    result["iv"] = numeric(
        frame,
        find_col(frame, ["iv", "implied_volatility", "impliedvolatility"]),
    )

    result = result.dropna(subset=["strike"])
    result = result[result["option_type"].isin(["CE", "PE"])].copy()
    return result if not result.empty else None


def normalize_wide_format(frame: pd.DataFrame) -> pd.DataFrame | None:
    strike_col = find_col(
        frame,
        ["strike", "strike_price", "strikeprice", "strike_price_value"],
    )

    if not strike_col:
        return None

    call_oi_col = find_col(
        frame,
        [
            "call_oi",
            "ce_oi",
            "calls_oi",
            "call_open_interest",
            "ce_open_interest",
            "callopeninterest",
        ],
    )
    put_oi_col = find_col(
        frame,
        [
            "put_oi",
            "pe_oi",
            "puts_oi",
            "put_open_interest",
            "pe_open_interest",
            "putopeninterest",
        ],
    )

    if not call_oi_col and not put_oi_col:
        return None

    strikes = pd.to_numeric(frame[strike_col], errors="coerce")

    calls = pd.DataFrame(
        {
            "strike": strikes,
            "option_type": "CE",
            "oi": numeric(frame, call_oi_col),
            "change_oi": numeric(
                frame,
                find_col(
                    frame,
                    [
                        "call_change_oi",
                        "ce_change_oi",
                        "call_oi_change",
                        "ce_oi_change",
                        "call_change_in_oi",
                        "ce_change_in_oi",
                        "call_chg_oi",
                    ],
                ),
            ),
            "volume": numeric(
                frame,
                find_col(
                    frame,
                    ["call_volume", "ce_volume", "call_vol", "ce_vol"],
                ),
            ),
            "iv": numeric(
                frame,
                find_col(
                    frame,
                    [
                        "call_iv",
                        "ce_iv",
                        "call_implied_volatility",
                        "ce_implied_volatility",
                    ],
                ),
            ),
        }
    )

    puts = pd.DataFrame(
        {
            "strike": strikes,
            "option_type": "PE",
            "oi": numeric(frame, put_oi_col),
            "change_oi": numeric(
                frame,
                find_col(
                    frame,
                    [
                        "put_change_oi",
                        "pe_change_oi",
                        "put_oi_change",
                        "pe_oi_change",
                        "put_change_in_oi",
                        "pe_change_in_oi",
                        "put_chg_oi",
                    ],
                ),
            ),
            "volume": numeric(
                frame,
                find_col(
                    frame,
                    ["put_volume", "pe_volume", "put_vol", "pe_vol"],
                ),
            ),
            "iv": numeric(
                frame,
                find_col(
                    frame,
                    [
                        "put_iv",
                        "pe_iv",
                        "put_implied_volatility",
                        "pe_implied_volatility",
                    ],
                ),
            ),
        }
    )

    result = pd.concat([calls, puts], ignore_index=True)
    result = result.dropna(subset=["strike"])
    return result if not result.empty else None


def normalize_option_chain(frame: pd.DataFrame) -> pd.DataFrame:
    long_result = normalize_long_format(frame)
    if long_result is not None:
        return long_result

    wide_result = normalize_wide_format(frame)
    if wide_result is not None:
        return wide_result

    raise RuntimeError(
        "Could not detect option-chain structure. "
        f"Available columns: {list(frame.columns)}. "
        "Run with --inspect and share the output."
    )


def append_history(path: Path, row: dict[str, Any]) -> pd.DataFrame:
    new = pd.DataFrame([row])
    if path.exists():
        try:
            old = pd.read_csv(path, low_memory=False)
            combined = pd.concat([old, new], ignore_index=True)
        except Exception:
            combined = new
    else:
        combined = new

    combined.to_csv(path, index=False, encoding="utf-8-sig")
    return combined


def calculate_pcr(chain: pd.DataFrame) -> dict[str, float]:
    calls = chain[chain["option_type"] == "CE"]
    puts = chain[chain["option_type"] == "PE"]

    call_oi = calls["oi"].sum()
    put_oi = puts["oi"].sum()
    call_change = calls["change_oi"].clip(lower=0).sum()
    put_change = puts["change_oi"].clip(lower=0).sum()
    call_volume = calls["volume"].sum()
    put_volume = puts["volume"].sum()

    oi_pcr = put_oi / call_oi if call_oi > 0 else 0.0
    change_pcr = put_change / call_change if call_change > 0 else 0.0
    volume_pcr = put_volume / call_volume if call_volume > 0 else 0.0
    modified_pcr = (
        oi_pcr * 0.50
        + change_pcr * 0.30
        + volume_pcr * 0.20
    )

    return {
        "oi_pcr": round(oi_pcr, 6),
        "change_oi_pcr": round(change_pcr, 6),
        "modified_pcr": round(modified_pcr, 6),
        "volume_pcr": round(volume_pcr, 6),
    }


def calculate_pcr_trend(history: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(
        history.get("modified_pcr"),
        errors="coerce",
    ).dropna().tail(8)

    if len(values) < 2:
        return {
            "pcr_trend": "INSUFFICIENT HISTORY",
            "pcr_slope": 0.0,
            "pcr_acceleration": 0.0,
            "pcr_interpretation": "Collect more snapshots.",
        }

    differences = values.diff().dropna()
    slope = safe_float(differences.mean())
    acceleration = (
        safe_float(differences.diff().dropna().mean())
        if len(differences) >= 2
        else 0.0
    )

    current = safe_float(values.iloc[-1])

    if slope > 0.01:
        trend = "RISING"
    elif slope < -0.01:
        trend = "FALLING"
    else:
        trend = "FLAT"

    if current < 0.85 and trend == "FALLING":
        interpretation = "BEARISH STRENGTHENING"
    elif current < 0.85 and trend == "RISING":
        interpretation = "BEARISH PRESSURE WEAKENING"
    elif current > 1.05 and trend == "RISING":
        interpretation = "BULLISH STRENGTHENING"
    elif current > 1.05 and trend == "FALLING":
        interpretation = "BULLISH PRESSURE WEAKENING"
    elif trend == "RISING":
        interpretation = "BULLISH MOMENTUM DEVELOPING"
    elif trend == "FALLING":
        interpretation = "BEARISH MOMENTUM DEVELOPING"
    else:
        interpretation = "SIDEWAYS / BALANCED"

    return {
        "pcr_trend": trend,
        "pcr_slope": round(slope, 6),
        "pcr_acceleration": round(acceleration, 6),
        "pcr_interpretation": interpretation,
    }


def strike_of_max(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return 0.0
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.dropna().empty:
        return 0.0
    idx = values.idxmax()
    return safe_float(frame.loc[idx, "strike"])


def calculate_walls(chain: pd.DataFrame) -> dict[str, float]:
    calls = chain[chain["option_type"] == "CE"].copy()
    puts = chain[chain["option_type"] == "PE"].copy()
    calls["positive_change"] = calls["change_oi"].clip(lower=0)
    puts["positive_change"] = puts["change_oi"].clip(lower=0)

    return {
        "positional_call_wall": strike_of_max(calls, "oi"),
        "fresh_call_wall": strike_of_max(calls, "positive_change"),
        "positional_put_wall": strike_of_max(puts, "oi"),
        "fresh_put_wall": strike_of_max(puts, "positive_change"),
    }


def calculate_wall_migration(history: pd.DataFrame) -> dict[str, str]:
    if len(history) < 2:
        return {
            "call_wall_shift": "INSUFFICIENT HISTORY",
            "put_wall_shift": "INSUFFICIENT HISTORY",
            "wall_migration": "INSUFFICIENT HISTORY",
        }

    previous = history.iloc[-2]
    current = history.iloc[-1]

    call_change = (
        safe_float(current.get("fresh_call_wall"))
        - safe_float(previous.get("fresh_call_wall"))
    )
    put_change = (
        safe_float(current.get("fresh_put_wall"))
        - safe_float(previous.get("fresh_put_wall"))
    )

    def direction(value: float) -> str:
        if value > 0:
            return "UP"
        if value < 0:
            return "DOWN"
        return "STABLE"

    if call_change > 0 and put_change > 0:
        migration = "BULLISH UPWARD SHIFT"
    elif call_change < 0 and put_change < 0:
        migration = "BEARISH DOWNWARD SHIFT"
    elif call_change < 0 and put_change > 0:
        migration = "RANGE COMPRESSION"
    elif call_change > 0 and put_change < 0:
        migration = "RANGE EXPANSION"
    else:
        migration = "MIXED / STABLE"

    return {
        "call_wall_shift": direction(call_change),
        "put_wall_shift": direction(put_change),
        "wall_migration": migration,
    }


def calculate_pivots(high: float, low: float, close: float) -> dict[str, float]:
    if not all(value > 0 for value in [high, low, close]):
        return {
            "pivot": 0.0,
            "r1": 0.0,
            "r2": 0.0,
            "s1": 0.0,
            "s2": 0.0,
        }

    pivot = (high + low + close) / 3
    return {
        "pivot": round(pivot, 2),
        "r1": round(2 * pivot - low, 2),
        "r2": round(pivot + high - low, 2),
        "s1": round(2 * pivot - high, 2),
        "s2": round(pivot - high + low, 2),
    }


def calculate_iv_move(
    spot: float,
    atm_iv: float,
    session_open: float,
) -> dict[str, float]:
    daily_percent = atm_iv / math.sqrt(252) if atm_iv > 0 else 0.0
    move_points = spot * daily_percent / 100 if spot > 0 else 0.0
    actual_move = (
        abs(spot - session_open)
        if spot > 0 and session_open > 0
        else 0.0
    )
    captured = (
        actual_move / move_points * 100
        if move_points > 0
        else 0.0
    )

    return {
        "daily_iv_move_percent": round(daily_percent, 4),
        "daily_iv_move_points": round(move_points, 2),
        "expected_upper_range": round(spot + move_points, 2),
        "expected_lower_range": round(spot - move_points, 2),
        "actual_move_points": round(actual_move, 2),
        "move_captured_percent": round(captured, 2),
        "remaining_move_points": round(
            max(move_points - actual_move, 0.0),
            2,
        ),
    }


def final_signal(
    spot: float,
    atp: float,
    pivot: float,
    yesterday_high: float,
    yesterday_low: float,
    pcr_interpretation: str,
    wall_migration: str,
    remaining_move: float,
) -> dict[str, Any]:
    bull = 0.0
    bear = 0.0
    reasons: list[str] = []

    if spot > atp > 0:
        bull += 20
        reasons.append("Spot above ATP")
    elif spot < atp and atp > 0:
        bear += 20
        reasons.append("Spot below ATP")

    if spot > pivot > 0:
        bull += 15
        reasons.append("Spot above Pivot")
    elif spot < pivot and pivot > 0:
        bear += 15
        reasons.append("Spot below Pivot")

    if spot > yesterday_high > 0:
        bull += 20
        reasons.append("Yesterday High breakout")
    elif spot < yesterday_low and yesterday_low > 0:
        bear += 20
        reasons.append("Yesterday Low breakdown")

    if "BULLISH" in pcr_interpretation.upper():
        bull += 15
        reasons.append(pcr_interpretation)
    elif "BEARISH" in pcr_interpretation.upper():
        bear += 15
        reasons.append(pcr_interpretation)

    if "BULLISH" in wall_migration.upper():
        bull += 10
        reasons.append(wall_migration)
    elif "BEARISH" in wall_migration.upper():
        bear += 10
        reasons.append(wall_migration)

    if remaining_move > 0:
        bull += 5
        bear += 5
        reasons.append("IV move remains")

    if bull >= 55 and bull > bear:
        signal = "BUY CALL"
        direction = "BULLISH"
        score = bull
    elif bear >= 55 and bear > bull:
        signal = "BUY PUT"
        direction = "BEARISH"
        score = bear
    else:
        signal = "WAIT"
        direction = "SIDEWAYS"
        score = max(bull, bear)

    return {
        "final_signal": signal,
        "final_direction": direction,
        "options_buyer_score": round(score, 1),
        "bullish_score": round(bull, 1),
        "bearish_score": round(bear, 1),
        "signal_reasons": " | ".join(reasons),
    }


def run_engine(underlying: str) -> None:
    if not OPTION_CHAIN.exists():
        raise SystemExit(f"Missing option-chain file: {OPTION_CHAIN}")

    raw_chain = read_csv(OPTION_CHAIN)
    chain = normalize_option_chain(raw_chain)

    summaries = [
        latest_row(path)
        for path in SUMMARY_FILES
        if path.exists()
    ]

    spot = safe_float(
        pick(
            summaries,
            ["spot_price", "spot", "ltp", "current_price"],
            0.0,
        )
    )
    previous_high = safe_float(
        pick(
            summaries,
            [
                "previous_day_high",
                "yesterday_high",
                "prev_high",
                "previous_high",
            ],
            0.0,
        )
    )
    previous_low = safe_float(
        pick(
            summaries,
            [
                "previous_day_low",
                "yesterday_low",
                "prev_low",
                "previous_low",
            ],
            0.0,
        )
    )
    previous_close = safe_float(
        pick(
            summaries,
            [
                "previous_close",
                "prev_close",
                "yesterday_close",
                "close",
            ],
            0.0,
        )
    )
    session_open = safe_float(
        pick(
            summaries,
            ["open", "session_open", "day_open"],
            previous_close,
        )
    )
    atp = safe_float(
        pick(
            summaries,
            [
                "average_trade_price",
                "average_traded_price",
                "atp",
                "vwap",
            ],
            spot,
        )
    )

    pcr = calculate_pcr(chain)

    timestamp = datetime.now().isoformat(timespec="seconds")

    pcr_history = append_history(
        PCR_HISTORY,
        {
            "timestamp": timestamp,
            "underlying": underlying,
            **pcr,
        },
    )
    pcr_intelligence = calculate_pcr_trend(pcr_history)

    walls = calculate_walls(chain)

    wall_history = append_history(
        WALL_HISTORY,
        {
            "timestamp": timestamp,
            "underlying": underlying,
            **walls,
        },
    )
    migration = calculate_wall_migration(wall_history)

    pivots = calculate_pivots(
        previous_high,
        previous_low,
        previous_close,
    )

    atm_iv = safe_float(
        pick(
            summaries,
            [
                "atm_iv",
                "average_atm_iv",
                "implied_volatility",
                "iv",
            ],
            0.0,
        )
    )

    if atm_iv <= 0 and spot > 0:
        temp = chain.copy()
        temp["distance"] = (temp["strike"] - spot).abs()
        atm_rows = temp.sort_values("distance").head(2)
        atm_iv = safe_float(atm_rows["iv"].mean(), 0.0)

    iv_move = calculate_iv_move(
        spot,
        atm_iv,
        session_open,
    )

    signal = final_signal(
        spot=spot,
        atp=atp,
        pivot=pivots["pivot"],
        yesterday_high=previous_high,
        yesterday_low=previous_low,
        pcr_interpretation=pcr_intelligence[
            "pcr_interpretation"
        ],
        wall_migration=migration["wall_migration"],
        remaining_move=iv_move["remaining_move_points"],
    )

    if (
        spot > atp > pivots["pivot"] > 0
        and spot > previous_high > 0
    ):
        structure = "HH-HL"
    elif (
        spot < atp < pivots["pivot"]
        and spot < previous_low
        and previous_low > 0
    ):
        structure = "LH-LL"
    else:
        structure = "SIDEWAYS / MIXED"

    output = {
        "generated_at": timestamp,
        "underlying": underlying,
        "spot": round(spot, 2),
        "average_traded_price": round(atp, 2),
        "spot_minus_atp": round(spot - atp, 2),
        "yesterday_high": round(previous_high, 2),
        "yesterday_low": round(previous_low, 2),
        "previous_close": round(previous_close, 2),
        **pivots,
        "market_structure": structure,
        **pcr,
        **pcr_intelligence,
        **walls,
        **migration,
        "atm_iv": round(atm_iv, 4),
        **iv_move,
        **signal,
    }

    pd.DataFrame([output]).to_csv(
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

    print("\nAQSD MARKET STRUCTURE ENGINE v1.1")
    print("=" * 92)
    print(f"Detected columns:         {list(raw_chain.columns)}")
    print(f"Normalised option rows:   {len(chain)}")
    print(f"Underlying:               {underlying}")
    print(f"Spot:                     {spot:,.2f}")
    print(f"ATP:                      {atp:,.2f}")
    print(f"Yesterday High / Low:     {previous_high:,.2f} / {previous_low:,.2f}")
    print(f"Pivot:                    {pivots['pivot']:,.2f}")
    print("-" * 92)
    print(f"OI PCR:                   {pcr['oi_pcr']:.4f}")
    print(f"Modified PCR:             {pcr['modified_pcr']:.4f}")
    print(f"Volume PCR:               {pcr['volume_pcr']:.4f}")
    print(f"PCR Trend:                {pcr_intelligence['pcr_trend']}")
    print(f"PCR Interpretation:       {pcr_intelligence['pcr_interpretation']}")
    print("-" * 92)
    print(f"Positional Call Wall:     {walls['positional_call_wall']:,.0f}")
    print(f"Fresh Call Wall:          {walls['fresh_call_wall']:,.0f}")
    print(f"Positional Put Wall:      {walls['positional_put_wall']:,.0f}")
    print(f"Fresh Put Wall:           {walls['fresh_put_wall']:,.0f}")
    print(f"Wall Migration:           {migration['wall_migration']}")
    print("-" * 92)
    print(f"ATM IV:                   {atm_iv:.2f}%")
    print(f"Daily IV Move:            {iv_move['daily_iv_move_percent']:.2f}%")
    print(f"Move Captured:            {iv_move['move_captured_percent']:.2f}%")
    print(f"Remaining Move:           {iv_move['remaining_move_points']:,.2f}")
    print("-" * 92)
    print(f"FINAL SIGNAL:             {signal['final_signal']}")
    print(f"OPTIONS BUYER SCORE:      {signal['options_buyer_score']:.1f}")
    print("=" * 92)
    print(f"CSV:  {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


def status() -> None:
    print("\nAQSD MARKET STRUCTURE STATUS v1.1")
    print("=" * 92)
    print(
        f"Option Chain: "
        f"{OPTION_CHAIN if OPTION_CHAIN.exists() else 'MISSING'}"
    )

    if OPTION_CHAIN.exists():
        try:
            frame = pd.read_csv(OPTION_CHAIN, nrows=2)
            print(f"Columns: {list(frame.columns)}")
        except Exception as exc:
            print(f"Read Error: {exc}")

    for path in SUMMARY_FILES:
        print(
            f"{path.name:<40} "
            f"{'FOUND' if path.exists() else 'MISSING'}"
        )

    print("=" * 92)


def inspect() -> None:
    if not OPTION_CHAIN.exists():
        raise SystemExit(f"Missing option-chain file: {OPTION_CHAIN}")

    frame = pd.read_csv(OPTION_CHAIN, low_memory=False)

    print("\nAQSD OPTION-CHAIN INSPECTION")
    print("=" * 92)
    print("COLUMNS:")
    for index, column in enumerate(frame.columns, start=1):
        print(f"{index:>3}. {column}")

    print("\nFIRST 5 ROWS:")
    print(frame.head().to_string(index=False))
    print("=" * 92)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Market Structure Engine v1.1"
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--underlying", default="BANKNIFTY")

    args = parser.parse_args()

    if args.status:
        status()
    elif args.inspect:
        inspect()
    elif args.run:
        run_engine(args.underlying.strip().upper())
    else:
        raise SystemExit(
            "Use --status, --inspect, or --run --underlying BANKNIFTY"
        )


if __name__ == "__main__":
    main()
