import pandas as pd, numpy as np

print("=== 588 FAILURE FORENSICS: TIMESTAMP ALIGNMENT VS REAL FUTURE LEAK ===")

a=pd.read_csv("data/final_end_to_end_causality_audit.csv")
a["candidate_time"]=pd.to_datetime(a["candidate_time"],utc=True,errors="coerce")
a["mapped_candidate_time"]=pd.to_datetime(a["mapped_candidate_time"],utc=True,errors="coerce")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

failed=a[~a["fully_causal_mechanics"].astype(bool)].copy()
print("Failed rows to explain:",len(failed))

rows=[]
for rid,x in failed.iterrows():
    ot=x.candidate_time; mt=x.mapped_candidate_time
    oi=idx.get(ot); mi=idx.get(mt)
    extreme=float(x.get("extreme",np.nan))
    if not np.isfinite(extreme):
        orig_stop=float(x.entry)-float(x.risk) if x.direction=="LONG" else float(x.entry)+float(x.risk)
        extreme=orig_stop+.25 if x.direction=="LONG" else orig_stop-.25

    orig_match=False; mapped_match=False
    if oi is not None:
        orig_match=abs(float(one.iloc[oi].low if x.direction=="LONG" else one.iloc[oi].high)-extreme)<=.2500001
    if mi is not None:
        mapped_match=abs(float(one.iloc[mi].low if x.direction=="LONG" else one.iloc[mi].high)-extreme)<=.2500001

    delta=(mt-ot).total_seconds()/60 if pd.notna(mt) and pd.notna(ot) else np.nan
    rows.append({"row_id":rid,"direction":x.direction,"original_time":ot,"mapped_time":mt,
                 "mapped_minus_original_min":delta,"extreme":extreme,
                 "extreme_on_original_bar":orig_match,"extreme_on_mapped_bar":mapped_match})

d=pd.DataFrame(rows)
print("\nTIME OFFSET COUNTS")
print(d["mapped_minus_original_min"].value_counts(dropna=False).sort_index().to_string())
print("\nEXTREME LOCATION")
print("Extreme matches ORIGINAL timestamp bar:",int(d.extreme_on_original_bar.sum()),"/",len(d))
print("Extreme matches MAPPED 1m bar:       ",int(d.extreme_on_mapped_bar.sum()),"/",len(d))
print("Matches either bar:                  ",int((d.extreme_on_original_bar|d.extreme_on_mapped_bar).sum()),"/",len(d))

# Search +/-6m around original timestamp for the actual minute containing the stored extreme.
found=[]
for _,x in d.iterrows():
    oi=idx.get(x.original_time); hits=[]
    if oi is not None:
        lo=max(0,oi-6); hi=min(len(one),oi+7)
        for k in range(lo,hi):
            px=float(one.iloc[k].low if x.direction=="LONG" else one.iloc[k].high)
            if abs(px-x.extreme)<=.2500001: hits.append(one.iloc[k].t)
    found.append(hits[0] if hits else pd.NaT)
d["actual_extreme_minute"]=found
d["actual_minus_original_min"]=(pd.to_datetime(d.actual_extreme_minute,utc=True)-d.original_time).dt.total_seconds()/60
print("\nACTUAL STORED EXTREME FOUND WITHIN +/-6M:",int(d.actual_extreme_minute.notna().sum()),"/",len(d))
print("ACTUAL EXTREME OFFSET COUNTS")
print(d["actual_minus_original_min"].value_counts(dropna=False).sort_index().to_string())

# Critical causal question: was the stored extreme already known by original signal time T+3?
known_by_entry=(d.actual_extreme_minute.notna()) & (pd.to_datetime(d.actual_extreme_minute,utc=True)<=d.original_time+pd.Timedelta(minutes=3))
print("\nSTORED EXTREME KNOWN BY ORIGINAL T+3 ENTRY:",int(known_by_entry.sum()),"/",len(d))
print("STORED EXTREME OCCURS AFTER ORIGINAL T+3 ENTRY:",int((d.actual_extreme_minute.notna() & ~known_by_entry).sum()),"/",len(d))
print("EXTREME NOT LOCATED IN +/-6M:",int(d.actual_extreme_minute.isna().sum()),"/",len(d))

d["extreme_known_by_Tplus3"]=known_by_entry
d.to_csv("data/failed_588_extreme_timing_forensics.csv",index=False)
print("\nSaved data/failed_588_extreme_timing_forensics.csv")
print("NEXT DECISION: if the extreme existed by T+3, the previous failure was timestamp-alignment, not future leakage; if it occurred after T+3, it is genuinely non-causal.")
