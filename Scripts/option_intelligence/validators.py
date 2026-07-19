"""
AQSD
Option Intelligence

Module: validators.py
Version: 1.0

Description:
Validation and data-quality checks for AQSD
Option Intelligence option-chain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from Scripts.option_intelligence.config import (
    ALLOW_NEGATIVE_CHANGE_IN_OI,
    ALLOW_NEGATIVE_OPEN_INTEREST,
    ALLOW_NEGATIVE_VOLUME,
    DROP_DUPLICATE_ROWS,
    DROP_INVALID_STRIKES,
    REQUIRED_OPTION_COLUMNS,
    VALID_OPTION_TYPES,
)
from Scripts.option_intelligence.common import (
    normalize_option_type,
)


# ============================================================
# VALIDATION RESULT MODEL
# ============================================================

@dataclass
class ValidationResult:
    """
    Stores the result of an option-chain validation.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_received: int = 0
    rows_valid: int = 0
    rows_removed: int = 0
    duplicate_rows: int = 0
    missing_ce_strikes: list[float] = field(default_factory=list)
    missing_pe_strikes: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        """
        Return validation summary as a dictionary.
        """

        return {
            "is_valid": self.is_valid,
            "rows_received": self.rows_received,
            "rows_valid": self.rows_valid,
            "rows_removed": self.rows_removed,
            "duplicate_rows": self.duplicate_rows,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "missing_ce_strikes": self.missing_ce_strikes,
            "missing_pe_strikes": self.missing_pe_strikes,
        }


# ============================================================
# BASIC VALIDATION HELPERS
# ============================================================

def find_missing_columns(
    dataframe: pd.DataFrame,
    required_columns: Iterable[str],
) -> list[str]:
    """
    Return required columns missing from the dataframe.
    """

    available_columns = {
        str(column).strip()
        for column in dataframe.columns
    }

    return [
        column
        for column in required_columns
        if column not in available_columns
    ]


def validate_required_columns(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Validate required option-chain columns.
    """

    missing_columns = find_missing_columns(
        dataframe=dataframe,
        required_columns=REQUIRED_OPTION_COLUMNS,
    )

    if not missing_columns:
        return []

    return [
        "Missing required columns: "
        + ", ".join(missing_columns)
    ]


def validate_dataframe_not_empty(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Validate that dataframe contains rows.
    """

    if dataframe.empty:
        return [
            "Option-chain dataframe is empty."
        ]

    return []


def validate_numeric_column(
    dataframe: pd.DataFrame,
    column: str,
) -> list[str]:
    """
    Validate that a column contains numeric values.
    """

    if column not in dataframe.columns:
        return []

    converted = pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )

    invalid_count = int(
        converted.isna().sum()
    )

    if invalid_count == 0:
        return []

    return [
        f"Column '{column}' contains "
        f"{invalid_count} invalid numeric value(s)."
    ]


def validate_non_negative_column(
    dataframe: pd.DataFrame,
    column: str,
    allow_negative: bool,
) -> list[str]:
    """
    Validate negative values in numeric columns.
    """

    if column not in dataframe.columns:
        return []

    if allow_negative:
        return []

    values = pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )

    negative_count = int(
        (values < 0).sum()
    )

    if negative_count == 0:
        return []

    return [
        f"Column '{column}' contains "
        f"{negative_count} negative value(s)."
    ]


# ============================================================
# OPTION-SPECIFIC VALIDATION
# ============================================================

