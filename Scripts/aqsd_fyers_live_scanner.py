"""
AQSD Professional - FYERS Live Scanner v1.0

Fetches the active AQSD NSE/F&O universe using FYERS live quotes.
No order placement. No database writes.
"""

from __future__ import annotations

import argparse
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

OUTPUT_CSV = OUTPUT_DIR / "AQSD_FYERS_Live_Scanner.csv"
OUTPUT_XLSX = OUTPUT_DIR / "AQSD_FYERS_Live_Scanner.xlsx"
FAILED_CSV = OUTPUT_DIR / "AQSD_FYERS_Live_Scanner_Failed.csv"

MAX_SYMBOLS_PER_REQUEST = 50


def load_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_FILE}")

    config: dict[str, str] = {}

    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    missing = [
        key for key in ("CLIENT_ID", "ACCESS_TOKEN")
        if not config.get(key)
    ]

    if missing:
        raise RuntimeError(
            "Missing FYERS configuration values: "
            + ", ".join(missing)
        )

    return config


def create_client() -> fyersModel.FyersModel:
    config = load_config()

    return fyersModel.FyersModel(
        client_id=config["CLIENT_ID"],
        token=config["ACCESS_TOKEN"],
        is_async=False,
        log_path="",
    )


def normalize_nse_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()

    if not symbol:
        raise ValueError("Blank symbol.")

    if symbol.startswith("NSE:"):
        return symbol

    if symbol.endswith(".NS"):
        symbol = symbol[:-3]

    if symbol.endswith("-EQ"):
        return f"NSE:{symbol}"

    return f"NSE:{symbol}-EQ"


def short_symbol(value: str) -> str:
    return (
        str(value or "")
        .replace("NSE:", "")
        .replace("-EQ", "")
    )


def detect_symbol_column(frame: pd.DataFrame) -> str:
    candidates = [
        "nse_symbol",
        "NSE Symbol",
        "symbol",
        "Symbol",
        "yahoo_symbol",
    ]

    for column in candidates:
        if column in frame.columns:
            return column

    raise RuntimeError(
        "Could not find a symbol column in AQSD_Symbol_Master.csv."
    )


def load_master_symbols(limit: int | None = None) -> list[str]:
    if not SYMBOL_MASTER.exists():
        raise FileNotFoundError(
            f"Symbol master not found: {SYMBOL_MASTER}"
        )

    frame = pd.read_csv(SYMBOL_MASTER)
    symbol_column = detect_symbol_column(frame)

    if "active" in frame.columns:
        active = pd.to_numeric(
            frame["active"],
            errors="coerce",
        ).fillna(0)

        frame = frame[active == 1]

    symbols = sorted(
        {
            normalize_nse_symbol(value)
            for value in frame[symbol_column].dropna()
        }
    )

    if limit is not None:
        symbols = symbols[:max(1, limit)]

    return symbols


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [
        values[index:index + size]
        for index in range(0, len(values), size)
    ]


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_strength(
    ltp: float | None,
    open_price: float | None,
    high: float | None,
    low: float | None,
    change_percent: float | None,
) -> str:
    if ltp is None:
        return "NO DATA"

    score = 0

    if change_percent is not None:
        if change_percent >= 1:
            score += 2
        elif change_percent > 0:
            score += 1
        elif change_percent <= -1:
            score -= 2
        elif change_percent < 0:
            score -= 1

    if open_price is not None:
        score += 1 if ltp >= open_price else -1

    if high is not None and low is not None and high > low:
        location = (ltp - low) / (high - low)

        if location >= 0.75:
            score += 1
        elif location <= 0.25:
            score -= 1

    if score >= 3:
        return "STRONG"
    if score >= 1:
        return "POSITIVE"
    if score <= -3:
        return "VERY WEAK"
    if score <= -1:
        return "WEAK"
    return "NEUTRAL"


