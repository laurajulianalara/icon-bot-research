import pandas as pd, numpy as np

print("=== V90 SESSION-EXTREME STRUCTURE BRAIN ===")
d=pd.read_parquet("data/v88_full_rich_causal_features.parquet").copy()
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()

def pick(df,names):
    return next(c for c in names if c in df.columns)
dt=pick(d,["candidate_time","t_utc","time","candidate_time_et"])
mt=pick(m,["time_ny","time","timestamp","datetime"])
d["_t"]=pd.to_datetime(d[dt],utc=True,errors="coerce")
m["_t"]=pd.to_datetime(m[mt],errors="coerce")
if m["_t"].dt.tz is None:
    m["_t"]=m["_t"].dt.tz_localize("America/New_York",ambiguous="infer",nonexistent="shift_forward").dt.tz_convert("UTC")
else: m["_t"]=m["_t"].dt.tz_convert("UTC")
m=m.sort_values("_t").set_index("_t")

# Session starts in NY local time.
starts={"ASIA":(20,0),"LONDON":(2,0),"NYAM":(9,30),"NYPM":(13,30)}
rows=[]
for idx,r in d.iterrows():
    t=r["_t"]; direction=str(r.get("direction","")).upper(); s=str(r.get("session","")).upper()
    if pd.isna(t) or direction not in ("LONG","SHORT") or s not in starts: continue
    ny=t.tz_convert("America/New_York"); hh,mm=starts[s]
    st=ny.normalize()+pd.Timedelta(hours=hh,minutes=mm)
    if s=="ASIA" and ny.hour<12: st-=pd.Timedelta(days=1)
    st=st.tz_convert("UTC")
    cutoff=t+pd.Timedelta(minutes=2)
    w=m.loc[st:cutoff]
    pre=m.loc[st:t-pd.Timedelta(minutes=1)]
    post=m.loc[t:cutoff]
    if len(w)<3 or len(post)<3: continue
    atr=float(r.get("early_reclaim_atr",np.nan))
    # use price ATR reconstructed from prior 20 bars
    hist=m.loc[:cutoff].tail(25)
    pc=hist.close.shift()
    tr=pd.concat([(hist.high-hist.low),(hist.high-pc).abs(),(hist.low-pc).abs()],axis=1).max(axis=1)
    A=float(tr.tail(20).mean())
    if not np.isfinite(A) or A<=0: continue
    ext=float(r.get("extreme", post.low.min() if direction=="LONG" else post.high.max()))
    sign=1 if direction=="LONG" else -1
    # rejection away from extreme known through T+2
    reject=sign*(float(post.close.iloc[-1])-ext)/A
    best_away=(float(post.high.max())-ext)/A if direction=="LONG" else (ext-float(post.low.min()))/A
    continued=(max(0,ext-float(post.low.min()))/A if direction=="LONG" else max(0,float(post.high.max())-ext)/A)
    closes_away=int((post.close>post.open).sum()) if direction=="LONG" else int((post.close<post.open).sum())
    # session progress / repeated extremes before this candidate
    if len(pre):
        sess_range=(float(pre.high.max())-float(pre.low.min()))/A
        open_dist=sign*(ext-float(w.open.iloc[0]))/A
    else: sess_range=0; open_dist=0
    # prior same-direction candidate count and spacing, using only candidates at/before t
    prior=d.iloc[:idx+1]
    prior=prior[(prior["session"].astype(str).str.upper()==s)&(prior["direction"].astype(str).str.upper()==direction)&(prior["_t"]<=t)]
    count=len(prior)
    spacing=(t-prior["_t"].iloc[-2]).total_seconds()/60 if count>1 else np.nan
    # close reclaim of candidate 1m range and micro CISD: break opposite-side prior 2-bar body/close reference
    before=m.loc[:t-pd.Timedelta(minutes=1)].tail(5)
    if len(before)>=2:
        ref=float(before.close.tail(2).max()) if direction=="LONG" else float(before.close.tail(2).min())
        cisd_break=sign*(float(post.close.iloc[-1])-ref)/A
        cisd_confirm=int(cisd_break>0)
    else: cisd_break=np.nan; cisd_confirm=0
    rows.append({"_row":idx,"reject_2m_atr":reject,"best_reject_2m_atr":best_away,
      "continuation_2m_atr":continued,"reversal_closes_3":closes_away,
      "session_range_before_atr":sess_range,"extreme_from_session_open_atr":open_dist,
      "prior_same_extremes":count,"minutes_since_prior_extreme":spacing,
      "micro_cisd_break_atr":cisd_break,"micro_cisd_confirm":cisd_confirm,
      "finished_pressure":reject-continued})

f=pd.DataFrame(rows).set_index("_row")
for c in f.columns: d[c]=f[c]
out="data/v90_session_extreme_structure_features.parquet"
d.to_parquet(out,index=False)
print("Rows:",len(d),"rebuilt:",len(f),"new features:",len(f.columns))
print(f.describe().T[["count","mean","std","50%"]].to_string())
print("\nSaved:",out)
print("NEXT: V91 retrains WAIT/ENTER with these session-extreme-specific features and compares against 73.39%.")
