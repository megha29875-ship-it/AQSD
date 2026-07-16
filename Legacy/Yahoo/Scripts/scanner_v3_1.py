from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# SETTINGS
# ============================================================

EMA20_PERIOD = 20
EMA50_PERIOD = 50
EMA200_PERIOD = 200

ATR_PERIOD = 14
RSI_PERIOD = 14
ADX_PERIOD = 14

SUPERTREND_ATR_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

VOLUME_AVG_PERIOD = 20
BREAKOUT_PERIOD = 20
HIGH_LOW_PERIOD = 252

STOP_ATR_MULTIPLIER = 1.5
TARGET1_RR = 2.0
TARGET2_RR = 3.0


# ============================================================
# FILE PATHS
# ============================================================

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "Data" / "FnO_Stocks.xlsx"
OUTPUT_FILE = BASE / "Output" / "Dashboard.xlsx"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# INDICATORS
# ============================================================

def calculate_atr(df: pd.DataFrame, period: int, column_name: str) -> pd.DataFrame:
    data = df.copy()
    previous_close = data["Close"].shift(1)

    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    data[column_name] = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return data


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    data = df.copy()
    change = data["Close"].diff()

    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)

    average_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = average_gain / average_loss
    data["RSI14"] = 100 - (100 / (1 + rs))

    data.loc[(average_loss == 0) & (average_gain > 0), "RSI14"] = 100
    data.loc[(average_gain == 0) & (average_loss > 0), "RSI14"] = 0

    return data


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    data = df.copy()

    up_move = data["High"].diff()
    down_move = -data["Low"].diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=data.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=data.index,
    )

    previous_close = data["Close"].shift(1)

    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    plus_di = 100 * (
        plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        / atr
    )

    minus_di = 100 * (
        minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        / atr
    )

    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / denominator) * 100

    data["Plus_DI"] = plus_di
    data["Minus_DI"] = minus_di
    data["ADX14"] = dx.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return data


def calculate_supertrend(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    data = df.copy()
    atr_column = f"ATR{atr_period}"

    data = calculate_atr(data, period=atr_period, column_name=atr_column)

    midpoint = (data["High"] + data["Low"]) / 2
    basic_upper = midpoint + multiplier * data[atr_column]
    basic_lower = midpoint - multiplier * data[atr_column]

    final_upper = pd.Series(np.nan, index=data.index, dtype="float64")
    final_lower = pd.Series(np.nan, index=data.index, dtype="float64")
    supertrend = pd.Series(np.nan, index=data.index, dtype="float64")
    direction = pd.Series("", index=data.index, dtype="object")

    valid_positions = np.where(data[atr_column].notna().to_numpy())[0]

    if len(valid_positions) == 0:
        data["Supertrend"] = supertrend
        data["ST_Direction"] = direction
        return data

    start = int(valid_positions[0])

    final_upper.iloc[start] = basic_upper.iloc[start]
    final_lower.iloc[start] = basic_lower.iloc[start]

    if data["Close"].iloc[start] <= final_upper.iloc[start]:
        direction.iloc[start] = "SELL"
        supertrend.iloc[start] = final_upper.iloc[start]
    else:
        direction.iloc[start] = "BUY"
        supertrend.iloc[start] = final_lower.iloc[start]

    for i in range(start + 1, len(data)):
        previous_close = data["Close"].iloc[i - 1]

        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or previous_close > final_upper.iloc[i - 1]
        ):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or previous_close < final_lower.iloc[i - 1]
        ):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        current_close = data["Close"].iloc[i]
        previous_direction = direction.iloc[i - 1]

        if previous_direction == "BUY":
            if current_close < final_lower.iloc[i]:
                direction.iloc[i] = "SELL"
                supertrend.iloc[i] = final_upper.iloc[i]
            else:
                direction.iloc[i] = "BUY"
                supertrend.iloc[i] = final_lower.iloc[i]
        else:
            if current_close > final_upper.iloc[i]:
                direction.iloc[i] = "BUY"
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                direction.iloc[i] = "SELL"
                supertrend.iloc[i] = final_upper.iloc[i]

    data["Supertrend"] = supertrend
    data["ST_Direction"] = direction

    return data


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_ema_trend(close: float, ema20: float, ema50: float, ema200: float) -> str:
    if close > ema20 > ema50 > ema200:
        return "Strong Uptrend"
    if close > ema20 and ema20 > ema50:
        return "Uptrend"
    if close > ema20:
        return "Pullback"
    return "Downtrend"


