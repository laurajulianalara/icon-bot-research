#!/usr/bin/env python3
"""Quick audit: which of the 32 non-London causal trades match the frozen historical benchmark.

READ-ONLY. Uses existing CSVs only; does not rerun strategy or alter logic.
"""
from pathlib import Path
import pandas as pd

LEG=Path("data/reports/2026-09_trades.csv")
CAU=Path("data/reports/2026-09_strict_causal_outcomes.csv")
if not LEG.exists(): raise FileNotFoundError(f"Missing {LEG}")
if not CAU.exists(): raise FileNotFoundError(f"Missing {CAU}")

b=pd.read_csv(LEG)
c=pd.read_csv(CAU)

def col(df,names):
    for x in names:
        if x in df.columns: return x
    raise KeyError(f"Missing one of {names}. Columns={list(df.columns)}")

be=col(b,["entry_time","entry_time_et"]); bc=col(b,["candidate_time","candidate_time_et"])
ce=col(c,["entry_time_et","entry_time"]); cc=col(c,["candidate_time_et","candidate_time"])
bs=col(b,["session","Session"]); cs=col(c,["session","Session"])
bd=col(b,["direction","Direction"]); cd=col(c,["direction","Direction"])

for df,x in [(b,be),(b,bc),(c,ce),(c,cc)]:
    df[x]=pd.to_datetime(df[x],utc=True)

def key(r,e,s,d,ct):
    return (r[e],str(r[s]).upper(),str(r[d]).upper(),r[ct])

hist={key(r,be,bs,bd,bc) for _,r in b.iterrows()}
c["historical_match"]=[key(r,ce,cs,cd,cc) in hist for _,r in c.iterrows()]
non=c[c[cs].astype(str).str.upper()!="LONDON"].copy().sort_values(ce)

print("\n"+"="*100)
print("THE ICON — NON-LONDON CAUSAL vs ORIGINAL HISTORICAL BENCHMARK")
print("="*100)
print(f"Historical benchmark total: {len(b)}")
print(f"Causal total: {len(c)}")
print(f"Non-London causal trades: {len(non)}")
print(f"Non-London that MATCH historical: {int(non.historical_match.sum())}")
print(f"Non-London that are CAUSAL-ONLY: {int((~non.historical_match).sum())}")
print(f"Match rate: {100*non.historical_match.mean():.2f}%")

print("\nBY SESSION")
z=(non.groupby(cs)["historical_match"]
   .agg(Trades="size",HistoricalMatches="sum"))
z["CausalOnly"]=z["Trades"]-z["HistoricalMatches"]
z["MatchRate%"]=100*z["HistoricalMatches"]/z["Trades"]
print(z.round(2).to_string())

show=[ce,cc,cs,cd,"historical_match"]
for rr in ["1R","2R","3R","4R","5R","6R"]:
    if rr in non.columns: show.append(rr)
print("\nALL 32 NON-LONDON TRADES")
print(non[show].to_string(index=False))

print("\nHISTORICAL-MATCH NON-LONDON TRADES")
m=non[non.historical_match]
print(m[show].to_string(index=False) if len(m) else "NONE")

print("\nCAUSAL-ONLY NON-LONDON TRADES")
x=non[~non.historical_match]
print(x[show].to_string(index=False) if len(x) else "NONE")

print("\nREAD-ONLY. No strategy, reports, thresholds, sessions, or execution changed.")
