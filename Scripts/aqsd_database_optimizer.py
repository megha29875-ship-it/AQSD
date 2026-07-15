from __future__ import annotations
import argparse,sqlite3
from pathlib import Path
from datetime import datetime
BASE_DIR=Path(__file__).resolve().parent.parent
DB=BASE_DIR/"Data"/"aqsd_core.db"
TABLES=["symbols","daily_prices","intelligence_scores","news_events","macro_events","global_markets","commodities","system_runs","settings"]
def c(): return sqlite3.connect(DB)
def integ(x): return x.execute("PRAGMA integrity_check").fetchone()[0]
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--status",action="store_true")
 p.add_argument("--optimize",action="store_true")
 p.add_argument("--integrity",action="store_true")
 a=p.parse_args()
 conn=c()
 if a.integrity:
  print("Integrity:",integ(conn));return
 if a.optimize:
  conn.execute("ANALYZE");conn.execute("REINDEX");conn.commit();conn.close();conn=c();conn.execute("VACUUM");conn.commit();print("Optimized",datetime.now());print("Integrity:",integ(conn));return
 print("AQSD DATABASE STATUS");print("DB:",DB);print("Size MB:",round(DB.stat().st_size/1024/1024,2));print("Integrity:",integ(conn))
 for t in TABLES:
  try:v=conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
  except:v="N/A"
  print(f"{t:<24}{v}")
if __name__=="__main__": main()