def classify_rsi(rsi: float) -> str:
    if rsi >= 70:
        return "Overbought"
    if rsi >= 55:
        return "Bullish"
    if rsi >= 45:
        return "Neutral"
    if rsi >= 30:
        return "Bearish"
    return "Oversold"


def classify_adx(adx: float) -> str:
    if adx >= 40:
        return "Very Strong"
    if adx >= 25:
        return "Strong"
    if adx >= 20:
        return "Developing"
    return "Weak"


# ============================================================
# SCORES
# ============================================================

def calculate_option_score(
    st_direction: str,
    fresh_st_buy: bool,
    ema_trend: str,
    fresh_ema20_cross: bool,
    rsi: float,
    rsi_cross_50: bool,
    adx: float,
    adx_rising: bool,
    volume_breakout: bool,
    breakout_20d: bool,
    atr_percent: float,
    st_gap_percent: float,
) -> int:
    score = 0

    if st_direction == "BUY":
        score += 20
    if fresh_st_buy:
        score += 15

    if ema_trend == "Strong Uptrend":
        score += 15
    elif ema_trend == "Uptrend":
        score += 10
    elif ema_trend == "Pullback":
        score += 5

    if fresh_ema20_cross:
        score += 10

    if 55 <= rsi < 70:
        score += 10
    elif 50 <= rsi < 55:
        score += 5

    if rsi_cross_50:
        score += 5

    if adx >= 25:
        score += 10
    elif adx >= 20:
        score += 5

    if adx_rising:
        score += 5
    if volume_breakout:
        score += 5
    if breakout_20d:
        score += 10
    if 1.5 <= atr_percent <= 4:
        score += 5
    if st_direction == "BUY" and 0 <= st_gap_percent <= 3:
        score += 5

    return min(score, 100)


def calculate_investment_score(
    close: float,
    ema50: float,
    ema200: float,
    high_52w: float,
    rsi: float,
    adx: float,
) -> int:
    score = 0

    if close > ema200:
        score += 30
    if ema50 > ema200:
        score += 25
    if close > ema50:
        score += 15

    distance_from_high = ((high_52w - close) / high_52w) * 100

    if distance_from_high <= 10:
        score += 15
    elif distance_from_high <= 20:
        score += 10

    if 50 <= rsi <= 70:
        score += 10
    if adx >= 20:
        score += 5

    return min(score, 100)


def option_action(score: int, st_direction: str) -> str:
    if st_direction != "BUY":
        return "AVOID"
    if score >= 85:
        return "STRONG BUY"
    if score >= 70:
        return "BUY"
    if score >= 55:
        return "WATCH"
    return "WAIT"


def investment_action(score: int) -> str:
    if score >= 80:
        return "STRONG"
    if score >= 65:
        return "ACCUMULATE"
    if score >= 50:
        return "WATCH"
    return "WEAK"


# ============================================================
# INPUT
# ============================================================

if not DATA_FILE.exists():
    raise FileNotFoundError(f"File not found:\n{DATA_FILE}")

stocks_df = pd.read_excel(DATA_FILE)

if "Symbol" not in stocks_df.columns:
    raise ValueError("FnO_Stocks.xlsx must contain a column named Symbol.")

symbols = (
    stocks_df["Symbol"]
    .dropna()
    .astype(str)
    .str.strip()
)
symbols = symbols[symbols.ne("")]

option_results = []
investment_results = []

print("Starting AQSD v3.1...\n")
print(f"Stocks to scan: {len(symbols)}\n")


# ============================================================
# SCAN
# ============================================================

