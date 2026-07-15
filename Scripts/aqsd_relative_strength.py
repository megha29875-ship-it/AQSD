
"""
AQSD Relative Strength Intelligence Engine

Ranks stocks by relative strength versus:
1. NIFTY benchmark
2. Their own sector

Commands
--------
python aqsd_relative_strength.py --run
python aqsd_relative_strength.py --status
python aqsd_relative_strength.py --report
"""

from pathlib import Path
import argparse
import sqlite3
import pandas as pd

DB = Path(__file__).resolve().parent.parent / "Data" / "aqsd_core.db"

def status():
    con=sqlite3.connect(DB)
    cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS relative_strength(
        trade_date TEXT,
        symbol TEXT,
        sector TEXT,
        rs_market REAL,
        rs_sector REAL,
        rs_score REAL,
        rating TEXT,
        PRIMARY KEY(trade_date,symbol)
    )""")
    con.commit()
    c=cur.execute("SELECT COUNT(*) FROM relative_strength").fetchone()[0]
    print(f"Relative strength records : {c}")
    con.close()

def run():
    con=sqlite3.connect(DB)
    try:
        df=pd.read_sql("""
        SELECT
            p.trade_date,
            s.nse_symbol,
            s.sector,
            p.close,
            LAG(p.close,20) OVER(
                PARTITION BY p.symbol_id
                ORDER BY p.trade_date
            ) previous_close
        FROM daily_prices p
        JOIN symbols s
        ON s.symbol_id=p.symbol_id
        """,con)
    except Exception:
        print("Run historical price loader first.")
        return

    df=df.dropna()
    if df.empty:
        print("No sufficient history.")
        return

    df["ret20"]=(df["close"]/df["previous_close"]-1)*100
    latest=df.groupby("nse_symbol").tail(1).copy()

    sector_mean=latest.groupby("sector")["ret20"].transform("mean")
    market_mean=latest["ret20"].mean()

    latest["rs_market"]=latest["ret20"]-market_mean
    latest["rs_sector"]=latest["ret20"]-sector_mean

    latest["rs_score"]=50+latest["rs_market"]*2+latest["rs_sector"]*2
    latest["rs_score"]=latest["rs_score"].clip(0,100)

    def rating(x):
        if x>=80: return "LEADER"
        if x>=65: return "OUTPERFORM"
        if x<=20: return "LAGGARD"
        if x<=35: return "UNDERPERFORM"
        return "NEUTRAL"

    latest["rating"]=latest["rs_score"].apply(rating)

    latest[[
        "trade_date","nse_symbol","sector",
        "rs_market","rs_sector","rs_score","rating"
    ]].rename(columns={"nse_symbol":"symbol"}).to_sql(
        "relative_strength",
        con,
        if_exists="replace",
        index=False
    )

    print(latest.sort_values("rs_score",ascending=False)[[
        "nse_symbol","sector","rs_score","rating"
    ]].head(25).to_string(index=False))

    con.close()

def report():
    con=sqlite3.connect(DB)
    df=pd.read_sql("SELECT * FROM relative_strength ORDER BY rs_score DESC",con)
    con.close()
    out=Path(__file__).resolve().parent.parent/"Output"/"Relative_Strength.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out,index=False)
    print(out)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--run",action="store_true")
    p.add_argument("--status",action="store_true")
    p.add_argument("--report",action="store_true")
    a=p.parse_args()

    if a.run:
        run()
    elif a.report:
        report()
    else:
        status()
