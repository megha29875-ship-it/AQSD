"""
AQSD
Trading Calendar Engine

Module    : trading_calendar.py
Module ID : CORE-005A
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Provides trading-day calculations for AQSD.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from .constants import CONFIG_DIR


class TradingCalendar:
    """
    NSE Trading Calendar
    """

    def __init__(self, calendar_file: str = "nse_calendar_2026.csv") -> None:

        self.calendar_path = CONFIG_DIR / calendar_file

        self.calendar = self._load_calendar()

    def _load_calendar(self) -> pd.DataFrame:

        if not self.calendar_path.exists():

            raise FileNotFoundError(
                f"Trading calendar not found : {self.calendar_path}"
            )

        df = pd.read_csv(
            self.calendar_path,
            parse_dates=["Date"],
        )

        df = df.sort_values("Date").reset_index(drop=True)

        return df

    def is_trading_day(self, date) -> bool:

        date = pd.Timestamp(date).normalize()

        row = self.calendar.loc[
            self.calendar["Date"] == date
        ]

        if row.empty:
            return False

        return bool(row.iloc[0]["Trading"])

    def is_weekend(self, date) -> bool:

        return pd.Timestamp(date).weekday() >= 5

    def is_holiday(self, date) -> bool:

        date = pd.Timestamp(date).normalize()

        row = self.calendar.loc[
            self.calendar["Date"] == date
        ]

        if row.empty:
            return False

        return bool(row.iloc[0]["Holiday"])

    def previous_trading_day(self, date):

        date = pd.Timestamp(date).normalize()

        df = self.calendar[
            (self.calendar["Date"] < date)
            & (self.calendar["Trading"])
        ]

        if df.empty:
            return None

        return df.iloc[-1]["Date"]

    def next_trading_day(self, date):

        date = pd.Timestamp(date).normalize()

        df = self.calendar[
            (self.calendar["Date"] > date)
            & (self.calendar["Trading"])
        ]

        if df.empty:
            return None

        return df.iloc[0]["Date"]

    def trading_days_between(
        self,
        start_date,
        end_date,
    ) -> int:

        start = pd.Timestamp(start_date).normalize()

        end = pd.Timestamp(end_date).normalize()

        df = self.calendar[
            (self.calendar["Date"] >= start)
            & (self.calendar["Date"] <= end)
            & (self.calendar["Trading"])
        ]

        return len(df)