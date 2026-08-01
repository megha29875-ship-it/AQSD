"""
AQSD
Data Storage Migration Utility

Module : PATH-002
Version: 1.0.0
Author : AQSD

Purpose
-------
Safely migrate existing AQSD market data from the project drive (C:)
to the dedicated AQSD data drive (D:).

Safety Policy
-------------
1. COPY only.
2. Never delete source data.
3. Existing destination files are preserved/updated.
4. Verify source and destination file counts.
5. Verify total byte counts.
6. Database is copied separately.
7. C: source remains untouched until manual approval.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from Scripts.aqsd_core.paths import (
    PROJECT_ROOT,
    DATA_ROOT,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    DATABASE_DIR,
    NSE_FNO_HISTORICAL_DB,
    ensure_aqsd_directories,
)


MODULE_ID = "PATH-002"
VERSION = "1.0.0"


# ==========================================================
# EXISTING C: LOCATIONS
# ==========================================================

OLD_DATA_ROOT = PROJECT_ROOT / "Data"

OLD_RAW_DIR = OLD_DATA_ROOT / "Raw"

OLD_PROCESSED_DIR = OLD_DATA_ROOT / "Processed"

OLD_DATABASE_DIR = PROJECT_ROOT / "Databases"

OLD_NSE_DATABASE = (
    OLD_DATABASE_DIR
    / "NSE_FNO_Historical.db"
)


# ==========================================================
# HELPERS
# ==========================================================

def directory_statistics(path: Path) -> tuple[int, int]:
    """
    Return:
        file_count,
        total_bytes
    """

    if not path.exists():
        return 0, 0

    files = [
        file
        for file in path.rglob("*")
        if file.is_file()
    ]

    total_bytes = sum(
        file.stat().st_size
        for file in files
    )

    return len(files), total_bytes


def human_size(size: int) -> str:
    """
    Convert bytes to readable size.
    """

    value = float(size)

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ):
        if value < 1024:
            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{value:,.2f} PB"


def copy_directory(
    source: Path,
    destination: Path,
) -> bool:
    """
    Copy directory tree without deleting source.
    """

    print()
    print("-" * 100)
    print(f"SOURCE      : {source}")
    print(f"DESTINATION : {destination}")
    print("-" * 100)

    if not source.exists():
        print("SOURCE NOT FOUND - SKIPPED")
        return False

    before_files, before_bytes = (
        directory_statistics(source)
    )

    print(
        f"Source Files : {before_files:,}"
    )

    print(
        f"Source Size  : "
        f"{human_size(before_bytes)}"
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        copy_function=shutil.copy2,
    )

    after_files, after_bytes = (
        directory_statistics(destination)
    )

    print(
        f"Destination Files : "
        f"{after_files:,}"
    )

    print(
        f"Destination Size  : "
        f"{human_size(after_bytes)}"
    )

    valid = (
        before_files == after_files
        and
        before_bytes == after_bytes
    )

    print(
        "VALIDATION        : "
        + ("PASS" if valid else "FAIL")
    )

    return valid


def copy_database() -> bool:
    """
    Copy historical SQLite database.
    """

    print()
    print("-" * 100)
    print("HISTORICAL DATABASE")
    print("-" * 100)

    print(
        f"SOURCE      : "
        f"{OLD_NSE_DATABASE}"
    )

    print(
        f"DESTINATION : "
        f"{NSE_FNO_HISTORICAL_DB}"
    )

    if not OLD_NSE_DATABASE.exists():
        print(
            "DATABASE SOURCE NOT FOUND - SKIPPED"
        )
        return False

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_size = (
        OLD_NSE_DATABASE.stat().st_size
    )

    shutil.copy2(
        OLD_NSE_DATABASE,
        NSE_FNO_HISTORICAL_DB,
    )

    destination_size = (
        NSE_FNO_HISTORICAL_DB.stat().st_size
    )

    print(
        f"Source Size      : "
        f"{human_size(source_size)}"
    )

    print(
        f"Destination Size : "
        f"{human_size(destination_size)}"
    )

    valid = (
        source_size == destination_size
    )

    print(
        "VALIDATION       : "
        + ("PASS" if valid else "FAIL")
    )

    return valid


# ==========================================================
# MAIN MIGRATION
# ==========================================================

def run_migration() -> None:

    ensure_aqsd_directories()

    print()
    print("=" * 100)
    print("AQSD DATA STORAGE MIGRATION")
    print("=" * 100)

    print(
        f"Module           : {MODULE_ID}"
    )

    print(
        f"Version          : {VERSION}"
    )

    print(
        f"Project Root     : {PROJECT_ROOT}"
    )

    print(
        f"New Data Root    : {DATA_ROOT}"
    )

    print()
    print(
        "MODE             : COPY ONLY"
    )

    print(
        "SOURCE DELETION  : PROHIBITED"
    )

    print("=" * 100)

    results: dict[str, bool] = {}

    # ------------------------------------------------------
    # RAW DATA
    # ------------------------------------------------------

    results["Raw"] = copy_directory(
        OLD_RAW_DIR,
        RAW_DATA_DIR,
    )

    # ------------------------------------------------------
    # PROCESSED DATA
    # ------------------------------------------------------

    results["Processed"] = copy_directory(
        OLD_PROCESSED_DIR,
        PROCESSED_DATA_DIR,
    )

    # ------------------------------------------------------
    # DATABASE
    # ------------------------------------------------------

    results["Database"] = (
        copy_database()
    )

    # ------------------------------------------------------
    # FINAL REPORT
    # ------------------------------------------------------

    print()
    print("=" * 100)
    print("AQSD MIGRATION SUMMARY")
    print("=" * 100)

    for name, result in results.items():

        print(
            f"{name:<20}: "
            f"{'PASS' if result else 'NOT MIGRATED'}"
        )

    print("-" * 100)

    if all(results.values()):

        print(
            "MIGRATION STATUS : SUCCESS"
        )

        print()
        print(
            "IMPORTANT:"
        )

        print(
            "C: SOURCE DATA HAS NOT BEEN DELETED."
        )

        print(
            "DO NOT DELETE IT YET."
        )

        print(
            "The D: database must first be tested "
            "by AQSD."
        )

    else:

        print(
            "MIGRATION STATUS : INCOMPLETE"
        )

        print(
            "NO SOURCE DATA HAS BEEN DELETED."
        )

    print("=" * 100)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    run_migration()