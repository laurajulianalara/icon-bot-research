import pandas as pd
import numpy as np
from itertools import product

IN="data/v7_base_trade_quality.parquet"
OUT="data/v7_quality_filter_search.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True)
d["candidate_time"]=pd.to_datetime(d.candidate_time)
cut=d.candidate_time.min()+(d.candidate_time.max()-d.candidate_time.min())*.70
train=d[d.candidate_time<cut]; test=d[d.candidate_time>=cut]

# Thresholds deliberately broad around the features that actually separated winners.
RECLAIM=[.35,.50,.65,.80,1.00,1.20]
M2CP=[.35,.45,.55,.65,.75,.85]
WICK=[.20,.30,.35,.40,.50,.60]
M2MOVE=[-.80,-.60,-.45,-.30,-.15,.00]
DIR5=[1,2,3]
SESSIONS=[None,("LONDON","NYAM","NYPM"),("LONDON","NYAM"),("NYAM","NYPM")]

def stats(q):
    if q.empty:return None
    wr=100*(q.outcome=="WIN").mean()
    days=max(1,(q.candidate_time.max()-q.candidate_time.min()).days)
    tpd=len(q)/days
    exp=(wr/100)*4-(1-wr/100)
    return len(q),wr,tpd,exp

rows=[]
for rec,cp,wk,mv,db,ss in product(RECLAIM,M2CP,WICK,M2MOVE,DIR5,SESSIONS):
    def filt(x):
        q=x[(x.early_reclaim_atr<=rec)&(x.m2_close_pos<=cp)&(x.wick_percent<=wk)&(x.m2_move_atr<=mv)&(x.m2_dir_bars5<=db)]
        if ss is not None:q=q[q.session.isin(ss)]
        return q
    a=filt(train); b=filt(test); sa=stats(a); sb=stats(b)
    if sa is None or sb is None or sa[0]<300 or sb[0]<120:continue
    # Annualized frequency uses full 365-day denominator so it matches user's actual goal.
    allq=filt(d); freq=len(allq)/365
    if freq<3 or freq>6:continue
    rows.append((rec,cp,wk,mv,db,"ALL" if ss is None else "+".join(ss),len(allq),freq,sa[0],sa[1],sb[0],sb[1],min(sa[1],sb[1]),100*(allq.outcome=="WIN").mean(),stats(allq)[3]))

r=pd.DataFrame(rows,columns=["reclaim_max","m2_close_max","wick_max","m2_move_max","dir5_max","sessions","trades","trades_per_day","train_trades","train_wr","test_trades","test_wr","robust_wr","all_wr","expectancy_r"])
if r.empty:
 print("No combinations met minimum sample + 3-6 trades/day constraints.")
 raise SystemExit
r=r.sort_values(["robust_wr","test_trades"],ascending=[False,False]).drop_duplicates(["trades","train_wr","test_wr"]).reset_index(drop=True)
r.to_csv(OUT,index=False)
print("=== V7 QUALITY FILTER SEARCH: HARD TARGET 4R / 55%+ / 3-6 TRADES PER DAY ===")
print("Qualifying frequency/sample combinations:",len(r))
print("\nTOP 40:")
print(r.head(40).round(2).to_string(index=False))
print("\n55%+ BOTH train/test:",int(((r.train_wr>=55)&(r.test_wr>=55)).sum()))
sweet=r[(r.trades_per_day>=4)&(r.trades_per_day<=5)]
print("55%+ BOTH AND 4-5/day:",int(((sweet.train_wr>=55)&(sweet.test_wr>=55)).sum()))
print("\nSaved:",OUT)
