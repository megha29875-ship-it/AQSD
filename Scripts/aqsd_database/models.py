"""
AQSD
Database Models

Module    : models.py
Module ID : DB-001A
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Dataclasses used by the AQSD Database Builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd


# ==========================================================
# Workbook Information
# ==========================================================

@dataclass(slots=True)
class WorkbookInfo:
    """
    Metadata describing the source workbook.
    """

    file_path: Path
    file_name: str
    sheet_name: str
    rows: int = 0
    columns: int = 0
    loaded_at: datetime = field(default_factory=datetime.now)


# ==========================================================
# Validation Summary
# ==========================================================

@dataclass(slots=True)
class ValidationSummary:
    """
    Overall validation results.
    """

    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.passed = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


# ==========================================================
# Database Result
# ==========================================================

@dataclass(slots=True)
class DatabaseResult:
    """
    Final output from the Database Builder.
    """

    success: bool
    dataframe: pd.DataFrame

    workbook: WorkbookInfo

    validation: ValidationSummary

    rows_processed: int

    execution_time: float

    output_file: Path | None = None

    validation_report: Path | None = None

    log_file: Path | None = None


# ==========================================================
# Build Statistics
# ==========================================================

@dataclass(slots=True)
class BuildStatistics:
    """
    Statistics generated during database creation.
    """

    total_rows: int = 0

    total_columns: int = 0

    duplicate_dates: int = 0

    missing_values: int = 0

    weekend_dates: int = 0

    holiday_dates: int = 0

    invalid_dates: int = 0

    invalid_numeric_values: int = 0