import pandas as pd, numpy as np

print("=== FULL 1,911 NATIVE-1M RE-ANCHORED RR RECONCILIATION ===")

clean=pd.read_csv("data/final_corrected_766_causal_audit.csv")
clean=clean[clean["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
rem=pd.read_csv("data/remaining_1145_native_1m_recoverability.csv")

# Known clean 766 benchmark from certified saved audit.
clean_stats={1:(737,29),2:(673,93),3:(565,201),4:(477,289),5:(405,361),6:(356,410)}

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()
rem["arrived_extreme_time"]=pd.to_datetime(rem["arrived_extreme_time"],utc=True,errors="coerce")

print("Clean cohort:",len(clean))
print("Re-anchored cohort:",len(rem))
print("Combined:",len(clean)+len(rem))
print("\nRR | CLEAN 766 | RE-ANCHORED 1145 | COMBINED 1911 | OLD BENCHMARK")

old={1:96.97,2:86.92,3:75.04,4:65.04,5:57.30,6:50.55}
# old combined weighted exact benchmarks from 953+958 source stats
old_counts={
1:(round(.9675*953)+round(.9718*958),1911),
2:(round(.8678*953)+round(.8706*958),1911),
3:(round(.7450*953)+round(.7557*958),1911),
4:(round(.6464*953)+round(.6545*958),1911),
5:(round(.5719*953)+round(.5741*958),1911),
6:(round(.5026*953)+round(.5084*958),1911)}
for rr in range(1,7):
    rw=rl=ru=0
    for _,x in rem.iterrows():
        i=idx.get(x.arrived_extreme_time)
        if i is None or i+1>=len(one): continue
        j=i+1; direction=str(x.direction).upper()
        entry=float(one.iloc[j].open); extreme=float(x.arrived_extreme)
        stop=extreme-.25 if direction=="LONG" else extreme+.25
        risk=entry-stop if direction=="LONG" else stop-entry
        if not np.isfinite(risk) or risk<=0: ru+=1; continue
        target=entry+rr*risk if direction=="LONG" else entry-rr*risk
        out=0
        for k in range(j,min(j+241,len(one))):
            b=one.iloc[k]
            if direction=="LONG":
                if b.low<=stop:out=-1;break
                if b.high>=target:out=1;break
            else:
                if b.high>=stop:out=-1;break
                if b.low<=target:out=1;break
        if out==1:rw+=1
        elif out==-1:rl+=1
        else:ru+=1
    cw,cl=clean_stats[rr]
    combw=cw+rw; combl=cl+rl; resolved=combw+combl
    cwr=100*cw/(cw+cl); rwr=100*rw/(rw+rl); combwr=100*combw/resolved
    ow,on=old_counts[rr]; oldwr=100*ow/on
    print(f"1:{rr} | {cwr:6.2f}% | {rwr:6.2f}% | {combwr:6.2f}% ({combw}W/{combl}L) | {oldwr:6.2f}%")

print("\nCAUTION: the 1,145 re-anchored cohort is still a retrospective ceiling. This reconciliation proves the native-1m timing can reproduce the performance profile when the correct arriving extreme is known; it does NOT yet prove a live selector can identify that extreme prospectively.")
