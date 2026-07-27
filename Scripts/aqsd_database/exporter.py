"""
AQSD
Database Exporter

Module    : exporter.py
Module ID : DB-001E
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Exports AQSD datasets to Excel, CSV and JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aqsd_core.logger import get_logger

logger = get_logger(__name__)


class DatabaseExporter:

    def __init__(
        self,
        output_folder: Path,
    ) -> None:

        self.output_folder = output_folder

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    def export_excel(
        self,
        dataframe: pd.DataFrame,
        filename: str,
    ) -> Path:

        file_path = self.output_folder / filename

        dataframe.to_excel(
            file_path,
            index=False,
            engine="openpyxl",
        )

        logger.info(
            "Excel exported : %s",
            file_path,
        )

        return file_path

    def export_csv(
        self,
        dataframe: pd.DataFrame,
        filename: str,
    ) -> Path:

        file_path = self.output_folder / filename

        dataframe.to_csv(
            file_path,
            index=False,
        )

        logger.info(
            "CSV exported : %s",
            file_path,
        )

        return file_path

    def export_json(
        self,
        data: dict,
        filename: str,
    ) -> Path:

        file_path = self.output_folder / filename

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                default=str,
            )

        logger.info(
            "JSON exported : %s",
            file_path,
        )

        return file_path