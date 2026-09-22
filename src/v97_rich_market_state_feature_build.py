import pandas as pd, numpy as np

print("=== V97 RICH MARKET-STATE FEATURE BUILD ===")
c1=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
base=pd.read_parquet("data/v88_full_rich_causal_features.parquet").copy()
tc1="time_ny" if "time_ny" in c1.columns else next(c for c in c1 if "time" in c.lower())
tcb=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in base.columns)
c1["_t"]=pd.to_datetime(c1[tc1],utc=True,errors="coerce")
base["_t"]=pd.to_datetime(base[tcb],utc=True,errors="coerce")
c1=c1.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
idx=pd.Series(np.arange(len(c1)),index=c1["_t"])
O,H,L,C=[c1[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
V=c1["volume"].astype(float).to_numpy() if "volume" in c1.columns else np.full(len(c1),np.nan)
tr=np.maximum(H-L,np.maximum(np.abs(H-np.r_[C[0],C[:-1]]),np.abs(L-np.r_[C[0],C[:-1]])))
atr=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()
rows=[]
for q,r in base.iterrows():
 t=r["_t"]; j=idx.get(t-pd.Timedelta(minutes=1),None)
 if j is None: j=idx.get(t+pd.Timedelta(minutes=2),None)
 if j is None or j<65: rows.append({"_t":t}); continue
 j=int(j); a=atr[j] if np.isfinite(atr[j]) and atr[j]>0 else 1.0
 direction=str(r.get("direction","")).upper(); s=1 if direction=="LONG" else -1
 z={"_t":t}
 for w in [3,5,10,15,30,60]:
  lo=j-w+1; op=O[lo]; cl=C[j]
  z[f"path_return_{w}_atr"]=s*(cl-op)/a
  z[f"path_range_{w}_atr"]=(np.max(H[lo:j+1])-np.min(L[lo:j+1]))/a
  z[f"path_efficiency_{w}"]=abs(cl-op)/(np.sum(np.abs(np.diff(C[lo:j+1])))+1e-9)
  z[f"dir_close_count_{w}"]=np.sum((np.diff(C[lo-1:j+1])*s)>0)
  z[f"opp_close_count_{w}"]=np.sum((np.diff(C[lo-1:j+1])*s)<0)
  z[f"upper_wick_mean_{w}"]=np.mean((H[lo:j+1]-np.maximum(O[lo:j+1],C[lo:j+1]))/(H[lo:j+1]-L[lo:j+1]+1e-9))
  z[f"lower_wick_mean_{w}"]=np.mean((np.minimum(O[lo:j+1],C[lo:j+1])-L[lo:j+1])/(H[lo:j+1]-L[lo:j+1]+1e-9))
 # compression/expansion and acceleration
 z["range_compression_5v20"]=z["path_range_5_atr"]/(z["path_range_20_atr"]+1e-9)
 z["range_compression_10v30"]=z["path_range_10_atr"]/(z["path_range_30_atr"]+1e-9)
 z["momentum_accel_5v15"]=z["path_return_5_atr"]-z["path_return_15_atr"]/3
 # completed-bar liquidity/swing context
 for w in [10,20,30,60]:
  lo=j-w+1
  prior_hi=np.max(H[lo:j]); prior_lo=np.min(L[lo:j])
  z[f"dist_prior_high_{w}_atr"]=(prior_hi-C[j])/a
  z[f"dist_prior_low_{w}_atr"]=(C[j]-prior_lo)/a
  z[f"sweep_high_{w}"]=float(H[j]>prior_hi and C[j]<prior_hi)
  z[f"sweep_low_{w}"]=float(L[j]<prior_lo and C[j]>prior_lo)
 # volume state if available
 if np.isfinite(V[j]):
  for w in [5,20,60]:
   vv=V[j-w+1:j+1]; z[f"volume_ratio_{w}"]=V[j]/(np.nanmean(vv)+1e-9)
  z["volume_z20"]=(V[j]-np.nanmean(V[j-19:j+1]))/(np.nanstd(V[j-19:j+1])+1e-9)
 # EMA/VWAP-like causal trend distances
 for span in [5,10,20,50]:
  vals=C[j-span+1:j+1]; weights=np.arange(1,span+1)
  ema=np.average(vals,weights=weights)
  z[f"dist_trend_{span}_atr"]=s*(C[j]-ema)/a
 rows.append(z)
feat=pd.DataFrame(rows)
out=base.merge(feat,on="_t",how="left")
new=[c for c in feat.columns if c!="_t"]
print("Rows:",len(out),"new features:",len(new))
print("Median non-null:",f"{out[new].notna().mean().median()*100:.2f}%")
print("Feature groups: price path, efficiency, wick pressure, compression, liquidity sweeps, volume, trend distance")
out.to_parquet("data/v97_rich_market_state_features.parquet",index=False)
print("Saved data/v97_rich_market_state_features.parquet")
print("NEXT: V98 will run one large causal search on these richer market-state features against 1R-6R.")
