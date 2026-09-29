#!/usr/bin/env python3
"""THE ICON — Sep 18 reporter-vs-live decision diagnostic.

READ-ONLY diagnostic. It does not modify strategy logic, thresholds, market
data, reports, or execution. It traces the same Sep 18 candidates through the
frozen reporter decision path and the causal/live decision path so the first
implementation divergence is obvious.
"""
from pathlib import Path
import bisect, json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ
DAY=pd.Timestamp("2026-09-18",tz=TZ)
END=DAY+pd.Timedelta(days=1)
NEED=live.NEED
V11=Path("data/v11_reversal_state_forensics.csv")
REPORT=Path("data/reports/2026-09_trades.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

def norm_ts(x):
    x=pd.Timestamp(x)
    if x.tzinfo is None:
        x=x.tz_localize(TZ)
    else:
        x=x.tz_convert(TZ)
    return x.isoformat()

# Same cached source assembly used by the parity audit.
frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns): continue
        q=q[NEED].copy(); q["time_ny"]=et(q.time_ny); frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=DAY-pd.Timedelta(days=3))&(one.time_ny<END)].copy().reset_index(drop=True)

# Build the reporter's frozen V15 historical membership exactly.
if not V11.exists(): raise SystemExit("Missing "+str(V11))
ref=pd.read_csv(V11)
ref["candidate_time"]=pd.to_datetime(ref["candidate_time"],utc=True)
ref["candidate_time_et"]=ref["candidate_time"].dt.tz_convert(TZ)
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent
ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr
ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
parts=[]
for col,hi,w in live.SPEC:
    r=ref[col].rank(pct=True); comp=r if hi else 1-r; parts += [comp]*w
ref["score"]=pd.concat(parts,axis=1).mean(axis=1)
threshold=ref.score.quantile(.07)
hist_ref=ref[ref.score>=threshold].copy()
hist_ref["date_et"]=hist_ref.candidate_time_et.dt.date
hist_ref=hist_ref.sort_values("candidate_time_et").reset_index(drop=True)
hist_ref["trade_num_day"]=hist_ref.groupby("date_et").cumcount()+1
hist_ref=hist_ref[hist_ref.trade_num_day<=6]
allowed=set((norm_ts(t),str(d)) for t,d in zip(hist_ref.candidate_time_et,hist_ref.direction))
max_ref_date=ref.candidate_time_et.dt.date.max()