def parse_quote(item: dict[str, Any]) -> dict[str, Any]:
    values = item.get("v") or {}
    fyers_symbol = item.get("n") or values.get("symbol") or ""

    ltp = safe_float(values.get("lp"))
    open_price = safe_float(values.get("open_price"))
    high = safe_float(values.get("high_price"))
    low = safe_float(values.get("low_price"))
    previous_close = safe_float(values.get("prev_close_price"))
    change = safe_float(values.get("ch"))
    change_percent = safe_float(values.get("chp"))
    volume = safe_float(values.get("volume"))
    bid = safe_float(values.get("bid"))
    ask = safe_float(values.get("ask"))

    spread = None

    if bid is not None and ask is not None and ask > 0:
        spread = round(ask - bid, 4)

    day_position_percent = None

    if (
        ltp is not None
        and high is not None
        and low is not None
        and high > low
    ):
        day_position_percent = round(
            (ltp - low) / (high - low) * 100,
            2,
        )

    return {
        "nse_symbol": short_symbol(fyers_symbol),
        "fyers_symbol": fyers_symbol,
        "ltp": ltp,
        "change": change,
        "change_percent": change_percent,
        "open": open_price,
        "high": high,
        "low": low,
        "previous_close": previous_close,
        "volume": volume,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "day_position_percent": day_position_percent,
        "intraday_strength": classify_strength(
            ltp,
            open_price,
            high,
            low,
            change_percent,
        ),
        "fetched_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }


def fetch_batch(
    client: fyersModel.FyersModel,
    symbols: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    response = client.quotes(
        {"symbols": ",".join(symbols)}
    )

    if not isinstance(response, dict):
        raise RuntimeError("Unexpected FYERS quote response.")

    if response.get("s") != "ok":
        raise RuntimeError(
            "FYERS quote request failed. "
            f"Code={response.get('code')}; "
            f"Message={response.get('message')}"
        )

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    returned: set[str] = set()

    for item in response.get("d", []):
        if not isinstance(item, dict):
            continue

        row = parse_quote(item)
        rows.append(row)

        if row["fyers_symbol"]:
            returned.add(row["fyers_symbol"])

    for symbol in symbols:
        if symbol not in returned:
            failures.append(
                {
                    "fyers_symbol": symbol,
                    "reason": "No quote row returned",
                }
            )

    return rows, failures


def run_scanner(
    symbols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    client = create_client()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    batches = chunks(
        symbols,
        MAX_SYMBOLS_PER_REQUEST,
    )

    for batch_number, batch in enumerate(batches, start=1):
        print(
            f"Fetching batch {batch_number}/{len(batches)} "
            f"({len(batch)} symbols)..."
        )

        try:
            batch_rows, batch_failures = fetch_batch(
                client,
                batch,
            )
            rows.extend(batch_rows)
            failures.extend(batch_failures)

        except Exception as error:
            for symbol in batch:
                failures.append(
                    {
                        "fyers_symbol": symbol,
                        "reason": str(error),
                    }
                )

    frame = pd.DataFrame(rows)
    failed = pd.DataFrame(failures)

    if not frame.empty:
        frame = frame.sort_values(
            ["change_percent", "volume"],
            ascending=[False, False],
            na_position="last",
        ).reset_index(drop=True)

        frame.insert(
            0,
            "rank",
            range(1, len(frame) + 1),
        )

    return frame, failed


def save_outputs(
    frame: pd.DataFrame,
    failed: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    failed.to_csv(
        FAILED_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        OUTPUT_XLSX,
        engine="openpyxl",
    ) as writer:
        frame.to_excel(
            writer,
            sheet_name="Live Scanner",
            index=False,
        )

        failed.to_excel(
            writer,
            sheet_name="Failed Symbols",
            index=False,
        )

        summary = pd.DataFrame(
            [
                {
                    "generated_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "quotes_received": len(frame),
                    "failed_symbols": len(failed),
                }
            ]
        )

        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )


def show_results(
    frame: pd.DataFrame,
    failed: pd.DataFrame,
) -> None:
    print("\nAQSD FYERS LIVE SCANNER")
    print("=" * 100)

    if frame.empty:
        print("No quote rows received.")
    else:
        columns = [
            "rank",
            "nse_symbol",
            "ltp",
            "change_percent",
            "volume",
            "day_position_percent",
            "intraday_strength",
        ]

        print(
            frame[columns]
            .head(30)
            .to_string(index=False)
        )

    print("=" * 100)
    print(f"Quotes received: {len(frame)}")
    print(f"Failed symbols:  {len(failed)}")
    print(f"CSV:             {OUTPUT_CSV}")
    print(f"Excel:           {OUTPUT_XLSX}")
    print(f"Failures:        {FAILED_CSV}")


def show_status() -> None:
    print("\nAQSD FYERS LIVE SCANNER STATUS")
    print("=" * 72)
    print("Version: 1.0")
    print(
        f"Configuration: "
        f"{'FOUND' if CONFIG_FILE.exists() else 'MISSING'}"
    )
    print(
        f"Symbol master: "
        f"{'FOUND' if SYMBOL_MASTER.exists() else 'MISSING'}"
    )
    print(f"Output folder: {OUTPUT_DIR}")
    print("Database writes: DISABLED")
    print("Order placement: DISABLED")
    print("Yahoo files modified: NO")
    print("=" * 72)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Live Scanner."
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
        "--limit",
        type=int,
    )

    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.symbols:
        symbols = [
            normalize_nse_symbol(value)
            for value in args.symbols.split(",")
            if value.strip()
        ]
    else:
        symbols = load_master_symbols(
            limit=args.limit
        )

    frame, failed = run_scanner(
        symbols
    )

    save_outputs(
        frame,
        failed,
    )

    show_results(
        frame,
        failed,
    )


if __name__ == "__main__":
    main()
