import pandas as pd, numpy as np
q=pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# Rebuild V12 interaction features
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
q["close_x_reclaim"]=q.m2_close_pos*q.early_reclaim_atr
q["sweep_minus_reclaim"]=q.sweep_atr-q.early_reclaim_atr
q["impulse_minus_reclaim"]=q.reversal_impulse-q.early_reclaim_atr
q["quality_balance"]=q.rejection_quality+q.impulse_to_reclaim-q.reclaim_to_sweep
# Locked Option 1: reject only when >=3 bad signals
bad=(q.reclaim_x_wick>.13).astype(int)+(q.close_x_reclaim>.16).astype(int)+(q.sweep_minus_reclaim<.10).astype(int)+(q.impulse_minus_reclaim<.00).astype(int)+(q.quality_balance<.10).astype(int)
z=q[bad<3].copy()
et=z.candidate_time.dt.tz_convert("America/New_York")
z["month"]=et.dt.to_period("M").astype(str)
def maxdd(x):
 e=x.r.cumsum();return float((e.cummax()-e).max())
rows=[]
for m,g in z.groupby("month"):
 if not m.startswith("2026"):continue
 rows.append([m,len(g),100*g.win.mean(),g.r.sum(),g.r.mean(),maxdd(g)])
r=pd.DataFrame(rows,columns=["month","trades","wr","net_r","expectancy_r","max_dd_r"])
print("=== OPTION 1 — 2026 MONTHLY BREAKDOWN ===")
print(r.round(2).to_string(index=False))
print("\n2026 total:",len(z[et.dt.year==2026]),"trades")
print("Saved: data/option1_2026_monthly.csv")
r.to_csv("data/option1_2026_monthly.csv",index=False)
