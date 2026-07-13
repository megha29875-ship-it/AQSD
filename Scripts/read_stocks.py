from pathlib import Path
import pandas as pd

# AQSD main folder
base_folder = Path(__file__).resolve().parent.parent

# Excel file location
excel_file = base_folder / "Data" / "FnO_Stocks.xlsx"

print(f"Reading stock list from:\n{excel_file}\n")

if not excel_file.exists():
    print("ERROR: FnO_Stocks.xlsx was not found.")
    raise SystemExit(1)

stocks_df = pd.read_excel(excel_file)

if "Symbol" not in stocks_df.columns:
    print("ERROR: Excel must contain a column named Symbol.")
    raise SystemExit(1)

# Remove blank cells and extra spaces
symbols = (
    stocks_df["Symbol"]
    .dropna()
    .astype(str)
    .str.strip()
)

print(f"Stocks found: {len(symbols)}\n")

for symbol in symbols:
    print(symbol)