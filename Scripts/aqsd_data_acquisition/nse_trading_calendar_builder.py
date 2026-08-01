"""
AQSD
NSE Trading Calendar Builder

Module : NTC-001
Version: 1.1.0
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
MODULE_VERSION: Final[str] = "1.1.0"

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

DEFAULT_END_DATE: Final[date] = date.today()

REQUEST_TIMEOUT: Final[int] = 30


# ==========================================================
# VERIFIED NSE F&O HISTORICAL HOLIDAY ARCHIVE
# ==========================================================
#
# Purpose
# -------
# NSE's live holiday-master endpoint is primarily intended for
# current exchange holiday publication. Historical backfills must
# not assume that the live API contains every prior calendar year.
#
# These records are transcribed from official NSE F&O circulars
# and are used as a deterministic historical archive.
#
# Official NSE F&O circulars:
# 2024 : NSE/FAOP/59723
# 2025 : NSE/FAOP/65588
# 2026 : NSE/FAOP/71777
#
# Special Muhurat sessions are listed separately because those
# dates are exchange holidays for the normal session but still
# contain a special trading session and may have market data.
# ==========================================================

VERIFIED_FO_HOLIDAYS: Final[
    dict[int, tuple[tuple[str, str], ...]]
] = {
    2024: (
        ("2024-01-26", "Republic Day"),
        ("2024-03-08", "Mahashivratri"),
        ("2024-03-25", "Holi"),
        ("2024-03-29", "Good Friday"),
        ("2024-04-11", "Id-Ul-Fitr (Ramadan Eid)"),
        ("2024-04-17", "Shri Ram Navmi"),
        ("2024-05-01", "Maharashtra Day"),
        ("2024-06-17", "Bakri Id"),
        ("2024-07-17", "Moharram"),
        (
            "2024-08-15",
            "Independence Day/Parsi New Year",
        ),
        ("2024-10-02", "Mahatma Gandhi Jayanti"),
        ("2024-11-01", "Diwali Laxmi Pujan"),
        ("2024-11-15", "Gurunanak Jayanti"),
        ("2024-12-25", "Christmas"),
    ),
    2025: (
        ("2025-02-26", "Mahashivratri"),
        ("2025-03-14", "Holi"),
        ("2025-03-31", "Id-Ul-Fitr (Ramadan Eid)"),
        ("2025-04-10", "Shri Mahavir Jayanti"),
        (
            "2025-04-14",
            "Dr. Baba Saheb Ambedkar Jayanti",
        ),
        ("2025-04-18", "Good Friday"),
        ("2025-05-01", "Maharashtra Day"),
        ("2025-08-15", "Independence Day"),
        ("2025-08-27", "Ganesh Chaturthi"),
        (
            "2025-10-02",
            "Mahatma Gandhi Jayanti/Dussehra",
        ),
        ("2025-10-21", "Diwali Laxmi Pujan"),
        ("2025-10-22", "Diwali-Balipratipada"),
        (
            "2025-11-05",
            "Prakash Gurpurb Sri Guru Nanak Dev",
        ),
        ("2025-12-25", "Christmas"),
    ),
    2026: (
        ("2026-01-26", "Republic Day"),
        ("2026-03-03", "Holi"),
        ("2026-03-26", "Shri Ram Navami"),
        ("2026-03-31", "Shri Mahavir Jayanti"),
        ("2026-04-03", "Good Friday"),
        (
            "2026-04-14",
            "Dr. Baba Saheb Ambedkar Jayanti",
        ),
        ("2026-05-01", "Maharashtra Day"),
        ("2026-05-28", "Bakri Id"),
        ("2026-06-26", "Muharram"),
        ("2026-09-14", "Ganesh Chaturthi"),
        ("2026-10-02", "Mahatma Gandhi Jayanti"),
        ("2026-10-20", "Dussehra"),
        ("2026-11-10", "Diwali-Balipratipada"),
        (
            "2026-11-24",
            "Prakash Gurpurb Sri Guru Nanak Dev",
        ),
        ("2026-12-25", "Christmas"),
    ),
}


SPECIAL_TRADING_SESSIONS: Final[
    dict[str, str]
] = {
    "2024-11-01": "Muhurat Trading",
    "2025-10-21": "Muhurat Trading",
    "2026-11-08": "Muhurat Trading",
}


VERIFIED_CIRCULAR_BY_YEAR: Final[
    dict[int, str]
] = {
    2024: "NSE/FAOP/59723",
    2025: "NSE/FAOP/65588",
    2026: "NSE/FAOP/71777",
}


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
# HISTORICAL HOLIDAY ARCHIVE / VALIDATION
# ==========================================================

def verified_historical_holidays() -> pd.DataFrame:
    """
    Return deterministic NSE F&O holiday records transcribed
    from official NSE F&O circulars.
    """

    rows: list[dict[str, object]] = []

    for year, records in VERIFIED_FO_HOLIDAYS.items():

        circular = VERIFIED_CIRCULAR_BY_YEAR.get(
            year,
            "NSE OFFICIAL F&O CIRCULAR",
        )

        for holiday_date, description in records:

            parsed = datetime.strptime(
                holiday_date,
                "%Y-%m-%d",
            ).date()

            rows.append(
                {
                    "holiday_date": holiday_date,
                    "weekday": parsed.strftime("%A"),
                    "description": description,
                    "segment": "FO",
                    "source": (
                        "NSE VERIFIED F&O CIRCULAR "
                        f"{circular}"
                    ),
                }
            )

    return pd.DataFrame(rows)


def merge_holiday_sources(
    *,
    live_holidays: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge live NSE holiday-master records with AQSD's verified
    NSE historical circular archive.

    Duplicate dates are resolved in favour of the verified
    circular archive to keep historical backfills deterministic.
    """

    verified = verified_historical_holidays()

    combined = pd.concat(
        [
            live_holidays,
            verified,
        ],
        ignore_index=True,
    )

    combined["holiday_date"] = (
        combined["holiday_date"]
        .astype(str)
        .str.strip()
    )

    combined = (
        combined
        .drop_duplicates(
            subset=["holiday_date"],
            keep="last",
        )
        .sort_values("holiday_date")
        .reset_index(drop=True)
    )

    return combined


