"""
AQSD
Data Acquisition Engine

Module : Download Manifest
Version: 1.0.0

Description
-----------
Creates structured JSON manifests for AQSD download runs.

The manifest records:
- Trade date
- Run time
- Source
- Report results
- File metadata
- Validation status
- Overall run status
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


# ==========================================================
# DATA MODELS
# ==========================================================

@dataclass
class ManifestFileRecord:
    """
    Metadata for one downloaded file.
    """

    report_id: str
    report_name: str
    url: str
    output_file: str
    status: str
    file_size_bytes: int
    sha256: str | None
    message: str


@dataclass
class DownloadManifest:
    """
    Complete record of one AQSD download run.
    """

    module_id: str
    module_version: str
    source: str
    trade_date: str
    run_started_at: str
    run_finished_at: str
    output_directory: str
    reports_requested: int
    reports_successful: int
    reports_failed: int
    overall_status: str
    files: list[ManifestFileRecord]


# ==========================================================
# STATUS LOGIC
# ==========================================================

def determine_overall_status(
    successful: int,
    failed: int,
) -> str:
    """
    Determine the overall status of a download run.
    """

    if failed == 0 and successful > 0:
        return "SUCCESS"

    if successful > 0 and failed > 0:
        return "PARTIAL_FAILURE"

    return "FAILED"


# ==========================================================
# MANIFEST CREATION
# ==========================================================

def create_manifest(
    *,
    module_id: str,
    module_version: str,
    source: str,
    trade_date: date,
    run_started_at: datetime,
    run_finished_at: datetime,
    output_directory: Path,
    file_records: list[ManifestFileRecord],
) -> DownloadManifest:
    """
    Build a DownloadManifest object.
    """

    successful = sum(
        record.status == "SUCCESS"
        for record in file_records
    )

    failed = len(file_records) - successful

    return DownloadManifest(
        module_id=module_id,
        module_version=module_version,
        source=source,
        trade_date=trade_date.isoformat(),
        run_started_at=run_started_at
        .astimezone()
        .isoformat(timespec="seconds"),
        run_finished_at=run_finished_at
        .astimezone()
        .isoformat(timespec="seconds"),
        output_directory=str(output_directory),
        reports_requested=len(file_records),
        reports_successful=successful,
        reports_failed=failed,
        overall_status=determine_overall_status(
            successful=successful,
            failed=failed,
        ),
        files=file_records,
    )


# ==========================================================
# FILE OUTPUT
# ==========================================================

def save_manifest(
    manifest: DownloadManifest,
    manifest_file: Path,
) -> Path:
    """
    Save the manifest as formatted JSON.
    """

    manifest_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_data: dict[str, Any] = asdict(manifest)

    with manifest_file.open(
        "w",
        encoding="utf-8",
    ) as file_handle:
        json.dump(
            manifest_data,
            file_handle,
            indent=4,
            ensure_ascii=False,
        )

    return manifest_file


def load_manifest(
    manifest_file: Path,
) -> dict[str, Any]:
    """
    Read an existing manifest JSON file.
    """

    if not manifest_file.exists():
        raise FileNotFoundError(
            f"Manifest file not found: {manifest_file}"
        )

    with manifest_file.open(
        "r",
        encoding="utf-8",
    ) as file_handle:
        data = json.load(file_handle)

    if not isinstance(data, dict):
        raise ValueError(
            "Manifest content must be a JSON object."
        )

    return data