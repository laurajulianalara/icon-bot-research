#!/usr/bin/env python3
"""THE ICON — uncapped causal stream + online session-allocation research.

READ-ONLY. Replays the unchanged Option 2B live evaluator chronologically with
only closed 1m bars + just-opened entry OPEN. First collects every causal FINAL
candidate WITHOUT the legacy 6/day selection cap. Then applies several session
allocation policies online and scores canonical 1R..6R outcomes.

No Option 2B filter/threshold/session/entry/stop/execution logic is changed.
"""
from pathlib import Path
import sys, numpy as np, pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ; NEED=live.NEED; RISK_DOLLARS=300
LEGACY=Path("data/reports/2026-09_trades.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns): continue
        q=q[NEED].copy(); q["time_ny"]=et(q.time_ny); frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=pd.Timestamp("2026-08-28",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy().reset_index(drop=True)
sep=one[(one.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))]
boundaries=sorted(set(t for t in sep.time_ny if t.minute%3==0))

# 1) UNCAP causal FINAL stream.
uncapped={}; violations=[]
for n,t in enumerate(boundaries,1):
    pos=one.index[one.time_ny==t]
    if len(pos)==0: continue
    p=int(pos[-1]); closed=one.loc[:p-1,NEED].tail(6500).copy(); r=one.loc[p]
    op={"time_ny":r.time_ny,"ticker":r.ticker,"open":float(r.open)}
    if len(closed) and not closed.time_ny.max()<t:
        violations.append((t,"closed_not_before_boundary"))
    for x in live.evaluate(closed,live_open=op):
        xt=pd.Timestamp(x["entry_time_et"]); ct=pd.Timestamp(x["candidate_time_et"])
        if xt!=t: continue
        if not ct<xt: violations.append((t,"candidate_not_before_entry"))
        k=(xt,str(x["session"]),str(x["direction"]),ct)
        uncapped.setdefault(k,x)
    if n%1000==0: print(f"Checked {n}/{len(boundaries)} boundaries...")

u=pd.DataFrame(sorted(uncapped.values(),key=lambda x:pd.Timestamp(x["entry_time_et"])))
if u.empty: raise RuntimeError("No uncapped causal FINAL candidates.")
u["entry_ts"]=pd.to_datetime(u["entry_time_et"]); u["date"]=u["entry_ts"].dt.date.astype(str)

# Score outcomes once, after candidate generation.
for rr in range(1,7): u[f"{rr}R"]="OPEN"
for ix,t in u.iterrows():
    entry_time=pd.Timestamp(t.entry_time_et); pos=one.index[one.time_ny==entry_time]
    if len(pos)==0: continue
    j=int(pos[-1]); entry=float(t.entry); stop=float(t.stop); d=str(t.direction); ticker=str(one.iloc[j].ticker)
    risk=entry-stop if d=="LONG" else stop-entry
    if not np.isfinite(risk) or risk<=0: continue
    for rr in range(1,7):
        target=entry+rr*risk if d=="LONG" else entry-rr*risk
        outcome="OPEN"
        for q in range(j,min(j+241,len(one))):
            b=one.iloc[q]
            if str(b.ticker)!=ticker: break
            stop_hit=float(b.low)<=stop if d=="LONG" else float(b.high)>=stop
            target_hit=float(b.high)>=target if d=="LONG" else float(b.low)<=target
            if stop_hit: outcome="LOSS"; break
            if target_hit: outcome="WIN"; break
        u.at[ix,f"{rr}R"]=outcome

# Policies are causal: each arriving FINAL is accepted/rejected using counts so far only.
policies={
 "FIRST6 baseline":{"ASIA":99,"LONDON":99,"NYAM":99,"NYPM":99,"global":6},
 "2 each / max 8":{"ASIA":2,"LONDON":2,"NYAM":2,"NYPM":2,"global":8},
 "2 each / max 6":{"ASIA":2,"LONDON":2,"NYAM":2,"NYPM":2,"global":6},
 "1A 2L 2N 2P / max 7":{"ASIA":1,"LONDON":2,"NYAM":2,"NYPM":2,"global":7},
 "2L 2N 2P / max 6":{"ASIA":0,"LONDON":2,"NYAM":2,"NYPM":2,"global":6},
 "1L 2N 2P / max 5":{"ASIA":0,"LONDON":1,"NYAM":2,"NYPM":2,"global":5},
 "1A 1L 2N 2P / max 6":{"ASIA":1,"LONDON":1,"NYAM":2,"NYPM":2,"global":6},
 "1A 2L 3N 2P / max 6":{"ASIA":1,"LONDON":2,"NYAM":3,"NYPM":2,"global":6},
}

legacy_keys=set(); legacy_session={}
if LEGACY.exists():
    b=pd.read_csv(LEGACY); b["entry_time"]=et(b.entry_time); b["candidate_time"]=et(b.candidate_time)
    b=b[(b.entry_time.dt.year==2026)&(b.entry_time.dt.month==9)]
    for _,r in b.iterrows():
        k=(pd.Timestamp(r.entry_time),str(r.session),str(r.direction),pd.Timestamp(r.candidate_time))
        legacy_keys.add(k); legacy_session[str(r.session)]=legacy_session.get(str(r.session),0)+1

def choose(a):
    keep=[]
    for day,g in u.groupby("date",sort=True):
        counts={"ASIA":0,"LONDON":0,"NYAM":0,"NYPM":0}; total=0
        for ix,r in g.sort_values("entry_ts").iterrows():
            s=str(r.session)
            if total>=a["global"]: break
            if s not in counts or counts[s]>=a.get(s,0): continue
            keep.append(ix); counts[s]+=1; total+=1
    return u.loc[keep].sort_values("entry_ts")

def maxdd(s,rr):
    vals=np.where(s=="WIN",rr,np.where(s=="LOSS",-1,0)).astype(float)
    eq=np.cumsum(vals); peaks=np.maximum.accumulate(np.r_[0.,eq]); dd=peaks[1:]-eq
    return (float(dd.max()) if len(dd) else 0.)*RISK_DOLLARS

print("\n"+"="*112)
print("THE ICON — UNCAPPED CAUSAL SESSION-ALLOCATION TEST")
print("="*112)
print("Decision boundaries:",len(boundaries))
print("Uncapped causal FINAL candidates:",len(u))
print("Future-data invariant violations:",len(violations))
print("\nUNCAPPED SESSION MIX")
print(u.groupby("session").size().to_string())
if legacy_session:
    print("\nLEGACY 73 SESSION MIX:",legacy_session)

rows=[]
for name,a in policies.items():
    z=choose(a)
    keys=set((pd.Timestamp(r.entry_time_et),str(r.session),str(r.direction),pd.Timestamp(r.candidate_time_et)) for _,r in z.iterrows())
    row={"Policy":name,"Trades":len(z),"LegacyRecovered":len(keys&legacy_keys) if legacy_keys else np.nan}
    for s in ["ASIA","LONDON","NYAM","NYPM"]: row[s]=int((z.session==s).sum())
    for rr in [2,3,4,5,6]:
        o=z[f"{rr}R"]; w=int((o=="WIN").sum()); l=int((o=="LOSS").sum()); resolved=w+l
        row[f"{rr}R_WR%"]=100*w/resolved if resolved else np.nan
        row[f"{rr}R_PnL$"]=w*rr*RISK_DOLLARS-l*RISK_DOLLARS
        row[f"{rr}R_DD$"]=maxdd(o,rr)
    rows.append(row)
res=pd.DataFrame(rows)
pd.set_option("display.max_columns",None); pd.set_option("display.width",260)
print("\nPOLICY RESULTS")
print(res.round(2).to_string(index=False))

print("\nLEGACY RECOVERY BY POLICY / SESSION")
for name,a in policies.items():
    z=choose(a); keys=set((pd.Timestamp(r.entry_time_et),str(r.session),str(r.direction),pd.Timestamp(r.candidate_time_et)) for _,r in z.iterrows())
    hit=keys&legacy_keys
    d={s:sum(1 for k in hit if k[1]==s) for s in ["ASIA","LONDON","NYAM","NYPM"]}
    print(f"{name}: {len(hit)}/{len(legacy_keys)}  {d}")

Path("data/reports").mkdir(parents=True,exist_ok=True)
u.to_csv("data/reports/2026-09_uncapped_causal_finals_outcomes.csv",index=False)
res.to_csv("data/reports/2026-09_causal_session_allocation_results.csv",index=False)
print("\nSaved uncapped candidates + allocation results under data/reports/.")
print("READ-ONLY RESEARCH. Option 2B strategy/filter/threshold/session/execution logic was not changed.")
