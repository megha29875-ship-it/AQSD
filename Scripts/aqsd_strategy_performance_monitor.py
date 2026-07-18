"""
AQSD Strategy Performance Monitor v1.0

Purpose
-------
Tracks historical AQSD decisions and evaluates realised performance.

Primary inputs
--------------
Output/AQSD_AI_Master_Decision_History.csv
Output/AQSD_AI_Master_Decision.csv
Output/AQSD_FYERS_Live_Scanner.csv
Output/AQSD_Live_Scanner.csv
Output/Live_Scanner.csv

Outputs
-------
Output/AQSD_Strategy_Performance.csv
Output/AQSD_Strategy_Performance.json
Output/AQSD_Strategy_Summary.csv
Output/AQSD_Equity_Curve.csv

Examples
--------
python aqsd_strategy_performance_monitor.py --status
python aqsd_strategy_performance_monitor.py --run
python aqsd_strategy_performance_monitor.py --run --capital 1000000
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

DECISION_HISTORY = OUT / "AQSD_AI_Master_Decision_History.csv"
LATEST_DECISION = OUT / "AQSD_AI_Master_Decision.csv"

PRICE_FILES = [
    OUT / "AQSD_FYERS_Live_Scanner.csv",
    OUT / "AQSD_Live_Scanner.csv",
    OUT / "Live_Scanner.csv",
]

PERFORMANCE_OUTPUT = OUT / "AQSD_Strategy_Performance.csv"
SUMMARY_OUTPUT = OUT / "AQSD_Strategy_Summary.csv"
EQUITY_OUTPUT = OUT / "AQSD_Equity_Curve.csv"
JSON_OUTPUT = OUT / "AQSD_Strategy_Performance.json"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if pd.isna(number) else number
    except Exception:
        return default


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text


def load_decisions() -> pd.DataFrame:
    if DECISION_HISTORY.exists():
        frame = pd.read_csv(DECISION_HISTORY, low_memory=False)
    elif LATEST_DECISION.exists():
        frame = pd.read_csv(LATEST_DECISION, low_memory=False)
    else:
        raise SystemExit(
            "Missing AQSD AI decision history. "
            f"Expected: {DECISION_HISTORY}"
        )

    if frame.empty:
        raise SystemExit("AQSD AI decision history is empty.")

    return frame.copy()


def load_latest_prices() -> pd.DataFrame:
    for path in PRICE_FILES:
        if path.exists():
            try:
                frame = pd.read_csv(path, low_memory=False)
                if not frame.empty:
                    return frame
            except Exception:
                continue
    return pd.DataFrame()


def detect_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    mapping = {
        str(column).strip().lower(): column
        for column in frame.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in mapping:
            return mapping[key]

    return None


def normalize_decisions(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    timestamp_col = detect_column(
        result,
        [
            "generated_at",
            "timestamp",
            "decision_time",
            "run_time",
            "date",
        ],
    )

    if timestamp_col:
        result["decision_time"] = pd.to_datetime(
            result[timestamp_col],
            errors="coerce",
        )
    else:
        result["decision_time"] = pd.NaT

    underlying_col = detect_column(
        result,
        [
            "underlying",
            "symbol",
            "ticker",
            "instrument",
        ],
    )

    if underlying_col:
        result["underlying_norm"] = (
            result[underlying_col]
            .astype(str)
            .str.strip()
            .str.upper()
        )
    else:
        result["underlying_norm"] = "UNKNOWN"

    verdict_col = detect_column(
        result,
        [
            "final_verdict",
            "base_action",
            "suggested_action",
            "signal",
            "direction",
        ],
    )

    if verdict_col:
        result["verdict_norm"] = (
            result[verdict_col]
            .astype(str)
            .str.strip()
            .str.upper()
        )
    else:
        result["verdict_norm"] = "WAIT"

    entry_col = detect_column(
        result,
        [
            "spot_price",
            "entry_price",
            "ltp",
            "close",
            "price",
        ],
    )

    result["entry_price_norm"] = (
        pd.to_numeric(
            result[entry_col],
            errors="coerce",
        )
        if entry_col
        else math.nan
    )

    confidence_col = detect_column(
        result,
        [
            "final_confidence_percent",
            "confidence_percent",
            "ai_confidence_percent",
            "confidence",
        ],
    )

    result["confidence_norm"] = (
        pd.to_numeric(
            result[confidence_col],
            errors="coerce",
        ).fillna(0.0)
        if confidence_col
        else 0.0
    )

    quality_col = detect_column(
        result,
        [
            "trade_quality",
            "quality",
            "signal_quality",
        ],
    )

    result["trade_quality_norm"] = (
        result[quality_col].astype(str).str.strip().str.upper()
        if quality_col
        else ""
    )

    probability_col = detect_column(
        result,
        [
            "probability_success_percent",
            "success_probability",
            "probability_success",
        ],
    )

    result["probability_norm"] = (
        pd.to_numeric(
            result[probability_col],
            errors="coerce",
        ).fillna(0.0)
        if probability_col
        else 0.0
    )

    result = result[
        result["verdict_norm"].isin(["BUY", "SELL"])
    ].copy()

    result = result[
        result["entry_price_norm"].notna()
        & (result["entry_price_norm"] > 0)
    ].copy()

    result = result.sort_values(
        "decision_time",
        na_position="last",
    ).reset_index(drop=True)

    return result


def build_price_map(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {}

    symbol_col = detect_column(
        frame,
        [
            "underlying",
            "symbol",
            "ticker",
            "instrument",
        ],
    )

    price_col = detect_column(
        frame,
        [
            "ltp",
            "last_price",
            "close",
            "current_price",
            "spot_price",
            "price",
        ],
    )

    if not symbol_col or not price_col:
        return {}

    working = frame[[symbol_col, price_col]].copy()
    working["symbol_norm"] = (
        working[symbol_col]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    working["price_norm"] = pd.to_numeric(
        working[price_col],
        errors="coerce",
    )
    working = working.dropna(subset=["price_norm"])

    return dict(
        zip(
            working["symbol_norm"],
            working["price_norm"],
        )
    )


def calculate_performance(
    decisions: pd.DataFrame,
    price_map: dict[str, float],
    capital: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    actionable_count = max(len(decisions), 1)
    capital_per_trade = capital / actionable_count

    for index, row in decisions.iterrows():
        symbol = safe_text(
            row.get("underlying_norm"),
            "UNKNOWN",
        )
        verdict = safe_text(
            row.get("verdict_norm"),
            "WAIT",
        ).upper()
        entry_price = safe_float(
            row.get("entry_price_norm"),
            0.0,
        )

        current_price = price_map.get(symbol)

        if current_price is None:
            current_price = entry_price

        if verdict == "BUY":
            return_percent = (
                (current_price - entry_price)
                / entry_price
                * 100
            )
        else:
            return_percent = (
                (entry_price - current_price)
                / entry_price
                * 100
            )

        realised_pnl = (
            capital_per_trade
            * return_percent
            / 100
        )

        outcome = "WIN" if return_percent > 0 else (
            "LOSS" if return_percent < 0 else "FLAT"
        )

        rows.append(
            {
                "trade_id": index + 1,
                "decision_time": (
                    row.get("decision_time").isoformat()
                    if pd.notna(row.get("decision_time"))
                    else ""
                ),
                "underlying": symbol,
                "verdict": verdict,
                "entry_price": round(entry_price, 4),
                "current_price": round(
                    safe_float(current_price),
                    4,
                ),
                "return_percent": round(
                    return_percent,
                    4,
                ),
                "realised_pnl": round(
                    realised_pnl,
                    2,
                ),
                "outcome": outcome,
                "confidence_percent": round(
                    safe_float(
                        row.get("confidence_norm")
                    ),
                    2,
                ),
                "probability_success_percent": round(
                    safe_float(
                        row.get("probability_norm")
                    ),
                    2,
                ),
                "trade_quality": safe_text(
                    row.get("trade_quality_norm")
                ),
                "evaluation_status": (
                    "LIVE PRICE MATCHED"
                    if symbol in price_map
                    else "ENTRY PRICE USED"
                ),
            }
        )

    return pd.DataFrame(rows)


def calculate_summary(
    performance: pd.DataFrame,
    capital: float,
) -> pd.DataFrame:
    if performance.empty:
        return pd.DataFrame(
            [
                {
                    "generated_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "flat": 0,
                    "win_rate_percent": 0.0,
                    "average_return_percent": 0.0,
                    "median_return_percent": 0.0,
                    "best_return_percent": 0.0,
                    "worst_return_percent": 0.0,
                    "gross_profit": 0.0,
                    "gross_loss": 0.0,
                    "net_pnl": 0.0,
                    "ending_equity": capital,
                    "profit_factor": 0.0,
                    "expectancy": 0.0,
                    "max_drawdown_percent": 0.0,
                    "sharpe_ratio": 0.0,
                }
            ]
        )

    total = len(performance)
    wins = int(
        performance["outcome"].eq("WIN").sum()
    )
    losses = int(
        performance["outcome"].eq("LOSS").sum()
    )
    flat = int(
        performance["outcome"].eq("FLAT").sum()
    )

    returns = performance["return_percent"].astype(float)
    pnl = performance["realised_pnl"].astype(float)

    gross_profit = pnl[pnl > 0].sum()
    gross_loss = abs(pnl[pnl < 0].sum())
    net_pnl = pnl.sum()

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else gross_profit
    )

    average_win = (
        returns[returns > 0].mean()
        if (returns > 0).any()
        else 0.0
    )

    average_loss = (
        abs(returns[returns < 0].mean())
        if (returns < 0).any()
        else 0.0
    )

    win_rate = wins / total if total else 0.0
    loss_rate = losses / total if total else 0.0

    expectancy = (
        win_rate * average_win
        - loss_rate * average_loss
    )

    equity = capital + pnl.cumsum()
    running_peak = equity.cummax()
    drawdown = (
        (equity - running_peak)
        / running_peak.replace(0, math.nan)
        * 100
    )

    max_drawdown = abs(
        safe_float(drawdown.min(), 0.0)
    )

    return_std = safe_float(
        returns.std(ddof=1),
        0.0,
    )

    sharpe = (
        returns.mean() / return_std
        * math.sqrt(total)
        if return_std > 0 and total > 1
        else 0.0
    )

    confidence_accuracy = (
        performance.loc[
            performance["outcome"].eq("WIN"),
            "confidence_percent",
        ].mean()
        if wins
        else 0.0
    )

    return pd.DataFrame(
        [
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "flat": flat,
                "win_rate_percent": round(
                    win_rate * 100,
                    2,
                ),
                "average_return_percent": round(
                    returns.mean(),
                    4,
                ),
                "median_return_percent": round(
                    returns.median(),
                    4,
                ),
                "best_return_percent": round(
                    returns.max(),
                    4,
                ),
                "worst_return_percent": round(
                    returns.min(),
                    4,
                ),
                "gross_profit": round(
                    gross_profit,
                    2,
                ),
                "gross_loss": round(
                    gross_loss,
                    2,
                ),
                "net_pnl": round(
                    net_pnl,
                    2,
                ),
                "ending_equity": round(
                    capital + net_pnl,
                    2,
                ),
                "profit_factor": round(
                    profit_factor,
                    4,
                ),
                "expectancy_percent": round(
                    expectancy,
                    4,
                ),
                "max_drawdown_percent": round(
                    max_drawdown,
                    4,
                ),
                "sharpe_ratio": round(
                    sharpe,
                    4,
                ),
                "average_confidence_on_wins": round(
                    safe_float(confidence_accuracy),
                    2,
                ),
            }
        ]
    )


def calculate_equity_curve(
    performance: pd.DataFrame,
    capital: float,
) -> pd.DataFrame:
    if performance.empty:
        return pd.DataFrame(
            [
                {
                    "trade_id": 0,
                    "equity": capital,
                    "running_peak": capital,
                    "drawdown_percent": 0.0,
                }
            ]
        )

    curve = performance[
        [
            "trade_id",
            "decision_time",
            "underlying",
            "verdict",
            "realised_pnl",
            "return_percent",
        ]
    ].copy()

    curve["equity"] = (
        capital
        + curve["realised_pnl"].astype(float).cumsum()
    )

    curve["running_peak"] = curve["equity"].cummax()

    curve["drawdown_percent"] = (
        (
            curve["equity"]
            - curve["running_peak"]
        )
        / curve["running_peak"].replace(0, math.nan)
        * 100
    ).fillna(0.0)

    return curve


def save_outputs(
    performance: pd.DataFrame,
    summary: pd.DataFrame,
    equity: pd.DataFrame,
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    performance.to_csv(
        PERFORMANCE_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    equity.to_csv(
        EQUITY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    payload = {
        "summary": (
            summary.iloc[0].to_dict()
            if not summary.empty
            else {}
        ),
        "trades": performance.to_dict(
            orient="records"
        ),
    }

    JSON_OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def show(
    performance: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]

    print("\nAQSD STRATEGY PERFORMANCE MONITOR")
    print("=" * 84)
    print(f"Total Trades:           {row['total_trades']}")
    print(f"Wins:                   {row['wins']}")
    print(f"Losses:                 {row['losses']}")
    print(f"Flat:                   {row['flat']}")
    print(f"Win Rate:               {row['win_rate_percent']}%")
    print(f"Average Return:         {row['average_return_percent']}%")
    print(f"Best Return:            {row['best_return_percent']}%")
    print(f"Worst Return:           {row['worst_return_percent']}%")
    print(f"Net P/L:                {row['net_pnl']}")
    print(f"Ending Equity:          {row['ending_equity']}")
    print(f"Profit Factor:          {row['profit_factor']}")
    print(
    f"Expectancy:             "
    f"{row.get('expectancy_percent', row.get('expectancy', 0.0))}%"
)
    print(f"Maximum Drawdown:       {row['max_drawdown_percent']}%")
    print(f"Sharpe Ratio:           {row['sharpe_ratio']}")
    print("-" * 84)
    print(f"Performance CSV:        {PERFORMANCE_OUTPUT}")
    print(f"Summary CSV:            {SUMMARY_OUTPUT}")
    print(f"Equity Curve CSV:       {EQUITY_OUTPUT}")
    print(f"JSON:                   {JSON_OUTPUT}")
    print("=" * 84)

    if not performance.empty:
        print("\nLATEST 10 EVALUATED TRADES")
        print(
            performance.tail(10).to_string(
                index=False
            )
        )


def status() -> None:
    print("\nAQSD STRATEGY PERFORMANCE STATUS")
    print("=" * 78)
    print(
        f"Decision History:       "
        f"{'FOUND' if DECISION_HISTORY.exists() else 'MISSING'}"
    )
    print(
        f"Latest Decision:        "
        f"{'FOUND' if LATEST_DECISION.exists() else 'MISSING'}"
    )

    for path in PRICE_FILES:
        print(
            f"{path.name:<30} "
            f"{'FOUND' if path.exists() else 'MISSING'}"
        )

    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Strategy Performance Monitor"
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
        "--capital",
        type=float,
        default=1_000_000,
        help="Starting capital used for equity calculations.",
    )

    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.run:
        decisions = normalize_decisions(
            load_decisions()
        )

        prices = build_price_map(
            load_latest_prices()
        )

        performance = calculate_performance(
            decisions,
            prices,
            max(args.capital, 1.0),
        )

        summary = calculate_summary(
            performance,
            max(args.capital, 1.0),
        )

        equity = calculate_equity_curve(
            performance,
            max(args.capital, 1.0),
        )

        save_outputs(
            performance,
            summary,
            equity,
        )

        show(
            performance,
            summary,
        )
        return

    raise SystemExit(
        "Use --status or --run --capital 1000000"
    )


if __name__ == "__main__":
    main()
