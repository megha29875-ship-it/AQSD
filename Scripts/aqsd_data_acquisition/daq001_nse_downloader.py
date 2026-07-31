"""
AQSD
Data Acquisition Engine

Module : DAQ-001 NSE Downloader
Version: 1.1.0

Description
-----------
Command-line entry point for the AQSD NSE download framework.

The actual work is handled by:
- catalog
- downloader
- validators
- manifest
- download_manager
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from Scripts.aqsd_data_acquisition.download_manager import (
    run_nse_download_manager,
)


def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Download official NSE reports "
            "through the AQSD download framework."
        )
    )

    parser.add_argument(
        "--date",
        type=str,
        default=date.today().isoformat(),
        help=(
            "Trading date in YYYY-MM-DD format. "
            "Default: today's date."
        ),
    )

    return parser.parse_args()


def parse_trade_date(
    date_text: str,
) -> date:
    """
    Convert YYYY-MM-DD text into a Python date.
    """

    try:
        return datetime.strptime(
            date_text,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. "
            "Use YYYY-MM-DD."
        ) from exc


def main() -> None:
    """
    Run the NSE download framework.
    """

    arguments = parse_arguments()

    selected_date = parse_trade_date(
        arguments.date
    )

    result = run_nse_download_manager(
        selected_date
    )

    if result.reports_failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()