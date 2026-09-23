import pandas as pd, numpy as np
print("=== V103 1M FORENSIC SIGNATURE SEARCH ===")
d=pd.read_parquet("data/v102_1m_cisd_choch_liquidity_forensics.parquet").copy()
# Goal: find interpretable signatures enriched in the 1,911 reference trades.
# This is forensic discovery only; future-timed confirmations are grouped by the minute they become available.
y=d.is_reference.astype(bool).to_numpy()
def report(name,mask):
 mask=np.asarray(mask)&np.ones(len(d),dtype=bool); n=mask.sum()
 if n<50:return
 refs=(y&mask).sum(); rate=refs/n; base=y.mean(); recall=refs/y.sum()
 print(f"{name:62s} n={n:6d} REF={refs:4d} purity={rate*100:6.2f}% lift={rate/base:5.2f}x recall={recall*100:6.2f}%")
print(f"BASE reference prevalence: {y.mean()*100:.2f}% ({y.sum()}/{len(y)})")
# Candidate-time information.
report("sweep",d.swept_liquidity==1)
report("sweep + reclaim",(d.swept_liquidity==1)&(d.sweep_reclaimed==1))
for q in [.25,.5,.75,1.0,1.25]:
 report(f"sweep + depth <= {q} ATR",(d.swept_liquidity==1)&(d.sweep_depth_atr<=q))
 report(f"sweep+reclaim + depth <= {q} ATR",(d.swept_liquidity==1)&(d.sweep_reclaimed==1)&(d.sweep_depth_atr<=q))
# Confirmation information, only considered at/after the stated minute.
for h in [1,2,3,5,8]:
 for sig in ["cisd","choch"]:
  col=f"{sig}_by_{h}m"
  report(f"@{h}m sweep + {sig.upper()}",(d.swept_liquidity==1)&(d[col]==1))
  report(f"@{h}m sweep+reclaim + {sig.upper()}",(d.swept_liquidity==1)&(d.sweep_reclaimed==1)&(d[col]==1))
 report(f"@{h}m sweep + CISD + CHOCH",(d.swept_liquidity==1)&(d[f"cisd_by_{h}m"]==1)&(d[f"choch_by_{h}m"]==1))
# Search compact causal combinations; never use is_reference as input.
best=[]
for sw in [0,1]:
 for rec in [0,1]:
  for depth in [.25,.5,.75,1,1.5,3]:
   base=np.ones(len(d),bool)
   if sw: base&=d.swept_liquidity.eq(1).to_numpy()
   if rec: base&=d.sweep_reclaimed.eq(1).to_numpy()
   base&=d.sweep_depth_atr.le(depth).fillna(False).to_numpy()
   for h in [1,2,3,5,8]:
    for ci in [0,1]:
     for ch in [0,1]:
      z=base.copy()
      if ci:z&=d[f"cisd_by_{h}m"].eq(1).to_numpy()
      if ch:z&=d[f"choch_by_{h}m"].eq(1).to_numpy()
      n=z.sum(); refs=(z&y).sum()
      if n>=100 and refs>=20:
       purity=refs/n; recall=refs/y.sum(); score=purity*np.sqrt(refs)
       best.append((score,purity,recall,n,refs,sw,rec,depth,h,ci,ch))
print("\nTOP FORENSIC SIGNATURES")
for z in sorted(best,reverse=True)[:20]:
 _,p,r,n,refs,sw,rec,dep,h,ci,ch=z
 print(f"purity={p*100:5.2f}% lift={p/y.mean():4.2f}x recall={r*100:5.1f}% n={n:5d} refs={refs:4d} | sweep={sw} reclaim={rec} depth<={dep} @ {h}m CISD={ci} CHOCH={ch}")
print("\nNEXT: V104 uses the strongest signatures in a true minute-by-minute sequential trade simulation and scores 1R-6R.")
