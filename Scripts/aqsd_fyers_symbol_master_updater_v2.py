"""
AQSD Professional
Module: FYERS NSE F&O Symbol Master Updater
Version: 2.0

Purpose
-------
Adaptive parser for the FYERS NSE F&O symbol master.

This version:
- accepts 19, 20, 21 or more columns;
- detects important fields heuristically;
- preserves every original raw column;
- builds futures, options, underlyings and NEAR/NEXT/FAR files;
- creates a parser diagnostics report;
- does not modify Yahoo files or the AQSD database.

Commands
--------
python aqsd_fyers_symbol_master_updater_v2.py --download
python aqsd_fyers_symbol_master_updater_v2.py --build
python aqsd_fyers_symbol_master_updater_v2.py --run
python aqsd_fyers_symbol_master_updater_v2.py --status
python aqsd_fyers_symbol_master_updater_v2.py --inspect

Run with:
C:\\Users\\megha\\AQSD\\.venv-fyers\\Scripts\\python.exe
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
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
ALL_CONTRACTS_FILE = DATA_DIR / "FYERS_FNO_Contracts.csv"
FUTURES_FILE = DATA_DIR / "FYERS_Futures_Contracts.csv"
FUTURES_3M_FILE = DATA_DIR / "FYERS_Futures_Near_Next_Far.csv"
OPTIONS_FILE = DATA_DIR / "FYERS_Options_Contracts.csv"
UNDERLYINGS_FILE = DATA_DIR / "FYERS_FNO_Underlyings.csv"

AUDIT_FILE = OUTPUT_DIR / "FYERS_Symbol_Master_Audit.csv"
PARSER_DIAGNOSTICS_FILE = OUTPUT_DIR / "FYERS_Symbol_Master_Parser_Diagnostics.json"
COLUMN_PROFILE_FILE = OUTPUT_DIR / "FYERS_Symbol_Master_Column_Profile.csv"
ADDITIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Additions.csv"
DELETIONS_FILE = OUTPUT_DIR / "FYERS_Futures_Deletions.csv"
LOT_CHANGES_FILE = OUTPUT_DIR / "FYERS_Lot_Size_Changes.csv"


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


def backup_file(path: Path) -> Path:
    ensure_folders()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, destination)

    return destination


def backup_outputs() -> None:
    for path in [
        ALL_CONTRACTS_FILE,
        FUTURES_FILE,
        FUTURES_3M_FILE,
        OPTIONS_FILE,
        UNDERLYINGS_FILE,
    ]:
        if path.exists():
            backup_file(path)


def download_file() -> None:
    ensure_folders()

    temporary = RAW_FILE.with_suffix(".download")

    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 AQSD-FYERS-Symbol-Master-Updater/2.0"
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

    first_bytes = content[:200].lower()

    if b"<html" in first_bytes or b"<!doctype" in first_bytes:
        raise RuntimeError(
            "FYERS returned HTML instead of the CSV file."
        )

    temporary.write_bytes(content)

    if RAW_FILE.exists():
        backup_file(RAW_FILE)

    temporary.replace(RAW_FILE)

    print(f"Saved: {RAW_FILE}")
    print(f"Bytes: {RAW_FILE.stat().st_size:,}")
    print(f"SHA256: {file_sha256(RAW_FILE)}")


def count_csv_columns(path: Path) -> int:
    with path.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
    ) as handle:
        reader = csv.reader(handle)
        first = next(reader)

    return len(first)


def read_raw_file() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"FYERS raw symbol master not found:\n{RAW_FILE}"
        )

    frame = pd.read_csv(
        RAW_FILE,
        header=None,
        low_memory=False,
    )

    frame.columns = [
        f"raw_{index:02d}"
        for index in range(1, len(frame.columns) + 1)
    ]

    return frame


def sample_strings(series: pd.Series, limit: int = 10) -> list[str]:
    values = (
        series.dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        (values != "")
        & (values.str.upper() != "NAN")
    ]

    return values.drop_duplicates().head(limit).tolist()


def numeric_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0

    parsed = pd.to_numeric(
        series,
        errors="coerce",
    )

    return float(parsed.notna().mean())


def symbol_ratio(series: pd.Series) -> float:
    values = series.astype(str).str.upper()

    matches = values.str.contains(
        r"^NSE:.*-(FUT|CE|PE)$",
        regex=True,
        na=False,
    )

    return float(matches.mean())


def option_type_ratio(series: pd.Series) -> float:
    values = series.astype(str).str.strip().str.upper()

    return float(
        values.isin(["CE", "PE"]).mean()
    )


def expiry_score(series: pd.Series) -> float:
    values = series.dropna().astype(str).str.strip()

    if values.empty:
        return 0.0

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    )

    unix_score = (
        numeric.between(
            1_000_000_000,
            5_000_000_000,
        ).mean()
    )

    yyyymmdd_score = (
        numeric.between(
            20_000_000,
            21_000_000,
        ).mean()
    )

    parsed = pd.to_datetime(
        values,
        errors="coerce",
        dayfirst=True,
    )

    date_score = parsed.notna().mean()

    return float(
        max(
            unix_score,
            yyyymmdd_score,
            date_score,
        )
    )


def description_ratio(series: pd.Series) -> float:
    values = series.astype(str).str.upper()

    return float(
        values.str.contains(
            r"(FUT|CALL|PUT|CE|PE|NIFTY|BANKNIFTY)",
            regex=True,
            na=False,
        ).mean()
    )


def profile_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for column in frame.columns:
        series = frame[column]

        rows.append(
            {
                "column": column,
                "non_null_ratio": round(
                    float(series.notna().mean()),
                    4,
                ),
                "numeric_ratio": round(
                    numeric_ratio(series),
                    4,
                ),
                "symbol_ratio": round(
                    symbol_ratio(series),
                    4,
                ),
                "option_type_ratio": round(
                    option_type_ratio(series),
                    4,
                ),
                "expiry_score": round(
                    expiry_score(series),
                    4,
                ),
                "description_ratio": round(
                    description_ratio(series),
                    4,
                ),
                "samples": " | ".join(
                    sample_strings(series)
                ),
            }
        )

    profile = pd.DataFrame(rows)

    profile.to_csv(
        COLUMN_PROFILE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return profile


def choose_best_column(
    profile: pd.DataFrame,
    score_column: str,
    excluded: set[str] | None = None,
    minimum_score: float = 0.0,
) -> str | None:
    excluded = excluded or set()

    candidates = profile[
        ~profile["column"].isin(excluded)
    ].sort_values(
        score_column,
        ascending=False,
    )

    if candidates.empty:
        return None

    row = candidates.iloc[0]

    if float(row[score_column]) < minimum_score:
        return None

    return str(row["column"])


def infer_mapping(
    frame: pd.DataFrame,
    profile: pd.DataFrame,
) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    used: set[str] = set()

    mapping["fyers_symbol"] = choose_best_column(
        profile,
        "symbol_ratio",
        minimum_score=0.05,
    )

    if mapping["fyers_symbol"]:
        used.add(mapping["fyers_symbol"])

    mapping["option_type"] = choose_best_column(
        profile,
        "option_type_ratio",
        excluded=used,
        minimum_score=0.01,
    )

    if mapping["option_type"]:
        used.add(mapping["option_type"])

    mapping["expiry_raw"] = choose_best_column(
        profile,
        "expiry_score",
        excluded=used,
        minimum_score=0.05,
    )

    if mapping["expiry_raw"]:
        used.add(mapping["expiry_raw"])

    mapping["description"] = choose_best_column(
        profile,
        "description_ratio",
        excluded=used,
        minimum_score=0.05,
    )

    if mapping["description"]:
        used.add(mapping["description"])

    numeric_candidates = profile[
        (~profile["column"].isin(used))
        & (profile["numeric_ratio"] >= 0.80)
    ].copy()

    # Tick size tends to be small positive decimals.
    tick_column = None
    tick_score = -1.0

    for column in numeric_candidates["column"]:
        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        positive = values[values > 0]

        if positive.empty:
            continue

        small_ratio = float(
            positive.between(
                0.0001,
                10,
            ).mean()
        )

        decimal_ratio = float(
            ((positive % 1) != 0).mean()
        )

        score = small_ratio + decimal_ratio

        if score > tick_score:
            tick_score = score
            tick_column = str(column)

    mapping["tick_size"] = tick_column

    if tick_column:
        used.add(tick_column)

    numeric_candidates = profile[
        (~profile["column"].isin(used))
        & (profile["numeric_ratio"] >= 0.80)
    ].copy()

    # Lot size is normally a positive integer, generally below 1,000,000.
    lot_column = None
    lot_score = -1.0

    for column in numeric_candidates["column"]:
        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        ).dropna()

        positive = values[values > 0]

        if positive.empty:
            continue

        integer_ratio = float(
            ((positive % 1) == 0).mean()
        )

        range_ratio = float(
            positive.between(
                1,
                1_000_000,
            ).mean()
        )

        uniqueness_penalty = min(
            float(positive.nunique()) / 10000,
            1.0,
        )

        score = (
            integer_ratio
            + range_ratio
            - uniqueness_penalty
        )

        if score > lot_score:
            lot_score = score
            lot_column = str(column)

    mapping["lot_size"] = lot_column

    if lot_column:
        used.add(lot_column)

    # Strike price is numeric and usually has high variety.
    numeric_candidates = profile[
        (~profile["column"].isin(used))
        & (profile["numeric_ratio"] >= 0.70)
    ].copy()

    strike_column = None
    strike_score = -1.0

    for column in numeric_candidates["column"]:
        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        ).dropna()

        positive = values[values > 0]

        if positive.empty:
            continue

        variety = min(
            float(positive.nunique()) / 1000,
            1.0,
        )

        sensible = float(
            positive.between(
                0.01,
                1_000_000,
            ).mean()
        )

        score = variety + sensible

        if score > strike_score:
            strike_score = score
            strike_column = str(column)

    mapping["strike_price"] = strike_column

    # Underlying may be a clean symbol-like text column, but not FYERS symbol.
    underlying_column = None
    underlying_score = -1.0

    for column in frame.columns:
        if column in used or column == strike_column:
            continue

        values = (
            frame[column]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )

        if values.empty:
            continue

        clean_ratio = float(
            values.str.match(
                r"^[A-Z0-9&\-]{1,30}$",
                na=False,
            ).mean()
        )

        fyers_penalty = float(
            values.str.startswith("NSE:").mean()
        )

        score = clean_ratio - fyers_penalty

        if score > underlying_score:
            underlying_score = score
            underlying_column = str(column)

    mapping["underlying_symbol"] = underlying_column

    return mapping


def parse_expiry(value: Any) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if not text or text.lower() in {
        "none",
        "nan",
        "0",
    }:
        return pd.NaT

    numeric = pd.to_numeric(
        text,
        errors="coerce",
    )

    if not pd.isna(numeric):
        number = float(numeric)

        if 1_000_000_000 <= number <= 5_000_000_000:
            return pd.to_datetime(
                int(number),
                unit="s",
                errors="coerce",
            ).normalize()

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


def derive_underlying_from_symbol(
    fyers_symbol: str,
) -> str:
    symbol = normalize_text(fyers_symbol)

    if symbol.startswith("NSE:"):
        symbol = symbol[4:]

    symbol = re.sub(
        r"-(FUT|CE|PE)$",
        "",
        symbol,
    )

    # Remove common expiry/strike tail while preserving stock names.
    match = re.match(
        r"^([A-Z&\-]+?)(?:\d{1,2}[A-Z]{3}\d{2}|\d{2}[A-Z]{3}|\d{6,})",
        symbol,
    )

    if match:
        return match.group(1).rstrip("-")

    return symbol


def normalize_text(value: Any) -> str:
    return str(value or "").strip().upper()


def build_canonical_frame(
    raw: pd.DataFrame,
    mapping: dict[str, str | None],
) -> pd.DataFrame:
    result = raw.copy()

    for target, source in mapping.items():
        if source and source in raw.columns:
            result[target] = raw[source]
        else:
            result[target] = pd.NA

    result["fyers_symbol"] = (
        result["fyers_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result["description"] = (
        result["description"]
        .astype(str)
        .str.strip()
    )

    result["option_type"] = (
        result["option_type"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace(
            {
                "NAN": "",
                "NONE": "",
                "<NA>": "",
            }
        )
    )

    for column in [
        "lot_size",
        "tick_size",
        "strike_price",
    ]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result["expiry_date"] = result[
        "expiry_raw"
    ].apply(parse_expiry)

    result["underlying"] = (
        result["underlying_symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    invalid_underlying = result["underlying"].isin(
        [
            "",
            "NAN",
            "NONE",
            "<NA>",
            "0",
            "-1",
        ]
    )

    result.loc[
        invalid_underlying,
        "underlying",
    ] = result.loc[
        invalid_underlying,
        "fyers_symbol",
    ].apply(
        derive_underlying_from_symbol
    )

    symbol_upper = result[
        "fyers_symbol"
    ].astype(str).str.upper()

    result["instrument_family"] = "OTHER"

    result.loc[
        symbol_upper.str.endswith("-FUT", na=False),
        "instrument_family",
    ] = "FUTURE"

    result.loc[
        symbol_upper.str.endswith("-CE", na=False)
        | symbol_upper.str.endswith("-PE", na=False)
        | result["option_type"].isin(["CE", "PE"]),
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

    valid = result[
        result["expiry_date"].notna()
        & (~result["is_expired"])
    ].copy()

    for underlying, group in valid.groupby("underlying"):
        expiries = sorted(
            pd.Series(
                group["expiry_date"].unique()
            )
            .dropna()
            .tolist()
        )

        labels = {
            1: "NEAR",
            2: "NEXT",
            3: "FAR",
        }

        expiry_mapping = {
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
            lambda value: expiry_mapping[
                pd.Timestamp(value)
            ][0]
        )

        result.loc[
            indexes,
            "expiry_bucket",
        ] = result.loc[
            indexes,
            "expiry_date",
        ].map(
            lambda value: expiry_mapping[
                pd.Timestamp(value)
            ][1]
        )

    return result


def build_underlyings(
    futures: pd.DataFrame,
    options: pd.DataFrame,
) -> pd.DataFrame:
    underlyings = sorted(
        set(futures["underlying"].dropna().astype(str))
        | set(options["underlying"].dropna().astype(str))
    )

    rows: list[dict[str, Any]] = []

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
                "lot_size": (
                    live_futures["lot_size"].dropna().iloc[0]
                    if not live_futures["lot_size"].dropna().empty
                    else None
                ),
                "live_futures_contracts": len(live_futures),
                "live_options_contracts": len(live_options),
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    return pd.DataFrame(rows)


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
            ["fyers_symbol", "lot_size"]
        ].rename(
            columns={
                "lot_size": "old_lot_size"
            }
        )

        new = current_futures[
            ["fyers_symbol", "lot_size"]
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


def save_diagnostics(
    raw: pd.DataFrame,
    profile: pd.DataFrame,
    mapping: dict[str, str | None],
) -> None:
    diagnostics = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "detected_column_count": len(raw.columns),
        "raw_columns": list(raw.columns),
        "inferred_mapping": mapping,
        "raw_file": str(RAW_FILE),
        "column_profile_file": str(COLUMN_PROFILE_FILE),
        "top_profiles": profile.to_dict(
            orient="records"
        ),
    }

    PARSER_DIAGNOSTICS_FILE.write_text(
        json.dumps(
            diagnostics,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def build_outputs() -> None:
    ensure_folders()

    raw = read_raw_file()
    profile = profile_columns(raw)
    mapping = infer_mapping(
        raw,
        profile,
    )

    required = [
        "fyers_symbol",
        "expiry_raw",
        "lot_size",
    ]

    missing = [
        field
        for field in required
        if not mapping.get(field)
    ]

    save_diagnostics(
        raw,
        profile,
        mapping,
    )

    if missing:
        raise RuntimeError(
            "Adaptive parser could not confidently identify: "
            + ", ".join(missing)
            + f". Review {PARSER_DIAGNOSTICS_FILE}."
        )

    contracts = build_canonical_frame(
        raw,
        mapping,
    )

    futures = contracts[
        contracts["instrument_family"] == "FUTURE"
    ].copy()

    options = contracts[
        contracts["instrument_family"] == "OPTION"
    ].copy()

    previous_futures = previous_frame(
        FUTURES_FILE
    )

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

    underlyings = build_underlyings(
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
                "detected_columns": len(raw.columns),
                "raw_rows": len(raw),
                "contracts": len(contracts),
                "futures_contracts": len(futures),
                "live_futures_contracts": int(
                    (~futures["is_expired"]).sum()
                ),
                "near_next_far_contracts": len(three_month),
                "options_contracts": len(options),
                "unique_underlyings": len(underlyings),
                "source_url": SOURCE_URL,
                "raw_file_sha256": file_sha256(RAW_FILE),
            }
        ]
    )

    audit.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nAQSD FYERS SYMBOL MASTER V2")
    print("=" * 84)
    print(f"Detected columns:       {len(raw.columns)}")
    print(f"Raw rows:               {len(raw):,}")
    print(f"Contracts:              {len(contracts):,}")
    print(f"Futures contracts:      {len(futures):,}")
    print(
        f"Live futures contracts: "
        f"{int((~futures['is_expired']).sum()):,}"
    )
    print(f"Near/Next/Far rows:     {len(three_month):,}")
    print(f"Options contracts:      {len(options):,}")
    print(f"Unique underlyings:     {len(underlyings):,}")
    print("-" * 84)
    print("Detected mapping:")

    for key, value in mapping.items():
        print(f"{key:<22}: {value}")

    print("=" * 84)
    print(f"Futures master: {FUTURES_FILE}")
    print(f"3-month master: {FUTURES_3M_FILE}")
    print(f"Options master: {OPTIONS_FILE}")
    print(f"Underlyings:    {UNDERLYINGS_FILE}")
    print(f"Diagnostics:    {PARSER_DIAGNOSTICS_FILE}")


def inspect_raw() -> None:
    raw = read_raw_file()
    profile = profile_columns(raw)
    mapping = infer_mapping(
        raw,
        profile,
    )

    save_diagnostics(
        raw,
        profile,
        mapping,
    )

    print("\nFYERS RAW MASTER INSPECTION")
    print("=" * 84)
    print(f"Rows:    {len(raw):,}")
    print(f"Columns: {len(raw.columns)}")
    print("-" * 84)

    print(
        profile[
            [
                "column",
                "numeric_ratio",
                "symbol_ratio",
                "option_type_ratio",
                "expiry_score",
                "description_ratio",
                "samples",
            ]
        ].to_string(
            index=False
        )
    )

    print("=" * 84)
    print("Inferred mapping:")

    for key, value in mapping.items():
        print(f"{key:<22}: {value}")

    print(f"\nDiagnostics saved: {PARSER_DIAGNOSTICS_FILE}")


def show_status() -> None:
    print("\nAQSD FYERS SYMBOL MASTER V2 STATUS")
    print("=" * 76)

    for label, path in [
        ("Raw FYERS master", RAW_FILE),
        ("All contracts", ALL_CONTRACTS_FILE),
        ("Futures master", FUTURES_FILE),
        ("Near/Next/Far", FUTURES_3M_FILE),
        ("Options master", OPTIONS_FILE),
        ("Underlyings", UNDERLYINGS_FILE),
    ]:
        status = "FOUND" if path.exists() else "MISSING"
        size = (
            f"{path.stat().st_size:,} bytes"
            if path.exists()
            else ""
        )

        print(f"{label:<22}: {status:<8} {size}")

    print(f"Source: {SOURCE_URL}")
    print("Adaptive columns: ENABLED")
    print("Yahoo files modified: NO")
    print("AQSD database modified: NO")
    print("Order placement: DISABLED")
    print("=" * 76)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "AQSD Adaptive FYERS NSE F&O Symbol Master Updater."
        )
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

    parser.add_argument(
        "--inspect",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.inspect:
        inspect_raw()
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
