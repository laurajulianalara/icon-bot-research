import pandas as pd, numpy as np

print("=== ORIGINAL 1,911: LIVE VS FUTURE-DEPENDENT SELECTION AUDIT ===")

files=["data/v56_icon_bot_funded_prior_year_trades.csv","data/v27_option2a_trades.csv"]
parts=[]
for f in files:
    x=pd.read_csv(f)
    x["_source"]=f
    parts.append(x)
tr=pd.concat(parts,ignore_index=True)
print("Original trades loaded:",len(tr))

cand=pd.read_parquet("data/v101_1m_candidate_reference_map.parquet").copy()

def tcol(df):
    for n in ["candidate_time","time","signal_time","entry_time","datetime","date"]:
        if n in df.columns: return n
    return next((c for c in df.columns if "time" in c.lower()),None)

ct=tcol(cand)
cand[ct]=pd.to_datetime(cand[ct],utc=True,errors="coerce")
refs=cand[cand["is_reference"].astype(int)==1].copy()

dircol="direction"
refs["future_dependent"]=False
refs["future_extreme_time"]=None

group_cols=[c for c in ["session","session_date","date"] if c in cand.columns]
if not group_cols:
    cand["_day"]=cand[ct].dt.tz_convert("America/New_York").dt.date
    refs["_day"]=refs[ct].dt.tz_convert("America/New_York").dt.date
    group_cols=["_day"]

lookup={}
for key,g in cand.sort_values(ct).groupby(group_cols+[dircol],dropna=False):
    if not isinstance(key,tuple): key=(key,)
    lookup[key]=list(g[ct].dropna())

for i,r in refs.iterrows():
    key=tuple(r[c] for c in group_cols+[dircol])
    times=lookup.get(key,[])
    t=r[ct]
    cutoff=t+pd.Timedelta(minutes=3)
    future=[x for x in times if x>t and x<=cutoff]
    if future:
        refs.at[i,"future_dependent"]=True
        refs.at[i,"future_extreme_time"]=future[0].isoformat()

n=len(refs); fut=int(refs.future_dependent.sum()); live=n-fut
print()
print("AUDIT RESULT")
print(f"Reference trades mapped: {n} / 1911")
print(f"LIVE-VALID selection:       {live} / {n} = {100*live/n:.2f}%")
print(f"FUTURE-DEPENDENT selection: {fut} / {n} = {100*fut/n:.2f}%")
print()
refs.to_csv("data/original_1911_live_vs_future_audit.csv",index=False)
print("Saved data/original_1911_live_vs_future_audit.csv")
