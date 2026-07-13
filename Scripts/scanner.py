from io import StringIO

import pandas as pd
import requests


NSE_URL = (
    "https://www.nseindia.com/static/products-services/"
    "equity-derivatives-list-underlyings-information"
)


def get_fno_symbols() -> list[str]:
    """Download the current NSE individual-stock F&O symbols."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/150 Safari/537.36"
        )
    }

    response = requests.get(NSE_URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    symbols: list[str] = []

    for table in tables:
        table.columns = [
            str(column).strip().upper() for column in table.columns
        ]

        if "SYMBOL" not in table.columns:
            continue

        for value in table["SYMBOL"].dropna():
            symbol = str(value).strip().upper()

            if symbol and symbol not in {
                "NIFTY",
                "BANKNIFTY",
                "FINNIFTY",
                "MIDCPNIFTY",
                "NIFTYNXT50",
            }:
                symbols.append(f"{symbol}.NS")

    symbols = sorted(set(symbols))

    if not symbols:
        raise RuntimeError("No NSE F&O stock symbols were found.")

    return symbols


def main() -> None:
    print("Downloading latest NSE F&O stock list...\n")

    try:
        symbols = get_fno_symbols()
    except Exception as error:
        print(f"ERROR: {error}")
        return

    print(f"Total F&O stocks found: {len(symbols)}\n")

    for symbol in symbols:
        print(symbol)

    pd.DataFrame({"Symbol": symbols}).to_excel(
        "FnO_Stocks.xlsx",
        index=False,
    )

    print("\nCreated: FnO_Stocks.xlsx")


if __name__ == "__main__":
    main()