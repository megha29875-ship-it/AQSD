"""
AQSD
ID Generator

Module    : id_generator.py
Module ID : DB-001D
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Generates unique AQSD IDs for every trading session.
"""

from __future__ import annotations

import pandas as pd


class AQSDIDGenerator:
    """
    Generate AQSD IDs.
    """

    def __init__(
        self,
        prefix: str = "AQSD",
        date_column: str = "Date",
    ) -> None:

        self.prefix = prefix
        self.date_column = date_column

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add AQSD_ID column.
        """

        df = dataframe.copy()

        df[self.date_column] = pd.to_datetime(
            df[self.date_column]
        )

        df = df.sort_values(
            self.date_column
        ).reset_index(drop=True)

        df.insert(
            0,
            "AQSD_ID",
            [
                self._create_id(index + 1, date)
                for index, date in enumerate(df[self.date_column])
            ],
        )

        return df

    def _create_id(
        self,
        sequence: int,
        trade_date: pd.Timestamp,
    ) -> str:
        """
        Create AQSD ID.

        Example:
        AQSD-20260727-000663
        """

        date_part = trade_date.strftime("%Y%m%d")

        sequence_part = f"{sequence:06d}"

        return (
            f"{self.prefix}-"
            f"{date_part}-"
            f"{sequence_part}"
        )