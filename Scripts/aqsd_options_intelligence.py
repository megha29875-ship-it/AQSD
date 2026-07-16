"""
AQSD Professional
Module: Advanced Options Intelligence Engine
Version: 1.0

Purpose
-------
Calculates advanced options intelligence for one underlying using AQSD's
existing FYERS outputs.

Key outputs
-----------
- PCR OI
- PCR Change in OI
- PCR Volume
- ATM-zone PCR
- Weighted PCR
- Modified PCR
- Positional and fresh call/put walls
- Secondary walls
- Wall shifts
- Max-pain shift and pinning score
- OI concentration and dispersion
- IV / HV analytics when source columns are available
- Bullish reversal probability
- Bearish reversal probability
- Continuation probability
- Explainable conclusion
- Historical snapshot storage

Inputs
------
Output/AQSD_FYERS_Option_Chain.csv
Output/AQSD_FYERS_Option_Chain_Summary.csv
Output/AQSD_FYERS_Futures_OI_Analytics.csv

Outputs
-------
Output/AQSD_Options_Intelligence.csv
Output/AQSD_Options_Intelligence.json
Output/AQSD_Options_Intelligence_History.csv
Output/AQSD_Options_Intelligence_Walls.csv

Safety
------
- No order placement
- No database writes
- Yahoo files untouched

Examples
--------
python aqsd_options_intelligence.py --status
python aqsd_options_intelligence.py --run --underlying BANKNIFTY
python aqsd_options_intelligence.py --run --underlying NIFTY --atm-strikes 5
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

SUMMARY_OUTPUT = OUTPUT_DIR / "AQSD_Options_Intelligence.csv"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_Options_Intelligence.json"
HISTORY_OUTPUT = OUTPUT_DIR / "AQSD_Options_Intelligence_History.csv"
WALLS_OUTPUT = OUTPUT_DIR / "AQSD_Options_Intelligence_Walls.csv"


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


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype=float)

    return pd.to_numeric(
        frame[column],
        errors="coerce",
    ).fillna(0.0)


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file missing:\n{path}")

    return pd.read_csv(path, low_memory=False)


def select_underlying_row(
    frame: pd.DataFrame,
    underlying: str,
) -> pd.Series:
    if "underlying" not in frame.columns:
        raise RuntimeError(
            f"File has no 'underlying' column: {list(frame.columns)}"
        )

    target = underlying.strip().upper()

    rows = frame[
        frame["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(target)
    ]

    if rows.empty:
        available = ", ".join(
            frame["underlying"]
            .astype(str)
            .drop_duplicates()
            .head(20)
            .tolist()
        )

        raise RuntimeError(
            f"No row found for {target}. Available: {available or 'none'}"
        )

    return rows.iloc[0]


def load_inputs(
    underlying: str,
) -> tuple[pd.DataFrame, pd.Series, pd.Series | None]:
    chain = load_csv(OPTION_CHAIN_FILE)
    summary = load_csv(OPTION_SUMMARY_FILE)

    summary_row = select_underlying_row(
        summary,
        underlying,
    )

    if "underlying" in chain.columns:
        target = underlying.strip().upper()

        chain_rows = chain[
            chain["underlying"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq(target)
        ].copy()

        if not chain_rows.empty:
            chain = chain_rows

    futures_row = None

    if FUTURES_FILE.exists():
        futures = pd.read_csv(
            FUTURES_FILE,
            low_memory=False,
        )

        try:
            futures_row = select_underlying_row(
                futures,
                underlying,
            )
        except RuntimeError:
            futures_row = None

    return chain, summary_row, futures_row


def sum_positive(series: pd.Series) -> float:
    return float(series[series > 0].sum())


def ratio(
    numerator: float,
    denominator: float,
) -> float | None:
    if denominator <= 0:
        return None

    return numerator / denominator


def nearest_strikes(
    chain: pd.DataFrame,
    atm: float,
    count_each_side: int,
) -> pd.DataFrame:
    strikes = sorted(
        pd.to_numeric(
            chain["strike_price"],
            errors="coerce",
        )
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    if not strikes:
        return chain.copy()

    nearest = min(
        strikes,
        key=lambda value: abs(value - atm),
    )

    index = strikes.index(nearest)

    selected = set(
        strikes[
            max(0, index - count_each_side):
            min(len(strikes), index + count_each_side + 1)
        ]
    )

    return chain[
        pd.to_numeric(
            chain["strike_price"],
            errors="coerce",
        ).isin(selected)
    ].copy()


def top_two_walls(
    chain: pd.DataFrame,
    value_column: str,
) -> list[dict[str, float | None]]:
    if value_column not in chain.columns:
        return [
            {"strike": None, "value": None},
            {"strike": None, "value": None},
        ]

    work = chain[
        ["strike_price", value_column]
    ].copy()

    work["strike_price"] = pd.to_numeric(
        work["strike_price"],
        errors="coerce",
    )

    work[value_column] = pd.to_numeric(
        work[value_column],
        errors="coerce",
    )

    work = (
        work.dropna()
        .sort_values(value_column, ascending=False)
        .drop_duplicates("strike_price")
        .head(2)
    )

    result = [
        {
            "strike": safe_float(row["strike_price"]),
            "value": safe_float(row[value_column]),
        }
        for _, row in work.iterrows()
    ]

    while len(result) < 2:
        result.append(
            {
                "strike": None,
                "value": None,
            }
        )

    return result


def fresh_wall(
    chain: pd.DataFrame,
    change_column: str,
) -> dict[str, float | None]:
    if change_column not in chain.columns:
        return {
            "strike": None,
            "change": None,
        }

    work = chain[
        ["strike_price", change_column]
    ].copy()

    work["strike_price"] = pd.to_numeric(
        work["strike_price"],
        errors="coerce",
    )

    work[change_column] = pd.to_numeric(
        work[change_column],
        errors="coerce",
    )

    work = work[
        work[change_column] > 0
    ].dropna()

    if work.empty:
        return {
            "strike": None,
            "change": None,
        }

    row = work.loc[
        work[change_column].idxmax()
    ]

    return {
        "strike": safe_float(row["strike_price"]),
        "change": safe_float(row[change_column]),
    }


def concentration_metrics(
    chain: pd.DataFrame,
) -> dict[str, float | None]:
    ce = numeric(
        chain,
        "ce_open_interest",
    )

    pe = numeric(
        chain,
        "pe_open_interest",
    )

    ce_total = float(ce.sum())
    pe_total = float(pe.sum())

    ce_top3 = float(ce.nlargest(3).sum())
    pe_top3 = float(pe.nlargest(3).sum())

    ce_concentration = (
        ce_top3 / ce_total * 100
        if ce_total > 0
        else None
    )

    pe_concentration = (
        pe_top3 / pe_total * 100
        if pe_total > 0
        else None
    )

    combined = None

    values = [
        value
        for value in [
            ce_concentration,
            pe_concentration,
        ]
        if value is not None
    ]

    if values:
        combined = sum(values) / len(values)

    dispersion = (
        100 - combined
        if combined is not None
        else None
    )

    return {
        "call_top3_concentration_percent": ce_concentration,
        "put_top3_concentration_percent": pe_concentration,
        "combined_concentration_percent": combined,
        "dispersion_percent": dispersion,
    }


def detect_iv_columns(
    chain: pd.DataFrame,
) -> tuple[str | None, str | None]:
    ce_candidates = [
        "ce_iv",
        "call_iv",
        "ce_implied_volatility",
    ]

    pe_candidates = [
        "pe_iv",
        "put_iv",
        "pe_implied_volatility",
    ]

    ce_column = next(
        (
            column
            for column in ce_candidates
            if column in chain.columns
        ),
        None,
    )

    pe_column = next(
        (
            column
            for column in pe_candidates
            if column in chain.columns
        ),
        None,
    )

    return ce_column, pe_column


def iv_hv_metrics(
    chain: pd.DataFrame,
    atm: float,
) -> dict[str, Any]:
    ce_column, pe_column = detect_iv_columns(
        chain
    )

    hv_candidates = [
        "historical_volatility",
        "hv",
        "realised_volatility",
    ]

    hv_column = next(
        (
            column
            for column in hv_candidates
            if column in chain.columns
        ),
        None,
    )

    result = {
        "atm_call_iv": None,
        "atm_put_iv": None,
        "atm_average_iv": None,
        "weighted_iv": None,
        "historical_volatility": None,
        "iv_hv_spread": None,
        "iv_skew": None,
        "iv_regime": "NO IV DATA",
    }

    if not ce_column and not pe_column:
        return result

    work = chain.copy()

    work["strike_price"] = pd.to_numeric(
        work["strike_price"],
        errors="coerce",
    )

    nearest_index = (
        work["strike_price"]
        .sub(atm)
        .abs()
        .idxmin()
    )

    atm_row = work.loc[
        nearest_index
    ]

    call_iv = (
        safe_float(atm_row.get(ce_column))
        if ce_column
        else None
    )

    put_iv = (
        safe_float(atm_row.get(pe_column))
        if pe_column
        else None
    )

    iv_values = [
        value
        for value in [
            call_iv,
            put_iv,
        ]
        if value is not None
    ]

    average_iv = (
        sum(iv_values) / len(iv_values)
        if iv_values
        else None
    )

    weighted_values: list[float] = []

    for column in [
        ce_column,
        pe_column,
    ]:
        if not column:
            continue

        values = pd.to_numeric(
            work[column],
            errors="coerce",
        ).dropna()

        weighted_values.extend(
            values.tolist()
        )

    weighted_iv = (
        sum(weighted_values) / len(weighted_values)
        if weighted_values
        else None
    )

    hv = None

    if hv_column:
        hv_values = pd.to_numeric(
            work[hv_column],
            errors="coerce",
        ).dropna()

        if not hv_values.empty:
            hv = float(
                hv_values.iloc[-1]
            )

    spread = (
        average_iv - hv
        if average_iv is not None
        and hv is not None
        else None
    )

    skew = (
        put_iv - call_iv
        if put_iv is not None
        and call_iv is not None
        else None
    )

    if spread is None:
        regime = "IV AVAILABLE / HV MISSING"
    elif spread >= 5:
        regime = "IV EXPENSIVE"
    elif spread <= -2:
        regime = "IV CHEAP"
    else:
        regime = "IV FAIR"

    result.update(
        {
            "atm_call_iv": call_iv,
            "atm_put_iv": put_iv,
            "atm_average_iv": average_iv,
            "weighted_iv": weighted_iv,
            "historical_volatility": hv,
            "iv_hv_spread": spread,
            "iv_skew": skew,
            "iv_regime": regime,
        }
    )

    return result


def latest_previous_snapshot(
    underlying: str,
) -> pd.Series | None:
    if not HISTORY_OUTPUT.exists():
        return None

    history = pd.read_csv(
        HISTORY_OUTPUT,
        low_memory=False,
    )

    if history.empty or "underlying" not in history.columns:
        return None

    rows = history[
        history["underlying"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(underlying.strip().upper())
    ]

    if rows.empty:
        return None

    return rows.iloc[-1]


def modified_pcr(
    oi_pcr: float | None,
    change_pcr: float | None,
    volume_pcr: float | None,
    atm_pcr: float | None,
) -> float | None:
    weighted = [
        (oi_pcr, 0.40),
        (change_pcr, 0.30),
        (volume_pcr, 0.20),
        (atm_pcr, 0.10),
    ]

    available = [
        (value, weight)
        for value, weight in weighted
        if value is not None
    ]

    if not available:
        return None

    total_weight = sum(
        weight
        for _, weight in available
    )

    return sum(
        value * weight
        for value, weight in available
    ) / total_weight


def weighted_pcr(
    oi_pcr: float | None,
    change_pcr: float | None,
) -> float | None:
    available = [
        (oi_pcr, 0.60),
        (change_pcr, 0.40),
    ]

    valid = [
        item
        for item in available
        if item[0] is not None
    ]

    if not valid:
        return None

    total_weight = sum(
        weight
        for _, weight in valid
    )

    return sum(
        value * weight
        for value, weight in valid
    ) / total_weight


def score_probabilities(
    current: dict[str, Any],
    previous: pd.Series | None,
    futures: pd.Series | None,
) -> dict[str, Any]:
    bullish = 20.0
    bearish = 20.0
    continuation = 35.0
    reasons: list[str] = []

    spot = safe_float(
        current.get("spot_price")
    )

    modified = safe_float(
        current.get("modified_pcr")
    )

    oi_pcr = safe_float(
        current.get("oi_pcr")
    )

    iv_spread = safe_float(
        current.get("iv_hv_spread")
    )

    put_wall = safe_float(
        current.get("positional_put_wall")
    )

    call_wall = safe_float(
        current.get("positional_call_wall")
    )

    fresh_put = safe_float(
        current.get("fresh_put_wall")
    )

    fresh_call = safe_float(
        current.get("fresh_call_wall")
    )

    if modified is not None:
        if modified <= 0.70:
            bearish += 15
            reasons.append(
                "Modified PCR shows call-side dominance"
            )

        elif modified >= 1.30:
            bullish += 15
            reasons.append(
                "Modified PCR shows put-side dominance"
            )

    if oi_pcr is not None:
        if oi_pcr <= 0.65:
            bullish += 8
            bearish += 8
            reasons.append(
                "Extreme low PCR raises reversal risk"
            )

        elif oi_pcr >= 1.50:
            bullish += 8
            bearish += 8
            reasons.append(
                "Extreme high PCR raises reversal risk"
            )

    if spot is not None and put_wall is not None:
        distance = abs(
            spot - put_wall
        )

        if distance <= max(100, spot * 0.003):
            bullish += 12
            reasons.append(
                "Price is close to positional put wall"
            )

    if spot is not None and call_wall is not None:
        distance = abs(
            call_wall - spot
        )

        if distance <= max(100, spot * 0.003):
            bearish += 12
            reasons.append(
                "Price is close to positional call wall"
            )

    if fresh_put is not None:
        bullish += 7
        reasons.append(
            "Fresh put wall is present"
        )

    if fresh_call is not None:
        bearish += 7
        reasons.append(
            "Fresh call wall is present"
        )

    if iv_spread is not None:
        if iv_spread >= 5:
            bullish += 5
            bearish += 5
            continuation -= 5
            reasons.append(
                "IV is materially above HV; volatility contraction risk"
            )

        elif iv_spread <= -2:
            continuation += 8
            reasons.append(
                "IV is below HV; volatility expansion risk"
            )

    if futures is not None:
        near_cycle = str(
            futures.get(
                "near_cycle",
                "",
            )
        ).upper()

        rollover = str(
            futures.get(
                "rollover_signal",
                "",
            )
        ).upper()

        if near_cycle == "SHORT COVERING":
            bullish += 12
            reasons.append(
                "Near futures show short covering"
            )

        elif near_cycle == "LONG BUILDUP":
            bullish += 10
            continuation += 8
            reasons.append(
                "Near futures show long buildup"
            )

        elif near_cycle == "SHORT BUILDUP":
            bearish += 10
            continuation += 8
            reasons.append(
                "Near futures show short buildup"
            )

        elif near_cycle == "LONG UNWINDING":
            bearish += 8
            reasons.append(
                "Near futures show long unwinding"
            )

        if "BULLISH" in rollover:
            bullish += 8

        if "BEARISH" in rollover:
            bearish += 8

    pcr_trend = "NO HISTORY"
    wall_shift_signal = "NO HISTORY"
    max_pain_shift = None

    if previous is not None:
        previous_modified = safe_float(
            previous.get("modified_pcr")
        )

        if (
            previous_modified is not None
            and modified is not None
        ):
            change = modified - previous_modified

            if change > 0.03:
                pcr_trend = "RISING"
                bullish += 10
                reasons.append(
                    "Modified PCR is rising"
                )

            elif change < -0.03:
                pcr_trend = "FALLING"
                bearish += 10
                reasons.append(
                    "Modified PCR is falling"
                )

            else:
                pcr_trend = "FLAT"

        previous_call_wall = safe_float(
            previous.get("positional_call_wall")
        )

        previous_put_wall = safe_float(
            previous.get("positional_put_wall")
        )

        call_shift = (
            call_wall - previous_call_wall
            if call_wall is not None
            and previous_call_wall is not None
            else None
        )

        put_shift = (
            put_wall - previous_put_wall
            if put_wall is not None
            and previous_put_wall is not None
            else None
        )

        if call_shift is not None and call_shift < 0:
            bearish += 8
            wall_shift_signal = "CALL WALL MOVING DOWN"

        elif put_shift is not None and put_shift > 0:
            bullish += 8
            wall_shift_signal = "PUT WALL MOVING UP"

        else:
            wall_shift_signal = "STABLE / MIXED"

        previous_max_pain = safe_float(
            previous.get("max_pain")
        )

        current_max_pain = safe_float(
            current.get("max_pain")
        )

        if (
            previous_max_pain is not None
            and current_max_pain is not None
        ):
            max_pain_shift = (
                current_max_pain
                - previous_max_pain
            )

            if max_pain_shift > 0:
                bullish += 5

            elif max_pain_shift < 0:
                bearish += 5

    bullish = min(
        95.0,
        max(5.0, bullish),
    )

    bearish = min(
        95.0,
        max(5.0, bearish),
    )

    continuation = min(
        95.0,
        max(5.0, continuation),
    )

    if bullish >= bearish + 12:
        reversal_signal = "BULLISH REVERSAL WATCH"

    elif bearish >= bullish + 12:
        reversal_signal = "BEARISH REVERSAL WATCH"

    else:
        reversal_signal = "NO CLEAR REVERSAL"

    return {
        "bullish_reversal_probability": round(
            bullish,
            1,
        ),
        "bearish_reversal_probability": round(
            bearish,
            1,
        ),
        "continuation_probability": round(
            continuation,
            1,
        ),
        "reversal_signal": reversal_signal,
        "pcr_trend": pcr_trend,
        "wall_shift_signal": wall_shift_signal,
        "max_pain_shift": max_pain_shift,
        "reason_1": reasons[0] if len(reasons) > 0 else "",
        "reason_2": reasons[1] if len(reasons) > 1 else "",
        "reason_3": reasons[2] if len(reasons) > 2 else "",
        "reason_4": reasons[3] if len(reasons) > 3 else "",
        "reason_5": reasons[4] if len(reasons) > 4 else "",
    }


def calculate(
    underlying: str,
    atm_strikes: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    chain, summary, futures = load_inputs(
        underlying
    )

    atm = safe_float(
        summary.get("atm_strike")
    )

    spot = safe_float(
        summary.get("spot_price")
    )

    if atm is None:
        raise RuntimeError(
            "ATM strike is missing from option summary."
        )

    ce_oi = numeric(
        chain,
        "ce_open_interest",
    )

    pe_oi = numeric(
        chain,
        "pe_open_interest",
    )

    ce_change = numeric(
        chain,
        "ce_oi_change",
    )

    pe_change = numeric(
        chain,
        "pe_oi_change",
    )

    ce_volume = numeric(
        chain,
        "ce_volume",
    )

    pe_volume = numeric(
        chain,
        "pe_volume",
    )

    oi_pcr = ratio(
        float(pe_oi.sum()),
        float(ce_oi.sum()),
    )

    change_pcr = ratio(
        sum_positive(pe_change),
        sum_positive(ce_change),
    )

    volume_pcr = ratio(
        float(pe_volume.sum()),
        float(ce_volume.sum()),
    )

    atm_chain = nearest_strikes(
        chain,
        atm,
        atm_strikes,
    )

    atm_pcr = ratio(
        float(
            numeric(
                atm_chain,
                "pe_open_interest",
            ).sum()
        ),
        float(
            numeric(
                atm_chain,
                "ce_open_interest",
            ).sum()
        ),
    )

    modified = modified_pcr(
        oi_pcr,
        change_pcr,
        volume_pcr,
        atm_pcr,
    )

    weighted = weighted_pcr(
        oi_pcr,
        change_pcr,
    )

    call_walls = top_two_walls(
        chain,
        "ce_open_interest",
    )

    put_walls = top_two_walls(
        chain,
        "pe_open_interest",
    )

    fresh_call = fresh_wall(
        chain,
        "ce_oi_change",
    )

    fresh_put = fresh_wall(
        chain,
        "pe_oi_change",
    )

    concentration = concentration_metrics(
        chain
    )

    iv_metrics = iv_hv_metrics(
        chain,
        atm,
    )

    max_pain = safe_float(
        summary.get("max_pain")
    )

    pinning = None

    if (
        spot is not None
        and max_pain is not None
    ):
        distance = abs(
            spot - max_pain
        )

        reference = max(
            abs(spot) * 0.01,
            1,
        )

        pinning = max(
            0.0,
            100.0
            * (
                1
                - min(
                    distance / reference,
                    1,
                )
            ),
        )

    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "underlying": underlying.strip().upper(),
        "spot_price": spot,
        "atm_strike": atm,
        "expiry_date": summary.get(
            "expiry_date"
        ),
        "oi_pcr": oi_pcr,
        "change_in_oi_pcr": change_pcr,
        "volume_pcr": volume_pcr,
        "atm_zone_pcr": atm_pcr,
        "weighted_pcr": weighted,
        "modified_pcr": modified,
        "positional_call_wall": call_walls[0]["strike"],
        "positional_call_wall_oi": call_walls[0]["value"],
        "secondary_call_wall": call_walls[1]["strike"],
        "secondary_call_wall_oi": call_walls[1]["value"],
        "fresh_call_wall": fresh_call["strike"],
        "fresh_call_wall_oi_change": fresh_call["change"],
        "positional_put_wall": put_walls[0]["strike"],
        "positional_put_wall_oi": put_walls[0]["value"],
        "secondary_put_wall": put_walls[1]["strike"],
        "secondary_put_wall_oi": put_walls[1]["value"],
        "fresh_put_wall": fresh_put["strike"],
        "fresh_put_wall_oi_change": fresh_put["change"],
        "max_pain": max_pain,
        "distance_from_max_pain": (
            spot - max_pain
            if spot is not None
            and max_pain is not None
            else None
        ),
        "pinning_probability": pinning,
    }

    result.update(
        concentration
    )

    result.update(
        iv_metrics
    )

    previous = latest_previous_snapshot(
        underlying
    )

    probabilities = score_probabilities(
        result,
        previous,
        futures,
    )

    result.update(
        probabilities
    )

    summary_frame = pd.DataFrame(
        [result]
    )

    wall_rows = pd.DataFrame(
        [
            {
                "wall_type": "POSITIONAL CALL",
                "strike": call_walls[0]["strike"],
                "value": call_walls[0]["value"],
            },
            {
                "wall_type": "SECONDARY CALL",
                "strike": call_walls[1]["strike"],
                "value": call_walls[1]["value"],
            },
            {
                "wall_type": "FRESH CALL",
                "strike": fresh_call["strike"],
                "value": fresh_call["change"],
            },
            {
                "wall_type": "POSITIONAL PUT",
                "strike": put_walls[0]["strike"],
                "value": put_walls[0]["value"],
            },
            {
                "wall_type": "SECONDARY PUT",
                "strike": put_walls[1]["strike"],
                "value": put_walls[1]["value"],
            },
            {
                "wall_type": "FRESH PUT",
                "strike": fresh_put["strike"],
                "value": fresh_put["change"],
            },
        ]
    )

    wall_rows.insert(
        0,
        "underlying",
        underlying.strip().upper(),
    )

    wall_rows.insert(
        0,
        "generated_at",
        result["generated_at"],
    )

    return summary_frame, wall_rows


def save_outputs(
    summary: pd.DataFrame,
    walls: pd.DataFrame,
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

    walls.to_csv(
        WALLS_OUTPUT,
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
                "summary": summary.to_dict(
                    orient="records"
                ),
                "walls": walls.to_dict(
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

    print("\nAQSD ADVANCED OPTIONS INTELLIGENCE")
    print("=" * 92)
    print(f"Underlying:              {row['underlying']}")
    print(f"Spot:                    {row['spot_price']}")
    print(f"ATM:                     {row['atm_strike']}")
    print(f"OI PCR:                  {row['oi_pcr']}")
    print(f"Change-in-OI PCR:        {row['change_in_oi_pcr']}")
    print(f"Volume PCR:              {row['volume_pcr']}")
    print(f"ATM-zone PCR:            {row['atm_zone_pcr']}")
    print(f"Modified PCR:            {row['modified_pcr']}")
    print("-" * 92)
    print(f"Positional Call Wall:    {row['positional_call_wall']}")
    print(f"Fresh Call Wall:         {row['fresh_call_wall']}")
    print(f"Positional Put Wall:     {row['positional_put_wall']}")
    print(f"Fresh Put Wall:          {row['fresh_put_wall']}")
    print(f"Max Pain:                {row['max_pain']}")
    print(f"Pinning Probability:     {row['pinning_probability']}")
    print("-" * 92)
    print(f"IV Regime:               {row['iv_regime']}")
    print(f"PCR Trend:               {row['pcr_trend']}")
    print(f"Wall Shift:              {row['wall_shift_signal']}")
    print(f"Reversal Signal:         {row['reversal_signal']}")
    print(
        f"Bullish Reversal Prob.:  "
        f"{row['bullish_reversal_probability']}%"
    )
    print(
        f"Bearish Reversal Prob.:  "
        f"{row['bearish_reversal_probability']}%"
    )
    print(
        f"Continuation Prob.:      "
        f"{row['continuation_probability']}%"
    )
    print("=" * 92)
    print(f"Summary CSV:             {SUMMARY_OUTPUT}")
    print(f"History CSV:             {HISTORY_OUTPUT}")
    print(f"Walls CSV:               {WALLS_OUTPUT}")
    print(f"JSON:                    {JSON_OUTPUT}")


def show_status() -> None:
    print("\nAQSD ADVANCED OPTIONS INTELLIGENCE STATUS")
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
    print("IV/HV calculation: CONDITIONAL ON SOURCE COLUMNS")
    print("Order placement: DISABLED")
    print("AQSD database writes: DISABLED")
    print("=" * 78)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Advanced Options Intelligence Engine."
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

    parser.add_argument(
        "--atm-strikes",
        type=int,
        default=5,
        help="Strikes on each side of ATM for ATM-zone PCR. Default 5.",
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
            "python aqsd_options_intelligence.py "
            "--run --underlying BANKNIFTY"
        )

    summary, walls = calculate(
        args.underlying,
        max(
            1,
            args.atm_strikes,
        ),
    )

    save_outputs(
        summary,
        walls,
    )

    show_results(
        summary
    )


if __name__ == "__main__":
    main()
