import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_no_fib_reversal_location_scan.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

cut=df.fill_time.min()+(df.fill_time.max()-df.fill_time.min())*.70
CISD=[.85,.90,.925,.95]
DISP=[1.0,1.1,1.2,1.25,1.3,1.4]
SR=[None,.15,.30,.50]
SWEEP=[None,.05,.15,.30]

def m(x):
    if len(x)<1:return None
    return len(x),(x.outcome=="WIN").mean()*100,x.result_r.mean()

rows=[]
for c in CISD:
 for d in DISP:
  for sr in SR:
   for sw in SWEEP:
    z=df[(df.confirm_close_pos>=c)&(df.disp_atr>=d)]
    if sr is not None:z=z[z.sr_dist_atr<=sr]
    if sw is not None:z=z[z.sweep_atr>=sw]
    tr=z[z.fill_time<cut]; va=z[z.fill_time>=cut]
    a=m(tr); b=m(va)
    if not a or not b or a[0]<100 or b[0]<50:continue
    rows.append(dict(cisd_close_min=c,displacement_min_atr=d,sr_max_atr=sr,sweep_min_atr=sw,
      train_trades=a[0],train_wr=a[1],train_exp_r=a[2],
      valid_trades=b[0],valid_wr=b[1],valid_exp_r=b[2],robust_wr=min(a[1],b[1])))

r=pd.DataFrame(rows).sort_values(["robust_wr","valid_trades"],ascending=[False,False])
r.to_csv(OUTFILE,index=False)
print("\n=== V4 NO-FIB: REVERSAL LOCATION SCAN ===")
print("Still excluded: volume, absorption, FVG, IFVG")
print("Minimum sample: 100 train / 50 validation")
print("\nTOP 30:")
print(r.head(30).round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
