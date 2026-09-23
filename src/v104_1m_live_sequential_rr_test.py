import pandas as pd, numpy as np
print("=== V104 1M LIVE SEQUENTIAL RR TEST ===")
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
c=pd.read_parquet("data/v102_1m_cisd_choch_liquidity_forensics.parquet").copy()
tc="time_ny" if "time_ny" in m.columns else next(x for x in m if "time" in x.lower())
m["_t"]=pd.to_datetime(m[tc],utc=True,errors="coerce"); m=m.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
idx=pd.Series(np.arange(len(m)),index=m["_t"]); H=m.high.astype(float).to_numpy(); L=m.low.astype(float).to_numpy(); O=m.open.astype(float).to_numpy()
c["candidate_time"]=pd.to_datetime(c.candidate_time,utc=True)
# Candidate-time filters only. CISD/CHOCH are NOT used here because V103 showed they do not improve reference selection early enough.
rules=[
 ("ALL",np.ones(len(c),bool)),
 ("SWEEP",c.swept_liquidity.eq(1).to_numpy()),
 ("SWEEP_D025",(c.swept_liquidity.eq(1)&c.sweep_depth_atr.le(.25)).to_numpy()),
 ("SWEEP_D050",(c.swept_liquidity.eq(1)&c.sweep_depth_atr.le(.50)).to_numpy()),
 ("SWEEP_D075",(c.swept_liquidity.eq(1)&c.sweep_depth_atr.le(.75)).to_numpy()),
 ("SWEEP_RECLAIM_D025",(c.swept_liquidity.eq(1)&c.sweep_reclaimed.eq(1)&c.sweep_depth_atr.le(.25)).to_numpy()),
 ("SWEEP_RECLAIM_D050",(c.swept_liquidity.eq(1)&c.sweep_reclaimed.eq(1)&c.sweep_depth_atr.le(.50)).to_numpy()),
]
def simulate(mask,R):
 wins=losses=amb=0; next_free=-1
 for _,r in c.loc[mask].sort_values("candidate_time").iterrows():
  j=idx.get(r.candidate_time,None)
  if j is None: continue
  j=int(j); entry_i=j+1
  if entry_i>=len(m) or entry_i<=next_free: continue
  entry=O[entry_i]; stop=float(r.extreme)+(.25 if r.direction=="SHORT" else -.25); risk=abs(entry-stop)
  if risk<=0: continue
  target=entry+R*risk if r.direction=="LONG" else entry-R*risk
  end=min(len(m),entry_i+241); done=False
  for q in range(entry_i,end):
   hs=H[q]>=stop if r.direction=="SHORT" else L[q]<=stop
   ht=H[q]>=target if r.direction=="LONG" else L[q]<=target
   if hs and ht: losses+=1; amb+=1; next_free=q; done=True; break
   if hs: losses+=1; next_free=q; done=True; break
   if ht: wins+=1; next_free=q; done=True; break
  if not done: next_free=end-1
 return wins,losses,amb
print("Entry = next 1m bar OPEN after candidate. One position at a time. Stop-first on ambiguous bars.")
for name,mask in rules:
 print("\n"+name)
 for R in range(1,7):
  w,l,a=simulate(mask,R); n=w+l
  print(f"{R}R trades={n:5d} WR={100*w/n if n else 0:6.2f}% W={w} L={l} ambiguous_stop_first={a}")
print("\nNEXT: If 1m sweep rules do not materially recover high-R performance, V105 stops hand-picked filters and builds the broader native-1m strategy discovery engine.")
