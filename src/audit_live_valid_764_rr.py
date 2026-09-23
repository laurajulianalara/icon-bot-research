import pandas as pd, numpy as np

print("=== LIVE-VALID RR SCORECARD — FIXED 1,911 ROW MATCH ===")

A=pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv")
B=pd.read_csv("data/v27_option2a_trades.csv")
tr=pd.concat([A,B],ignore_index=True)
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True,errors="coerce")

audit=pd.read_csv("data/original_1911_live_vs_future_audit.csv")
audit["candidate_time"]=pd.to_datetime(audit["candidate_time"],utc=True,errors="coerce")
audit["future_dependent"]=audit["future_dependent"].astype(str).str.lower().map({"true":True,"false":False})

# Match by occurrence number as well as timestamp/direction so duplicate timestamps
# across the two benchmark periods cannot collapse into a set.
keys=["candidate_time"]
if "direction" in tr.columns and "direction" in audit.columns: keys.append("direction")
tr["_occ"]=tr.groupby(keys,dropna=False).cumcount()
audit["_occ"]=audit.groupby(keys,dropna=False).cumcount()
keys2=keys+["_occ"]

m=tr.merge(audit[keys2+["future_dependent"]],on=keys2,how="left",validate="one_to_one")
print("Original trades:",len(tr))
print("Audit rows:",len(audit))
print("Matched audit classifications:",m.future_dependent.notna().sum())
print("LIVE-VALID:",int((m.future_dependent==False).sum()))
print("FUTURE-DEPENDENT:",int((m.future_dependent==True).sum()))

live=m[m.future_dependent==False].copy()
one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
one["t_utc"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
idx=pd.Series(one.index,index=one.t_utc).to_dict()

print()
print("LIVE-VALID RR")
for rr in range(1,7):
    w=l=u=miss=0
    for _,x in live.iterrows():
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
    print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | misses={miss}" if n else f"1:{rr} no resolved trades")
