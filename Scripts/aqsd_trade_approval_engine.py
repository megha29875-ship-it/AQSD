
from pathlib import Path
import argparse
import json
from datetime import datetime
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"
DATA = BASE / "Data"

DECISION = OUT / "AQSD_Decision_Engine.csv"
RISK = OUT / "AQSD_Risk_Engine.csv"
CONFIG = DATA / "AQSD_Risk_Config.json"

CSV_OUT = OUT / "AQSD_Trade_Approval.csv"
JSON_OUT = OUT / "AQSD_Trade_Approval.json"
REJECT_OUT = OUT / "AQSD_Trade_Rejections.csv"

DEFAULTS = {
    "minimum_confidence_percent": 70.0,
    "minimum_risk_reward": 1.50,
    "minimum_score_spread": 15.0,
    "allowed_trade_grades": ["A+", "A", "B"],
    "minimum_expected_value": 0.0
}

def sf(v, d=0.0):
    try:
        x = float(v)
        return d if pd.isna(x) else x
    except Exception:
        return d

def latest(path):
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, low_memory=False)
        return {} if df.empty else df.iloc[-1].to_dict()
    except Exception:
        return {}

def rules():
    r = DEFAULTS.copy()
    if CONFIG.exists():
        try:
            c = json.loads(CONFIG.read_text(encoding="utf-8"))
            for k in r:
                if k in c:
                    r[k] = c[k]
        except Exception:
            pass
    return r

def calc_ev(action, pup, pdown, rr):
    wp = pup/100 if action == "BUY" else pdown/100 if action == "SELL" else 0
    return wp * max(rr, 0) - (1 - wp)

def run():
    d = latest(DECISION)
    rk = latest(RISK)
    if not d:
        raise SystemExit(f"Missing or empty: {DECISION}")

    r = rules()
    action = str(d.get("suggested_action","")).strip().upper()
    grade = str(d.get("trade_quality","")).strip().upper()
    conf = sf(d.get("confidence_percent"))
    rr = sf(d.get("risk_reward"))
    bull = sf(d.get("institutional_bull_score"))
    bear = sf(d.get("institutional_bear_score"))
    pup = sf(d.get("probability_up"))
    pdown = sf(d.get("probability_down"))
    spread = abs(bull-bear)
    ev = calc_ev(action,pup,pdown,rr)

    reasons = []
    if action not in {"BUY","SELL"}:
        reasons.append(f"Action is {action or 'EMPTY'}, not BUY or SELL")
    if conf < sf(r["minimum_confidence_percent"],70):
        reasons.append(f"Confidence {conf:.1f}% is below {sf(r['minimum_confidence_percent'],70):.1f}%")
    allowed = {str(x).upper() for x in r["allowed_trade_grades"]}
    if grade not in allowed:
        reasons.append(f"Trade quality {grade or 'EMPTY'} is not institutional grade")
    if rr < sf(r["minimum_risk_reward"],1.5):
        reasons.append(f"Risk/Reward {rr:.2f} is below {sf(r['minimum_risk_reward'],1.5):.2f}")
    if spread < sf(r["minimum_score_spread"],15):
        reasons.append(f"Score spread {spread:.1f} is below {sf(r['minimum_score_spread'],15):.1f}")
    risk_approval = str(rk.get("trade_approved","")).strip().upper()
    if risk_approval in {"NO","REJECTED","FALSE"}:
        reasons.append("Risk Engine rejected the trade")
    if ev <= sf(r["minimum_expected_value"],0):
        reasons.append(f"Expected value {ev:.3f} is not positive")

    approved = not reasons
    row = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "underlying": d.get("underlying",""),
        "spot_price": d.get("spot_price",""),
        "action": action,
        "trade_quality": grade,
        "confidence_percent": round(conf,1),
        "risk_reward": round(rr,2),
        "institutional_bull_score": round(bull,1),
        "institutional_bear_score": round(bear,1),
        "score_spread": round(spread,1),
        "expected_value": round(ev,3),
        "trade_approved": "YES" if approved else "NO",
        "approval_status": "INSTITUTIONAL TRADE APPROVED" if approved else "TRADE REJECTED",
        "rejection_reason_1": reasons[0] if len(reasons)>0 else "",
        "rejection_reason_2": reasons[1] if len(reasons)>1 else "",
        "rejection_reason_3": reasons[2] if len(reasons)>2 else "",
        "rejection_reason_4": reasons[3] if len(reasons)>3 else "",
        "rejection_reason_5": reasons[4] if len(reasons)>4 else "",
        "order_placement": "DISABLED"
    }

    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    df.to_csv(CSV_OUT,index=False,encoding="utf-8-sig")
    JSON_OUT.write_text(json.dumps(row,indent=2,default=str),encoding="utf-8")

    if not approved:
        hist = pd.read_csv(REJECT_OUT) if REJECT_OUT.exists() else pd.DataFrame()
        pd.concat([hist,df],ignore_index=True).to_csv(REJECT_OUT,index=False,encoding="utf-8-sig")

    print("\nAQSD INSTITUTIONAL TRADE APPROVAL ENGINE")
    print("="*78)
    print("Underlying:      ",row["underlying"])
    print("Action:          ",row["action"])
    print("Trade Quality:   ",row["trade_quality"])
    print("Confidence:      ",row["confidence_percent"])
    print("Risk/Reward:     ",row["risk_reward"])
    print("Score Spread:    ",row["score_spread"])
    print("Expected Value:  ",row["expected_value"])
    print("Trade Approved:  ",row["trade_approved"])
    print("Status:          ",row["approval_status"])
    for i in range(1,6):
        x = row[f"rejection_reason_{i}"]
        if x:
            print(f"Reason {i}:       {x}")
    print("="*78)

def status():
    print("Decision:", DECISION.exists())
    print("Risk:", RISK.exists())
    print("Config:", CONFIG.exists())

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",action="store_true")
    p.add_argument("--status",action="store_true")
    a=p.parse_args()
    status() if a.status else run()
