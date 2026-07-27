"""
AQSD
Validation Engine

Module    : validation.py
Module ID : CORE-006
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Provides reusable validation functions for AQSD modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


# ==========================================================
# Validation Result
# ==========================================================

@dataclass
class ValidationResult:
    """
    Standard validation result object.
    """

    status: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    records_checked: int = 0

    def add_error(self, message: str) -> None:
        self.status = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


# ==========================================================
# Required Columns
# ==========================================================

def validate_required_columns(
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    for column in required_columns:

        if column not in df.columns:
            result.add_error(
                f"DB003 : Missing required column -> {column}"
            )

    return result


# ==========================================================
# Empty DataFrame
# ==========================================================

def validate_not_empty(
    df: pd.DataFrame,
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    if df.empty:
        result.add_error("DB005 : Workbook is empty")

    return result


# ==========================================================
# Duplicate Dates
# ==========================================================

def validate_duplicate_dates(
    df: pd.DataFrame,
    date_column: str,
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    duplicates = df[df.duplicated(date_column)]

    if not duplicates.empty:

        for value in duplicates[date_column]:

            result.add_error(
                f"DB002 : Duplicate date -> {value}"
            )

    return result


# ==========================================================
# Missing Values
# ==========================================================

def validate_missing_values(
    df: pd.DataFrame,
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    missing = df.isna().sum()

    for column, count in missing.items():

        if count > 0:

            result.add_warning(
                f"{column} : {count} missing values"
            )

    return result


# ==========================================================
# Numeric Columns
# ==========================================================

def validate_numeric_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    for column in columns:

        if column not in df.columns:
            continue

        converted = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid = converted.isna() & df[column].notna()

        if invalid.any():

            result.add_error(
                f"DB004 : Invalid numeric values in '{column}'"
            )

    return result


# ==========================================================
# Date Column
# ==========================================================

def validate_date_column(
    df: pd.DataFrame,
    date_column: str,
) -> ValidationResult:

    result = ValidationResult(records_checked=len(df))

    try:

        pd.to_datetime(
            df[date_column],
            errors="raise",
        )

    except Exception:

        result.add_error(
            "DB006 : Invalid date format"
        )

    return result


# ==========================================================
# Combine Results
# ==========================================================

def merge_results(
    *results: ValidationResult,
) -> ValidationResult:

    merged = ValidationResult()

    for result in results:

        merged.records_checked = max(
            merged.records_checked,
            result.records_checked,
        )

        merged.errors.extend(result.errors)

        merged.warnings.extend(result.warnings)

    merged.status = len(merged.errors) == 0

    return merged