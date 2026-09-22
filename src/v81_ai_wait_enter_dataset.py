import pandas as pd
import numpy as np

print("=== V81 AI WAIT / ENTER DATASET ===")
d=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()

tc=next((c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns),None)
if tc is None: raise ValueError("No candidate timestamp column found")
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)

# V68 already contains the audited historical next-extreme invalidation label.
labelcol=next((c for c in ["future_invalidated","invalidated","next_extreme_invalidated","old_future_invalidated","hindsight_rejected"] if c in d.columns),None)
if labelcol is None:
    # Reconstruct the exact old behavior: within session/direction, a newer extreme at/before T+3 means WAIT.
    grp=[c for c in ["session","direction"] if c in d.columns]
    if len(grp)!=2: raise ValueError("Need session and direction to reconstruct WAIT label")
    d["trade_date"]=d[tc].dt.tz_convert("America/New_York").dt.date
    nxt=d.groupby(["trade_date","session","direction"])[tc].shift(-1)
    signal=d[tc]+pd.Timedelta(minutes=3)
    d["ai_wait"]=(nxt.notna() & (nxt<=signal)).astype(int)
    labelcol="ai_wait"
else:
    d["ai_wait"]=pd.to_numeric(d[labelcol],errors="coerce").fillna(0).astype(int).clip(0,1)
    labelcol="ai_wait"

d["ai_enter"]=1-d[labelcol]

# Keep only numeric, pre-entry candidate features. Explicitly exclude outcomes/future-derived fields.
ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
idcols={tc,"ai_wait","ai_enter","entry","risk"}
features=[]
for c in d.columns:
    if c in idcols: continue
    if any(x in c.lower() for x in ban): continue
    if pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000:
        features.append(c)

outcols=[tc]+[c for c in ["session","direction","entry","risk"] if c in d.columns]+features+["ai_wait","ai_enter"]
out=d[outcols].copy()
out.to_parquet("data/v81_ai_wait_enter_dataset.parquet",index=False)

print("Rows:",len(out))
print("WAIT:",int(out.ai_wait.sum()),f"({100*out.ai_wait.mean():.2f}%)")
print("ENTER:",int(out.ai_enter.sum()),f"({100*out.ai_enter.mean():.2f}%)")
print("Causal numeric predictors:",len(features))
print("Saved: data/v81_ai_wait_enter_dataset.parquet")
print("NEXT: train chronological WAIT/ENTER ML models and measure out-of-sample replication accuracy.")
