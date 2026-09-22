import pandas as pd, numpy as np
ONE="data/mnq_2024_09_22_to_2025_09_16_continuous_1m.parquet"
CAND="data/reversal_candidates_2024_09_22_to_2025_09_16.parquet"
TRADES="data/v56_icon_bot_funded_prior_year_trades.csv"
OUT="data/v57_prior_year_monthly_rr_1_to_6.csv"
RRS=range(1,7); RISK=300
one=pd.read_parquet(ONE);cand=pd.read_parquet(CAND);z=pd.read_csv(TRADES)
one["time_ny"]=pd.to_datetime(one.time_ny);cand["time_ny"]=pd.to_datetime(cand.time_ny);z["candidate_time"]=pd.to_datetime(z.candidate_time)
one=one.sort_values("time_ny").reset_index(drop=True);cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict();cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
def replay(row,rr):
 c=cm.get((row.candidate_time,str(row.direction)));i=idx.get(c.time_ny) if c is not None else None
 if i is None or i+3>=len(one):return None
 j=i+3
 if one.iloc[j].ticker!=c.ticker:return None
 if pd.notna(c.next_same_extreme_time) and one.iloc[j].time_ny>=c.next_same_extreme_time:return None
 entry=float(one.iloc[j].open);stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
 risk=entry-stop if c.direction=="LONG" else stop-entry
 if risk<=0:return None
 target=entry+rr*risk if c.direction=="LONG" else entry-rr*risk
 for k in range(j,min(j+241,len(one))):
  b=one.iloc[k]
  if b.ticker!=c.ticker:break
  sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
  th=b.high>=target if c.direction=="LONG" else b.low<=target
  if sh:return 0
  if th:return 1
 return None
z["month"]=z.candidate_time.dt.tz_convert("America/New_York").dt.strftime("%Y-%m")
rows=[]
for month,g in z.groupby("month"):
 row={"month":month,"trades":len(g)}
 for rr in RRS:
  oc=g.apply(lambda x:replay(x,rr),axis=1).dropna();w=int(oc.sum());l=len(oc)-w
  row[str(rr)+"R_wr"]=100*w/len(oc);row[str(rr)+"R_pnl"]=RISK*(w*rr-l)
 rows.append(row)
out=pd.DataFrame(rows);out.to_csv(OUT,index=False)
print("=== ICON BOT FUNDED — 2024-2025 MONTHLY RR / WR / P&L ($300 RISK) ===")
print(out.round(2).to_string(index=False))
print("\nTOTAL")
for rr in RRS:
 oc=z.apply(lambda x:replay(x,rr),axis=1).dropna();w=int(oc.sum());l=len(oc)-w
 print("1:%d | %dW/%dL | WR %.2f%% | P&L $%s" % (rr,w,l,100*w/len(oc),format(RISK*(w*rr-l),",")))
print("\nSaved:",OUT)
