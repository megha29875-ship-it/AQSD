"""
AQSD
Central Path Configuration

Module : PATH-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Provide one central location for all AQSD filesystem paths.

Architecture
------------
C: = AQSD application / source code
D: = AQSD primary market data
E: = AQSD backup

Important
---------
Individual AQSD modules should import paths from this file rather
than hard-coding C:\\Users\\... paths.

This allows AQSD data storage to move between disks or cloud
storage later without redesigning individual engines.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final


# ==========================================================
# AQSD PROJECT ROOT
# ==========================================================

PROJECT_ROOT: Final[Path] = (
    Path(__file__).resolve().parents[2]
)


# ==========================================================
# PRIMARY DATA ROOT
# ==========================================================
#
# Environment variable can override the default later:
#
# AQSD_DATA_ROOT=D:\\AQSD_DATA
#
# ==========================================================

DEFAULT_DATA_ROOT: Final[Path] = Path(
    r"D:\AQSD_DATA"
)

DATA_ROOT: Final[Path] = Path(
    os.getenv(
        "AQSD_DATA_ROOT",
        str(DEFAULT_DATA_ROOT),
    )
)


# ==========================================================
# BACKUP ROOT
# ==========================================================

DEFAULT_BACKUP_ROOT: Final[Path] = Path(
    r"E:\AQSD_BACKUP"
)

BACKUP_ROOT: Final[Path] = Path(
    os.getenv(
        "AQSD_BACKUP_ROOT",
        str(DEFAULT_BACKUP_ROOT),
    )
)


# ==========================================================
# PROJECT-SIDE DIRECTORIES
# ==========================================================

SCRIPTS_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Scripts"
)

CONFIG_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Config"
)

DOCS_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Docs"
)

DASHBOARD_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Dashboard"
)

RESEARCH_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Research"
)

LOGS_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Logs"
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)


# ==========================================================
# PRIMARY DATA DIRECTORIES
# ==========================================================

RAW_DATA_DIR: Final[Path] = (
    DATA_ROOT
    / "Raw"
)

PROCESSED_DATA_DIR: Final[Path] = (
    DATA_ROOT
    / "Processed"
)

HISTORICAL_DATA_DIR: Final[Path] = (
    DATA_ROOT
    / "Historical"
)

DATABASE_DIR: Final[Path] = (
    DATA_ROOT
    / "Databases"
)

TEMP_DATA_DIR: Final[Path] = (
    DATA_ROOT
    / "Temp"
)

OUTPUT_DATA_DIR: Final[Path] = (
    DATA_ROOT
    / "Output_Data"
)


# ==========================================================
# NSE DATA DIRECTORIES
# ==========================================================

NSE_RAW_DIR: Final[Path] = (
    RAW_DATA_DIR
    / "NSE"
)

NSE_DERIVATIVES_RAW_DIR: Final[Path] = (
    NSE_RAW_DIR
    / "Derivatives"
)

NSE_PROCESSED_DIR: Final[Path] = (
    PROCESSED_DATA_DIR
    / "NSE"
)

NSE_DERIVATIVES_PROCESSED_DIR: Final[Path] = (
    NSE_PROCESSED_DIR
    / "Derivatives"
)

NSE_HISTORICAL_DIR: Final[Path] = (
    HISTORICAL_DATA_DIR
    / "NSE"
)


# ==========================================================
# AQSD DATABASE FILES
# ==========================================================

NSE_FNO_HISTORICAL_DB: Final[Path] = (
    DATABASE_DIR
    / "NSE_FNO_Historical.db"
)


# ==========================================================
# BACKUP DIRECTORIES
# ==========================================================

PROJECT_BACKUP_DIR: Final[Path] = (
    BACKUP_ROOT
    / "AQSD_PROJECT"
)

DATA_BACKUP_DIR: Final[Path] = (
    BACKUP_ROOT
    / "AQSD_DATA"
)


# ==========================================================
# DIRECTORY INITIALIZATION
# ==========================================================

def ensure_aqsd_directories() -> None:
    """
    Create AQSD data and backup directory structure.
    """

    directories = (
        DATA_ROOT,

        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        HISTORICAL_DATA_DIR,
        DATABASE_DIR,
        TEMP_DATA_DIR,
        OUTPUT_DATA_DIR,

        NSE_RAW_DIR,
        NSE_DERIVATIVES_RAW_DIR,

        NSE_PROCESSED_DIR,
        NSE_DERIVATIVES_PROCESSED_DIR,

        NSE_HISTORICAL_DIR,

        BACKUP_ROOT,
        PROJECT_BACKUP_DIR,
        DATA_BACKUP_DIR,

        LOGS_DIR,
        OUTPUT_DIR,
    )

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    """
    Display AQSD filesystem architecture.
    """

    print()
    print("=" * 100)
    print("AQSD CENTRAL PATH CONFIGURATION")
    print("=" * 100)

    print(
        f"Project Root               : "
        f"{PROJECT_ROOT}"
    )

    print(
        f"Primary Data Root          : "
        f"{DATA_ROOT}"
    )

    print(
        f"Backup Root                : "
        f"{BACKUP_ROOT}"
    )

    print("-" * 100)

    print(
        f"NSE Raw Derivatives        : "
        f"{NSE_DERIVATIVES_RAW_DIR}"
    )

    print(
        f"NSE Processed Derivatives  : "
        f"{NSE_DERIVATIVES_PROCESSED_DIR}"
    )

    print(
        f"NSE Historical Database    : "
        f"{NSE_FNO_HISTORICAL_DB}"
    )

    print("-" * 100)

    print(
        f"D: Data Root Exists        : "
        f"{'YES' if DATA_ROOT.exists() else 'NO'}"
    )

    print(
        f"E: Backup Root Exists      : "
        f"{'YES' if BACKUP_ROOT.exists() else 'NO'}"
    )

    print("=" * 100)


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    ensure_aqsd_directories()

    show_status()