import pandas as pd, numpy as np

print("=== V102 1M CISD / CHOCH / LIQUIDITY FORENSICS ===")
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
c=pd.read_parquet("data/v101_1m_candidate_reference_map.parquet").copy()
tc="time_ny" if "time_ny" in m.columns else next(x for x in m if "time" in x.lower())
m["_t"]=pd.to_datetime(m[tc],utc=True,errors="coerce"); m=m.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
idx=pd.Series(np.arange(len(m)),index=m["_t"])
O,H,L,C=[m[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
prev=np.r_[C[0],C[:-1]]; tr=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev)))
ATR=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()
rows=[]
for _,r in c.iterrows():
 t=pd.to_datetime(r.candidate_time,utc=True); j=idx.get(t,None)
 z={"candidate_time":t}
 if j is None or j<65: rows.append(z); continue
 j=int(j); s=1 if r.direction=="LONG" else -1; a=ATR[j] if np.isfinite(ATR[j]) and ATR[j]>0 else 1.
 # Only bars THROUGH candidate minute are known here. Confirmation timing is measured forward separately,
 # and a feature only becomes available at the minute it actually occurs.
 # Confirmed pivots before candidate (2-bar confirmation).
 ph=[]; pl=[]
 for k in range(max(2,j-60),j-1):
  if H[k]>H[k-1] and H[k]>=H[k+1]: ph.append((k,H[k]))
  if L[k]<L[k-1] and L[k]<=L[k+1]: pl.append((k,L[k]))
 # Liquidity sweep at candidate: take prior confirmed swing then close back through it.
 if s==-1 and ph:
  level=max(x[1] for x in ph[-12:]); z["swept_liquidity"]=int(H[j]>level); z["sweep_reclaimed"]=int(H[j]>level and C[j]<level); z["sweep_depth_atr"]=max(0,H[j]-level)/a
 elif s==1 and pl:
  level=min(x[1] for x in pl[-12:]); z["swept_liquidity"]=int(L[j]<level); z["sweep_reclaimed"]=int(L[j]<level and C[j]>level); z["sweep_depth_atr"]=max(0,level-L[j])/a
 else:
  z.update(swept_liquidity=0,sweep_reclaimed=0,sweep_depth_atr=0.)
 # Opposing structure level existing before candidate for CHOCH.
 if s==-1 and pl: struct=pl[-1][1]
 elif s==1 and ph: struct=ph[-1][1]
 else: struct=np.nan
 z["structure_distance_atr"]=abs(C[j]-struct)/a if np.isfinite(struct) else np.nan
 # CISD proxy: reversal close through open of most recent directional delivery candle before extreme.
 look=range(max(0,j-8),j+1); opp=[k for k in look if (C[k]-O[k])*s<0]
 cisd_level=O[opp[-1]] if opp else np.nan
 for horizon in [1,2,3,5,8]:
  end=min(len(m)-1,j+horizon); choch_min=np.nan; cisd_min=np.nan
  for q in range(j+1,end+1):
   if np.isnan(choch_min) and np.isfinite(struct) and ((s==1 and C[q]>struct) or (s==-1 and C[q]<struct)): choch_min=q-j
   if np.isnan(cisd_min) and np.isfinite(cisd_level) and ((s==1 and C[q]>cisd_level) or (s==-1 and C[q]<cisd_level)): cisd_min=q-j
  z[f"choch_by_{horizon}m"]=int(np.isfinite(choch_min)); z[f"cisd_by_{horizon}m"]=int(np.isfinite(cisd_min))
  z[f"choch_minutes_{horizon}"]=choch_min; z[f"cisd_minutes_{horizon}"]=cisd_min
 rows.append(z)
f=pd.DataFrame(rows); out=c.merge(f,on="candidate_time",how="left")
# Forensics only: compare labels. Future confirmation columns are NOT entry-time features unless decision is delayed until that minute.
cols=["swept_liquidity","sweep_reclaimed","sweep_depth_atr","structure_distance_atr"]+[x for x in f if x.startswith(("choch_by_","cisd_by_"))]
print("Candidates:",len(out),"references:",int(out.is_reference.sum()))
print("\nREFERENCE vs REJECTED/PREMATURE")
for x in cols:
 a=out.loc[out.is_reference,x]; b=out.loc[~out.is_reference,x]
 print(f"{x:28s} REF={a.mean():.4f} OTHER={b.mean():.4f} DIFF={a.mean()-b.mean():+.4f}")
out.to_parquet("data/v102_1m_cisd_choch_liquidity_forensics.parquet",index=False)
print("\nSaved data/v102_1m_cisd_choch_liquidity_forensics.parquet")
print("NEXT: use the strongest 1m timing signatures to build a LIVE sequential ENTER/WAIT test; no future confirmation is exposed before its minute occurs.")
