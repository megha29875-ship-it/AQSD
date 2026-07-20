"""
AQSD
LIVE OPTION INTELLIGENCE MASTER

Module: live_option_intelligence_master.py
Version: 2.0
Author: AQSD

Purpose:
Run all Option Intelligence analytics modules and save the
latest Decision Intelligence snapshot to the SQLite history database.

Important:
- This master does not open the dashboard.
- The dashboard should be opened once from the Control Center.
- The open dashboard reloads automatically when output changes.
"""

from __future__ import annotations

import subprocess
import sys
import time

from dataclasses import dataclass

from Scripts.option_intelligence.history_database import (
    DECISION_JSON_FILE,
    build_snapshot,
    connect_database,
    create_database_schema,
    load_json_file,
    save_snapshot,
)


# ============================================================
# PIPELINE MODEL
# ============================================================

@dataclass(frozen=True)
class PipelineStep:
    """
    One Option Intelligence pipeline module.
    """

    number: int
    title: str
    module: str


# ============================================================
# PIPELINE STEPS
# ============================================================

PIPELINE_STEPS = [
    PipelineStep(
        number=1,
        title="Live Decision Engine",
        module=(
            "Scripts.option_intelligence."
            "live_decision_runner"
        ),
    ),
    PipelineStep(
        number=2,
        title="Live IV Surface",
        module=(
            "Scripts.option_intelligence."
            "live_iv_surface_runner"
        ),
    ),
    PipelineStep(
        number=3,
        title="Live Volatility Analytics",
        module=(
            "Scripts.option_intelligence."
            "live_volatility_analytics_runner"
        ),
    ),
    PipelineStep(
        number=4,
        title="Live Probability V2",
        module=(
            "Scripts.option_intelligence."
            "live_probability_v2_runner"
        ),
    ),
]


# ============================================================
# PIPELINE EXECUTION
# ============================================================

def run_step(
    step: PipelineStep,
) -> bool:
    """
    Execute one AQSD Python module.

    Returns:
        True when the module completes successfully.
        False when the module returns an error.
    """

    print()
    print("=" * 80)
    print(
        f"STEP {step.number} : {step.title}"
    )
    print("=" * 80)

    start_time = time.time()

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                step.module,
            ],
            check=False,
        )

    except Exception as error:
        elapsed = (
            time.time()
            - start_time
        )

        print()
        print(
            f"FAILED ({elapsed:.1f} sec)"
        )
        print(
            f"Error: {error}"
        )

        return False

    elapsed = (
        time.time()
        - start_time
    )

    if result.returncode == 0:
        print()
        print(
            f"SUCCESS ({elapsed:.1f} sec)"
        )

        return True

    print()
    print(
        f"FAILED ({elapsed:.1f} sec)"
    )
    print(
        f"Return code: {result.returncode}"
    )

    return False


# ============================================================
# HISTORY DATABASE
# ============================================================

def save_pipeline_history() -> bool:
    """
    Save the latest Decision Intelligence JSON to SQLite.

    Returns:
        True when the history operation completes successfully.
        False when the history operation fails.
    """

    print()
    print("=" * 80)
    print("STEP 5 : SAVE OPTION INTELLIGENCE HISTORY")
    print("=" * 80)

    start_time = time.time()

    try:
        data = load_json_file(
            DECISION_JSON_FILE
        )

        snapshot = build_snapshot(
            data
        )

        with connect_database() as connection:
            create_database_schema(
                connection
            )

            inserted = save_snapshot(
                connection,
                snapshot,
            )

        elapsed = (
            time.time()
            - start_time
        )

        print()

        if inserted:
            print(
                "HISTORY SNAPSHOT SAVED SUCCESSFULLY"
            )
        else:
            print(
                "HISTORY SNAPSHOT ALREADY EXISTS "
                "FOR THIS TIMESTAMP"
            )

        print(
            f"SUCCESS ({elapsed:.1f} sec)"
        )

        return True

    except Exception as error:
        elapsed = (
            time.time()
            - start_time
        )

        print()
        print(
            f"HISTORY SAVE FAILED ({elapsed:.1f} sec)"
        )
        print(
            f"Error: {error}"
        )

        return False


# ============================================================
# MASTER PIPELINE
# ============================================================

def run_pipeline() -> bool:
    """
    Run all Option Intelligence analytics modules.

    The dashboard is not launched from this master. After all analytics
    modules complete, the latest Decision Intelligence snapshot is stored
    in the history database.
    """

    pipeline_start = time.time()

    print()
    print("=" * 80)
    print("AQSD LIVE OPTION INTELLIGENCE")
    print("=" * 80)
    print()
    print(
        "Dashboard launch disabled in analytics pipeline."
    )
    print(
        "The existing dashboard will update automatically."
    )

    for step in PIPELINE_STEPS:
        success = run_step(
            step
        )

        if not success:
            print()
            print("=" * 80)
            print(
                f"PIPELINE STOPPED AT STEP {step.number}"
            )
            print("=" * 80)

            return False

    history_success = save_pipeline_history()

    if not history_success:
        print()
        print("=" * 80)
        print(
            "ANALYTICS COMPLETED, BUT HISTORY SAVE FAILED"
        )
        print("=" * 80)

        return False

    total_elapsed = (
        time.time()
        - pipeline_start
    )

    print()
    print("=" * 80)
    print("ALL MODULES COMPLETED SUCCESSFULLY")
    print(
        f"TOTAL TIME: {total_elapsed:.1f} sec"
    )
    print("=" * 80)

    return True


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Run the complete Option Intelligence pipeline.
    """

    success = run_pipeline()

    if not success:
        raise SystemExit(
            1
        )


if __name__ == "__main__":
    main()