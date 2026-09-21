import pandas as pd
import numpy as np

RULES="data/v6_old_winner_early_rules.csv"
SIG="data/v6_old_winner_early_signature.csv"
OUT="data/v6_early_rule_robustness.csv"

r=pd.read_csv(RULES);d=pd.read_csv(SIG)
d["candidate_time"]=pd.to_datetime(d.candidate_time,utc=True);d=d.sort_values("candidate_time").reset_index(drop=True)

# Deduplicate identical rules created by repeated quantile thresholds.
r=r.drop_duplicates("rule").copy()
# Require meaningful coverage; tiny 4-7 trade validation cells are too fragile.
r=r[(r.discovery_trades>=15)&(r.validation_trades>=8)&(r.test_trades>=8)].copy()
r["total_trades"]=r.discovery_trades+r.validation_trades+r.test_trades
r["weighted_wr"]=(r.discovery_trades*r.discovery_wr+r.validation_trades*r.validation_wr+r.test_trades*r.test_wr)/r.total_trades
r["spread"]=r[["discovery_wr","validation_wr","test_wr"]].max(axis=1)-r[["discovery_wr","validation_wr","test_wr"]].min(axis=1)
r["robust_score"]=r[["discovery_wr","validation_wr","test_wr"]].min(axis=1)-.35*r.spread
r=r.sort_values(["robust_score","total_trades"],ascending=[False,False])
r.to_csv(OUT,index=False)

print("Unique rules after de-duplication:",len(r))
print("\n=== ROBUST EARLY RULES WITH MINIMUM SAMPLE SIZE ===")
print(r[["rule","discovery_trades","discovery_wr","validation_trades","validation_wr","test_trades","test_wr","total_trades","weighted_wr","spread","robust_score"]].head(40).round(2).to_string(index=False))
print("\n50%+ all periods with >=15/8/8 trades:",int(((r.discovery_wr>=50)&(r.validation_wr>=50)&(r.test_wr>=50)).sum()))
print("55%+ all periods with >=15/8/8 trades:",int(((r.discovery_wr>=55)&(r.validation_wr>=55)&(r.test_wr>=55)).sum()))
print("\nSaved:",OUT)
