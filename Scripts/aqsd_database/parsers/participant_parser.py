"""
AQSD
Participant Database Engine

Module : APD-003 Participant Report Parser
Version: 1.0.0

Description
-----------
Reads official NSE participant-wise Open Interest or Trading Volume
CSV reports and converts them into standardized ParticipantPosition
records.

Raw source files are never modified.

Supported participants:
- CLIENT
- FII
- DII
- PRO

The TOTAL row is ignored because it can be recalculated from the
individual participant records.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from Scripts.aqsd_database.repositories import (
    ParticipantPosition,
    ParticipantRepository,
)


# ==========================================================
# PARTICIPANT LABELS
# ==========================================================

PARTICIPANT_ALIASES: Final[dict[str, str]] = {
    "CLIENT": "CLIENT",
    "CLIENTS": "CLIENT",
    "FII": "FII",
    "FPI": "FII",
    "DII": "DII",
    "PRO": "PRO",
    "PROPRIETARY": "PRO",
    "TOTAL": "TOTAL",
}


# ==========================================================
# PARSE RESULT
# ==========================================================

@dataclass(frozen=True)
class ParticipantParseResult:
    """
    Summary returned after parsing one NSE participant file.
    """

    source_file: Path
    trade_date: date
    report_type: str
    participants_found: tuple[str, ...]
    records_created: int
    records_inserted: int
    records_skipped: int
    status: str
    message: str


# ==========================================================
# TEXT NORMALIZATION
# ==========================================================

def normalize_text(value: str) -> str:
    """
    Convert text to a consistent uppercase form.
    """

    normalized = value.strip().upper()

    normalized = re.sub(
        r"[^A-Z0-9]+",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def normalize_participant(value: str) -> str:
    """
    Convert an NSE participant label into the AQSD standard.
    """

    normalized = normalize_text(value)

    return PARTICIPANT_ALIASES.get(
        normalized,
        normalized,
    )


# ==========================================================
# NUMERIC CONVERSION
# ==========================================================

def parse_numeric_value(value: str) -> float:
    """
    Convert an NSE numeric value into float.

    Handles:
    - commas
    - blank cells
    - quoted numbers
    - negative numbers
    """

    cleaned = value.strip().replace(",", "")

    if cleaned in {"", "-", "--", "NA", "N/A"}:
        return 0.0

    try:
        return float(cleaned)

    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric value: {value!r}"
        ) from exc


# ==========================================================
# REPORT TYPE
# ==========================================================

def detect_report_type(source_file: Path) -> str:
    """
    Detect whether the source file is OI or trading volume.
    """

    filename = source_file.name.lower()

    if "participant_oi" in filename:
        return "OPEN INTEREST"

    if "participant_vol" in filename:
        return "TRADING VOLUME"

    raise ValueError(
        "Could not detect participant report type from filename: "
        f"{source_file.name}"
    )


# ==========================================================
# HEADER MAPPING
# ==========================================================

def split_header(
    header: str,
    report_type: str,
) -> tuple[str, str] | None:
    """
    Convert an NSE column header into:

    segment
    position_side

    Examples
    --------
    Future Index Long
        -> OPEN INTEREST - INDEX FUTURES
        -> LONG

    Option Index Call Long
        -> OPEN INTEREST - INDEX OPTIONS CALL
        -> LONG
    """

    normalized = normalize_text(header)

    if normalized in {
        "",
        "CLIENT TYPE",
        "CLIENTTYPE",
    }:
        return None

    if normalized.startswith("TOTAL"):
        return None

    side: str | None = None

    if normalized.endswith(" LONG"):
        side = "LONG"
        base_header = normalized.removesuffix(" LONG").strip()

    elif normalized.endswith(" SHORT"):
        side = "SHORT"
        base_header = normalized.removesuffix(" SHORT").strip()

    else:
        return None

    segment_map = {
        "FUTURE INDEX": "INDEX FUTURES",
        "FUTURES INDEX": "INDEX FUTURES",
        "FUTURE STOCK": "STOCK FUTURES",
        "FUTURES STOCK": "STOCK FUTURES",
        "OPTION INDEX CALL": "INDEX OPTIONS CALL",
        "OPTION INDEX PUT": "INDEX OPTIONS PUT",
        "OPTION STOCK CALL": "STOCK OPTIONS CALL",
        "OPTION STOCK PUT": "STOCK OPTIONS PUT",
    }

    segment = segment_map.get(base_header)

    if segment is None:
        return None

    combined_segment = (
        f"{report_type} - {segment}"
    )

    return combined_segment, side


# ==========================================================
# CSV READING
# ==========================================================

def read_csv_rows(
    source_file: Path,
) -> tuple[list[str], list[list[str]]]:
    """
    Read an NSE participant CSV and automatically locate
    the actual header row.

    NSE participant files commonly contain a report-title row
    before the row beginning with 'Client Type'.
    """

    if not source_file.exists():
        raise FileNotFoundError(
            f"Participant report not found: {source_file}"
        )

    encodings = (
        "utf-8-sig",
        "utf-8",
        "latin-1",
    )

    last_error: Exception | None = None

    for encoding in encodings:
        try:
            with source_file.open(
                "r",
                encoding=encoding,
                newline="",
            ) as file_handle:
                all_rows = list(csv.reader(file_handle))

            if not all_rows:
                raise ValueError(
                    "Participant report is empty."
                )

            header_row_index: int | None = None

            for row_index, row in enumerate(all_rows):
                if not row:
                    continue

                first_cell = normalize_text(row[0])

                if first_cell in {
                    "CLIENT TYPE",
                    "CLIENTTYPE",
                }:
                    header_row_index = row_index
                    break

            if header_row_index is None:
                raise ValueError(
                    "Could not locate the 'Client Type' header row."
                )

            headers = [
                cell.strip()
                for cell in all_rows[header_row_index]
            ]

            data_rows = [
                row
                for row in all_rows[header_row_index + 1:]
                if row
                and any(cell.strip() for cell in row)
            ]

            return headers, data_rows

        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeError(
        f"Unable to decode participant report: {source_file}"
    ) from last_error

# ==========================================================
# RECORD CREATION
# ==========================================================

def create_participant_positions(
    *,
    source_file: Path,
    trade_date: date,
) -> tuple[
    list[ParticipantPosition],
    tuple[str, ...],
    str,
]:
    """
    Convert one NSE participant report into repository records.
    """

    report_type = detect_report_type(
        source_file
    )

    headers, rows = read_csv_rows(
        source_file
    )

    if len(headers) < 2:
        raise ValueError(
            "Participant report contains insufficient columns."
        )

    positions: list[ParticipantPosition] = []
    participants_found: set[str] = set()

    for row_number, row in enumerate(
        rows,
        start=2,
    ):
        if not row:
            continue

        participant = normalize_participant(
            row[0]
        )

        if participant == "TOTAL":
            continue

        if participant not in {
            "CLIENT",
            "FII",
            "DII",
            "PRO",
        }:
            continue

        participants_found.add(
            participant
        )

        for column_index in range(
            1,
            min(len(headers), len(row)),
        ):
            mapping = split_header(
                headers[column_index],
                report_type,
            )

            if mapping is None:
                continue

            segment, position_side = mapping

            try:
                numeric_value = parse_numeric_value(
                    row[column_index]
                )

            except ValueError as exc:
                raise ValueError(
                    f"{exc} File: {source_file.name}; "
                    f"row: {row_number}; "
                    f"column: {headers[column_index]!r}"
                ) from exc

            positions.append(
                ParticipantPosition(
                    trade_date=trade_date,
                    participant=participant,
                    segment=segment,
                    position_side=position_side,
                    value=numeric_value,
                    source_file=source_file.name,
                )
            )

    if not positions:
        raise ValueError(
            "No participant-position records were created. "
            "The NSE report structure may have changed."
        )

    return (
        positions,
        tuple(sorted(participants_found)),
        report_type,
    )


# ==========================================================
# MAIN PARSER
# ==========================================================

def parse_participant_report(
    *,
    source_file: Path,
    trade_date: date,
    repository: ParticipantRepository | None = None,
) -> ParticipantParseResult:
    """
    Parse one NSE participant report and insert its records
    into the APD database.
    """

    owns_repository = repository is None

    active_repository = (
        repository
        if repository is not None
        else ParticipantRepository()
    )

    try:
        (
            positions,
            participants,
            report_type,
        ) = create_participant_positions(
            source_file=source_file,
            trade_date=trade_date,
        )

        inserted, skipped = (
            active_repository.insert_many(
                positions
            )
        )

        return ParticipantParseResult(
            source_file=source_file,
            trade_date=trade_date,
            report_type=report_type,
            participants_found=participants,
            records_created=len(positions),
            records_inserted=inserted,
            records_skipped=skipped,
            status="SUCCESS",
            message="Participant report parsed successfully.",
        )

    except Exception as exc:
        return ParticipantParseResult(
            source_file=source_file,
            trade_date=trade_date,
            report_type="UNKNOWN",
            participants_found=(),
            records_created=0,
            records_inserted=0,
            records_skipped=0,
            status="FAILED",
            message=str(exc),
        )

    finally:
        if owns_repository:
            active_repository.close()