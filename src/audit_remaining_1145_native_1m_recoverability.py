import pandas as pd, numpy as np

print("=== REMAINING 1,145 — NATIVE 1M RECOVERABILITY AUDIT ===")
a=pd.read_csv("data/original_1911_exact_live_future_rr_audit.csv")
# discover classification column robustly
cc=next(c for c in a.columns if "class" in c.lower() or "future" in c.lower() and a[c].dtype=="object")
print("Classification column:",cc)
print(a[cc].value_counts(dropna=False).to_string())

bad=a[a[cc].astype(str).str.upper().str.contains("FUTURE")].copy()
print("\nFuture-dependent reference rows:",len(bad))

# Parse likely time/direction fields
ot=next(c for c in ["candidate_time","original_candidate_time","time"] if c in bad.columns)
mt=next((c for c in ["mapped_candidate_time","mapped_time"] if c in bad.columns),None)
dc=next(c for c in ["direction","side","dir"] if c in bad.columns)
bad[ot]=pd.to_datetime(bad[ot],utc=True,errors="coerce")
if mt: bad[mt]=pd.to_datetime(bad[mt],utc=True,errors="coerce")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

rows=[]
for _,r in bad.iterrows():
    T=r[ot]; i=idx.get(T)
    if i is None: continue
    direction=str(r[dc]).upper()
    # Original old decision/entry boundary is T+3 open.
    entry_i=i+3
    if entry_i>=len(one): continue
    # Find latest same-direction new session extreme from T through T+3 using only arrived 1m bars.
    ny=one.t.dt.tz_convert("America/New_York")
    tny=ny.iloc[i]; mins=tny.hour*60+tny.minute
    if mins>=1200 or mins<1: lo,hi=1200,1440
    elif 120<=mins<300: lo,hi=120,300
    elif 570<=mins<750: lo,hi=570,750
    elif 810<=mins<1020: lo,hi=810,1020
    else: continue
    day=tny.date()
    # session start index for running extreme
    k=i
    while k>0:
        pny=ny.iloc[k-1]; pm=pny.hour*60+pny.minute
        same_day=pny.date()==day or (lo==1200 and (pny.date()==day))
        in_s=(pm>=lo and pm<hi) if lo!=1200 else (pm>=1200 or pm<1)
        if not in_s: break
        k-=1
    latest=None
    run=-np.inf if direction=="SHORT" else np.inf
    for z in range(k,min(entry_i+1,len(one))):
        val=float(one.iloc[z].high if direction=="SHORT" else one.iloc[z].low)
        isnew=val>run if direction=="SHORT" else val<run
        if isnew:
            run=val
            if z>=i: latest=z
    if latest is None: latest=i
    off=latest-i
    rows.append({"original_time":T,"direction":direction,"latest_extreme_offset_min":off,
                 "latest_extreme_time":one.iloc[latest].t,
                 "known_by_Tplus3":latest<=entry_i,
                 "can_enter_next_open":latest+1<len(one),
                 "next_open_offset":latest+1-i})
out=pd.DataFrame(rows)
print("\nMapped to native 1m:",len(out),"/",len(bad))
if len(out):
    print("\nLATEST ARRIVED EXTREME OFFSET FROM ORIGINAL T")
    print(out.latest_extreme_offset_min.value_counts().sort_index().to_string())
    print("\nKnown by original T+3 boundary:",int(out.known_by_Tplus3.sum()),"/",len(out))
    print("Potentially re-anchorable to latest arrived 1m extreme:",int(out.can_enter_next_open.sum()),"/",len(out))
    print("\nNEXT-OPEN OFFSET AFTER LATEST ARRIVED EXTREME")
    print(out.next_open_offset.value_counts().sort_index().to_string())
out.to_csv("data/remaining_1145_native_1m_recoverability.csv",index=False)
print("\nSaved data/remaining_1145_native_1m_recoverability.csv")
print("This is a timing/recoverability audit only. It does NOT call these trades causal or profitable yet.")
