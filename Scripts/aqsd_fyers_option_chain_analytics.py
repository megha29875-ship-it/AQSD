"""
AQSD Professional
Module: FYERS Option Chain Analytics Engine
Version: 1.0

Purpose
-------
Builds a strike-wise option chain from AQSD's FYERS options master and live
FYERS data, then calculates:

- ATM strike
- Call and put OI
- Previous-day OI
- Change in OI
- OI PCR
- Volume PCR
- Maximum call-OI resistance
- Maximum put-OI support
- Max pain
- Strike-wise CE/PE analytics
- Option-writing / covering labels based on premium and OI changes

Important design choice
-----------------------
This first production-safe version runs ONE underlying and ONE expiry at a
time. A complete all-stock options-chain run can involve thousands of
contracts and should only be added after API-load testing.

Safety
------
- No order placement
- No AQSD database writes
- Yahoo files untouched
- Reads API credentials from Data/fyers_config.env

Required input
--------------
Data/FYERS_Options_Contracts.csv

Examples
--------
python aqsd_fyers_option_chain_analytics.py --status

python aqsd_fyers_option_chain_analytics.py ^
    --run --underlying RELIANCE --expiry NEAR --strikes 10

python aqsd_fyers_option_chain_analytics.py ^
    --run --underlying NIFTY --expiry NEAR --strikes 20

Run with:
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
OPTIONS_MASTER = DATA_DIR / "FYERS_Options_Contracts.csv"

CHAIN_CSV = OUTPUT_DIR / "AQSD_FYERS_Option_Chain.csv"
SUMMARY_CSV = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Summary.csv"
FAILED_CSV = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Failed.csv"
EXCEL_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Analytics.xlsx"
JSON_OUTPUT = OUTPUT_DIR / "AQSD_FYERS_Option_Chain_Analytics.json"

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


def detect_column(
    frame: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    lower_map = {
        str(column).strip().lower(): column
        for column in frame.columns
    }

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    for candidate in candidates:
        target = candidate.lower()

        for column in frame.columns:
            if target in str(column).strip().lower():
                return column

    return None


def spot_symbol(underlying: str) -> str:
    value = str(underlying).strip().upper()

    index_map = {
        "NIFTY": "NSE:NIFTY50-INDEX",
        "NIFTY50": "NSE:NIFTY50-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
        "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
        "FINNIFTY": "NSE:FINNIFTY-INDEX",
        "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
        "NIFTYNXT50": "NSE:NIFTYNXT50-INDEX",
    }

    if value in index_map:
        return index_map[value]

    return f"NSE:{value}-EQ"


def load_option_master(
    underlying: str,
    expiry_selector: str,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    if not OPTIONS_MASTER.exists():
        raise FileNotFoundError(
            f"Options master not found:\n{OPTIONS_MASTER}\n"
            "Run aqsd_fyers_symbol_master_updater_v3.py --build first."
        )

    frame = pd.read_csv(
        OPTIONS_MASTER,
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
        "strike_price": detect_column(
            frame,
            ["strike_price", "strike"],
        ),
        "option_type": detect_column(
            frame,
            ["option_type"],
        ),
        "lot_size": detect_column(
            frame,
            ["lot_size"],
        ),
    }

    missing = [
        key
        for key in [
            "underlying",
            "fyers_symbol",
            "expiry_date",
            "strike_price",
            "option_type",
            "lot_size",
        ]
        if mapping[key] is None
    ]

    if missing:
        raise RuntimeError(
            "Options master missing required columns: "
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
            "strike_price": pd.to_numeric(
                frame[mapping["strike_price"]],
                errors="coerce",
            ),
            "option_type": (
                frame[mapping["option_type"]]
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

    target = str(underlying).strip().upper()

    result = result[
        (result["underlying"] == target)
        & result["option_type"].isin(["CE", "PE"])
        & result["expiry_date"].notna()
        & (
            result["expiry_date"]
            >= pd.Timestamp(date.today())
        )
    ].copy()

    if result.empty:
        raise RuntimeError(
            f"No live option contracts found for {target}."
        )

    expiries = sorted(
        result["expiry_date"]
        .drop_duplicates()
        .tolist()
    )

    selector = str(expiry_selector).strip().upper()

    bucket_map = {
        "NEAR": 0,
        "NEXT": 1,
        "FAR": 2,
    }

    if selector in bucket_map:
        index = bucket_map[selector]

        if index >= len(expiries):
            raise RuntimeError(
                f"{selector} expiry is unavailable for {target}."
            )

        selected_expiry = pd.Timestamp(expiries[index])

    else:
        selected_expiry = pd.to_datetime(
            expiry_selector,
            errors="coerce",
        )

        if pd.isna(selected_expiry):
            raise RuntimeError(
                "Expiry must be NEAR, NEXT, FAR or YYYY-MM-DD."
            )

        selected_expiry = pd.Timestamp(
            selected_expiry
        ).normalize()

    result = result[
        result["expiry_date"].dt.normalize()
        == selected_expiry.normalize()
    ].copy()

    if result.empty:
        available = ", ".join(
            pd.Timestamp(value).strftime("%Y-%m-%d")
            for value in expiries
        )

        raise RuntimeError(
            f"Expiry {selected_expiry.date()} not found. "
            f"Available expiries: {available}"
        )

    result = result.drop_duplicates(
        subset=["fyers_symbol"]
    )

    return result, selected_expiry


def chunks(
    values: list[str],
    size: int,
) -> list[list[str]]:
    return [
        values[index:index + size]
        for index in range(0, len(values), size)
    ]


def fetch_quotes(
    client: fyersModel.FyersModel,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    quote_map: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    unique_symbols = sorted(set(symbols))

    for batch in chunks(
        unique_symbols,
        MAX_QUOTES_PER_REQUEST,
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

                values = item.get("v") or {}
                symbol = (
                    item.get("n")
                    or values.get("symbol")
                    or ""
                )

                if not symbol:
                    continue

                quote_map[symbol] = {
                    "ltp": safe_float(values.get("lp")),
                    "change": safe_float(values.get("ch")),
                    "change_percent": safe_float(
                        values.get("chp")
                    ),
                    "volume": safe_float(
                        values.get("volume")
                    ),
                    "bid": safe_float(values.get("bid")),
                    "ask": safe_float(values.get("ask")),
                }

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
            first_value = next(iter(data.values()))

            if isinstance(first_value, dict):
                return first_value

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

    for index, symbol in enumerate(
        symbols,
        start=1,
    ):
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

        if index % 20 == 0 or index == total:
            print(
                f"Option depth completed: {index}/{total}"
            )

        if delay_seconds > 0 and index < total:
            time.sleep(delay_seconds)

    return depth_map, failures


def choose_strikes(
    option_master: pd.DataFrame,
    spot_price: float,
    strike_count_each_side: int,
) -> tuple[pd.DataFrame, float]:
    strikes = sorted(
        option_master["strike_price"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    if not strikes:
        raise RuntimeError(
            "No strikes found in selected option expiry."
        )

    atm_strike = min(
        strikes,
        key=lambda strike: abs(
            float(strike) - spot_price
        ),
    )

    atm_index = strikes.index(atm_strike)

    start = max(
        0,
        atm_index - strike_count_each_side,
    )

    end = min(
        len(strikes),
        atm_index + strike_count_each_side + 1,
    )

    selected = set(
        strikes[start:end]
    )

    result = option_master[
        option_master["strike_price"].isin(selected)
    ].copy()

    return result, float(atm_strike)


def option_position_label(
    premium_change_percent: float | None,
    oi_change: float | None,
) -> str:
    if (
        premium_change_percent is None
        or oi_change is None
    ):
        return "INSUFFICIENT DATA"

    if premium_change_percent > 0 and oi_change > 0:
        return "FRESH OPTION BUYING"

    if premium_change_percent < 0 and oi_change > 0:
        return "FRESH OPTION WRITING"

    if premium_change_percent > 0 and oi_change < 0:
        return "WRITER SHORT COVERING"

    if premium_change_percent < 0 and oi_change < 0:
        return "OPTION LONG UNWINDING"

    return "NEUTRAL"


def build_contract_rows(
    selected_options: pd.DataFrame,
    quote_map: dict[str, dict[str, Any]],
    depth_map: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, contract in selected_options.iterrows():
        symbol = contract["fyers_symbol"]
        quote = quote_map.get(symbol, {})
        depth = depth_map.get(symbol, {})

        ltp = safe_float(quote.get("ltp"))

        if ltp is None:
            ltp = safe_float(depth.get("ltp"))

        change_percent = safe_float(
            quote.get("change_percent")
        )

        if change_percent is None:
            change_percent = safe_float(
                depth.get("chp")
            )

        volume = safe_float(
            quote.get("volume")
        )

        if volume is None:
            volume = safe_float(depth.get("v"))

        current_oi = safe_float(depth.get("oi"))
        previous_day_oi = safe_float(
            depth.get("pdoi")
        )

        oi_change = None

        if (
            current_oi is not None
            and previous_day_oi is not None
        ):
            oi_change = (
                current_oi - previous_day_oi
            )

        rows.append(
            {
                "underlying": contract["underlying"],
                "expiry_date": (
                    contract["expiry_date"]
                    .date()
                    .isoformat()
                ),
                "strike_price": safe_float(
                    contract["strike_price"]
                ),
                "option_type": contract["option_type"],
                "fyers_symbol": symbol,
                "ltp": ltp,
                "change_percent": change_percent,
                "volume": volume,
                "open_interest": current_oi,
                "previous_day_open_interest": (
                    previous_day_oi
                ),
                "oi_change": oi_change,
                "oi_change_percent": safe_float(
                    depth.get("oipercent")
                ),
                "bid": safe_float(
                    quote.get("bid")
                ),
                "ask": safe_float(
                    quote.get("ask")
                ),
                "lot_size": safe_float(
                    contract["lot_size"]
                ),
                "position_label": option_position_label(
                    change_percent,
                    oi_change,
                ),
                "fetched_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        )

    return pd.DataFrame(rows)


def calculate_max_pain(
    chain: pd.DataFrame,
) -> float | None:
    if chain.empty:
        return None

    strikes = sorted(
        chain["strike_price"]
        .dropna()
        .unique()
        .tolist()
    )

    if not strikes:
        return None

    pain_rows: list[tuple[float, float]] = []

    for settlement in strikes:
        total_pain = 0.0

        for _, row in chain.iterrows():
            strike = safe_float(
                row["strike_price"]
            )
            oi = safe_float(
                row["open_interest"]
            ) or 0.0
            option_type = row["option_type"]

            if strike is None:
                continue

            if option_type == "CE":
                intrinsic = max(
                    settlement - strike,
                    0,
                )
            else:
                intrinsic = max(
                    strike - settlement,
                    0,
                )

            total_pain += intrinsic * oi

        pain_rows.append(
            (
                float(settlement),
                total_pain,
            )
        )

    return min(
        pain_rows,
        key=lambda item: item[1],
    )[0]


def pivot_chain(
    contracts: pd.DataFrame,
    spot_price: float,
    atm_strike: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for strike, group in contracts.groupby(
        "strike_price"
    ):
        ce = group[
            group["option_type"] == "CE"
        ]

        pe = group[
            group["option_type"] == "PE"
        ]

        ce_row = (
            ce.iloc[0]
            if not ce.empty
            else pd.Series(dtype=object)
        )

        pe_row = (
            pe.iloc[0]
            if not pe.empty
            else pd.Series(dtype=object)
        )

        strike_value = safe_float(strike)

        if strike_value is None:
            moneyness = ""
        elif strike_value == atm_strike:
            moneyness = "ATM"
        elif strike_value < spot_price:
            moneyness = "CE ITM / PE OTM"
        else:
            moneyness = "CE OTM / PE ITM"

        rows.append(
            {
                "strike_price": strike_value,
                "moneyness": moneyness,
                "ce_ltp": ce_row.get("ltp"),
                "ce_change_percent": ce_row.get(
                    "change_percent"
                ),
                "ce_volume": ce_row.get("volume"),
                "ce_open_interest": ce_row.get(
                    "open_interest"
                ),
                "ce_oi_change": ce_row.get(
                    "oi_change"
                ),
                "ce_position": ce_row.get(
                    "position_label"
                ),
                "pe_ltp": pe_row.get("ltp"),
                "pe_change_percent": pe_row.get(
                    "change_percent"
                ),
                "pe_volume": pe_row.get("volume"),
                "pe_open_interest": pe_row.get(
                    "open_interest"
                ),
                "pe_oi_change": pe_row.get(
                    "oi_change"
                ),
                "pe_position": pe_row.get(
                    "position_label"
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "strike_price"
    ).reset_index(drop=True)


def build_summary(
    contracts: pd.DataFrame,
    chain: pd.DataFrame,
    underlying: str,
    expiry_date: pd.Timestamp,
    spot_price: float,
    atm_strike: float,
) -> pd.DataFrame:
    ce = contracts[
        contracts["option_type"] == "CE"
    ]

    pe = contracts[
        contracts["option_type"] == "PE"
    ]

    total_ce_oi = pd.to_numeric(
        ce["open_interest"],
        errors="coerce",
    ).fillna(0).sum()

    total_pe_oi = pd.to_numeric(
        pe["open_interest"],
        errors="coerce",
    ).fillna(0).sum()

    total_ce_volume = pd.to_numeric(
        ce["volume"],
        errors="coerce",
    ).fillna(0).sum()

    total_pe_volume = pd.to_numeric(
        pe["volume"],
        errors="coerce",
    ).fillna(0).sum()

    total_ce_oi_change = pd.to_numeric(
        ce["oi_change"],
        errors="coerce",
    ).fillna(0).sum()

    total_pe_oi_change = pd.to_numeric(
        pe["oi_change"],
        errors="coerce",
    ).fillna(0).sum()

    oi_pcr = (
        total_pe_oi / total_ce_oi
        if total_ce_oi > 0
        else None
    )

    volume_pcr = (
        total_pe_volume / total_ce_volume
        if total_ce_volume > 0
        else None
    )

    resistance = None
    support = None

    if not ce.empty:
        valid_ce = ce.copy()
        valid_ce["open_interest"] = pd.to_numeric(
            valid_ce["open_interest"],
            errors="coerce",
        )

        valid_ce = valid_ce.dropna(
            subset=["open_interest"]
        )

        if not valid_ce.empty:
            resistance = float(
                valid_ce.loc[
                    valid_ce["open_interest"].idxmax(),
                    "strike_price",
                ]
            )

    if not pe.empty:
        valid_pe = pe.copy()
        valid_pe["open_interest"] = pd.to_numeric(
            valid_pe["open_interest"],
            errors="coerce",
        )

        valid_pe = valid_pe.dropna(
            subset=["open_interest"]
        )

        if not valid_pe.empty:
            support = float(
                valid_pe.loc[
                    valid_pe["open_interest"].idxmax(),
                    "strike_price",
                ]
            )

    max_pain = calculate_max_pain(
        contracts
    )

    if oi_pcr is None:
        bias = "INSUFFICIENT DATA"
    elif oi_pcr >= 1.20:
        bias = "PUT OI DOMINANT / SUPPORTIVE"
    elif oi_pcr <= 0.80:
        bias = "CALL OI DOMINANT / CAUTIOUS"
    else:
        bias = "BALANCED"

    return pd.DataFrame(
        [
            {
                "underlying": underlying,
                "expiry_date": expiry_date.date().isoformat(),
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "selected_strikes": len(chain),
                "total_call_oi": total_ce_oi,
                "total_put_oi": total_pe_oi,
                "oi_pcr": oi_pcr,
                "total_call_volume": total_ce_volume,
                "total_put_volume": total_pe_volume,
                "volume_pcr": volume_pcr,
                "total_call_oi_change": (
                    total_ce_oi_change
                ),
                "total_put_oi_change": (
                    total_pe_oi_change
                ),
                "maximum_call_oi_resistance": (
                    resistance
                ),
                "maximum_put_oi_support": support,
                "max_pain": max_pain,
                "option_chain_bias": bias,
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            }
        ]
    )


def save_outputs(
    summary: pd.DataFrame,
    chain: pd.DataFrame,
    contracts: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary.to_csv(
        SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    chain.to_csv(
        CHAIN_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    failures.to_csv(
        FAILED_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        EXCEL_OUTPUT,
        engine="openpyxl",
    ) as writer:
        summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        chain.to_excel(
            writer,
            sheet_name="Option Chain",
            index=False,
        )

        contracts.to_excel(
            writer,
            sheet_name="Contract Detail",
            index=False,
        )

        failures.to_excel(
            writer,
            sheet_name="Failed Requests",
            index=False,
        )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "summary": summary.to_dict(
                    orient="records"
                ),
                "chain": chain.to_dict(
                    orient="records"
                ),
                "contracts": contracts.to_dict(
                    orient="records"
                ),
                "failures": failures.to_dict(
                    orient="records"
                ),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def show_results(
    summary: pd.DataFrame,
    chain: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    row = summary.iloc[0]

    print("\nAQSD FYERS OPTION CHAIN ANALYTICS")
    print("=" * 118)
    print(f"Underlying:  {row['underlying']}")
    print(f"Expiry:      {row['expiry_date']}")
    print(f"Spot:        {row['spot_price']}")
    print(f"ATM:         {row['atm_strike']}")
    print(f"OI PCR:      {row['oi_pcr']}")
    print(f"Volume PCR:  {row['volume_pcr']}")
    print(f"Support:     {row['maximum_put_oi_support']}")
    print(f"Resistance:  {row['maximum_call_oi_resistance']}")
    print(f"Max Pain:    {row['max_pain']}")
    print(f"Bias:        {row['option_chain_bias']}")
    print("-" * 118)

    preview_columns = [
        "strike_price",
        "moneyness",
        "ce_ltp",
        "ce_open_interest",
        "ce_oi_change",
        "pe_ltp",
        "pe_open_interest",
        "pe_oi_change",
    ]

    print(
        chain[preview_columns].to_string(
            index=False
        )
    )

    print("=" * 118)
    print(f"Failed requests: {len(failures)}")
    print(f"Summary CSV:     {SUMMARY_CSV}")
    print(f"Chain CSV:       {CHAIN_CSV}")
    print(f"Excel:           {EXCEL_OUTPUT}")
    print(f"JSON:            {JSON_OUTPUT}")
    print(f"Failures:        {FAILED_CSV}")


def show_status() -> None:
    print("\nAQSD FYERS OPTION CHAIN ANALYTICS STATUS")
    print("=" * 78)
    print("Version: 1.0")
    print(
        f"Configuration: "
        f"{'FOUND' if CONFIG_FILE.exists() else 'MISSING'}"
    )
    print(
        f"Options master: "
        f"{'FOUND' if OPTIONS_MASTER.exists() else 'MISSING'}"
    )
    print(f"Output folder: {OUTPUT_DIR}")
    print("Run mode: ONE UNDERLYING / ONE EXPIRY")
    print("Order placement: DISABLED")
    print("AQSD database writes: DISABLED")
    print("Yahoo files modified: NO")
    print("=" * 78)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD FYERS Option Chain Analytics Engine."
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
        help="Underlying such as RELIANCE, NIFTY or BANKNIFTY.",
    )

    parser.add_argument(
        "--expiry",
        default="NEAR",
        help="NEAR, NEXT, FAR or YYYY-MM-DD.",
    )

    parser.add_argument(
        "--strikes",
        type=int,
        default=10,
        help="Strikes on each side of ATM. Default 10.",
    )

    parser.add_argument(
        "--depth-delay",
        type=float,
        default=0.20,
        help="Pause between depth calls. Default 0.20 seconds.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if not args.underlying:
        raise SystemExit(
            "Please provide --underlying, for example:\n"
            "python aqsd_fyers_option_chain_analytics.py "
            "--run --underlying RELIANCE"
        )

    client = create_client()
    underlying = str(
        args.underlying
    ).strip().upper()

    option_master, selected_expiry = load_option_master(
        underlying,
        args.expiry,
    )

    spot = spot_symbol(underlying)

    spot_quotes, spot_failures = fetch_quotes(
        client,
        [spot],
    )

    spot_price = safe_float(
        spot_quotes.get(
            spot,
            {},
        ).get("ltp")
    )

    if spot_price is None:
        raise RuntimeError(
            f"Could not obtain spot price for {spot}."
        )

    selected_options, atm_strike = choose_strikes(
        option_master,
        spot_price,
        max(1, args.strikes),
    )

    option_symbols = selected_options[
        "fyers_symbol"
    ].astype(str).tolist()

    quote_map, quote_failures = fetch_quotes(
        client,
        option_symbols,
    )

    depth_map, depth_failures = fetch_depth(
        client,
        option_symbols,
        max(0.0, args.depth_delay),
    )

    contracts = build_contract_rows(
        selected_options,
        quote_map,
        depth_map,
    )

    chain = pivot_chain(
        contracts,
        spot_price,
        atm_strike,
    )

    summary = build_summary(
        contracts,
        chain,
        underlying,
        selected_expiry,
        spot_price,
        atm_strike,
    )

    failures = pd.DataFrame(
        spot_failures
        + quote_failures
        + depth_failures,
        columns=[
            "stage",
            "symbol",
            "reason",
        ],
    )

    save_outputs(
        summary,
        chain,
        contracts,
        failures,
    )

    show_results(
        summary,
        chain,
        failures,
    )


if __name__ == "__main__":
    main()