def validate_year_coverage(
    *,
    start_date: date,
    end_date: date,
    holidays: pd.DataFrame,
) -> None:
    """
    Fail closed when AQSD lacks an official holiday source for a
    historical calendar year.

    Future years are also rejected unless the live NSE holiday
    master already contains records for that year.
    """

    required_years = set(
        range(
            start_date.year,
            end_date.year + 1,
        )
    )

    available_years: set[int] = set()

    for value in holidays["holiday_date"].astype(str):

        try:
            available_years.add(
                datetime.strptime(
                    value,
                    "%Y-%m-%d",
                ).year
            )
        except ValueError:
            continue

    missing_years = sorted(
        required_years
        - available_years
    )

    if missing_years:
        raise RuntimeError(
            "NSE F&O holiday coverage is unavailable for "
            "calendar year(s): "
            + ", ".join(
                str(year)
                for year in missing_years
            )
            + ". AQSD will not fabricate trading sessions."
        )


def validate_calendar_output(
    *,
    calendar: pd.DataFrame,
    holidays: pd.DataFrame,
) -> None:
    """
    Validate the generated trading calendar before saving it.
    """

    if calendar.empty:
        raise RuntimeError(
            "Generated NSE trading calendar is empty."
        )

    required_columns = {
        "trade_date",
        "is_trading_day",
        "is_weekend",
        "is_nse_holiday",
    }

    missing_columns = (
        required_columns
        - set(calendar.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "Generated trading calendar is missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    duplicate_dates = (
        calendar["trade_date"]
        .astype(str)
        .duplicated()
        .any()
    )

    if duplicate_dates:
        raise RuntimeError(
            "Generated trading calendar contains duplicate dates."
        )

    # Official holidays must not be normal trading sessions,
    # except an explicitly declared special trading session.
    holiday_dates = set(
        holidays["holiday_date"]
        .astype(str)
    )

    for holiday_date in holiday_dates:

        if holiday_date in SPECIAL_TRADING_SESSIONS:
            continue

        row = calendar.loc[
            calendar["trade_date"]
            .astype(str)
            .eq(holiday_date)
        ]

        if row.empty:
            continue

        if bool(
            row.iloc[0]["is_trading_day"]
        ):
            raise RuntimeError(
                "Holiday validation failed for "
                f"{holiday_date}."
            )


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
    Build the complete calendar and mark NSE F&O trading sessions.

    Rules
    -----
    1. Monday-Friday are potential normal sessions.
    2. Official NSE F&O holidays are excluded.
    3. Explicit special sessions (for example Muhurat Trading)
       override weekend/holiday closure.
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

        date_text = current.isoformat()

        weekday_number = current.weekday()

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

        special_session_description = (
            SPECIAL_TRADING_SESSIONS.get(
                date_text,
                "",
            )
        )

        is_special_session = bool(
            special_session_description
        )

        if is_special_session:
            is_trading_day = True
            session_type = "SPECIAL"
        else:
            is_trading_day = (
                not is_weekend
                and not is_nse_holiday
            )
            session_type = (
                "NORMAL"
                if is_trading_day
                else "CLOSED"
            )

        rows.append(
            {
                "trade_date": date_text,
                "weekday": current.strftime(
                    "%A"
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
                "is_special_session": (
                    is_special_session
                ),
                "special_session_description": (
                    special_session_description
                ),
                "session_type": (
                    session_type
                ),
                "segment": "FO",
                "source": (
                    "NSE OFFICIAL F&O HOLIDAY SOURCES"
                ),
            }
        )

        current += timedelta(
            days=1
        )

    frame = pd.DataFrame(rows)

    validate_calendar_output(
        calendar=frame,
        holidays=holidays,
    )

    return frame


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
            "is_special_session",
            "special_session_description",
            "session_type",
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

    live_holidays = (
        extract_fo_holidays(
            payload
        )
    )

    holidays = merge_holiday_sources(
        live_holidays=live_holidays,
    )

    validate_year_coverage(
        start_date=start_date,
        end_date=end_date,
        holidays=holidays,
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
            "Default is today."
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