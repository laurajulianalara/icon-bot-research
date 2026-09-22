import pandas as pd, numpy as np
from pathlib import Path

print("=== V88 RICH CAUSAL FEATURE REBUILD ===")
cand=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()
m1=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()

def timecol(d):
    for c in ["candidate_time","time","timestamp","datetime","date"]:
        if c in d.columns: return c
    if isinstance(d.index,pd.DatetimeIndex):
        d["_idx_time"]=d.index; return "_idx_time"
    raise RuntimeError("No time column")
ct=timecol(cand); mt=timecol(m1)
cand["_t"]=pd.to_datetime(cand[ct],utc=True,errors="coerce")
m1["_t"]=pd.to_datetime(m1[mt],utc=True,errors="coerce")
m1=m1.sort_values("_t").set_index("_t")
for c in ["open","high","low","close"]:
    if c not in m1: raise RuntimeError(f"Missing {c}")

rows=[]
for n,(idx,r) in enumerate(cand.iterrows(),1):
    t=r["_t"]
    # Decision is T+3 open. Strict predictors end at T+2:59 => use 1m bars through T+2.
    cutoff=t+pd.Timedelta(minutes=2)
    w=m1.loc[:cutoff].tail(61)
    if len(w)<31: continue
    o,h,l,c=[w[x].astype(float) for x in ["open","high","low","close"]]
    tr=pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.tail(20).mean()
    if not np.isfinite(atr) or atr<=0: continue
    direction=str(r.get("direction","")).upper()
    sign=1 if direction=="LONG" else -1
    def ret(k): return sign*(c.iloc[-1]-c.iloc[-1-k])/atr
    def rng(k): return (h.tail(k).max()-l.tail(k).min())/atr
    body=(c-o).abs()
    # Causal reversal/displacement proxies at exact cutoff.
    last3=w.tail(3)
    rev_move=sign*(c.iloc[-1]-c.iloc[-3])/atr
    disp=sign*(c.iloc[-1]-o.iloc[-1])/atr
    cisd_strength=max(0.0,rev_move)
    # prior swing sweep using only history before candidate minute
    pre=m1.loc[:t-pd.Timedelta(minutes=1)].tail(20)
    if len(pre):
        prior_hi=float(pre.high.max()); prior_lo=float(pre.low.min())
        ext=float(r.get("extreme",np.nan))
        sweep=(prior_lo-ext)/atr if direction=="LONG" else (ext-prior_hi)/atr
    else: sweep=np.nan
    z={"_row":idx,"candidate_time":t,"cisd":cisd_strength,"disp":disp,"sweep":sweep,
       "approach3_atr":ret(3),"approach5_atr":ret(5),"approach10_atr":ret(10),
       "pre30_range_atr":rng(30),"pre10_avg_range_atr":((h-l).tail(10).mean()/atr),
       "pre10_avg_body_atr":body.tail(10).mean()/atr,
       "pre5_directional_bars":int((sign*(c-o).tail(5)>0).sum()),
       "stretch20_atr":ret(20),"range5_atr":rng(5),"range10_atr":rng(10),
       "range20_atr":rng(20)}
    rows.append(z)
rich=pd.DataFrame(rows)
out=cand.reset_index(names="_row").merge(rich,on="_row",how="left",suffixes=("","_v88"))
out.to_parquet("data/v88_full_rich_causal_features.parquet",index=False)
print("Rows:",len(out),"rebuilt:",len(rich))
fs=["cisd","disp","sweep","approach3_atr","approach5_atr","approach10_atr","pre30_range_atr",
"pre10_avg_range_atr","pre10_avg_body_atr","pre5_directional_bars","stretch20_atr","range5_atr","range10_atr","range20_atr"]
print("New causal features:",len(fs))
print(out[fs].describe().T[["count","mean","std","50%"]].to_string())
print("\nSaved: data/v88_full_rich_causal_features.parquet")
print("NEXT: V89 retrains WAIT/ENTER with old 11 + these causal features and compares directly with 73.13% baseline.")
