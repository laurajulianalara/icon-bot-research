#!/usr/bin/env python3
"""THE ICON — verify the 155 historical supersession mismatches.

FAST / READ ONLY. Reuses the saved September causal replay and the original
full-day 1m dataset. No slow bar-by-bar replay and no strategy changes.

For each causal-only signal that the original full-day simulate() classifies
as SUPERSEDED, this proves whether the superseding 3m bucket was actually
complete at the signal timestamp. If it was not complete, historical rejection
used information unavailable at live entry time.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

PROOF=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
if not PROOF.exists():
    raise RuntimeError("Missing original simulate proof. Run: python src/prove_september_original_simulate_extras.py")

def etcol(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

p=pd.read_csv(PROOF)
p=p[p.original_simulate_result.eq("SUPERSEDED")].copy()
p["entry_time"]=etcol(p.entry_time)
p["next_extreme"]=etcol(p.next_same_extreme_time)

# A left-labeled 3m bucket T contains T,T+1,T+2 and is only knowable after T+2 closes.
p["superseding_bucket_complete_at_entry"] = p.entry_time >= (p.next_extreme + pd.Timedelta(minutes=3))
p["minutes_until_bucket_complete"] = ((p.next_extreme + pd.Timedelta(minutes=3))-p.entry_time).dt.total_seconds()/60
p["same_timestamp"] = p.entry_time.eq(p.next_extreme)

print("="*96)
print("THE ICON — 155 SUPERSESSION INFORMATION-TIMING VERIFICATION")
print("="*96)
print("Supersession cases:",len(p))
print("Superseding 3m bucket complete at entry:",int(p.superseding_bucket_complete_at_entry.sum()))
print("Superseding 3m bucket NOT complete at entry:",int((~p.superseding_bucket_complete_at_entry).sum()))
print("Superseding bucket starts exactly at entry:",int(p.same_timestamp.sum()))
print("\nMinutes from entry until superseding bucket is fully knowable:")
print(p.minutes_until_bucket_complete.value_counts(dropna=False).sort_index().to_string())

if len(p)==155 and (~p.superseding_bucket_complete_at_entry).all():
    print("\nPASS — 155/155 historical supersession rejections require an unfinished 3m bucket at entry.")
    print("These cannot be known causally at the original market-entry timestamp.")
elif (~p.superseding_bucket_complete_at_entry).all():
    print(f"\nPASS — {len(p)}/{len(p)} tested supersession rejections require unfinished 3m information at entry.")
else:
    print("\nMIXED — some supersession rejections were already knowable at entry. Inspect output before patching logic.")

out=Path("data/reports/2026-09_supersession_timing_verification.csv")
p.to_csv(out,index=False)
print("Saved:",out)
print("READ ONLY — no strategy thresholds, entries, or datasets changed.")
