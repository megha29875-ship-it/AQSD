"""
AQSD Professional
Dashboard: One-Screen Analytics Cockpit
Version: 1.0

Purpose
-------
A compact, analytics-first Streamlit page designed to show the major
technical, futures, options and smart-money metrics without vertical scrolling.

The chart is intentionally excluded for now.

Inputs
------
Output/AQSD_FYERS_Futures_OI_Analytics.csv
Output/AQSD_FYERS_Option_Chain_Summary.csv
Output/AQSD_FYERS_Smart_Money_Summary.csv
Output/AQSD_BANKNIFTY_Institutional_Levels.csv

Safety
------
No order placement.
No database writes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE))

OUTPUT = BASE / "Output"

FUTURES_FILE = OUTPUT / "AQSD_FYERS_Futures_OI_Analytics.csv"
OPTION_FILE = OUTPUT / "AQSD_FYERS_Option_Chain_Summary.csv"
SMART_FILE = OUTPUT / "AQSD_FYERS_Smart_Money_Summary.csv"
BANKNIFTY_FILE = OUTPUT / "AQSD_BANKNIFTY_Institutional_Levels.csv"


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
        if pd.isna(number):
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


def find_row(frame: pd.DataFrame, underlying: str) -> pd.Series | None:
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

    return None if rows.empty else rows.iloc[0]


def value(row: pd.Series | None, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    return row.get(key, default)


def fmt_number(number: Any, decimals: int = 0) -> str:
    parsed = safe_float(number)

    if parsed is None:
        return "--"

    return f"{parsed:,.{decimals}f}"


def fmt_percent(number: Any, decimals: int = 1) -> str:
    parsed = safe_float(number)

    if parsed is None:
        return "--"

    return f"{parsed:,.{decimals}f}%"


def load_snapshot(underlying: str) -> dict[str, Any]:
    futures = find_row(read_csv(FUTURES_FILE), underlying)
    options = find_row(read_csv(OPTION_FILE), underlying)
    smart = find_row(read_csv(SMART_FILE), underlying)

    bank = None
    bank_frame = read_csv(BANKNIFTY_FILE)

    if underlying == "BANKNIFTY" and not bank_frame.empty:
        bank = bank_frame.iloc[0]

    snapshot = {
        "underlying": underlying,
        "spot": value(options, "spot_price"),
        "atm": value(options, "atm_strike"),
        "oi_pcr": value(options, "oi_pcr"),
        "volume_pcr": value(options, "volume_pcr"),
        "call_oi_change": value(options, "total_call_oi_change"),
        "put_oi_change": value(options, "total_put_oi_change"),
        "max_pain": value(options, "max_pain"),
        "call_wall": value(options, "maximum_call_oi_resistance"),
        "put_wall": value(options, "maximum_put_oi_support"),
        "option_bias": value(options, "option_chain_bias", "NO DATA"),
        "near_oi": value(futures, "near_open_interest"),
        "next_oi": value(futures, "next_open_interest"),
        "far_oi": value(futures, "far_open_interest"),
        "total_oi": value(futures, "total_open_interest"),
        "near_change": value(futures, "near_oi_change"),
        "next_change": value(futures, "next_oi_change"),
        "far_change": value(futures, "far_oi_change"),
        "rollover_share": value(futures, "rollover_share_percent"),
        "term_structure": value(futures, "term_structure", "NO DATA"),
        "oi_migration": value(futures, "oi_migration", "NO DATA"),
        "rollover_signal": value(futures, "rollover_signal", "NO DATA"),
        "near_cycle": value(futures, "near_cycle", "NO DATA"),
        "next_cycle": value(futures, "next_cycle", "NO DATA"),
        "far_cycle": value(futures, "far_cycle", "NO DATA"),
        "smart_bias": value(smart, "smart_money_bias", "NO DATA"),
        "smart_score": value(smart, "total_smart_money_score"),
        "support": value(smart, "support"),
        "resistance": value(smart, "resistance"),
        "conclusion": value(smart, "conclusion", "NO DATA"),
    }

    if bank is not None:
        snapshot["spot"] = value(bank, "spot_price", snapshot["spot"])
        snapshot["atm"] = value(bank, "atm_strike", snapshot["atm"])
        snapshot["max_pain"] = value(bank, "max_pain", snapshot["max_pain"])
        snapshot["call_wall"] = value(bank, "call_wall", snapshot["call_wall"])
        snapshot["put_wall"] = value(bank, "put_wall", snapshot["put_wall"])
        snapshot["expected_low"] = value(bank, "straddle_expected_low")
        snapshot["expected_high"] = value(bank, "straddle_expected_high")
        snapshot["pinning"] = value(bank, "pinning_score_percent")
        snapshot["concentration"] = value(bank, "oi_concentration_score")
        snapshot["smart_bias"] = value(
            bank,
            "banknifty_bias",
            snapshot["smart_bias"],
        )
        snapshot["conclusion"] = value(
            bank,
            "conclusion",
            snapshot["conclusion"],
        )
    else:
        snapshot["expected_low"] = None
        snapshot["expected_high"] = None
        snapshot["pinning"] = None
        snapshot["concentration"] = None

    return snapshot


def card(title: str, main: str, sub: str = "", css_class: str = "") -> None:
    st.markdown(
        f"""
        <div class="aqsd-card {css_class}">
            <div class="aqsd-card-title">{title}</div>
            <div class="aqsd-card-main">{main}</div>
            <div class="aqsd-card-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def bias_class(text: str) -> str:
    upper = str(text).upper()

    if "BULL" in upper or "LONG BUILDUP" in upper or "SHORT COVERING" in upper:
        return "positive"

    if "BEAR" in upper or "SHORT BUILDUP" in upper or "LONG UNWINDING" in upper:
        return "negative"

    return "neutral"


