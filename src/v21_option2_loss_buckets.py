import pandas as pd, numpy as np
q=pd.read_csv("data/v19_failed_reversal_sequence.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
print("=== V21 OPTION 2 LOSS BUCKETS ===")
print(f"Trades {len(q)} | wins {q.win.sum()} | losses {(1-q.win).sum()} | WR {100*q.win.mean():.2f}%")
# score bands to see how many losses live in weakest-quality tail
q["score_band"]=pd.qcut(q.score,10,duplicates="drop")
x=q.groupby("score_band",observed=True).agg(trades=("win","size"),wins=("win","sum"),wr=("win","mean"),avg_score=("score","mean"))
x["losses"]=x.trades-x.wins;x["wr"]*=100
print("\nDECILES BY CAUSAL QUALITY SCORE")
print(x[["trades","wins","losses","wr","avg_score"]].round(2).to_string())
# cluster vs isolated losses
loss=q[q.win==0]
print(f"\nLosses in 3+ streak clusters: {int(q.cluster_loss.sum())}")
print(f"Other losses: {len(loss)-int(q.cluster_loss.sum())}")
print(f"Cluster share of all losses: {100*q.cluster_loss.sum()/len(loss):.2f}%")
# late-session overlap
late=q.mins_into_session>=90
print(f"\nLate-session (>=90 min) trades: {late.sum()} | WR {100*q.loc[late,'win'].mean():.2f}% | losses {int((1-q.loc[late,'win']).sum())}")
print(f"Late-session cluster losses: {int(q.loc[late,'cluster_loss'].sum())}")
# combined weak quality / late session
for s in [.30,.35,.40,.45,.50]:
 bad=(q.score<s)
 z=q[~bad]
 print(f"score >= {s:.2f}: keep {len(z):4d} | losses {int((1-z.win).sum()):3d} | WR {100*z.win.mean():5.2f}% | removed {bad.sum():3d}")
q.to_csv("data/v21_option2_loss_buckets.csv",index=False)
