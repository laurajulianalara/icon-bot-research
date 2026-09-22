import pandas as pd
import numpy as np

print("=== V79 FULL CAUSAL RR OUTCOME CACHE ===")
d=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()
b=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
b["t"]=pd.to_datetime(b.time_ny,utc=True,errors="coerce")
idx=pd.Series(b.index,index=b.t).to_dict()

def utc(x): return pd.to_datetime(x,utc=True,errors="coerce")
timecol=next(c for c in ["candidate_time","time","candidate_time_et"] if c in d.columns)
d["t_utc"]=utc(d[timecol])

# V68 rows are candidate-time causal features. Match the canonical execution:
# signal/entry at candidate T+3, market/open; stop = candidate extreme +/- .25.
# Prefer saved entry/risk when present; otherwise reconstruct from raw candidate fields.
miss=0
for rr in range(1,7): d[f"win_{rr}r"]=np.nan

for k,x in d.iterrows():
    i=idx.get(x.t_utc)
    if i is None or i+3>=len(b):
        miss+=1; continue
    j=i+3
    entry=float(x["entry"]) if "entry" in d.columns and pd.notna(x.get("entry")) else float(b.iloc[j].open)
    if "risk" in d.columns and pd.notna(x.get("risk")):
        risk=float(x["risk"])
    else:
        # candidate extreme columns differ across research versions
        ex=None
        for c in ["candidate_extreme","extreme","candidate_price"]:
            if c in d.columns and pd.notna(x.get(c)): ex=float(x[c]); break
        if ex is None:
            # canonical 3m candidate bar from 1m bars T..T+2
            tri=b.iloc[i:i+3]
            ex=float(tri.low.min() if x.direction=="LONG" else tri.high.max())
        stop=ex-0.25 if x.direction=="LONG" else ex+0.25
        risk=entry-stop if x.direction=="LONG" else stop-entry
    if not np.isfinite(risk) or risk<=0: continue
    stop=entry-risk if x.direction=="LONG" else entry+risk
    fut=b.iloc[j:min(j+241,len(b))]
    for rr in range(1,7):
        target=entry+rr*risk if x.direction=="LONG" else entry-rr*risk
        y=np.nan
        for _,bar in fut.iterrows():
            # conservative ambiguity: STOP checked first
            if x.direction=="LONG":
                if bar.low<=stop: y=0; break
                if bar.high>=target: y=1; break
            else:
                if bar.high>=stop: y=0; break
                if bar.low<=target: y=1; break
        d.at[k,f"win_{rr}r"]=y

d.to_parquet("data/v79_full_causal_rr_outcomes.parquet",index=False)
print("Rows:",len(d),"timestamp misses:",miss)
for rr in range(1,7):
    z=d[f"win_{rr}r"].dropna()
    print(f"1:{rr} resolved={len(z)} wins={int(z.sum())} WR={100*z.mean():.2f}%")
print("Saved: data/v79_full_causal_rr_outcomes.parquet")
print("NEXT: rerank all 27,412 V78 signature combinations by actual causal RR outcomes, then chronological one-position-at-a-time validation.")
