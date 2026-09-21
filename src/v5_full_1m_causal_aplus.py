import pandas as pd
import numpy as np

DATA_1M="data/mnq_continuous_1m.parquet"
CANDIDATES="data/reversal_candidates.parquet"
OUT="data/v5_1m_causal_aplus.csv"

LOOKBACK_DAYS=365
MAX_CONFIRM_MINUTES=15
RR=4.0
STOP_BUFFERS=[0.25,0.50]

rules={
 "ASIA":dict(cisd=.95,disp=1.20,sweep=.20),
 "NYAM":dict(cisd=.95,disp=1.20,sweep=.20),
 "LONDON":dict(cisd=.96,disp=1.20,sweep=.20),
 "NYPM":dict(cisd=.97,disp=1.10,sweep=None),
}

one=pd.read_parquet(DATA_1M)
cand=pd.read_parquet(CANDIDATES)
for x in (one,cand): x["time_ny"]=pd.to_datetime(x["time_ny"])
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").reset_index(drop=True)

end=one.time_ny.max()
start=end-pd.Timedelta(days=LOOKBACK_DAYS)
one=one[one.time_ny>=start].copy().reset_index(drop=True)
cand=cand[cand.time_ny>=start].copy().reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False)["time_ny"].shift(-1)

one["atr"]=pd.concat([
    one.high-one.low,
    (one.high-one.close.shift()).abs(),
    (one.low-one.close.shift()).abs()
],axis=1).max(axis=1).rolling(20).mean()

idx=pd.Series(one.index,index=one.time_ny).to_dict()
one_idx=one.set_index("time_ny")

def confirm_1m(c):
    if c.time_ny not in idx:return None
    i=idx[c.time_ny]
    reference=c.open
    nxt=c.next_same_extreme_time
    for j in range(i+1,min(i+MAX_CONFIRM_MINUTES+1,len(one))):
        r=one.iloc[j]
        if r.ticker!=c.ticker:return None
        if pd.notna(nxt) and r.time_ny>=nxt:return None
        if c.direction=="LONG" and r.close<r.open: reference=r.open
        elif c.direction=="SHORT" and r.close>r.open: reference=r.open
        confirmed=(c.direction=="LONG" and r.close>reference) or (c.direction=="SHORT" and r.close<reference)
        if not confirmed:continue
        atr=float(r.atr) if pd.notna(r.atr) else np.nan
        if not np.isfinite(atr) or atr<=0:return None
        disp=abs(r.close-r.open)/atr
        cp=(r.close-r.low)/(r.high-r.low) if r.high>r.low else .5
        if c.direction=="SHORT":cp=1-cp
        # 1m bar stamped T is only known when the minute closes.
        signal_time=r.time_ny+pd.Timedelta(minutes=1)
        return dict(confirm_time=r.time_ny,signal_time=signal_time,cisd=cp,disp=disp)
    return None

def simulate(c,cf,sb):
    stop=c.extreme-sb if c.direction=="LONG" else c.extreme+sb
    z=one_idx.loc[cf["signal_time"]:cf["signal_time"]+pd.Timedelta(minutes=1)]
    z=z[z.ticker==c.ticker]
    if z.empty:return None
    ft=z.index[0]; entry=float(z.iloc[0].open)
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+risk*RR if c.direction=="LONG" else entry-risk*RR
    td=one_idx.loc[ft:ft+pd.Timedelta(hours=4)]
    td=td[td.ticker==c.ticker]
    if td.empty:return None
    outcome="TIMEOUT"; xt=td.index[-1]; mfe=mae=0.0
    for ts,b in td.iterrows():
        if c.direction=="LONG":
            fav=b.high-entry; adv=entry-b.low; sh=b.low<=stop; th=b.high>=target
        else:
            fav=entry-b.low; adv=b.high-entry; sh=b.high>=stop; th=b.low<=target
        mfe=max(mfe,fav); mae=max(mae,adv)
        if sh:outcome="LOSS";xt=ts;break
        if th:outcome="WIN";xt=ts;break
    return dict(fill_time=ft,exit_time=xt,outcome=outcome,result_r=RR if outcome=="WIN" else (-1 if outcome=="LOSS" else 0),mfe_r=mfe/risk,mae_r=mae/risk)

rows=[]
for n,(_,c) in enumerate(cand.iterrows(),1):
    if n%2000==0:print(f"Candidate {n:,}/{len(cand):,}")
    cf=confirm_1m(c)
    if cf is None:continue
    atr=float(c.atr) if pd.notna(c.atr) else np.nan
    sweep=(c.sweep_distance/atr) if np.isfinite(atr) and atr>0 else 0
    rule=rules.get(c.session)
    if rule is None:continue
    if cf["cisd"]<rule["cisd"] or cf["disp"]<rule["disp"]:continue
    if rule["sweep"] is not None and sweep<rule["sweep"]:continue
    for sb in STOP_BUFFERS:
        tr=simulate(c,cf,sb)
        if tr is None:continue
        rows.append({**tr,"candidate_time":c.time_ny,"session":c.session,"direction":c.direction,
                     "confirm_time":cf["confirm_time"],"signal_available_time":cf["signal_time"],
                     "confirm_close_pos":cf["cisd"],"disp_atr":cf["disp"],"sweep_atr":sweep,"stop_buffer":sb})

d=pd.DataFrame(rows)
if d.empty:raise RuntimeError("No 1-minute A+ trades produced.")
viol=(d.fill_time<d.signal_available_time).sum()
print(f"\nCausal timing violations: {viol}")
if viol:raise RuntimeError("Timing violation.")
raw=len(d)
d=d.drop_duplicates(["candidate_time","session","direction"],keep="first").sort_values("fill_time").copy()
print(f"Duplicate cache rows removed: {raw-len(d)}")

# One live trade at a time.
keep=[]; live_until=None
for ix,r in d.iterrows():
    if live_until is not None and r.fill_time<=live_until:continue
    keep.append(ix); live_until=r.exit_time
d=d.loc[keep].copy()
resolved=d[d.outcome.isin(["WIN","LOSS"])].copy()

def stats(x,label):
    if x.empty:return dict(period=label,trades=0,wins=0,losses=0,wr=np.nan,expectancy_r=np.nan,max_dd_r=np.nan)
    w=(x.outcome=="WIN").sum(); eq=x.result_r.cumsum()
    return dict(period=label,trades=len(x),wins=w,losses=len(x)-w,wr=100*w/len(x),
                expectancy_r=x.result_r.mean(),max_dd_r=abs((eq-eq.cummax()).min()))

out=[]
edges=np.linspace(0,len(resolved),6,dtype=int)
for i in range(5):out.append(stats(resolved.iloc[edges[i]:edges[i+1]],f"chronological_20pct_{i+1}"))
for s,g in resolved.groupby("session"):out.append(stats(g,f"session_{s}"))
out.append(stats(resolved,"ALL"))
report=pd.DataFrame(out)
report.to_csv(OUT,index=False)

print("\n=== V5 — FULL 1-MINUTE CAUSAL A+ — 4R ===")
print("Confirmation, CISD quality and displacement are all calculated from CLOSED 1-minute candles.")
print("\nChronological blocks:")
print(report[report.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSessions + combined:")
print(report[~report.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSaved:",OUT)
