"""
AQSD Professional
Module: FYERS Market Depth Engine
Version: 1.1

Fixes
-----
- Parses FYERS depth payload nested under:
  response["d"][symbol]
- Supports FYERS field names:
  totalbuyqty, totalsellqty, o, h, l, c, ltp, v, atp,
  lower_ckt, upper_ckt, oi, pdoi, oipercent, bids, ask

Safety
------
- No order placement
- No database writes
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
SUMMARY_CSV = OUTPUT_DIR / "AQSD_FYERS_Market_Depth_Summary.csv"
LEVELS_CSV = OUTPUT_DIR / "AQSD_FYERS_Market_Depth_Levels.csv"
RAW_JSON = OUTPUT_DIR / "AQSD_FYERS_Market_Depth.json"


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

    missing = [
        key
        for key in ("CLIENT_ID", "ACCESS_TOKEN")
        if not config.get(key)
    ]

    if missing:
        raise RuntimeError(
            "Missing FYERS configuration values: "
            + ", ".join(missing)
        )

    return config


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()

    if not value:
        raise ValueError("Symbol cannot be blank.")

    if value.startswith("NSE:"):
        return value

    if value.endswith(".NS"):
        value = value[:-3]

    if value in {"NIFTY", "NIFTY50", "NIFTY50-INDEX"}:
        return "NSE:NIFTY50-INDEX"

    if value in {"BANKNIFTY", "NIFTYBANK", "NIFTYBANK-INDEX"}:
        return "NSE:NIFTYBANK-INDEX"

    if value.endswith("-EQ"):
        return f"NSE:{value}"

    return f"NSE:{value}-EQ"


def create_client() -> fyersModel.FyersModel:
    config = load_config()

    return fyersModel.FyersModel(
        client_id=config["CLIENT_ID"],
        token=config["ACCESS_TOKEN"],
        is_async=False,
        log_path="",
    )


def safe_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None

    try:
        number = float(value)

        if number.is_integer():
            return int(number)

        return number

    except (TypeError, ValueError):
        return None


def extract_payload(
    response: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    data = response.get("d")

    if isinstance(data, dict):
        symbol_payload = data.get(symbol)

        if isinstance(symbol_payload, dict):
            return symbol_payload

        if len(data) == 1:
            first_value = next(iter(data.values()))

            if isinstance(first_value, dict):
                return first_value

    raise RuntimeError(
        "Could not locate symbol payload inside FYERS depth response."
    )


def extract_summary(
    symbol: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ltp = safe_number(payload.get("ltp"))
    previous_close = safe_number(payload.get("c"))
    change = safe_number(payload.get("ch"))
    change_percent = safe_number(payload.get("chp"))

    bid_levels = payload.get("bids") or []
    ask_levels = payload.get("ask") or []

    best_bid = (
        safe_number(bid_levels[0].get("price"))
        if bid_levels and isinstance(bid_levels[0], dict)
        else None
    )

    best_ask = (
        safe_number(ask_levels[0].get("price"))
        if ask_levels and isinstance(ask_levels[0], dict)
        else None
    )

    spread = None

    if (
        best_bid is not None
        and best_ask is not None
        and best_ask > 0
    ):
        spread = round(float(best_ask) - float(best_bid), 4)

    return {
        "fyers_symbol": symbol,
        "ltp": ltp,
        "open": safe_number(payload.get("o")),
        "high": safe_number(payload.get("h")),
        "low": safe_number(payload.get("l")),
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "volume": safe_number(payload.get("v")),
        "last_traded_quantity": safe_number(payload.get("ltq")),
        "last_traded_time": safe_number(payload.get("ltt")),
        "average_trade_price": safe_number(payload.get("atp")),
        "total_buy_quantity": safe_number(payload.get("totalbuyqty")),
        "total_sell_quantity": safe_number(payload.get("totalsellqty")),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "open_interest": safe_number(payload.get("oi")),
        "previous_day_open_interest": safe_number(payload.get("pdoi")),
        "oi_change_percent": safe_number(payload.get("oipercent")),
        "oi_available": bool(payload.get("oiflag")),
        "upper_circuit": safe_number(payload.get("upper_ckt")),
        "lower_circuit": safe_number(payload.get("lower_ckt")),
        "tick_size": safe_number(payload.get("tick_Size")),
        "expiry": payload.get("expiry") or "",
        "fetched_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }


def extract_levels(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for side, key in (
        ("BID", "bids"),
        ("ASK", "ask"),
    ):
        levels = payload.get(key) or []

        if not isinstance(levels, list):
            continue

        for index, level in enumerate(levels, start=1):
            if not isinstance(level, dict):
                continue

            rows.append(
                {
                    "side": side,
                    "level": index,
                    "price": safe_number(level.get("price")),
                    "quantity": safe_number(level.get("volume")),
                    "orders": safe_number(level.get("ord")),
                }
            )

    return rows


def fetch_depth(
    symbol: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
]:
    client = create_client()

    response = client.depth(
        {
            "symbol": symbol,
            "ohlcv_flag": "1",
        }
    )

    if not isinstance(response, dict):
        raise RuntimeError(
            "Unexpected FYERS market-depth response."
        )

    if response.get("s") != "ok":
        raise RuntimeError(
            "FYERS market-depth request failed. "
            f"Code={response.get('code')}; "
            f"Message={response.get('message')}"
        )

    payload = extract_payload(
        response,
        symbol,
    )

    summary = extract_summary(
        symbol,
        payload,
    )

    levels = extract_levels(
        payload
    )

    return response, summary, levels


def save_outputs(
    response: dict[str, Any],
    summary: dict[str, Any],
    levels: list[dict[str, Any]],
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame([summary]).to_csv(
        SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        levels,
        columns=[
            "side",
            "level",
            "price",
            "quantity",
            "orders",
        ],
    ).to_csv(
        LEVELS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    RAW_JSON.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "summary": summary,
                "levels": levels,
                "raw_response": response,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def print_results(
    summary: dict[str, Any],
    levels: list[dict[str, Any]],
) -> None:
    print("\nAQSD FYERS MARKET DEPTH V1.1")
    print("=" * 86)

    for label, key in [
        ("Symbol", "fyers_symbol"),
        ("LTP", "ltp"),
        ("Open", "open"),
        ("High", "high"),
        ("Low", "low"),
        ("Previous Close", "previous_close"),
        ("Change", "change"),
        ("Change %", "change_percent"),
        ("Volume", "volume"),
        ("ATP", "average_trade_price"),
        ("Total Buy Qty", "total_buy_quantity"),
        ("Total Sell Qty", "total_sell_quantity"),
        ("Best Bid", "best_bid"),
        ("Best Ask", "best_ask"),
        ("Spread", "spread"),
        ("Open Interest", "open_interest"),
        ("Previous Day OI", "previous_day_open_interest"),
        ("OI Change %", "oi_change_percent"),
        ("OI Available", "oi_available"),
        ("Lower Circuit", "lower_circuit"),
        ("Upper Circuit", "upper_circuit"),
    ]:
        print(f"{label:<22}: {summary.get(key)}")

    print("-" * 86)

    if levels:
        frame = pd.DataFrame(levels)
        print(frame.to_string(index=False))
    else:
        print("No market-depth levels returned.")

    print("=" * 86)
    print(f"Summary CSV: {SUMMARY_CSV}")
    print(f"Levels CSV:  {LEVELS_CSV}")
    print(f"Raw JSON:    {RAW_JSON}")


def show_status() -> None:
    print("\nAQSD FYERS MARKET DEPTH ENGINE STATUS")
    print("=" * 72)
    print("Version: 1.1")
    print(
        f"Configuration: "
        f"{'FOUND' if CONFIG_FILE.exists() else 'MISSING'}"
    )
    print(f"Output folder: {OUTPUT_DIR}")
    print("Database writes: DISABLED")
    print("Order placement: DISABLED")
    print("Request mode: ONE SYMBOL PER REQUEST")
    print("=" * 72)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Market Depth Engine."
    )

    parser.add_argument(
        "--symbol",
        help="NSE symbol such as RELIANCE.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status without contacting FYERS.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if not args.symbol:
        raise SystemExit(
            "Please provide a symbol, for example:\n"
            "python aqsd_fyers_market_depth.py --symbol RELIANCE"
        )

    symbol = normalize_symbol(args.symbol)

    response, summary, levels = fetch_depth(
        symbol
    )

    save_outputs(
        response,
        summary,
        levels,
    )

    print_results(
        summary,
        levels,
    )


if __name__ == "__main__":
    main()
