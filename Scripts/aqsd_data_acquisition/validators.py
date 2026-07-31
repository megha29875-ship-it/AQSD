"""
AQSD
Data Acquisition Engine

Module : Reusable File Validators
Version: 1.0.0

Description
-----------
Provides reusable validation functions for downloaded files.

Current validators:
- Basic file validation
- HTML error-page detection
- CSV readability validation
- NSE participant report validation

This module contains no download logic.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final


# ==========================================================
# CONSTANTS
# ==========================================================

MINIMUM_VALID_FILE_SIZE: Final[int] = 100

HTML_ERROR_MARKERS: Final[tuple[str, ...]] = (
    "<html",
    "<!doctype html",
    "access denied",
    "request rejected",
    "forbidden",
    "temporarily unavailable",
)

PARTICIPANT_EXPECTED_TERMS: Final[tuple[str, ...]] = (
    "client type",
    "future index long",
    "future index short",
    "future stock long",
    "future stock short",
    "option index call long",
    "option index call short",
    "option index put long",
    "option index put short",
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class ValidationResult:
    """
    Result returned by every AQSD file validator.
    """

    is_valid: bool
    validator_name: str
    message: str
    file_size_bytes: int
    row_count: int | None = None
    column_count: int | None = None


# ==========================================================
# BASIC UTILITIES
# ==========================================================

def read_text_safely(file_path: Path) -> str:
    """
    Read a text-based file without failing on encoding differences.
    """

    encodings = (
        "utf-8-sig",
        "utf-8",
        "latin-1",
    )

    last_error: Exception | None = None

    for encoding in encodings:
        try:
            return file_path.read_text(
                encoding=encoding,
                errors="strict",
            )
        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeError(
        f"Could not decode file using supported encodings: {file_path}"
    ) from last_error


def validate_file_exists(file_path: Path) -> ValidationResult:
    """
    Validate that the file exists and is a regular file.
    """

    if not file_path.exists():
        return ValidationResult(
            is_valid=False,
            validator_name="file_exists",
            message="File does not exist.",
            file_size_bytes=0,
        )

    if not file_path.is_file():
        return ValidationResult(
            is_valid=False,
            validator_name="file_exists",
            message="Path exists but is not a regular file.",
            file_size_bytes=0,
        )

    return ValidationResult(
        is_valid=True,
        validator_name="file_exists",
        message="PASS",
        file_size_bytes=file_path.stat().st_size,
    )


def validate_minimum_size(
    file_path: Path,
    minimum_size: int = MINIMUM_VALID_FILE_SIZE,
) -> ValidationResult:
    """
    Validate that the file is not abnormally small.
    """

    existence_result = validate_file_exists(file_path)

    if not existence_result.is_valid:
        return existence_result

    file_size = file_path.stat().st_size

    if file_size < minimum_size:
        return ValidationResult(
            is_valid=False,
            validator_name="minimum_size",
            message=(
                f"File is too small: {file_size} bytes. "
                f"Minimum required: {minimum_size} bytes."
            ),
            file_size_bytes=file_size,
        )

    return ValidationResult(
        is_valid=True,
        validator_name="minimum_size",
        message="PASS",
        file_size_bytes=file_size,
    )


def validate_not_html(file_path: Path) -> ValidationResult:
    """
    Detect HTML pages accidentally saved as CSV or text files.
    """

    size_result = validate_minimum_size(file_path)

    if not size_result.is_valid:
        return size_result

    try:
        content = read_text_safely(file_path).lower()
    except (OSError, UnicodeError) as exc:
        return ValidationResult(
            is_valid=False,
            validator_name="not_html",
            message=f"Unable to inspect file contents: {exc}",
            file_size_bytes=file_path.stat().st_size,
        )

    for marker in HTML_ERROR_MARKERS:
        if marker in content:
            return ValidationResult(
                is_valid=False,
                validator_name="not_html",
                message=(
                    "Downloaded file appears to be an HTML "
                    f"error page. Marker found: {marker}"
                ),
                file_size_bytes=file_path.stat().st_size,
            )

    return ValidationResult(
        is_valid=True,
        validator_name="not_html",
        message="PASS",
        file_size_bytes=file_path.stat().st_size,
    )


# ==========================================================
# CSV VALIDATION
# ==========================================================

def inspect_csv(
    file_path: Path,
) -> tuple[list[str], int, int]:
    """
    Read a CSV file and return:

    - normalized header names
    - data row count
    - column count
    """

    content = read_text_safely(file_path)

    rows = list(csv.reader(content.splitlines()))

    if not rows:
        raise ValueError("CSV file is empty.")

    headers = [
        header.strip().lower()
        for header in rows[0]
    ]

    data_rows = [
        row for row in rows[1:]
        if any(cell.strip() for cell in row)
    ]

    column_count = len(headers)
    row_count = len(data_rows)

    return headers, row_count, column_count


def validate_csv_readable(file_path: Path) -> ValidationResult:
    """
    Validate that the file is readable as CSV.
    """

    html_result = validate_not_html(file_path)

    if not html_result.is_valid:
        return html_result

    try:
        headers, row_count, column_count = inspect_csv(file_path)

    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        return ValidationResult(
            is_valid=False,
            validator_name="csv_readable",
            message=f"CSV validation failed: {exc}",
            file_size_bytes=file_path.stat().st_size,
        )

    if column_count < 2:
        return ValidationResult(
            is_valid=False,
            validator_name="csv_readable",
            message=(
                "CSV contains fewer than two columns."
            ),
            file_size_bytes=file_path.stat().st_size,
            row_count=row_count,
            column_count=column_count,
        )

    if row_count < 1:
        return ValidationResult(
            is_valid=False,
            validator_name="csv_readable",
            message="CSV contains no data rows.",
            file_size_bytes=file_path.stat().st_size,
            row_count=row_count,
            column_count=column_count,
        )

    return ValidationResult(
        is_valid=True,
        validator_name="csv_readable",
        message="PASS",
        file_size_bytes=file_path.stat().st_size,
        row_count=row_count,
        column_count=column_count,
    )


# ==========================================================
# NSE PARTICIPANT VALIDATION
# ==========================================================

def validate_participant_csv(
    file_path: Path,
) -> ValidationResult:
    """
    Validate an NSE participant-wise OI or volume report.
    """

    csv_result = validate_csv_readable(file_path)

    if not csv_result.is_valid:
        return csv_result

    try:
        content = read_text_safely(file_path).lower()

    except (OSError, UnicodeError) as exc:
        return ValidationResult(
            is_valid=False,
            validator_name="participant_csv",
            message=f"Unable to read participant CSV: {exc}",
            file_size_bytes=file_path.stat().st_size,
        )

    matched_terms = [
        term
        for term in PARTICIPANT_EXPECTED_TERMS
        if term in content
    ]

    minimum_required_matches = 4

    if len(matched_terms) < minimum_required_matches:
        return ValidationResult(
            is_valid=False,
            validator_name="participant_csv",
            message=(
                "Participant report structure not recognized. "
                f"Matched {len(matched_terms)} expected terms; "
                f"minimum required is {minimum_required_matches}."
            ),
            file_size_bytes=file_path.stat().st_size,
            row_count=csv_result.row_count,
            column_count=csv_result.column_count,
        )

    return ValidationResult(
        is_valid=True,
        validator_name="participant_csv",
        message=(
            "PASS — participant report validated. "
            f"Matched terms: {len(matched_terms)}."
        ),
        file_size_bytes=file_path.stat().st_size,
        row_count=csv_result.row_count,
        column_count=csv_result.column_count,
    )


# ==========================================================
# VALIDATOR REGISTRY
# ==========================================================

ValidatorFunction = Callable[[Path], ValidationResult]


VALIDATOR_REGISTRY: Final[dict[str, ValidatorFunction]] = {
    "basic_file": validate_minimum_size,
    "csv": validate_csv_readable,
    "participant_csv": validate_participant_csv,
}


def get_validator(
    validator_name: str,
) -> ValidatorFunction:
    """
    Return a validator function from the central registry.
    """

    normalized_name = validator_name.strip().lower()

    try:
        return VALIDATOR_REGISTRY[normalized_name]

    except KeyError as exc:
        available = ", ".join(sorted(VALIDATOR_REGISTRY))

        raise ValueError(
            f"Unknown validator: {validator_name}. "
            f"Available validators: {available}"
        ) from exc


def validate_file(
    file_path: Path,
    validator_name: str,
) -> ValidationResult:
    """
    Run the requested validator against a file.
    """

    validator = get_validator(validator_name)
    return validator(file_path)