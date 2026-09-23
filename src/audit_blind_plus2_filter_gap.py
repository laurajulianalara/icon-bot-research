import pandas as pd, numpy as np

print("=== BLIND +2 FILTER GAP AUDIT: 1,911 VS ALL OTHER EXTREMES ===")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
ny=one.t.dt.tz_convert("America/New_York")
one["date"]=ny.dt.date
one["mins"]=ny.dt.hour*60+ny.dt.minute
def sess(m):
    if m>=1200:return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None
one["session"]=[sess(m) for m in one.mins]

# Build blind candidates exactly as full-stream +2 test.
c=[]
for (d,s),g in one.dropna(subset=["session"]).groupby(["date","session"],sort=False):
    hi=-np.inf;lo=np.inf
    for i in g.index:
        h=float(one.at[i,"high"]);l=float(one.at[i,"low"])
        if h>hi:c.append((i,"SHORT"));hi=h
        if l<lo:c.append((i,"LONG"));lo=l

# Reference native-1m candidate anchors from the audited 1,911.
a=pd.read_csv("data/original_1911_exact_live_future_rr_audit.csv")
a["mapped_1m_candidate_time"]=pd.to_datetime(a["mapped_1m_candidate_time"],utc=True,errors="coerce")
ref=set(zip(a["mapped_1m_candidate_time"],a["direction"].astype(str).str.upper()))

rows=[]
for i,d in c:
    if i+2>=len(one):continue
    ts=[one.at[i+k,"t"] for k in range(3)]
    if any((ts[k]-ts[k-1])!=pd.Timedelta(minutes=1) for k in range(1,3)):continue
    if any(one.at[i+k,"session"]!=one.at[i,"session"] for k in range(3)):continue
    w=one.iloc[i:i+3]
    ext=float(w.high.max() if d=="SHORT" else w.low.min())
    rng=np.maximum(w.high-w.low,.25)
    # all observable by close of T+2
    if d=="SHORT":
        rev=(w.high-w.close)/rng
        move=(w.close.iloc[-1]-w.open.iloc[0])
    else:
        rev=(w.close-w.low)/rng
        move=(w.open.iloc[0]-w.close.iloc[-1])
    rows.append({
        "t":one.at[i,"t"],"direction":d,
        "is_ref":(one.at[i,"t"],d) in ref,
        "rev0":float(rev.iloc[0]),"rev1":float(rev.iloc[1]),"rev2":float(rev.iloc[2]),
        "range0":float(rng.iloc[0]),"range1":float(rng.iloc[1]),"range2":float(rng.iloc[2]),
        "net_reversal_move":float(move),
        "extreme_shift":abs(ext-(float(one.at[i,"high"]) if d=="SHORT" else float(one.at[i,"low"])))
    })
d=pd.DataFrame(rows)
print("Rows:",len(d),"Reference anchors:",int(d.is_ref.sum()),"Other:",int((~d.is_ref).sum()))
print("Reference prevalence:",f"{100*d.is_ref.mean():.2f}%")
print("\nMedian +2-observable differences:")
for col in ["rev0","rev1","rev2","range0","range1","range2","net_reversal_move","extreme_shift"]:
    r=d.loc[d.is_ref,col];o=d.loc[~d.is_ref,col]
    print(f"{col}: REF={r.median():.4f} OTHER={o.median():.4f}")

d.to_parquet("data/blind_plus2_filter_gap_audit.parquet",index=False)
print("\nSaved data/blind_plus2_filter_gap_audit.parquet")
print("NEXT: use this population plus the existing causal structure/liquidity features to build a chronological selector; do not train on future RR outcomes.")
