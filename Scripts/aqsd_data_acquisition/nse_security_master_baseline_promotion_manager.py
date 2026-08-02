"""
AQSD
NSE Security Master Baseline Promotion Manager

Module : SMD-007
Version: 1.0.0
Author : AQSD

Purpose
-------
Safely promote the latest validated AQSD Security Master to become
the persistent Security Master baseline.

Normal behaviour
----------------
- Reads SMD-005 change summary.
- Reads current enriched Security Master.
- Reads existing persistent baseline.
- Does NOT replace baseline automatically.
- If NO CHANGE exists, baseline remains untouched.
- If changes exist, explicit --approve is required.
- Existing baseline is archived before replacement.
- Promotion is recorded in an audit JSON.

Protection
----------
- Historical NSE F&O database is never modified.
- Existing Security Master baseline is never silently overwritten.
- Promotion must be deliberate and auditable.
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

MODULE_ID = "SMD-007"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

SECURITY_MASTER_DIR = (
    PROJECT_ROOT
    / "Data"
    / "Security_Master"
)

SNAPSHOT_HISTORY_DIR = (
    SECURITY_MASTER_DIR
    / "Snapshots"
)

CURRENT_MASTER = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

BASELINE_MASTER = (
    SECURITY_MASTER_DIR
    / "AQSD_Security_Master_Baseline.csv"
)

BASELINE_METADATA = (
    SECURITY_MASTER_DIR
    / "AQSD_Security_Master_Baseline.json"
)

CHANGE_SUMMARY = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Change_Summary.json"
)

PROMOTION_AUDIT = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Promotion_Audit.json"
)


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    SECURITY_MASTER_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SNAPSHOT_HISTORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def timestamp() -> str:

    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def filename_timestamp() -> str:

    return datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_json(
    path: Path,
) -> dict[str, object]:

    if not path.exists():
        raise FileNotFoundError(
            f"Required JSON file not found: {path}"
        )

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"Invalid JSON file: {path}"
        ) from exc


def load_master(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Security Master not found: {path}"
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


# ============================================================
# VALIDATION
# ============================================================

def validate_master(
    dataframe: pd.DataFrame,
) -> dict[str, int]:

    rows = len(
        dataframe
    )

    symbol_series = (
        dataframe["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    id_series = (
        dataframe["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    blank_symbols = int(
        symbol_series.eq("").sum()
    )

    duplicate_symbols = int(
        symbol_series[
            symbol_series.ne("")
        ]
        .duplicated(
            keep=False
        )
        .sum()
    )

    blank_security_ids = int(
        id_series.eq("").sum()
    )

    duplicate_security_ids = int(
        id_series[
            id_series.ne("")
        ]
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


# ============================================================
# CHANGE SUMMARY
# ============================================================

def read_change_status() -> dict[str, object]:

    summary = load_json(
        CHANGE_SUMMARY
    )

    total_changes = int(
        summary.get(
            "total_changes",
            0,
        )
        or 0
    )

    return {
        "total_changes": total_changes,
        "new_securities": int(
            summary.get(
                "new_securities",
                0,
            )
            or 0
        ),
        "removed_securities": int(
            summary.get(
                "removed_securities",
                0,
            )
            or 0
        ),
        "symbol_changes": int(
            summary.get(
                "symbol_changes",
                0,
            )
            or 0
        ),
        "fno_status_changes": int(
            summary.get(
                "fno_status_changes",
                0,
            )
            or 0
        ),
        "structural_changes": int(
            summary.get(
                "structural_changes",
                0,
            )
            or 0
        ),
        "change_status": str(
            summary.get(
                "status",
                "UNKNOWN",
            )
        ),
    }


# ============================================================
# ARCHIVE BASELINE
# ============================================================

def archive_existing_baseline() -> Path | None:

    if not BASELINE_MASTER.exists():
        return None

    archive_file = (
        SNAPSHOT_HISTORY_DIR
        / (
            "AQSD_Security_Master_Baseline_"
            + filename_timestamp()
            + ".csv"
        )
    )

    shutil.copy2(
        BASELINE_MASTER,
        archive_file,
    )

    return archive_file


# ============================================================
# PROMOTION
# ============================================================

def promote_baseline(
    *,
    approved: bool,
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
            "Current Security Master failed validation. "
            f"Critical Issues: "
            f"{validation['critical_issues']}"
        )

    change = read_change_status()

    total_changes = int(
        change[
            "total_changes"
        ]
    )

    current_hash = sha256_file(
        CURRENT_MASTER
    )

    baseline_hash_before = None

    if BASELINE_MASTER.exists():

        baseline_hash_before = sha256_file(
            BASELINE_MASTER
        )

    # --------------------------------------------------------
    # NO CHANGE
    # --------------------------------------------------------

    if total_changes == 0:

        result = {
            "module_id":
                MODULE_ID,
            "module_version":
                MODULE_VERSION,
            "generated_at":
                timestamp(),
            "status":
                "NO PROMOTION REQUIRED",
            "promoted":
                False,
            "reason":
                "SMD-005 detected no Security Master changes.",
            "rows":
                validation[
                    "rows"
                ],
            "total_changes":
                0,
            "baseline_hash_before":
                baseline_hash_before,
            "current_hash":
                current_hash,
            "historical_database_modified":
                False,
        }

        save_audit(
            result
        )

        return result

    # --------------------------------------------------------
    # CHANGES EXIST BUT NOT APPROVED
    # --------------------------------------------------------

    if not approved:

        result = {
            "module_id":
                MODULE_ID,
            "module_version":
                MODULE_VERSION,
            "generated_at":
                timestamp(),
            "status":
                "APPROVAL REQUIRED",
            "promoted":
                False,
            "reason":
                "Security Master changes detected. "
                "Explicit --approve required.",
            "rows":
                validation[
                    "rows"
                ],
            "total_changes":
                total_changes,
            "new_securities":
                change[
                    "new_securities"
                ],
            "removed_securities":
                change[
                    "removed_securities"
                ],
            "symbol_changes":
                change[
                    "symbol_changes"
                ],
            "fno_status_changes":
                change[
                    "fno_status_changes"
                ],
            "structural_changes":
                change[
                    "structural_changes"
                ],
            "baseline_hash_before":
                baseline_hash_before,
            "current_hash":
                current_hash,
            "historical_database_modified":
                False,
        }

        save_audit(
            result
        )

        return result

    # --------------------------------------------------------
    # APPROVED PROMOTION
    # --------------------------------------------------------

    archived_baseline = archive_existing_baseline()

    shutil.copy2(
        CURRENT_MASTER,
        BASELINE_MASTER,
    )

    baseline_hash_after = sha256_file(
        BASELINE_MASTER
    )

    metadata = {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "promoted_at":
            timestamp(),
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
            baseline_hash_after,
        "promotion_policy":
            "EXPLICIT_APPROVAL_ONLY",
        "historical_database_modified":
            False,
        "status":
            "SUCCESS",
    }

    BASELINE_METADATA.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "generated_at":
            timestamp(),
        "status":
            "PROMOTED",
        "promoted":
            True,
        "rows":
            validation[
                "rows"
            ],
        "total_changes":
            total_changes,
        "new_securities":
            change[
                "new_securities"
            ],
        "removed_securities":
            change[
                "removed_securities"
            ],
        "symbol_changes":
            change[
                "symbol_changes"
            ],
        "fno_status_changes":
            change[
                "fno_status_changes"
            ],
        "structural_changes":
            change[
                "structural_changes"
            ],
        "archived_baseline":
            (
                str(
                    archived_baseline
                )
                if archived_baseline
                else None
            ),
        "baseline_hash_before":
            baseline_hash_before,
        "baseline_hash_after":
            baseline_hash_after,
        "historical_database_modified":
            False,
    }

    save_audit(
        result
    )

    return result


# ============================================================
# AUDIT
# ============================================================

def save_audit(
    result: dict[str, object],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROMOTION_AUDIT.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_result(
    result: dict[str, object],
) -> None:

    print()
    print("=" * 82)
    print("AQSD SECURITY MASTER BASELINE PROMOTION MANAGER")
    print("=" * 82)

    print(
        f"Module                     : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                    : "
        f"{MODULE_VERSION}"
    )

    print("-" * 82)

    print(
        f"Current Master             : "
        f"{CURRENT_MASTER}"
    )

    print(
        f"Persistent Baseline        : "
        f"{BASELINE_MASTER}"
    )

    print(
        f"Rows                       : "
        f"{int(result.get('rows', 0) or 0):,}"
    )

    print(
        f"Total Detected Changes     : "
        f"{int(result.get('total_changes', 0) or 0)}"
    )

    if int(
        result.get(
            "total_changes",
            0,
        )
        or 0
    ) > 0:

        print(
            f"New Securities             : "
            f"{int(result.get('new_securities', 0) or 0)}"
        )

        print(
            f"Removed Securities         : "
            f"{int(result.get('removed_securities', 0) or 0)}"
        )

        print(
            f"Symbol Changes             : "
            f"{int(result.get('symbol_changes', 0) or 0)}"
        )

        print(
            f"F&O Status Changes         : "
            f"{int(result.get('fno_status_changes', 0) or 0)}"
        )

        print(
            f"Structural Changes         : "
            f"{int(result.get('structural_changes', 0) or 0)}"
        )

    print("-" * 82)

    print(
        f"Promoted                   : "
        f"{result.get('promoted', False)}"
    )

    print(
        "Promotion Policy           : EXPLICIT APPROVAL ONLY"
    )

    print(
        "Historical Database        : READ ONLY / UNTOUCHED"
    )

    print(
        f"Audit JSON                 : "
        f"{PROMOTION_AUDIT}"
    )

    reason = result.get(
        "reason"
    )

    if reason:

        print(
            f"Reason                     : "
            f"{reason}"
        )

    print("-" * 82)

    print(
        f"Status                     : "
        f"{result.get('status', 'UNKNOWN')}"
    )

    print("=" * 82)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "AQSD Security Master Baseline Promotion Manager"
        )
    )

    parser.add_argument(
        "--approve",
        action="store_true",
        help=(
            "Explicitly approve promotion of detected "
            "Security Master changes."
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    arguments = parse_arguments()

    try:

        result = promote_baseline(
            approved=bool(
                arguments.approve
            )
        )

        display_result(
            result
        )

    except Exception as exc:

        print()
        print("=" * 82)
        print("AQSD SECURITY MASTER BASELINE PROMOTION MANAGER")
        print("=" * 82)

        print(
            "Status                     : FAILED"
        )

        print(
            f"Reason                     : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 82)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()