def validate_option_types(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Validate and normalize CE/PE option types.
    """

    if "option_type" not in dataframe.columns:
        return []

    invalid_values: set[str] = set()

    for value in dataframe["option_type"].dropna():
        try:
            normalized = normalize_option_type(
                value
            )

            if normalized not in VALID_OPTION_TYPES:
                invalid_values.add(str(value))

        except ValueError:
            invalid_values.add(str(value))

    if not invalid_values:
        return []

    return [
        "Invalid option-type values: "
        + ", ".join(sorted(invalid_values))
    ]


def validate_strikes(
    dataframe: pd.DataFrame,
) -> list[str]:
    """
    Validate strike values.
    """

    if "strike" not in dataframe.columns:
        return []

    strikes = pd.to_numeric(
        dataframe["strike"],
        errors="coerce",
    )

    errors: list[str] = []

    invalid_count = int(
        strikes.isna().sum()
    )

    non_positive_count = int(
        (strikes <= 0).sum()
    )

    if invalid_count > 0:
        errors.append(
            f"Strike column contains "
            f"{invalid_count} invalid value(s)."
        )

    if non_positive_count > 0:
        errors.append(
            f"Strike column contains "
            f"{non_positive_count} non-positive value(s)."
        )

    return errors


def count_duplicate_rows(
    dataframe: pd.DataFrame,
) -> int:
    """
    Count duplicate option rows.
    """

    subset = [
        column
        for column in [
            "strike",
            "option_type",
            "expiry",
        ]
        if column in dataframe.columns
    ]

    if not subset:
        return int(
            dataframe.duplicated().sum()
        )

    return int(
        dataframe.duplicated(
            subset=subset,
            keep="first",
        ).sum()
    )


def find_missing_option_pairs(
    dataframe: pd.DataFrame,
) -> tuple[list[float], list[float]]:
    """
    Find strikes missing CE or PE contracts.
    """

    required = {
        "strike",
        "option_type",
    }

    if not required.issubset(
        dataframe.columns
    ):
        return [], []

    working = dataframe[
        ["strike", "option_type"]
    ].copy()

    working["strike"] = pd.to_numeric(
        working["strike"],
        errors="coerce",
    )

    normalized_types: list[str | None] = []

    for value in working["option_type"]:
        try:
            normalized_types.append(
                normalize_option_type(value)
            )
        except ValueError:
            normalized_types.append(None)

    working["option_type"] = normalized_types

    working = working.dropna(
        subset=["strike", "option_type"]
    )

    all_strikes = sorted(
        working["strike"].unique().tolist()
    )

    ce_strikes = set(
        working.loc[
            working["option_type"] == "CE",
            "strike",
        ].tolist()
    )

    pe_strikes = set(
        working.loc[
            working["option_type"] == "PE",
            "strike",
        ].tolist()
    )

    missing_ce = [
        float(strike)
        for strike in all_strikes
        if strike not in ce_strikes
    ]

    missing_pe = [
        float(strike)
        for strike in all_strikes
        if strike not in pe_strikes
    ]

    return missing_ce, missing_pe


# ============================================================
# DATA CLEANING
# ============================================================

def clean_option_chain(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean and standardize option-chain data.
    """

    cleaned = dataframe.copy()

    cleaned.columns = [
        str(column).strip()
        for column in cleaned.columns
    ]

    numeric_columns = [
        "strike",
        "open_interest",
        "change_in_oi",
        "volume",
        "ltp",
        "iv",
        "bid",
        "ask",
    ]

    for column in numeric_columns:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(
                cleaned[column],
                errors="coerce",
            )

    if "option_type" in cleaned.columns:
        normalized_types: list[str | None] = []

        for value in cleaned["option_type"]:
            try:
                normalized_types.append(
                    normalize_option_type(value)
                )
            except ValueError:
                normalized_types.append(None)

        cleaned["option_type"] = normalized_types

    if DROP_INVALID_STRIKES:
        if "strike" in cleaned.columns:
            cleaned = cleaned[
                cleaned["strike"].notna()
                & (cleaned["strike"] > 0)
            ]

    if DROP_DUPLICATE_ROWS:
        duplicate_subset = [
            column
            for column in [
                "strike",
                "option_type",
                "expiry",
            ]
            if column in cleaned.columns
        ]

        cleaned = cleaned.drop_duplicates(
            subset=duplicate_subset or None,
            keep="first",
        )

    cleaned = cleaned.reset_index(
        drop=True
    )

    return cleaned


# ============================================================
# MASTER VALIDATOR
# ============================================================

def validate_option_chain(
    dataframe: pd.DataFrame,
) -> ValidationResult:
    """
    Run complete validation for option-chain data.
    """

    rows_received = len(dataframe)

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(
        validate_dataframe_not_empty(
            dataframe
        )
    )

    errors.extend(
        validate_required_columns(
            dataframe
        )
    )

    duplicate_rows = count_duplicate_rows(
        dataframe
    )

    if duplicate_rows > 0:
        warnings.append(
            f"Detected {duplicate_rows} duplicate row(s)."
        )

    if not errors:
        for column in [
            "strike",
            "open_interest",
            "change_in_oi",
            "volume",
        ]:
            errors.extend(
                validate_numeric_column(
                    dataframe=dataframe,
                    column=column,
                )
            )

        errors.extend(
            validate_strikes(dataframe)
        )

        errors.extend(
            validate_option_types(dataframe)
        )

        errors.extend(
            validate_non_negative_column(
                dataframe=dataframe,
                column="open_interest",
                allow_negative=(
                    ALLOW_NEGATIVE_OPEN_INTEREST
                ),
            )
        )

        errors.extend(
            validate_non_negative_column(
                dataframe=dataframe,
                column="change_in_oi",
                allow_negative=(
                    ALLOW_NEGATIVE_CHANGE_IN_OI
                ),
            )
        )

        errors.extend(
            validate_non_negative_column(
                dataframe=dataframe,
                column="volume",
                allow_negative=(
                    ALLOW_NEGATIVE_VOLUME
                ),
            )
        )

    cleaned = clean_option_chain(
        dataframe
    )

    missing_ce, missing_pe = (
        find_missing_option_pairs(cleaned)
    )

    if missing_ce:
        warnings.append(
            f"{len(missing_ce)} strike(s) missing CE contracts."
        )

    if missing_pe:
        warnings.append(
            f"{len(missing_pe)} strike(s) missing PE contracts."
        )

    rows_valid = len(cleaned)
    rows_removed = rows_received - rows_valid

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        rows_received=rows_received,
        rows_valid=rows_valid,
        rows_removed=rows_removed,
        duplicate_rows=duplicate_rows,
        missing_ce_strikes=missing_ce,
        missing_pe_strikes=missing_pe,
    )


