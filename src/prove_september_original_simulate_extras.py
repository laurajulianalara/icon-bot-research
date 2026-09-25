#!/usr/bin/env python3
"""THE ICON — Full September original simulate() proof.

READ ONLY. No strategy changes.
Takes every causal-only extra already saved by the September true bar-by-bar
replay and runs it through the original V7 simulate() rejection ordering.

This does NOT rerun the slow minute-by-minute replay; it reuses the saved
causal emissions and tests all extras against the original historical
supersession/ticker/risk/4R simulation logic.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

CAUSAL=Path("data/reports/2026-09_true_bar_by_bar.csv")
HISTTR=Path("data/reports/2026-09_trades.csv")
for p in [CAUSAL,HISTTR,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

ca=pd.read_csv(CAUSAL)
ca["entry_time"]=et(ca.entry_time_et); ca["candidate_time"]=et(ca.candidate_time_et)
ca=ca[(ca.entry_time.dt.date>=pd.Timestamp("2026-09-01").date())&
      (ca.entry_time.dt.date<=pd.Timestamp("2026-09-24").date())].copy().sort_values("entry_time")

ht=pd.read_csv(HISTTR); ht["entry_time"]=et(ht.entry_time)
ht=ht[(ht.entry_time.dt.date>=pd.Timestamp("2026-09-01").date())&
      (ht.entry_time.dt.date<=pd.Timestamp("2026-09-24").date())].copy()
hkeys=set(zip(ht.entry_time.astype(str),ht.session.astype(str),ht.direction.astype(str)))
ca["original"]=ca.apply(lambda x:(str(x.entry_time),str(x.session),str(x.direction)) in hkeys,axis=1)
extras=ca[~ca.original].copy()

one=pd.read_parquet(live.HIST)[live.NEED].copy(); one["time_ny"]=et(one.time_ny)
start=pd.Timestamp("2026-08-29",tz=live.TZ); end=pd.Timestamp("2026-09-25",tz=live.TZ)
one=one[(one.time_ny>=start)&(one.time_ny<end)].sort_values("time_ny").reset_index(drop=True)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.session),str(r.direction)):r for _,r in cand.iterrows()}

rows=[]
for _,x in extras.iterrows():
    ck=(str(x.candidate_time),str(x.session),str(x.direction)); c=cmap.get(ck)
    reason="UNKNOWN"; signal=pd.NaT; next_ext=pd.NaT
    if c is None: reason="NO_FULL_DAY_CANDIDATE"
    else:
        i=idx.get(c.time_ny)
        if i is None: reason="NO_1M_INDEX"
        elif i+3>=len(one): reason="NO_SIGNAL_BAR"
        else:
            j=i+3; signal=one.iloc[j].time_ny; next_ext=c.next_same_extreme_time
            # Original V7 simulate() rejection order.
            if one.iloc[j].ticker != c.ticker: reason="TICKER_MISMATCH"
            elif pd.notna(next_ext) and signal>=next_ext: reason="SUPERSEDED"
            else:
                entry=float(one.iloc[j].open)
                stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
                risk=entry-stop if c.direction=="LONG" else stop-entry
                if risk<=0: reason="INVALID_RISK"
                else:
                    target=entry+4*risk if c.direction=="LONG" else entry-4*risk
                    outcome=None
                    for z in range(j,min(j+241,len(one))):
                        b=one.iloc[z]
                        if b.ticker!=c.ticker: break
                        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
                        th=b.high>=target if c.direction=="LONG" else b.low<=target
                        if sh: outcome="LOSS"; break
                        if th: outcome="WIN"; break
                    reason="SIMULATE_ACCEPT_"+str(outcome) if outcome else "NO_4R_OR_SL_WITHIN_WINDOW"
    rows.append({"date":x.entry_time.date(),"entry_time":x.entry_time,
                 "candidate_time":x.candidate_time,"session":x.session,
                 "direction":x.direction,"signal_time_from_original":signal,
                 "next_same_extreme_time":next_ext,"original_simulate_result":reason})

out=pd.DataFrame(rows)
print("="*116)
print("THE ICON — FULL SEPTEMBER ORIGINAL simulate() PROOF")
print("="*116)
print(f"Historical trades: {len(ht)} | causal emitted: {len(ca)} | causal-only extras tested: {len(out)}")
print("\nORIGINAL simulate() RESULT — ALL EXTRAS")
print(out.original_simulate_result.value_counts().to_string())

print("\nBY DAY")
daily=out.groupby(["date","original_simulate_result"]).size().unstack(fill_value=0)
daily["TOTAL_EXTRAS"]=daily.sum(axis=1)
print(daily.to_string())

n=int((out.original_simulate_result=="SUPERSEDED").sum())
print("\n"+"="*116)
print(f"SUPERSESSION PROOF: {n}/{len(out)} causal-only September extras rejected by original simulate() specifically for supersession.")
if len(out)==224 and n==224:
    print("PASS — 224/224 SEPTEMBER EXTRAS ARE REJECTED BY ORIGINAL V7 simulate() SUPERSESSION.")
elif n==len(out) and len(out)>0:
    print(f"PASS — ALL {len(out)}/{len(out)} SAVED SEPTEMBER EXTRAS ARE REJECTED BY ORIGINAL V7 simulate() SUPERSESSION.")
else:
    print(f"PARTIAL — {len(out)-n} extras have another original-simulate result. Inspect summary/detail CSV before changing live code.")

save=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
save.parent.mkdir(parents=True,exist_ok=True); out.to_csv(save,index=False)
print("Saved:",save)
print("READ ONLY — no Option 2B code, thresholds, or historical datasets changed.")
