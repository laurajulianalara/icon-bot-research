import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_asia_nyam_threshold_scan.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&
      (df.outcome.isin(["WIN","LOSS"]))&(df.session.isin(["ASIA","NYAM"]))].copy()

CISD=[.90,.925,.95,.96,.97]
DISP=[1.10,1.20,1.25,1.30,1.35,1.40,1.50]
SWEEP=[.15,.20,.25,.30,.35,.40]
cut=df.fill_time.min()+(df.fill_time.max()-df.fill_time.min())*.70

def m(x):
    if x.empty:return (0,np.nan,np.nan,np.nan)
    eq=x.result_r.cumsum()
    return len(x),(x.outcome=="WIN").mean()*100,x.result_r.mean(),abs((eq-eq.cummax()).min())

rows=[]
for c in CISD:
 for d in DISP:
  for sw in SWEEP:
   z=df[(df.confirm_close_pos>=c)&(df.disp_atr>=d)&(df.sweep_atr>=sw)].sort_values("fill_time")
   tr=z[z.fill_time<cut]; va=z[z.fill_time>=cut]
   a=m(tr); b=m(va)
   if a[0]<40 or b[0]<15: continue
   rows.append(dict(cisd_close_min=c,displacement_min_atr=d,sweep_min_atr=sw,
      train_trades=a[0],train_wr=a[1],train_exp_r=a[2],train_dd_r=a[3],
      valid_trades=b[0],valid_wr=b[1],valid_exp_r=b[2],valid_dd_r=b[3],
      robust_wr=min(a[1],b[1])))
r=pd.DataFrame(rows).sort_values(["robust_wr","valid_trades"],ascending=[False,False])
r.to_csv(OUTFILE,index=False)
print("\n=== V4 ASIA + NYAM THRESHOLD ROBUSTNESS — 4R ===")
print("Still excluded: volume, absorption, FVG, IFVG")
print("Minimum sample: 40 train / 15 validation")
print("\nTOP 30:")
print(r.head(30).round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
