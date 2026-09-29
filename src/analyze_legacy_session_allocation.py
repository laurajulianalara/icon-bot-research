#!/usr/bin/env python3
"""Compare legacy 73-trade session mix and causal session-cap allocations.

READ-ONLY research. Does not alter Option 2B logic or production selection.
Uses local report CSVs already generated in the Codespace.
"""
from pathlib import Path
import pandas as pd, numpy as np

LEG=Path("data/reports/2026-09_trades.csv")
CAU=Path("data/reports/2026-09_strict_causal_outcomes.csv")
if not LEG.exists(): raise FileNotFoundError(f"Missing {LEG}")
if not CAU.exists(): raise FileNotFoundError(f"Missing {CAU}")

legacy=pd.read_csv(LEG); causal=pd.read_csv(CAU)

def timecol(df):
    for c in ["entry_time_et","candidate_time_et","time_ny","entry_time","candidate_time"]:
        if c in df.columns: return c
    raise KeyError(f"No recognized time column. Columns={list(df.columns)}")
def sesscol(df):
    for c in ["session","Session"]:
        if c in df.columns: return c
    raise KeyError(f"No session column. Columns={list(df.columns)}")

lt=timecol(legacy); ls=sesscol(legacy); ct=timecol(causal); cs=sesscol(causal)
legacy[lt]=pd.to_datetime(legacy[lt]); causal[ct]=pd.to_datetime(causal[ct])
legacy=legacy.sort_values(lt); causal=causal.sort_values(ct)
causal["date"]=causal[ct].dt.date.astype(str)

print("\n"+"="*100)
print("THE ICON — LEGACY SESSION MIX + CAUSAL ALLOCATION RESEARCH")
print("="*100)
print(f"Legacy benchmark trades: {len(legacy)}")
print("\nLEGACY 73 — TRADES BY SESSION")
x=legacy.groupby(ls).size().rename("Trades").to_frame()
x["Share%"]=100*x.Trades/len(legacy)
print(x.round(2).to_string())

print("\nLEGACY 73 — SESSION x DATE")
legacy["date"]=legacy[lt].dt.date.astype(str)
print(pd.crosstab(legacy["date"],legacy[ls]).to_string())

# The saved causal file is the already-selected 125. Allocation tests on it can
# measure redistribution among those selected candidates, but cannot resurrect
# candidates suppressed by the original global cap. State that explicitly.
print("\n"+"="*100)
print("CAUSAL 125 — SESSION MIX")
print("="*100)
print(causal.groupby(cs).size().rename("Trades").to_string())

allocs={
 "2 each / max 8":{"ASIA":2,"LONDON":2,"NYAM":2,"NYPM":2,"global":8},
 "1A 2L 2N 2P / max 7":{"ASIA":1,"LONDON":2,"NYAM":2,"NYPM":2,"global":7},
 "2L 2N 2P / max 6":{"ASIA":0,"LONDON":2,"NYAM":2,"NYPM":2,"global":6},
 "1L 2N 2P / max 5":{"ASIA":0,"LONDON":1,"NYAM":2,"NYPM":2,"global":5},
 "2 each / max 6":{"ASIA":2,"LONDON":2,"NYAM":2,"NYPM":2,"global":6},
 "1A 1L 2N 2P / max 6":{"ASIA":1,"LONDON":1,"NYAM":2,"NYPM":2,"global":6},
}
def select(g,a):
    counts={k:0 for k in ["ASIA","LONDON","NYAM","NYPM"]}; out=[]
    for i,r in g.sort_values(ct).iterrows():
        s=r[cs]
        if s not in counts or counts[s]>=a.get(s,0): continue
        if len(out)>=a["global"]: break
        counts[s]+=1; out.append(i)
    return out

print("\n"+"="*100)
print("ALLOCATION TESTS ON THE SAVED 125")
print("="*100)
rows=[]
for name,a in allocs.items():
    idx=[]
    for _,g in causal.groupby("date",sort=True): idx += select(g,a)
    z=causal.loc[idx].sort_values(ct)
    row={"Allocation":name,"Trades":len(z)}
    for rr in [2,3,4,5,6]:
        col=f"{rr}R"; w=int((z[col]=="WIN").sum()); l=int((z[col]=="LOSS").sum())
        row[f"{rr}R_WR%"]=100*w/(w+l) if w+l else np.nan
        row[f"{rr}R_PnL$"]=w*rr*300-l*300
    rows.append(row)
print(pd.DataFrame(rows).round(2).to_string(index=False))

print("\nIMPORTANT:")
print("These allocation rows use the already-selected 125 trades.")
print("They DO NOT yet reveal NYAM/NYPM candidates that the old first-6/day cap prevented from entering the 125.")
print("If session caps look promising, the next definitive test must replay the uncapped causal candidate stream and apply")
print("each allocation online, then score outcomes. That is the test that can show whether later historical/winning trades return.")
print("\nREAD-ONLY. No strategy/filter/threshold/session/execution rules changed.")
