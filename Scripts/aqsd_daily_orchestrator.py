
"""
AQSD Professional
Module: Daily Orchestrator V2
Version: 2.0

Purpose
-------
Runs the complete AQSD daily workflow in the correct order.

New in V2
---------
- Includes Market Regime Engine
- Includes Alert Engine
- Includes Morning Brief Generator
- Includes System Audit
- Better pre-flight checks
- Dashboard-open detection
- Required vs optional step handling
- Dry-run mode
- Continue-on-error mode
- JSONL run log
- Clear final summary

Commands
--------
python aqsd_daily_orchestrator_v2.py --full
python aqsd_daily_orchestrator_v2.py --morning
python aqsd_daily_orchestrator_v2.py --intelligence-only
python aqsd_daily_orchestrator_v2.py --prices-only
python aqsd_daily_orchestrator_v2.py --status
python aqsd_daily_orchestrator_v2.py --full --dry-run
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


SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
OUTPUT_DIR = BASE_DIR / "Output"
LOG_DIR = BASE_DIR / "Logs"
DASHBOARD = OUTPUT_DIR / "Dashboard.xlsx"
RUN_LOG = LOG_DIR / "aqsd_orchestrator_v2_runs.jsonl"


@dataclass(frozen=True)
class Step:
    name: str
    script: str
    arguments: tuple[str, ...]
    required: bool = True
    needs_dashboard_closed: bool = False
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


@dataclass
class StepResult:
    name: str
    script: str
    status: str
    started_at: str
    completed_at: str
    duration_seconds: float
    return_code: int | None
    required: bool
    message: str
    stdout_tail: str = ""
    stderr_tail: str = ""


PRICE_STEPS = [
    Step(
        "Incremental Price Update",
        "aqsd_incremental_updater.py",
        ("--update",),
        required=True,
        description="Update missing daily OHLCV data.",
    ),
    Step(
        "Price Cache Status",
        "aqsd_incremental_updater.py",
        ("--status",),
        required=True,
        description="Check latest cached market-data date.",
    ),
]

CORE_INTELLIGENCE_STEPS = [
    Step(
        "Price Structure Intelligence",
        "aqsd_price_structure.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Relative Strength Intelligence",
        "aqsd_relative_strength.py",
        ("--run",),
        required=True,
    ),
    Step(
        "Market Breadth Intelligence",
        "aqsd_market_breadth.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Sector Rotation Intelligence",
        "aqsd_sector_rotation.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Global Intelligence",
        "aqsd_global_intelligence.py",
        ("--update",),
        required=False,
        needs_dashboard_closed=True,
    ),
    Step(
        "Unified Master Intelligence",
        "aqsd_unified_master_intelligence.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Trade Decision Engine",
        "aqsd_decision_engine.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Portfolio Allocation",
        "aqsd_portfolio_allocator.py",
        ("--run",),
        required=False,
    ),
    Step(
        "Market Regime Intelligence",
        "aqsd_market_regime.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Alert Intelligence Engine",
        "aqsd_alert_engine.py",
        ("--run",),
        required=True,
        needs_dashboard_closed=True,
    ),
    Step(
        "Morning Brief Generator",
        "aqsd_morning_brief.py",
        ("--run", "--top", "15"),
        required=True,
        needs_dashboard_closed=True,
    ),
]

MAINTENANCE_STEPS = [
    Step(
        "Database Optimizer",
        "aqsd_database_optimizer.py",
        ("--optimize",),
        required=False,
    ),
    Step(
        "System Audit",
        "aqsd_system_audit.py",
        ("--quick",),
        required=False,
    ),
]

OPTIONAL_DATA_STEPS = [
    Step(
        "News Intelligence Report",
        "aqsd_news_intelligence.py",
        ("--report",),
        required=False,
        needs_dashboard_closed=True,
    ),
    Step(
        "Macro Intelligence Report",
        "aqsd_macro_intelligence.py",
        ("--report",),
        required=False,
        needs_dashboard_closed=True,
    ),
    Step(
        "Futures Intelligence Report",
        "aqsd_futures_intelligence.py",
        ("--report",),
        required=False,
        needs_dashboard_closed=True,
    ),
    Step(
        "Options Intelligence Report",
        "aqsd_options_intelligence.py",
        ("--report",),
        required=False,
        needs_dashboard_closed=True,
    ),
]


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def tail_text(text: str, lines: int = 25) -> str:
    parts = str(text or "").splitlines()
    return "\n".join(parts[-lines:])


def dashboard_lock_detected() -> bool:
    lock_file = DASHBOARD.with_name(f"~${DASHBOARD.name}")
    return lock_file.exists()


def append_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with RUN_LOG.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


def preflight(steps: Iterable[Step]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for step in steps:
        if not step.script_path.exists():
            message = f"Missing script: {step.script}"

            if step.required:
                errors.append(message)
            else:
                warnings.append(message)

    if dashboard_lock_detected():
        errors.append(
            "Dashboard.xlsx appears to be open. Close Excel before running."
        )

    print("\nAQSD ORCHESTRATOR V2 PREFLIGHT")
    print("=" * 84)

    if errors:
        print("Errors:")
        for item in errors:
            print(f"- {item}")

    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")

    if not errors and not warnings:
        print("All required checks passed.")

    print("=" * 84)

    return not errors, warnings


def run_step(
    step: Step,
    *,
    dry_run: bool,
    timeout_seconds: int,
) -> StepResult:
    started = now_text()
    started_clock = time.perf_counter()

    if not step.script_path.exists():
        return StepResult(
            name=step.name,
            script=step.script,
            status="FAILED" if step.required else "SKIPPED",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0,
            return_code=None,
            required=step.required,
            message=f"Script not found: {step.script_path}",
        )

    if step.needs_dashboard_closed and dashboard_lock_detected():
        return StepResult(
            name=step.name,
            script=step.script,
            status="FAILED",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0,
            return_code=None,
            required=step.required,
            message="Dashboard.xlsx appears to be open.",
        )

    if dry_run:
        return StepResult(
            name=step.name,
            script=step.script,
            status="DRY RUN",
            started_at=started,
            completed_at=now_text(),
            duration_seconds=0,
            return_code=None,
            required=step.required,
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
            time.perf_counter() - started_clock,
            2,
        )

        return StepResult(
            name=step.name,
            script=step.script,
            status=(
                "SUCCESS"
                if process.returncode == 0
                else "FAILED"
            ),
            started_at=started,
            completed_at=now_text(),
            duration_seconds=duration,
            return_code=process.returncode,
            required=step.required,
            message=(
                "Completed successfully."
                if process.returncode == 0
                else f"Returned exit code {process.returncode}."
            ),
            stdout_tail=tail_text(process.stdout),
            stderr_tail=tail_text(process.stderr),
        )

    except subprocess.TimeoutExpired as error:
        duration = round(
            time.perf_counter() - started_clock,
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
            required=step.required,
            message=f"Timed out after {timeout_seconds} seconds.",
            stdout_tail=tail_text(error.stdout or ""),
            stderr_tail=tail_text(error.stderr or ""),
        )

    except Exception as error:
        duration = round(
            time.perf_counter() - started_clock,
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
            required=step.required,
            message=str(error),
        )


def execute_workflow(
    steps: list[Step],
    *,
    mode: str,
    dry_run: bool,
    continue_on_error: bool,
    timeout_seconds: int,
) -> list[StepResult]:
    results: list[StepResult] = []

    print("\nAQSD DAILY ORCHESTRATOR V2")
    print("=" * 84)
    print(f"Mode: {mode}")
    print(f"Started: {now_text()}")
    print(f"Steps: {len(steps)}")
    print("=" * 84)

    for index, step in enumerate(steps, start=1):
        print(
            f"\n[{index}/{len(steps)}] {step.name}"
        )
        print("-" * 84)
        print(
            "Command: "
            + " ".join(
                f'"{part}"' if " " in part else part
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
            print("\nError:")
            print(result.stderr_tail)

        append_log(
            {
                "mode": mode,
                **asdict(result),
            }
        )

        if result.status == "FAILED":
            if not step.required:
                print("Optional step failed; continuing.")
                continue

            if continue_on_error:
                print(
                    "Required step failed, but "
                    "--continue-on-error is active."
                )
                continue

            print("Workflow stopped.")
            break

    return results


def show_summary(results: list[StepResult]) -> None:
    successful = sum(
        item.status == "SUCCESS"
        for item in results
    )
    failed = sum(
        item.status == "FAILED"
        for item in results
    )
    skipped = sum(
        item.status == "SKIPPED"
        for item in results
    )
    dry = sum(
        item.status == "DRY RUN"
        for item in results
    )

    duration = round(
        sum(item.duration_seconds for item in results),
        2,
    )

    print("\nAQSD ORCHESTRATOR V2 SUMMARY")
    print("=" * 84)
    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Skipped:    {skipped}")
    print(f"Dry run:    {dry}")
    print(f"Duration:   {duration:.2f} seconds")
    print(f"Log:        {RUN_LOG}")

    failed_steps = [
        item
        for item in results
        if item.status == "FAILED"
    ]

    if failed_steps:
        print("\nFailed steps:")
        for item in failed_steps:
            print(f"- {item.name}: {item.message}")

    print("=" * 84)


def show_status() -> None:
    all_steps = (
        PRICE_STEPS
        + CORE_INTELLIGENCE_STEPS
        + MAINTENANCE_STEPS
        + OPTIONAL_DATA_STEPS
    )

    print("\nAQSD ORCHESTRATOR V2 STATUS")
    print("=" * 108)
    print(f"Scripts:   {SCRIPTS_DIR}")
    print(f"Dashboard: {DASHBOARD}")
    print(
        f"Excel lock: "
        f"{'DETECTED' if dashboard_lock_detected() else 'NOT DETECTED'}"
    )
    print("-" * 108)
    print(
        f"{'Module':<40}"
        f"{'Script':<38}"
        f"{'State':<12}"
        f"{'Required'}"
    )
    print("-" * 108)

    for step in all_steps:
        print(
            f"{step.name:<40}"
            f"{step.script:<38}"
            f"{'READY' if step.script_path.exists() else 'MISSING':<12}"
            f"{'YES' if step.required else 'NO'}"
        )

    print("=" * 108)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Daily Orchestrator V2."
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument("--full", action="store_true")
    mode.add_argument("--morning", action="store_true")
    mode.add_argument("--prices-only", action="store_true")
    mode.add_argument("--intelligence-only", action="store_true")
    mode.add_argument("--status", action="store_true")

    parser.add_argument(
        "--include-optional-data",
        action="store_true",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
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
        steps = CORE_INTELLIGENCE_STEPS + MAINTENANCE_STEPS

    else:
        mode = "MORNING" if args.morning else "FULL"
        steps = (
            PRICE_STEPS
            + CORE_INTELLIGENCE_STEPS
            + MAINTENANCE_STEPS
        )

    if args.include_optional_data:
        steps = steps + OPTIONAL_DATA_STEPS

    okay, _warnings = preflight(steps)

    if not okay and not args.dry_run:
        raise SystemExit(1)

    results = execute_workflow(
        steps,
        mode=mode,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
        timeout_seconds=max(
            1,
            args.timeout_minutes,
        ) * 60,
    )

    show_summary(results)

    required_failures = [
        item
        for item in results
        if item.status == "FAILED"
        and item.required
    ]

    if required_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
