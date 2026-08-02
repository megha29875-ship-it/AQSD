"""
AQSD
NSE Security Master Orchestrator

Module : SMD-008
Version: 1.0.0
Author : AQSD

Purpose
-------
Run the complete AQSD Security Master pipeline in the correct order.

Pipeline
--------
SMD-001  Security Master Builder
SMD-002  Security Master Validator
SMD-003  Security Master Enrichment Builder
SMD-004  Security Master Enrichment Validator
SMD-005  Security Master Change Detector
SMD-006  Security Master Snapshot Manager
SMD-007  Security Master Baseline Promotion Manager

Important protection
--------------------
- Historical database remains READ ONLY.
- Historical rebuild is never used.
- Baseline promotion is never auto-approved.
- Any failed module stops the pipeline immediately.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-008"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PYTHON_EXE = (
    PROJECT_ROOT
    / ".venv-fyers"
    / "Scripts"
    / "python.exe"
)


# ============================================================
# PIPELINE
# ============================================================

PIPELINE = [
    (
        "SMD-001",
        "Security Master Builder",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_builder",
        [],
    ),
    (
        "SMD-002",
        "Security Master Validator",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_validator",
        [],
    ),
    (
        "SMD-003",
        "Security Master Enrichment Builder",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_enrichment_builder",
        [],
    ),
    (
        "SMD-004",
        "Security Master Enrichment Validator",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_enrichment_validator",
        [],
    ),
    (
        "SMD-005",
        "Security Master Change Detector",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_change_detector",
        [],
    ),
    (
        "SMD-006",
        "Security Master Snapshot Manager",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_snapshot_manager",
        [
            "--status",
        ],
    ),
    (
        "SMD-007",
        "Security Master Baseline Promotion Manager",
        "Scripts.aqsd_data_acquisition."
        "nse_security_master_baseline_promotion_manager",
        [],
    ),
]


# ============================================================
# HELPERS
# ============================================================

def print_header() -> None:

    print()
    print("=" * 88)
    print("AQSD SECURITY MASTER ORCHESTRATOR")
    print("=" * 88)

    print(
        f"Module                     : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                    : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Started                    : "
        f"{datetime.now().astimezone().isoformat(timespec='seconds')}"
    )

    print(
        "Mode                       : CONTROLLED PIPELINE"
    )

    print(
        "Historical Database        : READ ONLY / UNTOUCHED"
    )

    print(
        "Historical Rebuild         : NOT USED"
    )

    print(
        "Baseline Auto Promotion    : PROHIBITED"
    )

    print("=" * 88)


def validate_environment() -> None:

    if not PYTHON_EXE.exists():

        raise FileNotFoundError(
            "AQSD Python environment not found:\n"
            f"{PYTHON_EXE}"
        )


def run_module(
    *,
    module_id: str,
    label: str,
    module_path: str,
    arguments: list[str],
) -> dict[str, object]:

    print()
    print("-" * 88)

    print(
        f"{module_id} - {label}"
    )

    print("-" * 88)

    command = [
        str(
            PYTHON_EXE
        ),
        "-m",
        module_path,
        *arguments,
    ]

    started = time.perf_counter()

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    )

    elapsed = round(
        time.perf_counter()
        - started,
        2,
    )

    if result.returncode != 0:

        print()

        print(
            f"{module_id} Result               : FAILED"
        )

        print(
            f"{module_id} Exit Code            : "
            f"{result.returncode}"
        )

        print(
            f"{module_id} Time                 : "
            f"{elapsed} sec"
        )

        raise RuntimeError(
            f"{module_id} - {label} failed "
            f"with exit code {result.returncode}."
        )

    print()

    print(
        f"{module_id} Result               : SUCCESS"
    )

    print(
        f"{module_id} Time                 : "
        f"{elapsed} sec"
    )

    return {
        "module_id":
            module_id,
        "label":
            label,
        "status":
            "SUCCESS",
        "seconds":
            elapsed,
    }


# ============================================================
# ORCHESTRATOR
# ============================================================

def run_pipeline() -> list[dict[str, object]]:

    results: list[
        dict[str, object]
    ] = []

    for (
        module_id,
        label,
        module_path,
        arguments,
    ) in PIPELINE:

        result = run_module(
            module_id=module_id,
            label=label,
            module_path=module_path,
            arguments=arguments,
        )

        results.append(
            result
        )

    return results


# ============================================================
# SUMMARY
# ============================================================

def display_summary(
    results: list[dict[str, object]],
) -> None:

    total_seconds = round(
        sum(
            float(
                row.get(
                    "seconds",
                    0,
                )
            )
            for row in results
        ),
        2,
    )

    print()
    print("=" * 88)
    print("AQSD SECURITY MASTER PIPELINE SUMMARY")
    print("=" * 88)

    for row in results:

        print(
            f"{row['module_id']:<10} "
            f"{row['status']:<10} "
            f"{row['seconds']:>8} sec  "
            f"{row['label']}"
        )

    print("-" * 88)

    print(
        f"Modules Completed          : "
        f"{len(results)}/{len(PIPELINE)}"
    )

    print(
        f"Total Pipeline Time        : "
        f"{total_seconds} sec"
    )

    print(
        "Historical Database        : UNTOUCHED"
    )

    print(
        "Historical Rebuild         : NOT USED"
    )

    print(
        "Baseline Auto Promotion    : NOT USED"
    )

    print(
        "Security Master            : READY"
    )

    print("-" * 88)

    print(
        "Status                     : SUCCESS"
    )

    print("=" * 88)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print_header()

    try:

        validate_environment()

        results = run_pipeline()

        display_summary(
            results
        )

    except Exception as exc:

        print()
        print("=" * 88)
        print("AQSD SECURITY MASTER ORCHESTRATOR")
        print("=" * 88)

        print(
            "Status                     : FAILED"
        )

        print(
            f"Reason                     : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "Pipeline                   : STOPPED"
        )

        print(
            "Historical Database        : UNTOUCHED"
        )

        print(
            "Baseline Auto Promotion    : NOT USED"
        )

        print("=" * 88)

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()