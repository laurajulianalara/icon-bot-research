import bisect, json
import pandas as pd
import numpy as np

TZ="America/New_York"; RTH=.576132; WTH=.183258; V15_THRESHOLD=.145921011058
RRS=[1,2,3,4,5,6]; RISK_DOLLARS=300
PERIODS=[
 {"name":"PRIOR","one":"data/mnq_2024_09_22_to_2025_09_16_continuous_1m.parquet","cand":"data/reversal_candidates_2024_09_22_to_2025_09_16.parquet","features":"data/v55_prior_year_base_trade_quality.parquet","apply_v8":True},
 {"name":"CURRENT","one":"data/mnq_continuous_1m.parquet","cand":"data/reversal_candidates.parquet","features":"data/v11_reversal_state_forensics.csv","apply_v8":False},
]
with open("data/icon_v15_pine_reference.json") as f: REF=json.load(f)
for k in REF: REF[k]=sorted(float(x) for x in REF[k])
WEIGHTS=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]

def frozen_rank(v,arr):
 if not np.isfinite(v): return np.nan
 lo=bisect.bisect_left(arr,float(v)); hi=bisect.bisect_right(arr,float(v))
 return (lo+(hi-lo+1)/2)/len(arr) if hi>lo else min(1,max(0,(lo+1)/len(arr)))

def prep(q):
 q=q.copy()
 q["rejection_quality"]=(1-q.m2_close_pos.clip(0,1))*(1-q.wick_percent.clip(0,1))
 q["reversal_impulse"]=-q.m2_move_atr
 q["reclaim_to_sweep"]=q.early_reclaim_atr/(q.sweep_atr.abs()+.05)
 q["impulse_to_reclaim"]=q.reversal_impulse/(q.early_reclaim_atr.abs()+.05)
 q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
 q["close_x_reclaim"]=q.m2_close_pos*q.early_reclaim_atr
 q["sweep_minus_reclaim"]=q.sweep_atr-q.early_reclaim_atr
 q["impulse_minus_reclaim"]=q.reversal_impulse-q.early_reclaim_atr
 q["quality_balance"]=q.rejection_quality*q.impulse_to_reclaim/(1+q.reclaim_to_sweep)
 parts=[]
 for col,hi,w in WEIGHTS:
  r=q[col].map(lambda v:frozen_rank(v,REF[col])); comp=r if hi else 1-r
  parts += [comp]*w
 q["score"]=pd.concat(parts,axis=1).mean(axis=1)
 return q

def run_period(p):
 one=pd.read_parquet(p["one"]); cand=pd.read_parquet(p["cand"])
 q=pd.read_parquet(p["features"]) if p["features"].endswith(".parquet") else pd.read_csv(p["features"])
 one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
 q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True); q["candidate_time_et"]=q.candidate_time.dt.tz_convert(TZ)
 one=one.sort_values("time_ny").reset_index(drop=True)
 cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
 cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
 if p["apply_v8"]:
  q=q[(q.early_reclaim_atr<=.90)&(q.m2_close_pos<=.80)&(q.wick_percent<=.60)&(q.m2_move_atr<=.15)&(q.m2_dir_bars5<=4)].copy()
 q=prep(q); q=q[q.score>=V15_THRESHOLD].copy()
 q=q[~((q.early_reclaim_atr>=RTH)&(q.reclaim_x_wick>=WTH))].sort_values("candidate_time_et").reset_index(drop=True)
 idx=pd.Series(one.index,index=one.time_ny).to_dict(); cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
 sel=[]; daily={}
 for _,r in q.iterrows():
  c=cm.get((r.candidate_time_et,str(r.direction)))
  if c is None: continue
  i=idx.get(c.time_ny)
  if i is None or i+3>=len(one): continue
  j=i+3; signal=one.iloc[j].time_ny
  if one.iloc[j].ticker!=c.ticker: continue
  if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time: continue
  entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
  risk=entry-stop if c.direction=="LONG" else stop-entry
  if risk<=0: continue
  day=signal.tz_convert(TZ).date()
  if daily.get(day,0)>=6: continue
  daily[day]=daily.get(day,0)+1
  sel.append({"period":p["name"],"candidate_time":r.candidate_time,"candidate_time_et":r.candidate_time_et,"entry_time":signal,"date_et":str(day),"session":r.session,"direction":r.direction,"score":r.score,"entry":entry,"stop":stop,"risk_points":risk,"_j":j,"_ticker":c.ticker})
 b=pd.DataFrame(sel)
 if b.empty:return b
 def replay(r,rr):
  j=int(r._j); target=r.entry+rr*r.risk_points if r.direction=="LONG" else r.entry-rr*r.risk_points
  for k in range(j,min(j+241,len(one))):
   bar=one.iloc[k]
   if bar.ticker!=r._ticker: break
   sh=bar.low<=r.stop if r.direction=="LONG" else bar.high>=r.stop
   th=bar.high>=target if r.direction=="LONG" else bar.low<=target
   if sh:return "LOSS"
   if th:return "WIN"
  return "UNRESOLVED"
 def mfe(r):
  j=int(r._j); best=0.
  for k in range(j,min(j+241,len(one))):
   bar=one.iloc[k]
   if bar.ticker!=r._ticker: break
   sh=bar.low<=r.stop if r.direction=="LONG" else bar.high>=r.stop
   if sh: break
   fav=(float(bar.high)-r.entry)/r.risk_points if r.direction=="LONG" else (r.entry-float(bar.low))/r.risk_points
   best=max(best,fav)
  return best
 for rr in RRS:b[f"{rr}R"]=b.apply(lambda r:replay(r,rr),axis=1)
 b["max_R"]=b.apply(mfe,axis=1)
 return b.drop(columns=["_j","_ticker"])

