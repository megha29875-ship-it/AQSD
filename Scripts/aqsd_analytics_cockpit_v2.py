"""AQSD Analytics Cockpit v2 - options-buyer focused Streamlit dashboard.

Run:
    streamlit run Scripts/aqsd_analytics_cockpit_v2.py

Colours:
    Green  = Bullish / CALL bias
    Red    = Bearish / PUT bias
    Yellow = Sideways / WAIT
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"

FILES = {
    "command": [OUT / "AQSD_Command_Center_v2.csv", OUT / "AQSD_Command_Center.csv"],
    "master": [OUT / "AQSD_AI_Master_Decision.csv"],
    "score": [OUT / "AQSD_Institutional_Scoring.csv"],
    "options": [OUT / "BANKNIFTY_Options_Intelligence_Summary.csv", OUT / "AQSD_Options_Intelligence_Summary.csv"],
    "futures": [OUT / "BANKNIFTY_Futures_Analytics.csv", OUT / "AQSD_Futures_Analytics.csv"],
}

BULL = "#00d084"
BEAR = "#ff4d5a"
SIDE = "#ffc107"
BG = "#07101d"
CARD = "#101a2b"
BORDER = "#26344a"
TEXT = "#f3f6fb"
SUB = "#9aa9bd"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if math.isnan(number) else number
    except Exception:
        return default


def safe_text(value: Any, default: str = "-") -> str:
    text = "" if value is None else str(value).strip()
    return default if not text or text.lower() in {"nan", "none", "null"} else text


@st.cache_data(ttl=10)
def latest_row(paths: tuple[str, ...]) -> dict[str, Any]:
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, low_memory=False)
            if not frame.empty:
                return frame.iloc[-1].to_dict()
        except Exception:
            pass
    return {}


def load_data() -> dict[str, dict[str, Any]]:
    return {key: latest_row(tuple(str(p) for p in paths)) for key, paths in FILES.items()}


def pick(sources: list[dict[str, Any]], names: list[str], default: Any = None) -> Any:
    for source in sources:
        lowered = {str(k).strip().lower(): v for k, v in source.items()}
        for name in names:
            value = lowered.get(name.lower())
            if value is not None and safe_text(value, ""):
                return value
    return default


def normalize_bias(value: Any) -> str:
    text = safe_text(value, "SIDEWAYS").upper()
    if any(word in text for word in ["BULL", "BUY", "CALL", "LONG"]):
        return "BULLISH"
    if any(word in text for word in ["BEAR", "SELL", "PUT", "SHORT"]):
        return "BEARISH"
    return "SIDEWAYS"


def color_for(state: str) -> str:
    state = state.upper()
    if "BULL" in state or "CALL" in state or state == "BUY":
        return BULL
    if "BEAR" in state or "PUT" in state or state == "SELL":
        return BEAR
    return SIDE


def classify_trend(directional: float, trend: float, confidence: float) -> tuple[str, float]:
    score = directional * 0.4 + trend * 0.4 + confidence * 0.2
    if score >= 75:
        return "VERY STRONG", score
    if score >= 62:
        return "STRONG", score
    if score >= 52:
        return "MODERATE", score
    return "WEAK / SIDEWAYS", score


def classify_iv(iv_rank: float, iv_percentile: float, regime: str) -> tuple[str, str]:
    text = regime.upper()
    if "LOW" in text or max(iv_rank, iv_percentile) <= 30:
        return "LOW", "Premiums relatively favourable for option buying"
    if "HIGH" in text or max(iv_rank, iv_percentile) >= 60:
        return "HIGH", "Premiums expensive; require a stronger directional move"
    return "NORMAL", "Balanced volatility environment"


def buyer_decision(
    bias: str,
    trend_score: float,
    confidence: float,
    probability: float,
    iv_state: str,
    expected_move: float,
) -> dict[str, Any]:
    instrument = "BUY CALL" if bias == "BULLISH" else "BUY PUT" if bias == "BEARISH" else "NO TRADE"
    iv_factor = 1.10 if iv_state == "LOW" else 0.85 if iv_state == "HIGH" else 1.0
    score = (
        trend_score * 0.35
        + confidence * 0.25
        + probability * 0.25
        + min(abs(expected_move) * 20, 100) * 0.15
    ) * iv_factor
    score = max(0.0, min(score, 100.0))

    if bias == "SIDEWAYS":
        return {"action": "WAIT", "instrument": instrument, "grade": "AVOID", "score": score,
                "reason": "Direction is unclear. Avoid option buying in a sideways market."}
    if trend_score >= 62 and confidence >= 65 and probability >= 65 and abs(expected_move) >= 0.75:
        return {"action": instrument, "instrument": instrument, "grade": "A" if score >= 78 else "B", "score": score,
                "reason": "Direction, trend and expected movement support directional option buying."}
    if trend_score >= 62 and confidence >= 60:
        return {"action": "WATCH", "instrument": instrument, "grade": "C", "score": score,
                "reason": "Direction is visible, but probability or movement needs confirmation."}
    return {"action": "WAIT", "instrument": instrument, "grade": "AVOID", "score": score,
            "reason": "Trend strength is insufficient for option buying."}


def card(title: str, value: str, subtitle: str, state: str = "SIDEWAYS", extra: str = "") -> None:
    color = color_for(state)
    st.markdown(
        f"""
        <div class='card' style='border-left:5px solid {color};'>
            <div class='title'>{title}</div>
            <div class='value'>{value}</div>
            <div class='subtitle'>{subtitle}</div>
            <div class='extra'>{extra}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_card(title: str, score: float, state: str, subtitle: str) -> None:
    color = color_for(state)
    score = max(0.0, min(score, 100.0))
    st.markdown(
        f"""
        <div class='card'>
            <div class='title'>{title}</div>
            <div class='value'>{score:.1f}</div>
            <div class='bar'><div class='fill' style='width:{score:.1f}%;background:{color};'></div></div>
            <div class='subtitle'>{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(name: str) -> None:
    st.markdown(f"<div class='section'>{name}</div>", unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp{{background:{BG};color:{TEXT}}}
        [data-testid='stHeader']{{background:transparent}}
        .block-container{{max-width:100%;padding:0.65rem 1rem 1rem 1rem}}
        .header{{background:linear-gradient(90deg,#101b2d,#162237);border:1px solid {BORDER};border-radius:14px;
                 padding:14px 18px;display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
        .brand{{font-size:1.45rem;font-weight:900;color:{BULL};letter-spacing:.04em}}
        .underlying{{font-size:1.35rem;font-weight:900}}
        .section{{margin:9px 0 6px;color:#67a9ff;font-size:.82rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}}
        .card{{min-height:128px;background:{CARD};border:1px solid {BORDER};border-radius:14px;padding:14px;margin-bottom:10px;
               box-shadow:0 3px 10px rgba(0,0,0,.16)}}
        .title{{color:{SUB};font-size:.73rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}
        .value{{color:{TEXT};font-size:1.42rem;font-weight:900;margin-top:8px;line-height:1.2}}
        .subtitle{{color:{SUB};font-size:.77rem;margin-top:7px;line-height:1.25}}
        .extra{{color:{TEXT};font-size:.71rem;margin-top:7px;opacity:.88}}
        .bar{{width:100%;height:9px;background:#273246;border-radius:9px;overflow:hidden;margin-top:10px}}
        .fill{{height:100%;border-radius:9px}}
        .conclusion{{background:linear-gradient(135deg,#111d30,#16243a);border:1px solid {BORDER};border-radius:14px;padding:16px;min-height:230px}}
        .big{{font-size:2rem;font-weight:950;margin:8px 0}}
        .chip{{display:inline-block;border-radius:12px;padding:4px 8px;margin:3px 3px 0 0;font-size:.72rem;font-weight:800;background:#233149}}
        table.matrix{{width:100%;border-collapse:collapse}}
        table.matrix td{{border-bottom:1px solid #253248;padding:8px 7px;font-size:.83rem}}
        table.matrix td:last-child{{text-align:right;font-weight:800}}
        .stButton>button{{width:100%;background:#1a2940;color:{TEXT};border:1px solid {BORDER}}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="AQSD Analytics Cockpit v2", page_icon="📊", layout="wide")
    inject_css()

    data = load_data()
    command, master, score, options, futures = [data[k] for k in ["command", "master", "score", "options", "futures"]]
    sources = [command, master, score, options, futures]
    live = any(bool(x) for x in sources)

    left, middle, right = st.columns([2.2, 3.8, 1.4])
    with left:
        underlying = st.selectbox("Underlying", ["BANKNIFTY", "NIFTY"], label_visibility="collapsed")
    with middle:
        st.markdown(
            f"<div class='header'><div><div class='brand'>AQSD ANALYTICS COCKPIT</div>"
            f"<div style='color:{SUB};font-size:.76rem'>OPTIONS BUYER • DIRECTION • TREND • IV • EXPECTED MOVE</div></div>"
            f"<div class='underlying'>{underlying}</div></div>", unsafe_allow_html=True)
    with right:
        if st.button("↻ REFRESH"):
            st.cache_data.clear(); st.rerun()
        status_color = BULL if live else BEAR
        st.markdown(f"<div style='text-align:center;color:{status_color};font-weight:900'>● {'LIVE' if live else 'OFFLINE'}<br>"
                    f"<span style='color:{SUB};font-size:.72rem'>{datetime.now():%H:%M:%S}</span></div>", unsafe_allow_html=True)

    spot = safe_float(pick(sources, ["spot_price", "spot", "ltp"], 0))
    atm = safe_float(pick(sources, ["atm", "atm_strike"], round(spot / 100) * 100 if spot else 0))
    bias = normalize_bias(pick(sources, ["final_bias", "final_verdict", "suggested_action", "direction"], "SIDEWAYS"))
    confidence = safe_float(pick(sources, ["final_confidence_percent", "confidence_percent", "ai_confidence_percent", "confidence"], 0))
    probability = safe_float(pick(sources, ["probability_success_percent", "success_probability", "probability_down", "probability_up"], 0))
    directional = safe_float(pick(sources, ["directional_score"], confidence))
    trend = safe_float(pick(sources, ["trend_score", "trend_strength_score"], directional))
    trend_label, trend_score = classify_trend(directional, trend, confidence)

    oi_pcr = safe_float(pick(sources, ["oi_pcr", "pcr_oi"], 0))
    volume_pcr = safe_float(pick(sources, ["volume_pcr", "pcr_volume"], 0))
    max_pain = safe_float(pick(sources, ["max_pain", "max_pain_strike"], 0))
    put_wall = safe_float(pick(sources, ["positional_put_wall", "put_wall"], 0))
    call_wall = safe_float(pick(sources, ["positional_call_wall", "call_wall"], 0))
    rollover = safe_float(pick(sources, ["rollover_share_percent", "rollover_percent"], 0))

    iv_rank = safe_float(pick(sources, ["iv_rank"], 0))
    iv_percentile = safe_float(pick(sources, ["iv_percentile"], 0))
    iv_regime = safe_text(pick(sources, ["iv_regime", "volatility_regime"], "NO IV DATA"))
    iv_state, iv_comment = classify_iv(iv_rank, iv_percentile, iv_regime)

    expected_move = safe_float(pick(sources, ["expected_move_percent", "expected_move_pct"], 0))
    expected_low = safe_float(pick(sources, ["expected_range_low", "expected_low"], 0))
    expected_high = safe_float(pick(sources, ["expected_range_high", "expected_high"], 0))
    pinning = safe_float(pick(sources, ["pinning_probability", "pinning_probability_percent"], 0))
    concentration = safe_float(pick(sources, ["oi_concentration", "concentration_score"], 0))

    near_oi = safe_float(pick(sources, ["near_open_interest", "near_oi"], 0))
    next_oi = safe_float(pick(sources, ["next_open_interest", "next_oi"], 0))
    far_oi = safe_float(pick(sources, ["far_open_interest", "far_oi"], 0))
    total_oi = safe_float(pick(sources, ["total_open_interest", "total_futures_oi"], near_oi + next_oi + far_oi))
    near_cycle = safe_text(pick(sources, ["near_cycle", "near_oi_cycle"], "-"))
    next_cycle = safe_text(pick(sources, ["next_cycle", "next_oi_cycle"], "-"))
    far_cycle = safe_text(pick(sources, ["far_cycle", "far_oi_cycle"], "-"))
    term = safe_text(pick(sources, ["term_structure", "futures_term_structure"], "-"))
    migration = safe_text(pick(sources, ["oi_migration", "rollover_interpretation", "interpretation"], "-"))

    call_doi = safe_float(pick(sources, ["call_change_oi", "call_delta_oi", "call_doi"], 0))
    put_doi = safe_float(pick(sources, ["put_change_oi", "put_delta_oi", "put_doi"], 0))

    buyer = buyer_decision(bias, trend_score, confidence, probability, iv_state, expected_move)

    section("Market Intelligence")
    cols = st.columns(8)
    items = [
        ("Spot", f"{spot:,.2f}", f"ATM {atm:,.0f}", bias, "Underlying reference"),
        ("Final Bias", bias, f"Trend: {trend_label}", bias, f"Directional score {directional:.1f}"),
        ("OI PCR", f"{oi_pcr:.2f}", "Put OI / Call OI", "BULLISH" if oi_pcr >= 1.05 else "BEARISH" if oi_pcr <= .85 else "SIDEWAYS", "Bull >1.05 | Bear <0.85"),
        ("Volume PCR", f"{volume_pcr:.2f}", "Put Volume / Call Volume", "BULLISH" if volume_pcr >= 1.05 else "BEARISH" if volume_pcr <= .85 else "SIDEWAYS", "Fresh flow indicator"),
        ("Max Pain", f"{max_pain:,.0f}", f"Distance {abs(max_pain-spot):,.0f} pts", "SIDEWAYS", "Expiry magnet"),
        ("Put Wall", f"{put_wall:,.0f}", "Primary support", "BULLISH", "Put concentration"),
        ("Call Wall", f"{call_wall:,.0f}", "Primary resistance", "BEARISH", "Call concentration"),
        ("Rollover", f"{rollover:.1f}%", migration, bias, "Near → Next → Far"),
    ]
    for col, item in zip(cols, items):
        with col: card(*item)

    section("Options Buyer Edge")
    cols = st.columns([1.2, 1, 1, 1, 1, 1.5])
    with cols[0]: card("Preferred Instrument", buyer["instrument"], buyer["reason"], bias, f"Grade {buyer['grade']}")
    with cols[1]: score_card("Buyer Edge Score", buyer["score"], bias, "Direction + trend + probability + movement + IV")
    with cols[2]: score_card("Trend Strength", trend_score, bias, trend_label)
    with cols[3]: score_card("AI Confidence", confidence, bias, "Directional confidence")
    with cols[4]: score_card("Success Probability", probability, bias, "Model probability")
    with cols[5]: card("IV Environment", iv_state, iv_comment, "BULLISH" if iv_state == "LOW" else "BEARISH" if iv_state == "HIGH" else "SIDEWAYS", f"IV Rank {iv_rank:.1f} | IV Percentile {iv_percentile:.1f}")

    section("Futures Intelligence")
    cols = st.columns(6)
    items = [
        ("Near Future", f"{near_oi:,.0f}", near_cycle, normalize_bias(near_cycle), "Near-month OI"),
        ("Next Future", f"{next_oi:,.0f}", next_cycle, normalize_bias(next_cycle), "Next-month OI"),
        ("Far Future", f"{far_oi:,.0f}", far_cycle, normalize_bias(far_cycle), "Far-month OI"),
        ("Total Futures OI", f"{total_oi:,.0f}", "Near + Next + Far", bias, "Aggregate positioning"),
        ("Term Structure", term.upper(), "Contango / Backwardation", "SIDEWAYS", "Curve structure"),
        ("OI Migration", migration.upper(), "Contract positioning shift", bias, "Rollover interpretation"),
    ]
    for col, item in zip(cols, items):
        with col: card(*item)

    section("Options and Institutional Structure")
    cols = st.columns([1, 1, 1, 1, 1.4])
    with cols[0]: card("Call ΔOI", f"{call_doi:,.0f}", "Fresh call positioning", "BEARISH" if call_doi > 0 else "BULLISH", "Writing + | Unwinding -")
    with cols[1]: card("Put ΔOI", f"{put_doi:,.0f}", "Fresh put positioning", "BULLISH" if put_doi > 0 else "BEARISH", "Writing + | Unwinding -")
    expected_range = f"{expected_low:,.0f}–{expected_high:,.0f}" if expected_low and expected_high else f"{expected_move:+.2f}%"
    with cols[2]: card("Expected Range", expected_range, "Option buyer movement potential", bias, "Directional move estimate")
    with cols[3]: card("Pinning / Concentration", f"{pinning:.1f}% / {concentration:.1f}", "Max pain proximity / OI clustering", "SIDEWAYS", "Expiry structure")
    with cols[4]:
        c = color_for(bias)
        st.markdown(
            f"<div class='conclusion' style='border-left:6px solid {c}'><div class='title'>AQSD OPTIONS BUYER CONCLUSION</div>"
            f"<div class='big' style='color:{c}'>{buyer['action']}</div><div style='font-size:1.05rem;font-weight:850'>{bias} • {trend_label}</div>"
            f"<div style='margin-top:10px;color:{SUB};font-size:.79rem'>{buyer['reason']}</div><div style='margin-top:12px'>"
            f"<span class='chip'>Score {buyer['score']:.1f}</span><span class='chip'>Grade {buyer['grade']}</span>"
            f"<span class='chip'>IV {iv_state}</span><span class='chip'>P {probability:.0f}%</span></div></div>", unsafe_allow_html=True)

    section("Decision Matrix")
    matrices = [
        [("Support", f"{put_wall or max_pain:,.0f}"), ("Resistance", f"{call_wall or max_pain:,.0f}"), ("ATM", f"{atm:,.0f}"), ("Max Pain", f"{max_pain:,.0f}"), ("Expected Move", f"{expected_move:+.2f}%")],
        [("Near Cycle", near_cycle.upper()), ("Next Cycle", next_cycle.upper()), ("Far Cycle", far_cycle.upper()), ("Term Structure", term.upper()), ("Rollover", f"{rollover:.1f}%")],
        [("Direction", bias), ("Trend", trend_label), ("Option Bias", buyer["instrument"]), ("IV State", iv_state), ("Final Action", buyer["action"])],
    ]
    for col, rows in zip(st.columns(3), matrices):
        with col:
            html = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows)
            st.markdown(f"<div class='card'><table class='matrix'>{html}</table></div>", unsafe_allow_html=True)

    st.caption("AQSD analytics and decision support only. Order execution remains disabled.")


if __name__ == "__main__":
    main()
