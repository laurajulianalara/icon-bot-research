import pandas as pd
import numpy as np

IN="data/v6_full_universe_validation.csv"
OUT="data/v6_full_universe_shortlist.csv"
d=pd.read_csv(IN)
# The broad test shows minute-2 causal entries clearly dominate minute-3.
m2=d[d.entry_after_minute==2].copy().sort_values(["robust_wr","test_trades"],ascending=[False,False])
print("=== LARGE-SAMPLE RESULT ===")
print("Best minute-2 rule:")
print(m2.head(1).round(2).to_string(index=False))
print("\nMinute-2 rules tested:",len(m2))
print("40%+ BOTH train/test:",int(((m2.train_wr>=40)&(m2.test_wr>=40)).sum()))
print("45%+ BOTH train/test:",int(((m2.train_wr>=45)&(m2.test_wr>=45)).sum()))
print("50%+ BOTH train/test:",int(((m2.train_wr>=50)&(m2.test_wr>=50)).sum()))
m2.to_csv(OUT,index=False)
print("\nSaved:",OUT)