# ============================================================
# TEST DATA
# ============================================================

def create_test_option_chain() -> pd.DataFrame:
    """
    Create test option-chain data.
    """

    return pd.DataFrame(
        [
            {
                "strike": 57000,
                "option_type": "CE",
                "open_interest": 400000,
                "change_in_oi": 90000,
                "volume": 180000,
                "ltp": 720.0,
            },
            {
                "strike": 57000,
                "option_type": "PE",
                "open_interest": 520000,
                "change_in_oi": 80000,
                "volume": 220000,
                "ltp": 150.0,
            },
            {
                "strike": 57500,
                "option_type": "CE",
                "open_interest": 620000,
                "change_in_oi": 130000,
                "volume": 290000,
                "ltp": 390.0,
            },
            {
                "strike": 57500,
                "option_type": "PE",
                "open_interest": 610000,
                "change_in_oi": 95000,
                "volume": 260000,
                "ltp": 310.0,
            },
            {
                "strike": 58000,
                "option_type": "CE",
                "open_interest": 520000,
                "change_in_oi": 120000,
                "volume": 290000,
                "ltp": 190.0,
            },
            {
                "strike": 58000,
                "option_type": "PE",
                "open_interest": 290000,
                "change_in_oi": 40000,
                "volume": 185000,
                "ltp": 540.0,
            },
        ]
    )


# ============================================================
# TEST
# ============================================================

def main() -> None:
    """
    Test validator functions.
    """

    test_data = create_test_option_chain()

    result = validate_option_chain(
        test_data
    )

    cleaned_data = clean_option_chain(
        test_data
    )

    print()
    print("=" * 72)
    print("AQSD OPTION INTELLIGENCE — DATA VALIDATOR")
    print("=" * 72)

    print(
        f"Validation Status       : "
        f"{'VALID' if result.is_valid else 'INVALID'}"
    )
    print(
        f"Rows Received           : "
        f"{result.rows_received}"
    )
    print(
        f"Rows Valid              : "
        f"{result.rows_valid}"
    )
    print(
        f"Rows Removed            : "
        f"{result.rows_removed}"
    )
    print(
        f"Duplicate Rows          : "
        f"{result.duplicate_rows}"
    )
    print(
        f"Errors                  : "
        f"{len(result.errors)}"
    )
    print(
        f"Warnings                : "
        f"{len(result.warnings)}"
    )
    print(
        f"Missing CE Strikes      : "
        f"{result.missing_ce_strikes}"
    )
    print(
        f"Missing PE Strikes      : "
        f"{result.missing_pe_strikes}"
    )
    print(
        f"Cleaned Data Rows       : "
        f"{len(cleaned_data)}"
    )

    if result.errors:
        print()
        print("Errors:")

        for error in result.errors:
            print(f"- {error}")

    if result.warnings:
        print()
        print("Warnings:")

        for warning in result.warnings:
            print(f"- {warning}")

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()