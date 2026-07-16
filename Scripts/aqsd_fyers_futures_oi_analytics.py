"""
AQSD Professional
Module: FYERS Futures OI Analytics Engine
Version: 1.0

Purpose
-------
Calculates contract-wise and underlying-wise futures open-interest analytics
for NEAR, NEXT and FAR contracts.

Inputs
------
Data/FYERS_Futures_Near_Next_Far.csv
Data/fyers_config.env

Outputs
-------
Output/AQSD_FYERS_Futures_OI_Contracts.csv
Output/AQSD_FYERS_Futures_OI_Analytics.csv
Output/AQSD_FYERS_Futures_OI_Analytics.xlsx
Output/AQSD_FYERS_Futures_OI_Analytics.json
Output/AQSD_FYERS_Futures_OI_Failed.csv

Key calculations
----------------
- Current OI
- Previous-day OI
- Change in OI
- OI change %
- Near / Next / Far OI
- Total OI
- OI share by expiry
- Rollover share
- Futures cycle:
    LONG BUILDUP
    SHORT BUILDUP
    SHORT COVERING
    LONG UNWINDING
- OI migration
- Near-Next and Next-Far spreads
- Contango / Backwardation / Mixed Curve
- Contract value
- OI exposure = OI * lot size * futures price

Safety
------
- No order placement
- No AQSD database writes
- Yahoo files untouched

Examples
--------
python aqsd_fyers_futures_oi_analytics.py --status
python aqsd_fyers_futures_oi_analytics.py --run --underlying RELIANCE
python aqsd_fyers_futures_oi_analytics.py --run --limit 10
python aqsd_fyers_futures_oi_analytics.py --run

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
FUTURES_MASTER = DATA_DIR / "FYERS_Futures_Near_Next_Far.csv"

CONTRACT_OUTPUT = (
    OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Contracts.csv"
)
UNDERLYING_OUTPUT = (
    OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.csv"
)
EXCEL_OUTPUT = (
    OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.xlsx"
)
JSON_OUTPUT = (
    OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Analytics.json"
)
FAILED_OUTPUT = (
    OUTPUT_DIR / "AQSD_FYERS_Futures_OI_Failed.csv"
)


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
            "Run aqsd_fyers_symbol_master_updater_v3.py --build first."
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
            ["lot_size"],
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
            "Futures master missing required columns: "
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
        target = str(
            underlying_filter
        ).strip().upper()

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


def fetch_contract_depth(
    client: fyersModel.FyersModel,
    master: pd.DataFrame,
    delay_seconds: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    total = len(master)

    for index, contract in master.iterrows():
        symbol = str(contract["fyers_symbol"])

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

            payload = extract_depth_payload(
                response,
                symbol,
            )

            current_oi = safe_float(
                payload.get("oi")
            )
            previous_day_oi = safe_float(
                payload.get("pdoi")
            )
            oi_change_percent = safe_float(
                payload.get("oipercent")
            )

            oi_change = None

            if (
                current_oi is not None
                and previous_day_oi is not None
            ):
                oi_change = (
                    current_oi - previous_day_oi
                )

            future_price = safe_float(
                payload.get("ltp")
            )
            price_change = safe_float(
                payload.get("ch")
            )
            price_change_percent = safe_float(
                payload.get("chp")
            )
            volume = safe_float(
                payload.get("v")
            )
            average_trade_price = safe_float(
                payload.get("atp")
            )

            lot_size = safe_float(
                contract["lot_size"]
            )

            contract_value = None
            oi_exposure = None

            if (
                future_price is not None
                and lot_size is not None
            ):
                contract_value = (
                    future_price * lot_size
                )

                if current_oi is not None:
                    oi_exposure = (
                        current_oi
                        * lot_size
                        * future_price
                    )

            rows.append(
                {
                    "underlying": contract["underlying"],
                    "expiry_bucket": contract["expiry_bucket"],
                    "expiry_date": (
                        contract["expiry_date"].date().isoformat()
                        if not pd.isna(
                            contract["expiry_date"]
                        )
                        else ""
                    ),
                    "days_to_expiry": safe_float(
                        contract["days_to_expiry"]
                    ),
                    "fyers_symbol": symbol,
                    "future_price": future_price,
                    "price_change": price_change,
                    "price_change_percent": (
                        price_change_percent
                    ),
                    "volume": volume,
                    "average_trade_price": (
                        average_trade_price
                    ),
                    "open_interest": current_oi,
                    "previous_day_open_interest": (
                        previous_day_oi
                    ),
                    "oi_change": oi_change,
                    "oi_change_percent": (
                        oi_change_percent
                    ),
                    "lot_size": lot_size,
                    "tick_size": safe_float(
                        contract["tick_size"]
                    ),
                    "contract_value": contract_value,
                    "oi_exposure": oi_exposure,
                    "futures_cycle": classify_cycle(
                        price_change_percent,
                        oi_change,
                    ),
                    "fetched_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

        except Exception as error:
            failures.append(
                {
                    "underlying": str(
                        contract["underlying"]
                    ),
                    "expiry_bucket": str(
                        contract["expiry_bucket"]
                    ),
                    "fyers_symbol": symbol,
                    "reason": str(error),
                }
            )

        completed = index + 1

        if completed % 25 == 0 or completed == total:
            print(
                f"Depth completed: {completed}/{total}"
            )

        if delay_seconds > 0 and completed < total:
            time.sleep(delay_seconds)

    contract_frame = pd.DataFrame(rows)
    failed_frame = pd.DataFrame(
        failures,
        columns=[
            "underlying",
            "expiry_bucket",
            "fyers_symbol",
            "reason",
        ],
    )

    return contract_frame, failed_frame


def classify_cycle(
    price_change_percent: float | None,
    oi_change: float | None,
) -> str:
    if (
        price_change_percent is None
        or oi_change is None
    ):
        return "INSUFFICIENT DATA"

    if price_change_percent > 0 and oi_change > 0:
        return "LONG BUILDUP"

    if price_change_percent < 0 and oi_change > 0:
        return "SHORT BUILDUP"

    if price_change_percent > 0 and oi_change < 0:
        return "SHORT COVERING"

    if price_change_percent < 0 and oi_change < 0:
        return "LONG UNWINDING"

    return "NEUTRAL"


def bucket_value(
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
    near_price: float | None,
    next_price: float | None,
    far_price: float | None,
) -> str:
    if (
        near_price is not None
        and next_price is not None
        and far_price is not None
    ):
        if far_price > next_price > near_price:
            return "CONTANGO"

        if far_price < next_price < near_price:
            return "BACKWARDATION"

        return "MIXED CURVE"

    available = [
        value
        for value in [
            near_price,
            next_price,
            far_price,
        ]
        if value is not None
    ]

    if len(available) < 2:
        return "INSUFFICIENT DATA"

    if available[1] > available[0]:
        return "CONTANGO"

    if available[1] < available[0]:
        return "BACKWARDATION"

    return "FLAT CURVE"


def classify_oi_migration(
    near_change: float | None,
    next_change: float | None,
    far_change: float | None,
) -> str:
    near_change = near_change or 0.0
    next_change = next_change or 0.0
    far_change = far_change or 0.0

    if near_change < 0 and next_change > 0 and far_change > 0:
        return "ROLLOVER TO NEXT AND FAR"

    if near_change < 0 and next_change > 0:
        return "ROLLOVER TO NEXT"

    if near_change < 0 and far_change > 0:
        return "ROLLOVER TO FAR"

    if near_change > 0 and next_change > 0 and far_change > 0:
        return "OI BUILDUP ACROSS CURVE"

    if near_change > 0 and next_change <= 0 and far_change <= 0:
        return "OI CONCENTRATED IN NEAR"

    if near_change < 0 and next_change < 0 and far_change < 0:
        return "OI REDUCTION ACROSS CURVE"

    if next_change > 0 and far_change > 0:
        return "FORWARD OI BUILDUP"

    return "MIXED OI MIGRATION"


def classify_rollover(
    near_cycle: str,
    next_cycle: str,
    far_cycle: str,
    migration: str,
) -> str:
    if (
        near_cycle in {
            "SHORT COVERING",
            "LONG UNWINDING",
        }
        and next_cycle == "LONG BUILDUP"
    ):
        return "BULLISH ROLLOVER"

    if (
        near_cycle in {
            "LONG UNWINDING",
            "SHORT COVERING",
        }
        and next_cycle == "SHORT BUILDUP"
    ):
        return "BEARISH ROLLOVER"

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

    if (
        far_cycle == "LONG BUILDUP"
        and "FAR" in migration
    ):
        return "LONG-TERM BULLISH POSITIONING"

    if (
        far_cycle == "SHORT BUILDUP"
        and "FAR" in migration
    ):
        return "LONG-TERM BEARISH POSITIONING"

    return "MIXED / NO CLEAR ROLLOVER"


def build_underlying_analytics(
    contracts: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for underlying, group in contracts.groupby(
        "underlying"
    ):
        near_price = safe_float(
            bucket_value(
                group,
                "NEAR",
                "future_price",
            )
        )
        next_price = safe_float(
            bucket_value(
                group,
                "NEXT",
                "future_price",
            )
        )
        far_price = safe_float(
            bucket_value(
                group,
                "FAR",
                "future_price",
            )
        )

        near_oi = safe_float(
            bucket_value(
                group,
                "NEAR",
                "open_interest",
            )
        ) or 0.0
        next_oi = safe_float(
            bucket_value(
                group,
                "NEXT",
                "open_interest",
            )
        ) or 0.0
        far_oi = safe_float(
            bucket_value(
                group,
                "FAR",
                "open_interest",
            )
        ) or 0.0

        near_oi_change = safe_float(
            bucket_value(
                group,
                "NEAR",
                "oi_change",
            )
        )
        next_oi_change = safe_float(
            bucket_value(
                group,
                "NEXT",
                "oi_change",
            )
        )
        far_oi_change = safe_float(
            bucket_value(
                group,
                "FAR",
                "oi_change",
            )
        )

        total_oi = (
            near_oi
            + next_oi
            + far_oi
        )

        total_oi_change = sum(
            value or 0.0
            for value in [
                near_oi_change,
                next_oi_change,
                far_oi_change,
            ]
        )

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
            (next_oi + far_oi)
            / total_oi
            * 100
            if total_oi > 0
            else None
        )

        near_exposure = safe_float(
            bucket_value(
                group,
                "NEAR",
                "oi_exposure",
            )
        ) or 0.0
        next_exposure = safe_float(
            bucket_value(
                group,
                "NEXT",
                "oi_exposure",
            )
        ) or 0.0
        far_exposure = safe_float(
            bucket_value(
                group,
                "FAR",
                "oi_exposure",
            )
        ) or 0.0

        total_exposure = (
            near_exposure
            + next_exposure
            + far_exposure
        )

        near_cycle = str(
            bucket_value(
                group,
                "NEAR",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )
        next_cycle = str(
            bucket_value(
                group,
                "NEXT",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )
        far_cycle = str(
            bucket_value(
                group,
                "FAR",
                "futures_cycle",
            )
            or "INSUFFICIENT DATA"
        )

        migration = classify_oi_migration(
            near_oi_change,
            next_oi_change,
            far_oi_change,
        )

        rollover_signal = classify_rollover(
            near_cycle,
            next_cycle,
            far_cycle,
            migration,
        )

        rows.append(
            {
                "underlying": underlying,
                "near_symbol": bucket_value(
                    group,
                    "NEAR",
                    "fyers_symbol",
                ),
                "next_symbol": bucket_value(
                    group,
                    "NEXT",
                    "fyers_symbol",
                ),
                "far_symbol": bucket_value(
                    group,
                    "FAR",
                    "fyers_symbol",
                ),
                "near_expiry": bucket_value(
                    group,
                    "NEAR",
                    "expiry_date",
                ),
                "next_expiry": bucket_value(
                    group,
                    "NEXT",
                    "expiry_date",
                ),
                "far_expiry": bucket_value(
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
                "near_open_interest": near_oi,
                "next_open_interest": next_oi,
                "far_open_interest": far_oi,
                "total_open_interest": total_oi,
                "near_oi_change": near_oi_change,
                "next_oi_change": next_oi_change,
                "far_oi_change": far_oi_change,
                "total_oi_change": total_oi_change,
                "near_oi_share_percent": near_share,
                "next_oi_share_percent": next_share,
                "far_oi_share_percent": far_share,
                "rollover_share_percent": rollover_share,
                "near_cycle": near_cycle,
                "next_cycle": next_cycle,
                "far_cycle": far_cycle,
                "oi_migration": migration,
                "rollover_signal": rollover_signal,
                "near_oi_exposure": near_exposure,
                "next_oi_exposure": next_exposure,
                "far_oi_exposure": far_exposure,
                "total_oi_exposure": total_exposure,
                "lot_size": bucket_value(
                    group,
                    "NEAR",
                    "lot_size",
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
                "total_oi_exposure",
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
    contracts: pd.DataFrame,
    underlyings: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    contracts.to_csv(
        CONTRACT_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    underlyings.to_csv(
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
        underlyings.to_excel(
            writer,
            sheet_name="OI Analytics",
            index=False,
        )

        contracts.to_excel(
            writer,
            sheet_name="Contract OI",
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
                    "underlyings": len(underlyings),
                    "contracts": len(contracts),
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
                "underlying_rows": underlyings.to_dict(
                    orient="records"
                ),
                "contract_rows": contracts.to_dict(
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


def show_preview(
    underlyings: pd.DataFrame,
    contracts: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    print("\nAQSD FYERS FUTURES OI ANALYTICS")
    print("=" * 130)

    if underlyings.empty:
        print("No analytics rows created.")
    else:
        columns = [
            "rank",
            "underlying",
            "near_open_interest",
            "next_open_interest",
            "far_open_interest",
            "total_open_interest",
            "total_oi_change",
            "rollover_share_percent",
            "term_structure",
            "oi_migration",
            "rollover_signal",
        ]

        print(
            underlyings[columns]
            .head(30)
            .to_string(index=False)
        )

    print("=" * 130)
    print(f"Underlyings:      {len(underlyings)}")
    print(f"Contracts:        {len(contracts)}")
    print(f"Failed requests:  {len(failures)}")
    print(f"Underlying CSV:   {UNDERLYING_OUTPUT}")
    print(f"Contract CSV:     {CONTRACT_OUTPUT}")
    print(f"Excel:            {EXCEL_OUTPUT}")
    print(f"JSON:             {JSON_OUTPUT}")
    print(f"Failures:         {FAILED_OUTPUT}")


def show_status() -> None:
    print("\nAQSD FYERS FUTURES OI ANALYTICS STATUS")
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
        description="AQSD FYERS Futures OI Analytics Engine."
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
        "--depth-delay",
        type=float,
        default=0.20,
        help="Pause between FYERS depth requests.",
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
            "No NEAR/NEXT/FAR futures contracts matched."
        )

    client = create_client()

    contracts, failures = fetch_contract_depth(
        client,
        master,
        max(0.0, args.depth_delay),
    )

    underlyings = build_underlying_analytics(
        contracts
    )

    save_outputs(
        contracts,
        underlyings,
        failures,
    )

    show_preview(
        underlyings,
        contracts,
        failures,
    )


if __name__ == "__main__":
    main()
