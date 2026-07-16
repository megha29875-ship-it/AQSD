"""
AQSD Professional
Module: FYERS Live Quote Engine
Version: 1.0

Purpose
-------
Fetches live quote snapshots from FYERS without modifying the AQSD database.

Examples
--------
python aqsd_fyers_live_quotes.py --symbol RELIANCE
python aqsd_fyers_live_quotes.py --symbols RELIANCE,TCS,INFY
python aqsd_fyers_live_quotes.py --fno
python aqsd_fyers_live_quotes.py --status
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"

CONFIG_FILE = DATA_DIR / "fyers_config.env"
SYMBOL_MASTER = DATA_DIR / "AQSD_Symbol_Master.csv"
OUTPUT_CSV = OUTPUT_DIR / "AQSD_FYERS_Live_Quotes.csv"
OUTPUT_JSON = OUTPUT_DIR / "AQSD_FYERS_Live_Quotes.json"

MAX_SYMBOLS_PER_REQUEST = 50


def load_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"FYERS configuration file not found:\n{CONFIG_FILE}"
        )

    config: dict[str, str] = {}

    for raw_line in CONFIG_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    required = ["CLIENT_ID", "ACCESS_TOKEN"]
    missing = [key for key in required if not config.get(key)]

    if missing:
        raise RuntimeError(
            "Missing FYERS configuration values: "
            + ", ".join(missing)
        )

    return config


def normalize_nse_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()

    if not value:
        raise ValueError("Empty symbol received.")

    if value.startswith("NSE:"):
        return value

    if value.endswith(".NS"):
        value = value[:-3]

    if value.endswith("-EQ"):
        return f"NSE:{value}"

    return f"NSE:{value}-EQ"


def load_fno_symbols() -> list[str]:
    if not SYMBOL_MASTER.exists():
        raise FileNotFoundError(
            f"Symbol master not found:\n{SYMBOL_MASTER}"
        )

    frame = pd.read_csv(SYMBOL_MASTER)

    symbol_column = next(
        (
            column
            for column in [
                "nse_symbol",
                "NSE Symbol",
                "symbol",
                "Symbol",
            ]
            if column in frame.columns
        ),
        None,
    )

    if symbol_column is None:
        raise RuntimeError(
            "Could not find an NSE symbol column in AQSD_Symbol_Master.csv."
        )

    if "active" in frame.columns:
        frame = frame[
            pd.to_numeric(
                frame["active"],
                errors="coerce",
            ).fillna(0)
            == 1
        ]

    symbols = [
        normalize_nse_symbol(value)
        for value in frame[symbol_column].dropna().tolist()
    ]

    return sorted(set(symbols))


def create_client() -> fyersModel.FyersModel:
    config = load_config()

    return fyersModel.FyersModel(
        client_id=config["CLIENT_ID"],
        token=config["ACCESS_TOKEN"],
        is_async=False,
        log_path="",
    )


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [
        values[index:index + size]
        for index in range(0, len(values), size)
    ]


def parse_quote_item(item: dict[str, Any]) -> dict[str, Any]:
    values = item.get("v") or {}
    symbol = item.get("n") or values.get("symbol") or ""

    return {
        "fyers_symbol": symbol,
        "nse_symbol": (
            symbol.replace("NSE:", "").replace("-EQ", "")
            if symbol
            else ""
        ),
        "ltp": values.get("lp"),
        "open": values.get("open_price"),
        "high": values.get("high_price"),
        "low": values.get("low_price"),
        "previous_close": values.get("prev_close_price"),
        "change": values.get("ch"),
        "change_percent": values.get("chp"),
        "volume": values.get("volume"),
        "bid": values.get("bid"),
        "ask": values.get("ask"),
        "spread": (
            round(float(values["ask"]) - float(values["bid"]), 4)
            if values.get("ask") is not None
            and values.get("bid") is not None
            else None
        ),
        "exchange": values.get("exchange"),
        "description": values.get("description"),
        "short_name": values.get("short_name"),
        "quote_type": values.get("original_name"),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_quotes(symbols: list[str]) -> tuple[pd.DataFrame, list[dict]]:
    if not symbols:
        raise ValueError("No symbols supplied.")

    client = create_client()
    rows: list[dict] = []
    raw_responses: list[dict] = []

    for batch_number, batch in enumerate(
        chunks(symbols, MAX_SYMBOLS_PER_REQUEST),
        start=1,
    ):
        response = client.quotes(
            {"symbols": ",".join(batch)}
        )

        if not isinstance(response, dict):
            raise RuntimeError(
                f"Unexpected FYERS response for batch {batch_number}."
            )

        raw_responses.append(response)

        if response.get("s") != "ok":
            message = response.get("message") or "Unknown FYERS error"
            code_value = response.get("code")

            raise RuntimeError(
                f"FYERS quote request failed. "
                f"Code={code_value}; Message={message}"
            )

        for item in response.get("d", []):
            if isinstance(item, dict):
                rows.append(parse_quote_item(item))

    frame = pd.DataFrame(rows)

    if not frame.empty:
        frame = frame.sort_values(
            "nse_symbol"
        ).reset_index(drop=True)

    return frame, raw_responses


def save_outputs(
    frame: pd.DataFrame,
    raw_responses: list[dict],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frame.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    safe_json = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "quote_count": len(frame),
        "responses": raw_responses,
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            safe_json,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def print_quotes(frame: pd.DataFrame) -> None:
    print("\nAQSD FYERS LIVE QUOTES")
    print("=" * 90)

    if frame.empty:
        print("No quote rows returned.")
        return

    columns = [
        column
        for column in [
            "nse_symbol",
            "ltp",
            "change",
            "change_percent",
            "open",
            "high",
            "low",
            "volume",
            "bid",
            "ask",
        ]
        if column in frame.columns
    ]

    print(
        frame[columns].to_string(
            index=False
        )
    )

    print("=" * 90)
    print(f"Quotes received: {len(frame)}")
    print(f"CSV:  {OUTPUT_CSV}")
    print(f"JSON: {OUTPUT_JSON}")


def show_status() -> None:
    print("\nAQSD FYERS LIVE QUOTE ENGINE STATUS")
    print("=" * 72)
    print(f"Configuration: {'FOUND' if CONFIG_FILE.exists() else 'MISSING'}")
    print(f"Symbol master: {'FOUND' if SYMBOL_MASTER.exists() else 'MISSING'}")
    print(f"Output folder: {OUTPUT_DIR}")
    print("Database writes: DISABLED")
    print("Order placement: DISABLED")
    print("=" * 72)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Live Quote Engine."
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--symbol",
        help="One NSE symbol, e.g. RELIANCE.",
    )

    group.add_argument(
        "--symbols",
        help="Comma-separated NSE symbols.",
    )

    group.add_argument(
        "--fno",
        action="store_true",
        help="Fetch active symbols from AQSD_Symbol_Master.csv.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show engine status without contacting FYERS.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.symbol:
        symbols = [normalize_nse_symbol(args.symbol)]

    elif args.symbols:
        symbols = [
            normalize_nse_symbol(value)
            for value in args.symbols.split(",")
            if value.strip()
        ]

    elif args.fno:
        symbols = load_fno_symbols()

    else:
        symbols = [
            "NSE:RELIANCE-EQ",
            "NSE:TCS-EQ",
            "NSE:INFY-EQ",
        ]

    frame, raw_responses = fetch_quotes(symbols)
    save_outputs(frame, raw_responses)
    print_quotes(frame)


if __name__ == "__main__":
    main()
