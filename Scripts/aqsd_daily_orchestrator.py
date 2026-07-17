"""
AQSD Daily Orchestrator v1.0

Runs the complete AQSD analytics pipeline in sequence.

Example:
python aqsd_daily_orchestrator.py --run --underlying BANKNIFTY
python aqsd_daily_orchestrator.py --status
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "Scripts"
OUTPUT = BASE / "Output"

LOG_FILE = OUTPUT / "AQSD_Run_Log.txt"
SUMMARY_FILE = OUTPUT / "AQSD_Run_Summary.csv"

PYTHON = Path(sys.executable)

PIPELINE = [
    (
        "Futures Analytics",
        "aqsd_fyers_futures_analytics.py",
        ["--run", "--underlying", "{underlying}"],
        False,
    ),
    (
        "Option Chain Analytics",
        "aqsd_fyers_option_chain_analytics.py",
        ["--run", "--underlying", "{underlying}", "--expiry", "NEAR", "--strikes", "20"],
        False,
    ),
    (
        "Options Intelligence",
        "aqsd_options_intelligence.py",
        ["--run", "--underlying", "{underlying}"],
        False,
    ),
    (
        "Decision Engine",
        "aqsd_decision_engine.py",
        ["--run", "--underlying", "{underlying}"],
        True,
    ),
    (
        "Risk Engine",
        "aqsd_risk_engine.py",
        ["--run"],
        True,
    ),
    (
        "Portfolio Engine",
        "aqsd_portfolio_engine.py",
        ["--run"],
        True,
    ),
    (
        "AI Alert Engine",
        "aqsd_ai_alert_engine.py",
        ["--run"],
        True,
    ),
    (
        "Command Center",
        "aqsd_command_center.py",
        ["--run"],
        True,
    ),
]


def log(message: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run_step(
    name: str,
    script_name: str,
    arguments: list[str],
    underlying: str,
    required: bool,
) -> dict:
    script_path = SCRIPTS / script_name

    if not script_path.exists():
        status = "FAILED" if required else "SKIPPED"
        message = f"{script_name} not found"
        log(f"{name}: {status} - {message}")
        return {
            "step": name,
            "script": script_name,
            "status": status,
            "return_code": "",
            "message": message,
        }

    formatted_arguments = [
        value.format(underlying=underlying)
        for value in arguments
    ]

    command = [
        str(PYTHON),
        str(script_path),
        *formatted_arguments,
    ]

    log(f"{name}: STARTED")

    try:
        result = subprocess.run(
            command,
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        log(f"{name}: FAILED - timeout")
        return {
            "step": name,
            "script": script_name,
            "status": "FAILED",
            "return_code": "",
            "message": "Timeout after 300 seconds",
        }
    except Exception as exc:
        log(f"{name}: FAILED - {exc}")
        return {
            "step": name,
            "script": script_name,
            "status": "FAILED",
            "return_code": "",
            "message": str(exc),
        }

    if result.stdout.strip():
        log(f"{name} OUTPUT:\n{result.stdout.strip()}")

    if result.stderr.strip():
        log(f"{name} ERROR:\n{result.stderr.strip()}")

    if result.returncode == 0:
        status = "SUCCESS"
        message = "Completed"
    else:
        status = "FAILED"
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown error"
        )

    log(f"{name}: {status}")

    return {
        "step": name,
        "script": script_name,
        "status": status,
        "return_code": result.returncode,
        "message": message[:500],
    }


def save_summary(rows: list[dict]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_time",
        "step",
        "script",
        "status",
        "return_code",
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
            fieldnames=fieldnames,
        )

        if not file_exists:
            writer.writeheader()

        run_time = datetime.now().isoformat(timespec="seconds")

        for row in rows:
            writer.writerow(
                {
                    "run_time": run_time,
                    **row,
                }
            )


def run_pipeline(underlying: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    log("=" * 80)
    log(f"AQSD PIPELINE STARTED FOR {underlying}")
    log(f"Python: {PYTHON}")

    results = []

    for name, script, args, required in PIPELINE:
        result = run_step(
            name,
            script,
            args,
            underlying,
            required,
        )
        results.append(result)

        if required and result["status"] == "FAILED":
            log(
                f"Pipeline stopped because required step "
                f"'{name}' failed."
            )
            break

    save_summary(results)

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

    log("-" * 80)
    log(f"Successful: {successful}")
    log(f"Failed:     {failed}")
    log(f"Skipped:    {skipped}")
    log(f"Summary:    {SUMMARY_FILE}")
    log(f"Log:        {LOG_FILE}")
    log("AQSD PIPELINE FINISHED")
    log("=" * 80)


def show_status() -> None:
    print("\nAQSD DAILY ORCHESTRATOR STATUS")
    print("=" * 84)
    print(f"Python: {PYTHON}")
    print(f"Base:   {BASE}")
    print("-" * 84)

    for name, script, _, required in PIPELINE:
        path = SCRIPTS / script
        state = "FOUND" if path.exists() else "MISSING"
        requirement = "REQUIRED" if required else "OPTIONAL"
        print(f"{name:<25} {state:<10} {requirement:<10} {path.name}")

    print("=" * 84)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Daily Orchestrator"
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--underlying",
        default="BANKNIFTY",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.run:
        run_pipeline(
            args.underlying.strip().upper()
        )
        return

    raise SystemExit(
        "Use --status or --run --underlying BANKNIFTY"
    )


if __name__ == "__main__":
    main()
