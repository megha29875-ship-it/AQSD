"""
AQSD Core
Module: Master Intelligence Engine v1
Combines core technical components into a single Master Score.
"""

from __future__ import annotations
import argparse
from datetime import date, datetime
import pandas as pd
from aqsd_database import connect, setup_database

WEIGHTS = {
    "structure_score":0.20,
    "trend_score":0.20,
    "relative_strength_score":0.15,
    "sector_score":0.10,
    "pivot_score":0.15,
    "news_score":0.05,
    "macro_score":0.05,
    "commodity_score":0.05,
    "global_score":0.05,
}

def weighted_score(row):
    total=0
    weight=0
    for k,w in WEIGHTS.items():
        v=row.get(k)
        if pd.notna(v):
            total+=float(v)*w
            weight+=w
    return round(total/weight,2) if weight else None

def recommendation(score):
    if score is None: return ""
    if score>=85: return "STRONG BUY"
    if score>=75: return "BUY"
    if score>=60: return "WATCH"
    if score>=45: return "NEUTRAL"
    return "AVOID"

def run():
    setup_database()
    with connect() as con:
        df=pd.read_sql_query("""
        SELECT score_id,structure_score,trend_score,
               relative_strength_score,sector_score,
               pivot_score,news_score,macro_score,
               commodity_score,global_score
        FROM intelligence_scores
        WHERE score_date=(SELECT MAX(score_date) FROM intelligence_scores)
        """,con)
        if df.empty:
            print("No intelligence records found.")
            return
        df["master_score"]=df.apply(weighted_score,axis=1)
        df["recommendation"]=df["master_score"].apply(recommendation)
        now=datetime.now().isoformat(timespec="seconds")
        cur=con.cursor()
        for _,r in df.iterrows():
            cur.execute("""
            UPDATE intelligence_scores
            SET master_score=?,
                recommendation=?,
                created_at=?
            WHERE score_id=?
            """,(r.master_score,r.recommendation,now,int(r.score_id)))
        con.commit()
        leaders=pd.read_sql_query("""
        SELECT s.nse_symbol,
               i.master_score,
               i.recommendation
        FROM intelligence_scores i
        JOIN symbols s ON s.symbol_id=i.symbol_id
        WHERE i.score_date=(SELECT MAX(score_date) FROM intelligence_scores)
        ORDER BY i.master_score DESC
        LIMIT 25
        """,con)
    print("\nAQSD MASTER INTELLIGENCE")
    print("="*60)
    print(leaders.to_string(index=False))
    print("="*60)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",action="store_true")
    a=p.parse_args()
    run()
