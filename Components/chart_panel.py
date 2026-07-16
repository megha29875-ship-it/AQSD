from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from fyers_apiv3 import fyersModel
from plotly.subplots import make_subplots

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "Data" / "fyers_config.env"

SYMBOL_MAP = {
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "NIFTY": "NSE:NIFTY50-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
}

RESOLUTION_MAP = {
    "1 Minute": ("1", 5),
    "3 Minute": ("3", 10),
    "5 Minute": ("5", 15),
    "15 Minute": ("15", 30),
    "1 Hour": ("60", 90),
    "Daily": ("D", 400),
}


def load_config() -> dict[str, str]:
    config = {}
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing FYERS config: {CONFIG_FILE}")

    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    for key in ("CLIENT_ID", "ACCESS_TOKEN"):
        if not config.get(key):
            raise RuntimeError(f"Missing {key} in {CONFIG_FILE}")

    return config


def create_client() -> fyersModel.FyersModel:
    config = load_config()
    return fyersModel.FyersModel(
        client_id=config["CLIENT_ID"],
        token=config["ACCESS_TOKEN"],
        is_async=False,
        log_path="",
    )


def fyers_symbol(instrument: str) -> str:
    value = instrument.strip().upper()
    if value in SYMBOL_MAP:
        return SYMBOL_MAP[value]
    if value.startswith("NSE:"):
        return value
    return f"NSE:{value}-EQ"


def fetch_history(instrument: str, timeframe: str) -> pd.DataFrame:
    resolution, lookback_days = RESOLUTION_MAP.get(timeframe, ("5", 15))
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    response = create_client().history(
        data={
            "symbol": fyers_symbol(instrument),
            "resolution": resolution,
            "date_format": "1",
            "range_from": start_date.isoformat(),
            "range_to": end_date.isoformat(),
            "cont_flag": "1",
        }
    )

    if not isinstance(response, dict) or response.get("s") != "ok":
        raise RuntimeError(f"FYERS history error: {response}")

    candles = response.get("candles") or []
    if not candles:
        raise RuntimeError("No candle data returned by FYERS.")

    frame = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    frame["datetime"] = pd.to_datetime(frame["timestamp"], unit="s", errors="coerce")

    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return (
        frame.dropna(subset=["datetime", "open", "high", "low", "close"])
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["ema20"] = result["close"].ewm(span=20, adjust=False).mean()
    result["ema50"] = result["close"].ewm(span=50, adjust=False).mean()

    typical_price = (result["high"] + result["low"] + result["close"]) / 3
    session = result["datetime"].dt.date
    cumulative_pv = (typical_price * result["volume"]).groupby(session).cumsum()
    cumulative_volume = result["volume"].groupby(session).cumsum().replace(0, pd.NA)
    result["vwap"] = cumulative_pv / cumulative_volume

    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(alpha=1 / 10, adjust=False).mean()
    midpoint = (result["high"] + result["low"]) / 2
    upper = midpoint + 3 * atr
    lower = midpoint - 3 * atr

    supertrend = pd.Series(index=result.index, dtype=float)
    direction = pd.Series(index=result.index, dtype=int)

    for index in range(len(result)):
        if index == 0:
            supertrend.iloc[index] = lower.iloc[index]
            direction.iloc[index] = 1
            continue

        if result["close"].iloc[index] >= lower.iloc[index]:
            supertrend.iloc[index] = lower.iloc[index]
            direction.iloc[index] = 1
        else:
            supertrend.iloc[index] = upper.iloc[index]
            direction.iloc[index] = -1

    result["supertrend"] = supertrend
    result["supertrend_direction"] = direction
    return result


def create_live_chart(instrument: str, timeframe: str):
    frame = add_indicators(fetch_history(instrument, timeframe))
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest

    snapshot = {
        "spot": float(latest["close"]),
        "change_percent": (
            (float(latest["close"]) - float(previous["close"]))
            / float(previous["close"])
            * 100
            if float(previous["close"]) != 0
            else None
        ),
        "ema20": float(latest["ema20"]),
        "ema50": float(latest["ema50"]),
        "vwap": float(latest["vwap"]) if not pd.isna(latest["vwap"]) else None,
        "supertrend_direction": int(latest["supertrend_direction"]),
    }

    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
    )

    figure.add_trace(
        go.Candlestick(
            x=frame["datetime"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="Price",
            increasing_line_color="#00E676",
            decreasing_line_color="#FF5252",
        ),
        row=1,
        col=1,
    )

    for column, name, color in [
        ("ema20", "EMA 20", "#42A5F5"),
        ("ema50", "EMA 50", "#FFC107"),
        ("vwap", "VWAP", "#AB47BC"),
    ]:
        figure.add_trace(
            go.Scatter(
                x=frame["datetime"],
                y=frame[column],
                name=name,
                mode="lines",
                line=dict(color=color, width=1.5),
            ),
            row=1,
            col=1,
        )

    bullish = frame["supertrend"].where(frame["supertrend_direction"] == 1)
    bearish = frame["supertrend"].where(frame["supertrend_direction"] == -1)

    figure.add_trace(
        go.Scatter(
            x=frame["datetime"],
            y=bullish,
            name="SuperTrend Bull",
            mode="lines",
            line=dict(color="#00E676", width=2),
        ),
        row=1,
        col=1,
    )

    figure.add_trace(
        go.Scatter(
            x=frame["datetime"],
            y=bearish,
            name="SuperTrend Bear",
            mode="lines",
            line=dict(color="#FF5252", width=2),
        ),
        row=1,
        col=1,
    )

    volume_colors = [
        "#00E676" if close >= open_ else "#FF5252"
        for open_, close in zip(frame["open"], frame["close"])
    ]

    figure.add_trace(
        go.Bar(
            x=frame["datetime"],
            y=frame["volume"],
            name="Volume",
            marker_color=volume_colors,
            opacity=0.55,
        ),
        row=2,
        col=1,
    )

    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        height=680,
        margin=dict(l=10, r=60, t=30, b=10),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0),
    )

    figure.update_xaxes(showgrid=False, rangeslider_visible=False)
    figure.update_yaxes(gridcolor="#202938", side="right")

    return figure, snapshot
