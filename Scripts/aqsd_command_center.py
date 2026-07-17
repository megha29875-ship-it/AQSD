"""
AQSD Command Center v1.0

Combines:
- Decision Engine
- Risk Engine
- Portfolio Engine
- AI Alert Engine

Outputs:
- Output/AQSD_Command_Center.csv
- Output/AQSD_Command_Center.json
"""

from pathlib import Path
import argparse
import json
from datetime import datetime

import pandas as pd


BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"

DECISION_FILE = OUT / "AQSD_Decision_Engine.csv"
RISK_FILE = OUT / "AQSD_Risk_Engine.csv"
PORTFOLIO_FILE = OUT / "AQSD_Portfolio_Summary.csv"
ALERT_FILE = OUT / "AQSD_AI_Alerts.csv"

CSV_OUTPUT = OUT / "AQSD_Command_Center.csv"
JSON_OUTPUT = OUT / "AQSD_Command_Center.json"


def read_latest(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        frame = pd.read_csv(path, low_memory=False)
    except Exception:
        return {}

    if frame.empty:
        return {}

    return frame.iloc[-1].to_dict()


def build_command_center() -> pd.DataFrame:
    decision = read_latest(DECISION_FILE)
    risk = read_latest(RISK_FILE)
    portfolio = read_latest(PORTFOLIO_FILE)

    alerts = []
    if ALERT_FILE.exists():
        try:
            alert_df = pd.read_csv(ALERT_FILE, low_memory=False)
            alerts = alert_df.to_dict(orient="records")
        except Exception:
            alerts = []

    priority_order = {
        "CRITICAL": 4,
        "HIGH": 3,
        "NORMAL": 2,
        "LOW": 1,
    }

    top_alert = {}

    if alerts:
        top_alert = sorted(
            alerts,
            key=lambda x: priority_order.get(
                str(x.get("priority", "")).upper(),
                0,
            ),
            reverse=True,
        )[0]

    row = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),

        "underlying": decision.get("underlying", ""),
        "spot_price": decision.get("spot_price", ""),
        "suggested_action": decision.get("suggested_action", ""),
        "trade_quality": decision.get("trade_quality", ""),
        "confidence_percent": decision.get("confidence_percent", ""),
        "market_regime": decision.get("market_regime", ""),

        "institutional_bull_score": decision.get(
            "institutional_bull_score",
            "",
        ),
        "institutional_bear_score": decision.get(
            "institutional_bear_score",
            "",
        ),

        "aggressive_entry": decision.get("aggressive_entry", ""),
        "conservative_entry": decision.get("conservative_entry", ""),
        "stop_loss": decision.get("stop_loss", ""),
        "target_1": decision.get("target_1", ""),
        "target_2": decision.get("target_2", ""),
        "target_3": decision.get("target_3", ""),
        "risk_reward": decision.get("risk_reward", ""),

        "suggested_quantity": risk.get("suggested_quantity", ""),
        "trade_approved": risk.get("trade_approved", ""),
        "max_risk_amount": risk.get("max_risk_amount", ""),

        "portfolio_status": portfolio.get("portfolio_status", ""),
        "portfolio_risk_score": portfolio.get(
            "portfolio_risk_score",
            "",
        ),
        "open_positions": portfolio.get("open_positions", ""),
        "total_exposure_percent": portfolio.get(
            "total_exposure_percent",
            "",
        ),
        "total_unrealised_pnl": portfolio.get(
            "total_unrealised_pnl",
            "",
        ),

        "top_alert_type": top_alert.get("type", ""),
        "top_alert_priority": top_alert.get("priority", ""),
        "top_alert_message": top_alert.get("message", ""),

        "reason_1": decision.get("reason_1", ""),
        "reason_2": decision.get("reason_2", ""),
        "reason_3": decision.get("reason_3", ""),

        "order_placement": "DISABLED",
    }

    return pd.DataFrame([row])


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    result = build_command_center()

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

    row = result.iloc[0]

    print("\nAQSD COMMAND CENTER")
    print("=" * 80)
    print(f"Underlying:            {row['underlying']}")
    print(f"Spot:                  {row['spot_price']}")
    print(f"Action:                {row['suggested_action']}")
    print(f"Trade Quality:         {row['trade_quality']}")
    print(f"Confidence:            {row['confidence_percent']}")
    print(f"Market Regime:         {row['market_regime']}")
    print("-" * 80)
    print(f"Entry:                 {row['aggressive_entry']}")
    print(f"Stop Loss:             {row['stop_loss']}")
    print(f"Target 1:              {row['target_1']}")
    print(f"Target 2:              {row['target_2']}")
    print(f"Target 3:              {row['target_3']}")
    print(f"Risk Reward:           {row['risk_reward']}")
    print("-" * 80)
    print(f"Suggested Quantity:    {row['suggested_quantity']}")
    print(f"Trade Approved:        {row['trade_approved']}")
    print(f"Portfolio Status:      {row['portfolio_status']}")
    print(f"Portfolio Risk Score:  {row['portfolio_risk_score']}")
    print(f"Top Alert:             {row['top_alert_message']}")
    print("=" * 80)
    print(f"CSV:                   {CSV_OUTPUT}")
    print(f"JSON:                  {JSON_OUTPUT}")
    print("Order Placement:       DISABLED")


def status() -> None:
    print("\nAQSD COMMAND CENTER STATUS")
    print("=" * 70)
    print(f"Decision Engine:   {'FOUND' if DECISION_FILE.exists() else 'MISSING'}")
    print(f"Risk Engine:       {'FOUND' if RISK_FILE.exists() else 'MISSING'}")
    print(f"Portfolio Engine:  {'FOUND' if PORTFOLIO_FILE.exists() else 'MISSING'}")
    print(f"AI Alert Engine:   {'FOUND' if ALERT_FILE.exists() else 'MISSING'}")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Command Center"
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")

    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.run:
        run()
        return

    raise SystemExit("Use --status or --run")


if __name__ == "__main__":
    main()
