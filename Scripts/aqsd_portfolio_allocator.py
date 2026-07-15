
"""
AQSD Portfolio Allocation Intelligence (Starter)
Ranks actionable trades and suggests capital allocation.

Commands
--------
python aqsd_portfolio_allocator.py --run
python aqsd_portfolio_allocator.py --status
"""

import sqlite3
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "Data" / "aqsd_core.db"
OUT = BASE / "Output" / "Portfolio_Allocation.csv"

def status():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_allocation(
        trade_date TEXT,
        symbol TEXT,
        action TEXT,
        priority_rank INTEGER,
        allocation_percent REAL,
        conviction TEXT,
        PRIMARY KEY(trade_date,symbol)
    )
    """)
    con.commit()
    n = cur.execute("SELECT COUNT(*) FROM portfolio_allocation").fetchone()[0]
    print(f"Portfolio allocation records: {n}")
    con.close()

def run():
    con = sqlite3.connect(DB)

    df = pd.read_sql("""
    SELECT
        trade_date,
        nse_symbol,
        action,
        priority_rank,
        priority_score,
        confidence_percent,
        master_score
    FROM aqsd_trade_decisions
    WHERE trade_date=(
        SELECT MAX(trade_date)
        FROM aqsd_trade_decisions)
    ORDER BY priority_rank
    """, con)

    if df.empty:
        print("Run aqsd_decision_engine.py first.")
        return

    df = df[df.action.isin(["STRONG BUY","BUY","BUY ON DIP"])].copy()

    if df.empty:
        print("No actionable trades.")
        return

    df["weight"] = (
        df["priority_score"]*0.45 +
        df["confidence_percent"]*0.30 +
        df["master_score"]*0.25
    )

    total = df["weight"].sum()
    df["allocation_percent"] = (df["weight"]/total*100).round(2)

    def conviction(x):
        if x >= 18:
            return "VERY HIGH"
        if x >= 12:
            return "HIGH"
        if x >= 7:
            return "MEDIUM"
        return "LOW"

    df["conviction"] = df["allocation_percent"].apply(conviction)

    out = df[[
        "trade_date",
        "nse_symbol",
        "action",
        "priority_rank",
        "allocation_percent",
        "conviction"
    ]].rename(columns={"nse_symbol":"symbol"})

    out.to_sql("portfolio_allocation", con,
               if_exists="replace", index=False)

    OUT.parent.mkdir(exist_ok=True)
    out.to_csv(OUT, index=False)

    print("\nSuggested Portfolio Allocation\n")
    print(out.to_string(index=False))
    print(f"\nCSV saved to: {OUT}")

    con.close()

if __name__=="__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true")
    p.add_argument("--status", action="store_true")
    a = p.parse_args()

    if a.run:
        run()
    else:
        status()