for number, symbol in enumerate(symbols, start=1):
    print(f"[{number}/{len(symbols)}] Downloading {symbol}")

    try:
        df = yf.download(
            symbol,
            period="2y",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )

        if df.empty:
            print(f"No data for {symbol}")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        missing = [column for column in required_columns if column not in df.columns]

        if missing:
            print(f"Missing columns for {symbol}: {missing}")
            continue

        df = df.dropna(subset=required_columns)

        if len(df) < HIGH_LOW_PERIOD:
            print(f"Insufficient history for {symbol}")
            continue

        df["EMA20"] = df["Close"].ewm(span=EMA20_PERIOD, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=EMA50_PERIOD, adjust=False).mean()
        df["EMA200"] = df["Close"].ewm(span=EMA200_PERIOD, adjust=False).mean()

        df = calculate_atr(df, ATR_PERIOD, "ATR14")
        df = calculate_supertrend(df, SUPERTREND_ATR_PERIOD, SUPERTREND_MULTIPLIER)
        df = calculate_rsi(df, RSI_PERIOD)
        df = calculate_adx(df, ADX_PERIOD)

        df["AverageVolume20"] = df["Volume"].rolling(VOLUME_AVG_PERIOD).mean()
        df["VolumeRatio"] = df["Volume"] / df["AverageVolume20"]

        df["PreviousHigh20"] = df["High"].rolling(BREAKOUT_PERIOD).max().shift(1)
        df["High52W"] = df["High"].rolling(HIGH_LOW_PERIOD).max()
        df["Low52W"] = df["Low"].rolling(HIGH_LOW_PERIOD).min()

        valid = df.dropna(
            subset=[
                "EMA20", "EMA50", "EMA200", "ATR14", "Supertrend",
                "RSI14", "ADX14", "VolumeRatio", "PreviousHigh20",
                "High52W", "Low52W",
            ]
        )

        if len(valid) < 2:
            print(f"Indicators unavailable for {symbol}")
            continue

        last = valid.iloc[-1]
        previous = valid.iloc[-2]

        close = float(last["Close"])
        volume = int(last["Volume"])
        previous_close = float(previous["Close"])

        ema20 = float(last["EMA20"])
        ema50 = float(last["EMA50"])
        ema200 = float(last["EMA200"])
        previous_ema20 = float(previous["EMA20"])

        atr14 = float(last["ATR14"])
        atr_percent = (atr14 / close) * 100

        rsi = float(last["RSI14"])
        previous_rsi = float(previous["RSI14"])

        adx = float(last["ADX14"])
        previous_adx = float(previous["ADX14"])

        plus_di = float(last["Plus_DI"])
        minus_di = float(last["Minus_DI"])

        volume_ratio = float(last["VolumeRatio"])

        supertrend = float(last["Supertrend"])
        st_direction = str(last["ST_Direction"])
        previous_st_direction = str(previous["ST_Direction"])

        fresh_st_buy = st_direction == "BUY" and previous_st_direction == "SELL"
        fresh_st_sell = st_direction == "SELL" and previous_st_direction == "BUY"

        fresh_ema20_cross = previous_close <= previous_ema20 and close > ema20
        rsi_cross_50 = previous_rsi <= 50 and rsi > 50
        adx_rising = adx > previous_adx
        volume_breakout = volume_ratio >= 1.5

        previous_high_20 = float(last["PreviousHigh20"])
        breakout_20d = close > previous_high_20

        if fresh_st_buy:
            st_signal = "Fresh BUY"
        elif fresh_st_sell:
            st_signal = "Fresh SELL"
        else:
            st_signal = st_direction

        st_gap = close - supertrend
        st_gap_percent = (st_gap / supertrend) * 100 if supertrend != 0 else np.nan

        ema_trend = classify_ema_trend(close, ema20, ema50, ema200)
        rsi_status = classify_rsi(rsi)
        adx_status = classify_adx(adx)

        high_52w = float(last["High52W"])
        low_52w = float(last["Low52W"])

        distance_from_52w_high = ((high_52w - close) / high_52w) * 100

        entry = close
        atr_stop = close - (STOP_ATR_MULTIPLIER * atr14)

        if st_direction == "BUY":
            stop_loss = max(supertrend, atr_stop)
            risk = entry - stop_loss
        else:
            stop_loss = np.nan
            risk = np.nan

        if pd.notna(risk) and risk > 0:
            target_1 = entry + TARGET1_RR * risk
            target_2 = entry + TARGET2_RR * risk
            rr_1 = f"1:{TARGET1_RR:.0f}"
            rr_2 = f"1:{TARGET2_RR:.0f}"
        else:
            target_1 = np.nan
            target_2 = np.nan
            rr_1 = ""
            rr_2 = ""

        opt_score = calculate_option_score(
            st_direction, fresh_st_buy, ema_trend, fresh_ema20_cross,
            rsi, rsi_cross_50, adx, adx_rising, volume_breakout,
            breakout_20d, atr_percent, st_gap_percent,
        )

        inv_score = calculate_investment_score(
            close, ema50, ema200, high_52w, rsi, adx,
        )

        option_results.append(
            {
                "Symbol": symbol,
                "Close": round(close, 2),
                "ST Direction": st_direction,
                "ST Signal": st_signal,
                "Supertrend": round(supertrend, 2),
                "ST Gap %": round(st_gap_percent, 2),
                "Fresh ST Buy": "YES" if fresh_st_buy else "NO",
                "Fresh ST Sell": "YES" if fresh_st_sell else "NO",
                "EMA20 Cross": "YES" if fresh_ema20_cross else "NO",
                "RSI Cross 50": "YES" if rsi_cross_50 else "NO",
                "ADX Rising": "YES" if adx_rising else "NO",
                "Volume Breakout": "YES" if volume_breakout else "NO",
                "20D Breakout": "YES" if breakout_20d else "NO",
                "EMA Trend": ema_trend,
                "EMA20": round(ema20, 2),
                "EMA50": round(ema50, 2),
                "EMA200": round(ema200, 2),
                "RSI14": round(rsi, 2),
                "RSI Status": rsi_status,
                "ADX14": round(adx, 2),
                "ADX Status": adx_status,
                "Plus DI": round(plus_di, 2),
                "Minus DI": round(minus_di, 2),
                "ATR14": round(atr14, 2),
                "ATR %": round(atr_percent, 2),
                "Volume": volume,
                "Volume Ratio": round(volume_ratio, 2),
                "Entry": round(entry, 2),
                "Stop Loss": round(stop_loss, 2) if pd.notna(stop_loss) else "",
                "Target 1": round(target_1, 2) if pd.notna(target_1) else "",
                "Target 2": round(target_2, 2) if pd.notna(target_2) else "",
                "R:R T1": rr_1,
                "R:R T2": rr_2,
                "Option Score": opt_score,
                "Action": option_action(opt_score, st_direction),
            }
        )

        investment_results.append(
            {
                "Symbol": symbol,
                "Close": round(close, 2),
                "EMA50": round(ema50, 2),
                "EMA200": round(ema200, 2),
                "Above EMA200": "YES" if close > ema200 else "NO",
                "EMA50 > EMA200": "YES" if ema50 > ema200 else "NO",
                "52W High": round(high_52w, 2),
                "52W Low": round(low_52w, 2),
                "Distance From 52W High %": round(distance_from_52w_high, 2),
                "RSI14": round(rsi, 2),
                "ADX14": round(adx, 2),
                "Investment Score": inv_score,
                "Investment Action": investment_action(inv_score),
            }
        )

    except Exception as error:
        print(f"Error processing {symbol}: {error}")


