"""
AQSD Professional
Module: FYERS Smart Money Engine
Version: 1.0

Purpose
-------
Combines AQSD futures OI analytics with the latest FYERS option-chain output
to create an actionable derivatives interpretation for one underlying.

Inputs
------
Output/AQSD_FYERS_Futures_OI_Analytics.csv
Output/AQSD_FYERS_Option_Chain_Summary.csv
Output/AQSD_FYERS_Option_Chain.csv

Outputs
-------
Output/AQSD_FYERS_Smart_Money_Summary.csv
Output/AQSD_FYERS_Smart_Money_Strikes.csv
Output/AQSD_FYERS_Smart_Money.xlsx
Output/AQSD_FYERS_Smart_Money.json

Key interpretation
------------------
- Futures rollover signal
- Futures curve structure
- OI migration
- OI PCR and volume PCR
- Maximum call-OI resistance
- Maximum put-OI support
- Max pain
- Dominant call writing
- Dominant put writing
- Call short covering
- Put short covering
- Bullish / bearish / range-bound derivatives score
- Final smart-money conclusion

Safety
------
- No order placement
- No AQSD database writes
- Yahoo files untouched

Examples
--------
python aqsd_fyers_smart_money_engine.py --status
python aqsd_fyers_smart_money_engine.py --run --underlying RELIANCE
python aqsd_fyers_smart_money_engine.py --run --underlying NIFTY
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
OPTION_SUMMARY_FILE = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Summary.csv"
OPTION_CHAIN_FILE = OUTPUT_DIR / "AQSD_FYERS_Option_Chain.csv"

SUMMARY_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Smart_Money_Summary.csv"
STRIKES_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Smart_Money_Strikes.csv"
EXCEL_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Smart_Money.xlsx"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Smart_Money.json"


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


def load_inputs(
    underlying: str,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    missing = [
        str(path)
        for path in [
            FUTURES_FILE,
            OPTION_SUMMARY_FILE,
            OPTION_CHAIN_FILE,
        ]
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Required AQSD output file(s) missing:\n"
            + "\n".join(missing)
        )

    futures = pd.read_csv(
        FUTURES_FILE,
        low_memory=False,
    )

    option_summary = pd.read_csv(
        OPTION_SUMMARY_FILE,
        low_memory=False,
    )

    option_chain = pd.read_csv(
        OPTION_CHAIN_FILE,
        low_memory=False,
    )

    target = str(underlying).strip().upper()

    if "underlying" not in futures.columns:
        raise RuntimeError(
            "Futures analytics file has no 'underlying' column."
        )

    futures_rows = futures[
        futures["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        == target
    ]

    if futures_rows.empty:
        raise RuntimeError(
            f"No futures analytics row found for {target}."
        )

    if "underlying" not in option_summary.columns:
        raise RuntimeError(
            "Option summary file has no 'underlying' column."
        )

    option_rows = option_summary[
        option_summary["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        == target
    ]

    if option_rows.empty:
        available = ", ".join(
            option_summary["underlying"]
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

        raise RuntimeError(
            f"Latest option-chain output is not for {target}. "
            f"Available: {available or 'none'}.\n"
            f"Run option-chain analytics for {target} first."
        )

    return (
        futures_rows.iloc[0],
        option_rows.iloc[0],
        option_chain.copy(),
    )


def numeric_series(
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


def classify_strikes(
    chain: pd.DataFrame,
) -> pd.DataFrame:
    result = chain.copy()

    ce_change = numeric_series(
        result,
        "ce_change_percent",
    )
    ce_oi_change = numeric_series(
        result,
        "ce_oi_change",
    )
    pe_change = numeric_series(
        result,
        "pe_change_percent",
    )
    pe_oi_change = numeric_series(
        result,
        "pe_oi_change",
    )

    def label(
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

    result["ce_smart_money_action"] = [
        label(pc, oi, "CALL")
        for pc, oi in zip(
            ce_change,
            ce_oi_change,
        )
    ]

    result["pe_smart_money_action"] = [
        label(pc, oi, "PUT")
        for pc, oi in zip(
            pe_change,
            pe_oi_change,
        )
    ]

    result["ce_oi_change_abs"] = (
        numeric_series(
            result,
            "ce_oi_change",
        ).abs()
    )

    result["pe_oi_change_abs"] = (
        numeric_series(
            result,
            "pe_oi_change",
        ).abs()
    )

    return result


def top_strike(
    frame: pd.DataFrame,
    action_column: str,
    target_action: str,
    magnitude_column: str,
) -> tuple[float | None, float | None]:
    rows = frame[
        frame[action_column] == target_action
    ].copy()

    if rows.empty:
        return None, None

    rows[magnitude_column] = pd.to_numeric(
        rows[magnitude_column],
        errors="coerce",
    ).fillna(0.0)

    row = rows.sort_values(
        magnitude_column,
        ascending=False,
    ).iloc[0]

    return (
        safe_float(row.get("strike_price")),
        safe_float(row.get(magnitude_column)),
    )


def score_futures(
    futures: pd.Series,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    rollover = str(
        futures.get(
            "rollover_signal",
            "",
        )
    ).upper()

    migration = str(
        futures.get(
            "oi_migration",
            "",
        )
    ).upper()

    term_structure = str(
        futures.get(
            "term_structure",
            "",
        )
    ).upper()

    near_cycle = str(
        futures.get(
            "near_cycle",
            "",
        )
    ).upper()

    next_cycle = str(
        futures.get(
            "next_cycle",
            "",
        )
    ).upper()

    if "BULLISH" in rollover:
        score += 3
        reasons.append("Bullish futures rollover")

    if "BEARISH" in rollover:
        score -= 3
        reasons.append("Bearish futures rollover")

    if near_cycle == "LONG BUILDUP":
        score += 2
        reasons.append("Near-month long buildup")

    if near_cycle == "SHORT BUILDUP":
        score -= 2
        reasons.append("Near-month short buildup")

    if near_cycle == "SHORT COVERING":
        score += 1
        reasons.append("Near-month short covering")

    if near_cycle == "LONG UNWINDING":
        score -= 1
        reasons.append("Near-month long unwinding")

    if next_cycle == "LONG BUILDUP":
        score += 1
        reasons.append("Next-month long buildup")

    if next_cycle == "SHORT BUILDUP":
        score -= 1
        reasons.append("Next-month short buildup")

    if "ROLLOVER TO NEXT" in migration:
        reasons.append("OI migrating to forward contracts")

    if term_structure == "CONTANGO":
        reasons.append("Futures curve in contango")

    if term_structure == "BACKWARDATION":
        reasons.append("Futures curve in backwardation")

    return score, reasons


def score_options(
    option_summary: pd.Series,
    strikes: pd.DataFrame,
) -> tuple[int, list[str], dict[str, Any]]:
    score = 0
    reasons: list[str] = []

    oi_pcr = safe_float(
        option_summary.get("oi_pcr")
    )

    volume_pcr = safe_float(
        option_summary.get("volume_pcr")
    )

    total_call_change = safe_float(
        option_summary.get(
            "total_call_oi_change"
        )
    ) or 0.0

    total_put_change = safe_float(
        option_summary.get(
            "total_put_oi_change"
        )
    ) or 0.0

    if oi_pcr is not None:
        if oi_pcr >= 1.20:
            score += 2
            reasons.append("Put OI dominates call OI")
        elif oi_pcr <= 0.80:
            score -= 2
            reasons.append("Call OI dominates put OI")
        else:
            reasons.append("OI PCR is balanced")

    if volume_pcr is not None:
        if volume_pcr >= 1.20:
            score += 1
            reasons.append("Put volume dominates")
        elif volume_pcr <= 0.80:
            score -= 1
            reasons.append("Call volume dominates")

    if total_put_change > total_call_change:
        score += 1
        reasons.append("Put OI addition exceeds call OI addition")
    elif total_call_change > total_put_change:
        score -= 1
        reasons.append("Call OI addition exceeds put OI addition")

    call_writing_strike, call_writing_size = top_strike(
        strikes,
        "ce_smart_money_action",
        "CALL WRITING",
        "ce_oi_change_abs",
    )

    put_writing_strike, put_writing_size = top_strike(
        strikes,
        "pe_smart_money_action",
        "PUT WRITING",
        "pe_oi_change_abs",
    )

    call_covering_strike, call_covering_size = top_strike(
        strikes,
        "ce_smart_money_action",
        "CALL SHORT COVERING",
        "ce_oi_change_abs",
    )

    put_covering_strike, put_covering_size = top_strike(
        strikes,
        "pe_smart_money_action",
        "PUT SHORT COVERING",
        "pe_oi_change_abs",
    )

    if put_writing_size and (
        not call_writing_size
        or put_writing_size > call_writing_size
    ):
        score += 2
        reasons.append("Put writing is stronger than call writing")

    if call_writing_size and (
        not put_writing_size
        or call_writing_size > put_writing_size
    ):
        score -= 2
        reasons.append("Call writing is stronger than put writing")

    if call_covering_size and call_covering_size > 0:
        score += 1
        reasons.append("Call writers are covering")

    if put_covering_size and put_covering_size > 0:
        score -= 1
        reasons.append("Put writers are covering")

    details = {
        "dominant_call_writing_strike": call_writing_strike,
        "dominant_call_writing_oi_change": call_writing_size,
        "dominant_put_writing_strike": put_writing_strike,
        "dominant_put_writing_oi_change": put_writing_size,
        "dominant_call_covering_strike": call_covering_strike,
        "dominant_call_covering_oi_change": call_covering_size,
        "dominant_put_covering_strike": put_covering_strike,
        "dominant_put_covering_oi_change": put_covering_size,
    }

    return score, reasons, details


def final_bias(score: int) -> str:
    if score >= 6:
        return "STRONG BULLISH"

    if score >= 3:
        return "BULLISH"

    if score <= -6:
        return "STRONG BEARISH"

    if score <= -3:
        return "BEARISH"

    return "RANGE-BOUND / MIXED"


def build_summary(
    futures: pd.Series,
    option_summary: pd.Series,
    strikes: pd.DataFrame,
) -> pd.DataFrame:
    futures_score, futures_reasons = score_futures(
        futures
    )

    options_score, options_reasons, details = score_options(
        option_summary,
        strikes,
    )

    total_score = futures_score + options_score

    support = safe_float(
        option_summary.get(
            "maximum_put_oi_support"
        )
    )

    resistance = safe_float(
        option_summary.get(
            "maximum_call_oi_resistance"
        )
    )

    spot = safe_float(
        option_summary.get("spot_price")
    )

    max_pain = safe_float(
        option_summary.get("max_pain")
    )

    range_width = None

    if (
        support is not None
        and resistance is not None
    ):
        range_width = resistance - support

    all_reasons = futures_reasons + options_reasons

    conclusion = final_bias(
        total_score
    )

    if support is not None and resistance is not None:
        conclusion_text = (
            f"{conclusion}; expected derivatives range "
            f"{support:g} to {resistance:g}."
        )
    else:
        conclusion_text = conclusion

    row = {
        "underlying": option_summary.get("underlying"),
        "expiry_date": option_summary.get("expiry_date"),
        "spot_price": spot,
        "atm_strike": safe_float(
            option_summary.get("atm_strike")
        ),
        "support": support,
        "resistance": resistance,
        "range_width": range_width,
        "max_pain": max_pain,
        "oi_pcr": safe_float(
            option_summary.get("oi_pcr")
        ),
        "volume_pcr": safe_float(
            option_summary.get("volume_pcr")
        ),
        "term_structure": futures.get(
            "term_structure"
        ),
        "oi_migration": futures.get(
            "oi_migration"
        ),
        "futures_rollover_signal": futures.get(
            "rollover_signal"
        ),
        "near_cycle": futures.get(
            "near_cycle"
        ),
        "next_cycle": futures.get(
            "next_cycle"
        ),
        "far_cycle": futures.get(
            "far_cycle"
        ),
        "futures_score": futures_score,
        "options_score": options_score,
        "total_smart_money_score": total_score,
        "smart_money_bias": conclusion,
        "conclusion": conclusion_text,
        "reason_1": all_reasons[0] if len(all_reasons) > 0 else "",
        "reason_2": all_reasons[1] if len(all_reasons) > 1 else "",
        "reason_3": all_reasons[2] if len(all_reasons) > 2 else "",
        "reason_4": all_reasons[3] if len(all_reasons) > 3 else "",
        "reason_5": all_reasons[4] if len(all_reasons) > 4 else "",
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    row.update(details)

    return pd.DataFrame([row])


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
            sheet_name="Smart Money Summary",
            index=False,
        )

        strikes.to_excel(
            writer,
            sheet_name="Strike Intelligence",
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

    print("\nAQSD FYERS SMART MONEY ENGINE")
    print("=" * 90)
    print(f"Underlying:       {row['underlying']}")
    print(f"Expiry:           {row['expiry_date']}")
    print(f"Spot:             {row['spot_price']}")
    print(f"ATM:              {row['atm_strike']}")
    print(f"Support:          {row['support']}")
    print(f"Resistance:       {row['resistance']}")
    print(f"Max Pain:         {row['max_pain']}")
    print(f"OI PCR:           {row['oi_pcr']}")
    print(f"Volume PCR:       {row['volume_pcr']}")
    print(f"Term Structure:   {row['term_structure']}")
    print(f"OI Migration:     {row['oi_migration']}")
    print(f"Rollover Signal:  {row['futures_rollover_signal']}")
    print("-" * 90)
    print(f"Futures Score:    {row['futures_score']}")
    print(f"Options Score:    {row['options_score']}")
    print(f"Total Score:      {row['total_smart_money_score']}")
    print(f"Final Bias:       {row['smart_money_bias']}")
    print(f"Conclusion:       {row['conclusion']}")
    print("=" * 90)
    print(f"Summary CSV:      {SUMMARY_OUTPUT}")
    print(f"Strike CSV:       {STRIKES_OUTPUT}")
    print(f"Excel:            {EXCEL_OUTPUT}")
    print(f"JSON:             {JSON_OUTPUT}")


def show_status() -> None:
    print("\nAQSD FYERS SMART MONEY ENGINE STATUS")
    print("=" * 78)
    print("Version: 1.0")

    for label, path in [
        ("Futures analytics", FUTURES_FILE),
        ("Option summary", OPTION_SUMMARY_FILE),
        ("Option chain", OPTION_CHAIN_FILE),
    ]:
        print(
            f"{label:<20}: "
            f"{'FOUND' if path.exists() else 'MISSING'}"
        )

    print(f"Output folder: {OUTPUT_DIR}")
    print("Order placement: DISABLED")
    print("AQSD database writes: DISABLED")
    print("Yahoo files modified: NO")
    print("=" * 78)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Smart Money Engine."
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
        help="Underlying such as RELIANCE or NIFTY.",
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
            "python aqsd_fyers_smart_money_engine.py "
            "--run --underlying RELIANCE"
        )

    futures, option_summary, option_chain = load_inputs(
        args.underlying
    )

    strike_intelligence = classify_strikes(
        option_chain
    )

    summary = build_summary(
        futures,
        option_summary,
        strike_intelligence,
    )

    save_outputs(
        summary,
        strike_intelligence,
    )

    show_results(
        summary
    )


if __name__ == "__main__":
    main()
