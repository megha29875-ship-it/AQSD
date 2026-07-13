import numpy as np
import pandas as pd

from Indicators.atr import calculate_atr


def calculate_supertrend(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0
) -> pd.DataFrame:

    data = df.copy()

    atr_column = f"ATR{atr_period}"

    # Calculate Wilder ATR
    data = calculate_atr(
        data,
        period=atr_period,
        column_name=atr_column
    )

    midpoint = (data["High"] + data["Low"]) / 2

    basic_upper = midpoint + multiplier * data[atr_column]
    basic_lower = midpoint - multiplier * data[atr_column]

    final_upper = pd.Series(
        np.nan,
        index=data.index,
        dtype="float64"
    )

    final_lower = pd.Series(
        np.nan,
        index=data.index,
        dtype="float64"
    )

    supertrend = pd.Series(
        np.nan,
        index=data.index,
        dtype="float64"
    )

    direction = pd.Series(
        "",
        index=data.index,
        dtype="object"
    )

    # Find first row where ATR is available
    valid_positions = np.where(
        data[atr_column].notna().to_numpy()
    )[0]

    if len(valid_positions) == 0:
        data["ST_Upper"] = final_upper
        data["ST_Lower"] = final_lower
        data["Supertrend"] = supertrend
        data["ST_Direction"] = direction
        return data

    start = int(valid_positions[0])

    # Initialise bands
    final_upper.iloc[start] = basic_upper.iloc[start]
    final_lower.iloc[start] = basic_lower.iloc[start]

    # Initialise Supertrend
    if data["Close"].iloc[start] <= final_upper.iloc[start]:
        supertrend.iloc[start] = final_upper.iloc[start]
        direction.iloc[start] = "SELL"
    else:
        supertrend.iloc[start] = final_lower.iloc[start]
        direction.iloc[start] = "BUY"

    # Calculate subsequent rows
    for i in range(start + 1, len(data)):

        previous_close = data["Close"].iloc[i - 1]

        # Final upper band
        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or previous_close > final_upper.iloc[i - 1]
        ):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        # Final lower band
        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or previous_close < final_lower.iloc[i - 1]
        ):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        previous_supertrend = supertrend.iloc[i - 1]

        # Previous trend was bearish
        if previous_supertrend == final_upper.iloc[i - 1]:

            if data["Close"].iloc[i] <= final_upper.iloc[i]:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = "SELL"
            else:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = "BUY"

        # Previous trend was bullish
        else:

            if data["Close"].iloc[i] >= final_lower.iloc[i]:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = "BUY"
            else:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = "SELL"

    data["ST_Upper"] = final_upper
    data["ST_Lower"] = final_lower
    data["Supertrend"] = supertrend
    data["ST_Direction"] = direction

    return data