import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE))

import streamlit as st

from Components.chart_panel import create_live_chart
from Components.derivatives_panel import render_derivatives_panel


st.set_page_config(
    page_title="AQSD Professional",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #0B0F19;
        color: #F5F5F5;
    }

    [data-testid="stHeader"] {
        background: rgba(0,0,0,0);
        height: 0rem;
    }

    [data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid #2A2F3A;
    }

    div.block-container {
        padding-top: 0.5rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }

    .aqsd-title {
        color: #00E676;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.04em;
    }

    .aqsd-subtitle {
        color: #9CA3AF;
        margin-bottom: 0.8rem;
    }

    .terminal-card {
        background: #111827;
        border: 1px solid #2A2F3A;
        border-radius: 12px;
        padding: 1rem;
    }

    .terminal-label {
        color: #9CA3AF;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .terminal-value {
        color: #F5F5F5;
        font-size: 1.45rem;
        font-weight: 750;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="aqsd-title">AQSD PROFESSIONAL TERMINAL</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="aqsd-subtitle">'
    'Institutional Derivatives Analytics Platform'
    '</div>',
    unsafe_allow_html=True,
)


st.sidebar.title("AQSD")

instrument = st.sidebar.selectbox(
    "Instrument",
    [
        "BANKNIFTY",
        "NIFTY",
        "FINNIFTY",
        "MIDCPNIFTY",
        "RELIANCE",
    ],
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    [
        "1 Minute",
        "3 Minute",
        "5 Minute",
        "15 Minute",
        "1 Hour",
        "Daily",
    ],
    index=2,
)

candle_count = st.sidebar.slider(
    "Visible Candles",
    min_value=50,
    max_value=250,
    value=120,
    step=10,
)

st.sidebar.button(
    "Refresh Now",
    use_container_width=True,
)

st.sidebar.success("FYERS configuration connected")


try:
    figure, snapshot = create_live_chart(
        instrument,
        timeframe,
    )

    spot = snapshot.get("spot")
    change_percent = snapshot.get("change_percent")
    ema20 = snapshot.get("ema20")
    ema50 = snapshot.get("ema50")
    vwap = snapshot.get("vwap")
    supertrend_direction = snapshot.get(
        "supertrend_direction"
    )

    if (
        supertrend_direction == 1
        and spot is not None
        and ema20 is not None
        and ema50 is not None
        and spot > ema20 > ema50
    ):
        technical_bias = "BULLISH"

    elif (
        supertrend_direction == -1
        and spot is not None
        and ema20 is not None
        and ema50 is not None
        and spot < ema20 < ema50
    ):
        technical_bias = "BEARISH"

    else:
        technical_bias = "MIXED"

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:
        st.metric(
            "Spot",
            f"{spot:,.2f}" if spot is not None else "--",
            f"{change_percent:+.2f}%"
            if change_percent is not None
            else None,
        )

    with metric2:
        st.metric(
            "Technical Bias",
            technical_bias,
        )

    with metric3:
        st.metric(
            "EMA 20 / EMA 50",
            f"{ema20:,.2f} / {ema50:,.2f}"
            if ema20 is not None and ema50 is not None
            else "--",
        )

    with metric4:
        st.metric(
            "VWAP",
            f"{vwap:,.2f}" if vwap is not None else "--",
        )

    st.divider()

    st.subheader(
        f"{instrument} Live Price Chart"
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": True,
        },
    )

    st.divider()

    derivatives = render_derivatives_panel(
        instrument
    )

    st.divider()

    left, middle, right = st.columns(3)

    with left:
        st.subheader("Market DNA")

        trend_score = (
            85
            if technical_bias == "BULLISH"
            else 25
            if technical_bias == "BEARISH"
            else 55
        )

        derivatives_score = (
            derivatives.get("confidence_score")
            if derivatives.get("confidence_score") is not None
            else 50
        )

        st.progress(
            trend_score / 100,
            text=f"Trend {trend_score}/100",
        )

        st.progress(
            derivatives_score / 100,
            text=f"Derivatives {derivatives_score:.0f}/100",
        )

    with middle:
        st.subheader("Technical Structure")

        st.write(
            f"**SuperTrend:** "
            f"{'Bullish' if supertrend_direction == 1 else 'Bearish'}"
        )

        st.write(
            f"**Price vs VWAP:** "
            f"{'Above VWAP' if spot is not None and vwap is not None and spot >= vwap else 'Below VWAP'}"
        )

        st.write(
            f"**EMA Structure:** "
            f"{'Positive' if ema20 is not None and ema50 is not None and ema20 >= ema50 else 'Negative'}"
        )

    with right:
        st.subheader("AQSD View")

        st.markdown(
            f"""
            <div class="terminal-card">
                <div class="terminal-label">Technical Bias</div>
                <div class="terminal-value">{technical_bias}</div>
                <br>
                <div class="terminal-label">Derivatives Bias</div>
                <div class="terminal-value">
                    {derivatives.get('smart_money_bias', 'NO DATA')}
                </div>
                <br>
                <div class="terminal-label">Rollover</div>
                {derivatives.get('rollover_signal', 'NO DATA')}
            </div>
            """,
            unsafe_allow_html=True,
        )

except Exception as error:
    st.error("AQSD dashboard could not be loaded.")
    st.exception(error)
