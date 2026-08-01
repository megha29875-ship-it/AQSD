"""
AQSD
NSE Trading Calendar Builder

Module : NTC-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Build a reliable NSE trading calendar for AQSD historical backfill.

The calendar is generated using:

1. Calendar weekdays
2. NSE official trading holidays
3. F&O holiday segment

Output
------
Data/NSE_Trading_Calendar.csv

Columns
-------
trade_date
weekday
is_trading_day
is_weekend
is_nse_holiday
holiday_description
segment
source

Important
---------
This module does NOT use Yahoo data.
It does NOT call FYERS.
It does NOT generate market intelligence.

It only builds the official trading-session calendar used by
AQSD historical backfill and research modules.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
import requests


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "NTC-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DATA_DIR: Final[Path] = BASE_DIR / "Data"
OUTPUT_DIR: Final[Path] = BASE_DIR / "Output"

CALENDAR_FILE: Final[Path] = (
    DATA_DIR
    / "NSE_Trading_Calendar.csv"
)

HOLIDAY_FILE: Final[Path] = (
    DATA_DIR
    / "NSE_FO_Holidays.csv"
)

AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "NSE_Trading_Calendar_Audit.json"
)

NSE_HOME_URL: Final[str] = (
    "https://www.nseindia.com/"
)

NSE_HOLIDAY_URL: Final[str] = (
    "https://www.nseindia.com/api/"
    "holiday-master?type=trading"
)

DEFAULT_START_DATE: Final[date] = date(
    2024,
    1,
    1,
)

DEFAULT_END_DATE: Final[date] = date(
    2027,
    12,
    31,
)

REQUEST_TIMEOUT: Final[int] = 30


# ==========================================================
# HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def ensure_directories() -> None:
    """
    Create AQSD directories when required.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# NSE SESSION
# ==========================================================

def create_nse_session() -> requests.Session:
    """
    Create an NSE-compatible HTTP session.
    """

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "application/json,text/plain,*/*"
            ),
            "Accept-Language": (
                "en-US,en;q=0.9"
            ),
            "Referer": (
                "https://www.nseindia.com/"
            ),
            "Connection": "keep-alive",
        }
    )

    return session


# ==========================================================
# HOLIDAY DOWNLOAD
# ==========================================================

