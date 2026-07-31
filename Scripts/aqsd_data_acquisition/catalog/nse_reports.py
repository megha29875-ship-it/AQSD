"""
AQSD
Data Acquisition Engine

Module : NSE Report Catalog
Version: 1.0.0

Description
-----------
Defines every official NSE report known to AQSD.

This file contains NO download logic.

Only report metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


# ==========================================================
# CONSTANTS
# ==========================================================

NSE_ARCHIVE_BASE_URL: Final = (
    "https://nsearchives.nseindia.com/content/nsccl"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class NSEReport:
    """
    Metadata describing one NSE report.
    """

    report_id: str

    report_name: str

    filename_template: str

    validator: str

    destination_folder: str

    description: str


# ==========================================================
# REPORT DEFINITIONS
# ==========================================================

PARTICIPANT_OI = NSEReport(

    report_id="PARTICIPANT_OI",

    report_name="Participant Wise Open Interest",

    filename_template="fao_participant_oi_{date}.csv",

    validator="participant_csv",

    destination_folder="Participant",

    description=(
        "Daily participant-wise open interest report."
    ),
)


PARTICIPANT_VOLUME = NSEReport(

    report_id="PARTICIPANT_VOLUME",

    report_name="Participant Wise Trading Volume",

    filename_template="fao_participant_vol_{date}.csv",

    validator="participant_csv",

    destination_folder="Participant",

    description=(
        "Daily participant-wise trading volume report."
    ),
)


# ==========================================================
# CATALOG
# ==========================================================

ALL_REPORTS: Final = (

    PARTICIPANT_OI,

    PARTICIPANT_VOLUME,

)


# ==========================================================
# PUBLIC API
# ==========================================================

def get_nse_report_catalog(
    trade_date: date,
) -> list[dict]:
    """
    Return a download catalog for the requested trading date.
    """

    date_code = trade_date.strftime("%d%m%Y")

    catalog = []

    for report in ALL_REPORTS:

        filename = report.filename_template.format(
            date=date_code
        )

        catalog.append(
            {
                "id": report.report_id,
                "name": report.report_name,
                "filename": filename,
                "url": (
                    f"{NSE_ARCHIVE_BASE_URL}/{filename}"
                ),
                "validator": report.validator,
                "destination": report.destination_folder,
                "description": report.description,
            }
        )

    return catalog