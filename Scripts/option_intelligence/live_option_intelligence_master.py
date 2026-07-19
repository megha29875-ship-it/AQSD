"""
AQSD
LIVE OPTION INTELLIGENCE MASTER
"""

from __future__ import annotations

import subprocess
import sys
import time

from dataclasses import dataclass


@dataclass
class PipelineStep:
    number: int
    title: str
    module: str


PIPELINE_STEPS = [
    PipelineStep(
        1,
        "Live Decision Engine",
        "Scripts.option_intelligence.live_decision_runner",
    ),
    PipelineStep(
        2,
        "Live IV Surface",
        "Scripts.option_intelligence.live_iv_surface_runner",
    ),
    PipelineStep(
        3,
        "Live Volatility Analytics",
        "Scripts.option_intelligence.live_volatility_analytics_runner",
    ),
    PipelineStep(
        4,
        "Live Probability V2",
        "Scripts.option_intelligence.live_probability_v2_runner",
    ),
    PipelineStep(
        5,
        "Professional Dashboard",
        "Scripts.option_intelligence.professional_option_dashboard_live",
    ),
]


def run_step(step: PipelineStep) -> bool:
    """
    Execute one AQSD module.
    """

    print()
    print("=" * 80)
    print(f"STEP {step.number} : {step.title}")
    print("=" * 80)

    start = time.time()

    if step.module.endswith(
        "professional_option_dashboard_live"
    ):
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                step.module,
            ]
        )

        elapsed = time.time() - start

        print()
        print(
            f"DASHBOARD OPENED ({elapsed:.1f} sec)"
        )

        return True

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            step.module,
        ]
    )

    elapsed = time.time() - start

    if result.returncode == 0:
        print()
        print(f"SUCCESS ({elapsed:.1f} sec)")
        return True

    print()
    print(f"FAILED ({elapsed:.1f} sec)")
    return False


def run_pipeline() -> None:
    """
    Run all AQSD Option Intelligence modules.
    """

    print()
    print("=" * 80)
    print("AQSD LIVE OPTION INTELLIGENCE")
    print("=" * 80)

    for step in PIPELINE_STEPS:
        success = run_step(step)

        if not success:
            print()
            print("PIPELINE STOPPED.")
            return

    print()
    print("=" * 80)
    print("ALL MODULES COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    run_pipeline()