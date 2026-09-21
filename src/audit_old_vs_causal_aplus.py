import pandas as pd
import numpy as np

OLD="data/v3_reversal_features.parquet"
NEW="data/v4_causal_reversal_features.parquet"
OUT="data/audit_old_vs_causal_aplus.csv"

rules={
 "ASIA":dict(cisd=.95,disp=1.20,sweep=.20),
 "NYAM":dict(cisd=.95,disp=1.20,sweep=.20),
 "LONDON":dict(cisd=.96,disp=1.20,sweep=.20),
 "NYPM":dict(cisd=.97,disp=1.10,sweep=None),
}

def select(path,label):
    d=pd.read_parquet(path)
    for c in ["candidate_time","fill_time","confirm_time","signal_available_time"]:
        if c in d.columns:d[c]=pd.to_datetime(d[c])
    d=d[(d.rr==4.0)&(d.max_cisd_bars==5)&(d.entry=="NO_FIB")&d.outcome.isin(["WIN","LOSS"])].copy()
    p=[]
    for s,r in rules.items():
        q=d[d.session==s].copy()
        q=q[(q.confirm_close_pos>=r["cisd"])&(q.disp_atr>=r["disp"])]
        if r["sweep"] is not None:q=q[q.sweep_atr>=r["sweep"]]
        p.append(q)
    z=pd.concat(p).sort_values("fill_time")
    raw=len(z)
    # One row per reversal candidate; stop-buffer variants are cache duplicates.
    key=[c for c in ["candidate_time","session","direction"] if c in z.columns]
    z=z.drop_duplicates(key,keep="first").copy()
    z["source"]=label
    print(f"{label}: raw qualifying rows={raw:,} | unique candidates={len(z):,} | wins={(z.outcome=='WIN').sum():,} | WR={((z.outcome=='WIN').mean()*100 if len(z) else np.nan):.2f}%")
    return z

old=select(OLD,"OLD_PRE_CAUSAL")
new=select(NEW,"NEW_CAUSAL")

key=["candidate_time","session","direction"]
oc=old[key+["fill_time","outcome","result_r"]].rename(columns={"fill_time":"old_fill","outcome":"old_outcome","result_r":"old_r"})
nc=new[key+["fill_time","outcome","result_r"]].rename(columns={"fill_time":"new_fill","outcome":"new_outcome","result_r":"new_r"})
m=oc.merge(nc,on=key,how="outer",indicator=True)

both=m[m._merge=="both"].copy()
old_only=m[m._merge=="left_only"].copy()
new_only=m[m._merge=="right_only"].copy()

print("\n=== OLD vs CAUSAL A+ AUDIT ===")
print(f"Old unique A+ candidates: {len(old):,}")
print(f"New unique A+ candidates: {len(new):,}")
print(f"Same candidate exists in both: {len(both):,}")
print(f"Old candidates missing after causal timing: {len(old_only):,}")
print(f"New-only candidates: {len(new_only):,}")
print(f"Old missing winners: {(old_only.old_outcome=='WIN').sum():,}")
print(f"Old missing losses: {(old_only.old_outcome=='LOSS').sum():,}")

if len(both):
    both["fill_delay_min"]=(both.new_fill-both.old_fill).dt.total_seconds()/60
    print(f"\nMatched candidates old WR: {(both.old_outcome=='WIN').mean()*100:.2f}%")
    print(f"Matched candidates new WR: {(both.new_outcome=='WIN').mean()*100:.2f}%")
    print(f"Old WIN -> New LOSS: {((both.old_outcome=='WIN')&(both.new_outcome=='LOSS')).sum():,}")
    print(f"Old LOSS -> New WIN: {((both.old_outcome=='LOSS')&(both.new_outcome=='WIN')).sum():,}")
    print(f"Median entry delay: {both.fill_delay_min.median():.2f} min")
    print(f"Mean entry delay: {both.fill_delay_min.mean():.2f} min")

m.to_csv(OUT,index=False)
print("\nSaved:",OUT)
print("\nNEXT: use this audit to decide whether the collapse came from missing fills, later entries, duplicate inflation, or outcome flips.")
