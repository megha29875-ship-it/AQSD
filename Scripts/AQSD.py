
"""
AQSD Professional
Master Controller
Version: 2.0

Modes
-----
daily:
    Update NSE list, scan stocks, create Market Pulse,
    format dashboard, add risk plan, and refresh analytics.

portfolio:
    Update portfolio CMP/MTM, trailing stop, trade journal,
    and performance analytics.

all:
    Run the daily workflow followed by the portfolio workflow.

setup-portfolio:
    Create/reset the Portfolio sheet using the current top trade.
    WARNING: this replaces the existing Portfolio sheet.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
OUTPUT_FILE = BASE_DIR / "Output" / "Dashboard.xlsx"

SCRIPTS = {
    "update": SCRIPTS_DIR / "update_fno_nse_v2.py",
    "scanner": SCRIPTS_DIR / "scanner.py",
    "market_pulse": SCRIPTS_DIR / "market_pulse.py",
    "format_dashboard": SCRIPTS_DIR / "format_dashboard.py",
    "risk_dashboard": SCRIPTS_DIR / "risk_dashboard.py",
    "portfolio_manager": SCRIPTS_DIR / "portfolio_manager.py",
    "portfolio_live": SCRIPTS_DIR / "portfolio_live_assistant.py",
    "trade_journal": SCRIPTS_DIR / "trade_journal.py",
    "analytics": SCRIPTS_DIR / "performance_analytics.py",
}


# ============================================================
# HELPERS
# ============================================================

def run_script(label: str, script_path: Path, required: bool = True) -> bool:
    """
    Run one AQSD module.

    Returns True when successful.
    If required=False, a missing script is skipped.
    """

    if not script_path.exists():
        if required:
            raise FileNotFoundError(
                f"{label} script was not found:\n{script_path}"
            )

        print(f"\nSKIPPED: {label}")
        print(f"Missing optional script: {script_path.name}")
        return False

    print("\n" + "=" * 64)
    print(label)
    print("=" * 64)

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(SCRIPTS_DIR),
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}."
        )

    return True


def open_dashboard() -> None:
    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            f"Dashboard was not created:\n{OUTPUT_FILE}"
        )

    if os.name == "nt":
        os.startfile(OUTPUT_FILE)  # type: ignore[attr-defined]
    else:
        print(f"\nOpen manually:\n{OUTPUT_FILE}")


def dashboard_has_sheet(sheet_name: str) -> bool:
    if not OUTPUT_FILE.exists():
        return False

    try:
        from openpyxl import load_workbook

        wb = load_workbook(
            OUTPUT_FILE,
            read_only=True,
            data_only=False,
        )

        exists = sheet_name in wb.sheetnames
        wb.close()
        return exists

    except Exception:
        return False


# ============================================================
# WORKFLOWS
# ============================================================

def run_daily(skip_update: bool) -> None:
    step = 1

    if skip_update:
        print("\nSTEP 1 - NSE F&O update skipped.")
    else:
        run_script(
            f"STEP {step} - UPDATE NSE F&O UNIVERSE",
            SCRIPTS["update"],
        )
    step += 1

    run_script(
        f"STEP {step} - SCAN NSE F&O STOCKS",
        SCRIPTS["scanner"],
    )
    step += 1

    run_script(
        f"STEP {step} - CREATE MARKET PULSE",
        SCRIPTS["market_pulse"],
    )
    step += 1

    run_script(
        f"STEP {step} - FORMAT PROFESSIONAL DASHBOARD",
        SCRIPTS["format_dashboard"],
    )
    step += 1

    run_script(
        f"STEP {step} - ADD RISK & POSITION PLAN",
        SCRIPTS["risk_dashboard"],
        required=False,
    )
    step += 1

    run_script(
        f"STEP {step} - REFRESH PERFORMANCE ANALYTICS",
        SCRIPTS["analytics"],
        required=False,
    )


def run_portfolio() -> None:
    if not dashboard_has_sheet("Portfolio"):
        raise RuntimeError(
            "Portfolio sheet is missing.\n"
            "Run: python AQSD.py --mode setup-portfolio"
        )

    if not dashboard_has_sheet("Trade Journal"):
        run_script(
            "CREATE TRADE JOURNAL",
            SCRIPTS["trade_journal"],
        )

    run_script(
        "UPDATE LIVE PORTFOLIO, MTM & TRAILING STOP",
        SCRIPTS["portfolio_live"],
    )

    run_script(
        "REFRESH TRADE JOURNAL",
        SCRIPTS["trade_journal"],
    )

    run_script(
        "REFRESH PERFORMANCE ANALYTICS",
        SCRIPTS["analytics"],
    )


def setup_portfolio() -> None:
    print("\nWARNING")
    print("This will replace the existing Portfolio sheet.")

    run_script(
        "CREATE / RESET PORTFOLIO SHEET",
        SCRIPTS["portfolio_manager"],
    )

    if not dashboard_has_sheet("Trade Journal"):
        run_script(
            "CREATE TRADE JOURNAL",
            SCRIPTS["trade_journal"],
        )

    run_script(
        "CREATE PERFORMANCE ANALYTICS",
        SCRIPTS["analytics"],
        required=False,
    )


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AQSD Professional workflows."
    )

    parser.add_argument(
        "--mode",
        choices=[
            "daily",
            "portfolio",
            "all",
            "setup-portfolio",
        ],
        default="daily",
        help=(
            "daily = scanner/dashboard; "
            "portfolio = MTM/journal; "
            "all = both; "
            "setup-portfolio = create/reset Portfolio sheet."
        ),
    )

    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Use the existing NSE F&O stock list.",
    )

    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open Dashboard.xlsx after completion.",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    args = parse_arguments()
    started = time.perf_counter()

    print("\n" + "=" * 64)
    print("AQSD PROFESSIONAL v2.0")
    print("NSE F&O TRADING, RISK & PORTFOLIO WORKSTATION")
    print("=" * 64)
    print(f"Mode: {args.mode}")

    try:
        if args.mode == "daily":
            run_daily(args.skip_update)

        elif args.mode == "portfolio":
            run_portfolio()

        elif args.mode == "all":
            run_daily(args.skip_update)

            if dashboard_has_sheet("Portfolio"):
                run_portfolio()
            else:
                print("\nPortfolio workflow skipped: Portfolio sheet not found.")
                print("Create it with:")
                print("python AQSD.py --mode setup-portfolio")

        elif args.mode == "setup-portfolio":
            setup_portfolio()

    except (FileNotFoundError, RuntimeError, PermissionError) as error:
        print("\n" + "=" * 64)
        print("AQSD STOPPED")
        print("=" * 64)
        print(error)

        if isinstance(error, PermissionError):
            print("\nClose Dashboard.xlsx in Excel and run again.")

        raise SystemExit(1)

    elapsed = time.perf_counter() - started

    print("\n" + "=" * 64)
    print("AQSD COMPLETED SUCCESSFULLY")
    print(f"Mode: {args.mode}")
    print(f"Time taken: {elapsed:.1f} seconds")
    print(f"Dashboard: {OUTPUT_FILE}")
    print("=" * 64)

    if not args.no_open and OUTPUT_FILE.exists():
        try:
            open_dashboard()
        except OSError as error:
            print(f"\nDashboard created but could not be opened: {error}")


if __name__ == "__main__":
    main()
