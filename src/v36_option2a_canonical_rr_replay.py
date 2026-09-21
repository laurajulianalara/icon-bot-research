import pandas as pd, numpy as np

ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
LOCKED="data/v27_option2a_trades.csv"
OUT="data/v36_option2a_exact_rr_1_to_6.csv"
RRS=[1,2,3,4,5,6]

one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); locked=pd.read_csv(LOCKED)
one["time_ny"]=pd.to_datetime(one["time_ny"]); cand["time_ny"]=pd.to_datetime(cand["time_ny"])
locked["candidate_time"]=pd.to_datetime(locked["candidate_time"])
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict()

# Reconstruct entries/stops EXACTLY as the canonical V7 engine that generated
# v7_base_trade_quality.parquet, from which Option 2A was selected:
# entry = open of i+3; stop = candidate extreme +/- 0.25; max 241 1m bars;
# ticker must remain same; stop checked before target.
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}

def replay(row,rr):
    key=(row.candidate_time,str(row.direction))
    c=cm.get(key)
    if c is None:return "MISSING"
    i=idx.get(c.time_ny)
    if i is None or i+3>=len(one):return "MISSING"
    j=i+3
    if one.iloc[j].ticker!=c.ticker:return "MISSING"
    signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:return "MISSING"
    entry=float(one.iloc[j].open)
    stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return "MISSING"
    target=entry+rr*risk if c.direction=="LONG" else entry-rr*risk
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker:break
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return "LOSS"
        if th:return "WIN"
    return "UNRESOLVED"

rows=[]
for rr in RRS:
    oc=locked.apply(lambda r:replay(r,rr),axis=1)
    wins=int((oc=="WIN").sum()); losses=int((oc=="LOSS").sum())
    unr=int((oc=="UNRESOLVED").sum()); miss=int((oc=="MISSING").sum())
    resolved=wins+losses
    wr=100*wins/resolved if resolved else np.nan
    exp=(wins*rr-losses)/resolved if resolved else np.nan
    rows.append([rr,len(locked),wins,losses,unr,miss,wr,exp])
out=pd.DataFrame(rows,columns=["rr","trades","wins","losses","unresolved","missing","wr_pct","expectancy_r"])
print("=== OPTION 2A — CANONICAL ENGINE RR 1:1 TO 1:6 ===")
print(out.round(2).to_string(index=False))
r4=out[out.rr==4].iloc[0]
parity=(int(r4.wins)==int((locked.outcome=="WIN").sum()) and int(r4.losses)==int((locked.outcome=="LOSS").sum()) and int(r4.unresolved)==0 and int(r4.missing)==0)
print("\n4R PARITY CHECK")
print(f"Canonical replay: {int(r4.wins)}W / {int(r4.losses)}L = {r4.wr_pct:.2f}%")
print(f"Locked Option 2A: {(locked.outcome=='WIN').sum()}W / {(locked.outcome=='LOSS').sum()}L = {100*(locked.outcome=='WIN').mean():.2f}%")
print("EXACT PARITY:",parity)
if not parity:
    raise RuntimeError("4R parity failed — do not use RR table.")
out.to_csv(OUT,index=False)
print("\nSaved:",OUT)
