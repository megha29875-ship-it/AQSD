
from io import StringIO
from pathlib import Path
from datetime import datetime
import shutil

import pandas as pd
import requests


BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "Data"
LOG_DIR = BASE / "Logs"

OUTPUT_FILE = DATA_DIR / "FnO_Stocks.xlsx"
CHANGE_LOG = LOG_DIR / "FNO_Changes.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Official NSE static page containing the current active underlyings table
NSE_URL = (
    "https://www.nseindia.com/static/products-services/"
    "equity-derivatives-list-underlyings-information"
)

INDEX_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
    "NIFTYCPSE",
}


def download_current_list() -> pd.DataFrame:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(NSE_URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    candidates = []

    for table in tables:
        table = table.copy()

        if isinstance(table.columns, pd.MultiIndex):
            table.columns = [
                " ".join(
                    str(x).strip()
                    for x in col
                    if str(x).lower() != "nan"
                ).strip()
                for col in table.columns
            ]

        table.columns = [str(c).strip().upper() for c in table.columns]

        symbol_col = next(
            (
                c for c in table.columns
                if c == "SYMBOL" or c.endswith(" SYMBOL")
            ),
            None,
        )

        if symbol_col is None:
            continue

        part = pd.DataFrame({
            "NSE Symbol": (
                table[symbol_col]
                .astype(str)
                .str.strip()
                .str.upper()
            )
        })

        candidates.append(part)

    if not candidates:
        raise RuntimeError(
            "Could not find the current NSE F&O symbols table."
        )

    stocks = pd.concat(candidates, ignore_index=True)

    stocks = stocks[
        stocks["NSE Symbol"].str.fullmatch(
            r"[A-Z0-9&\-]+",
            na=False,
        )
    ]

    stocks = stocks[
        ~stocks["NSE Symbol"].isin(INDEX_SYMBOLS)
    ]

    stocks = (
        stocks
        .drop_duplicates("NSE Symbol")
        .sort_values("NSE Symbol")
        .reset_index(drop=True)
    )

    stocks["Symbol"] = stocks["NSE Symbol"] + ".NS"

    return stocks[["Symbol", "NSE Symbol"]]


def read_old_symbols() -> set[str]:
    if not OUTPUT_FILE.exists():
        return set()

    old = pd.read_excel(OUTPUT_FILE, sheet_name="Sheet1")

    if "Symbol" not in old.columns:
        return set()

    return set(
        old["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
    )


def save_change_log(added: list[str], removed: list[str]) -> None:
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for symbol in added:
        rows.append({
            "Timestamp": now,
            "Change": "ADDED",
            "Symbol": symbol,
        })

    for symbol in removed:
        rows.append({
            "Timestamp": now,
            "Change": "REMOVED",
            "Symbol": symbol,
        })

    if not rows:
        return

    new_log = pd.DataFrame(rows)

    if CHANGE_LOG.exists():
        old_log = pd.read_csv(CHANGE_LOG)
        new_log = pd.concat([old_log, new_log], ignore_index=True)

    new_log.to_csv(CHANGE_LOG, index=False)


def main() -> None:
    print("Downloading current active NSE F&O stock list...\n")

    old_symbols = read_old_symbols()
    stocks = download_current_list()
    new_symbols = set(stocks["Symbol"])

    added = sorted(new_symbols - old_symbols)
    removed = sorted(old_symbols - new_symbols)

    if OUTPUT_FILE.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = DATA_DIR / f"FnO_Stocks_backup_{stamp}.xlsx"
        shutil.copy2(OUTPUT_FILE, backup)
        print(f"Backup created: {backup.name}")

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
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

    save_change_log(added, removed)

    print(f"\nCurrent active F&O stocks: {len(stocks)}")
    print(f"Added: {len(added)}")
    print(f"Removed: {len(removed)}")
    print(f"\nCreated: {OUTPUT_FILE}")

    if added:
        print("\nAdded symbols:")
        print(", ".join(added))

    if removed:
        print("\nRemoved symbols:")
        print(", ".join(removed))


if __name__ == "__main__":
    main()
