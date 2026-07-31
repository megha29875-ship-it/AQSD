"""
AQSD
Data Acquisition Engine

Module : Generic HTTP Downloader
Version: 1.0.0

Description
-----------
Provides reusable download functionality for all AQSD
data sources.

Responsibilities
----------------
✓ HTTP Session
✓ Retry Logic
✓ File Download
✓ File Validation
✓ SHA256 Hash
✓ Download Metadata

Contains NO report definitions.
Contains NO business logic.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import requests

from .validators import validate_file

# ==========================================================
# SETTINGS
# ==========================================================

REQUEST_TIMEOUT: Final = 30
MAX_RETRIES: Final = 3

HEADERS: Final = {
    "User-Agent":
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        )
}

# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass
class DownloadResult:

    success: bool

    url: str

    output_file: Path

    file_size: int

    sha256: str | None

    message: str

# ==========================================================
# UTILITIES
# ==========================================================

def calculate_sha256(file_path: Path) -> str:

    sha = hashlib.sha256()

    with file_path.open("rb") as handle:

        while True:

            block = handle.read(65536)

            if not block:
                break

            sha.update(block)

    return sha.hexdigest()

# ==========================================================
# HTTP SESSION
# ==========================================================

def create_session() -> requests.Session:

    session = requests.Session()

    session.headers.update(HEADERS)

    return session

# ==========================================================
# DOWNLOAD
# ==========================================================

def download_file(
    session: requests.Session,
    url: str,
    output_file: Path,
    validator: str,
) -> DownloadResult:

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_file.write_bytes(response.content)

            validation = validate_file(
                output_file,
                validator,
            )

            if not validation.is_valid:

                output_file.unlink(
                    missing_ok=True,
                )

                raise RuntimeError(
                    validation.message
                )

            sha = calculate_sha256(
                output_file
            )

            return DownloadResult(
                success=True,
                url=url,
                output_file=output_file,
                file_size=output_file.stat().st_size,
                sha256=sha,
                message="SUCCESS",
            )

        except Exception as exc:

            last_error = str(exc)

            if attempt < MAX_RETRIES:

                time.sleep(attempt)

    return DownloadResult(

        success=False,

        url=url,

        output_file=output_file,

        file_size=0,

        sha256=None,

        message=last_error,
    )