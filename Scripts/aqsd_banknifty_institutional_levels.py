"""
AQSD Professional
Module: BANKNIFTY Institutional Levels Engine
Version: 1.0

Purpose
-------
Builds an advanced BANKNIFTY derivatives view from the latest AQSD outputs.

Inputs
------
Output/AQSD_FYERS_Option_Chain.csv
Output/AQSD_FYERS_Option_Chain_Summary.csv
Output/AQSD_FYERS_Futures_OI_Analytics.csv

Outputs
-------
Output/AQSD_BANKNIFTY_Institutional_Levels.csv
Output/AQSD_BANKNIFTY_Strike_Levels.csv
Output/AQSD_BANKNIFTY_Institutional_Levels.xlsx
Output/AQSD_BANKNIFTY_Institutional_Levels.json

Analytics
---------
- Call wall
- Put wall
- Fresh call-writing wall
- Fresh put-writing wall
- ATM straddle value
- Straddle-implied expected range
- Max pain
- Support / resistance
- OI concentration score
- Pinning score around max pain
- Futures rollover signal
- Futures term structure
- Final BANKNIFTY bias

Important
---------
This module does not calculate true dealer gamma exposure because the current
AQSD option-chain output does not yet contain contract Greeks or implied
volatility. It uses OI concentration and premium/OI behaviour only.

Safety
------
- No order placement
- No AQSD database writes
- Yahoo files untouched

Examples
--------
python aqsd_banknifty_institutional_levels.py --status
python aqsd_banknifty_institutional_levels.py --run
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

OPTION_CHAIN_FILE = OUTPUT_DIR / "AQSD_FYERS_Option_Chain.csv"
OPTION_SUMMARY_FILE = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Summary.csv"
FUTURES_FILE = OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.csv"

SUMMARY_OUTPUT = OUTPUT_DIR / "AQSD_BANKNIFTY_Institutional_Levels.csv"
STRIKES_OUTPUT = OUTPUT_DIR / "AQSD_BANKNIFTY_Strike_Levels.csv"
EXCEL_OUTPUT = OUTPUT_DIR / "AQSD_BANKNIFTY_Institutional_Levels.xlsx"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_BANKNIFTY_Institutional_Levels.json"


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


def numeric(
    frame: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(
            [0.0] * len(frame),
            index=frame.index,
            dtype=float,
        )

    return pd.to_numeric(
        frame[column],
        errors="coerce",
    ).fillna(0.0)


def load_inputs() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    missing = [
        str(path)
        for path in [
            OPTION_CHAIN_FILE,
            OPTION_SUMMARY_FILE,
            FUTURES_FILE,
        ]
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Required AQSD output file(s) missing:\n"
            + "\n".join(missing)
        )

    chain = pd.read_csv(
        OPTION_CHAIN_FILE,
        low_memory=False,
    )

    option_summary = pd.read_csv(
        OPTION_SUMMARY_FILE,
        low_memory=False,
    )

    futures = pd.read_csv(
        FUTURES_FILE,
        low_memory=False,
    )

    if option_summary.empty:
        raise RuntimeError(
            "Option-chain summary is empty."
        )

    summary_row = option_summary.iloc[0]

    summary_underlying = str(
        summary_row.get("underlying", "")
    ).strip().upper()

    if summary_underlying != "BANKNIFTY":
        raise RuntimeError(
            "Latest option-chain output is not for BANKNIFTY.\n"
            "Run aqsd_fyers_option_chain_analytics.py "
            "--run --underlying BANKNIFTY first."
        )

    if "underlying" not in futures.columns:
        raise RuntimeError(
            "Futures analytics file has no underlying column."
        )

    future_rows = futures[
        futures["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        == "BANKNIFTY"
    ]

    if future_rows.empty:
        raise RuntimeError(
            "No BANKNIFTY futures analytics row found."
        )

    return (
        chain,
        summary_row,
        future_rows.iloc[0],
    )


def classify_actions(
    chain: pd.DataFrame,
) -> pd.DataFrame:
    result = chain.copy()

    ce_change = numeric(
        result,
        "ce_change_percent",
    )
    ce_oi_change = numeric(
        result,
        "ce_oi_change",
    )
    pe_change = numeric(
        result,
        "pe_change_percent",
    )
    pe_oi_change = numeric(
        result,
        "pe_oi_change",
    )

    def action(
        premium_change: float,
        oi_change: float,
        side: str,
    ) -> str:
        if premium_change > 0 and oi_change > 0:
            return f"{side} BUYING"

        if premium_change < 0 and oi_change > 0:
            return f"{side} WRITING"

        if premium_change > 0 and oi_change < 0:
            return f"{side} SHORT COVERING"

        if premium_change < 0 and oi_change < 0:
            return f"{side} LONG UNWINDING"

        return f"{side} NEUTRAL"

    result["ce_action"] = [
        action(pc, oi, "CALL")
        for pc, oi in zip(
            ce_change,
            ce_oi_change,
        )
    ]

    result["pe_action"] = [
        action(pc, oi, "PUT")
        for pc, oi in zip(
            pe_change,
            pe_oi_change,
        )
    ]

    result["ce_oi_share_percent"] = 0.0
    result["pe_oi_share_percent"] = 0.0

    total_ce_oi = numeric(
        result,
        "ce_open_interest",
    ).sum()

    total_pe_oi = numeric(
        result,
        "pe_open_interest",
    ).sum()

    if total_ce_oi > 0:
        result["ce_oi_share_percent"] = (
            numeric(
                result,
                "ce_open_interest",
            )
            / total_ce_oi
            * 100
        )

    if total_pe_oi > 0:
        result["pe_oi_share_percent"] = (
            numeric(
                result,
                "pe_open_interest",
            )
            / total_pe_oi
            * 100
        )

    return result


def max_strike_by(
    frame: pd.DataFrame,
    value_column: str,
) -> tuple[float | None, float | None]:
    if value_column not in frame.columns:
        return None, None

    work = frame.copy()

    work[value_column] = pd.to_numeric(
        work[value_column],
        errors="coerce",
    )

    work = work.dropna(
        subset=[
            "strike_price",
            value_column,
        ]
    )

    if work.empty:
        return None, None

    row = work.loc[
        work[value_column].idxmax()
    ]

    return (
        safe_float(row["strike_price"]),
        safe_float(row[value_column]),
    )


def max_action_strike(
    frame: pd.DataFrame,
    action_column: str,
    target_action: str,
    oi_change_column: str,
) -> tuple[float | None, float | None]:
    rows = frame[
        frame[action_column] == target_action
    ].copy()

    if rows.empty:
        return None, None

    rows[oi_change_column] = pd.to_numeric(
        rows[oi_change_column],
        errors="coerce",
    ).fillna(0.0)

    rows["magnitude"] = rows[
        oi_change_column
    ].abs()

    row = rows.sort_values(
        "magnitude",
        ascending=False,
    ).iloc[0]

    return (
        safe_float(row["strike_price"]),
        safe_float(row[oi_change_column]),
    )


def atm_row(
    chain: pd.DataFrame,
    atm_strike: float,
) -> pd.Series:
    rows = chain[
        pd.to_numeric(
            chain["strike_price"],
            errors="coerce",
        )
        == float(atm_strike)
    ]

    if rows.empty:
        nearest_index = (
            pd.to_numeric(
                chain["strike_price"],
                errors="coerce",
            )
            .sub(float(atm_strike))
            .abs()
            .idxmin()
        )

        return chain.loc[
            nearest_index
        ]

    return rows.iloc[0]


def pinning_score(
    spot: float | None,
    max_pain: float | None,
    atm_straddle: float | None,
) -> float | None:
    if (
        spot is None
        or max_pain is None
        or atm_straddle is None
        or atm_straddle <= 0
    ):
        return None

    distance = abs(
        spot - max_pain
    )

    score = (
        1
        - min(
            distance / atm_straddle,
            1,
        )
    ) * 100

    return round(
        score,
        2,
    )


def concentration_score(
    chain: pd.DataFrame,
) -> float | None:
    ce_shares = pd.to_numeric(
        chain.get(
            "ce_oi_share_percent",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    ).fillna(0.0)

    pe_shares = pd.to_numeric(
        chain.get(
            "pe_oi_share_percent",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    ).fillna(0.0)

    top_ce = ce_shares.nlargest(3).sum()
    top_pe = pe_shares.nlargest(3).sum()

    if top_ce == 0 and top_pe == 0:
        return None

    return round(
        (top_ce + top_pe) / 2,
        2,
    )


def derive_bias(
    futures: pd.Series,
    summary: pd.Series,
    call_writing_change: float | None,
    put_writing_change: float | None,
) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []

    rollover = str(
        futures.get(
            "rollover_signal",
            "",
        )
    ).upper()

    near_cycle = str(
        futures.get(
            "near_cycle",
            "",
        )
    ).upper()

    oi_pcr = safe_float(
        summary.get("oi_pcr")
    )

    if "BULLISH" in rollover:
        score += 3
        reasons.append(
            "Bullish futures rollover"
        )

    if "BEARISH" in rollover:
        score -= 3
        reasons.append(
            "Bearish futures rollover"
        )

    if near_cycle == "LONG BUILDUP":
        score += 2
        reasons.append(
            "Near futures long buildup"
        )

    if near_cycle == "SHORT BUILDUP":
        score -= 2
        reasons.append(
            "Near futures short buildup"
        )

    if near_cycle == "SHORT COVERING":
        score += 1
        reasons.append(
            "Near futures short covering"
        )

    if near_cycle == "LONG UNWINDING":
        score -= 1
        reasons.append(
            "Near futures long unwinding"
        )

    if oi_pcr is not None:
        if oi_pcr >= 1.20:
            score += 2
            reasons.append(
                "Put OI is dominant"
            )
        elif oi_pcr <= 0.80:
            score -= 2
            reasons.append(
                "Call OI is dominant"
            )

    call_strength = abs(
        call_writing_change or 0
    )

    put_strength = abs(
        put_writing_change or 0
    )

    if put_strength > call_strength:
        score += 2
        reasons.append(
            "Put writing stronger than call writing"
        )

    if call_strength > put_strength:
        score -= 2
        reasons.append(
            "Call writing stronger than put writing"
        )

    if score >= 6:
        bias = "STRONG BULLISH"
    elif score >= 3:
        bias = "BULLISH"
    elif score <= -6:
        bias = "STRONG BEARISH"
    elif score <= -3:
        bias = "BEARISH"
    else:
        bias = "RANGE-BOUND / MIXED"

    return score, bias, reasons


def build_summary(
    chain: pd.DataFrame,
    option_summary: pd.Series,
    futures: pd.Series,
) -> pd.DataFrame:
    spot = safe_float(
        option_summary.get(
            "spot_price"
        )
    )

    atm = safe_float(
        option_summary.get(
            "atm_strike"
        )
    )

    max_pain = safe_float(
        option_summary.get(
            "max_pain"
        )
    )

    call_wall, call_wall_oi = max_strike_by(
        chain,
        "ce_open_interest",
    )

    put_wall, put_wall_oi = max_strike_by(
        chain,
        "pe_open_interest",
    )

    call_writing_wall, call_writing_change = max_action_strike(
        chain,
        "ce_action",
        "CALL WRITING",
        "ce_oi_change",
    )

    put_writing_wall, put_writing_change = max_action_strike(
        chain,
        "pe_action",
        "PUT WRITING",
        "pe_oi_change",
    )

    atm_record = atm_row(
        chain,
        atm,
    )

    atm_call = safe_float(
        atm_record.get("ce_ltp")
    ) or 0.0

    atm_put = safe_float(
        atm_record.get("pe_ltp")
    ) or 0.0

    atm_straddle = (
        atm_call + atm_put
    )

    expected_low = (
        spot - atm_straddle
        if spot is not None
        else None
    )

    expected_high = (
        spot + atm_straddle
        if spot is not None
        else None
    )

    pin_score = pinning_score(
        spot,
        max_pain,
        atm_straddle,
    )

    concentration = concentration_score(
        chain
    )

    score, bias, reasons = derive_bias(
        futures,
        option_summary,
        call_writing_change,
        put_writing_change,
    )

    conclusion = bias

    if (
        put_wall is not None
        and call_wall is not None
    ):
        conclusion += (
            f"; key range {put_wall:g} to {call_wall:g}"
        )

    return pd.DataFrame(
        [
            {
                "underlying": "BANKNIFTY",
                "expiry_date": option_summary.get(
                    "expiry_date"
                ),
                "spot_price": spot,
                "atm_strike": atm,
                "atm_call_price": atm_call,
                "atm_put_price": atm_put,
                "atm_straddle_value": atm_straddle,
                "straddle_expected_low": expected_low,
                "straddle_expected_high": expected_high,
                "call_wall": call_wall,
                "call_wall_oi": call_wall_oi,
                "put_wall": put_wall,
                "put_wall_oi": put_wall_oi,
                "fresh_call_writing_wall": call_writing_wall,
                "fresh_call_writing_oi_change": call_writing_change,
                "fresh_put_writing_wall": put_writing_wall,
                "fresh_put_writing_oi_change": put_writing_change,
                "max_pain": max_pain,
                "pinning_score_percent": pin_score,
                "oi_concentration_score": concentration,
                "oi_pcr": safe_float(
                    option_summary.get(
                        "oi_pcr"
                    )
                ),
                "volume_pcr": safe_float(
                    option_summary.get(
                        "volume_pcr"
                    )
                ),
                "futures_term_structure": futures.get(
                    "term_structure"
                ),
                "futures_oi_migration": futures.get(
                    "oi_migration"
                ),
                "futures_rollover_signal": futures.get(
                    "rollover_signal"
                ),
                "near_futures_cycle": futures.get(
                    "near_cycle"
                ),
                "smart_money_score": score,
                "banknifty_bias": bias,
                "conclusion": conclusion,
                "reason_1": (
                    reasons[0]
                    if len(reasons) > 0
                    else ""
                ),
                "reason_2": (
                    reasons[1]
                    if len(reasons) > 1
                    else ""
                ),
                "reason_3": (
                    reasons[2]
                    if len(reasons) > 2
                    else ""
                ),
                "reason_4": (
                    reasons[3]
                    if len(reasons) > 3
                    else ""
                ),
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        ]
    )


def save_outputs(
    summary: pd.DataFrame,
    strikes: pd.DataFrame,
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

    strikes.to_csv(
        STRIKES_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        EXCEL_OUTPUT,
        engine="openpyxl",
    ) as writer:
        summary.to_excel(
            writer,
            sheet_name="BANKNIFTY Summary",
            index=False,
        )

        strikes.to_excel(
            writer,
            sheet_name="Strike Levels",
            index=False,
        )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "summary": summary.to_dict(
                    orient="records"
                ),
                "strikes": strikes.to_dict(
                    orient="records"
                ),
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

    print("\nAQSD BANKNIFTY INSTITUTIONAL LEVELS")
    print("=" * 92)
    print(f"Spot:                 {row['spot_price']}")
    print(f"ATM:                  {row['atm_strike']}")
    print(f"ATM Straddle:         {row['atm_straddle_value']}")
    print(
        f"Expected Range:       "
        f"{row['straddle_expected_low']} "
        f"to {row['straddle_expected_high']}"
    )
    print(f"Put Wall:             {row['put_wall']}")
    print(f"Call Wall:            {row['call_wall']}")
    print(
        f"Fresh Put Writing:    "
        f"{row['fresh_put_writing_wall']}"
    )
    print(
        f"Fresh Call Writing:   "
        f"{row['fresh_call_writing_wall']}"
    )
    print(f"Max Pain:             {row['max_pain']}")
    print(
        f"Pinning Score:        "
        f"{row['pinning_score_percent']}"
    )
    print(
        f"OI Concentration:     "
        f"{row['oi_concentration_score']}"
    )
    print(f"OI PCR:               {row['oi_pcr']}")
    print(
        f"Futures Rollover:     "
        f"{row['futures_rollover_signal']}"
    )
    print("-" * 92)
    print(f"Smart Money Score:    {row['smart_money_score']}")
    print(f"Final Bias:           {row['banknifty_bias']}")
    print(f"Conclusion:           {row['conclusion']}")
    print("=" * 92)
    print(f"Summary CSV:          {SUMMARY_OUTPUT}")
    print(f"Strike CSV:           {STRIKES_OUTPUT}")
    print(f"Excel:                {EXCEL_OUTPUT}")
    print(f"JSON:                 {JSON_OUTPUT}")


def show_status() -> None:
    print("\nAQSD BANKNIFTY INSTITUTIONAL LEVELS STATUS")
    print("=" * 78)
    print("Version: 1.0")

    for label, path in [
        ("Option chain", OPTION_CHAIN_FILE),
        ("Option summary", OPTION_SUMMARY_FILE),
        ("Futures analytics", FUTURES_FILE),
    ]:
        print(
            f"{label:<20}: "
            f"{'FOUND' if path.exists() else 'MISSING'}"
        )

    print(f"Output folder: {OUTPUT_DIR}")
    print("True gamma exposure: NOT YET ENABLED")
    print("Order placement: DISABLED")
    print("AQSD database writes: DISABLED")
    print("Yahoo files modified: NO")
    print("=" * 78)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD BANKNIFTY Institutional Levels Engine."
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    chain, option_summary, futures = load_inputs()

    strike_levels = classify_actions(
        chain
    )

    summary = build_summary(
        strike_levels,
        option_summary,
        futures,
    )

    save_outputs(
        summary,
        strike_levels,
    )

    show_results(
        summary
    )


if __name__ == "__main__":
    main()
