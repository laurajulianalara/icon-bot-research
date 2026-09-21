import pandas as pd
import numpy as np

ONE="data/mnq_continuous_1m.parquet"; CAND="data/reversal_candidates.parquet"
OUT="data/v6_developing_3m_entry_scan.csv"; RR=4.0
one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND)
one["time_ny"]=pd.to_datetime(one.time_ny);cand["time_ny"]=pd.to_datetime(cand.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True);cand=cand.sort_values("time_ny").reset_index(drop=True)
end=one.time_ny.max();start=end-pd.Timedelta(days=365);split=start+(end-start)*.70
one=one[one.time_ny>=start].reset_index(drop=True);cand=cand[cand.time_ny>=start].reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict(); oi=one.set_index("time_ny")

def test(c,minute):
    i=idx.get(c.time_ny)
    if i is None:return None
    nxt=c.next_same_extreme_time; ref=c.open
    # Recreate the developing 3m candle using ONLY 1m bars available at that moment.
    for j in range(i+1,min(i+16,len(one))):
        r=one.iloc[j]
        if r.ticker!=c.ticker:return None
        if pd.notna(nxt) and r.time_ny>=nxt:return None
        if c.direction=="LONG" and r.close<r.open:ref=r.open
        elif c.direction=="SHORT" and r.close>r.open:ref=r.open
        # minute=1 means first closed 1m sub-bar; 2 means second; 3 means completed 3m.
        elapsed=j-i
        if elapsed<minute:continue
        ok=(c.direction=="LONG" and r.close>ref) or (c.direction=="SHORT" and r.close<ref)
        if not ok:continue
        a=float(r.atr1)
        if not np.isfinite(a) or a<=0:return None
        cp=(r.close-r.low)/(r.high-r.low) if r.high>r.low else .5
        if c.direction=="SHORT":cp=1-cp
        disp=abs(r.close-r.open)/a
        signal=r.time_ny+pd.Timedelta(minutes=1)
        z=oi.loc[signal:signal];z=z[z.ticker==c.ticker]
        if z.empty:return None
        entry=float(z.iloc[0].open);stop=c.extreme-.25 if c.direction=="LONG" else c.extreme+.25
        risk=entry-stop if c.direction=="LONG" else stop-entry
        if risk<=0:return None
        target=entry+RR*risk if c.direction=="LONG" else entry-RR*risk
        td=oi.loc[signal:signal+pd.Timedelta(hours=4)];td=td[td.ticker==c.ticker]
        for ts,b in td.iterrows():
            sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
            th=b.high>=target if c.direction=="LONG" else b.low<=target
            if sh:return signal,ts,"LOSS",cp,disp,elapsed
            if th:return signal,ts,"WIN",cp,disp,elapsed
        return None
    return None

rows=[]
for n,(_,c) in enumerate(cand.iterrows(),1):
    if n%2000==0:print(f"Candidate {n:,}/{len(cand):,}",flush=True)
    for m in [1,2,3]:
        r=test(c,m)
        if r:
            fill,exit_,out,cp,disp,elapsed=r
            rows.append((c.time_ny,c.session,c.direction,m,fill,exit_,out,cp,disp,elapsed))
d=pd.DataFrame(rows,columns=["candidate_time","session","direction","earliest_subbar","fill_time","exit_time","outcome","cisd","disp","elapsed"])
d=d.drop_duplicates(["candidate_time","session","direction","earliest_subbar"])
print(f"Resolved developing-3m trades: {len(d):,}")

# Compare causal early-entry timing plus modest quality bands learned as broad sensitivity checks.
res=[]
for m in [1,2,3]:
 for sess in ["ALL","ASIA","LONDON","NYAM","NYPM"]:
  b=d[d.earliest_subbar==m] if sess=="ALL" else d[(d.earliest_subbar==m)&(d.session==sess)]
  for clo in [None,.5,.6,.7,.8,.9]:
   for chi in [None,.8,.9,.95]:
    if clo is not None and chi is not None and clo>=chi:continue
    for dlo in [None,.2,.4,.6]:
     for dhi in [None,.8,1.0,1.2,1.5]:
      if dlo is not None and dhi is not None and dlo>=dhi:continue
      q=b.copy()
      if clo is not None:q=q[q.cisd>=clo]
      if chi is not None:q=q[q.cisd<chi]
      if dlo is not None:q=q[q.disp>=dlo]
      if dhi is not None:q=q[q.disp<dhi]
      tr=q[q.fill_time<split];va=q[q.fill_time>=split]
      if len(tr)<40 or len(va)<15:continue
      tw=100*(tr.outcome=="WIN").mean();vw=100*(va.outcome=="WIN").mean()
      res.append((m,sess,clo,chi,dlo,dhi,len(tr),tw,len(va),vw,min(tw,vw)))
r=pd.DataFrame(res,columns=["subbar","session","cisd_min","cisd_max","disp_min","disp_max","train_trades","train_wr","valid_trades","valid_wr","robust_wr"])
r=r.sort_values(["robust_wr","valid_trades"],ascending=[False,False]);r.to_csv(OUT,index=False)
print("\n=== DEVELOPING 3M / EARLY CAUSAL ENTRY — TOP 40 ===")
print(r.head(40).round(2).to_string(index=False))
print("\n50%+ BOTH:",int(((r.train_wr>=50)&(r.valid_wr>=50)).sum()))
print("40%+ BOTH:",int(((r.train_wr>=40)&(r.valid_wr>=40)).sum()))
print("\n=== BEST BY ENTRY SUB-BAR ===")
print(r.groupby("subbar").head(1).round(2).to_string(index=False))
print("\nSaved:",OUT)
