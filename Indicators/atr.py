import pandas as pd


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14,
    column_name: str = "ATR14"
) -> pd.DataFrame:
    """
    Calculate Wilder's Average True Range.
    """

    data = df.copy()

    previous_close = data["Close"].shift(1)

    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    data[column_name] = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return data