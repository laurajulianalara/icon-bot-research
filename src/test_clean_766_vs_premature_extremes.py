import pandas as pd, numpy as np

print("=== 766 VS PREMATURE 1M EXTREMES — CAUSAL FORENSIC TEST ===")

ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["candidate_time"]=pd.to_datetime(ref["candidate_time"],utc=True,errors="coerce")
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")

seq=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
# discover timestamp/direction columns
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in seq.columns)
seq[tc]=pd.to_datetime(seq[tc],utc=True,errors="coerce")
dc=next(c for c in ["direction","side","dir"] if c in seq.columns)
mc=next((c for c in ["minute","delay_min","minutes_after","minute_after"] if c in seq.columns),None)
if mc is not None:
    base=seq[seq[mc]==0].copy()
else:
    base=seq.sort_values(tc).drop_duplicates([tc,dc]).copy()

# Exact frozen positives: native mapped minute + direction.
pos=set(zip(ref["mapped_candidate_time"],ref["direction"].astype(str).str.upper()))
base["is_clean_766"]=[(t,str(d).upper()) in pos for t,d in zip(base[tc],base[dc])]
print("Frozen 766 found in V106 candidate table:",int(base.is_clean_766.sum()),"/",len(ref))

# Restrict negatives to premature same-direction extremes occurring earlier in the same
# session/day before a frozen positive. This directly answers ENTER vs WAIT.
ny=base[tc].dt.tz_convert("America/New_York")
base["_day"]=ny.dt.date
if "session" not in base.columns:
    mins=ny.dt.hour*60+ny.dt.minute
    base["session"]=np.select([(mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)],
                              ["Asia","London","NYAM","NYPM"],default="")
positives=base[base.is_clean_766].copy()
neg_idx=set()
for _,p in positives.iterrows():
    g=base[(base["_day"]==p["_day"])&(base["session"]==p["session"])&
           (base[dc].astype(str).str.upper()==str(p[dc]).upper())&(base[tc]<p[tc])]
    neg_idx.update(g.index.tolist())
neg=base.loc[sorted(neg_idx)].copy()
study=pd.concat([positives,neg],ignore_index=True)
study["target"]=study.is_clean_766.astype(int)
print("Premature/rejected comparison extremes:",len(neg))
print("Total forensic rows:",len(study))

# Only numeric features that exist at minute 0; exclude labels/outcomes/future-derived fields.
exclude_tokens=["target","reference","win","outcome","rr","future","label","is_clean","bar_index"]
features=[]
for c in study.select_dtypes(include=[np.number,bool]).columns:
    lc=c.lower()
    if c==mc or any(k in lc for k in exclude_tokens): continue
    if study[c].notna().mean()<.70 or study[c].nunique(dropna=True)<2: continue
    features.append(c)

rows=[]
for c in features:
    p=study.loc[study.target==1,c].astype(float).replace([np.inf,-np.inf],np.nan).dropna()
    n=study.loc[study.target==0,c].astype(float).replace([np.inf,-np.inf],np.nan).dropna()
    if len(p)<50 or len(n)<50: continue
    pooled=np.sqrt((p.var()+n.var())/2)
    eff=(p.mean()-n.mean())/pooled if pooled and np.isfinite(pooled) else 0
    rows.append((c,len(p),len(n),p.mean(),n.mean(),eff,abs(eff)))
rank=pd.DataFrame(rows,columns=["feature","n_766","n_premature","mean_766","mean_premature","effect","abs_effect"]).sort_values("abs_effect",ascending=False)

print("\nTOP CAUSAL DIFFERENCES — 766 VS PREMATURE EXTREMES")
print(rank.head(25).drop(columns="abs_effect").round(4).to_string(index=False))

# Simple single-feature purity screen to expose interpretable ENTER/WAIT candidates,
# without training a model or using future labels as predictors.
screens=[]
base_rate=study.target.mean()
for _,r in rank.head(20).iterrows():
    c=r.feature
    vals=study[c].replace([np.inf,-np.inf],np.nan)
    for q in [.10,.20,.30,.40,.50,.60,.70,.80,.90]:
        th=vals.quantile(q)
        for op,mask in [("<=",vals<=th),(">=",vals>=th)]:
            s=study[mask.fillna(False)]
            if len(s)<50: continue
            purity=s.target.mean(); recall=s.target.sum()/max(1,study.target.sum())
            screens.append((c,op,th,len(s),purity,recall,purity/base_rate if base_rate else np.nan))
scr=pd.DataFrame(screens,columns=["feature","op","threshold","trades","purity","recall","lift"]).sort_values(["lift","recall"],ascending=False)

print("\nBEST SIMPLE LIVE-OBSERVABLE SEPARATORS")
print(scr.head(20).round(4).to_string(index=False))

rank.to_csv("data/clean766_vs_premature_feature_differences.csv",index=False)
scr.to_csv("data/clean766_vs_premature_simple_screens.csv",index=False)
study.to_parquet("data/clean766_vs_premature_forensic_rows.parquet",index=False)
print("\nSaved forensic outputs.")
print("NEXT: use the strongest causal differences to build ONE ENTER/WAIT rule, then independently backtest it on every native 1m session extreme.")
