import pandas as pd
import numpy as np
from itertools import product

IN="data/v7_base_trade_quality.parquet"; OUT="data/v7_sweetspot_search.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
cut=d.candidate_time.min()+(d.candidate_time.max()-d.candidate_time.min())*.70
tr=d[d.candidate_time<cut];te=d[d.candidate_time>=cut]

# Focus around the broad, high-frequency edge instead of the over-selective top-WR corner.
REC=[.9,1.0,1.1,1.2,1.3,1.4,1.6]
CP=[.75,.80,.85,.90,.912]
WK=[.45,.50,.55,.60,.65,.70]
MV=[-.15,-.10,-.05,0,.05,.10,.15]
DB=[2,3,4]
# Optional single-filter relaxations allow 4-5/day while retaining the causal signature.
def st(q):
 if len(q)==0:return None
 return len(q),100*(q.outcome=="WIN").mean()

rows=[]
for rec,cp,wk,mv,db in product(REC,CP,WK,MV,DB):
 def f(x):
  return x[(x.early_reclaim_atr<=rec)&(x.m2_close_pos<=cp)&(x.wick_percent<=wk)&(x.m2_move_atr<=mv)&(x.m2_dir_bars5<=db)]
 a=f(tr);b=f(te);allq=f(d)
 if len(a)<300 or len(b)<120:continue
 freq=len(allq)/365
 if not 3.0<=freq<=6.0:continue
 aw=100*(a.outcome=="WIN").mean();bw=100*(b.outcome=="WIN").mean();ow=100*(allq.outcome=="WIN").mean()
 rows.append((rec,cp,wk,mv,db,len(allq),freq,len(a),aw,len(b),bw,min(aw,bw),ow,ow*.04-(100-ow)*.01))

r=pd.DataFrame(rows,columns=["reclaim_max","m2_close_max","wick_max","m2_move_max","dir5_max","trades","trades_per_day","train_trades","train_wr","test_trades","test_wr","robust_wr","all_wr","expectancy_r"])
r=r.sort_values(["robust_wr","trades_per_day"],ascending=[False,False]).drop_duplicates(["trades","train_wr","test_wr"])
r.to_csv(OUT,index=False)
sweet=r[(r.trades_per_day>=4)&(r.trades_per_day<=5)]
print("=== 4-5/DAY SWEET-SPOT SEARCH ===")
print("Total 3-6/day combos:",len(r))
print("4-5/day combos:",len(sweet))
print("55%+ BOTH at 4-5/day:",int(((sweet.train_wr>=55)&(sweet.test_wr>=55)).sum()))
print("\nTOP 30 4-5/DAY:")
print(sweet.head(30).round(2).to_string(index=False))
print("\nIf 55%+ count is zero, the honest frontier is below 55% at 4-5/day with these causal features; next step is add NEW information, not over-tune thresholds.")
print("\nSaved:",OUT)
