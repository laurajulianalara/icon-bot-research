#!/usr/bin/env python3
"""Check whether the 19 benchmark trades absent from the delay audit are date-coverage related. READ ONLY."""
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; TZ="America/New_York"
REP=ROOT/"data/reports/2026-09_trades.csv"; RAW=ROOT/"data/reversal_candidates.parquet"; ONE=ROOT/"data/mnq_continuous_1m.parquet"
def norm(s):
 x=pd.to_datetime(s,errors="coerce")
 return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
rep=pd.read_csv(REP); rep["ct"]=norm(rep["candidate_time"]); rep["direction"]=rep.direction.astype(str).str.upper()
raw=pd.read_parquet(RAW); raw["time_ny"]=norm(raw.time_ny); raw["direction"]=raw.direction.astype(str).str.upper()
one=pd.read_parquet(ONE); one["time_ny"]=norm(one.time_ny)
keys=set(zip(raw.time_ny,raw.direction))
rep["in_raw"]=[(t,d) in keys for t,d in zip(rep.ct,rep.direction)]
print("="*92);print("SEPTEMBER 75 — DATE COVERAGE CHECK");print("="*92)
print("Reporter benchmark:",len(rep))
print("Reporter first/last candidate:",rep.ct.min(),"->",rep.ct.max())
print("1m history first/last:",one.time_ny.min(),"->",one.time_ny.max())
print("Raw candidates first/last:",raw.time_ny.min(),"->",raw.time_ny.max())
print("\nBENCHMARK TRADES BY DATE")
print(rep.groupby(rep.ct.dt.date).size().to_string())
print("\nBENCHMARK KEYS PRESENT IN RAW CANDIDATE FILE BY DATE")
print(rep.groupby(rep.ct.dt.date).in_raw.agg(["sum","count"]).to_string())
missing=rep[~rep.in_raw]
print("\nBENCHMARK KEYS ABSENT FROM RAW CANDIDATE FILE:",len(missing))
if len(missing): print(missing[["ct","session","direction"]].to_string(index=False))
print("\nTRADES AFTER SEP 17:",int((rep.ct.dt.date>pd.Timestamp("2026-09-17").date()).sum()))
print("READ-ONLY.")
