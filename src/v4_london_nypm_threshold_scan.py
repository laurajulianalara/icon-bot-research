import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_london_nypm_threshold_scan.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&
      df.outcome.isin(["WIN","LOSS"])&df.session.isin(["LONDON","NYPM"])].copy()

CISD=[.85,.90,.925,.95,.96,.97]
DISP=[.75,1.0,1.1,1.2,1.25,1.3,1.4,1.5]
SWEEP=[None,.05,.15,.20,.25,.30,.35,.40]
rows=[]

def m(x):
    if x.empty:return (0,np.nan,np.nan,np.nan)
    eq=x.result_r.cumsum()
    return len(x),(x.outcome=="WIN").mean()*100,x.result_r.mean(),abs((eq-eq.cummax()).min())

for session in ["LONDON","NYPM"]:
    base=df[df.session==session].sort_values("fill_time")
    cut=base.fill_time.min()+(base.fill_time.max()-base.fill_time.min())*.70
    for c in CISD:
      for d in DISP:
       for sw in SWEEP:
        z=base[(base.confirm_close_pos>=c)&(base.disp_atr>=d)]
        if sw is not None:z=z[z.sweep_atr>=sw]
        tr=z[z.fill_time<cut]; va=z[z.fill_time>=cut]
        a=m(tr); b=m(va)
        if a[0]<30 or b[0]<12:continue
        rows.append(dict(session=session,cisd_close_min=c,displacement_min_atr=d,sweep_min_atr=sw,
          train_trades=a[0],train_wr=a[1],train_exp_r=a[2],train_dd_r=a[3],
          valid_trades=b[0],valid_wr=b[1],valid_exp_r=b[2],valid_dd_r=b[3],
          robust_wr=min(a[1],b[1])))

r=pd.DataFrame(rows).sort_values(["session","robust_wr","valid_trades"],ascending=[True,False,False])
r.to_csv(OUTFILE,index=False)
print("\n=== V4 LONDON + NYPM SEPARATE THRESHOLD SCAN — 4R ===")
print("Still excluded: volume, absorption, FVG, IFVG")
for s in ["LONDON","NYPM"]:
    print(f"\n--- {s} TOP 20 ---")
    print(r[r.session==s].head(20).round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
