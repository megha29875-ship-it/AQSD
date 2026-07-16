
"""
AQSD FYERS Futures Master (v1)

Creates a master of all live Futures contracts from the FYERS Symbol Master.
"""

import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "Data"

SOURCE = DATA / "FYERS_NSE_Symbol_Master.csv"
OUTPUT = DATA / "FYERS_Futures_Contracts.csv"


def detect_columns(df):
    cols = {c.lower(): c for c in df.columns}

    def find(*names):
        for n in names:
            for k,v in cols.items():
                if n in k:
                    return v
        return None

    return {
        "symbol": find("symbol"),
        "underlying": find("underlying","underly"),
        "instrument": find("instrument","instrumenttype","type"),
        "expiry": find("expiry"),
        "lot": find("lot"),
        "tick": find("tick"),
    }


def bucket(expiry_series):
    dates = pd.to_datetime(expiry_series)
    unique = sorted(dates.dropna().unique())
    mapping={}
    names=["NEAR","NEXT","FAR"]
    for i,d in enumerate(unique[:3]):
        mapping[d]=names[i]
    return dates.map(mapping).fillna("LATER")


def main():
    if not SOURCE.exists():
        print("Missing:", SOURCE)
        return

    df = pd.read_csv(SOURCE, low_memory=False)
    c = detect_columns(df)

    if c["instrument"]:
        fut = df[df[c["instrument"]].astype(str).str.contains("FUT",case=False,na=False)].copy()
    else:
        fut = df.copy()

    if c["expiry"]:
        fut["expiry_bucket"] = bucket(fut[c["expiry"]])

    keep=[]
    for k in ["underlying","symbol","expiry","lot","tick"]:
        if c[k]:
            keep.append(c[k])

    if "expiry_bucket" in fut.columns:
        keep.append("expiry_bucket")

    out=fut[keep].copy()
    out.to_csv(OUTPUT,index=False)

    print("="*60)
    print("AQSD FYERS FUTURES MASTER")
    print("="*60)
    print("Contracts :",len(out))
    if "expiry_bucket" in out.columns:
        print(out["expiry_bucket"].value_counts())
    print("Saved :",OUTPUT)

if __name__=="__main__":
    main()
