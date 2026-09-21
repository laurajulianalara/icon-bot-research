import pandas as pd
import numpy as np

IN="data/v7_base_trade_quality.parquet"; OUT="data/v7_drawdown_forensics.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
q=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.0,-1.0);q["date"]=q.candidate_time.dt.date

# Per-day loss clustering and realized daily result.
daily=[]
for day,z in q.groupby("date"):
 z=z.sort_values("candidate_time"); losses=int((z.win==0).sum()); wins=int(z.win.sum())
 e=z.r.cumsum(); peak=np.maximum.accumulate(np.r_[0,e.to_numpy()]); path=np.r_[0,e.to_numpy()]
 dd=float(np.max(peak-path))
 # consecutive losses inside day
 arr=z.win.to_numpy();cur=mx=0
 for x in arr:
  cur=0 if x else cur+1;mx=max(mx,cur)
 daily.append((day,len(z),wins,losses,float(z.r.sum()),dd,mx))
D=pd.DataFrame(daily,columns=["date","trades","wins","losses","net_r","peak_to_trough_dd_r","max_loss_streak"])
D.to_csv(OUT,index=False)

print("=== DRAWDOWN FORENSICS — $250/RISK ===")
print("Trading days:",len(D))
for k in range(0,7):
 print(f"Days with exactly {k} losses: {(D.losses==k).sum()} ({100*(D.losses==k).mean():.2f}%)")
print("Days with 3+ losses:",int((D.losses>=3).sum()),f"({100*(D.losses>=3).mean():.2f}%)")
print("Days with 4+ losses:",int((D.losses>=4).sum()),f"({100*(D.losses>=4).mean():.2f}%)")
print("Days with >=3R intraday DD:",int((D.peak_to_trough_dd_r>=3).sum()),f"({100*(D.peak_to_trough_dd_r>=3).mean():.2f}%)")
print("Days with >=4R intraday DD:",int((D.peak_to_trough_dd_r>=4).sum()),f"({100*(D.peak_to_trough_dd_r>=4).mean():.2f}%)")
print("Days with >=5R intraday DD:",int((D.peak_to_trough_dd_r>=5).sum()),f"({100*(D.peak_to_trough_dd_r>=5).mean():.2f}%)")
print("Worst intraday DD:",D.peak_to_trough_dd_r.max(),"R = $",D.peak_to_trough_dd_r.max()*250)
print("Worst daily close:",D.net_r.min(),"R = $",D.net_r.min()*250)
print("Losing days:",int((D.net_r<0).sum()),f"({100*(D.net_r<0).mean():.2f}%)")
print("\nWORST DAYS:")
print(D.sort_values(["peak_to_trough_dd_r","net_r"],ascending=[False,True]).head(20).to_string(index=False))
print("\nSaved:",OUT)
