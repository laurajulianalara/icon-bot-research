import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier

print("=== FROZEN 766 — HIGH-PRECISION SEQUENTIAL RR VALIDATION ===")
d=pd.read_parquet("data/clean766_vs_premature_forensic_rows.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in d.columns)
dc=next(c for c in ["direction","side","dir"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.sort_values(tc).reset_index(drop=True)

exclude=["target","is_clean_766","is_reference","outcome","future","label","win","entry","extreme","risk"]
features=[]
for c in d.select_dtypes(include=[np.number,bool]).columns:
    if any(k in c.lower() for k in exclude): continue
    if d[c].notna().mean()>=.70 and d[c].nunique(dropna=True)>1: features.append(c)

cut=d[tc].quantile(.70)
tr=d[d[tc]<=cut].copy(); te=d[d[tc]>cut].copy()
med=tr[features].median()
Xtr=tr[features].replace([np.inf,-np.inf],np.nan).fillna(med)
Xte=te[features].replace([np.inf,-np.inf],np.nan).fillna(med)
m=ExtraTreesClassifier(n_estimators=700,min_samples_leaf=8,max_features="sqrt",class_weight="balanced",random_state=42,n_jobs=-1)
m.fit(Xtr,tr.target.astype(int))
te["score"]=m.predict_proba(Xte)[:,1]

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

# Fixed percentile thresholds selected without using RR outcomes.
for top_pct in [10,5,3,2,1]:
    th=np.quantile(te.score,1-top_pct/100)
    sig=te[te.score>=th].sort_values(tc).copy()
    print(f"\nTOP {top_pct}% | signals={len(sig)} | threshold={th:.6f}")
    for rr in range(1,7):
        w=l=u=miss=0; busy_until=-1
        for _,x in sig.iterrows():
            i=idx.get(x[tc])
            if i is None or i+1>=len(one): miss+=1; continue
            j=i+1
            if j<=busy_until: continue
            direction=str(x[dc]).upper()
            entry=float(one.iloc[j].open)
            extreme=float(one.iloc[i].low if direction=="LONG" else one.iloc[i].high)
            stop=extreme-.25 if direction=="LONG" else extreme+.25
            risk=entry-stop if direction=="LONG" else stop-entry
            if not np.isfinite(risk) or risk<=0: u+=1; continue
            target=entry+rr*risk if direction=="LONG" else entry-rr*risk
            out=0; end=j
            for k in range(j,min(j+241,len(one))):
                b=one.iloc[k]; end=k
                if "ticker" in one.columns and b.ticker!=one.iloc[j].ticker: break
                if direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low>=0 and b.low<=target: out=1; break
            busy_until=end
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        wr=100*w/n if n else 0
        print(f"  1:{rr} | {w}W/{l}L/{u}U | WR {wr:.2f}% | resolved={n} | misses={miss}")

print("\nThis is later unseen history only, sequential one-position-at-a-time, next-1m-open entry, stop-first.")
print("Use it to decide whether current causal features are strong enough before adding more reversal-sequence information.")
