import yfinance as yf

print("Downloading RELIANCE data...")

data = yf.download("RELIANCE.NS", period="3mo", interval="1d")

print(data.tail())