st.set_page_config(
    page_title="AQSD Analytics Cockpit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #070B12;
        color: #F5F7FA;
    }

    [data-testid="stHeader"] {
        height: 0;
        background: transparent;
    }

    div.block-container {
        padding: 0.35rem 0.75rem 0.35rem 0.75rem;
        max-width: 100%;
    }

    h1, h2, h3, p {
        margin-top: 0 !important;
        margin-bottom: 0.25rem !important;
    }

    .aqsd-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #0E1522;
        border: 1px solid #263244;
        border-radius: 10px;
        padding: 0.55rem 0.8rem;
        margin-bottom: 0.45rem;
    }

    .aqsd-name {
        font-size: 1.35rem;
        font-weight: 800;
        color: #00E676;
        letter-spacing: 0.04em;
    }

    .aqsd-instrument {
        font-size: 1.3rem;
        font-weight: 800;
        color: #FFFFFF;
    }

    .aqsd-card {
        background: #0E1522;
        border: 1px solid #263244;
        border-radius: 10px;
        padding: 0.55rem 0.65rem;
        min-height: 92px;
        margin-bottom: 0.35rem;
        overflow: hidden;
    }

    .aqsd-card-title {
        color: #8E9AAF;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .aqsd-card-main {
        color: #F5F7FA;
        font-size: 1.22rem;
        line-height: 1.25;
        font-weight: 800;
        margin-top: 0.15rem;
    }

    .aqsd-card-sub {
        color: #9AA5B7;
        font-size: 0.71rem;
        line-height: 1.25;
        margin-top: 0.15rem;
    }

    .positive {
        border-left: 4px solid #00E676;
    }

    .negative {
        border-left: 4px solid #FF5252;
    }

    .neutral {
        border-left: 4px solid #FFC107;
    }

    .section-label {
        color: #6FA8FF;
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        margin: 0.1rem 0 0.25rem 0;
    }

    .compact-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.74rem;
    }

    .compact-table td {
        border-bottom: 1px solid #202B3A;
        padding: 0.24rem 0.3rem;
    }

    .compact-table td:first-child {
        color: #8E9AAF;
    }

    .compact-table td:last-child {
        color: #F5F7FA;
        text-align: right;
        font-weight: 700;
    }

    [data-testid="stSidebar"] {
        background: #0E1522;
    }

    div[data-testid="stSelectbox"] label {
        font-size: 0.72rem;
    }

    .stButton button {
        height: 2.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

top_left, top_middle, top_right = st.columns([1.1, 1.2, 0.7])

with top_left:
    instrument = st.selectbox(
        "Instrument",
        ["BANKNIFTY", "NIFTY", "RELIANCE", "HDFCBANK", "ICICIBANK"],
        label_visibility="collapsed",
    )

with top_middle:
    st.markdown(
        f"""
        <div class="aqsd-header">
            <div class="aqsd-name">AQSD ANALYTICS COCKPIT</div>
            <div class="aqsd-instrument">{instrument}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_right:
    st.button("Refresh analytics", use_container_width=True)

data = load_snapshot(instrument)

# ROW 1: Core decision metrics
r1 = st.columns(8)

with r1[0]:
    card("Spot", fmt_number(data["spot"], 2), f"ATM {fmt_number(data['atm'])}")

with r1[1]:
    card(
        "Final Bias",
        str(data["smart_bias"]),
        f"Score {fmt_number(data['smart_score'], 1)}",
        bias_class(data["smart_bias"]),
    )

with r1[2]:
    card("OI PCR", fmt_number(data["oi_pcr"], 2), "Put OI / Call OI")

with r1[3]:
    card("Volume PCR", fmt_number(data["volume_pcr"], 2), "Put Vol / Call Vol")

with r1[4]:
    card("Max Pain", fmt_number(data["max_pain"]), "Expiry magnet")

with r1[5]:
    card("Put Wall", fmt_number(data["put_wall"]), "Primary support")

with r1[6]:
    card("Call Wall", fmt_number(data["call_wall"]), "Primary resistance")

with r1[7]:
    card(
        "Rollover",
        fmt_percent(data["rollover_share"], 1),
        str(data["rollover_signal"]),
        bias_class(data["rollover_signal"]),
    )

# ROW 2: Futures analytics
st.markdown('<div class="section-label">Futures Intelligence</div>', unsafe_allow_html=True)

r2 = st.columns(6)

with r2[0]:
    card(
        "Near Future",
        fmt_number(data["near_oi"]),
        f"ΔOI {fmt_number(data['near_change'])} | {data['near_cycle']}",
        bias_class(data["near_cycle"]),
    )

with r2[1]:
    card(
        "Next Future",
        fmt_number(data["next_oi"]),
        f"ΔOI {fmt_number(data['next_change'])} | {data['next_cycle']}",
        bias_class(data["next_cycle"]),
    )

with r2[2]:
    card(
        "Far Future",
        fmt_number(data["far_oi"]),
        f"ΔOI {fmt_number(data['far_change'])} | {data['far_cycle']}",
        bias_class(data["far_cycle"]),
    )

with r2[3]:
    card("Total Futures OI", fmt_number(data["total_oi"]), "Near + Next + Far")

with r2[4]:
    card(
        "Term Structure",
        str(data["term_structure"]),
        "Contango / Backwardation",
        bias_class(data["term_structure"]),
    )

with r2[5]:
    card(
        "OI Migration",
        str(data["oi_migration"]),
        "Contract positioning shift",
        bias_class(data["oi_migration"]),
    )

# ROW 3: Options and institutional structure
st.markdown('<div class="section-label">Options and Institutional Structure</div>', unsafe_allow_html=True)

r3 = st.columns([1, 1, 1, 1, 1.35])

with r3[0]:
    card(
        "Call ΔOI",
        fmt_number(data["call_oi_change"]),
        "Net call positioning",
        bias_class("BEARISH" if (safe_float(data["call_oi_change"]) or 0) > 0 else "BULLISH"),
    )

with r3[1]:
    card(
        "Put ΔOI",
        fmt_number(data["put_oi_change"]),
        "Net put positioning",
        bias_class("BULLISH" if (safe_float(data["put_oi_change"]) or 0) > 0 else "BEARISH"),
    )

with r3[2]:
    expected_range = (
        f"{fmt_number(data['expected_low'])}–{fmt_number(data['expected_high'])}"
        if data["expected_low"] is not None and data["expected_high"] is not None
        else "--"
    )
    card("Expected Range", expected_range, "ATM straddle estimate")

with r3[3]:
    card(
        "Pinning / Concentration",
        f"{fmt_percent(data['pinning'])} / {fmt_number(data['concentration'], 1)}",
        "Max pain proximity / OI clustering",
    )

with r3[4]:
    card(
        "AQSD Conclusion",
        str(data["conclusion"]),
        str(data["option_bias"]),
        bias_class(data["smart_bias"]),
    )

# ROW 4: Compact decision table
st.markdown('<div class="section-label">Decision Matrix</div>', unsafe_allow_html=True)

matrix_left, matrix_middle, matrix_right = st.columns(3)

with matrix_left:
    st.markdown(
        f"""
        <table class="compact-table">
            <tr><td>Support</td><td>{fmt_number(data['support'] or data['put_wall'])}</td></tr>
            <tr><td>Resistance</td><td>{fmt_number(data['resistance'] or data['call_wall'])}</td></tr>
            <tr><td>ATM</td><td>{fmt_number(data['atm'])}</td></tr>
            <tr><td>Max Pain</td><td>{fmt_number(data['max_pain'])}</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )

with matrix_middle:
    st.markdown(
        f"""
        <table class="compact-table">
            <tr><td>Near Cycle</td><td>{data['near_cycle']}</td></tr>
            <tr><td>Next Cycle</td><td>{data['next_cycle']}</td></tr>
            <tr><td>Far Cycle</td><td>{data['far_cycle']}</td></tr>
            <tr><td>Term Structure</td><td>{data['term_structure']}</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )

with matrix_right:
    st.markdown(
        f"""
        <table class="compact-table">
            <tr><td>Smart Money</td><td>{data['smart_bias']}</td></tr>
            <tr><td>Option Bias</td><td>{data['option_bias']}</td></tr>
            <tr><td>OI Migration</td><td>{data['oi_migration']}</td></tr>
            <tr><td>Rollover</td><td>{data['rollover_signal']}</td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )
