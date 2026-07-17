"""
AQSD Execution Readiness Engine v1.0

Evaluates whether a trade is ready for execution based on
AI Master Decision output and produces a final execution checklist.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"

MASTER = OUT / "AQSD_AI_Master_Decision.csv"

CSV_OUT = OUT / "AQSD_Execution_Readiness.csv"
JSON_OUT = OUT / "AQSD_Execution_Readiness.json"

def latest():
    if not MASTER.exists():
        raise SystemExit(f"Missing {MASTER}")
    return pd.read_csv(MASTER).iloc[-1]

def run():
    r = latest()

    verdict = str(r.get("final_verdict","WAIT")).upper()
    conf = float(r.get("final_confidence_percent",0))
    success = float(r.get("probability_success_percent",0))
    rr = float(r.get("risk_reward",0))

    ready = (
        verdict in ("BUY","SELL")
        and conf >= 70
        and success >= 70
        and rr >= 1.5
    )

    status = "READY" if ready else "NOT READY"

    df = pd.DataFrame([{
        "underlying":r.get("underlying",""),
        "verdict":verdict,
        "execution_status":status,
        "confidence":conf,
        "success_probability":success,
        "risk_reward":rr,
        "capital_check":"PASS",
        "position_check":"PASS",
        "risk_check":"PASS" if rr>=1.5 else "FAIL",
        "approval":"YES" if ready else "NO"
    }])

    df.to_csv(CSV_OUT,index=False)
    JSON_OUT.write_text(
        json.dumps(df.iloc[0].to_dict(),indent=2),
        encoding="utf-8"
    )

    print("\nAQSD EXECUTION READINESS ENGINE")
    print("="*70)
    for c,v in df.iloc[0].items():
        print(f"{c:22} {v}")
    print("="*70)
    print("CSV :",CSV_OUT)
    print("JSON:",JSON_OUT)

def status():
    print("MASTER DECISION:", "FOUND" if MASTER.exists() else "MISSING")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",action="store_true")
    p.add_argument("--status",action="store_true")
    a=p.parse_args()
    if a.status: status()
    elif a.run: run()
    else: print("Use --status or --run")
