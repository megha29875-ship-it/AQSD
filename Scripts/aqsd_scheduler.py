
"""
AQSD Professional
Module: AQSD Scheduler
Version: 1.0

Runs common AQSD workflows from one place.

Examples
--------
python aqsd_scheduler.py morning
python aqsd_scheduler.py evening
python aqsd_scheduler.py backup
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

TASKS = {
    "morning": [
        ("Configuration Sync", "config_sync.py"),
        ("Morning Checklist", "morning_checklist.py"),
        ("Daily Scan", "AQSD.py", "--mode", "daily", "--skip-update"),
    ],
    "evening": [
        ("Portfolio Update", "AQSD.py", "--mode", "portfolio"),
        ("Performance Dashboard", "performance_dashboard.py"),
        ("Trade Report", "daily_trading_report.py"),
        ("Auto Backup", "auto_backup.py"),
    ],
    "backup": [
        ("Auto Backup", "auto_backup.py"),
    ],
}

def run_task(task):
    name, script, *args = task
    print("="*70)
    print(name)
    print("="*70)
    cmd=[sys.executable, str(SCRIPTS/script), *args]
    start=time.time()
    result=subprocess.run(cmd,cwd=SCRIPTS)
    elapsed=time.time()-start
    if result.returncode==0:
        print(f"✓ Completed in {elapsed:.1f}s\n")
    else:
        print(f"✗ Failed ({result.returncode})\n")
        return False
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=TASKS.keys())
    args=p.parse_args()
    ok=0
    total=len(TASKS[args.mode])
    for t in TASKS[args.mode]:
        if run_task(t):
            ok+=1
    print("="*70)
    print(f"AQSD Scheduler finished: {ok}/{total} successful")
    print("="*70)

if __name__=="__main__":
    main()
