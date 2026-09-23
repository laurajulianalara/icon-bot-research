import pandas as pd, numpy as np

print("=== ORIGINAL 1,911 EXACT LIVE VS FUTURE + RR AUDIT ===")

files=["data/v56_icon_bot_funded_prior_year_trades.csv","data/v27_option2a_trades.csv"]
tr=pd.concat([pd.read_csv(f).assign(_source=f) for f in files],ignore_index=True)
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True,errors="coerce")

cand=pd.read_parquet("data/v101_1m_candidate_reference_map.parquet").copy()
cand["candidate_time"]=pd.to_datetime(cand["candidate_time"],utc=True,errors="coerce")

# IMPORTANT: V101 reference mapping was within +/-6m, so its is_reference rows are NOT
# exact benchmark timestamps. For each original trade, independently map to the nearest
# same-direction native 1m session extreme within +/-6m, exactly as V101 did.
mapped=[]
for rid,x in tr.iterrows():
    q=cand[(cand.candidate_time>=x.candidate_time-pd.Timedelta(minutes=6)) &
           (cand.candidate_time<=x.candidate_time+pd.Timedelta(minutes=6))]
    if "direction" in tr.columns:
        q=q[q.direction.astype(str).str.upper()==str(x.direction).upper()]
    if q.empty:
        mapped.append(None)
    else:
        j=(q.candidate_time-x.candidate_time).abs().idxmin()
        mapped.append(j)

if any(j is None for j in mapped):
    print("UNMAPPED original trades:",sum(j is None for j in mapped))
    raise SystemExit("Stop: all 1,911 must map before classification.")

# Classify each ORIGINAL trade from its independently mapped native candidate.
# A trade is future-dependent if a newer same-direction session extreme occurs after
# its mapped candidate but within the next 3 minutes. This matches the focused audit definition.
cand["_day"]=cand.candidate_time.dt.tz_convert("America/New_York").dt.date
lookup={}
for key,g in cand.sort_values("candidate_time").groupby(["_day","direction"],dropna=False):
    lookup[key]=list(g.candidate_time.dropna())

flags=[]; mapped_times=[]
for rid,j in enumerate(mapped):
    r=cand.loc[j]; t=r.candidate_time; mapped_times.append(t)
    key=(r["_day"],r["direction"])
    future=[z for z in lookup.get(key,[]) if z>t and z<=t+pd.Timedelta(minutes=3)]
    flags.append(bool(future))

tr["mapped_1m_candidate_time"]=mapped_times
tr["future_dependent"]=flags
live=tr[~tr.future_dependent].copy(); future=tr[tr.future_dependent].copy()
print(f"Original trades classified: {len(tr)} / 1911")
print(f"LIVE-VALID:       {len(live)} / 1911 = {100*len(live)/1911:.2f}%")
print(f"FUTURE-DEPENDENT: {len(future)} / 1911 = {100*len(future)/1911:.2f}%")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
one["t_utc"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
idx=pd.Series(one.index,index=one.t_utc).to_dict()

def score(df,label):
    print("\n"+label)
    for rr in range(1,7):
        w=l=u=miss=0
        for _,x in df.iterrows():
            i=idx.get(x.candidate_time)
            if i is None or i+3>=len(one): miss+=1; continue
            j=i+3; entry=float(x.entry); risk=float(x.risk)
            if not np.isfinite(risk) or risk<=0: continue
            stop=entry-risk if x.direction=="LONG" else entry+risk
            target=entry+rr*risk if x.direction=="LONG" else entry-rr*risk
            out=0
            for _,b in one.iloc[j:min(j+241,len(one))].iterrows():
                if x.direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low<=target: out=1; break
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | misses={miss}" if n else f"1:{rr} no resolved")
score(live,"LIVE-VALID RR")
score(future,"FUTURE-DEPENDENT RR")
tr.to_csv("data/original_1911_exact_live_future_rr_audit.csv",index=False)
print("\nSaved data/original_1911_exact_live_future_rr_audit.csv")
