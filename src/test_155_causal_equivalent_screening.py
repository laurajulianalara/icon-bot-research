#!/usr/bin/env python3
"""THE ICON — causal-equivalent screening: 155 supersession extras vs valid September trades.

FAST / READ ONLY. No slow full-month bar-by-bar replay. No production changes.
Every tested feature is available at the original entry OPEN.

Purpose: determine whether a simple causal screen can reject supersession extras
while preserving legitimate corrected September Option 2B trades. This script
reports trade-offs only; it does NOT choose or promote a rule.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

PROOF=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
GOOD=Path("data/reports/2026-09_trades.csv")
for p in [PROOF,GOOD,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

one=pd.read_parquet(live.HIST)[live.NEED].copy()
one["time_ny"]=et(one.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.session),str(r.direction)):r for _,r in cand.iterrows()}
omap={str(r.time_ny):r for _,r in one.iterrows()}

bad=pd.read_csv(PROOF)
bad=bad[bad.original_simulate_result.eq("SUPERSEDED")].copy()
bad["entry_time"]=et(bad.entry_time); bad["candidate_time"]=et(bad.candidate_time)
bad["kind"]="SUPERSESSION_EXTRA"

good=pd.read_csv(GOOD)
# tolerate reporter column naming
entry_col="entry_time_et" if "entry_time_et" in good.columns else "entry_time"
cand_col="candidate_time_et" if "candidate_time_et" in good.columns else "candidate_time"
good["entry_time"]=et(good[entry_col]); good["candidate_time"]=et(good[cand_col])
good["kind"]="VALID_OPTION2B"

def feature_rows(df):
    rows=[]
    for _,x in df.iterrows():
        c=cmap.get((str(x.candidate_time),str(x.session),str(x.direction)))
        b=omap.get(str(x.entry_time))
        if c is None or b is None: continue
        prior=(float(c.extreme)+float(c.sweep_distance)) if c.direction=="LONG" else (float(c.extreme)-float(c.sweep_distance))
        op=float(b.open); ca=float(c.atr)
        safe=(op-float(c.extreme)) if c.direction=="LONG" else (float(c.extreme)-op)
        rows.append(dict(kind=x.kind,entry_time=x.entry_time,candidate_time=x.candidate_time,
            session=x.session,direction=x.direction,entry_open=op,candidate_extreme=float(c.extreme),
            prior_extreme=prior,candidate_atr=ca,
            open_beyond_prior=(op<=prior) if c.direction=="LONG" else (op>=prior),
            safe_distance_atr=safe/ca if np.isfinite(ca) and ca>0 else np.nan))
    return pd.DataFrame(rows)

q=pd.concat([feature_rows(bad),feature_rows(good)],ignore_index=True)
B=q[q.kind.eq("SUPERSESSION_EXTRA")].copy()
G=q[q.kind.eq("VALID_OPTION2B")].copy()

print("="*108)
print("THE ICON — CAUSAL-EQUIVALENT SCREENING TRADE-OFF")
print("="*108)
print(f"Supersession extras available: {len(B)} / 155")
print(f"Valid corrected September trades available: {len(G)} / {len(good)}")
print("\nRULE: entry OPEN already beyond prior session extreme")
br=int(B.open_beyond_prior.sum()); gr=int(G.open_beyond_prior.sum())
print(f"Rejects extras: {br}/{len(B)} ({100*br/max(len(B),1):.1f}%)")
print(f"Rejects valid : {gr}/{len(G)} ({100*gr/max(len(G),1):.1f}%)")
print(f"Preserves valid: {len(G)-gr}/{len(G)} ({100*(len(G)-gr)/max(len(G),1):.1f}%)")

print("\nDISTANCE RULES — reject when safe_distance_atr <= threshold")
print(f"{'threshold':>10} | {'bad removed':>18} | {'good removed':>18} | {'good kept':>18}")
print("-"*76)
for th in [0,.025,.05,.075,.10,.125,.15,.175,.20,.225,.25,.275,.30,.35,.40,.45,.50]:
    br=int((B.safe_distance_atr<=th).sum()); gr=int((G.safe_distance_atr<=th).sum())
    print(f"{th:10.3f} | {br:3d}/{len(B):3d} {100*br/max(len(B),1):6.1f}% | {gr:3d}/{len(G):3d} {100*gr/max(len(G),1):6.1f}% | {len(G)-gr:3d}/{len(G):3d} {100*(len(G)-gr)/max(len(G),1):6.1f}%")

print("\nCOMBINED RULES — beyond prior extreme AND distance <= threshold")
print(f"{'threshold':>10} | {'bad removed':>18} | {'good removed':>18} | {'good kept':>18}")
print("-"*76)
for th in [.05,.075,.10,.125,.15,.175,.20,.225,.25,.275,.30,.35,.40,.45,.50]:
    br=int((B.open_beyond_prior & (B.safe_distance_atr<=th)).sum())
    gr=int((G.open_beyond_prior & (G.safe_distance_atr<=th)).sum())
    print(f"{th:10.3f} | {br:3d}/{len(B):3d} {100*br/max(len(B),1):6.1f}% | {gr:3d}/{len(G):3d} {100*gr/max(len(G),1):6.1f}% | {len(G)-gr:3d}/{len(G):3d} {100*(len(G)-gr)/max(len(G),1):6.1f}%")

out=Path("data/reports/2026-09_causal_equivalent_screening.csv")
q.to_csv(out,index=False)
print("\nSaved:",out)
print("READ ONLY — no thresholds, entries, live engine, or datasets changed.")
