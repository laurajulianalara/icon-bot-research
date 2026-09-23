import pandas as pd, numpy as np

print("=== MISSING REVERSAL SEQUENCE AUDIT — 766 VS PREMATURE EXTREMES ===")
d=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in d.columns)
dc=next(c for c in ["direction","side","dir"] if c in d.columns)
mc=next((c for c in ["minute","delay_min","minutes_after","minute_after"] if c in d.columns),None)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
if mc is None: raise RuntimeError("No sequence-minute column found.")

ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")
pos=set(zip(ref["mapped_candidate_time"],ref["direction"].astype(str).str.upper()))
d["clean766"]=[(t,str(s).upper()) in pos for t,s in zip(d[tc],d[dc])]

# Build premature negatives exactly as prior forensic test, then compare the full 0-3 minute sequence.
base=d[d[mc]==0].copy()
ny=base[tc].dt.tz_convert("America/New_York"); base["_day"]=ny.dt.date
if "session" not in base.columns:
    mins=ny.dt.hour*60+ny.dt.minute
    base["session"]=np.select([(mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)],["Asia","London","NYAM","NYPM"],default="")
positives=base[base.clean766].copy()
negkeys=set()
for _,p in positives.iterrows():
    g=base[(base["_day"]==p["_day"])&(base["session"]==p["session"])&(base[dc].astype(str).str.upper()==str(p[dc]).upper())&(base[tc]<p[tc])]
    negkeys.update(zip(g[tc],g[dc].astype(str).str.upper()))
d["premature"]=[(t,str(s).upper()) in negkeys for t,s in zip(d[tc],d[dc])]
s=d[(d.clean766|d.premature)&(d[mc].between(0,3))].copy()
s["target"]=s.clean766.astype(int)

exclude=["target","clean766","premature","reference","outcome","future","label","win","rr","entry","extreme","risk","bar_index"]
nums=[c for c in s.select_dtypes(include=[np.number,bool]).columns if c!=mc and not any(k in c.lower() for k in exclude)]
rows=[]
for minute in sorted(s[mc].dropna().unique()):
    z=s[s[mc]==minute]
    for c in nums:
        p=pd.to_numeric(z.loc[z.target==1,c],errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
        n=pd.to_numeric(z.loc[z.target==0,c],errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
        if len(p)<50 or len(n)<50: continue
        pooled=np.sqrt((p.var()+n.var())/2)
        eff=(p.mean()-n.mean())/pooled if pooled and np.isfinite(pooled) else 0
        rows.append((minute,c,len(p),len(n),p.mean(),n.mean(),eff,abs(eff)))
r=pd.DataFrame(rows,columns=["minute","feature","n766","npremature","mean766","meanpremature","effect","abs_effect"]).sort_values("abs_effect",ascending=False)
print("Clean 766 represented:",base.clean766.sum())
print("Premature comparison extremes:",len(negkeys))
print("\nTOP DIFFERENCES DURING THE 0-3 MINUTE DECISION WINDOW")
print(r.head(40).drop(columns="abs_effect").round(4).to_string(index=False))
print("\nBEST BY MINUTE")
for minute in sorted(r.minute.unique()):
    print("\nMinute",int(minute))
    print(r[r.minute==minute].head(10).drop(columns="abs_effect").round(4).to_string(index=False))
r.to_csv("data/missing_reversal_sequence_audit.csv",index=False)
print("\nSaved data/missing_reversal_sequence_audit.csv")
print("NEXT: use the strongest 1-3 minute causal reversal behaviors, not raw candidate-bar features, to define the next ENTER/WAIT selector.")
