import pandas as pd, numpy as np
print("=== V106 MEANINGFUL REVERSAL SEQUENCE DATASET ===")
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
c=pd.read_parquet("data/v101_1m_candidate_reference_map.parquet").copy()
tc="time_ny" if "time_ny" in m.columns else next(x for x in m if "time" in x.lower())
m["_t"]=pd.to_datetime(m[tc],utc=True,errors="coerce"); m=m.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
c["candidate_time"]=pd.to_datetime(c.candidate_time,utc=True)
idx=pd.Series(np.arange(len(m)),index=m["_t"])
O,H,L,C=[m[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
prev=np.r_[C[0],C[:-1]]; tr=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev))); atr=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()
rows=[]
for _,r in c.iterrows():
 j=idx.get(r.candidate_time,None)
 if j is None or j<65: continue
 j=int(j); s=1 if r.direction=="LONG" else -1; ex=float(r.extreme); a=atr[j] if np.isfinite(atr[j]) and atr[j]>0 else 1.
 stop=ex-.25 if s==1 else ex+.25
 # Build one snapshot per candidate per elapsed minute. Every predictor is timestamp-locked.
 for delay in range(0,9):
  q=j+delay
  if q+1>=len(m): break
  # Candidate is invalidated if a new same-direction extreme has already printed by q.
  invalid=(L[j:q+1].min()<ex if s==1 else H[j:q+1].max()>ex)
  if invalid: break
  entry=O[q+1]; risk=abs(entry-stop)
  if risk<=0: continue
  z={"candidate_time":r.candidate_time,"decision_time":m._t.iloc[q],"delay_min":delay,"direction":r.direction,"extreme":ex,"entry":entry,"risk":risk,"is_reference":int(r.is_reference)}
  rng=max(H[q]-L[q],.25); z["close_reversal_pos"]=(C[q]-L[q])/rng if s==1 else (H[q]-C[q])/rng
  z["body_pct"]=abs(C[q]-O[q])/rng; z["move_from_extreme_atr"]=s*(C[q]-ex)/a
  z["max_favorable_atr"]=((H[j:q+1].max()-ex) if s==1 else (ex-L[j:q+1].min()))/a
  z["retrace_to_extreme_atr"]=((C[q]-L[j:q+1].min()) if s==1 else (H[j:q+1].max()-C[q]))/a
  for w in [2,3,5,8,13,21,34]:
   k=max(0,q-w+1); z[f"ret_{w}_atr"]=s*(C[q]-C[k])/a
   z[f"range_{w}_atr"]=(H[k:q+1].max()-L[k:q+1].min())/a
   z[f"dirbars_{w}"]=np.mean(np.sign(C[k:q+1]-O[k:q+1])==s)
  # Objective future labels ONLY. Never predictors.
  for R in range(1,7):
   target=entry+s*R*risk; y=0
   for p in range(q+1,min(len(m),q+242)):
    hs=L[p]<=stop if s==1 else H[p]>=stop; ht=H[p]>=target if s==1 else L[p]<=target
    if hs: y=0; break
    if ht: y=1; break
   z[f"win_{R}R"]=y
  rows.append(z)
d=pd.DataFrame(rows).sort_values(["decision_time","candidate_time"])
d.to_parquet("data/v106_meaningful_reversal_sequence.parquet",index=False)
print("Candidate-minute snapshots:",len(d),"unique extremes:",d.candidate_time.nunique())
print("Reference extremes:",c.is_reference.sum())
for delay in range(9):
 x=d[d.delay_min==delay]
 print(f"minute {delay}: snapshots={len(x):6d} ref={x.is_reference.sum():4d}",end="")
 for R in [1,2,3,4,5,6]: print(f" {R}R={x[f'win_{R}R'].mean()*100:5.1f}%",end="")
 print()
print("Saved data/v106_meaningful_reversal_sequence.parquet")
print("NEXT: V107 runs the automated WAIT/ENTER search across these timestamp-locked sequences, optimizing early entry + 1R-6R on train/validation and proving it on untouched chronological test data.")
