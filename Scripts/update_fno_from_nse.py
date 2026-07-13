
from io import StringIO
from pathlib import Path
from datetime import datetime
import shutil

import pandas as pd
import requests


# ============================================================
# PATHS
# ============================================================

BASE = Path(__file__).resolve().parent.parent
DATA_FOLDER = BASE / "Data"
OUTPUT_FILE = DATA_FOLDER / "FnO_Stocks.xlsx"

DATA_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# OFFICIAL NSE SOURCE
# ============================================================

NSE_PAGE = (
    "https://www.nseindia.com/products-services/"
    "equity-derivatives-list-underlyings-information"
)

INDEX_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
}


def fetch_current_fno_stocks() -> pd.DataFrame:
    """Fetch current individual-security F&O underlyings from NSE."""

    session = requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Referer": "https://www.nseindia.com/",
    }

    # Establish NSE cookies first.
    session.get(
        "https://www.nseindia.com/",
        headers=headers,
        timeout=30,
    )

    response = session.get(
        NSE_PAGE,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    symbol_tables = []

    for table in tables:
        cleaned = table.copy()

        # Flatten any multi-level headers.
        if isinstance(cleaned.columns, pd.MultiIndex):
            cleaned.columns = [
                " ".join(
                    str(part).strip()
                    for part in column
                    if str(part) != "nan"
                ).strip()
                for column in cleaned.columns
            ]

        cleaned.columns = [
            str(column).strip().upper()
            for column in cleaned.columns
        ]

        symbol_column = next(
            (
                column
                for column in cleaned.columns
                if column == "SYMBOL"
                or column.endswith(" SYMBOL")
            ),
            None,
        )

        if symbol_column is not None:
            symbol_tables.append(
                cleaned[[symbol_column]].rename(
                    columns={symbol_column: "NSE Symbol"}
                )
            )

    if not symbol_tables:
        raise RuntimeError(
            "NSE page was downloaded, but no SYMBOL table was found."
        )

    symbols = pd.concat(
        symbol_tables,
        ignore_index=True,
    )

    symbols["NSE Symbol"] = (
        symbols["NSE Symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    symbols = symbols[
        symbols["NSE Symbol"].str.fullmatch(
            r"[A-Z0-9&\-]+",
            na=False,
        )
    ]

    # Remove index derivatives; keep only individual securities.
    symbols = symbols[
        ~symbols["NSE Symbol"].isin(INDEX_SYMBOLS)
    ]

    symbols = (
        symbols
        .drop_duplicates(subset=["NSE Symbol"])
        .sort_values("NSE Symbol")
        .reset_index(drop=True)
    )

    symbols["Symbol"] = symbols["NSE Symbol"] + ".NS"

    return symbols[["Symbol", "NSE Symbol"]]


def save_excel(stocks: pd.DataFrame) -> None:
    """Back up the old file, then save the current NSE list."""

    if OUTPUT_FILE.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = DATA_FOLDER / f"FnO_Stocks_backup_{timestamp}.xlsx"
        shutil.copy2(OUTPUT_FILE, backup_file)
        print(f"Backup created: {backup_file.name}")

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:
        stocks[["Symbol"]].to_excel(
            writer,
            sheet_name="Sheet1",
            index=False,
        )

        stocks.to_excel(
            writer,
            sheet_name="NSE Reference",
            index=False,
        )

    print(f"\nCreated: {OUTPUT_FILE}")
    print(f"Current individual F&O stocks: {len(stocks)}")
    print("\nFirst 10 symbols:")
    print(stocks.head(10).to_string(index=False))


def main() -> None:
    print("Downloading current F&O underlyings from NSE...\n")
    stocks = fetch_current_fno_stocks()

    if stocks.empty:
        raise RuntimeError("NSE returned an empty stock list.")

    save_excel(stocks)


if __name__ == "__main__":
    main()
