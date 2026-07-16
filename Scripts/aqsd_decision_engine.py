"""
AQSD Professional
Module: Institutional Decision Engine
Version: 1.0

Purpose
-------
Combines existing AQSD futures, options and smart-money outputs into one
explainable institutional decision for a selected underlying.

Inputs
------
Output/AQSD_FYERS_Futures_OI_Analytics.csv
Output/AQSD_Options_Intelligence.csv
Output/AQSD_FYERS_Smart_Money_Summary.csv
Output/AQSD_BANKNIFTY_Institutional_Levels.csv   (optional)

Outputs
-------
Output/AQSD_Decision_Engine.csv
Output/AQSD_Decision_Engine.json
Output/AQSD_Decision_Engine_History.csv

Safety
------
- Decision-support only
- No order placement
- No database writes

Examples
--------
python aqsd_decision_engine.py --status
python aqsd_decision_engine.py --run --underlying BANKNIFTY
python aqsd_decision_engine.py --run --underlying NIFTY
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "Output"

FUTURES_FILE = OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.csv"
OPTIONS_FILE = OUTPUT_DIR / "AQSD_Options_Intelligence.csv"
SMART_FILE = OUTPUT_DIR / "AQSD_FYERS_Smart_Money_Summary.csv"
BANKNIFTY_FILE = OUTPUT_DIR / "AQSD_BANKNIFTY_Institutional_Levels.csv"

SUMMARY_OUTPUT = OUTPUT_DIR / "AQSD_Decision_Engine.csv"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_Decision_Engine.json"
HISTORY_OUTPUT = OUTPUT_DIR / "AQSD_Decision_Engine_History.csv"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None

        number = float(value)

        if math.isnan(number):
            return None

        return number
    except (TypeError, ValueError):
        return None


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def select_row(
    frame: pd.DataFrame,
    underlying: str,
) -> pd.Series | None:
    if frame.empty or "underlying" not in frame.columns:
        return None

    target = underlying.strip().upper()

    rows = frame[
        frame["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(target)
    ]

    if rows.empty:
        return None

    return rows.iloc[-1]


def first_present(
    row: pd.Series | None,
    names: list[str],
    default: Any = None,
) -> Any:
    if row is None:
        return default

    for name in names:
        if name in row.index:
            value = row.get(name)

            if pd.notna(value):
                return value

    return default


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def probability_label(value: float) -> str:
    if value >= 80:
        return "VERY HIGH"

    if value >= 65:
        return "HIGH"

    if value >= 50:
        return "MEDIUM"

    return "LOW"


def grade_from_confidence(
    confidence: float,
    action: str,
) -> str:
    if action in {"WAIT", "AVOID"}:
        return "AVOID"

    if confidence >= 85:
        return "A+"

    if confidence >= 75:
        return "A"

    if confidence >= 65:
        return "B"

    if confidence >= 55:
        return "C"

    return "AVOID"


def infer_market_regime(
    bull_score: float,
    bear_score: float,
    continuation_probability: float | None,
    iv_regime: str,
) -> str:
    spread = abs(
        bull_score - bear_score
    )

    if continuation_probability is not None and continuation_probability >= 70:
        if bull_score > bear_score:
            return "BULLISH CONTINUATION"

        if bear_score > bull_score:
            return "BEARISH CONTINUATION"

    if "EXPENSIVE" in iv_regime.upper() and spread < 15:
        return "HIGH-VOLATILITY RANGE"

    if spread < 10:
        return "RANGE-BOUND / MIXED"

    return "TRENDING"


def score_futures(
    row: pd.Series | None,
) -> tuple[float, float, list[str]]:
    bull = 50.0
    bear = 50.0
    reasons: list[str] = []

    if row is None:
        return bull, bear, ["Futures analytics unavailable"]

    near_cycle = str(
        first_present(
            row,
            ["near_cycle"],
            "",
        )
    ).upper()

    next_cycle = str(
        first_present(
            row,
            ["next_cycle"],
            "",
        )
    ).upper()

    far_cycle = str(
        first_present(
            row,
            ["far_cycle"],
            "",
        )
    ).upper()

    rollover = str(
        first_present(
            row,
            ["rollover_signal"],
            "",
        )
    ).upper()

    migration = str(
        first_present(
            row,
            ["oi_migration"],
            "",
        )
    ).upper()

    term_structure = str(
        first_present(
            row,
            ["term_structure"],
            "",
        )
    ).upper()

    cycle_weights = {
        near_cycle: 12,
        next_cycle: 8,
        far_cycle: 5,
    }

    for cycle, weight in cycle_weights.items():
        if cycle == "LONG BUILDUP":
            bull += weight
            bear -= weight / 2
            reasons.append(f"{cycle.title()} in futures")

        elif cycle == "SHORT COVERING":
            bull += weight * 0.8
            bear -= weight / 3
            reasons.append(f"{cycle.title()} in futures")

        elif cycle == "SHORT BUILDUP":
            bear += weight
            bull -= weight / 2
            reasons.append(f"{cycle.title()} in futures")

        elif cycle == "LONG UNWINDING":
            bear += weight * 0.8
            bull -= weight / 3
            reasons.append(f"{cycle.title()} in futures")

    if "BULLISH" in rollover:
        bull += 12
        bear -= 5
        reasons.append("Bullish rollover")

    if "BEARISH" in rollover or "BROAD SHORT BUILDUP" in rollover:
        bear += 12
        bull -= 5
        reasons.append("Bearish rollover")

    if "BULLISH" in migration:
        bull += 8
        reasons.append("Bullish OI migration")

    if "BEARISH" in migration or "SHORT BUILDUP" in migration:
        bear += 8
        reasons.append("Bearish OI migration")

    if term_structure == "BACKWARDATION":
        bear += 4
        reasons.append("Backwardation")

    elif term_structure == "CONTANGO":
        reasons.append("Contango")

    return clamp(bull), clamp(bear), reasons


def score_options(
    row: pd.Series | None,
) -> tuple[float, float, list[str]]:
    bull = 50.0
    bear = 50.0
    reasons: list[str] = []

    if row is None:
        return bull, bear, ["Options intelligence unavailable"]

    modified_pcr = safe_float(
        first_present(
            row,
            ["modified_pcr"],
        )
    )

    oi_pcr = safe_float(
        first_present(
            row,
            ["oi_pcr"],
        )
    )

    pcr_trend = str(
        first_present(
            row,
            ["pcr_trend"],
            "",
        )
    ).upper()

    bull_reversal = safe_float(
        first_present(
            row,
            ["bullish_reversal_probability"],
        )
    )

    bear_reversal = safe_float(
        first_present(
            row,
            ["bearish_reversal_probability"],
        )
    )

    if modified_pcr is not None:
        if modified_pcr >= 1.25:
            bull += 13
            bear -= 5
            reasons.append("Modified PCR strongly supportive")

        elif modified_pcr >= 1.05:
            bull += 7
            reasons.append("Modified PCR moderately supportive")

        elif modified_pcr <= 0.70:
            bear += 13
            bull -= 5
            reasons.append("Modified PCR shows strong call dominance")

        elif modified_pcr <= 0.90:
            bear += 7
            reasons.append("Modified PCR moderately bearish")

    if oi_pcr is not None:
        if oi_pcr >= 1.30:
            bull += 8
            reasons.append("OI PCR elevated")

        elif oi_pcr <= 0.75:
            bear += 8
            reasons.append("OI PCR depressed")

    if pcr_trend == "RISING":
        bull += 8
        bear -= 3
        reasons.append("PCR trend rising")

    elif pcr_trend == "FALLING":
        bear += 8
        bull -= 3
        reasons.append("PCR trend falling")

    if bull_reversal is not None and bull_reversal >= 65:
        bull += 8
        reasons.append("Bullish reversal probability elevated")

    if bear_reversal is not None and bear_reversal >= 65:
        bear += 8
        reasons.append("Bearish reversal probability elevated")

    return clamp(bull), clamp(bear), reasons


def score_walls_and_price(
    row: pd.Series | None,
) -> tuple[float, float, list[str], dict[str, float | None]]:
    bull = 50.0
    bear = 50.0
    reasons: list[str] = []

    if row is None:
        return (
            bull,
            bear,
            ["Wall intelligence unavailable"],
            {
                "spot": None,
                "put_wall": None,
                "call_wall": None,
                "max_pain": None,
            },
        )

    spot = safe_float(
        first_present(
            row,
            ["spot_price"],
        )
    )

    put_wall = safe_float(
        first_present(
            row,
            ["positional_put_wall"],
        )
    )

    call_wall = safe_float(
        first_present(
            row,
            ["positional_call_wall"],
        )
    )

    fresh_put = safe_float(
        first_present(
            row,
            ["fresh_put_wall"],
        )
    )

    fresh_call = safe_float(
        first_present(
            row,
            ["fresh_call_wall"],
        )
    )

    max_pain = safe_float(
        first_present(
            row,
            ["max_pain"],
        )
    )

    wall_shift = str(
        first_present(
            row,
            ["wall_shift_signal"],
            "",
        )
    ).upper()

    if spot is not None and put_wall is not None:
        distance = abs(
            spot - put_wall
        )

        if distance <= max(100, spot * 0.004):
            bull += 10
            reasons.append("Spot close to positional put wall")

    if spot is not None and call_wall is not None:
        distance = abs(
            call_wall - spot
        )

        if distance <= max(100, spot * 0.004):
            bear += 10
            reasons.append("Spot close to positional call wall")

    if fresh_put is not None:
        bull += 6
        reasons.append("Fresh put wall present")

    if fresh_call is not None:
        bear += 6
        reasons.append("Fresh call wall present")

    if "PUT WALL MOVING UP" in wall_shift:
        bull += 8
        reasons.append("Put wall moving upward")

    if "CALL WALL MOVING DOWN" in wall_shift:
        bear += 8
        reasons.append("Call wall moving downward")

    if spot is not None and max_pain is not None:
        if spot > max_pain:
            bear += 3
            reasons.append("Spot above max pain")

        elif spot < max_pain:
            bull += 3
            reasons.append("Spot below max pain")

    return (
        clamp(bull),
        clamp(bear),
        reasons,
        {
            "spot": spot,
            "put_wall": put_wall,
            "call_wall": call_wall,
            "max_pain": max_pain,
        },
    )


def score_volatility(
    row: pd.Series | None,
) -> tuple[float, float, float, list[str]]:
    bull = 50.0
    bear = 50.0
    quality = 50.0
    reasons: list[str] = []

    if row is None:
        return bull, bear, quality, ["IV/HV intelligence unavailable"]

    iv_regime = str(
        first_present(
            row,
            ["iv_regime"],
            "NO IV DATA",
        )
    ).upper()

    iv_hv_spread = safe_float(
        first_present(
            row,
            ["iv_hv_spread"],
        )
    )

    if "EXPENSIVE" in iv_regime:
        quality -= 10
        reasons.append("IV materially above HV")

    elif "CHEAP" in iv_regime:
        quality += 10
        reasons.append("IV below HV")

    elif "FAIR" in iv_regime:
        quality += 5
        reasons.append("IV broadly aligned with HV")

    if iv_hv_spread is not None and iv_hv_spread >= 8:
        quality -= 8

    return (
        clamp(bull),
        clamp(bear),
        clamp(quality),
        reasons,
    )


def build_trade_levels(
    action: str,
    spot: float | None,
    put_wall: float | None,
    call_wall: float | None,
    max_pain: float | None,
) -> dict[str, float | None]:
    if spot is None or action in {"WAIT", "AVOID"}:
        return {
            "aggressive_entry": None,
            "conservative_entry": None,
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
            "target_3": None,
            "risk_reward": None,
        }

    fallback_distance = max(
        spot * 0.004,
        100,
    )

    if action == "BUY":
        support = (
            put_wall
            if put_wall is not None and put_wall < spot
            else max_pain
            if max_pain is not None and max_pain < spot
            else spot - fallback_distance
        )

        resistance = (
            call_wall
            if call_wall is not None and call_wall > spot
            else spot + fallback_distance * 2
        )

        aggressive_entry = spot
        conservative_entry = spot + fallback_distance * 0.20
        stop_loss = support - fallback_distance * 0.20
        target_1 = min(
            resistance,
            spot + fallback_distance,
        )
        target_2 = resistance
        target_3 = resistance + fallback_distance

    else:
        resistance = (
            call_wall
            if call_wall is not None and call_wall > spot
            else max_pain
            if max_pain is not None and max_pain > spot
            else spot + fallback_distance
        )

        support = (
            put_wall
            if put_wall is not None and put_wall < spot
            else spot - fallback_distance * 2
        )

        aggressive_entry = spot
        conservative_entry = spot - fallback_distance * 0.20
        stop_loss = resistance + fallback_distance * 0.20
        target_1 = max(
            support,
            spot - fallback_distance,
        )
        target_2 = support
        target_3 = support - fallback_distance

    risk = abs(
        aggressive_entry - stop_loss
    )

    reward = abs(
        target_2 - aggressive_entry
    )

    risk_reward = (
        reward / risk
        if risk > 0
        else None
    )

    return {
        "aggressive_entry": aggressive_entry,
        "conservative_entry": conservative_entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "target_3": target_3,
        "risk_reward": risk_reward,
    }


def build_decision(
    underlying: str,
) -> pd.DataFrame:
    futures_frame = read_csv(
        FUTURES_FILE
    )

    options_frame = read_csv(
        OPTIONS_FILE
    )

    smart_frame = read_csv(
        SMART_FILE
    )

    bank_frame = read_csv(
        BANKNIFTY_FILE
    )

    futures = select_row(
        futures_frame,
        underlying,
    )

    options = select_row(
        options_frame,
        underlying,
    )

    smart = select_row(
        smart_frame,
        underlying,
    )

    bank = None

    if (
        underlying.strip().upper() == "BANKNIFTY"
        and not bank_frame.empty
    ):
        bank = bank_frame.iloc[-1]

    futures_bull, futures_bear, futures_reasons = score_futures(
        futures
    )

    options_bull, options_bear, options_reasons = score_options(
        options
    )

    wall_bull, wall_bear, wall_reasons, levels = score_walls_and_price(
        options
    )

    _, _, volatility_quality, volatility_reasons = score_volatility(
        options
    )

    smart_score = safe_float(
        first_present(
            smart,
            ["total_smart_money_score"],
        )
    )

    smart_bull = 50.0
    smart_bear = 50.0
    smart_reasons: list[str] = []

    smart_bias = str(
        first_present(
            smart,
            ["smart_money_bias"],
            "",
        )
    ).upper()

    if "BULL" in smart_bias:
        smart_bull += 15
        smart_bear -= 7
        smart_reasons.append("Smart-money engine bullish")

    elif "BEAR" in smart_bias:
        smart_bear += 15
        smart_bull -= 7
        smart_reasons.append("Smart-money engine bearish")

    if smart_score is not None:
        smart_bull += max(
            0,
            smart_score * 2,
        )

        smart_bear += max(
            0,
            -smart_score * 2,
        )

    bull_score = (
        futures_bull * 0.30
        + options_bull * 0.30
        + wall_bull * 0.20
        + smart_bull * 0.20
    )

    bear_score = (
        futures_bear * 0.30
        + options_bear * 0.30
        + wall_bear * 0.20
        + smart_bear * 0.20
    )

    bull_score = clamp(
        bull_score
    )

    bear_score = clamp(
        bear_score
    )

    score_spread = bull_score - bear_score

    if score_spread >= 12:
        action = "BUY"

    elif score_spread <= -12:
        action = "SELL"

    elif abs(score_spread) < 7:
        action = "WAIT"

    else:
        action = "AVOID"

    directional_strength = abs(
        score_spread
    )

    confidence = clamp(
        50
        + directional_strength * 0.8
        + (volatility_quality - 50) * 0.2
    )

    if action in {"WAIT", "AVOID"}:
        confidence = min(
            confidence,
            59,
        )

    continuation_probability = safe_float(
        first_present(
            options,
            ["continuation_probability"],
        )
    )

    bullish_reversal_probability = safe_float(
        first_present(
            options,
            ["bullish_reversal_probability"],
        )
    )

    bearish_reversal_probability = safe_float(
        first_present(
            options,
            ["bearish_reversal_probability"],
        )
    )

    iv_regime = str(
        first_present(
            options,
            ["iv_regime"],
            "NO IV DATA",
        )
    )

    market_regime = infer_market_regime(
        bull_score,
        bear_score,
        continuation_probability,
        iv_regime,
    )

    trade_levels = build_trade_levels(
        action,
        levels["spot"],
        levels["put_wall"],
        levels["call_wall"],
        levels["max_pain"],
    )

    all_reasons = (
        futures_reasons
        + options_reasons
        + wall_reasons
        + smart_reasons
        + volatility_reasons
    )

    reason_priority: list[str] = []

    for reason in all_reasons:
        if reason and reason not in reason_priority:
            reason_priority.append(
                reason
            )

    grade = grade_from_confidence(
        confidence,
        action,
    )

    decision_text = (
        f"{action} | {market_regime} | "
        f"Confidence {confidence:.1f}%"
    )

    result = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "underlying": underlying.strip().upper(),
        "spot_price": levels["spot"],
        "institutional_bull_score": round(
            bull_score,
            1,
        ),
        "institutional_bear_score": round(
            bear_score,
            1,
        ),
        "probability_up": round(
            bull_score,
            1,
        ),
        "probability_down": round(
            bear_score,
            1,
        ),
        "confidence_percent": round(
            confidence,
            1,
        ),
        "confidence_label": probability_label(
            confidence
        ),
        "market_regime": market_regime,
        "suggested_action": action,
        "trade_quality": grade,
        "bullish_reversal_probability": bullish_reversal_probability,
        "bearish_reversal_probability": bearish_reversal_probability,
        "continuation_probability": continuation_probability,
        "iv_regime": iv_regime,
        "put_wall": levels["put_wall"],
        "call_wall": levels["call_wall"],
        "max_pain": levels["max_pain"],
        "aggressive_entry": trade_levels["aggressive_entry"],
        "conservative_entry": trade_levels["conservative_entry"],
        "stop_loss": trade_levels["stop_loss"],
        "target_1": trade_levels["target_1"],
        "target_2": trade_levels["target_2"],
        "target_3": trade_levels["target_3"],
        "risk_reward": trade_levels["risk_reward"],
        "decision": decision_text,
        "reason_1": reason_priority[0] if len(reason_priority) > 0 else "",
        "reason_2": reason_priority[1] if len(reason_priority) > 1 else "",
        "reason_3": reason_priority[2] if len(reason_priority) > 2 else "",
        "reason_4": reason_priority[3] if len(reason_priority) > 3 else "",
        "reason_5": reason_priority[4] if len(reason_priority) > 4 else "",
        "reason_6": reason_priority[5] if len(reason_priority) > 5 else "",
        "order_placement": "DISABLED",
    }

    if bank is not None:
        result["expected_low"] = safe_float(
            first_present(
                bank,
                ["straddle_expected_low"],
            )
        )

        result["expected_high"] = safe_float(
            first_present(
                bank,
                ["straddle_expected_high"],
            )
        )

    else:
        result["expected_low"] = None
        result["expected_high"] = None

    return pd.DataFrame(
        [result]
    )


def save_outputs(
    summary: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    if HISTORY_OUTPUT.exists():
        history = pd.read_csv(
            HISTORY_OUTPUT,
            low_memory=False,
        )

        history = pd.concat(
            [
                history,
                summary,
            ],
            ignore_index=True,
        )

    else:
        history = summary.copy()

    history.to_csv(
        HISTORY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "decision": summary.to_dict(
                    orient="records"
                )
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def show_results(
    summary: pd.DataFrame,
) -> None:
    row = summary.iloc[0]

    print("\nAQSD INSTITUTIONAL DECISION ENGINE")
    print("=" * 94)
    print(f"Underlying:             {row['underlying']}")
    print(f"Spot:                   {row['spot_price']}")
    print(f"Suggested Action:       {row['suggested_action']}")
    print(f"Trade Quality:          {row['trade_quality']}")
    print(f"Confidence:             {row['confidence_percent']}%")
    print(f"Market Regime:          {row['market_regime']}")
    print("-" * 94)
    print(f"Institutional Bull:     {row['institutional_bull_score']}")
    print(f"Institutional Bear:     {row['institutional_bear_score']}")
    print(f"Probability Up:         {row['probability_up']}%")
    print(f"Probability Down:       {row['probability_down']}%")
    print("-" * 94)
    print(f"Aggressive Entry:       {row['aggressive_entry']}")
    print(f"Conservative Entry:     {row['conservative_entry']}")
    print(f"Stop Loss:              {row['stop_loss']}")
    print(f"Target 1:               {row['target_1']}")
    print(f"Target 2:               {row['target_2']}")
    print(f"Target 3:               {row['target_3']}")
    print(f"Risk / Reward:          {row['risk_reward']}")
    print("-" * 94)
    print(f"Reason 1:               {row['reason_1']}")
    print(f"Reason 2:               {row['reason_2']}")
    print(f"Reason 3:               {row['reason_3']}")
    print(f"Reason 4:               {row['reason_4']}")
    print(f"Reason 5:               {row['reason_5']}")
    print("=" * 94)
    print(f"CSV:                    {SUMMARY_OUTPUT}")
    print(f"JSON:                   {JSON_OUTPUT}")
    print(f"History:                {HISTORY_OUTPUT}")
    print("Order placement:        DISABLED")


def show_status() -> None:
    print("\nAQSD INSTITUTIONAL DECISION ENGINE STATUS")
    print("=" * 82)
    print("Version: 1.0")

    for label, path in [
        ("Futures analytics", FUTURES_FILE),
        ("Options intelligence", OPTIONS_FILE),
        ("Smart money", SMART_FILE),
        ("BANKNIFTY levels", BANKNIFTY_FILE),
    ]:
        print(
            f"{label:<22}: "
            f"{'FOUND' if path.exists() else 'MISSING / OPTIONAL'}"
        )

    print(f"Output folder: {OUTPUT_DIR}")
    print("Order placement: DISABLED")
    print("=" * 82)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Institutional Decision Engine."
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
        "--underlying",
        help="Underlying such as BANKNIFTY, NIFTY or RELIANCE.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if not args.underlying:
        raise SystemExit(
            "Please provide --underlying, for example:\n"
            "python aqsd_decision_engine.py "
            "--run --underlying BANKNIFTY"
        )

    summary = build_decision(
        args.underlying
    )

    save_outputs(
        summary
    )

    show_results(
        summary
    )


if __name__ == "__main__":
    main()
