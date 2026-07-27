"""
AQSD
Database Validator

Module    : validator.py
Module ID : DB-001C
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Runs all validations on the participant workbook.
"""

from __future__ import annotations

import pandas as pd

from aqsd_core.trading_calendar import TradingCalendar
from aqsd_core.validation import (
    merge_results,
    validate_date_column,
    validate_duplicate_dates,
    validate_missing_values,
    validate_not_empty,
    validate_numeric_columns,
    validate_required_columns,
)


class DatabaseValidator:
    """
    AQSD Database Validator
    """

    def __init__(
        self,
        required_columns: list[str],
        numeric_columns: list[str],
        date_column: str = "Date",
    ) -> None:

        self.required_columns = required_columns
        self.numeric_columns = numeric_columns
        self.date_column = date_column

        self.calendar = TradingCalendar()

    def validate(
        self,
        dataframe: pd.DataFrame,
    ):

        results = []

        # Empty workbook
        results.append(
            validate_not_empty(dataframe)
        )

        # Required columns
        results.append(
            validate_required_columns(
                dataframe,
                self.required_columns,
            )
        )

        # Date format
        results.append(
            validate_date_column(
                dataframe,
                self.date_column,
            )
        )

        # Duplicate dates
        results.append(
            validate_duplicate_dates(
                dataframe,
                self.date_column,
            )
        )

        # Missing values
        results.append(
            validate_missing_values(
                dataframe,
            )
        )

        # Numeric validation
        results.append(
            validate_numeric_columns(
                dataframe,
                self.numeric_columns,
            )
        )

        # Trading calendar validation
        calendar_result = self.validate_calendar(
            dataframe
        )

        results.append(calendar_result)

        return merge_results(*results)

    def validate_calendar(
        self,
        dataframe: pd.DataFrame,
    ):

        from aqsd_core.validation import ValidationResult

        result = ValidationResult(
            records_checked=len(dataframe)
        )

        for value in dataframe[self.date_column]:

            date = pd.Timestamp(value)

            if self.calendar.is_weekend(date):

                result.add_error(
                    f"DB008 : Weekend -> {date.date()}"
                )

            if self.calendar.is_holiday(date):

                result.add_error(
                    f"DB009 : NSE Holiday -> {date.date()}"
                )

            if not self.calendar.is_trading_day(date):

                result.add_warning(
                    f"Not a trading session -> {date.date()}"
                )

        return result