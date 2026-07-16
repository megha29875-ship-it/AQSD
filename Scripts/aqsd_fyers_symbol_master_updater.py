"""
AQSD Professional
Module: FYERS NSE F&O Symbol Master Updater
Version: 1.0

Purpose
-------
1. Download the latest FYERS NSE Equity Derivatives symbol master.
2. Preserve every valid futures and options contract.
3. Build a complete futures contract master.
4. Assign NEAR / NEXT / FAR expiry separately for each underlying.
5. Preserve lot size, tick size, expiry, strike and option type.
6. Create backups and comparison reports.

Official FYERS NSE F&O symbol-master URL
---------------------------------------
https://public.fyers.in/sym_details/NSE_FO.csv

Safety
------
- Does not delete Yahoo files.
- Does not overwrite AQSD_Symbol_Master.csv.
- Backs up prior FYERS outputs before replacing them.
- Does not place orders.
- Does not write to the AQSD database.

Commands
--------
python aqsd_fyers_symbol_master_updater.py --download
python aqsd_fyers_symbol_master_updater.py --build
python aqsd_fyers_symbol_master_updater.py --run
python aqsd_fyers_symbol_master_updater.py --status

Run with the FYERS environment:
C:\\Users\\megha\\AQSD\\.venv-fyers\\Scripts\\python.exe
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"
BACKUP_DIR = DATA_DIR / "FYERS_Symbol_Master_Backups"

SOURCE_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

RAW_FILE = DATA_DIR / "FYERS_NSE_FO_Raw.csv"
CONTRACTS_FILE = DATA_DIR / "FYERS_FNO_Contracts.csv"
FUTURES_FILE = DATA_DIR / "FYERS_Futures_Contracts.csv"
FUTURES_3M_FILE = DATA_DIR / "FYERS_Futures_Near_Next_Far.csv"
OPTIONS_FILE = DATA_DIR / "FYERS_Options_Contracts.csv"
UNDERLYINGS_FILE = DATA_DIR / "FYERS_FNO_Underlyings.csv"

AUDIT_FILE = OUTPUT_DIR / "FYERS_Symbol_Master_Audit.csv"
ADDITIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Additions.csv"
DELETIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Deletions.csv"
LOT_CHANGES_FILE = OUTPUT_DIR / "FYERS_Lot_Size_Changes.csv"

# FYERS files have historically been distributed without headers.
# These names cover the commonly published 19-column layout.
FYERS_COLUMNS_19 = [
    "token",
    "description",
    "instrument_type_code",
    "lot_size",
    "tick_size",
    "isin",
    "trading_session",
    "last_update",
    "expiry_raw",
    "fyers_symbol",
    "exchange_token",
    "minimum_lot_size",
    "underlying_token",
    "underlying_symbol",
    "strike_price",
    "option_type",
    "reserved_1",
    "reserved_2",
    "reserved_3",
]


def ensure_folders() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def download_file() -> None:
    ensure_folders()

    temporary = RAW_FILE.with_suffix(".download")

    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 AQSD-FYERS-Symbol-Master-Updater/1.0"
            )
        },
    )

    print("Downloading FYERS NSE F&O symbol master...")
    print(SOURCE_URL)

    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()

    if len(content) < 1000:
        raise RuntimeError(
            "Downloaded FYERS file is unexpectedly small "
            f"({len(content)} bytes)."
        )

    temporary.write_bytes(content)

    first_bytes = content[:200].lower()

    if b"<html" in first_bytes or b"<!doctype" in first_bytes:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "FYERS returned an HTML page instead of the CSV file."
        )

    if RAW_FILE.exists():
        backup_file(RAW_FILE)

    temporary.replace(RAW_FILE)

    print(f"Saved: {RAW_FILE}")
    print(f"Bytes: {RAW_FILE.stat().st_size:,}")
    print(f"SHA256: {file_sha256(RAW_FILE)}")


def backup_file(path: Path) -> Path:
    ensure_folders()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"

    shutil.copy2(path, destination)
    return destination


def backup_outputs() -> None:
    for path in [
        CONTRACTS_FILE,
        FUTURES_FILE,
        FUTURES_3M_FILE,
        OPTIONS_FILE,
        UNDERLYINGS_FILE,
    ]:
        if path.exists():
            backup_file(path)


def count_csv_columns(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.reader(handle)
        first = next(reader)

    return len(first)


def read_raw_master() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"FYERS raw symbol master not found:\n{RAW_FILE}"
        )

    column_count = count_csv_columns(RAW_FILE)

    if column_count == len(FYERS_COLUMNS_19):
        frame = pd.read_csv(
            RAW_FILE,
            names=FYERS_COLUMNS_19,
            header=None,
            low_memory=False,
        )
    else:
        frame = pd.read_csv(
            RAW_FILE,
            header=None,
            low_memory=False,
        )

        frame.columns = [
            f"column_{index}"
            for index in range(1, len(frame.columns) + 1)
        ]

        raise RuntimeError(
            "FYERS symbol-master layout has changed. "
            f"Detected {column_count} columns instead of "
            f"{len(FYERS_COLUMNS_19)}. "
            f"Raw file preserved at {RAW_FILE}."
        )

    return frame


def parse_expiry(value: Any) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if not text or text.lower() in {"none", "nan", "0"}:
        return pd.NaT

    numeric = pd.to_numeric(text, errors="coerce")

    if not pd.isna(numeric):
        number = float(numeric)

        # Unix seconds.
        if 1_000_000_000 <= number <= 5_000_000_000:
            return pd.to_datetime(
                int(number),
                unit="s",
                errors="coerce",
            ).normalize()

        # YYYYMMDD.
        if 20_000_000 <= number <= 21_000_000:
            return pd.to_datetime(
                str(int(number)),
                format="%Y%m%d",
                errors="coerce",
            )

    return pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=True,
    )


def instrument_family(row: pd.Series) -> str:
    symbol = str(row.get("fyers_symbol", "")).upper()
    option_type = str(row.get("option_type", "")).upper()
    description = str(row.get("description", "")).upper()

    if symbol.endswith("-FUT") or " FUT " in f" {description} ":
        return "FUTURE"

    if option_type in {"CE", "PE"}:
        return "OPTION"

    if symbol.endswith("-CE") or symbol.endswith("-PE"):
        return "OPTION"

    return "OTHER"


def derive_underlying(row: pd.Series) -> str:
    value = str(row.get("underlying_symbol", "")).strip().upper()

    if value and value not in {"NAN", "NONE", "-1", "0"}:
        return value.replace("NSE:", "").replace("-EQ", "")

    symbol = str(row.get("fyers_symbol", "")).strip().upper()

    if symbol.startswith("NSE:"):
        symbol = symbol[4:]

    for suffix in ("-FUT", "-CE", "-PE"):
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]

    # FYERS derivative symbols generally begin with the underlying,
    # followed by expiry/strike information. The symbol master field
    # remains the preferred source when available.
    return symbol


def clean_master(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    result["fyers_symbol"] = (
        result["fyers_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["underlying"] = result.apply(
        derive_underlying,
        axis=1,
    )

    result["instrument_family"] = result.apply(
        instrument_family,
        axis=1,
    )

    result["expiry_date"] = result["expiry_raw"].apply(
        parse_expiry
    )

    for column in [
        "lot_size",
        "minimum_lot_size",
        "tick_size",
        "strike_price",
    ]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    # Prefer the explicit minimum lot size when valid.
    result["effective_lot_size"] = result[
        "minimum_lot_size"
    ].where(
        result["minimum_lot_size"] > 0,
        result["lot_size"],
    )

    today = pd.Timestamp(date.today())

    result["is_expired"] = (
        result["expiry_date"].notna()
        & (result["expiry_date"] < today)
    )

    result["days_to_expiry"] = (
        result["expiry_date"] - today
    ).dt.days

    result["option_type"] = (
        result["option_type"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": "", "NONE": ""})
    )

    result = result.drop_duplicates(
        subset=["fyers_symbol"],
        keep="last",
    )

    return result


def assign_expiry_buckets(
    futures: pd.DataFrame,
) -> pd.DataFrame:
    result = futures.copy()

    result["expiry_bucket"] = "LATER"
    result["expiry_rank"] = pd.NA

    valid = result[
        result["expiry_date"].notna()
        & (~result["is_expired"])
    ].copy()

    for underlying, group in valid.groupby("underlying"):
        expiries = sorted(
            pd.Series(group["expiry_date"].unique())
            .dropna()
            .tolist()
        )

        mapping: dict[pd.Timestamp, tuple[int, str]] = {}

        names = {
            1: "NEAR",
            2: "NEXT",
            3: "FAR",
        }

        for rank, expiry in enumerate(expiries, start=1):
            mapping[pd.Timestamp(expiry)] = (
                rank,
                names.get(rank, "LATER"),
            )

        indexes = group.index

        result.loc[indexes, "expiry_rank"] = (
            result.loc[indexes, "expiry_date"]
            .map(lambda value: mapping[pd.Timestamp(value)][0])
        )

        result.loc[indexes, "expiry_bucket"] = (
            result.loc[indexes, "expiry_date"]
            .map(lambda value: mapping[pd.Timestamp(value)][1])
        )

    return result


def build_underlying_master(
    contracts: pd.DataFrame,
    futures: pd.DataFrame,
    options: pd.DataFrame,
) -> pd.DataFrame:
    all_underlyings = sorted(
        {
            value
            for value in contracts["underlying"].dropna().astype(str)
            if value and value not in {"NAN", "NONE"}
        }
    )

    rows: list[dict[str, Any]] = []

    for underlying in all_underlyings:
        future_rows = futures[
            futures["underlying"] == underlying
        ]

        option_rows = options[
            options["underlying"] == underlying
        ]

        live_future_rows = future_rows[
            ~future_rows["is_expired"]
        ]

        expiries = sorted(
            live_future_rows["expiry_date"]
            .dropna()
            .dt.strftime("%Y-%m-%d")
            .unique()
            .tolist()
        )

        lot_sizes = sorted(
            {
                int(value)
                for value in live_future_rows[
                    "effective_lot_size"
                ].dropna()
                if float(value) > 0
            }
        )

        rows.append(
            {
                "underlying": underlying,
                "live_futures_contracts": len(live_future_rows),
                "live_options_contracts": int(
                    (~option_rows["is_expired"]).sum()
                ),
                "near_expiry": expiries[0] if len(expiries) >= 1 else "",
                "next_expiry": expiries[1] if len(expiries) >= 2 else "",
                "far_expiry": expiries[2] if len(expiries) >= 3 else "",
                "lot_sizes": ",".join(map(str, lot_sizes)),
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    return pd.DataFrame(rows)


def previous_file_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def create_change_reports(
    previous_futures: pd.DataFrame,
    current_futures: pd.DataFrame,
) -> None:
    old_symbols = (
        set(previous_futures["fyers_symbol"].astype(str))
        if not previous_futures.empty
        and "fyers_symbol" in previous_futures.columns
        else set()
    )

    new_symbols = set(
        current_futures["fyers_symbol"].astype(str)
    )

    additions = current_futures[
        current_futures["fyers_symbol"].isin(
            new_symbols - old_symbols
        )
    ].copy()

    if previous_futures.empty:
        deletions = pd.DataFrame(
            columns=current_futures.columns
        )
    else:
        deletions = previous_futures[
            previous_futures["fyers_symbol"].astype(str).isin(
                old_symbols - new_symbols
            )
        ].copy()

    additions.to_csv(
        ADDITIONS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    deletions.to_csv(
        DELETIONS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    lot_changes = pd.DataFrame()

    if (
        not previous_futures.empty
        and "effective_lot_size" in previous_futures.columns
    ):
        old = previous_futures[
            ["fyers_symbol", "effective_lot_size"]
        ].copy()

        old = old.rename(
            columns={
                "effective_lot_size": "old_lot_size"
            }
        )

        new = current_futures[
            ["fyers_symbol", "effective_lot_size"]
        ].copy()

        new = new.rename(
            columns={
                "effective_lot_size": "new_lot_size"
            }
        )

        lot_changes = old.merge(
            new,
            on="fyers_symbol",
            how="inner",
        )

        lot_changes = lot_changes[
            pd.to_numeric(
                lot_changes["old_lot_size"],
                errors="coerce",
            )
            != pd.to_numeric(
                lot_changes["new_lot_size"],
                errors="coerce",
            )
        ]

    lot_changes.to_csv(
        LOT_CHANGES_FILE,
        index=False,
        encoding="utf-8-sig",
    )


def build_outputs() -> None:
    ensure_folders()

    raw = read_raw_master()
    contracts = clean_master(raw)

    previous_futures = previous_file_frame(
        FUTURES_FILE
    )

    futures = contracts[
        contracts["instrument_family"] == "FUTURE"
    ].copy()

    options = contracts[
        contracts["instrument_family"] == "OPTION"
    ].copy()

    futures = assign_expiry_buckets(
        futures
    )

    futures = futures.sort_values(
        [
            "underlying",
            "expiry_date",
            "fyers_symbol",
        ],
        na_position="last",
    ).reset_index(drop=True)

    options = options.sort_values(
        [
            "underlying",
            "expiry_date",
            "strike_price",
            "option_type",
        ],
        na_position="last",
    ).reset_index(drop=True)

    three_month = futures[
        (~futures["is_expired"])
        & futures["expiry_bucket"].isin(
            ["NEAR", "NEXT", "FAR"]
        )
    ].copy()

    underlyings = build_underlying_master(
        contracts,
        futures,
        options,
    )

    backup_outputs()

    contracts.to_csv(
        CONTRACTS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    futures.to_csv(
        FUTURES_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    three_month.to_csv(
        FUTURES_3M_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    options.to_csv(
        OPTIONS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    underlyings.to_csv(
        UNDERLYINGS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    create_change_reports(
        previous_futures,
        futures,
    )

    audit = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "raw_rows": len(raw),
                "clean_contract_rows": len(contracts),
                "futures_rows": len(futures),
                "live_futures_rows": int(
                    (~futures["is_expired"]).sum()
                ),
                "near_next_far_rows": len(three_month),
                "options_rows": len(options),
                "unique_underlyings": len(underlyings),
                "raw_file_bytes": RAW_FILE.stat().st_size,
                "raw_file_sha256": file_sha256(RAW_FILE),
                "source_url": SOURCE_URL,
            }
        ]
    )

    audit.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nAQSD FYERS SYMBOL MASTER UPDATE")
    print("=" * 78)
    print(f"Raw rows:              {len(raw):,}")
    print(f"Clean contracts:       {len(contracts):,}")
    print(f"Futures contracts:     {len(futures):,}")
    print(
        f"Live futures:          "
        f"{int((~futures['is_expired']).sum()):,}"
    )
    print(f"Near/Next/Far rows:    {len(three_month):,}")
    print(f"Options contracts:     {len(options):,}")
    print(f"Unique underlyings:    {len(underlyings):,}")
    print("-" * 78)

    if not three_month.empty:
        print(
            three_month["expiry_bucket"]
            .value_counts()
            .reindex(
                ["NEAR", "NEXT", "FAR"],
                fill_value=0,
            )
            .to_string()
        )

    print("=" * 78)
    print(f"Raw:          {RAW_FILE}")
    print(f"All contracts:{CONTRACTS_FILE}")
    print(f"Futures:      {FUTURES_FILE}")
    print(f"3-month view: {FUTURES_3M_FILE}")
    print(f"Options:      {OPTIONS_FILE}")
    print(f"Underlyings:  {UNDERLYINGS_FILE}")
    print(f"Audit:        {AUDIT_FILE}")


def show_status() -> None:
    print("\nAQSD FYERS SYMBOL MASTER STATUS")
    print("=" * 72)

    for label, path in [
        ("Raw FYERS file", RAW_FILE),
        ("All contracts", CONTRACTS_FILE),
        ("Futures master", FUTURES_FILE),
        ("Near/Next/Far", FUTURES_3M_FILE),
        ("Options master", OPTIONS_FILE),
        ("Underlying master", UNDERLYINGS_FILE),
    ]:
        status = "FOUND" if path.exists() else "MISSING"
        size = f"{path.stat().st_size:,} bytes" if path.exists() else ""
        print(f"{label:<22}: {status:<8} {size}")

    print(f"Source URL: {SOURCE_URL}")
    print("Yahoo files modified: NO")
    print("AQSD database modified: NO")
    print("Order placement: DISABLED")
    print("=" * 72)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS NSE F&O Symbol Master Updater."
    )

    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the latest FYERS NSE F&O master.",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Build AQSD futures/options master files.",
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Download and build all outputs.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current file status.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.download:
        download_file()
        return

    if args.build:
        build_outputs()
        return

    # Default and --run both perform the complete workflow.
    download_file()
    build_outputs()


if __name__ == "__main__":
    main()
