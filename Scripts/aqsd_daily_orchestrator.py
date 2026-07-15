
"""
AQSD Professional
Module: Daily Orchestrator
Version: 1.0

Purpose
-------
Runs AQSD modules in the correct daily sequence with one command.

Supported modes
---------------
--full
    Price update + all active intelligence + decision + portfolio

--morning
    Same as --full, intended for the normal daily workflow

--prices-only
    Incremental price update and status check only

--intelligence-only
    Runs intelligence modules using existing cached prices

--status
    Shows availability of all orchestrated modules

--dry-run
    Prints commands without executing them

Examples
--------
python aqsd_daily_orchestrator.py --full
python aqsd_daily_orchestrator.py --morning
python aqsd_daily_orchestrator.py --prices-only
python aqsd_daily_orchestrator.py --intelligence-only
python aqsd_daily_orchestrator.py --status
python aqsd_daily_orchestrator.py --full --continue-on-error
python aqsd_daily_orchestrator.py --full --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


# ============================================================
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"
LOG_DIR = BASE_DIR / "Logs"
DASHBOARD = OUTPUT_DIR / "Dashboard.xlsx"

RUN_LOG = LOG_DIR / "aqsd_orchestrator_runs.jsonl"


# ============================================================
# MODULE DEFINITIONS
# ============================================================

@dataclass(frozen=True)
class Step:
    name: str
    script: str
    arguments: tuple[str, ...]
    optional: bool = False
    requires_dashboard_closed: bool = False
    description: str = ""

    @property
    def script_path(self) -> Path:
        return SCRIPTS_DIR / self.script

    @property
    def command(self) -> list[str]:
        return [
            sys.executable,
            str(self.script_path),
            *self.arguments,
        ]


PRICE_STEPS = [
    Step(
        name="Incremental Price Update",
        script="aqsd_incremental_updater.py",
        arguments=("--update",),
        description="Downloads only missing recent OHLCV data.",
    ),
    Step(
        name="Price Cache Status",
        script="aqsd_incremental_updater.py",
        arguments=("--status",),
        description="Checks cached-price freshness.",
    ),
]

INTELLIGENCE_STEPS = [
    Step(
        name="Price Structure Intelligence",
        script="aqsd_price_structure.py",
        arguments=("--run",),
        requires_dashboard_closed=True,
        description="Calculates swings, BOS, CHOCH, ATR, ADX and structure.",
    ),
    Step(
        name="Relative Strength Intelligence",
        script="aqsd_relative_strength.py",
        arguments=("--run",),
        description="Ranks stocks versus market and sector.",
    ),
    Step(
        name="Market Breadth Intelligence",
        script="aqsd_market_breadth.py",
        arguments=("--run",),
        requires_dashboard_closed=True,
        description="Calculates advances, declines and moving-average breadth.",
    ),
    Step(
        name="Sector Rotation Intelligence",
        script="aqsd_sector_rotation.py",
        arguments=("--run",),
        requires_dashboard_closed=True,
        description="Ranks sectors and sector leaders.",
    ),
    Step(
        name="Global & Commodity Intelligence",
        script="aqsd_global_intelligence.py",
        arguments=("--update",),
        optional=True,
        requires_dashboard_closed=True,
        description="Updates global indices, currencies and commodities.",
    ),
    Step(
        name="Unified Master Intelligence",
        script="aqsd_unified_master_intelligence.py",
        arguments=("--run",),
        requires_dashboard_closed=True,
        description="Combines all available intelligence engines.",
    ),
    Step(
        name="Trade Decision Engine",
        script="aqsd_decision_engine.py",
        arguments=("--run",),
        requires_dashboard_closed=True,
        description="Creates actions, entries, stops and targets.",
    ),
    Step(
        name="Portfolio Allocation",
        script="aqsd_portfolio_allocator.py",
        arguments=("--run",),
        description="Suggests capital allocation across actionable trades.",
    ),
    Step(
        name="Database Optimizer",
        script="aqsd_database_optimizer.py",
        arguments=("--optimize",),
        optional=True,
        description="Runs ANALYZE, REINDEX and VACUUM.",
    ),
]

OPTIONAL_DATA_STEPS = [
    Step(
        name="News Intelligence Report",
        script="aqsd_news_intelligence.py",
        arguments=("--report",),
        optional=True,
        requires_dashboard_closed=True,
        description="Rebuilds news report when news events exist.",
    ),
    Step(
        name="Macro Intelligence Report",
        script="aqsd_macro_intelligence.py",
        arguments=("--report",),
        optional=True,
        requires_dashboard_closed=True,
        description="Rebuilds macro report when macro events exist.",
    ),
    Step(
        name="Futures Intelligence Report",
        script="aqsd_futures_intelligence.py",
        arguments=("--report",),
        optional=True,
        requires_dashboard_closed=True,
        description="Rebuilds futures report when derivatives data exists.",
    ),
    Step(
        name="Options Intelligence Report",
        script="aqsd_options_intelligence.py",
        arguments=("--report",),
        optional=True,
        requires_dashboard_closed=True,
        description="Rebuilds options report when options data exists.",
    ),
]


# ============================================================
# RESULT MODEL
# ============================================================

@dataclass
class StepResult:
    name: str
    script: str
    status: str
    started_at: str
    completed_at: str
    duration_seconds: float
    return_code: int | None
    optional: bool
    command: list[str]
    message: str
    stdout_tail: str = ""
    stderr_tail: str = ""


# ============================================================
# FILE / PROCESS HELPERS
# ============================================================

def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def tail_text(text: str, lines: int = 20) -> str:
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def dashboard_may_be_open() -> bool:
    """
    A reliable cross-platform Excel lock check is not guaranteed.

    On Windows, Excel commonly creates a temporary lock file such as:
        ~$Dashboard.xlsx
    """

    lock_file = DASHBOARD.with_name(f"~${DASHBOARD.name}")
    return lock_file.exists()


def validate_step(step: Step) -> tuple[bool, str]:
    if not step.script_path.exists():
        return False, f"Missing script: {step.script_path}"

    return True, ""


def append_run_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with RUN_LOG.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


# ============================================================
# EXECUTION
# ============================================================

def run_step(
    step: Step,
    *,
    dry_run: bool,
    timeout_seconds: int,
) -> StepResult:
    started = now_text()
    start_clock = time.perf_counter()

    valid, message = validate_step(step)

    if not valid:
        status = "SKIPPED" if step.optional else "FAILED"

        return StepResult(
            name=step.name,
            script=step.script,
            status=status,
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0.0,
            return_code=None,
            optional=step.optional,
            command=step.command,
            message=message,
        )

    if (
        step.requires_dashboard_closed
        and dashboard_may_be_open()
    ):
        return StepResult(
            name=step.name,
            script=step.script,
            status="FAILED",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0.0,
            return_code=None,
            optional=step.optional,
            command=step.command,
            message=(
                "Dashboard.xlsx appears to be open. "
                "Close Excel and run again."
            ),
        )

    if dry_run:
        return StepResult(
            name=step.name,
            script=step.script,
            status="DRY RUN",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0.0,
            return_code=None,
            optional=step.optional,
            command=step.command,
            message="Command not executed.",
        )

    try:
        process = subprocess.run(
            step.command,
            cwd=SCRIPTS_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        duration = round(
            time.perf_counter() - start_clock,
            2,
        )

        status = (
            "SUCCESS"
            if process.returncode == 0
            else "FAILED"
        )

        message = (
            "Completed successfully."
            if process.returncode == 0
            else f"Process returned code {process.returncode}."
        )

        return StepResult(
            name=step.name,
            script=step.script,
            status=status,
            started_at=started,
            completed_at=now_text(),
            duration_seconds=duration,
            return_code=process.returncode,
            optional=step.optional,
            command=step.command,
            message=message,
            stdout_tail=tail_text(process.stdout),
            stderr_tail=tail_text(process.stderr),
        )

    except subprocess.TimeoutExpired as error:
        duration = round(
            time.perf_counter() - start_clock,
            2,
        )

        stdout = (
            error.stdout.decode()
            if isinstance(error.stdout, bytes)
            else error.stdout or ""
        )
        stderr = (
            error.stderr.decode()
            if isinstance(error.stderr, bytes)
            else error.stderr or ""
        )

        return StepResult(
            name=step.name,
            script=step.script,
            status="FAILED",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=duration,
            return_code=None,
            optional=step.optional,
            command=step.command,
            message=(
                f"Timed out after {timeout_seconds} seconds."
            ),
            stdout_tail=tail_text(stdout),
            stderr_tail=tail_text(stderr),
        )

    except Exception as error:
        duration = round(
            time.perf_counter() - start_clock,
            2,
        )

        return StepResult(
            name=step.name,
            script=step.script,
            status="FAILED",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=duration,
            return_code=None,
            optional=step.optional,
            command=step.command,
            message=str(error),
        )


def run_workflow(
    steps: Iterable[Step],
    *,
    mode: str,
    dry_run: bool,
    continue_on_error: bool,
    timeout_seconds: int,
) -> list[StepResult]:
    step_list = list(steps)
    results: list[StepResult] = []

    print("\nAQSD DAILY ORCHESTRATOR")
    print("=" * 84)
    print(f"Mode: {mode}")
    print(f"Started: {now_text()}")
    print(f"Steps: {len(step_list)}")
    print(f"Dry run: {'YES' if dry_run else 'NO'}")
    print("=" * 84)

    for index, step in enumerate(
        step_list,
        start=1,
    ):
        print(
            f"\n[{index}/{len(step_list)}] "
            f"{step.name}"
        )
        print("-" * 84)
        print(
            "Command: "
            + " ".join(
                f'"{part}"'
                if " " in part
                else part
                for part in step.command
            )
        )

        result = run_step(
            step,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )
        results.append(result)

        print(f"Status: {result.status}")
        print(f"Duration: {result.duration_seconds:.2f} seconds")
        print(f"Message: {result.message}")

        if result.stdout_tail:
            print("\nOutput:")
            print(result.stdout_tail)

        if result.stderr_tail:
            print("\nError output:")
            print(result.stderr_tail)

        append_run_log(
            {
                "workflow_mode": mode,
                **asdict(result),
            }
        )

        if result.status == "FAILED":
            if step.optional:
                print(
                    "\nOptional step failed. "
                    "Workflow will continue."
                )
                continue

            if continue_on_error:
                print(
                    "\nRequired step failed, but "
                    "--continue-on-error is active."
                )
                continue

            print(
                "\nWorkflow stopped because a "
                "required step failed."
            )
            break

    return results


# ============================================================
# STATUS
# ============================================================

def show_status() -> None:
    all_steps = (
        PRICE_STEPS
        + INTELLIGENCE_STEPS
        + OPTIONAL_DATA_STEPS
    )

    print("\nAQSD ORCHESTRATOR STATUS")
    print("=" * 100)
    print(f"Scripts folder: {SCRIPTS_DIR}")
    print(f"Dashboard: {DASHBOARD}")
    print(
        "Dashboard lock: "
        + (
            "POSSIBLY OPEN"
            if dashboard_may_be_open()
            else "NOT DETECTED"
        )
    )
    print("-" * 100)
    print(
        f"{'Module':<38}"
        f"{'Script':<38}"
        f"{'State':<12}"
        f"{'Optional'}"
    )
    print("-" * 100)

    for step in all_steps:
        state = (
            "READY"
            if step.script_path.exists()
            else "MISSING"
        )

        print(
            f"{step.name:<38}"
            f"{step.script:<38}"
            f"{state:<12}"
            f"{'YES' if step.optional else 'NO'}"
        )

    print("=" * 100)


# ============================================================
# SUMMARY
# ============================================================

def show_summary(
    results: list[StepResult],
) -> None:
    success = sum(
        result.status == "SUCCESS"
        for result in results
    )
    failed = sum(
        result.status == "FAILED"
        for result in results
    )
    skipped = sum(
        result.status == "SKIPPED"
        for result in results
    )
    dry_run = sum(
        result.status == "DRY RUN"
        for result in results
    )

    total_duration = round(
        sum(
            result.duration_seconds
            for result in results
        ),
        2,
    )

    print("\nAQSD ORCHESTRATOR SUMMARY")
    print("=" * 84)
    print(f"Successful: {success}")
    print(f"Failed:     {failed}")
    print(f"Skipped:    {skipped}")
    print(f"Dry run:    {dry_run}")
    print(f"Duration:   {total_duration:.2f} seconds")
    print(f"Log file:   {RUN_LOG}")

    if failed:
        print("\nFailed steps:")

        for result in results:
            if result.status == "FAILED":
                print(
                    f"- {result.name}: "
                    f"{result.message}"
                )

    print("=" * 84)


# ============================================================
# CLI
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AQSD modules in the correct "
            "daily sequence."
        )
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--full",
        action="store_true",
        help=(
            "Run price update and all active "
            "intelligence modules."
        ),
    )

    mode.add_argument(
        "--morning",
        action="store_true",
        help="Run the normal AQSD morning workflow.",
    )

    mode.add_argument(
        "--prices-only",
        action="store_true",
        help="Run only the price updater and status.",
    )

    mode.add_argument(
        "--intelligence-only",
        action="store_true",
        help=(
            "Run intelligence using existing "
            "cached prices."
        ),
    )

    mode.add_argument(
        "--status",
        action="store_true",
        help="Show module availability.",
    )

    parser.add_argument(
        "--include-optional-data",
        action="store_true",
        help=(
            "Also rebuild News, Macro, Futures "
            "and Options reports."
        ),
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "Continue after a required module fails."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them.",
    )

    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
        help=(
            "Maximum time allowed per module. "
            "Default: 30 minutes."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.prices_only:
        mode = "PRICES ONLY"
        steps = PRICE_STEPS

    elif args.intelligence_only:
        mode = "INTELLIGENCE ONLY"
        steps = INTELLIGENCE_STEPS

    else:
        mode = (
            "MORNING"
            if args.morning
            else "FULL"
        )
        steps = PRICE_STEPS + INTELLIGENCE_STEPS

    if args.include_optional_data:
        steps = steps + OPTIONAL_DATA_STEPS

    timeout_seconds = max(
        1,
        args.timeout_minutes,
    ) * 60

    results = run_workflow(
        steps,
        mode=mode,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
        timeout_seconds=timeout_seconds,
    )

    show_summary(results)

    required_failures = [
        result
        for result in results
        if (
            result.status == "FAILED"
            and not result.optional
        )
    ]

    if required_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