def download_holiday_master() -> dict:
    """
    Download NSE official trading holiday master.
    """

    session = create_nse_session()

    try:
        session.get(
            NSE_HOME_URL,
            timeout=REQUEST_TIMEOUT,
        )

        response = session.get(
            NSE_HOLIDAY_URL,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        payload = response.json()

    except Exception as exc:
        raise RuntimeError(
            "Could not download NSE trading holiday master: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "NSE holiday master returned unexpected data."
        )

    return payload


# ==========================================================
# F&O HOLIDAY EXTRACTION
# ==========================================================

def extract_fo_holidays(
    payload: dict,
) -> pd.DataFrame:
    """
    Extract NSE Futures & Options holidays.
    """

    records = payload.get(
        "FO",
        [],
    )

    if not isinstance(
        records,
        list,
    ):
        raise RuntimeError(
            "NSE holiday master does not contain "
            "a valid FO holiday section."
        )

    rows: list[
        dict[str, object]
    ] = []

    for item in records:
        if not isinstance(
            item,
            dict,
        ):
            continue

        raw_date = str(
            item.get(
                "tradingDate",
                "",
            )
        ).strip()

        if not raw_date:
            continue

        parsed_date = pd.to_datetime(
            raw_date,
            format="%d-%b-%Y",
            errors="coerce",
        )

        if pd.isna(
            parsed_date
        ):
            continue

        rows.append(
            {
                "holiday_date": (
                    parsed_date
                    .date()
                    .isoformat()
                ),
                "weekday": str(
                    item.get(
                        "weekDay",
                        "",
                    )
                ).strip(),
                "description": str(
                    item.get(
                        "description",
                        "",
                    )
                ).strip(),
                "segment": "FO",
                "source": (
                    "NSE HOLIDAY MASTER"
                ),
            }
        )

    frame = pd.DataFrame(
        rows
    )

    if frame.empty:
        raise RuntimeError(
            "No NSE F&O holiday records were extracted."
        )

    frame = (
        frame
        .drop_duplicates(
            subset=[
                "holiday_date"
            ],
            keep="last",
        )
        .sort_values(
            "holiday_date"
        )
        .reset_index(
            drop=True
        )
    )

    return frame


# ==========================================================
# CALENDAR BUILDER
# ==========================================================

def build_trading_calendar(
    *,
    start_date: date,
    end_date: date,
    holidays: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the complete calendar and mark NSE trading sessions.
    """

    if end_date < start_date:
        raise ValueError(
            "End date cannot be before start date."
        )

    holiday_lookup: dict[
        str,
        str,
    ] = {}

    for _, row in holidays.iterrows():
        holiday_lookup[
            str(
                row[
                    "holiday_date"
                ]
            )
        ] = str(
            row.get(
                "description",
                "",
            )
        )

    rows: list[
        dict[str, object]
    ] = []

    current = start_date

    while current <= end_date:
        date_text = (
            current.isoformat()
        )

        weekday_number = (
            current.weekday()
        )

        is_weekend = (
            weekday_number >= 5
        )

        holiday_description = (
            holiday_lookup.get(
                date_text,
                "",
            )
        )

        is_nse_holiday = bool(
            holiday_description
        )

        is_trading_day = (
            not is_weekend
            and not is_nse_holiday
        )

        rows.append(
            {
                "trade_date": (
                    date_text
                ),
                "weekday": (
                    current.strftime(
                        "%A"
                    )
                ),
                "is_trading_day": (
                    is_trading_day
                ),
                "is_weekend": (
                    is_weekend
                ),
                "is_nse_holiday": (
                    is_nse_holiday
                ),
                "holiday_description": (
                    holiday_description
                ),
                "segment": "FO",
                "source": (
                    "NSE HOLIDAY MASTER"
                ),
            }
        )

        current += timedelta(
            days=1
        )

    return pd.DataFrame(
        rows
    )


# ==========================================================
# SAVE OUTPUTS
# ==========================================================

def save_outputs(
    *,
    calendar: pd.DataFrame,
    holidays: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> None:
    """
    Save calendar, holiday master and audit.
    """

    ensure_directories()

    holidays.to_csv(
        HOLIDAY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    trading_days = calendar.loc[
        calendar[
            "is_trading_day"
        ]
        == True
    ].copy()

    trading_days[
        [
            "trade_date",
            "weekday",
            "is_trading_day",
            "is_weekend",
            "is_nse_holiday",
            "holiday_description",
            "segment",
            "source",
        ]
    ].to_csv(
        CALENDAR_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    audit = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),
        "generated_at": (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        ),
        "start_date": (
            start_date.isoformat()
        ),
        "end_date": (
            end_date.isoformat()
        ),
        "holiday_records": int(
            len(
                holidays
            )
        ),
        "trading_sessions": int(
            len(
                trading_days
            )
        ),
        "calendar_file": str(
            CALENDAR_FILE
        ),
        "holiday_file": str(
            HOLIDAY_FILE
        ),
        "source": (
            NSE_HOLIDAY_URL
        ),
        "status": "SUCCESS",
    }

    AUDIT_FILE.write_text(
        json.dumps(
            audit,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================================
# ENGINE
# ==========================================================

def run_builder(
    *,
    start_date: date,
    end_date: date,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Run complete NSE Trading Calendar Builder.
    """

    payload = (
        download_holiday_master()
    )

    holidays = (
        extract_fo_holidays(
            payload
        )
    )

    calendar = (
        build_trading_calendar(
            start_date=start_date,
            end_date=end_date,
            holidays=holidays,
        )
    )

    save_outputs(
        calendar=calendar,
        holidays=holidays,
        start_date=start_date,
        end_date=end_date,
    )

    return (
        calendar,
        holidays,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_summary(
    *,
    calendar: pd.DataFrame,
    holidays: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> None:
    """
    Display concise builder summary.
    """

    trading_sessions = (
        calendar[
            "is_trading_day"
        ]
        .astype(bool)
        .sum()
    )

    print()
    print("=" * 100)
    print(
        "AQSD NSE TRADING CALENDAR BUILDER"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Start Date                : "
        f"{start_date}"
    )

    print(
        f"End Date                  : "
        f"{end_date}"
    )

    print(
        f"NSE F&O Holidays          : "
        f"{len(holidays)}"
    )

    print(
        f"Trading Sessions          : "
        f"{trading_sessions}"
    )

    print("-" * 100)

    print(
        f"Calendar CSV              : "
        f"{CALENDAR_FILE}"
    )

    print(
        f"Holiday CSV               : "
        f"{HOLIDAY_FILE}"
    )

    print(
        f"Audit JSON                : "
        f"{AUDIT_FILE}"
    )

    print("-" * 100)

    print(
        "Source                    : "
        "NSE Official Trading Holiday Master"
    )

    print(
        "Segment                   : "
        "FUTURES & OPTIONS (FO)"
    )

    print(
        "Status                    : "
        "SUCCESS"
    )

    print("=" * 100)


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    """
    Display current calendar status.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE TRADING CALENDAR STATUS"
    )
    print("=" * 100)

    print(
        f"Calendar File             : "
        f"{CALENDAR_FILE}"
    )

    print(
        f"Calendar Exists           : "
        f"{'YES' if CALENDAR_FILE.exists() else 'NO'}"
    )

    print(
        f"Holiday File              : "
        f"{HOLIDAY_FILE}"
    )

    print(
        f"Holiday File Exists       : "
        f"{'YES' if HOLIDAY_FILE.exists() else 'NO'}"
    )

    if CALENDAR_FILE.exists():
        try:
            frame = pd.read_csv(
                CALENDAR_FILE,
                low_memory=False,
            )

            print(
                f"Trading Sessions Stored   : "
                f"{len(frame)}"
            )

            if (
                not frame.empty
                and "trade_date"
                in frame.columns
            ):
                print(
                    f"First Trading Date        : "
                    f"{frame['trade_date'].iloc[0]}"
                )

                print(
                    f"Last Trading Date         : "
                    f"{frame['trade_date'].iloc[-1]}"
                )

        except Exception as exc:
            print(
                f"Calendar Read Error       : "
                f"{exc}"
            )

    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Build AQSD NSE F&O Trading Calendar."
        )
    )

    parser.add_argument(
        "--start-date",
        required=False,
        help=(
            "Calendar start date YYYY-MM-DD. "
            "Default 2024-01-01."
        ),
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Calendar end date YYYY-MM-DD. "
            "Default 2027-12-31."
        ),
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Show current calendar status."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = (
        parse_arguments()
    )

    if arguments.status:
        show_status()
        return

    start_date = (
        parse_date(
            arguments.start_date
        )
        if arguments.start_date
        else DEFAULT_START_DATE
    )

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else DEFAULT_END_DATE
    )

    try:
        (
            calendar,
            holidays,
        ) = run_builder(
            start_date=start_date,
            end_date=end_date,
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print(
            "AQSD NSE TRADING CALENDAR BUILDER"
        )
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 100)

        raise SystemExit(
            1
        ) from exc

    display_summary(
        calendar=calendar,
        holidays=holidays,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    main()