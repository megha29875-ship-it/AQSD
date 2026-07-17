"""
AQSD Professional
Module: Portfolio Risk Engine
Version: 1.0

Purpose
-------
Builds a consolidated portfolio view from AQSD positions and the latest
Decision/Risk Engine outputs.

Inputs
------
Data/AQSD_Open_Positions.csv                 optional; auto-created template
Output/AQSD_Decision_Engine.csv              optional
Output/AQSD_Risk_Engine.csv                  optional
Data/AQSD_Risk_Config.json                   optional

Outputs
-------
Output/AQSD_Portfolio_Engine.csv
Output/AQSD_Portfolio_Summary.csv
Output/AQSD_Portfolio_Heatmap.csv
Output/AQSD_Portfolio_Engine.json

Examples
--------
python aqsd_portfolio_engine.py --setup
python aqsd_portfolio_engine.py --status
python aqsd_portfolio_engine.py --run
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"

POSITIONS_FILE = DATA_DIR / "AQSD_Open_Positions.csv"
CONFIG_FILE = DATA_DIR / "AQSD_Risk_Config.json"
DECISION_FILE = OUTPUT_DIR / "AQSD_Decision_Engine.csv"
RISK_FILE = OUTPUT_DIR / "AQSD_Risk_Engine.csv"

DETAIL_OUTPUT = OUTPUT_DIR / "AQSD_Portfolio_Engine.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "AQSD_Portfolio_Summary.csv"
HEATMAP_OUTPUT = OUTPUT_DIR / "AQSD_Portfolio_Heatmap.csv"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_Portfolio_Engine.json"


DEFAULT_CONFIG = {
    "capital": 1000000,
    "max_risk_per_trade_percent": 1.0,
    "max_daily_loss_percent": 3.0,
    "max_open_positions": 5,
    "max_total_exposure_percent": 100.0,
    "max_sector_exposure_percent": 30.0,
}


POSITION_COLUMNS = [
    "symbol",
    "underlying",
    "sector",
    "instrument_type",
    "direction",
    "quantity",
    "lot_size",
    "entry_price",
    "current_price",
    "stop_loss",
    "target_price",
    "margin_used",
    "opened_at",
    "status",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if pd.isna(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def setup_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2),
            encoding="utf-8",
        )

    if not POSITIONS_FILE.exists():
        template = pd.DataFrame(
            [
                {
                    "symbol": "BANKNIFTY",
                    "underlying": "BANKNIFTY",
                    "sector": "INDEX",
                    "instrument_type": "FUTURE",
                    "direction": "LONG",
                    "quantity": 0,
                    "lot_size": 1,
                    "entry_price": 0,
                    "current_price": 0,
                    "stop_loss": 0,
                    "target_price": 0,
                    "margin_used": 0,
                    "opened_at": "",
                    "status": "CLOSED",
                }
            ],
            columns=POSITION_COLUMNS,
        )
        template.to_csv(
            POSITIONS_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    print(f"Created/verified: {POSITIONS_FILE}")
    print(f"Created/verified: {CONFIG_FILE}")


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        setup_files()

    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}

    config = DEFAULT_CONFIG.copy()
    config.update(loaded)
    return config


def load_positions() -> pd.DataFrame:
    if not POSITIONS_FILE.exists():
        setup_files()

    try:
        frame = pd.read_csv(POSITIONS_FILE, low_memory=False)
    except Exception as exc:
        raise SystemExit(f"Unable to read {POSITIONS_FILE}: {exc}") from exc

    for column in POSITION_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""

    frame = frame[POSITION_COLUMNS].copy()

    frame["status"] = (
        frame["status"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    frame = frame[frame["status"].eq("OPEN")].copy()

    return frame


def latest_signal_map() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    if DECISION_FILE.exists():
        decision = pd.read_csv(DECISION_FILE, low_memory=False)

        if "underlying" in decision.columns:
            for _, row in decision.iterrows():
                key = str(row.get("underlying", "")).strip().upper()
                if key:
                    result.setdefault(key, {})
                    result[key].update(
                        {
                            "decision_action": row.get("suggested_action", ""),
                            "decision_confidence": row.get(
                                "confidence_percent",
                                0,
                            ),
                            "trade_quality": row.get("trade_quality", ""),
                            "market_regime": row.get("market_regime", ""),
                        }
                    )

    if RISK_FILE.exists():
        risk = pd.read_csv(RISK_FILE, low_memory=False)

        if "underlying" in risk.columns:
            for _, row in risk.iterrows():
                key = str(row.get("underlying", "")).strip().upper()
                if key:
                    result.setdefault(key, {})
                    result[key].update(
                        {
                            "risk_action": row.get("action", ""),
                            "suggested_quantity": row.get(
                                "suggested_quantity",
                                0,
                            ),
                            "trade_approved": row.get(
                                "trade_approved",
                                "",
                            ),
                        }
                    )

    return result


def calculate_positions(
    positions: pd.DataFrame,
    capital: float,
) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(
            columns=[
                *POSITION_COLUMNS,
                "units",
                "market_value",
                "unrealised_pnl",
                "risk_amount",
                "reward_amount",
                "risk_reward",
                "exposure_percent",
                "risk_percent_of_capital",
                "signal_alignment",
                "position_risk_score",
            ]
        )

    signals = latest_signal_map()
    rows: list[dict[str, Any]] = []

    for _, row in positions.iterrows():
        direction = str(row.get("direction", "")).strip().upper()
        underlying = str(row.get("underlying", "")).strip().upper()

        quantity = safe_float(row.get("quantity"))
        lot_size = max(safe_float(row.get("lot_size"), 1.0), 1.0)
        units = quantity * lot_size

        entry = safe_float(row.get("entry_price"))
        current = safe_float(row.get("current_price"))
        stop = safe_float(row.get("stop_loss"))
        target = safe_float(row.get("target_price"))
        margin_used = safe_float(row.get("margin_used"))

        multiplier = 1 if direction == "LONG" else -1

        market_value = abs(current * units)
        unrealised_pnl = (current - entry) * units * multiplier
        risk_amount = abs(entry - stop) * units
        reward_amount = abs(target - entry) * units

        risk_reward = (
            reward_amount / risk_amount
            if risk_amount > 0
            else 0.0
        )

        exposure_base = margin_used if margin_used > 0 else market_value
        exposure_percent = (
            exposure_base / capital * 100
            if capital > 0
            else 0.0
        )

        risk_percent = (
            risk_amount / capital * 100
            if capital > 0
            else 0.0
        )

        signal = signals.get(underlying, {})
        action = str(signal.get("decision_action", "")).upper()

        alignment = "UNKNOWN"

        if direction == "LONG" and action == "BUY":
            alignment = "ALIGNED"
        elif direction == "SHORT" and action == "SELL":
            alignment = "ALIGNED"
        elif action in {"WAIT", "AVOID", ""}:
            alignment = "NEUTRAL"
        else:
            alignment = "CONFLICT"

        risk_score = 25.0

        if risk_percent > 1:
            risk_score += min(30, (risk_percent - 1) * 15)

        if exposure_percent > 20:
            risk_score += min(20, (exposure_percent - 20) * 1.5)

        if risk_reward < 1:
            risk_score += 20
        elif risk_reward < 1.5:
            risk_score += 10

        if alignment == "CONFLICT":
            risk_score += 20
        elif alignment == "ALIGNED":
            risk_score -= 10

        risk_score = max(0, min(100, risk_score))

        output = row.to_dict()
        output.update(
            {
                "units": round(units, 2),
                "market_value": round(market_value, 2),
                "unrealised_pnl": round(unrealised_pnl, 2),
                "risk_amount": round(risk_amount, 2),
                "reward_amount": round(reward_amount, 2),
                "risk_reward": round(risk_reward, 2),
                "exposure_percent": round(exposure_percent, 2),
                "risk_percent_of_capital": round(risk_percent, 2),
                "decision_action": signal.get("decision_action", ""),
                "decision_confidence": signal.get(
                    "decision_confidence",
                    0,
                ),
                "trade_quality": signal.get("trade_quality", ""),
                "signal_alignment": alignment,
                "position_risk_score": round(risk_score, 1),
            }
        )
        rows.append(output)

    return pd.DataFrame(rows)


def build_summary(
    detail: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    capital = safe_float(config.get("capital"), 0)

    if detail.empty:
        values = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "capital": capital,
            "open_positions": 0,
            "total_market_value": 0,
            "total_margin_used": 0,
            "total_exposure_percent": 0,
            "total_unrealised_pnl": 0,
            "total_risk_amount": 0,
            "total_risk_percent": 0,
            "average_risk_reward": 0,
            "aligned_positions": 0,
            "conflicting_positions": 0,
            "portfolio_risk_score": 0,
            "portfolio_status": "NO OPEN POSITIONS",
        }
        return pd.DataFrame([values])

    total_market_value = detail["market_value"].sum()
    total_margin = pd.to_numeric(
        detail["margin_used"],
        errors="coerce",
    ).fillna(0).sum()

    exposure_value = total_margin if total_margin > 0 else total_market_value

    total_exposure_percent = (
        exposure_value / capital * 100
        if capital > 0
        else 0
    )

    total_pnl = detail["unrealised_pnl"].sum()
    total_risk = detail["risk_amount"].sum()

    total_risk_percent = (
        total_risk / capital * 100
        if capital > 0
        else 0
    )

    average_rr = detail["risk_reward"].mean()
    average_position_risk = detail["position_risk_score"].mean()

    max_exposure = safe_float(
        config.get("max_total_exposure_percent"),
        100,
    )

    max_positions = int(
        safe_float(
            config.get("max_open_positions"),
            5,
        )
    )

    portfolio_risk_score = average_position_risk

    if total_exposure_percent > max_exposure:
        portfolio_risk_score += 20

    if len(detail) > max_positions:
        portfolio_risk_score += 15

    if total_risk_percent > safe_float(
        config.get("max_daily_loss_percent"),
        3,
    ):
        portfolio_risk_score += 20

    portfolio_risk_score = max(
        0,
        min(
            100,
            portfolio_risk_score,
        ),
    )

    if portfolio_risk_score >= 75:
        status = "CRITICAL"
    elif portfolio_risk_score >= 55:
        status = "HIGH RISK"
    elif portfolio_risk_score >= 35:
        status = "MODERATE"
    else:
        status = "CONTROLLED"

    values = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "capital": round(capital, 2),
        "open_positions": len(detail),
        "total_market_value": round(total_market_value, 2),
        "total_margin_used": round(total_margin, 2),
        "total_exposure_percent": round(total_exposure_percent, 2),
        "total_unrealised_pnl": round(total_pnl, 2),
        "total_risk_amount": round(total_risk, 2),
        "total_risk_percent": round(total_risk_percent, 2),
        "average_risk_reward": round(average_rr, 2),
        "aligned_positions": int(
            detail["signal_alignment"].eq("ALIGNED").sum()
        ),
        "conflicting_positions": int(
            detail["signal_alignment"].eq("CONFLICT").sum()
        ),
        "portfolio_risk_score": round(portfolio_risk_score, 1),
        "portfolio_status": status,
    }

    return pd.DataFrame([values])


def build_heatmap(
    detail: pd.DataFrame,
    capital: float,
) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(
            columns=[
                "sector",
                "positions",
                "market_value",
                "margin_used",
                "unrealised_pnl",
                "risk_amount",
                "exposure_percent",
                "average_position_risk_score",
            ]
        )

    frame = detail.copy()
    frame["sector"] = (
        frame["sector"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
        .replace("", "UNKNOWN")
    )

    grouped = (
        frame.groupby("sector", as_index=False)
        .agg(
            positions=("symbol", "count"),
            market_value=("market_value", "sum"),
            margin_used=("margin_used", "sum"),
            unrealised_pnl=("unrealised_pnl", "sum"),
            risk_amount=("risk_amount", "sum"),
            average_position_risk_score=(
                "position_risk_score",
                "mean",
            ),
        )
    )

    grouped["exposure_value"] = grouped.apply(
        lambda row: (
            row["margin_used"]
            if row["margin_used"] > 0
            else row["market_value"]
        ),
        axis=1,
    )

    grouped["exposure_percent"] = (
        grouped["exposure_value"] / capital * 100
        if capital > 0
        else 0
    )

    grouped = grouped.drop(columns=["exposure_value"])

    numeric_columns = [
        "market_value",
        "margin_used",
        "unrealised_pnl",
        "risk_amount",
        "exposure_percent",
        "average_position_risk_score",
    ]

    grouped[numeric_columns] = grouped[numeric_columns].round(2)

    return grouped.sort_values(
        "exposure_percent",
        ascending=False,
    )


def run_engine() -> None:
    setup_files()
    config = load_config()
    capital = safe_float(config.get("capital"), 0)

    positions = load_positions()
    detail = calculate_positions(positions, capital)
    summary = build_summary(detail, config)
    heatmap = build_heatmap(detail, capital)

    detail.to_csv(
        DETAIL_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    heatmap.to_csv(
        HEATMAP_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "summary": summary.to_dict(orient="records"),
                "positions": detail.to_dict(orient="records"),
                "heatmap": heatmap.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    row = summary.iloc[0]

    print("\nAQSD PORTFOLIO RISK ENGINE")
    print("=" * 76)
    print(f"Open Positions:          {row['open_positions']}")
    print(f"Portfolio Status:        {row['portfolio_status']}")
    print(f"Portfolio Risk Score:    {row['portfolio_risk_score']}")
    print(f"Total Exposure:          {row['total_exposure_percent']}%")
    print(f"Total Unrealised P/L:    {row['total_unrealised_pnl']}")
    print(f"Total Risk:              {row['total_risk_amount']}")
    print(f"Aligned Positions:       {row['aligned_positions']}")
    print(f"Conflicting Positions:   {row['conflicting_positions']}")
    print("=" * 76)
    print(f"Details:                 {DETAIL_OUTPUT}")
    print(f"Summary:                 {SUMMARY_OUTPUT}")
    print(f"Heatmap:                 {HEATMAP_OUTPUT}")
    print(f"JSON:                    {JSON_OUTPUT}")


def show_status() -> None:
    print("\nAQSD PORTFOLIO ENGINE STATUS")
    print("=" * 70)
    print(f"Positions file:  {'FOUND' if POSITIONS_FILE.exists() else 'MISSING'}")
    print(f"Risk config:     {'FOUND' if CONFIG_FILE.exists() else 'MISSING'}")
    print(f"Decision file:   {'FOUND' if DECISION_FILE.exists() else 'MISSING / OPTIONAL'}")
    print(f"Risk file:       {'FOUND' if RISK_FILE.exists() else 'MISSING / OPTIONAL'}")
    print("=" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Portfolio Risk Engine"
    )
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.setup:
        setup_files()
        return

    if args.status:
        show_status()
        return

    if args.run:
        run_engine()
        return

    raise SystemExit(
        "Use --setup, --status or --run"
    )


if __name__ == "__main__":
    main()
