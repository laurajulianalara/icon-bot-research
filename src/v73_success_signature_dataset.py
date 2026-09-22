import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
raw=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
old=pd.read_parquet("data/v7_base_trade_quality.parquet").copy()
for d in (one,raw):
    d["time_ny"]=pd.to_datetime(d.time_ny)
# Detect time column in saved V7 file.
tc=next(c for c in ["candidate_time","time_ny","time"] if c in old.columns)
old[tc]=pd.to_datetime(old[tc])
idx=pd.Series(one.index,index=one.time_ny).to_dict()

# Old successful population: use actual saved V7 rows and only information
# observable no later than the historical entry timestamp. Outcome is a label,
# never a predictor.
if "outcome" in old.columns:
    winmask=old.outcome.astype(str).str.upper().str.contains("WIN")
elif "result" in old.columns:
    winmask=old.result.astype(str).str.upper().str.contains("WIN")
else:
    # V7 canonical 4R files commonly store pnl_r.
    col=next((c for c in ["pnl_r","r_multiple","R"] if c in old.columns),None)
    if col is None: raise RuntimeError("Cannot locate V7 outcome column: "+str(old.columns.tolist()))
    winmask=pd.to_numeric(old[col],errors="coerce")>0
wins=old[winmask].copy()

# Build a richer causal snapshot from bars T-15 through T+2.
def signature(t,direction):
    i=idx.get(t)
    if i is None or i<20 or i+2>=len(one): return None
    sg=1 if direction=="LONG" else -1
    a=one.iloc[i-19:i+1]
    tr=pd.concat([a.high-a.low,(a.high-a.close.shift()).abs(),(a.low-a.close.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.mean())
    if not np.isfinite(atr) or atr<=0:return None
    z={"candidate_time":t,"direction":direction,"atr":atr}
    base=float(one.iloc[i].close)
    for k in range(-10,3):
        b=one.iloc[i+k]
        z[f"ret_{k}"]=(float(b.close)-base)/atr*sg
        z[f"range_{k}"]=(float(b.high)-float(b.low))/atr
        z[f"body_{k}"]=abs(float(b.close)-float(b.open))/atr
        z[f"closepos_{k}"]=((b.close-b.low)/(b.high-b.low) if b.high>b.low else .5)
    pre=one.iloc[i-10:i+3]
    z["pre_range_atr"]=(float(pre.high.max())-float(pre.low.min()))/atr
    z["trend10_atr"]=(float(one.iloc[i].close)-float(one.iloc[i-10].close))/atr*sg
    z["vol_ratio_5_20"]=float((one.iloc[i-4:i+1].high-one.iloc[i-4:i+1].low).mean()/max((one.iloc[i-19:i+1].high-one.iloc[i-19:i+1].low).mean(),1e-9))
    return z

# Map V7 wins back to raw candidate direction/time.
keydir=raw.set_index("time_ny")["direction"].to_dict()
rows=[]
for _,r in wins.iterrows():
    t=r[tc]; direction=r["direction"] if "direction" in r.index else keydir.get(t)
    if direction not in ("LONG","SHORT"): continue
    s=signature(t,direction)
    if s: rows.append(s)
w=pd.DataFrame(rows)
w.to_parquet("data/v73_historical_winner_entry_signatures.parquet",index=False)

print("=== HISTORICAL WINNER ENTRY-SIGNATURE DATASET ===")
print("Saved V7 rows:",len(old))
print("Historical 4R winners found:",len(wins))
print("Causal entry signatures built:",len(w))
print("Features per trade:",len(w.columns)-2)
print("Saved: data/v73_historical_winner_entry_signatures.parquet")
print()
print("All predictor values are from T-10 through T+2 only; no post-entry/future bars are included.")
print("NEXT: compare these winner signatures against causal losers and search for stable clusters shared across both years.")
