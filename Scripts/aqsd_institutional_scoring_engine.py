"""
AQSD Institutional Scoring Engine v1.0

Combines AQSD decision, options, futures, smart-money, breadth and volatility
outputs into a unified institutional score.

Inputs are optional except Decision Engine:
- Output/AQSD_Decision_Engine.csv
- Output/AQSD_Options_Intelligence.csv
- Output/AQSD_FYERS_Futures_Analytics.csv
- Output/AQSD_FYERS_Smart_Money_Summary.csv
- Output/AQSD_Market_Breadth.csv
- Output/AQSD_Trade_Approval.csv

Outputs:
- Output/AQSD_Institutional_Scoring.csv
- Output/AQSD_Institutional_Scoring.json

Run:
python aqsd_institutional_scoring_engine.py --status
python aqsd_institutional_scoring_engine.py --run --underlying BANKNIFTY
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"

DECISION_FILE = OUT / "AQSD_Decision_Engine.csv"
OPTIONS_FILE = OUT / "AQSD_Options_Intelligence.csv"
FUTURES_FILE = OUT / "AQSD_FYERS_Futures_Analytics.csv"
SMART_FILE = OUT / "AQSD_FYERS_Smart_Money_Summary.csv"
BREADTH_FILE = OUT / "AQSD_Market_Breadth.csv"
APPROVAL_FILE = OUT / "AQSD_Trade_Approval.csv"

CSV_OUTPUT = OUT / "AQSD_Institutional_Scoring.csv"
JSON_OUTPUT = OUT / "AQSD_Institutional_Scoring.json"


def sf(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if pd.isna(number) else number
    except Exception:
        return default


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def read_latest(path: Path, underlying: str | None = None) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception:
        return {}

    if frame.empty:
        return {}

    if underlying and "underlying" in frame.columns:
        rows = frame[
            frame["underlying"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq(underlying.upper())
        ]
        if not rows.empty:
            return rows.iloc[-1].to_dict()

    return frame.iloc[-1].to_dict()


def text_score(value: str, bullish: list[str], bearish: list[str], base: float = 50.0) -> float:
    text = str(value or "").upper()
    score = base

    for item in bullish:
        if item in text:
            score += 15

    for item in bearish:
        if item in text:
            score -= 15

    return clamp(score)


def build_scores(underlying: str) -> pd.DataFrame:
    decision = read_latest(DECISION_FILE, underlying)
    options = read_latest(OPTIONS_FILE, underlying)
    futures = read_latest(FUTURES_FILE, underlying)
    smart = read_latest(SMART_FILE, underlying)
    breadth = read_latest(BREADTH_FILE, underlying)
    approval = read_latest(APPROVAL_FILE, underlying)

    if not decision:
        raise SystemExit(f"Missing or empty decision file: {DECISION_FILE}")

    bull = sf(decision.get("institutional_bull_score"), 50)
    bear = sf(decision.get("institutional_bear_score"), 50)
    confidence = sf(decision.get("confidence_percent"), 50)
    action = str(decision.get("suggested_action", "WAIT")).upper()
    regime = str(decision.get("market_regime", "")).upper()

    trend_score = 50.0
    if action == "BUY":
        trend_score += 15
    elif action == "SELL":
        trend_score -= 15

    if "TREND" in regime:
        trend_score += 10
    elif "RANGE" in regime:
        trend_score -= 5

    momentum_score = clamp((bull + (100 - bear)) / 2)

    modified_pcr = sf(options.get("modified_pcr"), 1.0)
    oi_pcr = sf(options.get("oi_pcr"), 1.0)
    pcr_trend = str(options.get("pcr_trend", "")).upper()

    options_score = 50.0
    if modified_pcr >= 1.15:
        options_score += 15
    elif modified_pcr <= 0.85:
        options_score -= 15

    if oi_pcr >= 1.20:
        options_score += 10
    elif oi_pcr <= 0.80:
        options_score -= 10

    if pcr_trend == "RISING":
        options_score += 10
    elif pcr_trend == "FALLING":
        options_score -= 10

    options_score = clamp(options_score)

    near_cycle = str(futures.get("near_cycle", "")).upper()
    rollover = str(
        futures.get(
            "rollover_interpretation",
            futures.get("rollover_signal", ""),
        )
    ).upper()
    oi_migration = str(futures.get("oi_migration", "")).upper()

    futures_score = 50.0
    futures_score += text_score(
        near_cycle,
        ["LONG BUILDUP", "SHORT COVERING"],
        ["SHORT BUILDUP", "LONG UNWINDING"],
        50,
    ) - 50
    futures_score += text_score(
        rollover,
        ["BULLISH"],
        ["BEARISH", "SHORT BUILDUP"],
        50,
    ) - 50
    futures_score += text_score(
        oi_migration,
        ["BULLISH"],
        ["BEARISH", "SHORT"],
        50,
    ) - 50
    futures_score = clamp(futures_score)

    smart_score_raw = sf(smart.get("total_smart_money_score"), 0)
    smart_bias = str(smart.get("smart_money_bias", "")).upper()
    smart_money_score = clamp(50 + smart_score_raw * 5)
    if "BULL" in smart_bias:
        smart_money_score = clamp(smart_money_score + 15)
    elif "BEAR" in smart_bias:
        smart_money_score = clamp(smart_money_score - 15)

    liquidity_score = 50.0
    if futures:
        failed = sf(futures.get("failed_requests"), 0)
        liquidity_score -= min(30, failed * 5)
        total_oi = sf(futures.get("total_open_interest"), 0)
        if total_oi > 0:
            liquidity_score += 20
    liquidity_score = clamp(liquidity_score)

    iv_regime = str(options.get("iv_regime", "")).upper()
    volatility_score = 50.0
    if "FAIR" in iv_regime:
        volatility_score += 10
    elif "CHEAP" in iv_regime:
        volatility_score += 15
    elif "EXPENSIVE" in iv_regime:
        volatility_score -= 15
    elif "NO IV DATA" in iv_regime:
        volatility_score -= 10
    volatility_score = clamp(volatility_score)

    breadth_score = sf(
        breadth.get(
            "market_breadth_score",
            breadth.get("breadth_score", 50),
        ),
        50,
    )
    breadth_score = clamp(breadth_score)

    institutional_score = (
        trend_score * 0.18
        + momentum_score * 0.14
        + options_score * 0.18
        + futures_score * 0.18
        + smart_money_score * 0.14
        + liquidity_score * 0.08
        + volatility_score * 0.05
        + breadth_score * 0.05
    )

    score_spread = abs(bull - bear)
    conviction = clamp(
        confidence * 0.50
        + score_spread * 1.20
        + abs(institutional_score - 50) * 0.60
    )

    if action == "SELL":
        directional_score = 100 - institutional_score
    elif action == "BUY":
        directional_score = institutional_score
    else:
        directional_score = 50

    approval_status = str(approval.get("trade_approved", "")).upper()
    if approval_status == "NO":
        conviction = min(conviction, 49)

    if conviction >= 80:
        confidence_label = "VERY HIGH"
    elif conviction >= 70:
        confidence_label = "HIGH"
    elif conviction >= 55:
        confidence_label = "MEDIUM"
    else:
        confidence_label = "LOW"

    row = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "underlying": underlying.upper(),
        "action": action,
        "trend_score": round(clamp(trend_score), 1),
        "momentum_score": round(clamp(momentum_score), 1),
        "options_score": round(options_score, 1),
        "futures_score": round(futures_score, 1),
        "smart_money_score": round(smart_money_score, 1),
        "liquidity_score": round(liquidity_score, 1),
        "volatility_score": round(volatility_score, 1),
        "market_breadth_score": round(breadth_score, 1),
        "overall_institutional_score": round(clamp(institutional_score), 1),
        "directional_score": round(clamp(directional_score), 1),
        "trade_conviction_percent": round(conviction, 1),
        "ai_confidence_percent": round((confidence + conviction) / 2, 1),
        "confidence_label": confidence_label,
        "trade_approved": approval.get("trade_approved", ""),
        "order_placement": "DISABLED",
    }

    return pd.DataFrame([row])


def save(result: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    result.to_csv(
        CSV_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    JSON_OUTPUT.write_text(
        json.dumps(
            result.to_dict(orient="records")[0],
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def show(result: pd.DataFrame) -> None:
    row = result.iloc[0]

    print("\nAQSD INSTITUTIONAL SCORING ENGINE")
    print("=" * 78)
    print(f"Underlying:              {row['underlying']}")
    print(f"Action:                  {row['action']}")
    print(f"Trend Score:             {row['trend_score']}")
    print(f"Momentum Score:          {row['momentum_score']}")
    print(f"Options Score:           {row['options_score']}")
    print(f"Futures Score:           {row['futures_score']}")
    print(f"Smart Money Score:       {row['smart_money_score']}")
    print(f"Liquidity Score:         {row['liquidity_score']}")
    print(f"Volatility Score:        {row['volatility_score']}")
    print(f"Market Breadth Score:    {row['market_breadth_score']}")
    print("-" * 78)
    print(f"Institutional Score:     {row['overall_institutional_score']}")
    print(f"Directional Score:       {row['directional_score']}")
    print(f"Trade Conviction:        {row['trade_conviction_percent']}%")
    print(f"AI Confidence:           {row['ai_confidence_percent']}%")
    print(f"Confidence Label:        {row['confidence_label']}")
    print("=" * 78)
    print(f"CSV:                     {CSV_OUTPUT}")
    print(f"JSON:                    {JSON_OUTPUT}")
    print("Order Placement:         DISABLED")


def status() -> None:
    print("\nAQSD INSTITUTIONAL SCORING STATUS")
    print("=" * 72)

    for name, path in [
        ("Decision Engine", DECISION_FILE),
        ("Options Intelligence", OPTIONS_FILE),
        ("Futures Analytics", FUTURES_FILE),
        ("Smart Money", SMART_FILE),
        ("Market Breadth", BREADTH_FILE),
        ("Trade Approval", APPROVAL_FILE),
    ]:
        print(f"{name:<24} {'FOUND' if path.exists() else 'MISSING / OPTIONAL'}")

    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Institutional Scoring Engine"
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--underlying", default="BANKNIFTY")
    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.run:
        result = build_scores(args.underlying)
        save(result)
        show(result)
        return

    raise SystemExit(
        "Use --status or --run --underlying BANKNIFTY"
    )


if __name__ == "__main__":
    main()
