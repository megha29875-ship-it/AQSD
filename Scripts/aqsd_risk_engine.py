from pathlib import Path
import argparse,json,pandas as pd
BASE=Path(__file__).resolve().parent.parent
OUT=BASE/"Output";DATA=BASE/"Data";CONFIG=DATA/"AQSD_Risk_Config.json";DECISION=OUT/"AQSD_Decision_Engine.csv"

def cfg():
 DATA.mkdir(exist_ok=True)
 d={"capital":1000000,"max_risk_per_trade_percent":1.0,"max_daily_loss_percent":3.0,"max_open_positions":5,"slippage_percent":0.05,"brokerage_per_order":20}

 if CONFIG.exists(): return json.loads(CONFIG.read_text())
 CONFIG.write_text(json.dumps(d,indent=2));return d

def run():
 c=cfg();df=pd.read_csv(DECISION);r=df.iloc[-1];e=float(r["aggressive_entry"]);s=float(r["stop_loss"]);risk=abs(e-s);mr=c["capital"]*c["max_risk_per_trade_percent"]/100;qty=int(mr//risk) if risk else 0;pd.DataFrame([{"underlying":r["underlying"],"action":r["suggested_action"],"suggested_quantity":qty}]).to_csv(OUT/"AQSD_Risk_Engine.csv",index=False);print("Done")

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--run",action="store_true");p.add_argument("--status",action="store_true");a=p.parse_args();print("Decision exists:",DECISION.exists()) if a.status else run()