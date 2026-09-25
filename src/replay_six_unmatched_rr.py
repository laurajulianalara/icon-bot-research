#!/usr/bin/env python3
from pathlib import Path
import pandas as pd, numpy as np
TZ="America/New_York"; TARGET=Path("data/reports/2026-09_six_exact_canonical_trace.csv"); ONE=Path("data/mnq_continuous_1m.parquet")
def et(s):
 x=pd.to_datetime(s); return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
t=pd.read_csv(TARGET); t["entry_time"]=et(t.entry_time_from_causal)
one=pd.read_parquet(ONE); one["time_ny"]=pd.to_datetime(one.time_ny)
one["time_ny"]=one.time_ny.dt.tz_localize(TZ) if one.time_ny.dt.tz is None else one.time_ny.dt.tz_convert(TZ)
one=one.sort_values("time_ny").reset_index(drop=True); idx=pd.Series(one.index,index=one.time_ny).to_dict()
rows=[]
for _,r in t.iterrows():
 j=idx[r.entry_time]; entry=float(one.iloc[j].open); risk=float(r.risk); stop=entry-risk if r.direction=="LONG" else entry+risk; ticker=one.iloc[j].ticker
 out={"entry_time":r.entry_time,"session":r.session,"direction":r.direction,"entry":entry,"stop":stop,"risk_points":risk}
 for rr in range(1,7):
  target=entry+rr*risk if r.direction=="LONG" else entry-rr*risk; result="UNRESOLVED"
  for k in range(j,min(j+241,len(one))):
   b=one.iloc[k]
   if b.ticker!=ticker: break
   sh=b.low<=stop if r.direction=="LONG" else b.high>=stop; th=b.high>=target if r.direction=="LONG" else b.low<=target
   if sh: result="LOSS"; break
   if th: result="WIN"; break
  out[str(rr)+"R"]=result
 rows.append(out)
o=pd.DataFrame(rows)
print("="*105); print("THE ICON — 6 UNMATCHED VALID TRADES: 1R THROUGH 6R"); print("="*105); print(o.to_string(index=False)); print("\nSUMMARY")
for rr in range(1,7):
 s=o[str(rr)+"R"]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum()); u=int((s=="UNRESOLVED").sum()); wr=100*w/(w+l) if w+l else np.nan; pnl=w*rr*300-l*300
 print(str(rr)+"R | "+str(w)+"W / "+str(l)+"L / "+str(u)+"U | WR "+format(wr,".2f")+"% | PnL @ $300: $"+format(pnl,",.0f"))
save=Path("data/reports/2026-09_six_unmatched_rr.csv"); o.to_csv(save,index=False); print("\nSaved:",save); print("READ ONLY — no strategy/data files changed.")
