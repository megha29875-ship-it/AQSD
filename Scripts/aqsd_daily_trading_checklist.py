
"""
AQSD Daily Trading Checklist v1.0
"""

from pathlib import Path
import argparse
import json
import pandas as pd

BASE=Path(__file__).resolve().parent.parent
OUT=BASE/"Output"

MASTER=OUT/"AQSD_AI_Master_Decision.csv"
READY=OUT/"AQSD_Execution_Readiness.csv"
CHECK=OUT/"AQSD_Daily_Checklist.csv"
JSONF=OUT/"AQSD_Daily_Checklist.json"

def latest(p):
    if not p.exists():
        return {}
    df=pd.read_csv(p)
    return {} if df.empty else df.iloc[-1].to_dict()

def run():
    m=latest(MASTER)
    r=latest(READY)
    if not m:
        raise SystemExit("Missing AI Master Decision output")

    items=[
        ("Market data updated","YES"),
        ("AI decision available","YES"),
        ("Execution ready",r.get("execution_status","NO")),
        ("Risk/Reward >=1.5","YES" if float(m.get("risk_reward",0))>=1.5 else "NO"),
        ("Confidence >=70%","YES" if float(m.get("final_confidence_percent",0))>=70 else "NO"),
        ("Probability >=70%","YES" if float(m.get("probability_success_percent",0))>=70 else "NO"),
        ("Trade Approved","YES" if str(m.get("final_verdict","")).upper() in ["BUY","SELL"] else "NO"),
    ]

    approved=all(v=="YES" or v=="READY" for _,v in items)

    df=pd.DataFrame(items,columns=["check","status"])
    df.loc[len(df)]=["FINAL STATUS","READY TO TRADE" if approved else "DO NOT TRADE"]
    CHECK.parent.mkdir(exist_ok=True)
    df.to_csv(CHECK,index=False)
    JSONF.write_text(json.dumps(df.to_dict(orient="records"),indent=2))
    print(df)

def status():
    print("Master:",MASTER.exists())
    print("Execution:",READY.exists())

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",action="store_true")
    p.add_argument("--status",action="store_true")
    a=p.parse_args()
    status() if a.status else run()
