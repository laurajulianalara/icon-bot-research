import pandas as pd
tr=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)
bars["time_utc"]=pd.to_datetime(bars["time_utc"],utc=True)
bars=bars.sort_values("time_utc").set_index("time_utc")

# Exact same 958 locked Option 2A entries. Replay each RR independently.
rows=[]
for rr in [1,2,3,4,5,6]:
 wins=losses=unresolved=0
 by_session={}
 for _,r in tr.iterrows():
  t=r.candidate_time; entry=float(r.entry); risk=float(r.risk); is_long=str(r.direction).upper()=="LONG"
  stop=entry-risk if is_long else entry+risk
  target=entry+rr*risk if is_long else entry-rr*risk
  w=bars.loc[t:t+pd.Timedelta(hours=4)]
  result="UNRESOLVED"
  for _,b in w.iterrows():
   stop_hit=(b.low<=stop) if is_long else (b.high>=stop)
   target_hit=(b.high>=target) if is_long else (b.low<=target)
   # Conservative: if both occur in same 1m bar, count STOP first.
   if stop_hit: result="LOSS"; break
   if target_hit: result="WIN"; break
  if result=="WIN": wins+=1
  elif result=="LOSS": losses+=1
  else: unresolved+=1
  by_session.setdefault(r.session,[0,0,0])
  by_session[r.session][{"WIN":0,"LOSS":1,"UNRESOLVED":2}[result]]+=1
 resolved=wins+losses
 wr=100*wins/resolved if resolved else 0
 all_wr=100*wins/len(tr)
 exp=(wins*rr-losses)/resolved if resolved else 0
 rows.append([rr,len(tr),wins,losses,unresolved,wr,all_wr,exp])
out=pd.DataFrame(rows,columns=["rr","trades","wins","losses","unresolved","wr_resolved_pct","wins_all_entries_pct","expectancy_r_resolved"])
print("=== OPTION 2A — EXACT RR REPLAY (SAME 958 ENTRIES) ===")
print("Rules: original 1R stop | 4h horizon | conservative stop-first same 1m bar")
print(out.round(2).to_string(index=False))
print("\nPARITY CHECK FOR 4R:")
r4=out[out.rr==4].iloc[0]
print(f"Replay 4R wins={int(r4.wins)} losses={int(r4.losses)} unresolved={int(r4.unresolved)}")
print("Locked Option 2A: wins=627 losses=331 WR=65.45%")
print("Exact parity:", int(r4.wins)==627 and int(r4.losses)==331 and int(r4.unresolved)==0)
out.to_csv("data/v35_option2a_rr_1_to_6.csv",index=False)