pieces=[]
for p in PERIODS:
 print("\nProcessing",p["name"],"...",flush=True); x=run_period(p); print(p["name"],"2B trades:",len(x)); pieces.append(x)
b=pd.concat(pieces,ignore_index=True).sort_values("entry_time").drop_duplicates(["candidate_time_et","session","direction"],keep="last").reset_index(drop=True)
b["date_et"]=pd.to_datetime(b.date_et).dt.date
print("\n============================================================\nTHE ICON — OPTION 2B FULL TWO-YEAR TEST\n============================================================")
print("Period:",b.entry_time.min(),"->",b.entry_time.max()); print("Trades:",len(b))
daily=b.groupby("date_et").size()
print("Active trade days:",len(daily)); print("Avg trades/active day:",round(daily.mean(),2)); print("Median trades/active day:",round(daily.median(),2)); print("Max trades/day:",int(daily.max()))
weekdays=pd.date_range(pd.Timestamp(b.date_et.min()),pd.Timestamp(b.date_et.max()),freq="B")
zero=sum(d.date() not in set(b.date_et) for d in weekdays)
print("Weekdays with zero 2B trades:",zero,"/",len(weekdays))
print("\n=== RR 1R THROUGH 6R ==="); rrrows=[]
for rr in RRS:
 s=b[f"{rr}R"]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum()); u=int((s=="UNRESOLVED").sum()); wr=100*w/(w+l) if w+l else np.nan; pnl=w*rr*300-l*300
 rrrows.append([rr,len(b),w,l,u,wr,pnl]); print(f"{rr}R | {w}W / {l}L / {u}U | WR {wr:.2f}% | PnL @ $300: {pnl:,.0f}")
print("\n=== SESSION DISTRIBUTION + WR ===")
for sess,x in b.groupby("session"):
 wrs=[]
 for rr in RRS:
  s=x[f"{rr}R"]; w=(s=="WIN").sum(); l=(s=="LOSS").sum(); wrs.append(100*w/(w+l) if w+l else np.nan)
 print(f"{sess:8s} | {len(x):4d} | "+" | ".join(f"{rr}R {wr:.2f}%" for rr,wr in zip(RRS,wrs)))
print("\n=== R EXCURSION ==="); print(f"Average max R: {b.max_R.mean():.2f}R"); print(f"Median max R: {b.max_R.median():.2f}R"); print(f"Highest max R: {b.max_R.max():.2f}R")
for r in [1,2,3,4,5,6,8,10,15,20]:
 n=int((b.max_R>=r).sum()); print(f"Reached {r}R+: {n}/{len(b)} ({100*n/len(b):.1f}%)")
def streak(s):
 cur=mx=0
 for v in s: cur=cur+1 if v=="LOSS" else 0; mx=max(mx,cur)
 return mx
print("\nLoss streaks | 1R:",streak(b["1R"]),"| 2R:",streak(b["2R"]),"| 4R:",streak(b["4R"]))
pd.DataFrame(rrrows,columns=["rr","trades","wins","losses","unresolved","wr_pct","pnl_at_300"]).to_csv("data/v2b_full_two_year_rr.csv",index=False)
b.to_csv("data/v2b_full_two_year_trades.csv",index=False)
print("\nSaved: data/v2b_full_two_year_trades.csv\nSaved: data/v2b_full_two_year_rr.csv\nFrozen Option 2A files were NOT modified.")
