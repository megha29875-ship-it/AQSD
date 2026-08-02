"""
AQSD
NSE F&O Historical Database Freeze Guard

Module : FDB-002
Version: 1.0.0
Author : AQSD

Purpose
-------
Protect the validated NSE F&O historical database baseline from
accidental full historical rebuilds.

Normal daily APPEND / INCREMENTAL processing remains allowed.

A full historical rebuild must be deliberately unlocked first.

Frozen baseline
---------------
Sessions        : 250
First Session   : 2025-07-25
Last Session    : 2026-07-31
Historical Rows : 9,760,876
Underlyings     : 249
Contract Master : 294,515

Principles
----------
- Historical baseline is immutable during normal operation.
- New trading sessions may be appended.
- Existing historical sessions must not be rebuilt accidentally.
- Unlocking is explicit and auditable.
"""

from __future__ import annotations

import argparse
import json

from datetime import datetime
from pathlib import Path
from typing import Final


# ==========================================================
# MODULE
# ==========================================================

MODULE_ID: Final[str] = "FDB-002"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# AQSD PATHS
# ==========================================================

AQSD_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

CONFIG_DIR: Final[Path] = AQSD_ROOT / "Config"

FREEZE_FILE: Final[Path] = (
    CONFIG_DIR
    / "NSE_FNO_Historical_Database_Freeze.json"
)


# ==========================================================
# FROZEN BASELINE
# ==========================================================

BASELINE: Final[dict[str, object]] = {
    "database": "NSE_FNO_Historical.db",
    "sessions": 250,
    "first_session": "2025-07-25",
    "last_session": "2026-07-31",
    "historical_rows": 9_760_876,
    "unique_underlyings": 249,
    "contract_master_rows": 294_515,
    "ndq_status": "SUCCESS",
    "critical_issues": 0,
}


# ==========================================================
# HELPERS
# ==========================================================

def ensure_config_directory() -> None:
    """
    Ensure AQSD Config directory exists.
    """

    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def utc_timestamp() -> str:
    """
    Return audit timestamp.
    """

    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def default_freeze_record() -> dict[str, object]:
    """
    Create the standard frozen-state record.
    """

    return {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "frozen": True,
        "frozen_at": utc_timestamp(),
        "unfrozen_at": None,
        "reason": (
            "Validated AQSD NSE F&O historical "
            "database baseline."
        ),
        "policy": (
            "APPEND_ONLY_NORMAL_OPERATION"
        ),
        "full_rebuild_allowed": False,
        "baseline": BASELINE,
    }


def write_record(
    record: dict[str, object],
) -> None:
    """
    Save freeze status atomically.
    """

    ensure_config_directory()

    temporary_file = FREEZE_FILE.with_suffix(
        ".json.tmp"
    )

    temporary_file.write_text(
        json.dumps(
            record,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        FREEZE_FILE
    )


def load_record() -> dict[str, object]:
    """
    Read the current freeze record.

    Missing freeze file defaults to frozen for safety.
    """

    if not FREEZE_FILE.exists():

        record = default_freeze_record()

        write_record(
            record
        )

        return record

    try:

        record = json.loads(
            FREEZE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "FDB-002 freeze file is invalid: "
            f"{FREEZE_FILE}"
        ) from exc

    return record


# ==========================================================
# PUBLIC API
# ==========================================================

def database_is_frozen() -> bool:
    """
    Return True when historical rebuild protection is active.
    """

    record = load_record()

    return bool(
        record.get(
            "frozen",
            True,
        )
    )


def assert_full_rebuild_allowed() -> None:
    """
    Block full historical rebuild while database is frozen.

    Incremental / append-only processing does not call this function.
    """

    if database_is_frozen():

        raise RuntimeError(
            "\n"
            "FDB-002 DATABASE FREEZE ACTIVE\n"
            "\n"
            "The AQSD NSE F&O historical baseline is frozen.\n"
            "Normal incremental / append-only updates are allowed.\n"
            "Full historical rebuild is BLOCKED.\n"
            "\n"
            "To intentionally unlock it, run:\n"
            "\n"
            "python -m "
            "Scripts.aqsd_data_acquisition."
            "nse_fno_database_freeze_guard "
            "--unfreeze\n"
        )


def freeze_database() -> None:
    """
    Activate historical database protection.
    """

    record = default_freeze_record()

    write_record(
        record
    )


def unfreeze_database() -> None:
    """
    Explicitly allow a manual historical rebuild.
    """

    record = load_record()

    record[
        "frozen"
    ] = False

    record[
        "unfrozen_at"
    ] = utc_timestamp()

    record[
        "full_rebuild_allowed"
    ] = True

    record[
        "policy"
    ] = "MANUAL_REBUILD_UNLOCKED"

    write_record(
        record
    )


def show_status() -> None:
    """
    Display current database freeze status.
    """

    record = load_record()

    baseline = record.get(
        "baseline",
        {},
    )

    frozen = bool(
        record.get(
            "frozen",
            True,
        )
    )

    print()
    print("=" * 78)
    print("AQSD NSE F&O HISTORICAL DATABASE FREEZE GUARD")
    print("=" * 78)

    print(
        f"Module                 : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Protection             : "
        f"{'FROZEN' if frozen else 'UNLOCKED'}"
    )

    print(
        f"Normal Daily Append    : ALLOWED"
    )

    print(
        f"Historical Rebuild     : "
        f"{'BLOCKED' if frozen else 'ALLOWED'}"
    )

    print("-" * 78)

    print(
        f"Baseline Sessions      : "
        f"{baseline.get('sessions', '')}"
    )

    print(
        f"First Session          : "
        f"{baseline.get('first_session', '')}"
    )

    print(
        f"Last Session           : "
        f"{baseline.get('last_session', '')}"
    )

    rows = int(
        baseline.get(
            "historical_rows",
            0,
        )
        or 0
    )

    print(
        f"Historical Rows        : "
        f"{rows:,}"
    )

    print(
        f"Unique Underlyings     : "
        f"{baseline.get('unique_underlyings', '')}"
    )

    contracts = int(
        baseline.get(
            "contract_master_rows",
            0,
        )
        or 0
    )

    print(
        f"Contract Master Rows   : "
        f"{contracts:,}"
    )

    print("-" * 78)

    print(
        f"Freeze File            : "
        f"{FREEZE_FILE}"
    )

    print(
        f"Policy                 : "
        f"{record.get('policy', '')}"
    )

    print("=" * 78)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Protect AQSD NSE F&O historical "
            "database from accidental rebuild."
        )
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--freeze",
        action="store_true",
        help=(
            "Freeze historical database baseline."
        ),
    )

    group.add_argument(
        "--unfreeze",
        action="store_true",
        help=(
            "Explicitly unlock historical rebuild."
        ),
    )

    group.add_argument(
        "--status",
        action="store_true",
        help=(
            "Display current freeze status."
        ),
    )

    return parser.parse_args()


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    if arguments.unfreeze:

        unfreeze_database()

        print()
        print(
            "WARNING: Historical database "
            "rebuild protection is now UNLOCKED."
        )

        show_status()

        return

    if arguments.freeze:

        freeze_database()

        print()
        print(
            "Historical database baseline "
            "has been FROZEN."
        )

        show_status()

        return

    # Default behaviour is safe:
    # create/restore freeze protection and show status.

    if not FREEZE_FILE.exists():
        freeze_database()

    show_status()


if __name__ == "__main__":
    main()