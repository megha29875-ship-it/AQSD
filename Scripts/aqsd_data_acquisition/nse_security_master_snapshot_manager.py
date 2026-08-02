"""
AQSD
NSE Security Master Snapshot Manager

Module : SMD-006
Version: 1.0.0
Author : AQSD

Purpose
-------
Create and maintain a persistent baseline snapshot of the validated
AQSD enriched Security Master.

Why
---
SMD-005 can only detect real future changes if it compares the latest
Security Master against a preserved earlier baseline.

This module:
- reads AQSD_Security_Master_Enriched.csv
- creates a persistent baseline snapshot if one does not exist
- preserves the baseline during normal operation
- does not overwrite the baseline unless explicitly requested
- writes snapshot metadata

It does NOT:
- modify the frozen historical database
- rebuild historical data
- modify the source Security Master
- fabricate metadata
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-006"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

SNAPSHOT_DIR = PROJECT_ROOT / "Data" / "Security_Master"

CURRENT_MASTER = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

BASELINE_MASTER = (
    SNAPSHOT_DIR
    / "AQSD_Security_Master_Baseline.csv"
)

BASELINE_JSON = (
    SNAPSHOT_DIR
    / "AQSD_Security_Master_Baseline.json"
)

SNAPSHOT_HISTORY_DIR = (
    SNAPSHOT_DIR
    / "Snapshots"
)


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    SNAPSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SNAPSHOT_HISTORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def file_sha256(
    path: Path,
) -> str:

    hasher = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            hasher.update(
                chunk
            )

    return hasher.hexdigest()


def load_master(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Security Master file not found: {path}"
        )

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        str(column).strip().lower()
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:
        raise RuntimeError(
            "Security Master missing required columns: "
            + ", ".join(
                missing
            )
        )

    return dataframe


def validate_master(
    dataframe: pd.DataFrame,
) -> dict[str, int]:

    rows = len(
        dataframe
    )

    blank_symbols = int(
        dataframe["symbol"]
        .isna()
        .sum()
        +
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    duplicate_symbols = int(
        dataframe["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
        .duplicated(
            keep=False
        )
        .sum()
    )

    blank_security_ids = int(
        dataframe["security_id"]
        .isna()
        .sum()
        +
        dataframe["security_id"]
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    duplicate_security_ids = int(
        dataframe["security_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        .duplicated(
            keep=False
        )
        .sum()
    )

    critical_issues = sum(
        [
            blank_symbols,
            duplicate_symbols,
            blank_security_ids,
            duplicate_security_ids,
        ]
    )

    return {
        "rows": rows,
        "blank_symbols": blank_symbols,
        "duplicate_symbols": duplicate_symbols,
        "blank_security_ids": blank_security_ids,
        "duplicate_security_ids": duplicate_security_ids,
        "critical_issues": critical_issues,
    }


def timestamp_for_filename() -> str:

    return datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


# ============================================================
# BASELINE CREATION
# ============================================================

def create_baseline(
    *,
    force: bool = False,
) -> dict[str, object]:

    ensure_directories()

    current = load_master(
        CURRENT_MASTER
    )

    validation = validate_master(
        current
    )

    if validation[
        "critical_issues"
    ] != 0:
        raise RuntimeError(
            "Current Security Master failed baseline validation. "
            f"Critical Issues: "
            f"{validation['critical_issues']}"
        )

    if (
        BASELINE_MASTER.exists()
        and not force
    ):
        return {
            "status": "BASELINE EXISTS",
            "created": False,
            "rows": validation[
                "rows"
            ],
        }

    if (
        BASELINE_MASTER.exists()
        and force
    ):

        archive_name = (
            "AQSD_Security_Master_Baseline_"
            + timestamp_for_filename()
            + ".csv"
        )

        archive_path = (
            SNAPSHOT_HISTORY_DIR
            / archive_name
        )

        shutil.copy2(
            BASELINE_MASTER,
            archive_path,
        )

    shutil.copy2(
        CURRENT_MASTER,
        BASELINE_MASTER,
    )

    baseline_hash = file_sha256(
        BASELINE_MASTER
    )

    metadata = {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "created_at":
            datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        "source_file":
            str(
                CURRENT_MASTER
            ),
        "baseline_file":
            str(
                BASELINE_MASTER
            ),
        "rows":
            validation[
                "rows"
            ],
        "sha256":
            baseline_hash,
        "critical_issues":
            validation[
                "critical_issues"
            ],
        "historical_database_modified":
            False,
        "source_security_master_modified":
            False,
        "baseline_policy":
            "PERSISTENT_UNTIL_EXPLICIT_REPLACE",
        "status":
            "SUCCESS",
    }

    BASELINE_JSON.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "status": "SUCCESS",
        "created": True,
        "rows": validation[
            "rows"
        ],
        "sha256": baseline_hash,
    }


# ============================================================
# STATUS
# ============================================================

def baseline_status() -> dict[str, object]:

    ensure_directories()

    if not BASELINE_MASTER.exists():

        return {
            "exists": False,
            "status": "NOT CREATED",
        }

    baseline = load_master(
        BASELINE_MASTER
    )

    validation = validate_master(
        baseline
    )

    baseline_hash = file_sha256(
        BASELINE_MASTER
    )

    return {
        "exists": True,
        "status": (
            "VALID"
            if validation[
                "critical_issues"
            ] == 0
            else "REVIEW REQUIRED"
        ),
        "rows":
            validation[
                "rows"
            ],
        "critical_issues":
            validation[
                "critical_issues"
            ],
        "sha256":
            baseline_hash,
    }


# ============================================================
# DISPLAY
# ============================================================

def display_result(
    result: dict[str, object],
) -> None:

    print()
    print("=" * 80)
    print("AQSD SECURITY MASTER SNAPSHOT MANAGER")
    print("=" * 80)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print("-" * 80)

    print(
        f"Baseline File             : "
        f"{BASELINE_MASTER}"
    )

    print(
        f"Metadata File             : "
        f"{BASELINE_JSON}"
    )

    print(
        f"Baseline Exists           : "
        f"{result.get('exists', result.get('created', False))}"
    )

    if "rows" in result:

        print(
            f"Baseline Rows             : "
            f"{int(result.get('rows', 0) or 0):,}"
        )

    if "critical_issues" in result:

        print(
            f"Critical Issues           : "
            f"{int(result.get('critical_issues', 0) or 0)}"
        )

    if "sha256" in result:

        print(
            f"SHA256                    : "
            f"{result.get('sha256')}"
        )

    print("-" * 80)

    print(
        "Historical Database       : READ ONLY / UNTOUCHED"
    )

    print(
        "Current Security Master   : READ ONLY / UNCHANGED"
    )

    print(
        "Baseline Replacement      : EXPLICIT ONLY"
    )

    print("-" * 80)

    print(
        f"Status                    : "
        f"{result.get('status', 'UNKNOWN')}"
    )

    print("=" * 80)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "AQSD Security Master Snapshot Manager"
        )
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display existing baseline status."
        ),
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Explicitly replace the current baseline "
            "with the latest validated Security Master."
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    arguments = parse_arguments()

    try:

        if arguments.status:

            result = baseline_status()

            display_result(
                result
            )

            return

        if arguments.replace:

            result = create_baseline(
                force=True
            )

            display_result(
                result
            )

            return

        result = create_baseline(
            force=False
        )

        display_result(
            result
        )

    except Exception as exc:

        print()
        print("=" * 80)
        print("AQSD SECURITY MASTER SNAPSHOT MANAGER")
        print("=" * 80)

        print(
            "Status                    : FAILED"
        )

        print(
            f"Reason                    : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 80)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()