import pandas as pd, numpy as np
from pathlib import Path

A="data/ICON_MASTER_1911_TRADE_LEVEL.csv"
B="data/v2b_full_two_year_trades.csv"
RISK=300
TZ="America/New_York"

def load(path,label):
 if not Path(path).exists(): raise FileNotFoundError(path)
 d=pd.read_csv(path)
 timecol=next((c for c in ["entry_time","candidate_time","candidate_time_et","time_ny"] if c in d.columns),None)
 if timecol is None: raise ValueError(label+" has no recognized time column. Columns: "+str(list(d.columns)))
 t=pd.to_datetime(d[timecol],utc=True,errors="coerce")
 d["date_et"]=t.dt.tz_convert(TZ).dt.date
 return d

def rrcol(d,r):
 candidates=[f"{r}R",f"{r}r",f"rr_{r}",f"RR_{r}",f"outcome_{r}r",f"outcome_{r}R",f"{r}R_outcome",f"rr{r}_outcome"]
 for c in candidates:
  if c in d.columns:return c
 # fallback: find a column containing both rr number and outcome-ish text
 for c in d.columns:
  s=c.lower().replace("_","")
  if str(r) in s and ("outcome" in s or s in [f"{r}r",f"rr{r}"]): return c
 raise ValueError(f"Cannot find {r}R outcome column. Columns: {list(d.columns)}")

a=load(A,"2A"); b=load(B,"2B")
print("2A:",len(a),"trades |",min(a.date_et),"->",max(a.date_et))
print("2B:",len(b),"trades |",min(b.date_et),"->",max(b.date_et))

# Strict apples-to-apples common date span.
start=max(min(a.date_et),min(b.date_et)); end=min(max(a.date_et),max(b.date_et))
a=a[(a.date_et>=start)&(a.date_et<=end)].copy(); b=b[(b.date_et>=start)&(b.date_et<=end)].copy()
print("\nCOMMON TEST WINDOW:",start,"->",end)
print("2A trades:",len(a),"| 2B trades:",len(b))

def daily_table(d,r):
 c=rrcol(d,r)
 x=d[d[c].isin(["WIN","LOSS"])].copy()
 x["pnl"]=np.where(x[c]=="WIN",r*RISK,-RISK)
 return x.groupby("date_et").agg(trades=(c,"size"),wins=(c,lambda s:(s=="WIN").sum()),losses=(c,lambda s:(s=="LOSS").sum()),pnl=("pnl","sum"))

# Operational dates = union of dates on which either frozen strategy actually generated a trade.
# This avoids falsely counting weekends/holidays as no-trade days.
op_dates=sorted(set(a.date_et)|set(b.date_et))

def metrics(d,r):
 dt=daily_table(d,r).reindex(op_dates,fill_value=0)
 green=dt.pnl>=150
 zero=dt.trades==0
 one=dt.trades==1
 # longest run of operational dates without a qualifying green day
 cur=mx=0
 for g in green:
  cur=0 if g else cur+1; mx=max(mx,cur)
 # monthly green counts / simple five-green-day blocks (not a prop-rule claim)
 tmp=dt.copy(); tmp["month"]=pd.to_datetime(tmp.index).strftime("%Y-%m"); tmp["green"]=green.astype(int)
 monthly=tmp.groupby("month").green.sum()
 return {
  "trades":int(dt.trades.sum()),"avg_trades":dt.trades.mean(),"median_trades":dt.trades.median(),
  "zero_days":int(zero.sum()),"one_days":int(one.sum()),"green_days":int(green.sum()),
  "green_rate":100*green.mean(),"pnl":float(dt.pnl.sum()),"max_nonqual_gap":mx,
  "avg_green_month":monthly.mean(),"median_green_month":monthly.median(),
  "five_green_blocks":int((monthly//5).sum())
 }

print("\n=== OPERATIONAL COMPARISON ===")
print("Operational dates (union of A/B trade dates):",len(op_dates))
rows=[]
for r in [1,2]:
 for name,d in [("2A",a),("2B",b)]:
  m=metrics(d,r); rows.append([name,r,*m.values()])
cols=["Strategy","RR","Trades","Avg trades/op day","Median trades/op day","Zero-trade days","One-trade days","Qualifying green days","Qualifying green %","PnL @ $300","Longest non-qualifying gap","Avg green days/month","Median green days/month","5-green-day blocks"]
out=pd.DataFrame(rows,columns=cols)
print(out.round(2).to_string(index=False))

print("\n=== WIN RATE / PNL 1R-6R ===")
rows=[]
for name,d in [("2A",a),("2B",b)]:
 for r in range(1,7):
  c=rrcol(d,r); s=d[c]; w=int((s=="WIN").sum()); l=int((s=="LOSS").sum()); wr=100*w/(w+l); pnl=w*r*RISK-l*RISK
  rows.append([name,r,w,l,wr,pnl])
print(pd.DataFrame(rows,columns=["Strategy","RR","Wins","Losses","WR %","PnL @ $300"]).round(2).to_string(index=False))

print("\nNOTE: +$150 qualifying day is modeled as daily realized P&L >= $150 at fixed $300 risk.")
print("Zero-trade comparison uses the union of dates where either strategy traded, so weekends/holidays are not falsely counted.")
print("5-green-day blocks = floor(monthly qualifying green days / 5); it is an operational comparison, not a claim about any prop firm's exact payout rules.")