# Full-data candidate list is the reporter view.
pc=one.close.shift(1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
cand=live.build_candidates(one)
cand=cand[(cand.time_ny>=DAY)&(cand.time_ny<END)].copy()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

rows=[]
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    base={"candidate":c.time_ny,"session":c.session,"dir":c.direction}
    if i is None or i<20 or i+3>=len(one):
        rows.append({**base,"reporter":"NO_CONTEXT"}); continue
    a=float(one.iloc[i].atr1); sg=1 if c.direction=="LONG" else -1; vals={}
    if not np.isfinite(a) or a<=0:
        rows.append({**base,"reporter":"ATR_FAIL"}); continue
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):
        rows.append({**base,"reporter":"V7_FAIL"}); continue
    first2=one.iloc[i+1:i+3]
    reclaim=((float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG"
             else (float(c.extreme)-float(first2.iloc[-1].close))/a)
    if not(reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(c.wick_percent)<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4):
        rows.append({**base,"reporter":"V8_FAIL"}); continue
    key=(norm_ts(c.time_ny),str(c.direction))
    historical=c.time_ny.date()<=max_ref_date
    if historical and key not in allowed:
        rows.append({**base,"reporter":"V15_MEMBERSHIP_FAIL"}); continue
    if not historical:
        rows.append({**base,"reporter":"FORWARD_NOT_EXPECTED"}); continue
    rw=reclaim*float(c.wick_percent)
    if reclaim>=live.RTH and rw>=live.WTH:
        rows.append({**base,"reporter":"V27_FAIL"}); continue
    signal=one.iloc[i+3].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:
        rows.append({**base,"reporter":"SUPERSEDED"}); continue
    if one.iloc[i+3].ticker!=c.ticker:
        rows.append({**base,"reporter":"TICKER_FAIL"}); continue
    rows.append({**base,"reporter":"FINAL_PRECAP","entry_time":signal,
                 "entry":float(one.iloc[i+3].open),
                 "stop":float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25})

trace=pd.DataFrame(rows)

# What causal/live would actually emit on Sep 18, boundary by boundary.
sep=one[(one.time_ny>=DAY)&(one.time_ny<END)]
# IMPORTANT: entry may occur exactly at the session end (e.g. 05:00 for a
# 04:57 London candidate). Therefore iterate every 3-minute boundary that
# exists in the data, not only boundaries whose own timestamp is inside a session.
bounds=[t for t in sep.time_ny if t.minute%3==0]
live_rows=[]; count=0
for t in bounds:
    pos=one.index[one.time_ny==t]
    if not len(pos): continue
    p=int(pos[-1]); closed=one.loc[:p-1,NEED].tail(6500).copy(); op=one.loc[p,NEED].to_dict()
    for x in live.evaluate(closed,live_open=op):
        if pd.Timestamp(x["entry_time_et"])!=t: continue
        x_candidate=pd.Timestamp(x["candidate_time_et"])
        if x_candidate.tzinfo is None:
            x_candidate=x_candidate.tz_localize(TZ)
        else:
            x_candidate=x_candidate.tz_convert(TZ)
        if x_candidate.date()<=max_ref_date:
            membership_key=(norm_ts(x_candidate),str(x["direction"]))
            if membership_key not in allowed:
                continue
        if count>=6: continue
        count+=1; live_rows.append(x)

lv=pd.DataFrame(live_rows)
live_keys=set()
if not lv.empty:
    live_keys=set((norm_ts(t),str(d)) for t,d in zip(pd.to_datetime(lv.candidate_time_et),lv.direction))

trace["live_emitted"]=[(norm_ts(r.candidate),str(r.dir)) in live_keys for _,r in trace.iterrows()]

# Frozen report finals for Sep 18.
bench=set()
if REPORT.exists():
    b=pd.read_csv(REPORT); b["candidate_time"]=et(b.candidate_time)
    b=b[(b.candidate_time>=DAY)&(b.candidate_time<END)]
    bench=set((norm_ts(t),str(d)) for t,d in zip(b.candidate_time,b.direction))
trace["benchmark_final"]=[(norm_ts(r.candidate),str(r.dir)) in bench for _,r in trace.iterrows()]

interesting=trace[(trace.live_emitted)|(trace.benchmark_final)|(trace.reporter=="FINAL_PRECAP")].copy()
print("="*112)
print("THE ICON — SEP 18 REPORTER vs CAUSAL/LIVE DIAGNOSTIC")
print("="*112)
print("READ-ONLY. No strategy/filter/threshold/data/execution changes.")
print("TEST MODE: historical V15 membership mirrored before the 6/day cap.")
print("Reporter frozen V15 allowed set:",len(allowed),"| historical reference through:",max_ref_date)
print("\nKEY: benchmark_final = in frozen 73-trade report; live_emitted = causal engine actually emitted")
print("\n"+interesting[["candidate","session","dir","reporter","benchmark_final","live_emitted"]].to_string(index=False))

print("\n"+"="*112)
print("FIRST DIVERGENCES")
print("="*112)
d=interesting[interesting.benchmark_final!=interesting.live_emitted]
if d.empty:
    print("None on Sep 18.")
else:
    print(d[["candidate","session","dir","reporter","benchmark_final","live_emitted"]].to_string(index=False))

print("\nLIVE SEP 18 EMISSIONS")
if lv.empty: print("None")
else: print(lv[["candidate_time_et","entry_time_et","session","direction","entry","stop","v15_score"]].to_string(index=False))
print("\nDiagnostic complete. No files changed.")


# ------------------------------------------------------------------
# DEEP SEP 18 FORWARD DIAGNOSTIC — read-only
# Shows whether full-data future candidate knowledge changes supersession.
# ------------------------------------------------------------------
print("\n"+"="*112)
print("SEP 18 DEEP FORWARD INSPECTION")
print("="*112)
print("Candidate | benchmark | live | full_next_same_extreme | entry_boundary | future_supersession_before/at_entry")

# Full-data candidate table already exists as cand.  Compare every interesting
# candidate with the next same-direction session extreme known only in the
# completed full-day view.
cand_lookup={}
for _,cc in cand.iterrows():
    cand_lookup[(norm_ts(cc.time_ny),str(cc.direction))]=cc

for _,rr in interesting.sort_values("candidate").iterrows():
    key=(norm_ts(rr.candidate),str(rr.dir))
    cc=cand_lookup.get(key)
    nxt=pd.NaT if cc is None else cc.next_same_extreme_time
    entry_boundary=pd.Timestamp(rr.candidate)+pd.Timedelta(minutes=3)
    future_block=bool(pd.notna(nxt) and entry_boundary>=pd.Timestamp(nxt))
    print(
        f"{pd.Timestamp(rr.candidate)} | bench={bool(rr.benchmark_final)} | live={bool(rr.live_emitted)} "
        f"| next={nxt} | entry={entry_boundary} | future_block={future_block}"
    )

print("\nInterpretation:")
print("future_block=True means the full-day reporter can see a later session extreme at/before the entry boundary.")
print("A truly causal engine at that entry boundary cannot use an unfinished future 3m candle to reject the earlier setup.")
print("No strategy/filter/threshold/data/execution changes were made.")


# ------------------------------------------------------------------
# DEEP TRACE: the two benchmark NYPM trades that causal/live missed.
# Recompute the exact live V7/V8/V15/V27 inputs at their entry boundary,
# and report how many earlier signals had already consumed the 6/day cap.
# ------------------------------------------------------------------
print("\n"+"="*112)
print("SEP 18 — 13:45 / 16:03 BENCHMARK-MISS TRACE")
print("="*112)

targets=[
    (pd.Timestamp("2026-09-18 13:45",tz=TZ),"SHORT"),
    (pd.Timestamp("2026-09-18 16:03",tz=TZ),"SHORT"),
]
for target, direction in targets:
    entry_boundary=target+pd.Timedelta(minutes=3)
    pos=one.index[one.time_ny==entry_boundary]
    print(f"\nTARGET {target} {direction} | entry boundary {entry_boundary}")
    if not len(pos):
        print("  ERROR: entry boundary absent from 1m data"); continue
    p=int(pos[-1])
    closed=one.loc[:p-1,NEED].tail(6500).copy()
    op=one.loc[p,NEED].to_dict()

    # Build the causal candidate set exactly as live.evaluate sees it.
    work=closed.copy().sort_values("time_ny").reset_index(drop=True)
    pc2=work.close.shift(1)
    work["atr1"]=pd.concat([work.high-work.low,(work.high-pc2).abs(),(work.low-pc2).abs()],axis=1).max(axis=1).rolling(20).mean()
    cc=live.build_candidates(work)
    hit=cc[(cc.time_ny==target)&(cc.direction==direction)]
    if hit.empty:
        print("  FAIL STAGE: candidate absent in causal build_candidates()"); continue
    x=hit.iloc[-1]
    ii=pd.Series(work.index,index=work.time_ny).to_dict().get(x.time_ny)
    a=float(work.iloc[ii].atr1); sg=-1
    vals={}
    for k in [1,2]:
        b=work.iloc[ii+k]; pre=work.iloc[max(0,ii+k-5):ii+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(work.iloc[ii].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    v7=(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912)
    first2=work.iloc[ii+1:ii+3]
    reclaim=(float(x.extreme)-float(first2.iloc[-1].close))/a
    v8=(reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(x.wick_percent)<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4)
    rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(x.wick_percent),0),1))
    ri=-vals["m2_move_atr"]; ca=float(x.atr)
    sa=float(x.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
    rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*float(x.wick_percent)
    f={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,
       "reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,"sweep_minus_reclaim":sa-reclaim,
       "impulse_minus_reclaim":ri-reclaim,"quality_balance":rq*itr/(1+rts)}
    sc=live.score(f)
    v15=bool(np.isfinite(sc) and sc>=live.V15_THRESHOLD)
    v27=not(reclaim>=live.RTH and rxw>=live.WTH)
    future_same=x.next_same_extreme_time
    superseded=bool(pd.notna(future_same) and entry_boundary>=future_same)
    ticker_ok=(op["ticker"]==x.ticker)
    emitted=live.evaluate(closed,live_open=op)
    emitted_hit=[e for e in emitted if pd.Timestamp(e["candidate_time_et"])==target and e["direction"]==direction]

    print(f"  causal candidate: YES")
    print(f"  V7: {v7} | m1_move={vals['m1_move_atr']:.6f} m1_close={vals['m1_close_pos']:.6f} m2_close={vals['m2_close_pos']:.6f}")
    print(f"  V8: {v8} | reclaim={reclaim:.6f} wick={float(x.wick_percent):.6f} m2_move={vals['m2_move_atr']:.6f} dirbars={vals['m2_dir_bars5']}")
    print(f"  V15: {v15} | score={sc:.9f} threshold={live.V15_THRESHOLD:.9f}")
    print(f"  V27: {v27} | reclaim={reclaim:.6f} rxw={rxw:.6f} thresholds=({live.RTH:.6f},{live.WTH:.6f})")
    print(f"  causal next_same_extreme={future_same} | superseded={superseded}")
    print(f"  ticker_ok={ticker_ok}")
    print(f"  raw live.evaluate emitted target={bool(emitted_hit)}")
    if not v7: print("  FIRST FAIL: V7")
    elif not v8: print("  FIRST FAIL: V8")
    elif not v15: print("  FIRST FAIL: V15 FORWARD SCORE")
    elif not v27: print("  FIRST FAIL: V27")
    elif superseded: print("  FIRST FAIL: SUPERSEDED")
    elif not ticker_ok: print("  FIRST FAIL: TICKER")
    elif not emitted_hit: print("  FIRST FAIL: evaluate() discrepancy after listed gates")
    else: print("  RAW STRATEGY PASSES — investigate wrapper/day-cap consumption")

print("\nNo strategy/filter/threshold/data/execution changes were made.")


# ------------------------------------------------------------------
# CAUSAL SUPERSESSION TIMELINE — Sep 18
# Read-only: determine what information exists at each entry boundary.
# ------------------------------------------------------------------
print("\n"+"="*112)
print("SEP 18 — CAUSAL SUPERSESSION TIMELINE")
print("="*112)
print("Rule under inspection: a candidate may only be superseded by information that is fully known by its entry boundary.")
print("No strategy rule is changed here; this compares full-day lookahead vs boundary-known state.\n")

for _,rr in interesting.sort_values("candidate").iterrows():
    ct=pd.Timestamp(rr.candidate)
    eb=ct+pd.Timedelta(minutes=3)
    pos=one.index[one.time_ny==eb]
    if not len(pos): continue
    p=int(pos[-1])
    closed=one.loc[:p-1,NEED].copy()
    causal_c=live.build_candidates(closed)
    same=causal_c[(causal_c.time_ny==ct)&(causal_c.direction==str(rr.dir))]
    causal_next=pd.NaT
    if not same.empty:
        causal_next=same.iloc[-1].next_same_extreme_time
    full= cand_lookup.get((norm_ts(ct),str(rr.dir)))
    full_next=pd.NaT if full is None else full.next_same_extreme_time
    full_block=bool(pd.notna(full_next) and eb>=pd.Timestamp(full_next))
    causal_block=bool(pd.notna(causal_next) and eb>=pd.Timestamp(causal_next))
    print(f"{ct} {rr.dir} | entry={eb} | full_next={full_next} block={full_block} | causal_next={causal_next} block={causal_block}")

print("\nIf full_block=True but causal_block=False, the historical reporter's rejection depends on later/full-day candidate knowledge")
print("that was not available to the bot at the entry boundary.")
print("Diagnostic complete. No files changed.")
