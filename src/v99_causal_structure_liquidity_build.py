import pandas as pd, numpy as np

print("=== V99 CAUSAL STRUCTURE / LIQUIDITY STATE BUILD ===")
c=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
b=pd.read_parquet("data/v97_rich_market_state_features.parquet").copy()
tc="time_ny" if "time_ny" in c.columns else next(x for x in c if "time" in x.lower())
bt=next(x for x in ["candidate_time","t_utc","time","candidate_time_et"] if x in b.columns)
c["_t"]=pd.to_datetime(c[tc],utc=True,errors="coerce"); b["_t"]=pd.to_datetime(b[bt],utc=True,errors="coerce")
c=c.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
idx=pd.Series(np.arange(len(c)),index=c["_t"])
O,H,L,C=[c[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
prev=np.r_[C[0],C[:-1]]; tr=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev)))
ATR=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()
rows=[]
for _,r in b.iterrows():
 t=r["_t"]; j=idx.get(t+pd.Timedelta(minutes=2),None)
 if j is None or j<125: rows.append({"_t":t}); continue
 j=int(j); a=ATR[j] if np.isfinite(ATR[j]) and ATR[j]>0 else 1.; s=1 if str(r.get("direction","")).upper()=="LONG" else -1
 z={"_t":t}
 # Confirmed-only swing/liquidity levels: pivot must have two bars to its right, so latest eligible pivot is j-2.
 for w in [20,40,60,120]:
  lo=max(2,j-w); hi=j-2
  ph=[]; pl=[]
  for k in range(lo,hi+1):
   if H[k]>H[k-1] and H[k]>=H[k+1]: ph.append(H[k])
   if L[k]<L[k-1] and L[k]<=L[k+1]: pl.append(L[k])
  z[f"confirmed_highs_{w}"]=len(ph); z[f"confirmed_lows_{w}"]=len(pl)
  if ph:
   q=np.array(ph); z[f"nearest_swing_high_{w}_atr"]=(q[q>=C[j]].min()-C[j])/a if np.any(q>=C[j]) else (q.max()-C[j])/a
  if pl:
   q=np.array(pl); z[f"nearest_swing_low_{w}_atr"]=(C[j]-q[q<=C[j]].max())/a if np.any(q<=C[j]) else (C[j]-q.min())/a
 # Equal-liquidity clusters among confirmed pivots.
 tol=.15*a
 for w in [30,60,120]:
  lo=max(2,j-w); hi=j-2
  ph=[H[k] for k in range(lo,hi+1) if H[k]>H[k-1] and H[k]>=H[k+1]]
  pl=[L[k] for k in range(lo,hi+1) if L[k]<L[k-1] and L[k]<=L[k+1]]
  z[f"equal_high_pairs_{w}"]=sum(abs(ph[p]-ph[q])<=tol for p in range(len(ph)) for q in range(p)) if len(ph)>1 else 0
  z[f"equal_low_pairs_{w}"]=sum(abs(pl[p]-pl[q])<=tol for p in range(len(pl)) for q in range(p)) if len(pl)>1 else 0
 # FVGs formed and completed by cutoff.
 for w in [15,30,60]:
  lo=j-w+1; bull=[]; bear=[]
  for k in range(max(lo,2),j+1):
   if L[k]>H[k-2]: bull.append((H[k-2],L[k]))
   if H[k]<L[k-2]: bear.append((H[k],L[k-2]))
  z[f"bull_fvg_count_{w}"]=len(bull); z[f"bear_fvg_count_{w}"]=len(bear)
  if bull: z[f"dist_bull_fvg_{w}_atr"]=min(abs(C[j]-(u+v)/2) for u,v in bull)/a
  if bear: z[f"dist_bear_fvg_{w}_atr"]=min(abs(C[j]-(u+v)/2) for u,v in bear)/a
 # Displacement / CISD-like delivery shift using completed bars only.
 bodies=np.abs(C-O); med=np.median(bodies[j-20:j+1])+1e-9
 for w in [3,5,8]:
  lo=j-w+1
  rev=(C[lo:j+1]-O[lo:j+1])*(-s)
  z[f"reversal_body_sum_{w}_atr"]=np.sum(np.maximum(rev,0))/a
  z[f"reversal_displacement_count_{w}"]=np.sum(rev>1.5*med)
  z[f"reversal_close_strength_{w}"]=(-s)*(C[j]-C[lo])/a
 # Failed continuation: how far price tried to extend extreme then closed away.
 z["close_away_from_high_atr"]=(H[j]-C[j])/a
 z["close_away_from_low_atr"]=(C[j]-L[j])/a
 z["reversal_close_away_atr"]=z["close_away_from_low_atr"] if s==1 else z["close_away_from_high_atr"]
 rows.append(z)
f=pd.DataFrame(rows); out=b.merge(f,on="_t",how="left")
new=[x for x in f if x!="_t"]
print("Rows:",len(out),"new structure/liquidity features:",len(new),"median non-null:",f"{out[new].notna().mean().median()*100:.2f}%")
out.to_parquet("data/v99_causal_structure_liquidity_features.parquet",index=False)
print("Saved data/v99_causal_structure_liquidity_features.parquet")
print("NEXT: V100 will mass-test these structure/liquidity/CISD features against 1R-6R with chronological holdout.")
