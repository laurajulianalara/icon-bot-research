import pandas as pd, numpy as np
ONE="data/mnq_2024_09_22_to_2025_09_16_continuous_1m.parquet"
CAND="data/reversal_candidates_2024_09_22_to_2025_09_16.parquet"
BASE="data/v55_prior_year_base_trade_quality.parquet"
OUT="data/v56_icon_bot_funded_prior_year_trades.csv"
RTH=.576132; WTH=.183258; RRS=[1,2,3,4,5,6]

one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); q=pd.read_parquet(BASE)
for x,c in [(one,"time_ny"),(cand,"time_ny"),(q,"candidate_time")]: x[c]=pd.to_datetime(x[c])
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
# Rebuild the exact derived field used by frozen Option 2A / Icon Bot Funded.
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
# Same pre-Option2 quality population used in the locked research chain.
q=q[(q.early_reclaim_atr<=.90)&(q.m2_close_pos<=.80)&(q.wick_percent<=.60)&(q.m2_move_atr<=.15)&(q.m2_dir_bars5<=4)].copy()
# Frozen finalist thresholds: DO NOT recalculate from this holdout.
z=q[(q.early_reclaim_atr<RTH)|(q.reclaim_x_wick<WTH)].copy().sort_values("candidate_time").reset_index(drop=True)

idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
def replay(row,rr):
 c=cm.get((row.candidate_time,str(row.direction)))
 if c is None:return "MISSING"
 i=idx.get(c.time_ny)
 if i is None or i+3>=len(one):return "MISSING"
 j=i+3
 if one.iloc[j].ticker!=c.ticker:return "MISSING"
 if pd.notna(c.next_same_extreme_time) and one.iloc[j].time_ny>=c.next_same_extreme_time:return "MISSING"
 entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
 risk=entry-stop if c.direction=="LONG" else stop-entry
 if risk<=0:return "MISSING"
 target=entry+rr*risk if c.direction=="LONG" else entry-rr*risk
 for k in range(j,min(j+241,len(one))):
  b=one.iloc[k]
  if b.ticker!=c.ticker:break
  sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
  th=b.high>=target if c.direction=="LONG" else b.low<=target
  if sh:return "LOSS"
  if th:return "WIN"
 return "UNRESOLVED"

print("=== ICON BOT FUNDED — FROZEN PRIOR-YEAR HOLDOUT ===")
print(f"Frozen thresholds: early_reclaim_atr < {RTH} OR reclaim_x_wick < {WTH}")
print("Selected trades:",len(z))
rows=[]
for rr in RRS:
 oc=z.apply(lambda r:replay(r,rr),axis=1)
 w=int((oc=="WIN").sum());l=int((oc=="LOSS").sum());u=int((oc=="UNRESOLVED").sum());m=int((oc=="MISSING").sum());res=w+l
 wr=100*w/res if res else np.nan; net=w*rr-l; exp=net/res if res else np.nan
 rows.append([rr,len(z),w,l,u,m,wr,net,exp])
 print(f"{rr}R: {w}W/{l}L | WR {wr:.2f}% | net {net:+.0f}R | unresolved {u} | missing {m}")
 if rr==4:z["outcome_4r"]=oc
pd.DataFrame(rows,columns=["rr","selected","wins","losses","unresolved","missing","wr_pct","net_r","expectancy_r"]).to_csv("data/v56_icon_bot_funded_prior_year_rr.csv",index=False)
z.to_csv(OUT,index=False)
print("\nMONTHLY 4R")
r=z[z.outcome_4r.isin(["WIN","LOSS"])].copy(); r["month"]=r.candidate_time.dt.tz_convert("America/New_York").dt.to_period("M").astype(str);r["win"]=(r.outcome_4r=="WIN").astype(int)
print(r.groupby("month").win.agg(trades="size",wins="sum",wr=lambda x:100*x.mean()).round(2).to_string())
print("\nSaved:",OUT)
