"""
AQSD
NSE F&O Daily Historical Database Update

Module : FDB-003
Version: 1.0.0
Author : AQSD

Purpose
-------
Safely update the AQSD NSE F&O historical database during normal
daily operation.

Rules
-----
1. Historical baseline remains frozen.
2. Full rebuild is never used.
3. Existing complete sessions are skipped.
4. Only new/incomplete processed sessions may be handled by FDB-001.
5. NDQ-001 validation remains mandatory through FDB-001.
6. No historical data is fabricated.
7. No historical baseline is deleted.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


MODULE_ID = "FDB-003"
MODULE_VERSION = "1.0.0"

AQSD_ROOT = Path(__file__).resolve().parents[2]

PYTHON_EXE = AQSD_ROOT / ".venv-fyers" / "Scripts" / "python.exe"

FREEZE_MODULE = (
    "Scripts.aqsd_data_acquisition."
    "nse_fno_database_freeze_guard"
)

BUILDER_MODULE = (
    "Scripts.aqsd_data_acquisition."
    "nse_fno_historical_database_builder"
)


def print_header() -> None:
    print()
    print("=" * 80)
    print("AQSD NSE F&O DAILY DATABASE UPDATE")
    print("=" * 80)
    print(f"Module             : {MODULE_ID}")
    print(f"Version            : {MODULE_VERSION}")
    print(
        "Started            : "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("Mode               : SAFE INCREMENTAL / APPEND ONLY")
    print("Historical Rebuild : PROHIBITED")
    print("=" * 80)


def run_command(
    command: list[str],
    *,
    description: str,
) -> None:
    print()
    print("-" * 80)
    print(description)
    print("-" * 80)

    result = subprocess.run(
        command,
        cwd=AQSD_ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{description} failed "
            f"with exit code {result.returncode}."
        )


def validate_environment() -> None:
    if not PYTHON_EXE.exists():
        raise FileNotFoundError(
            "AQSD Python environment not found:\n"
            f"{PYTHON_EXE}"
        )


def check_freeze_guard() -> None:
    """
    Confirm historical database freeze protection is active.
    """

    run_command(
        [
            str(PYTHON_EXE),
            "-m",
            FREEZE_MODULE,
            "--status",
        ],
        description="STEP 1 - DATABASE FREEZE STATUS",
    )


def run_incremental_builder() -> None:
    """
    Run FDB-001 in its normal incremental mode.

    IMPORTANT:
    --rebuild is intentionally never supplied.
    """

    run_command(
        [
            str(PYTHON_EXE),
            "-m",
            BUILDER_MODULE,
        ],
        description="STEP 2 - SAFE INCREMENTAL DATABASE UPDATE",
    )


def main() -> None:
    print_header()

    try:
        validate_environment()

        check_freeze_guard()

        run_incremental_builder()

    except Exception as exc:
        print()
        print("=" * 80)
        print("AQSD DAILY DATABASE UPDATE")
        print("=" * 80)
        print("Status : FAILED")
        print(
            f"Reason : {type(exc).__name__}: {exc}"
        )
        print("=" * 80)

        raise SystemExit(1) from exc

    print()
    print("=" * 80)
    print("AQSD DAILY DATABASE UPDATE")
    print("=" * 80)
    print("Historical Baseline : PRESERVED")
    print("Full Rebuild        : NOT USED")
    print("Incremental Update  : COMPLETED")
    print("Status              : SUCCESS")
    print("=" * 80)


if __name__ == "__main__":
    main()