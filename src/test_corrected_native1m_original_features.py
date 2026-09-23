import pandas as pd, numpy as np

print("=== NATIVE 1M — CORRECTED ORIGINAL FEATURE LOGIC ===")
ONE="data/mnq_continuous_1m.parquet"; CAND="data/reversal_candidates.parquet"; BASE="data/v7_base_trade_quality.parquet"
one=pd.read_parquet(ONE).copy(); cand=pd.read_parquet(CAND).copy(); base=pd.read_parquet(BASE).copy()
for d,c in [(one,"time_ny"),(cand,"time_ny"),(base,"candidate_time")]: d[c]=pd.to_datetime(d[c],utc=True)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
idx=pd.Series(one.index,index=one.time_ny).to_dict(); cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}

# Preserve the exact feature definitions from the original producer.
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
rows=[]
for _,c in cand.iterrows():
 i=idx.get(c.time_ny)
 if i is None or i<20 or i+2>=len(one):continue
 a=float(one.at[i,"atr1"])
 if not np.isfinite(a) or a<=0:continue
 sg=1 if c.direction=="LONG" else -1; vals={}
 for k in [1,2]:
  b=one.iloc[i+k];pre=one.iloc[max(0,i+k-5):i+k+1]
  vals[f"m{k}_move_atr"]=(float(b.close)-float(one.at[i,"close"]))/a*sg
  cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
  vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
  vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
 # IMPORTANT: original wick is the saved candidate wick, not a recalculation on an updated extreme.
 wick=float(c.wick_percent) if "wick_percent" in c and pd.notna(c.wick_percent) else np.nan
 first2=one.iloc[i+1:i+3]
 ext=float(c.extreme)
 reclaim=(float(first2.iloc[-1].close)-ext)/a if c.direction=="LONG" else (ext-float(first2.iloc[-1].close))/a
 baseok=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
 pre=baseok and reclaim<=.90 and vals["m2_close_pos"]<=.80 and wick<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4
 final=pre and (reclaim<.576132 or reclaim*wick<.183258)
 if final: rows.append((i,str(c.direction),ext,reclaim,wick))
print("Native 1m candidates:",len(cand),"| corrected filter passes:",len(rows))

# Verify alignment against authoritative 1,911 timestamps.
refs=pd.concat([pd.read_csv("data/v27_option2a_trades.csv"),pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv")],ignore_index=True)
refs["candidate_time"]=pd.to_datetime(refs.candidate_time,utc=True)
keys={(one.at[i,"t"] if "t" in one else one.at[i,"time_ny"],d) for i,d,*_ in rows}
hit=sum((r.candidate_time,str(r.direction)) in keys for _,r in refs.iterrows())
print("Original 1,911 recovered by corrected native-1m filter:",hit,"/ 1911",f"({100*hit/1911:.2f}%)")

# Live sequential replay: original candidate extreme, decision after +2 completed 1m candles, entry +3 open.
for rr in range(1,7):
 w=l=u=0;busy=-1;sig=0
 for i,d,ext,reclaim,wick in rows:
  j=i+3
  if j>=len(one) or j<=busy:continue
  entry=float(one.at[j,"open"]);stop=ext-.25 if d=="LONG" else ext+.25
  risk=entry-stop if d=="LONG" else stop-entry
  if risk<=0:continue
  target=entry+rr*risk if d=="LONG" else entry-rr*risk;sig+=1;out=0;end=j
  for k in range(j,min(j+241,len(one))):
   b=one.iloc[k];end=k
   if d=="LONG":
    if b.low<=stop:out=-1;break
    if b.high>=target:out=1;break
   else:
    if b.high>=stop:out=-1;break
    if b.low<=target:out=1;break
  busy=end
  if out==1:w+=1
  elif out==-1:l+=1
  else:u+=1
 print(f"1:{rr} | signals={sig} | WR={100*w/(w+l):.2f}% | {w}W/{l}L/{u}U")