# ============================================================
# EXPORT
# ============================================================

option_df = pd.DataFrame(option_results)
investment_df = pd.DataFrame(investment_results)

if option_df.empty:
    print("\nNo results generated.")
    raise SystemExit(1)

option_df = option_df.sort_values(
    by=["Option Score", "ST Gap %"],
    ascending=[False, True],
).reset_index(drop=True)

option_df.insert(0, "Rank", range(1, len(option_df) + 1))

investment_df = investment_df.sort_values(
    by="Investment Score",
    ascending=False,
).reset_index(drop=True)

investment_df.insert(0, "Rank", range(1, len(investment_df) + 1))

summary_df = pd.DataFrame(
    {
        "Metric": [
            "Stocks Scanned", "Strong Buy", "Buy", "Watch", "Wait", "Avoid",
            "Fresh ST Buy", "20D Breakout", "Volume Breakout",
        ],
        "Value": [
            len(option_df),
            int((option_df["Action"] == "STRONG BUY").sum()),
            int((option_df["Action"] == "BUY").sum()),
            int((option_df["Action"] == "WATCH").sum()),
            int((option_df["Action"] == "WAIT").sum()),
            int((option_df["Action"] == "AVOID").sum()),
            int((option_df["Fresh ST Buy"] == "YES").sum()),
            int((option_df["20D Breakout"] == "YES").sum()),
            int((option_df["Volume Breakout"] == "YES").sum()),
        ],
    }
)

try:
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        option_df.to_excel(writer, sheet_name="Option Buying", index=False)
        investment_df.to_excel(writer, sheet_name="Long Term", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

except PermissionError:
    print("\nClose Dashboard.xlsx and run again.")
    raise SystemExit(1)

print("\nAQSD v3.1 completed successfully.\n")

print(
    option_df[
        [
            "Rank", "Symbol", "ST Signal", "RSI14", "ADX14",
            "Volume Ratio", "20D Breakout", "Option Score", "Action",
        ]
    ].to_string(index=False)
)

print(f"\nDashboard saved at:\n{OUTPUT_FILE}")
