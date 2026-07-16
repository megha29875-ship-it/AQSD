"""
AQSD Professional
Component: Derivatives Intelligence Panel
Version: 1.0

Reads existing AQSD FYERS outputs and renders:
- Futures OI summary
- Near / Next / Far OI bars
- PCR metrics
- Max Pain
- Call Wall / Put Wall
- Rollover and OI migration
- Smart-money interpretation

No order placement. No database writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "Output"

FUTURES_FILE = OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.csv"
OPTION_SUMMARY_FILE = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Summary.csv"
SMART_MONEY_FILE = OUTPUT_DIR / "AQSD_FYERS_Smart_Money_Summary.csv"
BANKNIFTY_LEVELS_FILE = OUTPUT_DIR / "AQSD_BANKNIFTY_Institutional_Levels.csv"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        if pd.isna(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def _match_underlying(
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

    return rows.iloc[0]


def load_derivatives_snapshot(
    underlying: str,
) -> dict[str, Any]:
    futures = _read_csv(FUTURES_FILE)
    option_summary = _read_csv(OPTION_SUMMARY_FILE)
    smart_money = _read_csv(SMART_MONEY_FILE)
    banknifty_levels = _read_csv(BANKNIFTY_LEVELS_FILE)

    future_row = _match_underlying(futures, underlying)
    option_row = _match_underlying(option_summary, underlying)
    smart_row = _match_underlying(smart_money, underlying)

    levels_row = None
    if underlying.strip().upper() == "BANKNIFTY" and not banknifty_levels.empty:
        levels_row = banknifty_levels.iloc[0]

    snapshot: dict[str, Any] = {
        "underlying": underlying.strip().upper(),
        "near_oi": None,
        "next_oi": None,
        "far_oi": None,
        "total_oi": None,
        "near_oi_change": None,
        "next_oi_change": None,
        "far_oi_change": None,
        "rollover_share": None,
        "term_structure": "NO DATA",
        "oi_migration": "NO DATA",
        "rollover_signal": "NO DATA",
        "near_cycle": "NO DATA",
        "next_cycle": "NO DATA",
        "far_cycle": "NO DATA",
        "oi_pcr": None,
        "volume_pcr": None,
        "max_pain": None,
        "call_wall": None,
        "put_wall": None,
        "atm_strike": None,
        "smart_money_bias": "NO DATA",
        "confidence_score": None,
    }

    if future_row is not None:
        snapshot.update(
            {
                "near_oi": _safe_float(future_row.get("near_open_interest")),
                "next_oi": _safe_float(future_row.get("next_open_interest")),
                "far_oi": _safe_float(future_row.get("far_open_interest")),
                "total_oi": _safe_float(future_row.get("total_open_interest")),
                "near_oi_change": _safe_float(future_row.get("near_oi_change")),
                "next_oi_change": _safe_float(future_row.get("next_oi_change")),
                "far_oi_change": _safe_float(future_row.get("far_oi_change")),
                "rollover_share": _safe_float(
                    future_row.get("rollover_share_percent")
                ),
                "term_structure": str(
                    future_row.get("term_structure", "NO DATA")
                ),
                "oi_migration": str(
                    future_row.get("oi_migration", "NO DATA")
                ),
                "rollover_signal": str(
                    future_row.get("rollover_signal", "NO DATA")
                ),
                "near_cycle": str(future_row.get("near_cycle", "NO DATA")),
                "next_cycle": str(future_row.get("next_cycle", "NO DATA")),
                "far_cycle": str(future_row.get("far_cycle", "NO DATA")),
            }
        )

    if option_row is not None:
        snapshot.update(
            {
                "oi_pcr": _safe_float(option_row.get("oi_pcr")),
                "volume_pcr": _safe_float(option_row.get("volume_pcr")),
                "max_pain": _safe_float(option_row.get("max_pain")),
                "call_wall": _safe_float(
                    option_row.get("maximum_call_oi_resistance")
                ),
                "put_wall": _safe_float(
                    option_row.get("maximum_put_oi_support")
                ),
                "atm_strike": _safe_float(option_row.get("atm_strike")),
            }
        )

    if smart_row is not None:
        snapshot["smart_money_bias"] = str(
            smart_row.get("smart_money_bias", "NO DATA")
        )

        raw_score = _safe_float(
            smart_row.get("total_smart_money_score")
        )

        if raw_score is not None:
            snapshot["confidence_score"] = min(
                100.0,
                max(0.0, 50.0 + raw_score * 6.0),
            )

    if levels_row is not None:
        snapshot["call_wall"] = _safe_float(
            levels_row.get("call_wall")
        ) or snapshot["call_wall"]

        snapshot["put_wall"] = _safe_float(
            levels_row.get("put_wall")
        ) or snapshot["put_wall"]

        snapshot["max_pain"] = _safe_float(
            levels_row.get("max_pain")
        ) or snapshot["max_pain"]

    return snapshot


def create_futures_oi_chart(
    snapshot: dict[str, Any],
) -> go.Figure:
    labels = ["Near", "Next", "Far"]

    values = [
        snapshot.get("near_oi") or 0,
        snapshot.get("next_oi") or 0,
        snapshot.get("far_oi") or 0,
    ]

    changes = [
        snapshot.get("near_oi_change") or 0,
        snapshot.get("next_oi_change") or 0,
        snapshot.get("far_oi_change") or 0,
    ]

    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            name="Open Interest",
            text=[f"{value:,.0f}" for value in values],
            textposition="auto",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=labels,
            y=changes,
            name="OI Change",
            mode="lines+markers+text",
            text=[f"{value:+,.0f}" for value in changes],
            textposition="top center",
            yaxis="y2",
        )
    )

    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#111827",
        height=340,
        margin=dict(l=20, r=20, t=35, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
        ),
        yaxis=dict(
            title="Open Interest",
            gridcolor="#263244",
        ),
        yaxis2=dict(
            title="OI Change",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
    )

    return figure


def render_derivatives_panel(
    underlying: str,
) -> dict[str, Any]:
    snapshot = load_derivatives_snapshot(underlying)

    st.subheader("Derivatives Intelligence")

    top1, top2, top3, top4, top5 = st.columns(5)

    with top1:
        st.metric(
            "OI PCR",
            f"{snapshot['oi_pcr']:.2f}"
            if snapshot["oi_pcr"] is not None
            else "--",
        )

    with top2:
        st.metric(
            "Volume PCR",
            f"{snapshot['volume_pcr']:.2f}"
            if snapshot["volume_pcr"] is not None
            else "--",
        )

    with top3:
        st.metric(
            "Max Pain",
            f"{snapshot['max_pain']:,.0f}"
            if snapshot["max_pain"] is not None
            else "--",
        )

    with top4:
        st.metric(
            "Put Wall",
            f"{snapshot['put_wall']:,.0f}"
            if snapshot["put_wall"] is not None
            else "--",
        )

    with top5:
        st.metric(
            "Call Wall",
            f"{snapshot['call_wall']:,.0f}"
            if snapshot["call_wall"] is not None
            else "--",
        )

    left, right = st.columns([1.7, 1.0])

    with left:
        st.plotly_chart(
            create_futures_oi_chart(snapshot),
            use_container_width=True,
            config={"displaylogo": False},
        )

    with right:
        st.markdown(
            f"""
            <div class="terminal-card">
                <div class="terminal-label">Smart Money Bias</div>
                <div class="terminal-value">
                    {snapshot['smart_money_bias']}
                </div>
                <br>
                <b>Term Structure</b><br>
                {snapshot['term_structure']}<br><br>
                <b>OI Migration</b><br>
                {snapshot['oi_migration']}<br><br>
                <b>Rollover</b><br>
                {snapshot['rollover_signal']}<br><br>
                <b>Near / Next / Far</b><br>
                {snapshot['near_cycle']}<br>
                {snapshot['next_cycle']}<br>
                {snapshot['far_cycle']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if snapshot["total_oi"] is None:
        st.warning(
            "Futures analytics data is unavailable for this instrument. "
            "Run the futures OI analytics script first."
        )

    if snapshot["oi_pcr"] is None:
        st.warning(
            "Option-chain summary is unavailable for this instrument. "
            "Run the option-chain analytics script for the same instrument."
        )

    return snapshot
