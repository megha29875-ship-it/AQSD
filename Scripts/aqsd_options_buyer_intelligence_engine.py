"""
AQSD Options Buyer Intelligence Engine v1.0

Calculates PCR intelligence, four option walls, daily pivots,
yesterday high/low, ATP, market structure and daily IV move.

Run:
    python Scripts/aqsd_options_buyer_intelligence_engine.py --status
    python Scripts/aqsd_options_buyer_intelligence_engine.py --run --underlying BANKNIFTY
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
OUT = BASE / "Output"

OPTION_CHAIN_FILES = [
    OUT / "BANKNIFTY_Option_Chain_Analytics.csv",
    OUT / "AQSD_Option_Chain_Analytics.csv",
    OUT / "Option_Chain_Analytics.csv",
    OUT / "BANKNIFTY_Options_Chain.csv",
    OUT / "AQSD_Options_Chain.csv",
]
SUMMARY_FILES = [
    OUT / "BANKNIFTY_Options_Intelligence_Summary.csv",
    OUT / "AQSD_Options_Intelligence_Summary.csv",
    OUT / "Options_Intelligence_Summary.csv",
    OUT / "AQSD_Command_Center_v2.csv",
    OUT / "AQSD_AI_Master_Decision.csv",
    OUT / "AQSD_Market_Data.csv",
    OUT / "AQSD_Live_Scanner.csv",
    OUT / "Live_Scanner.csv",
]

OUTPUT_CSV = OUT / "AQSD_Options_Buyer_Intelligence.csv"
OUTPUT_JSON = OUT / "AQSD_Options_Buyer_Intelligence.json"
PCR_HISTORY = OUT / "AQSD_PCR_History.csv"
WALL_HISTORY = OUT / "AQSD_Wall_History.csv"


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
    return default if not text or text.lower() in {"nan", "none", "null"} else text


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def read_csv(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def detect_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    mapping = {str(c).strip().lower(): c for c in frame.columns}
    return next((mapping[x.lower()] for x in candidates if x.lower() in mapping), None)


def latest_sources() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in SUMMARY_FILES:
        frame = read_csv(path if path.exists() else None)
        if not frame.empty:
            rows.append(frame.iloc[-1].to_dict())
    return rows


def pick(sources: list[dict[str, Any]], names: list[str], default: Any = None) -> Any:
    for source in sources:
        lowered = {str(k).strip().lower(): v for k, v in source.items()}
        for name in names:
            if name.lower() in lowered and safe_text(lowered[name.lower()]):
                return lowered[name.lower()]
    return default


def normalize_chain(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    strike = detect_column(frame, ["strike", "strike_price", "strikeprice"])
    option_type = detect_column(frame, ["option_type", "type", "right", "cp_type"])
    oi = detect_column(frame, ["open_interest", "oi", "openinterest"])
    change_oi = detect_column(frame, ["change_in_oi", "oi_change", "change_oi", "chg_oi"])
    volume = detect_column(frame, ["volume", "traded_volume", "vol"])
    iv = detect_column(frame, ["iv", "implied_volatility", "impliedvolatility"])
    if not strike or not option_type:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["strike"] = pd.to_numeric(frame[strike], errors="coerce")
    out["option_type"] = frame[option_type].astype(str).str.upper().str.strip().replace(
        {"CALL": "CE", "C": "CE", "PUT": "PE", "P": "PE"}
    )
    out["oi"] = pd.to_numeric(frame[oi], errors="coerce").fillna(0.0) if oi else 0.0
    out["change_oi"] = pd.to_numeric(frame[change_oi], errors="coerce").fillna(0.0) if change_oi else 0.0
    out["volume"] = pd.to_numeric(frame[volume], errors="coerce").fillna(0.0) if volume else 0.0
    out["iv"] = pd.to_numeric(frame[iv], errors="coerce").fillna(0.0) if iv else 0.0
    return out.dropna(subset=["strike"])[out["option_type"].isin(["CE", "PE"])].copy()


def calculate_pcr(chain: pd.DataFrame) -> dict[str, float]:
    if chain.empty:
        return {"oi_pcr": 0.0, "modified_pcr": 0.0, "volume_pcr": 0.0}
    calls = chain[chain.option_type == "CE"]
    puts = chain[chain.option_type == "PE"]
    call_oi, put_oi = calls.oi.sum(), puts.oi.sum()
    call_chg = calls.change_oi.clip(lower=0).sum()
    put_chg = puts.change_oi.clip(lower=0).sum()
    call_vol, put_vol = calls.volume.sum(), puts.volume.sum()
    oi_pcr = put_oi / call_oi if call_oi else 0.0
    chg_pcr = put_chg / call_chg if call_chg else 0.0
    vol_pcr = put_vol / call_vol if call_vol else 0.0
    modified = 0.50 * oi_pcr + 0.30 * chg_pcr + 0.20 * vol_pcr
    return {"oi_pcr": round(oi_pcr, 6), "modified_pcr": round(modified, 6), "volume_pcr": round(vol_pcr, 6)}


def append_history(path: Path, row: dict[str, Any]) -> pd.DataFrame:
    new = pd.DataFrame([row])
    if path.exists():
        try:
            old = pd.read_csv(path, low_memory=False)
            new = pd.concat([old, new], ignore_index=True)
        except Exception:
            pass
    new.to_csv(path, index=False, encoding="utf-8-sig")
    return new


def calculate_pcr_trend(history: pd.DataFrame) -> dict[str, Any]:
    if len(history) < 2:
        return {"pcr_trend": "INSUFFICIENT HISTORY", "pcr_slope": 0.0, "pcr_acceleration": 0.0, "pcr_interpretation": "COLLECT MORE SNAPSHOTS"}
    values = pd.to_numeric(history["modified_pcr"], errors="coerce").dropna().tail(6)
    if len(values) < 2:
        return {"pcr_trend": "INSUFFICIENT HISTORY", "pcr_slope": 0.0, "pcr_acceleration": 0.0, "pcr_interpretation": "COLLECT MORE SNAPSHOTS"}
    diffs = values.diff().dropna()
    slope = safe_float(diffs.mean())
    acceleration = safe_float(diffs.diff().dropna().mean()) if len(diffs) > 1 else 0.0
    current = safe_float(values.iloc[-1])
    trend = "RISING" if slope > 0.01 else "FALLING" if slope < -0.01 else "FLAT"
    if current < 0.85 and trend == "FALLING": interpretation = "BEARISH STRENGTHENING"
    elif current < 0.85 and trend == "RISING": interpretation = "BEARISH PRESSURE WEAKENING"
    elif current > 1.05 and trend == "RISING": interpretation = "BULLISH STRENGTHENING"
    elif current > 1.05 and trend == "FALLING": interpretation = "BULLISH PRESSURE WEAKENING"
    elif trend == "RISING": interpretation = "BULLISH MOMENTUM DEVELOPING"
    elif trend == "FALLING": interpretation = "BEARISH MOMENTUM DEVELOPING"
    else: interpretation = "SIDEWAYS / BALANCED"
    return {"pcr_trend": trend, "pcr_slope": round(slope, 6), "pcr_acceleration": round(acceleration, 6), "pcr_interpretation": interpretation}


def strike_of_max(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0.0
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.dropna().empty:
        return 0.0
    return safe_float(frame.loc[values.idxmax(), "strike"])


def calculate_walls(chain: pd.DataFrame) -> dict[str, float]:
    if chain.empty:
        return {"positional_call_wall": 0.0, "fresh_call_wall": 0.0, "positional_put_wall": 0.0, "fresh_put_wall": 0.0}
    calls = chain[chain.option_type == "CE"].copy()
    puts = chain[chain.option_type == "PE"].copy()
    calls["positive_change"] = calls.change_oi.clip(lower=0)
    puts["positive_change"] = puts.change_oi.clip(lower=0)
    return {
        "positional_call_wall": strike_of_max(calls, "oi"),
        "fresh_call_wall": strike_of_max(calls, "positive_change"),
        "positional_put_wall": strike_of_max(puts, "oi"),
        "fresh_put_wall": strike_of_max(puts, "positive_change"),
    }


def calculate_wall_migration(history: pd.DataFrame) -> dict[str, str]:
    if len(history) < 2:
        return {"call_wall_shift": "INSUFFICIENT HISTORY", "put_wall_shift": "INSUFFICIENT HISTORY", "wall_migration": "INSUFFICIENT HISTORY"}
    previous, current = history.iloc[-2], history.iloc[-1]
    call_shift = safe_float(current.fresh_call_wall) - safe_float(previous.fresh_call_wall)
    put_shift = safe_float(current.fresh_put_wall) - safe_float(previous.fresh_put_wall)
    label = lambda x: "UP" if x > 0 else "DOWN" if x < 0 else "STABLE"
    if call_shift > 0 and put_shift > 0: migration = "BULLISH UPWARD SHIFT"
    elif call_shift < 0 and put_shift < 0: migration = "BEARISH DOWNWARD SHIFT"
    elif call_shift < 0 and put_shift > 0: migration = "RANGE COMPRESSION"
    elif call_shift > 0 and put_shift < 0: migration = "RANGE EXPANSION"
    else: migration = "MIXED / STABLE"
    return {"call_wall_shift": label(call_shift), "put_wall_shift": label(put_shift), "wall_migration": migration}


def pivots(high: float, low: float, close: float) -> dict[str, float]:
    if min(high, low, close) <= 0:
        return {"pivot": 0.0, "r1": 0.0, "r2": 0.0, "s1": 0.0, "s2": 0.0}
    p = (high + low + close) / 3
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - low, 2),
        "r2": round(p + high - low, 2),
        "s1": round(2 * p - high, 2),
        "s2": round(p - high + low, 2),
    }


def market_structure(sources: list[dict[str, Any]]) -> str:
    sh1 = safe_float(pick(sources, ["swing_high_1", "previous_swing_high"], 0))
    sh2 = safe_float(pick(sources, ["swing_high_2", "latest_swing_high"], 0))
    sl1 = safe_float(pick(sources, ["swing_low_1", "previous_swing_low"], 0))
    sl2 = safe_float(pick(sources, ["swing_low_2", "latest_swing_low"], 0))
    if min(sh1, sh2, sl1, sl2) > 0:
        if sh2 > sh1 and sl2 > sl1: return "HH-HL"
        if sh2 < sh1 and sl2 < sl1: return "LH-LL"
    return "SIDEWAYS / MIXED"


def calculate_iv_move(spot: float, atm_iv: float, day_open: float) -> dict[str, float]:
    move_pct = atm_iv / math.sqrt(252) if atm_iv > 0 else 0.0
    move_pts = spot * move_pct / 100 if spot > 0 else 0.0
    actual = abs(spot - day_open) if day_open > 0 else 0.0
    captured = actual / move_pts * 100 if move_pts > 0 else 0.0
    return {
        "daily_iv_move_percent": round(move_pct, 4),
        "daily_iv_move_points": round(move_pts, 2),
        "expected_upper_range": round(spot + move_pts, 2),
        "expected_lower_range": round(spot - move_pts, 2),
        "actual_move_points": round(actual, 2),
        "move_captured_percent": round(captured, 2),
        "remaining_move_points": round(max(move_pts - actual, 0), 2),
    }


def final_signal(spot: float, atp: float, p: dict[str, float], yh: float, yl: float, structure: str, pcr_text: str, wall_text: str, iv: dict[str, float]) -> dict[str, Any]:
    bull = bear = 0.0
    reasons: list[str] = []
    if spot > atp > 0: bull += 20; reasons.append("Spot above ATP")
    elif 0 < spot < atp: bear += 20; reasons.append("Spot below ATP")
    if spot > p["pivot"] > 0: bull += 15; reasons.append("Spot above Pivot")
    elif 0 < spot < p["pivot"]: bear += 15; reasons.append("Spot below Pivot")
    if spot > yh > 0: bull += 20; reasons.append("Yesterday High breakout")
    elif 0 < spot < yl: bear += 20; reasons.append("Yesterday Low breakdown")
    if structure == "HH-HL": bull += 20; reasons.append("HH-HL structure")
    elif structure == "LH-LL": bear += 20; reasons.append("LH-LL structure")
    if "BULLISH" in pcr_text: bull += 15; reasons.append(pcr_text)
    elif "BEARISH" in pcr_text: bear += 15; reasons.append(pcr_text)
    if "BULLISH" in wall_text: bull += 10; reasons.append(wall_text)
    elif "BEARISH" in wall_text: bear += 10; reasons.append(wall_text)
    if iv["remaining_move_points"] > 0 and iv["move_captured_percent"] < 80:
        bull += 5; bear += 5; reasons.append("Meaningful IV move remains")
    if bull >= 60 and bull > bear: signal, direction, score = "BUY CALL", "BULLISH", bull
    elif bear >= 60 and bear > bull: signal, direction, score = "BUY PUT", "BEARISH", bear
    else: signal, direction, score = "WAIT", "SIDEWAYS", max(bull, bear)
    return {"final_signal": signal, "final_direction": direction, "options_buyer_score": round(score, 1), "bullish_score": round(bull, 1), "bearish_score": round(bear, 1), "signal_reasons": " | ".join(reasons)}


def run(underlying: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    chain = normalize_chain(read_csv(first_existing(OPTION_CHAIN_FILES)))
    sources = latest_sources()
    timestamp = datetime.now().isoformat(timespec="seconds")

    spot = safe_float(pick(sources, ["spot_price", "spot", "ltp", "current_price"], 0))
    yh = safe_float(pick(sources, ["previous_day_high", "yesterday_high", "prev_high", "previous_high"], 0))
    yl = safe_float(pick(sources, ["previous_day_low", "yesterday_low", "prev_low", "previous_low"], 0))
    prev_close = safe_float(pick(sources, ["previous_close", "prev_close", "yesterday_close", "close"], 0))
    day_open = safe_float(pick(sources, ["open", "session_open", "day_open"], prev_close))
    turnover = safe_float(pick(sources, ["total_turnover", "turnover", "traded_value"], 0))
    volume = safe_float(pick(sources, ["total_volume", "volume", "traded_volume"], 0))
    fallback_atp = safe_float(pick(sources, ["average_trade_price", "average_traded_price", "atp", "vwap"], spot))
    atp = turnover / volume if turnover > 0 and volume > 0 else fallback_atp

    pcr = calculate_pcr(chain)
    pcr_hist = append_history(PCR_HISTORY, {"timestamp": timestamp, "underlying": underlying, **pcr})
    pcr_info = calculate_pcr_trend(pcr_hist)

    walls = calculate_walls(chain)
    wall_hist = append_history(WALL_HISTORY, {"timestamp": timestamp, "underlying": underlying, **walls})
    wall_info = calculate_wall_migration(wall_hist)

    p = pivots(yh, yl, prev_close)
    structure = market_structure(sources)
    atm_iv = safe_float(pick(sources, ["atm_iv", "average_atm_iv", "implied_volatility", "iv"], 0))
    if atm_iv <= 0 and not chain.empty and spot > 0:
        nearest = chain.assign(distance=(chain.strike - spot).abs()).sort_values("distance").head(2)
        atm_iv = safe_float(nearest.iv.mean())
    iv = calculate_iv_move(spot, atm_iv, day_open)
    signal = final_signal(spot, atp, p, yh, yl, structure, pcr_info["pcr_interpretation"], wall_info["wall_migration"], iv)

    strongest_support = p["s1"] if structure == "HH-HL" else yl if structure.startswith("SIDEWAYS") else p["s1"]
    strongest_resistance = p["r1"] if structure == "LH-LL" else yh if structure.startswith("SIDEWAYS") else p["r1"]

    row = {
        "generated_at": timestamp,
        "underlying": underlying,
        "spot": round(spot, 2),
        "average_traded_price": round(atp, 2),
        "spot_minus_atp": round(spot - atp, 2),
        "yesterday_high": round(yh, 2),
        "yesterday_low": round(yl, 2),
        "previous_close": round(prev_close, 2),
        "spot_minus_yesterday_high": round(spot - yh, 2),
        "spot_minus_yesterday_low": round(spot - yl, 2),
        **p,
        "spot_minus_pivot": round(spot - p["pivot"], 2),
        "market_structure": structure,
        "strongest_support": strongest_support,
        "strongest_resistance": strongest_resistance,
        **pcr,
        **pcr_info,
        **walls,
        **wall_info,
        "atm_iv": round(atm_iv, 4),
        **iv,
        **signal,
    }

    pd.DataFrame([row]).to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_JSON.write_text(json.dumps(row, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("\nAQSD OPTIONS BUYER INTELLIGENCE")
    print("=" * 88)
    for label, value in [
        ("Spot", f"{spot:,.2f}"), ("ATP", f"{atp:,.2f}"),
        ("Yesterday High", f"{yh:,.2f}"), ("Yesterday Low", f"{yl:,.2f}"),
        ("Pivot", f"{p['pivot']:,.2f}"), ("Structure", structure),
        ("OI PCR", f"{pcr['oi_pcr']:.4f}"), ("Modified PCR", f"{pcr['modified_pcr']:.4f}"),
        ("Volume PCR", f"{pcr['volume_pcr']:.4f}"), ("PCR Trend", pcr_info["pcr_trend"]),
        ("PCR Interpretation", pcr_info["pcr_interpretation"]),
        ("Positional Call Wall", f"{walls['positional_call_wall']:,.0f}"),
        ("Fresh Call Wall", f"{walls['fresh_call_wall']:,.0f}"),
        ("Positional Put Wall", f"{walls['positional_put_wall']:,.0f}"),
        ("Fresh Put Wall", f"{walls['fresh_put_wall']:,.0f}"),
        ("Wall Migration", wall_info["wall_migration"]),
        ("ATM IV", f"{atm_iv:.2f}%"),
        ("Daily IV Move", f"{iv['daily_iv_move_percent']:.2f}% / {iv['daily_iv_move_points']:,.2f} pts"),
        ("Move Captured", f"{iv['move_captured_percent']:.2f}%"),
        ("Remaining Move", f"{iv['remaining_move_points']:,.2f} pts"),
        ("FINAL SIGNAL", signal["final_signal"]),
        ("BUYER SCORE", signal["options_buyer_score"]),
    ]:
        print(f"{label:<24}: {value}")
    print("=" * 88)
    print(f"CSV : {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


def status() -> None:
    print("\nAQSD OPTIONS BUYER INTELLIGENCE STATUS")
    print("=" * 78)
    print(f"Option Chain : {first_existing(OPTION_CHAIN_FILES) or 'MISSING'}")
    print(f"Summary Data : {first_existing(SUMMARY_FILES) or 'MISSING'}")
    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(description="AQSD Options Buyer Intelligence Engine")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--underlying", default="BANKNIFTY")
    args = parser.parse_args()
    if args.status:
        status()
    elif args.run:
        run(args.underlying.strip().upper())
    else:
        raise SystemExit("Use --status or --run --underlying BANKNIFTY")


if __name__ == "__main__":
    main()
