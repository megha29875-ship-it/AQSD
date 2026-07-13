"""
=========================================================
AQSD Professional
Module : Market Pulse
Version: 1.0
=========================================================
"""

from pathlib import Path
import pandas as pd
import yfinance as yf

# -----------------------------
# Paths
# -----------------------------

BASE = Path(__file__).resolve().parent.parent

OUTPUT_FILE = BASE / "Output" / "Dashboard.xlsx"

# -----------------------------
# Market Symbols
# -----------------------------

MARKETS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "INDIA VIX": "^INDIAVIX"
}

# -----------------------------
# RSI Function
# -----------------------------

def calculate_rsi(close, period=14):

    delta = close.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()

    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss

    return 100 - (100/(1+rs))

# -----------------------------
# Download Market Data
# -----------------------------

def get_market(symbol):

    df = yf.download(
        symbol,
        period="6mo",
        interval="1d",
        progress=False,
        auto_adjust=True
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()

    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    df["RSI"] = calculate_rsi(df["Close"])

    return df

# =======================================================
# TEST
# =======================================================

print("\nAQSD MARKET PULSE\n")

for name, symbol in MARKETS.items():

    print(f"Downloading {name}...")

    df = get_market(symbol)

    if df is None:
        print("Failed\n")
        continue

    last = df.iloc[-1]

    print("--------------------------------")

    print(name)

    print("Close :", round(last["Close"],2))

    print("EMA20 :", round(last["EMA20"],2))

    print("EMA50 :", round(last["EMA50"],2))

    print("RSI   :", round(last["RSI"],2))

    print()