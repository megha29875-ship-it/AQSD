"""
AQSD Unified Orchestrator v2.0

Runs the complete AQSD analytics pipeline in institutional sequence.

Pipeline
--------
1. Futures Analytics
2. Option Chain Analytics
3. Options Intelligence
4. Market Breadth
5. Decision Engine
6. Risk Engine
7. Portfolio Engine
8. Trade Approval Engine
9. Institutional Scoring Engine
10. AI Master Decision Engine
11. AI Alert Engine
12. Command Center

Outputs
-------
Output/AQSD_Unified_Run_Log.txt
Output/AQSD_Unified_Run_Summary.csv
Output/AQSD_Unified_Run_Status.json

Examples
--------
python aqsd_unified_orchestrator.py --status
python aqsd_unified_orchestrator.py --run --underlying BANKNIFTY
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "Scripts"
OUTPUT = BASE / "Output"

PYTHON = Path(sys.executable)

LOG_FILE = OUTPUT / "AQSD_Unified_Run_Log.txt"
SUMMARY_FILE = OUTPUT / "AQSD_Unified_Run_Summary.csv"
STATUS_FILE = OUTPUT / "AQSD_Unified_Run_Status.json"


PIPELINE = [
    {
        "name": "Futures Analytics",
        "script": "aqsd_fyers_futures_analytics.py",
        "args": ["--run", "--underlying", "{underlying}"],
        "required": True,
    },
    {
        "name": "Option Chain Analytics",
        "script": "aqsd_fyers_option_chain_analytics.py",
        "args": [
            "--run",
            "--underlying",
            "{underlying}",
            "--expiry",
            "NEAR",
            "--strikes",
            "20",
        ],
        "required": True,
    },
    {
        "name": "Options Intelligence",
        "script": "aqsd_options_intelligence.py",
        "args": ["--run", "--underlying", "{underlying}"],
        "required": True,
    },
    {
        "name": "Market Breadth",
        "script": "aqsd_market_breadth_engine.py",
        "args": ["--run"],
        "required": False,
    },
    {
        "name": "Decision Engine",
        "script": "aqsd_decision_engine.py",
        "args": ["--run", "--underlying", "{underlying}"],
        "required": True,
    },
    {
        "name": "Risk Engine",
        "script": "aqsd_risk_engine.py",
        "args": ["--run"],
        "required": True,
    },
    {
        "name": "Portfolio Engine",
        "script": "aqsd_portfolio_engine.py",
        "args": ["--run"],
        "required": True,
    },
    {
        "name": "Trade Approval Engine",
        "script": "aqsd_trade_approval_engine.py",
        "args": ["--run"],
        "required": True,
    },
    {
        "name": "Institutional Scoring Engine",
        "script": "aqsd_institutional_scoring_engine.py",
        "args": ["--run", "--underlying", "{underlying}"],
        "required": True,
    },
    {
        "name": "AI Master Decision Engine",
        "script": "aqsd_ai_master_decision_engine.py",
        "args": ["--run", "--underlying", "{underlying}"],
        "required": True,
    },
    {
        "name": "AI Alert Engine",
        "script": "aqsd_ai_alert_engine.py",
        "args": ["--run"],
        "required": True,
    },
    {
        "name": "Command Center",
        "script": "aqsd_command_center.py",
        "args": ["--run"],
        "required": True,
    },
]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    line = f"[{now_text()}] {message}"
    print(line)

    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run_step(
    step: dict[str, Any],
    underlying: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    name = step["name"]
    script_name = step["script"]
    required = bool(step["required"])
    script_path = SCRIPTS / script_name

    started_at = datetime.now()

    if not script_path.exists():
        status = "FAILED" if required else "SKIPPED"
        message = f"Script not found: {script_path}"

        log(f"{name}: {status} - {message}")

        return {
            "step": name,
            "script": script_name,
            "required": required,
            "status": status,
            "return_code": "",
            "duration_seconds": 0,
            "message": message,
        }

    arguments = [
        str(value).format(underlying=underlying)
        for value in step["args"]
    ]

    command = [
        str(PYTHON),
        str(script_path),
        *arguments,
    ]

    log(f"{name}: STARTED")

    try:
        result = subprocess.run(
            command,
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        duration = (
            datetime.now() - started_at
        ).total_seconds()

        message = (
            f"Timed out after {timeout_seconds} seconds"
        )

        log(f"{name}: FAILED - {message}")

        return {
            "step": name,
            "script": script_name,
            "required": required,
            "status": "FAILED",
            "return_code": "",
            "duration_seconds": round(duration, 2),
            "message": message,
        }
    except Exception as exc:
        duration = (
            datetime.now() - started_at
        ).total_seconds()

        log(f"{name}: FAILED - {exc}")

        return {
            "step": name,
            "script": script_name,
            "required": required,
            "status": "FAILED",
            "return_code": "",
            "duration_seconds": round(duration, 2),
            "message": str(exc),
        }

    duration = (
        datetime.now() - started_at
    ).total_seconds()

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        log(f"{name} OUTPUT:\n{stdout}")

    if stderr:
        log(f"{name} ERROR:\n{stderr}")

    if result.returncode == 0:
        status = "SUCCESS"
        message = "Completed"
    else:
        status = "FAILED"
        message = (
            stderr
            or stdout
            or "Unknown error"
        )

    log(
        f"{name}: {status} "
        f"({duration:.2f} seconds)"
    )

    return {
        "step": name,
        "script": script_name,
        "required": required,
        "status": status,
        "return_code": result.returncode,
        "duration_seconds": round(duration, 2),
        "message": message[:1000],
    }


def save_summary(
    run_id: str,
    underlying: str,
    rows: list[dict[str, Any]],
) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    fields = [
        "run_id",
        "run_time",
        "underlying",
        "step",
        "script",
        "required",
        "status",
        "return_code",
        "duration_seconds",
        "message",
    ]

    file_exists = SUMMARY_FILE.exists()

    with SUMMARY_FILE.open(
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        if not file_exists:
            writer.writeheader()

        run_time = datetime.now().isoformat(
            timespec="seconds"
        )

        for row in rows:
            writer.writerow(
                {
                    "run_id": run_id,
                    "run_time": run_time,
                    "underlying": underlying,
                    **row,
                }
            )


def save_status(
    run_id: str,
    underlying: str,
    rows: list[dict[str, Any]],
    total_duration: float,
) -> None:
    successful = sum(
        row["status"] == "SUCCESS"
        for row in rows
    )
    failed = sum(
        row["status"] == "FAILED"
        for row in rows
    )
    skipped = sum(
        row["status"] == "SKIPPED"
        for row in rows
    )

    required_failed = [
        row["step"]
        for row in rows
        if row["required"]
        and row["status"] == "FAILED"
    ]

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "underlying": underlying,
        "python": str(PYTHON),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "required_failures": required_failed,
        "pipeline_status": (
            "SUCCESS"
            if not required_failed
            else "FAILED"
        ),
        "total_duration_seconds": round(
            total_duration,
            2,
        ),
        "steps": rows,
    }

    STATUS_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def run_pipeline(
    underlying: str,
    timeout_seconds: int,
    continue_on_error: bool,
) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    pipeline_started = datetime.now()

    log("=" * 92)
    log(
        f"AQSD UNIFIED PIPELINE STARTED "
        f"FOR {underlying}"
    )
    log(f"Run ID: {run_id}")
    log(f"Python: {PYTHON}")
    log("=" * 92)

    results: list[dict[str, Any]] = []

    for step in PIPELINE:
        result = run_step(
            step,
            underlying,
            timeout_seconds,
        )

        results.append(result)

        if (
            result["required"]
            and result["status"] == "FAILED"
            and not continue_on_error
        ):
            log(
                "Pipeline stopped because required "
                f"step '{result['step']}' failed."
            )
            break

    total_duration = (
        datetime.now() - pipeline_started
    ).total_seconds()

    save_summary(
        run_id,
        underlying,
        results,
    )

    save_status(
        run_id,
        underlying,
        results,
        total_duration,
    )

    successful = sum(
        row["status"] == "SUCCESS"
        for row in results
    )
    failed = sum(
        row["status"] == "FAILED"
        for row in results
    )
    skipped = sum(
        row["status"] == "SKIPPED"
        for row in results
    )

    log("-" * 92)
    log(f"Successful: {successful}")
    log(f"Failed:     {failed}")
    log(f"Skipped:    {skipped}")
    log(
        f"Duration:   {total_duration:.2f} seconds"
    )
    log(f"Summary:    {SUMMARY_FILE}")
    log(f"Status:     {STATUS_FILE}")
    log(f"Log:        {LOG_FILE}")
    log("AQSD UNIFIED PIPELINE FINISHED")
    log("=" * 92)


def show_status() -> None:
    print("\nAQSD UNIFIED ORCHESTRATOR STATUS")
    print("=" * 96)
    print(f"Python: {PYTHON}")
    print(f"Base:   {BASE}")
    print("-" * 96)

    for index, step in enumerate(
        PIPELINE,
        start=1,
    ):
        script_path = SCRIPTS / step["script"]
        state = (
            "FOUND"
            if script_path.exists()
            else "MISSING"
        )
        requirement = (
            "REQUIRED"
            if step["required"]
            else "OPTIONAL"
        )

        print(
            f"{index:>2}. "
            f"{step['name']:<32} "
            f"{state:<10} "
            f"{requirement:<10} "
            f"{step['script']}"
        )

    print("=" * 96)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Unified Orchestrator v2"
    )

    parser.add_argument(
        "--run",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    parser.add_argument(
        "--underlying",
        default="BANKNIFTY",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds allowed per step.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue even when a required step fails.",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.run:
        run_pipeline(
            args.underlying.strip().upper(),
            max(args.timeout, 30),
            args.continue_on_error,
        )
        return

    raise SystemExit(
        "Use --status or "
        "--run --underlying BANKNIFTY"
    )


if __name__ == "__main__":
    main()
