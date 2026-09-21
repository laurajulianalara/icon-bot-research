import pandas as pd
import numpy as np

OLD="data/v3_reversal_features.parquet"
ONE="data/mnq_continuous_1m.parquet"
OUT="data/v6_old_winner_early_signature.csv"

old=pd.read_parquet(OLD)
# Rebuild the exact old pre-causal A+ candidate set from the detailed V3 cache.
rules={
 "ASIA":dict(cisd=.95,disp=1.20,sweep=.20),
 "NYAM":dict(cisd=.95,disp=1.20,sweep=.20),
 "LONDON":dict(cisd=.96,disp=1.20,sweep=.20),
 "NYPM":dict(cisd=.97,disp=1.10,sweep=None),
}
old=old[(old.rr==4.0)&(old.max_cisd_bars==5)&(old.entry=="NO_FIB")&old.outcome.isin(["WIN","LOSS"])].copy()
parts=[]
for s,r in rules.items():
    q=old[old.session==s].copy()
    q=q[(q.confirm_close_pos>=r["cisd"])&(q.disp_atr>=r["disp"])]
    if r["sweep"] is not None:q=q[q.sweep_atr>=r["sweep"]]
    parts.append(q)
old=pd.concat(parts).sort_values("fill_time")
old["candidate_time"]=pd.to_datetime(old.candidate_time)
old=old.drop_duplicates(["candidate_time","session","direction"],keep="first")
timecol="candidate_time"

one=pd.read_parquet(ONE);one["time_ny"]=pd.to_datetime(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

out=[]
for _,r in old.iterrows():
    t=r[timecol];i=idx.get(t)
    if i is None or i<20:continue
    # outcome field compatibility
    oc=str(r.get("outcome",r.get("result",""))).upper()
    iswin=oc=="WIN" or float(r.get("result_r",0))>0
    direction=str(r.get("direction",""))
    if direction not in ["LONG","SHORT"]:continue
    sg=1 if direction=="LONG" else -1
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:continue
    # Snapshot what was genuinely visible 1m and 2m after candidate.
    vals={"candidate_time":t,"session":r.get("session",""),"direction":direction,"old_win":int(iswin)}
    for k in [1,2,3]:
        if i+k>=len(one):continue
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        vals[f"m{k}_body_atr"]=abs(float(b.close-b.open))/a
        vals[f"m{k}_close_pos"]=((b.close-b.low)/(b.high-b.low) if b.high>b.low else .5)
        if direction=="SHORT":vals[f"m{k}_close_pos"]=1-vals[f"m{k}_close_pos"]
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    out.append(vals)
d=pd.DataFrame(out);d.to_csv(OUT,index=False)
print(f"Old diagnostic unique NO_FIB candidates matched: {len(d):,}")
print(f"Old winners: {d.old_win.sum():,} | old losses: {(d.old_win==0).sum():,}")
features=[c for c in d if c.startswith("m")]
rows=[]
for f in features:
    w=d.loc[d.old_win==1,f].dropna();l=d.loc[d.old_win==0,f].dropna()
    if not len(w) or not len(l):continue
    pooled=np.sqrt((w.var()+l.var())/2);eff=(w.mean()-l.mean())/pooled if pooled>0 else 0
    rows.append((f,w.mean(),l.mean(),w.median(),l.median(),eff,abs(eff)))
s=pd.DataFrame(rows,columns=["feature","winner_mean","loser_mean","winner_median","loser_median","effect","abs_effect"]).sort_values("abs_effect",ascending=False)
print("\n=== WHAT WAS ALREADY VISIBLE EARLY IN OLD 3M WINNERS? ===")
print(s.head(20).drop(columns="abs_effect").round(3).to_string(index=False))
print("\nSaved:",OUT)
