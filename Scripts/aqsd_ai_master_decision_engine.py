"""
AQSD AI Master Decision Engine v1.0

Purpose
-------
Combines the latest outputs from:
- Decision Engine
- Trade Approval Engine
- Institutional Scoring Engine
- Risk Engine
- Market Breadth Engine
- Options Intelligence
- Futures Analytics
- Smart Money Engine

Produces one final institutional verdict:
BUY / SELL / WAIT / REJECT

Outputs
-------
Output/AQSD_AI_Master_Decision.csv
Output/AQSD_AI_Master_Decision.json
Output/AQSD_AI_Master_Decision_History.csv

Examples
--------
python aqsd_ai_master_decision_engine.py --status
python aqsd_ai_master_decision_engine.py --run --underlying BANKNIFTY
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
APPROVAL_FILE = OUT / "AQSD_Trade_Approval.csv"
SCORING_FILE = OUT / "AQSD_Institutional_Scoring.csv"
RISK_FILE = OUT / "AQSD_Risk_Engine.csv"
BREADTH_FILE = OUT / "AQSD_Market_Breadth.csv"
OPTIONS_FILE = OUT / "AQSD_Options_Intelligence.csv"
FUTURES_FILE = OUT / "AQSD_FYERS_Futures_Analytics.csv"
SMART_FILE = OUT / "AQSD_FYERS_Smart_Money_Summary.csv"

CSV_OUTPUT = OUT / "AQSD_AI_Master_Decision.csv"
JSON_OUTPUT = OUT / "AQSD_AI_Master_Decision.json"
HISTORY_OUTPUT = OUT / "AQSD_AI_Master_Decision_History.csv"


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
            .eq(underlying.strip().upper())
        ]
        if not rows.empty:
            return rows.iloc[-1].to_dict()

    return frame.iloc[-1].to_dict()


def text_contains(value: Any, words: list[str]) -> bool:
    text = str(value or "").upper()
    return any(word in text for word in words)


def build_master_decision(underlying: str) -> pd.DataFrame:
    decision = read_latest(DECISION_FILE, underlying)
    approval = read_latest(APPROVAL_FILE, underlying)
    scoring = read_latest(SCORING_FILE, underlying)
    risk = read_latest(RISK_FILE, underlying)
    breadth = read_latest(BREADTH_FILE)
    options = read_latest(OPTIONS_FILE, underlying)
    futures = read_latest(FUTURES_FILE, underlying)
    smart = read_latest(SMART_FILE, underlying)

    if not decision:
        raise SystemExit(f"Missing or empty decision file: {DECISION_FILE}")

    base_action = str(
        decision.get("suggested_action", "WAIT")
    ).strip().upper()

    trade_quality = str(
        decision.get("trade_quality", "")
    ).strip().upper()

    decision_confidence = sf(
        decision.get("confidence_percent"),
        50,
    )

    bull_score = sf(
        decision.get("institutional_bull_score"),
        50,
    )

    bear_score = sf(
        decision.get("institutional_bear_score"),
        50,
    )

    risk_reward = sf(
        decision.get("risk_reward"),
        0,
    )

    institutional_score = sf(
        scoring.get("overall_institutional_score"),
        50,
    )

    directional_score = sf(
        scoring.get("directional_score"),
        50,
    )

    conviction = sf(
        scoring.get("trade_conviction_percent"),
        50,
    )

    scoring_ai_confidence = sf(
        scoring.get("ai_confidence_percent"),
        50,
    )

    breadth_score = sf(
        breadth.get("market_breadth_score"),
        50,
    )

    breadth_regime = str(
        breadth.get("breadth_regime", "")
    ).upper()

    options_score = sf(
        scoring.get("options_score"),
        50,
    )

    futures_score = sf(
        scoring.get("futures_score"),
        50,
    )

    smart_money_score = sf(
        scoring.get("smart_money_score"),
        50,
    )

    volatility_score = sf(
        scoring.get("volatility_score"),
        50,
    )

    liquidity_score = sf(
        scoring.get("liquidity_score"),
        50,
    )

    approval_status = str(
        approval.get("trade_approved", "")
    ).strip().upper()

    risk_approval = str(
        risk.get("trade_approved", "")
    ).strip().upper()

    score_spread = abs(bull_score - bear_score)

    reasons: list[str] = []

    if base_action not in {"BUY", "SELL"}:
        reasons.append(
            f"Base Decision Engine action is {base_action or 'EMPTY'}"
        )

    if approval_status == "NO":
        reasons.append(
            "Trade Approval Engine rejected the trade"
        )

    if risk_approval in {"NO", "REJECTED", "FALSE"}:
        reasons.append(
            "Risk Engine rejected the trade"
        )

    if decision_confidence < 70:
        reasons.append(
            f"Decision confidence is only {decision_confidence:.1f}%"
        )

    if conviction < 60:
        reasons.append(
            f"Trade conviction is only {conviction:.1f}%"
        )

    if scoring_ai_confidence < 60:
        reasons.append(
            f"AI confidence is only {scoring_ai_confidence:.1f}%"
        )

    if risk_reward < 1.50:
        reasons.append(
            f"Risk/Reward {risk_reward:.2f} is below 1.50"
        )

    if trade_quality not in {"A+", "A", "B"}:
        reasons.append(
            f"Trade quality {trade_quality or 'EMPTY'} is below institutional grade"
        )

    if score_spread < 15:
        reasons.append(
            f"Institutional score spread {score_spread:.1f} is weak"
        )

    if base_action == "BUY" and breadth_score < 45:
        reasons.append(
            "Market breadth does not support BUY"
        )

    if base_action == "SELL" and breadth_score > 55:
        reasons.append(
            "Market breadth does not support SELL"
        )

    if base_action == "BUY" and directional_score < 55:
        reasons.append(
            "Directional score does not support BUY"
        )

    if base_action == "SELL" and directional_score < 55:
        reasons.append(
            "Directional score does not support SELL"
        )

    weighted_confidence = (
        decision_confidence * 0.30
        + conviction * 0.25
        + scoring_ai_confidence * 0.20
        + directional_score * 0.15
        + liquidity_score * 0.05
        + volatility_score * 0.05
    )

    weighted_confidence = clamp(weighted_confidence)

    probability_success = clamp(
        weighted_confidence
        + max(0, risk_reward - 1.5) * 5
        + max(0, score_spread - 15) * 0.4
    )

    probability_failure = clamp(
        100 - probability_success
    )

    if reasons:
        final_verdict = "REJECT"
    elif base_action in {"BUY", "SELL"}:
        final_verdict = base_action
    else:
        final_verdict = "WAIT"

    if final_verdict == "REJECT":
        final_confidence = min(
            weighted_confidence,
            49,
        )
    else:
        final_confidence = weighted_confidence

    if final_confidence >= 80:
        confidence_label = "VERY HIGH"
    elif final_confidence >= 70:
        confidence_label = "HIGH"
    elif final_confidence >= 60:
        confidence_label = "MEDIUM"
    else:
        confidence_label = "LOW"

    risk_grade = "LOW"

    if risk_reward < 1.0:
        risk_grade = "VERY HIGH"
    elif risk_reward < 1.5:
        risk_grade = "HIGH"
    elif decision_confidence < 70:
        risk_grade = "MODERATE"
    elif final_confidence >= 75:
        risk_grade = "LOW"
    else:
        risk_grade = "MODERATE"

    if final_verdict == "REJECT":
        ai_explanation = (
            "Trade rejected because institutional quality filters were not met."
        )
    elif final_verdict == "BUY":
        ai_explanation = (
            "BUY approved because price, derivatives, breadth and scoring are sufficiently aligned."
        )
    elif final_verdict == "SELL":
        ai_explanation = (
            "SELL approved because price, derivatives, breadth and scoring are sufficiently aligned."
        )
    else:
        ai_explanation = (
            "WAIT because the market does not provide a sufficiently clear institutional edge."
        )

    row = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "underlying": underlying.strip().upper(),
        "spot_price": decision.get("spot_price", ""),
        "base_action": base_action,
        "final_verdict": final_verdict,
        "trade_quality": trade_quality,
        "decision_confidence_percent": round(
            decision_confidence,
            1,
        ),
        "trade_conviction_percent": round(
            conviction,
            1,
        ),
        "scoring_ai_confidence_percent": round(
            scoring_ai_confidence,
            1,
        ),
        "final_confidence_percent": round(
            final_confidence,
            1,
        ),
        "confidence_label": confidence_label,
        "probability_success_percent": round(
            probability_success,
            1,
        ),
        "probability_failure_percent": round(
            probability_failure,
            1,
        ),
        "risk_grade": risk_grade,
        "risk_reward": round(risk_reward, 2),
        "institutional_bull_score": round(
            bull_score,
            1,
        ),
        "institutional_bear_score": round(
            bear_score,
            1,
        ),
        "institutional_score": round(
            institutional_score,
            1,
        ),
        "directional_score": round(
            directional_score,
            1,
        ),
        "options_score": round(options_score, 1),
        "futures_score": round(futures_score, 1),
        "smart_money_score": round(
            smart_money_score,
            1,
        ),
        "market_breadth_score": round(
            breadth_score,
            1,
        ),
        "breadth_regime": breadth_regime,
        "liquidity_score": round(
            liquidity_score,
            1,
        ),
        "volatility_score": round(
            volatility_score,
            1,
        ),
        "trade_approval_engine": approval_status,
        "risk_engine_approval": risk_approval,
        "ai_explanation": ai_explanation,
        "reason_1": reasons[0] if len(reasons) > 0 else "",
        "reason_2": reasons[1] if len(reasons) > 1 else "",
        "reason_3": reasons[2] if len(reasons) > 2 else "",
        "reason_4": reasons[3] if len(reasons) > 3 else "",
        "reason_5": reasons[4] if len(reasons) > 4 else "",
        "reason_6": reasons[5] if len(reasons) > 5 else "",
        "order_placement": "DISABLED",
    }

    return pd.DataFrame([row])


def save_outputs(result: pd.DataFrame) -> None:
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

    if HISTORY_OUTPUT.exists():
        history = pd.read_csv(
            HISTORY_OUTPUT,
            low_memory=False,
        )
        history = pd.concat(
            [history, result],
            ignore_index=True,
        )
    else:
        history = result.copy()

    history.to_csv(
        HISTORY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )


def show(result: pd.DataFrame) -> None:
    row = result.iloc[0]

    print("\nAQSD AI MASTER DECISION ENGINE")
    print("=" * 84)
    print(f"Underlying:             {row['underlying']}")
    print(f"Spot:                   {row['spot_price']}")
    print(f"Base Action:            {row['base_action']}")
    print(f"Final Verdict:          {row['final_verdict']}")
    print(f"Trade Quality:          {row['trade_quality']}")
    print(f"Final Confidence:       {row['final_confidence_percent']}%")
    print(f"Confidence Label:       {row['confidence_label']}")
    print(f"Probability Success:    {row['probability_success_percent']}%")
    print(f"Probability Failure:    {row['probability_failure_percent']}%")
    print(f"Risk Grade:             {row['risk_grade']}")
    print(f"Risk/Reward:            {row['risk_reward']}")
    print("-" * 84)
    print(f"Institutional Score:    {row['institutional_score']}")
    print(f"Directional Score:      {row['directional_score']}")
    print(f"Options Score:          {row['options_score']}")
    print(f"Futures Score:          {row['futures_score']}")
    print(f"Smart Money Score:      {row['smart_money_score']}")
    print(f"Market Breadth Score:   {row['market_breadth_score']}")
    print("-" * 84)
    print(f"AI Explanation:         {row['ai_explanation']}")

    for index in range(1, 7):
        reason = row.get(
            f"reason_{index}",
            "",
        )
        if isinstance(reason, str) and reason.strip():
            print(f"Reason {index}:              {reason}")

    print("=" * 84)
    print(f"CSV:                    {CSV_OUTPUT}")
    print(f"JSON:                   {JSON_OUTPUT}")
    print(f"History:                {HISTORY_OUTPUT}")
    print("Order Placement:        DISABLED")


def status() -> None:
    print("\nAQSD AI MASTER DECISION STATUS")
    print("=" * 78)

    for name, path, required in [
        ("Decision Engine", DECISION_FILE, True),
        ("Trade Approval", APPROVAL_FILE, True),
        ("Institutional Scoring", SCORING_FILE, True),
        ("Risk Engine", RISK_FILE, False),
        ("Market Breadth", BREADTH_FILE, False),
        ("Options Intelligence", OPTIONS_FILE, False),
        ("Futures Analytics", FUTURES_FILE, False),
        ("Smart Money", SMART_FILE, False),
    ]:
        state = "FOUND" if path.exists() else "MISSING"
        label = "REQUIRED" if required else "OPTIONAL"
        print(f"{name:<26} {state:<10} {label}")

    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD AI Master Decision Engine"
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--underlying",
        default="BANKNIFTY",
    )

    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.run:
        result = build_master_decision(
            args.underlying
        )
        save_outputs(result)
        show(result)
        return

    raise SystemExit(
        "Use --status or --run --underlying BANKNIFTY"
    )


if __name__ == "__main__":
    main()
