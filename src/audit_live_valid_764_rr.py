import pandas as pd, numpy as np

print("=== ORIGINAL 1,911: LIVE-VALID TRADES ONLY — RR SCORECARD ===")

A=pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv")
B=pd.read_csv("data/v27_option2a_trades.csv")
tr=pd.concat([A,B],ignore_index=True)
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True,errors="coerce")

audit=pd.read_csv("data/original_1911_live_vs_future_audit.csv")
audit["candidate_time"]=pd.to_datetime(audit["candidate_time"],utc=True,errors="coerce")
live_times=set(audit.loc[~audit["future_dependent"].astype(bool),"candidate_time"])

live=tr[tr["candidate_time"].isin(live_times)].copy()
print(f"Live-valid original trades matched: {len(live)} / 1911")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
one["t_utc"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
idx=pd.Series(one.index,index=one.t_utc).to_dict()

for rr in range(1,7):
    w=l=u=miss=0
    for _,x in live.iterrows():
        i=idx.get(x.candidate_time)
        if i is None or i+3>=len(one):
            miss+=1; continue
        j=i+3
        entry=float(x.entry); risk=float(x.risk)
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
        if out==1: w+=1
        elif out==-1: l+=1
        else: u+=1
    n=w+l
    wr=100*w/n if n else np.nan
    print(f"1:{rr} | {w}W/{l}L/{u}U | WR {wr:.2f}% | misses={miss}")

print()
print("This uses the ORIGINAL trade entry/risk and original V75 forward-scoring method,")
print("but includes ONLY the trades classified LIVE-VALID by the 1,911 audit.")
