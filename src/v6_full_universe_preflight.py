import pandas as pd
import numpy as np
from pathlib import Path

RULES="data/v6_walkforward_shortlist.csv"
SIG="data/v6_old_winner_early_signature.csv"
FEATURES="data/v3_reversal_features.parquet"
OUT="data/v6_full_universe_rule_validation.csv"

rules=pd.read_csv(RULES).drop_duplicates("rule")
# Take stable, reasonably covered finalists only.
rules=rules[(rules.worst_fold_wr>=55)&(rules.trades>=50)].head(25).copy()
sig=pd.read_csv(SIG)
sig["candidate_time"]=pd.to_datetime(sig.candidate_time,utc=True)
f=pd.read_parquet(FEATURES)
# This stage needs the same early-minute causal features for the full candidate universe.
# Fail loudly rather than silently validating on the old selected 121 again.
needed=set()
for rule in rules.rule:
    for part in rule.split(" & "):
        needed.add(part.split("<=")[0] if "<=" in part else part.split(">=")[0])
missing=[x for x in sorted(needed) if x not in f.columns]
print("Finalist rules:",len(rules))
print("Full candidate rows available:",len(f))
if missing:
    print("\nNEXT BUILD REQUIREMENT: full-universe table does not yet contain these causal early-minute features:")
    print(", ".join(missing))
    print("\nThis is expected. Do NOT reuse the 121-trade signature file as validation.")
    print("We must build the same m1/m2/m3 features for every historical reversal candidate before the real full-universe test.")
else:
    print("\nFull universe already has required features; ready for direct validation.")
