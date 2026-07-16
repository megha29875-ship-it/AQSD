"""
AQSD Professional
Module: FYERS NSE F&O Symbol Master Updater
Version: 3.0

Purpose
-------
Parses the current 21-column FYERS NSE F&O symbol master layout and builds:

- All F&O contracts
- Futures contracts
- NEAR / NEXT / FAR futures contracts
- Options contracts
- Underlying master
- Lot-size master
- Expiry calendar
- Additions / deletions / lot-size change reports

Current FYERS 21-column mapping
-------------------------------
raw_01 = token
raw_02 = description
raw_03 = instrument_type_code
raw_04 = lot_size
raw_05 = tick_size
raw_06 = isin
raw_07 = trading_session
raw_08 = last_update_date
raw_09 = expiry_epoch
raw_10 = fyers_symbol
raw_11 = exchange
raw_12 = segment
raw_13 = exchange_token
raw_14 = underlying_symbol
raw_15 = underlying_token
raw_16 = strike_price
raw_17 = option_type / XX for futures
raw_18 = unique_identifier
raw_19 = reserved_1
raw_20 = reserved_2
raw_21 = reserved_3

Safety
------
- No order placement
- No AQSD database writes
- Yahoo files untouched
- Existing FYERS outputs backed up before replacement

Commands
--------
python aqsd_fyers_symbol_master_updater_v3.py --status
python aqsd_fyers_symbol_master_updater_v3.py --download
python aqsd_fyers_symbol_master_updater_v3.py --build
python aqsd_fyers_symbol_master_updater_v3.py --run

Run with:
C:\\Users\\megha\\AQSD\\.venv-fyers\\Scripts\\python.exe
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"
BACKUP_DIR = DATA_DIR / "FYERS_Symbol_Master_Backups"

SOURCE_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

RAW_FILE = DATA_DIR / "FYERS_NSE_FO_Raw.csv"
ALL_CONTRACTS_FILE = DATA_DIR / "FYERS_FNO_Contracts.csv"
FUTURES_FILE = DATA_DIR / "FYERS_Futures_Contracts.csv"
FUTURES_3M_FILE = DATA_DIR / "FYERS_Futures_Near_Next_Far.csv"
OPTIONS_FILE = DATA_DIR / "FYERS_Options_Contracts.csv"
UNDERLYINGS_FILE = DATA_DIR / "FYERS_FNO_Underlyings.csv"
LOT_SIZE_FILE = DATA_DIR / "FYERS_Lot_Sizes.csv"
EXPIRY_CALENDAR_FILE = DATA_DIR / "FYERS_Expiry_Calendar.csv"

AUDIT_FILE = OUTPUT_DIR / "FYERS_Symbol_Master_Audit.csv"
ADDITIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Additions.csv"
DELETIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Deletions.csv"
LOT_CHANGES_FILE = OUTPUT_DIR / "FYERS_Lot_Size_Changes.csv"

FYERS_COLUMNS_21 = [
    "token",
    "description",
    "instrument_type_code",
    "lot_size",
    "tick_size",
    "isin",
    "trading_session",
    "last_update_date",
    "expiry_epoch",
    "fyers_symbol",
    "exchange",
    "segment",
    "exchange_token",
    "underlying_symbol",
    "underlying_token",
    "strike_price",
    "option_type",
    "unique_identifier",
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


def backup_file(path: Path) -> None:
    if not path.exists():
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, destination)


def backup_outputs() -> None:
    for path in [
        ALL_CONTRACTS_FILE,
        FUTURES_FILE,
        FUTURES_3M_FILE,
        OPTIONS_FILE,
        UNDERLYINGS_FILE,
        LOT_SIZE_FILE,
        EXPIRY_CALENDAR_FILE,
    ]:
        backup_file(path)


def download_file() -> None:
    ensure_folders()

    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 AQSD-FYERS-Updater/3.0"
        },
    )

    print("Downloading FYERS NSE F&O symbol master...")
    print(SOURCE_URL)

    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()

    if len(content) < 1000:
        raise RuntimeError(
            f"Downloaded file is unexpectedly small: {len(content)} bytes."
        )

    first_bytes = content[:200].lower()

    if b"<html" in first_bytes or b"<!doctype" in first_bytes:
        raise RuntimeError(
            "FYERS returned HTML instead of a CSV file."
        )

    temporary = RAW_FILE.with_suffix(".download")
    temporary.write_bytes(content)

    backup_file(RAW_FILE)
    temporary.replace(RAW_FILE)

    print(f"Saved: {RAW_FILE}")
    print(f"Bytes: {RAW_FILE.stat().st_size:,}")
    print(f"SHA256: {file_sha256(RAW_FILE)}")


def read_raw_master() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"FYERS raw symbol master not found:\n{RAW_FILE}"
        )

    frame = pd.read_csv(
        RAW_FILE,
        header=None,
        low_memory=False,
    )

    if len(frame.columns) != 21:
        raise RuntimeError(
            "Unexpected FYERS symbol-master layout. "
            f"Detected {len(frame.columns)} columns; expected 21."
        )

    frame.columns = FYERS_COLUMNS_21
    return frame


def clean_master(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    result["fyers_symbol"] = (
        result["fyers_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["underlying"] = (
        result["underlying_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["option_type"] = (
        result["option_type"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["expiry_date"] = pd.to_datetime(
        pd.to_numeric(
            result["expiry_epoch"],
            errors="coerce",
        ),
        unit="s",
        errors="coerce",
    ).dt.normalize()

    for column in [
        "lot_size",
        "tick_size",
        "strike_price",
        "exchange_token",
        "underlying_token",
        "instrument_type_code",
    ]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result["instrument_family"] = "OTHER"

    result.loc[
        result["option_type"].eq("XX"),
        "instrument_family",
    ] = "FUTURE"

    result.loc[
        result["option_type"].isin(["CE", "PE"]),
        "instrument_family",
    ] = "OPTION"

    today = pd.Timestamp(date.today())

    result["is_expired"] = (
        result["expiry_date"].notna()
        & (result["expiry_date"] < today)
    )

    result["days_to_expiry"] = (
        result["expiry_date"] - today
    ).dt.days

    result = result[
        result["fyers_symbol"].str.startswith(
            "NSE:",
            na=False,
        )
    ].copy()

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

    live = result[
        result["expiry_date"].notna()
        & (~result["is_expired"])
    ].copy()

    labels = {
        1: "NEAR",
        2: "NEXT",
        3: "FAR",
    }

    for underlying, group in live.groupby("underlying"):
        expiries = sorted(
            group["expiry_date"]
            .dropna()
            .drop_duplicates()
            .tolist()
        )

        mapping = {
            pd.Timestamp(expiry): (
                rank,
                labels.get(rank, "LATER"),
            )
            for rank, expiry in enumerate(
                expiries,
                start=1,
            )
        }

        indexes = group.index

        result.loc[
            indexes,
            "expiry_rank",
        ] = result.loc[
            indexes,
            "expiry_date",
        ].map(
            lambda value: mapping[pd.Timestamp(value)][0]
        )

        result.loc[
            indexes,
            "expiry_bucket",
        ] = result.loc[
            indexes,
            "expiry_date",
        ].map(
            lambda value: mapping[pd.Timestamp(value)][1]
        )

    return result


def build_underlying_master(
    futures: pd.DataFrame,
    options: pd.DataFrame,
) -> pd.DataFrame:
    underlyings = sorted(
        set(futures["underlying"].dropna().astype(str))
        | set(options["underlying"].dropna().astype(str))
    )

    rows: list[dict] = []

    for underlying in underlyings:
        future_rows = futures[
            futures["underlying"] == underlying
        ]

        option_rows = options[
            options["underlying"] == underlying
        ]

        live_futures = future_rows[
            ~future_rows["is_expired"]
        ]

        live_options = option_rows[
            ~option_rows["is_expired"]
        ]

        buckets = {
            bucket: live_futures[
                live_futures["expiry_bucket"] == bucket
            ]
            for bucket in ["NEAR", "NEXT", "FAR"]
        }

        lot_values = (
            live_futures["lot_size"]
            .dropna()
            .drop_duplicates()
            .sort_values()
            .tolist()
        )

        rows.append(
            {
                "underlying": underlying,
                "near_future_symbol": (
                    buckets["NEAR"].iloc[0]["fyers_symbol"]
                    if not buckets["NEAR"].empty
                    else ""
                ),
                "next_future_symbol": (
                    buckets["NEXT"].iloc[0]["fyers_symbol"]
                    if not buckets["NEXT"].empty
                    else ""
                ),
                "far_future_symbol": (
                    buckets["FAR"].iloc[0]["fyers_symbol"]
                    if not buckets["FAR"].empty
                    else ""
                ),
                "near_expiry": (
                    buckets["NEAR"].iloc[0]["expiry_date"]
                    if not buckets["NEAR"].empty
                    else ""
                ),
                "next_expiry": (
                    buckets["NEXT"].iloc[0]["expiry_date"]
                    if not buckets["NEXT"].empty
                    else ""
                ),
                "far_expiry": (
                    buckets["FAR"].iloc[0]["expiry_date"]
                    if not buckets["FAR"].empty
                    else ""
                ),
                "lot_sizes": ",".join(
                    str(int(value))
                    for value in lot_values
                ),
                "live_futures_contracts": len(live_futures),
                "live_options_contracts": len(live_options),
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    return pd.DataFrame(rows)


def build_lot_size_master(
    futures: pd.DataFrame,
) -> pd.DataFrame:
    live = futures[
        ~futures["is_expired"]
    ].copy()

    if live.empty:
        return pd.DataFrame(
            columns=[
                "underlying",
                "expiry_bucket",
                "expiry_date",
                "fyers_symbol",
                "lot_size",
                "tick_size",
            ]
        )

    return live[
        [
            "underlying",
            "expiry_bucket",
            "expiry_date",
            "fyers_symbol",
            "lot_size",
            "tick_size",
        ]
    ].sort_values(
        [
            "underlying",
            "expiry_date",
        ]
    )


def build_expiry_calendar(
    futures: pd.DataFrame,
    options: pd.DataFrame,
) -> pd.DataFrame:
    combined = pd.concat(
        [
            futures[
                [
                    "underlying",
                    "expiry_date",
                    "instrument_family",
                    "fyers_symbol",
                ]
            ],
            options[
                [
                    "underlying",
                    "expiry_date",
                    "instrument_family",
                    "fyers_symbol",
                ]
            ],
        ],
        ignore_index=True,
    )

    combined = combined[
        combined["expiry_date"].notna()
    ].copy()

    calendar = (
        combined.groupby(
            [
                "underlying",
                "expiry_date",
                "instrument_family",
            ]
        )
        .agg(
            contract_count=(
                "fyers_symbol",
                "nunique",
            )
        )
        .reset_index()
        .sort_values(
            [
                "expiry_date",
                "underlying",
                "instrument_family",
            ]
        )
    )

    return calendar


def previous_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(
            path,
            low_memory=False,
        )
    except Exception:
        return pd.DataFrame()


def create_change_reports(
    previous_futures: pd.DataFrame,
    current_futures: pd.DataFrame,
) -> None:
    old_symbols = (
        set(
            previous_futures["fyers_symbol"]
            .dropna()
            .astype(str)
        )
        if (
            not previous_futures.empty
            and "fyers_symbol" in previous_futures.columns
        )
        else set()
    )

    new_symbols = set(
        current_futures["fyers_symbol"]
        .dropna()
        .astype(str)
    )

    additions = current_futures[
        current_futures["fyers_symbol"].isin(
            new_symbols - old_symbols
        )
    ].copy()

    deletions = (
        previous_futures[
            previous_futures["fyers_symbol"].isin(
                old_symbols - new_symbols
            )
        ].copy()
        if not previous_futures.empty
        else pd.DataFrame(
            columns=current_futures.columns
        )
    )

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

    lot_changes = pd.DataFrame(
        columns=[
            "fyers_symbol",
            "old_lot_size",
            "new_lot_size",
        ]
    )

    if (
        not previous_futures.empty
        and "lot_size" in previous_futures.columns
    ):
        old = previous_futures[
            [
                "fyers_symbol",
                "lot_size",
            ]
        ].rename(
            columns={
                "lot_size": "old_lot_size"
            }
        )

        new = current_futures[
            [
                "fyers_symbol",
                "lot_size",
            ]
        ].rename(
            columns={
                "lot_size": "new_lot_size"
            }
        )

        merged = old.merge(
            new,
            on="fyers_symbol",
            how="inner",
        )

        lot_changes = merged[
            pd.to_numeric(
                merged["old_lot_size"],
                errors="coerce",
            )
            != pd.to_numeric(
                merged["new_lot_size"],
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

    previous_futures = previous_frame(
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
            [
                "NEAR",
                "NEXT",
                "FAR",
            ]
        )
    ].copy()

    underlyings = build_underlying_master(
        futures,
        options,
    )

    lot_sizes = build_lot_size_master(
        futures
    )

    expiry_calendar = build_expiry_calendar(
        futures,
        options,
    )

    backup_outputs()

    contracts.to_csv(
        ALL_CONTRACTS_FILE,
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

    lot_sizes.to_csv(
        LOT_SIZE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    expiry_calendar.to_csv(
        EXPIRY_CALENDAR_FILE,
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
                "all_contracts": len(contracts),
                "futures_contracts": len(futures),
                "live_futures_contracts": int(
                    (~futures["is_expired"]).sum()
                ),
                "near_next_far_contracts": len(three_month),
                "options_contracts": len(options),
                "unique_underlyings": len(underlyings),
                "lot_size_rows": len(lot_sizes),
                "expiry_calendar_rows": len(expiry_calendar),
                "source_url": SOURCE_URL,
                "raw_sha256": file_sha256(RAW_FILE),
            }
        ]
    )

    audit.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nAQSD FYERS SYMBOL MASTER V3")
    print("=" * 86)
    print(f"Raw rows:               {len(raw):,}")
    print(f"All contracts:          {len(contracts):,}")
    print(f"Futures contracts:      {len(futures):,}")
    print(
        f"Live futures contracts: "
        f"{int((~futures['is_expired']).sum()):,}"
    )
    print(f"Near/Next/Far rows:     {len(three_month):,}")
    print(f"Options contracts:      {len(options):,}")
    print(f"Unique underlyings:     {len(underlyings):,}")
    print("-" * 86)

    if not three_month.empty:
        print(
            three_month["expiry_bucket"]
            .value_counts()
            .reindex(
                [
                    "NEAR",
                    "NEXT",
                    "FAR",
                ],
                fill_value=0,
            )
            .to_string()
        )

    print("=" * 86)
    print(f"Futures master: {FUTURES_FILE}")
    print(f"3-month master: {FUTURES_3M_FILE}")
    print(f"Options master: {OPTIONS_FILE}")
    print(f"Underlyings:    {UNDERLYINGS_FILE}")
    print(f"Lot sizes:      {LOT_SIZE_FILE}")
    print(f"Expiry calendar:{EXPIRY_CALENDAR_FILE}")
    print(f"Audit:          {AUDIT_FILE}")


def show_status() -> None:
    print("\nAQSD FYERS SYMBOL MASTER V3 STATUS")
    print("=" * 76)

    for label, path in [
        ("Raw FYERS master", RAW_FILE),
        ("All contracts", ALL_CONTRACTS_FILE),
        ("Futures master", FUTURES_FILE),
        ("Near/Next/Far", FUTURES_3M_FILE),
        ("Options master", OPTIONS_FILE),
        ("Underlyings", UNDERLYINGS_FILE),
        ("Lot sizes", LOT_SIZE_FILE),
        ("Expiry calendar", EXPIRY_CALENDAR_FILE),
    ]:
        status = "FOUND" if path.exists() else "MISSING"
        size = (
            f"{path.stat().st_size:,} bytes"
            if path.exists()
            else ""
        )

        print(f"{label:<22}: {status:<8} {size}")

    print(f"Source: {SOURCE_URL}")
    print("21-column mapping: ENABLED")
    print("Yahoo files modified: NO")
    print("AQSD database modified: NO")
    print("Order placement: DISABLED")
    print("=" * 76)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS NSE F&O Symbol Master Updater V3."
    )

    parser.add_argument(
        "--download",
        action="store_true",
    )

    parser.add_argument(
        "--build",
        action="store_true",
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
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

    download_file()
    build_outputs()


if __name__ == "__main__":
    main()
