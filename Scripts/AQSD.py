
"""
AQSD Professional
Master Controller
Version: 1.0
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
OUTPUT_FILE = BASE_DIR / "Output" / "Dashboard.xlsx"

UPDATE_SCRIPT = SCRIPTS_DIR / "update_fno_nse_v2.py"
SCANNER_SCRIPT = SCRIPTS_DIR / "scanner.py"
MARKET_PULSE_SCRIPT = SCRIPTS_DIR / "market_pulse.py"
FORMAT_SCRIPT = SCRIPTS_DIR / "format_dashboard.py"


def run_script(label: str, script_path: Path) -> None:
    if not script_path.exists():
        raise FileNotFoundError(f"{label} script was not found:\n{script_path}")

    print("\n" + "=" * 58)
    print(label)
    print("=" * 58)

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(SCRIPTS_DIR),
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}."
        )


def open_dashboard() -> None:
    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(f"Dashboard was not created:\n{OUTPUT_FILE}")

    if os.name == "nt":
        os.startfile(OUTPUT_FILE)
    else:
        print(f"\nOpen this file manually:\n{OUTPUT_FILE}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete AQSD workflow."
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Use the existing FnO_Stocks.xlsx without updating it.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open Dashboard.xlsx after completion.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    start_time = time.perf_counter()

    print("\n" + "=" * 58)
    print("AQSD PROFESSIONAL v1.0")
    print("NSE F&O OPTION BUYING & INVESTMENT WORKSTATION")
    print("=" * 58)

    try:
        if not args.skip_update:
            run_script(
                "STEP 1/4 - UPDATE NSE F&O UNIVERSE",
                UPDATE_SCRIPT,
            )
        else:
            print("\nSTEP 1/4 - NSE update skipped.")

        run_script(
            "STEP 2/4 - SCAN F&O STOCKS",
            SCANNER_SCRIPT,
        )
        run_script(
            "STEP 3/4 - CREATE MARKET PULSE",
            MARKET_PULSE_SCRIPT,
        )
        run_script(
            "STEP 4/4 - FORMAT DASHBOARD",
            FORMAT_SCRIPT,
        )

    except (FileNotFoundError, RuntimeError) as error:
        print("\nAQSD STOPPED")
        print(error)
        raise SystemExit(1)

    elapsed = time.perf_counter() - start_time

    print("\n" + "=" * 58)
    print("AQSD COMPLETED SUCCESSFULLY")
    print(f"Time taken: {elapsed:.1f} seconds")
    print(f"Dashboard: {OUTPUT_FILE}")
    print("=" * 58)

    if not args.no_open:
        try:
            open_dashboard()
        except OSError as error:
            print(f"\nDashboard created, but could not be opened: {error}")


if __name__ == "__main__":
    main()
