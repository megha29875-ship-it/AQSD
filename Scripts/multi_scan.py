import yfinance as yf

stocks = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "SBIN.NS",
    "ICICIBANK.NS"
]

for stock in stocks:

    print("=" * 50)
    print(f"Downloading {stock}...")

    data = yf.download(stock, period="3mo", interval="1d", progress=False)

    if data.empty:
        print("No data found.")
        continue

    # Fix MultiIndex columns in newer yfinance versions
    if hasattr(data.columns, "levels"):
        data.columns = data.columns.get_level_values(0)

    last = data.iloc[-1]

    print(f"Close : {last['Close']:.2f}")
    print(f"High  : {last['High']:.2f}")
    print(f"Low   : {last['Low']:.2f}")
    print(f"Open  : {last['Open']:.2f}")
    print(f"Volume: {int(last['Volume'])}")