"""
AQSD
Workbook Reader

Module    : reader.py
Module ID : DB-001B
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Reads and validates the source participant workbook.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aqsd_core.logger import get_logger
from aqsd_database.models import WorkbookInfo

logger = get_logger(__name__)


def read_workbook(
    file_path: Path,
    sheet_name: str = 0,
) -> tuple[pd.DataFrame, WorkbookInfo]:
    """
    Read Excel workbook.

    Parameters
    ----------
    file_path : Path
        Workbook path.

    sheet_name : str | int
        Worksheet name or index.

    Returns
    -------
    tuple
        DataFrame and WorkbookInfo
    """

    logger.info("Reading workbook : %s", file_path)

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        engine="openpyxl",
    )

    # Remove completely empty rows
    df = df.dropna(how="all")

    # Remove leading/trailing spaces from column names
    df.columns = (
        df.columns.astype(str)
        .str.strip()
    )

    workbook = WorkbookInfo(
        file_path=file_path,
        file_name=file_path.name,
        sheet_name=str(sheet_name),
        rows=len(df),
        columns=len(df.columns),
    )

    logger.info(
        "Workbook loaded successfully (%d rows, %d columns)",
        workbook.rows,
        workbook.columns,
    )

    return df, workbook