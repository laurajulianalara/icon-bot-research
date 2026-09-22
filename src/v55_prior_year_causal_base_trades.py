import pandas as pd
import numpy as np

ONE="data/mnq_2024_09_22_to_2025_09_16_continuous_1m.parquet"
THREE="data/mnq_2024_09_22_to_2025_09_16_continuous_3m.parquet"
CAND="data/reversal_candidates_2024_09_22_to_2025_09_16.parquet"
BASE_RULE="m1_move_atr<=0.300 & m1_close_pos>=0.140 & m2_close_pos<=0.912"
OUT="data/v55_prior_year_base_trade_quality.parquet"

one=pd.read_parquet(ONE); three=pd.read_parquet(THREE); cand=pd.read_parquet(CAND)
for x in (one,three,cand): x["time_ny"]=pd.to_datetime(x["time_ny"])
one=one.sort_values("time_ny").reset_index(drop=True); three=three.sort_values("time_ny").reset_index(drop=True); cand=cand.sort_values("time_ny").reset_index(drop=True)
end=one.time_ny.max(); start=one.time_ny.min()
one=one[one.time_ny>=start-pd.Timedelta(days=2)].reset_index(drop=True); three=three[three.time_ny>=start-pd.Timedelta(days=30)].reset_index(drop=True); cand=cand[cand.time_ny>=start].drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)

one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
three["atr3"]=pd.concat([three.high-three.low,(three.high-three.close.shift()).abs(),(three.low-three.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
three["pivot_hi"]=np.where((three.high.shift(1)>three.high.shift(2))&(three.high.shift(1)>=three.high),three.high.shift(1),np.nan)
three["pivot_lo"]=np.where((three.low.shift(1)<three.low.shift(2))&(three.low.shift(1)<=three.low),three.low.shift(1),np.nan)
idx1=pd.Series(one.index,index=one.time_ny).to_dict(); idx3=pd.Series(three.index,index=three.time_ny).to_dict()

def simulate(c,i):
    j=i+3
    if j>=len(one) or one.iloc[j].ticker!=c.ticker:return None
    signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:return None
    entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+4*risk if c.direction=="LONG" else entry-4*risk
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker:break
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return "LOSS",entry,stop,target,risk
        if th:return "WIN",entry,stop,target,risk
    return None

rows=[]
for n,c in cand.iterrows():
    if (n+1)%2000==0:print(f"Quality build {n+1:,}/{len(cand):,}",flush=True)
    i=idx1.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one):continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:continue
    sg=1 if c.direction=="LONG" else -1
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        vals[f"m{k}_body_atr"]=abs(float(b.close-b.open))/a
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):continue
    tr=simulate(c,i)
    if tr is None:continue
    oc,entry,stop,target,risk=tr
    i3=idx3.get(c.time_ny); sr=np.nan; touches=0; sr_strength=np.nan
    if i3 is not None and i3>=5:
        hist=three.iloc[max(0,i3-100):i3+1]
        piv=hist.pivot_lo.dropna().to_numpy() if c.direction=="LONG" else hist.pivot_hi.dropna().to_numpy()
        atr3=float(three.iloc[i3].atr3)
        if len(piv) and np.isfinite(atr3) and atr3>0:
            ds=np.abs(piv-float(c.extreme))/atr3; sr=float(ds.min())
            touches=int((ds<=.30).sum()); sr_strength=int((ds<=.50).sum())
    # Candidate-level causal context already known at the extreme.
    atrc=float(c.atr) if "atr" in c and pd.notna(c.atr) and c.atr>0 else np.nan
    sweep=float(c.sweep_distance)/atrc if "sweep_distance" in c and np.isfinite(atrc) else np.nan
    wick=float(c.wick_percent) if "wick_percent" in c and pd.notna(c.wick_percent) else np.nan
    # Failure-to-continue / reclaim in first two closed minutes.
    first2=one.iloc[i+1:i+3]
    if c.direction=="LONG":
        adverse=(float(c.extreme)-float(first2.low.min()))/a
        reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a
    else:
        adverse=(float(first2.high.max())-float(c.extreme))/a
        reclaim=(float(c.extreme)-float(first2.iloc[-1].close))/a
    rows.append({"candidate_time":c.time_ny,"session":c.session,"direction":c.direction,"outcome":oc,"entry":entry,"risk":risk,
                 **vals,"sr_dist_atr":sr,"sr_touches_030":touches,"sr_strength_050":sr_strength,
                 "sweep_atr":sweep,"wick_percent":wick,"early_adverse_atr":adverse,"early_reclaim_atr":reclaim})

d=pd.DataFrame(rows).sort_values("candidate_time");d.to_parquet(OUT,index=False)
print(f"\nBase trades rebuilt: {len(d):,} | WR: {(d.outcome=='WIN').mean()*100:.2f}% | trades/day: {len(d)/365:.2f}")
print("\n=== WINNER VS LOSER QUALITY DIFFERENCES ===")
features=["sr_dist_atr","sr_touches_030","sr_strength_050","sweep_atr","wick_percent","early_adverse_atr","early_reclaim_atr","m1_move_atr","m1_close_pos","m2_body_atr","m2_move_atr","m2_close_pos","m2_dir_bars5"]
z=[]
for f in features:
 w=d.loc[d.outcome=="WIN",f].dropna();l=d.loc[d.outcome=="LOSS",f].dropna()
 if len(w) and len(l):
  pooled=np.sqrt((w.var()+l.var())/2); eff=(w.mean()-l.mean())/pooled if pooled>0 else 0
  z.append((f,len(w),w.mean(),l.mean(),eff,abs(eff)))
s=pd.DataFrame(z,columns=["feature","n_wins","winner_mean","loser_mean","effect","abs_effect"]).sort_values("abs_effect",ascending=False)
print(s.drop(columns="abs_effect").round(3).to_string(index=False))
print("\n=== SESSION BASELINE ===")
print(d.groupby("session").outcome.agg(trades="size",wr=lambda x:100*(x=="WIN").mean()).round(2).to_string())
print("\nSaved:",OUT)
