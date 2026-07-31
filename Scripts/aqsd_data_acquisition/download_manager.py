"""
AQSD
Data Acquisition Engine

Module : Download Manager
Version: 1.0.0

Description
-----------
Coordinates AQSD download activity.

Responsibilities:
- Load report catalog
- Create output folders
- Initialize HTTP session
- Download reports
- Validate downloaded files
- Build manifest records
- Save the run manifest
- Provide a summarized result

This module contains orchestration logic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from .catalog import get_nse_report_catalog
from .downloader import create_session, download_file
from .manifest import (
    ManifestFileRecord,
    create_manifest,
    save_manifest,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

RAW_DATA_DIR: Final[Path] = (
    BASE_DIR
    / "Data"
    / "Raw"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass
class ManagerResult:
    """
    Summary returned by the AQSD download manager.
    """

    trade_date: date
    output_directory: Path
    manifest_file: Path
    reports_requested: int
    reports_successful: int
    reports_failed: int
    overall_status: str


# ==========================================================
# PATH MANAGEMENT
# ==========================================================

def build_nse_output_directory(
    trade_date: date,
    destination_folder: str,
) -> Path:
    """
    Build the date-specific NSE raw-data folder.

    Example:
    Data/Raw/NSE/Participant/2026/07/30
    """

    output_directory = (
        RAW_DATA_DIR
        / "NSE"
        / destination_folder
        / trade_date.strftime("%Y")
        / trade_date.strftime("%m")
        / trade_date.strftime("%d")
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return output_directory


def build_manifest_directory(
    trade_date: date,
) -> Path:
    """
    Build the central manifest directory.

    Example:
    Data/Raw/NSE/Manifests/2026/07/30
    """

    manifest_directory = (
        RAW_DATA_DIR
        / "NSE"
        / "Manifests"
        / trade_date.strftime("%Y")
        / trade_date.strftime("%m")
        / trade_date.strftime("%d")
    )

    manifest_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return manifest_directory


# ==========================================================
# DOWNLOAD MANAGER
# ==========================================================

def run_nse_download_manager(
    trade_date: date,
) -> ManagerResult:
    """
    Download all NSE reports configured for the selected date.
    """

    run_started_at = datetime.now().astimezone()

    print("=" * 70)
    print("AQSD DOWNLOAD MANAGER STARTED")
    print(f"Trade date: {trade_date.isoformat()}")

    report_catalog = get_nse_report_catalog(
        trade_date
    )

    session = create_session()

    manifest_records: list[ManifestFileRecord] = []

    first_output_directory: Path | None = None

    for report in report_catalog:
        output_directory = build_nse_output_directory(
            trade_date=trade_date,
            destination_folder=report["destination"],
        )

        if first_output_directory is None:
            first_output_directory = output_directory

        output_file = (
            output_directory
            / report["filename"]
        )

        print(
            f"Downloading: {report['name']}"
        )

        result = download_file(
            session=session,
            url=report["url"],
            output_file=output_file,
            validator=report["validator"],
        )

        status = (
            "SUCCESS"
            if result.success
            else "FAILED"
        )

        manifest_records.append(
            ManifestFileRecord(
                report_id=report["id"],
                report_name=report["name"],
                url=report["url"],
                output_file=str(result.output_file),
                status=status,
                file_size_bytes=result.file_size,
                sha256=result.sha256,
                message=result.message,
            )
        )

        print(
            f"{status}: {report['filename']}"
        )

        if not result.success:
            print(
                f"Reason: {result.message}"
            )

    run_finished_at = datetime.now().astimezone()

    manifest_directory = build_manifest_directory(
        trade_date
    )

    manifest = create_manifest(
        module_id="DAQ-002",
        module_version="1.0.0",
        source="NSE",
        trade_date=trade_date,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        output_directory=(
            first_output_directory
            if first_output_directory is not None
            else manifest_directory
        ),
        file_records=manifest_records,
    )

    manifest_file = save_manifest(
        manifest=manifest,
        manifest_file=(
            manifest_directory
            / "download_manifest.json"
        ),
    )

    print(
        f"Successful: "
        f"{manifest.reports_successful}"
    )

    print(
        f"Failed: "
        f"{manifest.reports_failed}"
    )

    print(
        f"Overall status: "
        f"{manifest.overall_status}"
    )

    print(
        f"Manifest: {manifest_file}"
    )

    print("AQSD DOWNLOAD MANAGER FINISHED")
    print("=" * 70)

    return ManagerResult(
        trade_date=trade_date,
        output_directory=(
            first_output_directory
            if first_output_directory is not None
            else manifest_directory
        ),
        manifest_file=manifest_file,
        reports_requested=manifest.reports_requested,
        reports_successful=manifest.reports_successful,
        reports_failed=manifest.reports_failed,
        overall_status=manifest.overall_status,
    )