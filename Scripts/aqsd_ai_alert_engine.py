from pathlib import Path
import argparse,pandas as pd
BASE=Path(__file__).resolve().parent.parent
OUT=BASE/"Output"
DECISION=OUT/"AQSD_Decision_Engine.csv"
PORT=OUT/"AQSD_Portfolio_Summary.csv"
ALERT=OUT/"AQSD_AI_Alerts.csv"

def run():
 a=[]
 if DECISION.exists():
  d=pd.read_csv(DECISION).iloc[-1]
  if str(d.get("suggested_action","")) in ["BUY","SELL"] and float(d.get("confidence_percent",0))>=75:a.append({"type":"TRADE","priority":"HIGH","message":f"{d['underlying']} {d['suggested_action']} {d['confidence_percent']}%"})
 if PORT.exists():
  p=pd.read_csv(PORT).iloc[-1]
  if float(p.get("portfolio_risk_score",0))>=75:a.append({"type":"RISK","priority":"CRITICAL","message":"Portfolio risk high"})
 pd.DataFrame(a if a else [{"type":"INFO","priority":"NORMAL","message":"No actionable alerts"}]).to_csv(ALERT,index=False);print("Done")
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--status",action="store_true");p.add_argument("--run",action="store_true");x=p.parse_args();print("Decision",DECISION.exists(),"Portfolio",PORT.exists()) if x.status else run()