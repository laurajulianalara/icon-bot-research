import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_frequency_expansion_scan.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

# Wider but still thesis-driven search. Goal: see whether frequency can rise
# without abandoning the strong-reversal logic.
CISD=[.80,.825,.85,.875,.90,.925,.95,.96,.97]
DISP=[.50,.60,.75,.90,1.0,1.1,1.2,1.3]
SWEEP=[None,.05,.10,.15,.20,.25,.30]
rows=[]

for session in ["ASIA","LONDON","NYAM","NYPM"]:
    b=df[df.session==session].sort_values("fill_time")
    cut=b.fill_time.min()+(b.fill_time.max()-b.fill_time.min())*.70
    for c in CISD:
      for d in DISP:
       for sw in SWEEP:
        z=b[(b.confirm_close_pos>=c)&(b.disp_atr>=d)]
        if sw is not None:z=z[z.sweep_atr>=sw]
        tr=z[z.fill_time<cut]; va=z[z.fill_time>=cut]
        if len(tr)<75 or len(va)<30: continue
        tw=(tr.outcome=="WIN").mean()*100; vw=(va.outcome=="WIN").mean()*100
        rows.append(dict(session=session,cisd=c,disp=d,sweep=sw,
          train_trades=len(tr),valid_trades=len(va),total_trades=len(z),
          trades_per_day=len(z)/365,train_wr=tw,valid_wr=vw,robust_wr=min(tw,vw),
          expectancy_r=z.result_r.mean()))

r=pd.DataFrame(rows)
if r.empty:
 print("No configurations met the sample minimums.")
else:
 r["passes_50"]=r.robust_wr>=50
 r["passes_55"]=r.robust_wr>=55
 r=r.sort_values(["passes_50","total_trades","robust_wr"],ascending=[False,False,False])
 r.to_csv(OUTFILE,index=False)
 print("\n=== V4 FREQUENCY EXPANSION SCAN — 4R ===")
 print("Goal: increase trades while keeping >=50% robust WR.")
 for s in ["ASIA","LONDON","NYAM","NYPM"]:
   x=r[(r.session==s)&(r.robust_wr>=50)].sort_values(["total_trades","robust_wr"],ascending=[False,False]).head(15)
   print(f"\n--- {s}: HIGHEST VOLUME WITH >=50% ROBUST WR ---")
   print(x.round(2).to_string(index=False) if len(x) else "None")
 print("\nSaved:",OUTFILE)
