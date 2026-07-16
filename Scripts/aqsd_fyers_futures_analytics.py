"""
AQSD Professional
Module: FYERS Futures Analytics Engine
Version: 1.0

Purpose
-------
Builds contract-level and underlying-level analytics for NEAR, NEXT and FAR
futures using the FYERS futures master plus live FYERS quotes/depth.

Key analytics
-------------
- Spot and futures prices
- Basis and basis percentage
- Annualized carry
- Near/Next/Far calendar spreads
- Contango / backwardation / mixed curve
- Contract-wise OI and previous-day OI
- OI change and OI change percentage
- Total OI across all three live expiries
- OI distribution and rollover share
- Contract value using lot size
- Indicative margin using a configurable percentage
- Long buildup / short buildup / short covering / long unwinding
- Combined rollover interpretation

Safety
------
- No order placement
- No AQSD database writes
- Writes only CSV/Excel/JSON outputs
- Keeps Yahoo files untouched

Expected input
--------------
Data/FYERS_Futures_Near_Next_Far.csv

Examples
--------
python aqsd_fyers_futures_analytics.py --status
python aqsd_fyers_futures_analytics.py --run --limit 10
python aqsd_fyers_futures_analytics.py --run --underlying RELIANCE
python aqsd_fyers_futures_analytics.py --run --margin-percent 18
python aqsd_fyers_futures_analytics.py --run --no-depth

Run with the FYERS virtual environment:
C:\\Users\\megha\\AQSD\\.venv-fyers\\Scripts\\python.exe
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fyers_apiv3 import fyersModel


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"

CONFIG_FILE = DATA_DIR / "fyers_config.env"
FUTURES_MASTER = DATA_DIR / "FYERS_Futures_Near_Next_Far.csv"

CONTRACT_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Futures_Contract_Analytics.csv"
UNDERLYING_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Futures_Analytics.csv"
EXCEL_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Futures_Analytics.xlsx"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Futures_Analytics.json"
FAILED_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Futures_Analytics_Failed.csv"

MAX_QUOTES_PER_REQUEST = 50


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


def create_client() -> fyersModel.FyersModel:
    config = load_config()

    return fyersModel.FyersModel(
        client_id=config["CLIENT_ID"],
        token=config["ACCESS_TOKEN"],
        is_async=False,
        log_path="",
    )


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None

        number = float(value)

        if math.isnan(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def normalize_text(value: Any) -> str:
    return str(value or "").strip().upper()


def detect_column(
    frame: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    direct = {
        str(column).strip().lower(): column
        for column in frame.columns
    }

    for candidate in candidates:
        key = candidate.lower()

        if key in direct:
            return direct[key]

    for candidate in candidates:
        key = candidate.lower()

        for column in frame.columns:
            if key in str(column).strip().lower():
                return column

    return None


def load_master(
    underlying_filter: str | None,
    limit: int | None,
) -> pd.DataFrame:
    if not FUTURES_MASTER.exists():
        raise FileNotFoundError(
            f"Futures master not found:\n{FUTURES_MASTER}\n"
            "Run aqsd_fyers_symbol_master_updater.py --run first."
        )

    frame = pd.read_csv(
        FUTURES_MASTER,
        low_memory=False,
    )

    mapping = {
        "underlying": detect_column(
            frame,
            ["underlying", "underlying_symbol"],
        ),
        "fyers_symbol": detect_column(
            frame,
            ["fyers_symbol", "symbol"],
        ),
        "expiry_date": detect_column(
            frame,
            ["expiry_date", "expiry"],
        ),
        "expiry_bucket": detect_column(
            frame,
            ["expiry_bucket", "bucket"],
        ),
        "lot_size": detect_column(
            frame,
            ["effective_lot_size", "minimum_lot_size", "lot_size"],
        ),
        "tick_size": detect_column(
            frame,
            ["tick_size"],
        ),
        "days_to_expiry": detect_column(
            frame,
            ["days_to_expiry"],
        ),
    }

    required = [
        "underlying",
        "fyers_symbol",
        "expiry_date",
        "expiry_bucket",
        "lot_size",
    ]

    missing = [
        key
        for key in required
        if mapping[key] is None
    ]

    if missing:
        raise RuntimeError(
            "Futures master is missing required columns: "
            + ", ".join(missing)
        )

    result = pd.DataFrame(
        {
            "underlying": (
                frame[mapping["underlying"]]
                .astype(str)
                .str.strip()
                .str.upper()
            ),
            "fyers_symbol": (
                frame[mapping["fyers_symbol"]]
                .astype(str)
                .str.strip()
                .str.upper()
            ),
            "expiry_date": pd.to_datetime(
                frame[mapping["expiry_date"]],
                errors="coerce",
            ),
            "expiry_bucket": (
                frame[mapping["expiry_bucket"]]
                .astype(str)
                .str.strip()
                .str.upper()
            ),
            "lot_size": pd.to_numeric(
                frame[mapping["lot_size"]],
                errors="coerce",
            ),
        }
    )

    if mapping["tick_size"]:
        result["tick_size"] = pd.to_numeric(
            frame[mapping["tick_size"]],
            errors="coerce",
        )
    else:
        result["tick_size"] = pd.NA

    if mapping["days_to_expiry"]:
        result["days_to_expiry"] = pd.to_numeric(
            frame[mapping["days_to_expiry"]],
            errors="coerce",
        )
    else:
        today = pd.Timestamp(date.today())
        result["days_to_expiry"] = (
            result["expiry_date"] - today
        ).dt.days

    result = result[
        result["expiry_bucket"].isin(
            ["NEAR", "NEXT", "FAR"]
        )
    ].copy()

    result = result[
        result["expiry_date"].notna()
        & (
            result["expiry_date"]
            >= pd.Timestamp(date.today())
        )
    ].copy()

    result = result.drop_duplicates(
        subset=[
            "underlying",
            "expiry_bucket",
            "fyers_symbol",
        ]
    )

    if underlying_filter:
        target = normalize_text(underlying_filter)

        result = result[
            result["underlying"] == target
        ]

    if limit is not None:
        selected = (
            result["underlying"]
            .drop_duplicates()
            .head(max(1, limit))
            .tolist()
        )

        result = result[
            result["underlying"].isin(selected)
        ]

    return result.sort_values(
        [
            "underlying",
            "expiry_date",
        ]
    ).reset_index(drop=True)


def spot_symbol(underlying: str) -> str:
    value = normalize_text(underlying)

    index_map = {
        "NIFTY": "NSE:NIFTY50-INDEX",
        "NIFTY50": "NSE:NIFTY50-INDEX",
        "NIFTY 50": "NSE:NIFTY50-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
        "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
        "NIFTY BANK": "NSE:NIFTYBANK-INDEX",
        "FINNIFTY": "NSE:FINNIFTY-INDEX",
        "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    }

    if value in index_map:
        return index_map[value]

    if value.startswith("NSE:"):
        return value

    if value.endswith("-EQ"):
        return f"NSE:{value}"

    return f"NSE:{value}-EQ"


def chunks(
    values: list[str],
    size: int,
) -> list[list[str]]:
    return [
        values[index:index + size]
        for index in range(0, len(values), size)
    ]


def parse_quote_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    values = item.get("v") or {}
    symbol = item.get("n") or values.get("symbol") or ""

    return {
        "symbol": symbol,
        "ltp": safe_float(values.get("lp")),
        "change": safe_float(values.get("ch")),
        "change_percent": safe_float(values.get("chp")),
        "open": safe_float(values.get("open_price")),
        "high": safe_float(values.get("high_price")),
        "low": safe_float(values.get("low_price")),
        "previous_close": safe_float(
            values.get("prev_close_price")
        ),
        "volume": safe_float(values.get("volume")),
        "bid": safe_float(values.get("bid")),
        "ask": safe_float(values.get("ask")),
    }


def fetch_quotes(
    client: fyersModel.FyersModel,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    quote_map: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    unique_symbols = sorted(
        {
            symbol
            for symbol in symbols
            if symbol
        }
    )

    for batch_number, batch in enumerate(
        chunks(unique_symbols, MAX_QUOTES_PER_REQUEST),
        start=1,
    ):
        try:
            response = client.quotes(
                {
                    "symbols": ",".join(batch)
                }
            )

            if not isinstance(response, dict):
                raise RuntimeError(
                    "Unexpected FYERS quote response."
                )

            if response.get("s") != "ok":
                raise RuntimeError(
                    f"Code={response.get('code')}; "
                    f"Message={response.get('message')}"
                )

            returned: set[str] = set()

            for item in response.get("d", []):
                if not isinstance(item, dict):
                    continue

                row = parse_quote_item(item)
                symbol = row["symbol"]

                if symbol:
                    quote_map[symbol] = row
                    returned.add(symbol)

            for symbol in batch:
                if symbol not in returned:
                    failures.append(
                        {
                            "stage": "QUOTE",
                            "symbol": symbol,
                            "reason": "No quote returned",
                        }
                    )

        except Exception as error:
            for symbol in batch:
                failures.append(
                    {
                        "stage": "QUOTE",
                        "symbol": symbol,
                        "reason": str(error),
                    }
                )

        print(
            f"Quote batch {batch_number}/"
            f"{len(chunks(unique_symbols, MAX_QUOTES_PER_REQUEST))} completed."
        )

    return quote_map, failures


def extract_depth_payload(
    response: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    data = response.get("d")

    if isinstance(data, dict):
        payload = data.get(symbol)

        if isinstance(payload, dict):
            return payload

        if len(data) == 1:
            value = next(iter(data.values()))

            if isinstance(value, dict):
                return value

    raise RuntimeError(
        "Could not locate symbol payload in FYERS depth response."
    )


def fetch_depth(
    client: fyersModel.FyersModel,
    symbols: list[str],
    delay_seconds: float,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    depth_map: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    total = len(symbols)

    for index, symbol in enumerate(symbols, start=1):
        try:
            response = client.depth(
                {
                    "symbol": symbol,
                    "ohlcv_flag": "1",
                }
            )

            if not isinstance(response, dict):
                raise RuntimeError(
                    "Unexpected FYERS depth response."
                )

            if response.get("s") != "ok":
                raise RuntimeError(
                    f"Code={response.get('code')}; "
                    f"Message={response.get('message')}"
                )

            depth_map[symbol] = extract_depth_payload(
                response,
                symbol,
            )

        except Exception as error:
            failures.append(
                {
                    "stage": "DEPTH",
                    "symbol": symbol,
                    "reason": str(error),
                }
            )

        if index % 25 == 0 or index == total:
            print(
                f"Depth completed: {index}/{total}"
            )

        if delay_seconds > 0 and index < total:
            time.sleep(delay_seconds)

    return depth_map, failures


def contract_classification(
    price_change_percent: float | None,
    oi_change: float | None,
) -> str:
    if price_change_percent is None or oi_change is None:
        return "INSUFFICIENT DATA"

    price_up = price_change_percent > 0
    price_down = price_change_percent < 0
    oi_up = oi_change > 0
    oi_down = oi_change < 0

    if price_up and oi_up:
        return "LONG BUILDUP"

    if price_down and oi_up:
        return "SHORT BUILDUP"

    if price_up and oi_down:
        return "SHORT COVERING"

    if price_down and oi_down:
        return "LONG UNWINDING"

    return "NEUTRAL"


def build_contract_analytics(
    master: pd.DataFrame,
    quotes: dict[str, dict[str, Any]],
    depth: dict[str, dict[str, Any]],
    margin_percent: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, contract in master.iterrows():
        fyers_symbol = contract["fyers_symbol"]
        underlying = contract["underlying"]
        spot = spot_symbol(underlying)

        future_quote = quotes.get(
            fyers_symbol,
            {},
        )
        spot_quote = quotes.get(
            spot,
            {},
        )
        depth_payload = depth.get(
            fyers_symbol,
            {},
        )

        future_price = safe_float(
            future_quote.get("ltp")
        )
        spot_price = safe_float(
            spot_quote.get("ltp")
        )

        if future_price is None:
            future_price = safe_float(
                depth_payload.get("ltp")
            )

        future_change_percent = safe_float(
            future_quote.get("change_percent")
        )

        if future_change_percent is None:
            future_change_percent = safe_float(
                depth_payload.get("chp")
            )

        volume = safe_float(
            future_quote.get("volume")
        )

        if volume is None:
            volume = safe_float(
                depth_payload.get("v")
            )

        oi = safe_float(
            depth_payload.get("oi")
        )
        previous_day_oi = safe_float(
            depth_payload.get("pdoi")
        )
        oi_change_percent = safe_float(
            depth_payload.get("oipercent")
        )

        oi_change = None

        if oi is not None and previous_day_oi is not None:
            oi_change = oi - previous_day_oi

        basis = None
        basis_percent = None
        annualized_carry_percent = None

        if (
            future_price is not None
            and spot_price is not None
            and spot_price != 0
        ):
            basis = future_price - spot_price
            basis_percent = basis / spot_price * 100

            days = safe_float(
                contract["days_to_expiry"]
            )

            if days is not None and days > 0:
                annualized_carry_percent = (
                    basis_percent * 365 / days
                )

        lot_size = safe_float(
            contract["lot_size"]
        )

        contract_value = None
        indicative_margin = None

        if future_price is not None and lot_size is not None:
            contract_value = future_price * lot_size
            indicative_margin = (
                contract_value
                * margin_percent
                / 100
            )

        rows.append(
            {
                "underlying": underlying,
                "expiry_bucket": contract["expiry_bucket"],
                "expiry_date": (
                    contract["expiry_date"].date().isoformat()
                    if not pd.isna(contract["expiry_date"])
                    else ""
                ),
                "days_to_expiry": safe_float(
                    contract["days_to_expiry"]
                ),
                "fyers_symbol": fyers_symbol,
                "spot_symbol": spot,
                "spot_price": spot_price,
                "future_price": future_price,
                "future_change_percent": future_change_percent,
                "basis": basis,
                "basis_percent": basis_percent,
                "annualized_carry_percent": (
                    annualized_carry_percent
                ),
                "volume": volume,
                "open_interest": oi,
                "previous_day_open_interest": previous_day_oi,
                "oi_change": oi_change,
                "oi_change_percent": oi_change_percent,
                "futures_cycle": contract_classification(
                    future_change_percent,
                    oi_change,
                ),
                "lot_size": lot_size,
                "tick_size": safe_float(
                    contract["tick_size"]
                ),
                "contract_value": contract_value,
                "indicative_margin_percent": margin_percent,
                "indicative_margin_amount": indicative_margin,
                "fetched_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    return pd.DataFrame(rows)


def value_for_bucket(
    group: pd.DataFrame,
    bucket: str,
    column: str,
) -> Any:
    rows = group[
        group["expiry_bucket"] == bucket
    ]

    if rows.empty:
        return None

    return rows.iloc[0].get(column)


def classify_curve(
    near: float | None,
    next_price: float | None,
    far: float | None,
) -> str:
    available = [
        value
        for value in [near, next_price, far]
        if value is not None
    ]

    if len(available) < 2:
        return "INSUFFICIENT DATA"

    if (
        near is not None
        and next_price is not None
        and far is not None
    ):
        if far > next_price > near:
            return "CONTANGO"

        if far < next_price < near:
            return "BACKWARDATION"

        return "MIXED CURVE"

    first = available[0]
    second = available[1]

    if second > first:
        return "CONTANGO"

    if second < first:
        return "BACKWARDATION"

    return "FLAT CURVE"


def combined_interpretation(
    near_cycle: str,
    next_cycle: str,
    far_cycle: str,
    next_share: float | None,
    far_share: float | None,
) -> str:
    cycles = {
        "NEAR": near_cycle,
        "NEXT": next_cycle,
        "FAR": far_cycle,
    }

    if (
        near_cycle in {"SHORT COVERING", "LONG UNWINDING"}
        and next_cycle == "LONG BUILDUP"
    ):
        return "BULLISH ROLLOVER TO NEXT"

    if (
        near_cycle in {"SHORT COVERING", "LONG UNWINDING"}
        and far_cycle == "LONG BUILDUP"
    ):
        return "BULLISH POSITIONING IN FAR"

    if (
        near_cycle in {"LONG UNWINDING", "SHORT COVERING"}
        and next_cycle == "SHORT BUILDUP"
    ):
        return "BEARISH ROLLOVER TO NEXT"

    if (
        near_cycle == "LONG BUILDUP"
        and next_cycle == "LONG BUILDUP"
    ):
        return "BROAD LONG BUILDUP"

    if (
        near_cycle == "SHORT BUILDUP"
        and next_cycle == "SHORT BUILDUP"
    ):
        return "BROAD SHORT BUILDUP"

    if next_share is not None and next_share >= 50:
        return "OI CONCENTRATED IN NEXT"

    if far_share is not None and far_share >= 30:
        return "ELEVATED FAR-MONTH POSITIONING"

    meaningful = [
        value
        for value in cycles.values()
        if value not in {
            "INSUFFICIENT DATA",
            "NEUTRAL",
        }
    ]

    if not meaningful:
        return "NO CLEAR ROLLOVER SIGNAL"

    return "MIXED FUTURES POSITIONING"


def build_underlying_analytics(
    contract_frame: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for underlying, group in contract_frame.groupby(
        "underlying"
    ):
        near_price = safe_float(
            value_for_bucket(
                group,
                "NEAR",
                "future_price",
            )
        )
        next_price = safe_float(
            value_for_bucket(
                group,
                "NEXT",
                "future_price",
            )
        )
        far_price = safe_float(
            value_for_bucket(
                group,
                "FAR",
                "future_price",
            )
        )

        near_oi = safe_float(
            value_for_bucket(
                group,
                "NEAR",
                "open_interest",
            )
        ) or 0.0
        next_oi = safe_float(
            value_for_bucket(
                group,
                "NEXT",
                "open_interest",
            )
        ) or 0.0
        far_oi = safe_float(
            value_for_bucket(
                group,
                "FAR",
                "open_interest",
            )
        ) or 0.0

        total_oi = near_oi + next_oi + far_oi

        near_share = (
            near_oi / total_oi * 100
            if total_oi > 0
            else None
        )
        next_share = (
            next_oi / total_oi * 100
            if total_oi > 0
            else None
        )
        far_share = (
            far_oi / total_oi * 100
            if total_oi > 0
            else None
        )

        rollover_share = (
            (next_oi + far_oi) / total_oi * 100
            if total_oi > 0
            else None
        )

        near_cycle = str(
            value_for_bucket(
                group,
                "NEAR",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )
        next_cycle = str(
            value_for_bucket(
                group,
                "NEXT",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )
        far_cycle = str(
            value_for_bucket(
                group,
                "FAR",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )

        rows.append(
            {
                "underlying": underlying,
                "spot_price": value_for_bucket(
                    group,
                    "NEAR",
                    "spot_price",
                ),
                "near_expiry": value_for_bucket(
                    group,
                    "NEAR",
                    "expiry_date",
                ),
                "next_expiry": value_for_bucket(
                    group,
                    "NEXT",
                    "expiry_date",
                ),
                "far_expiry": value_for_bucket(
                    group,
                    "FAR",
                    "expiry_date",
                ),
                "near_price": near_price,
                "next_price": next_price,
                "far_price": far_price,
                "near_next_spread": (
                    next_price - near_price
                    if (
                        near_price is not None
                        and next_price is not None
                    )
                    else None
                ),
                "next_far_spread": (
                    far_price - next_price
                    if (
                        next_price is not None
                        and far_price is not None
                    )
                    else None
                ),
                "term_structure": classify_curve(
                    near_price,
                    next_price,
                    far_price,
                ),
                "near_basis": value_for_bucket(
                    group,
                    "NEAR",
                    "basis",
                ),
                "next_basis": value_for_bucket(
                    group,
                    "NEXT",
                    "basis",
                ),
                "far_basis": value_for_bucket(
                    group,
                    "FAR",
                    "basis",
                ),
                "near_annualized_carry_percent": value_for_bucket(
                    group,
                    "NEAR",
                    "annualized_carry_percent",
                ),
                "next_annualized_carry_percent": value_for_bucket(
                    group,
                    "NEXT",
                    "annualized_carry_percent",
                ),
                "far_annualized_carry_percent": value_for_bucket(
                    group,
                    "FAR",
                    "annualized_carry_percent",
                ),
                "near_open_interest": near_oi,
                "next_open_interest": next_oi,
                "far_open_interest": far_oi,
                "total_open_interest": total_oi,
                "near_oi_share_percent": near_share,
                "next_oi_share_percent": next_share,
                "far_oi_share_percent": far_share,
                "rollover_share_percent": rollover_share,
                "near_oi_change": value_for_bucket(
                    group,
                    "NEAR",
                    "oi_change",
                ),
                "next_oi_change": value_for_bucket(
                    group,
                    "NEXT",
                    "oi_change",
                ),
                "far_oi_change": value_for_bucket(
                    group,
                    "FAR",
                    "oi_change",
                ),
                "near_cycle": near_cycle,
                "next_cycle": next_cycle,
                "far_cycle": far_cycle,
                "rollover_interpretation": combined_interpretation(
                    near_cycle,
                    next_cycle,
                    far_cycle,
                    next_share,
                    far_share,
                ),
                "near_lot_size": value_for_bucket(
                    group,
                    "NEAR",
                    "lot_size",
                ),
                "near_contract_value": value_for_bucket(
                    group,
                    "NEAR",
                    "contract_value",
                ),
                "near_indicative_margin": value_for_bucket(
                    group,
                    "NEAR",
                    "indicative_margin_amount",
                ),
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    result = pd.DataFrame(rows)

    if not result.empty:
        result = result.sort_values(
            [
                "rollover_share_percent",
                "total_open_interest",
            ],
            ascending=[
                False,
                False,
            ],
            na_position="last",
        ).reset_index(drop=True)

        result.insert(
            0,
            "rank",
            range(1, len(result) + 1),
        )

    return result


def save_outputs(
    contract_frame: pd.DataFrame,
    underlying_frame: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    contract_frame.to_csv(
        CONTRACT_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    underlying_frame.to_csv(
        UNDERLYING_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    failures.to_csv(
        FAILED_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        EXCEL_OUTPUT,
        engine="openpyxl",
    ) as writer:
        underlying_frame.to_excel(
            writer,
            sheet_name="Underlying Analytics",
            index=False,
        )

        contract_frame.to_excel(
            writer,
            sheet_name="Contract Analytics",
            index=False,
        )

        failures.to_excel(
            writer,
            sheet_name="Failed Requests",
            index=False,
        )

        summary = pd.DataFrame(
            [
                {
                    "generated_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "underlyings": len(underlying_frame),
                    "contracts": len(contract_frame),
                    "failed_requests": len(failures),
                    "order_placement": "DISABLED",
                    "database_writes": "DISABLED",
                }
            ]
        )

        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "underlying_rows": underlying_frame.to_dict(
                    orient="records"
                ),
                "contract_rows": contract_frame.to_dict(
                    orient="records"
                ),
                "failures": failures.to_dict(
                    orient="records"
                ),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def show_preview(
    underlying_frame: pd.DataFrame,
    contract_frame: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    print("\nAQSD FYERS FUTURES ANALYTICS")
    print("=" * 120)

    if underlying_frame.empty:
        print("No underlying analytics created.")
    else:
        columns = [
            "rank",
            "underlying",
            "spot_price",
            "near_price",
            "next_price",
            "far_price",
            "term_structure",
            "total_open_interest",
            "rollover_share_percent",
            "near_cycle",
            "next_cycle",
            "far_cycle",
            "rollover_interpretation",
        ]

        available = [
            column
            for column in columns
            if column in underlying_frame.columns
        ]

        print(
            underlying_frame[available]
            .head(30)
            .to_string(index=False)
        )

    print("=" * 120)
    print(f"Underlyings:       {len(underlying_frame)}")
    print(f"Contracts:         {len(contract_frame)}")
    print(f"Failed requests:   {len(failures)}")
    print(f"Underlying CSV:    {UNDERLYING_OUTPUT}")
    print(f"Contract CSV:      {CONTRACT_OUTPUT}")
    print(f"Excel:             {EXCEL_OUTPUT}")
    print(f"JSON:              {JSON_OUTPUT}")
    print(f"Failures:          {FAILED_OUTPUT}")


def show_status() -> None:
    print("\nAQSD FYERS FUTURES ANALYTICS STATUS")
    print("=" * 78)
    print("Version: 1.0")
    print(
        f"Configuration: "
        f"{'FOUND' if CONFIG_FILE.exists() else 'MISSING'}"
    )
    print(
        f"Futures master: "
        f"{'FOUND' if FUTURES_MASTER.exists() else 'MISSING'}"
    )
    print(f"Output folder: {OUTPUT_DIR}")
    print("Order placement: DISABLED")
    print("AQSD database writes: DISABLED")
    print("Yahoo files modified: NO")
    print("=" * 78)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Futures Analytics Engine."
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
        "--underlying",
        help="Run one underlying, e.g. RELIANCE.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit underlyings for testing.",
    )

    parser.add_argument(
        "--margin-percent",
        type=float,
        default=18.0,
        help="Indicative margin percentage. Default 18.",
    )

    parser.add_argument(
        "--depth-delay",
        type=float,
        default=0.20,
        help="Pause between depth calls in seconds.",
    )

    parser.add_argument(
        "--no-depth",
        action="store_true",
        help="Skip depth calls. OI fields will be unavailable.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    master = load_master(
        underlying_filter=args.underlying,
        limit=args.limit,
    )

    if master.empty:
        raise RuntimeError(
            "No NEAR/NEXT/FAR futures contracts matched the request."
        )

    client = create_client()

    futures_symbols = master[
        "fyers_symbol"
    ].dropna().astype(str).tolist()

    spot_symbols = [
        spot_symbol(value)
        for value in master[
            "underlying"
        ].drop_duplicates().tolist()
    ]

    quote_map, quote_failures = fetch_quotes(
        client,
        futures_symbols + spot_symbols,
    )

    depth_map: dict[str, dict[str, Any]] = {}
    depth_failures: list[dict[str, str]] = []

    if not args.no_depth:
        depth_map, depth_failures = fetch_depth(
            client,
            futures_symbols,
            max(0.0, args.depth_delay),
        )

    contract_frame = build_contract_analytics(
        master,
        quote_map,
        depth_map,
        max(0.0, args.margin_percent),
    )

    underlying_frame = build_underlying_analytics(
        contract_frame
    )

    failures = pd.DataFrame(
        quote_failures + depth_failures,
        columns=[
            "stage",
            "symbol",
            "reason",
        ],
    )

    save_outputs(
        contract_frame,
        underlying_frame,
        failures,
    )

    show_preview(
        underlying_frame,
        contract_frame,
        failures,
    )


if __name__ == "__main__":
    main()
