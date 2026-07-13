import pandas as pd


def calculate_rsi(df, period=14):

    data = df.copy()

    delta = data["Close"].diff()

    gain = delta.where(delta > 0, 0)

    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(
        alpha=1/period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss

    data["RSI"] = 100 - (100 / (1 + rs))

    return data