import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier

print("=== +1M EXPLICIT EVENTS — UNSEEN RR BACKTEST ===")
seq=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in seq.columns)
dc=next(c for c in ["direction","side","dir"] if c in seq.columns)
mc=next(c for c in ["minute","delay_min","minutes_after","minute_after"] if c in seq.columns)
seq[tc]=pd.to_datetime(seq[tc],utc=True,errors="coerce")

ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")
pos=set(zip(ref["mapped_candidate_time"],ref["direction"].astype(str).str.upper()))

base=seq[seq[mc]==0].copy()
base["target"]=[int((t,str(s).upper()) in pos) for t,s in zip(base[tc],base[dc])]
ny=base[tc].dt.tz_convert("America/New_York"); base["_day"]=ny.dt.date
if "session" not in base:
    mins=ny.dt.hour*60+ny.dt.minute
    base["session"]=np.select([(mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)],["Asia","London","NYAM","NYPM"],default="")
neg=set()
for _,p in base[base.target==1].iterrows():
    g=base[(base._day==p._day)&(base.session==p.session)&(base[dc].astype(str).str.upper()==str(p[dc]).upper())&(base[tc]<p[tc])]
    neg.update(zip(g[tc],g[dc].astype(str).str.upper()))
keys=pos|neg

rich=pd.read_parquet("data/v99_causal_structure_liquidity_features.parquet").copy()
rtc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in rich.columns)
rdc=next(c for c in ["direction","side","dir"] if c in rich.columns)
rich[rtc]=pd.to_datetime(rich[rtc],utc=True,errors="coerce")
rich["_key"]=list(zip(rich[rtc],rich[rdc].astype(str).str.upper()))
tokens=["sweep","liquid","reclaim","cisd","choch","displace","structure","fvg","failed","wick"]
ev=[c for c in rich if any(k in c.lower() for k in tokens) and pd.api.types.is_numeric_dtype(rich[c])]

s=seq[seq[mc].between(0,1)].copy()
s=s[[(t,str(q).upper()) in keys for t,q in zip(s[tc],s[dc])]].copy()
s["target"]=[int((t,str(q).upper()) in pos) for t,q in zip(s[tc],s[dc])]
exclude=["target","reference","outcome","future","label","win","rr","entry","extreme","risk","bar_index","max_favorable"]
nums=[c for c in s.select_dtypes(include=[np.number,bool]) if c!=mc and not any(k in c.lower() for k in exclude)]
wide=None
for minute in [0,1]:
    z=s[s[mc]==minute][[tc,dc,"target"]+nums].drop_duplicates([tc,dc]).copy()
    z=z.rename(columns={c:f"m{minute}_{c}" for c in nums})
    if minute:z=z.drop(columns="target")
    wide=z if wide is None else wide.merge(z,on=[tc,dc],how="left")
wide["_key"]=list(zip(wide[tc],wide[dc].astype(str).str.upper()))
wide=wide.merge(rich[["_key"]+ev].drop_duplicates("_key"),on="_key",how="left").sort_values(tc).reset_index(drop=True)
features=[c for c in wide if c.startswith("m") or c in ev]
cut=wide[tc].quantile(.70); tr=wide[wide[tc]<=cut]; te=wide[wide[tc]>cut].copy()
med=tr[features].median()
m=ExtraTreesClassifier(n_estimators=900,min_samples_leaf=8,max_features="sqrt",class_weight="balanced",random_state=42,n_jobs=-1)
m.fit(tr[features].replace([np.inf,-np.inf],np.nan).fillna(med),tr.target.astype(int))
te["score"]=m.predict_proba(te[features].replace([np.inf,-np.inf],np.nan).fillna(med))[:,1]

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

# minute +1 must CLOSE before it is usable; earliest causal fill is +2 minute open.
for top in [20,10,5,3,2]:
    th=np.quantile(te.score,1-top/100); sig=te[te.score>=th].sort_values(tc)
    print(f"\nTOP {top}% | raw signals={len(sig)} | threshold={th:.6f}")
    for rr in range(1,7):
        w=l=u=miss=0; busy=-1
        for _,x in sig.iterrows():
            i=idx.get(x[tc])
            if i is None or i+2>=len(one):miss+=1;continue
            j=i+2
            if j<=busy:continue
            direction=str(x[dc]).upper()
            entry=float(one.iloc[j].open); extreme=float(one.iloc[i].low if direction=="LONG" else one.iloc[i].high)
            stop=extreme-.25 if direction=="LONG" else extreme+.25
            risk=entry-stop if direction=="LONG" else stop-entry
            if risk<=0 or not np.isfinite(risk):u+=1;continue
            target=entry+rr*risk if direction=="LONG" else entry-rr*risk
            out=0; end=j
            for k in range(j,min(j+241,len(one))):
                b=one.iloc[k]; end=k
                if direction=="LONG":
                    if b.low<=stop:out=-1;break
                    if b.high>=target:out=1;break
                else:
                    if b.high>=stop:out=-1;break
                    if b.low<=target:out=1;break
            busy=end
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        print(f"  1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | resolved={n} | misses={miss}" if n else f"  1:{rr} no resolved")
print("\nCAUSALITY NOTE: minute +1 features are only known after that candle closes, so this test enters at +2 open.")
