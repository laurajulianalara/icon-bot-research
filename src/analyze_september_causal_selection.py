#!/usr/bin/env python3
"""Analyze strict-causal September outcomes by session and daily slot.

READ-ONLY research. Uses the already-saved strict-causal outcome CSV.
Does not change strategy, filters, thresholds, sessions, caps, or execution.
"""
from pathlib import Path
import pandas as pd
import numpy as np

P = Path("data/reports/2026-09_strict_causal_outcomes.csv")
if not P.exists():
    raise FileNotFoundError(f"{P} not found. Run report_september_strict_causal_outcomes.py first.")

df = pd.read_csv(P)
df["entry_time_et"] = pd.to_datetime(df["entry_time_et"])
df = df.sort_values("entry_time_et").reset_index(drop=True)
df["date"] = df["entry_time_et"].dt.date.astype(str)
df["daily_slot"] = df.groupby("date").cumcount() + 1

print("\n" + "="*100)
print("THE ICON — SEPTEMBER CAUSAL TRADE SELECTION DIAGNOSTIC")
print("="*100)
print("Trades:", len(df))
print("Purpose: determine whether early/session trades consume the 6/day cap while later sessions contain better outcomes.")

for rr in range(1,7):
    col=f"{rr}R"
    print(f"\n--- {rr}R BY SESSION ---")
    rows=[]
    for sess,g in df.groupby("session", sort=False):
        w=int((g[col]=="WIN").sum()); l=int((g[col]=="LOSS").sum()); o=int((g[col]=="OPEN").sum())
        resolved=w+l
        wr=100*w/resolved if resolved else np.nan
        pnl=w*(rr*300)-l*300
        rows.append([sess,len(g),w,l,o,wr,pnl])
    print(pd.DataFrame(rows,columns=["Session","Trades","Wins","Losses","Open","WR%","PnL$"]).round(2).to_string(index=False))

print("\n" + "="*100)
print("DAILY SLOT QUALITY")
print("="*100)
slot_rows=[]
for slot,g in df.groupby("daily_slot"):
    row={"Slot":slot,"Trades":len(g)}
    for rr in [2,3,4,5,6]:
        s=g[f"{rr}R"]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum())
        row[f"{rr}R_WR%"]=100*w/(w+l) if w+l else np.nan
    slot_rows.append(row)
print(pd.DataFrame(slot_rows).round(2).to_string(index=False))

print("\n" + "="*100)
print("SESSION x DAILY SLOT — 3R / 4R / 5R / 6R")
print("="*100)
rows=[]
for (sess,slot),g in df.groupby(["session","daily_slot"]):
    row={"Session":sess,"Slot":slot,"Trades":len(g)}
    for rr in [3,4,5,6]:
        s=g[f"{rr}R"]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum())
        row[f"{rr}R_WR%"]=100*w/(w+l) if w+l else np.nan
    rows.append(row)
print(pd.DataFrame(rows).round(2).to_string(index=False))

print("\n" + "="*100)
print("CAP SATURATION BY SESSION")
print("="*100)
# For each day, show how many of the selected six came from each session and
# which session supplied the sixth selected trade.
days=[]
for d,g in df.groupby("date",sort=True):
    g=g.sort_values("entry_time_et")
    counts=g["session"].value_counts().to_dict()
    days.append({
        "Date":d,
        "Trades":len(g),
        "Asia":counts.get("ASIA",0),
        "London":counts.get("LONDON",0),
        "NYAM":counts.get("NYAM",0),
        "NYPM":counts.get("NYPM",0),
        "LastSelectedSession":g.iloc[-1]["session"] if len(g) else "",
        "CapHit":len(g)>=6,
    })
days=pd.DataFrame(days)
print(days.to_string(index=False))

print("\nCAP SUMMARY")
print("Days with 6 selected:", int(days.CapHit.sum()), "/", len(days))
for sess in ["ASIA","LONDON","NYAM","NYPM"]:
    n=int(((days.CapHit) & (days.LastSelectedSession==sess)).sum())
    print(f"Cap completed during {sess}: {n} days")

print("\n" + "="*100)
print("LONDON VS NON-LONDON SUMMARY")
print("="*100)
rows=[]
for name,g in [("LONDON",df[df.session=="LONDON"]),("NON-LONDON",df[df.session!="LONDON"])]:
    row={"Group":name,"Trades":len(g)}
    for rr in [2,3,4,5,6]:
        s=g[f"{rr}R"]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum())
        row[f"{rr}R_WR%"]=100*w/(w+l) if w+l else np.nan
        row[f"{rr}R_PnL$"]=w*(rr*300)-l*300
    rows.append(row)
print(pd.DataFrame(rows).round(2).to_string(index=False))

print("\nREAD-ONLY DIAGNOSTIC. No strategy or trade-selection rules were changed.")
