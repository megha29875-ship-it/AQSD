"""
AQSD
Data Acquisition Engine

Module : Download Manager
Version: 1.1.0

Description
-----------
Coordinates AQSD download activity.

Responsibilities:
- Load report catalog.
- Create output folders.
- Detect completed downloads.
- Skip valid duplicate downloads.
- Re-download missing or damaged files.
- Record every new attempt in SQLite history.
- Create a JSON run manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from .catalog import get_nse_report_catalog
from .download_history import (
    get_database_file,
    is_download_complete,
    record_download_result,
)
from .downloader import create_session, download_file
from .manifest import (
    ManifestFileRecord,
    create_manifest,
    save_manifest,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "DAQ-002"
MODULE_VERSION: Final[str] = "1.1.0"
DATA_SOURCE: Final[str] = "NSE"


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

@dataclass(frozen=True)
class ManagerResult:
    """
    Summary returned by the AQSD Download Manager.
    """

    trade_date: date
    output_directory: Path
    manifest_file: Path
    reports_requested: int
    reports_successful: int
    reports_failed: int
    reports_skipped: int
    overall_status: str


# ==========================================================
# PATH MANAGEMENT
# ==========================================================

def build_nse_output_directory(
    trade_date: date,
    destination_folder: str,
) -> Path:
    """
    Build a date-specific NSE raw-data folder.

    Example:
        Data/Raw/NSE/Participant/2026/07/30
    """

    output_directory = (
        RAW_DATA_DIR
        / DATA_SOURCE
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
    Build the central NSE manifest directory.

    Example:
        Data/Raw/NSE/Manifests/2026/07/30
    """

    manifest_directory = (
        RAW_DATA_DIR
        / DATA_SOURCE
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

    Valid existing downloads are skipped.

    Missing or damaged files are downloaded again.
    """

    run_started_at = datetime.now().astimezone()

    print("=" * 70)
    print("AQSD DOWNLOAD MANAGER STARTED")
    print(f"Module version : {MODULE_VERSION}")
    print(f"Trade date     : {trade_date.isoformat()}")
    print(f"History DB     : {get_database_file()}")
    print("-" * 70)

    report_catalog = get_nse_report_catalog(
        trade_date
    )

    session = create_session()

    manifest_records: list[ManifestFileRecord] = []

    first_output_directory: Path | None = None
    skipped_count = 0

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

        print(f"Report: {report['name']}")

        completed, existing_file, existing_hash = (
            is_download_complete(
                source=DATA_SOURCE,
                report_id=report["id"],
                trade_date=trade_date,
            )
        )

        # --------------------------------------------------
        # VALID DUPLICATE FOUND
        # --------------------------------------------------

        if completed and existing_file is not None:
            skipped_count += 1

            file_size = existing_file.stat().st_size

            print(
                "SKIPPED: Already downloaded and verified."
            )

            print(f"File: {existing_file}")

            manifest_records.append(
                ManifestFileRecord(
                    report_id=report["id"],
                    report_name=report["name"],
                    url=report["url"],
                    output_file=str(existing_file),
                    status="SUCCESS",
                    file_size_bytes=file_size,
                    sha256=existing_hash,
                    message=(
                        "SKIPPED_ALREADY_DOWNLOADED"
                    ),
                )
            )

            print("-" * 70)
            continue

        # --------------------------------------------------
        # DOWNLOAD REQUIRED
        # --------------------------------------------------

        if existing_file is not None:
            print(
                "Existing history found, but the file is "
                "missing or damaged. Re-downloading."
            )
        else:
            print("Downloading new report.")

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

        record_download_result(
            source=DATA_SOURCE,
            report_id=report["id"],
            report_name=report["name"],
            trade_date=trade_date,
            url=report["url"],
            output_file=result.output_file,
            status=status,
            file_size_bytes=result.file_size,
            sha256=result.sha256,
            message=result.message,
            module_version=MODULE_VERSION,
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

        print(f"{status}: {report['filename']}")

        if not result.success:
            print(f"Reason: {result.message}")

        print("-" * 70)

    # ======================================================
    # MANIFEST
    # ======================================================

    run_finished_at = datetime.now().astimezone()

    manifest_directory = build_manifest_directory(
        trade_date
    )

    final_output_directory = (
        first_output_directory
        if first_output_directory is not None
        else manifest_directory
    )

    manifest = create_manifest(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        source=DATA_SOURCE,
        trade_date=trade_date,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        output_directory=final_output_directory,
        file_records=manifest_records,
    )

    manifest_file = save_manifest(
        manifest=manifest,
        manifest_file=(
            manifest_directory
            / "download_manifest.json"
        ),
    )

    # ======================================================
    # FINAL SUMMARY
    # ======================================================

    print(f"Reports requested : {manifest.reports_requested}")
    print(f"Successful        : {manifest.reports_successful}")
    print(f"Skipped           : {skipped_count}")
    print(f"Failed            : {manifest.reports_failed}")
    print(f"Overall status    : {manifest.overall_status}")
    print(f"Manifest          : {manifest_file}")
    print("AQSD DOWNLOAD MANAGER FINISHED")
    print("=" * 70)

    return ManagerResult(
        trade_date=trade_date,
        output_directory=final_output_directory,
        manifest_file=manifest_file,
        reports_requested=manifest.reports_requested,
        reports_successful=manifest.reports_successful,
        reports_failed=manifest.reports_failed,
        reports_skipped=skipped_count,
        overall_status=manifest.overall_status,
    )