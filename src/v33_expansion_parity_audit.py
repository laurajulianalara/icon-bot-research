import pandas as pd
tr=pd.read_csv("data/v27_option2a_trades.csv")
x=pd.read_csv("data/v32_option2a_true_expansion_before_stop.csv")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)
x["time"]=pd.to_datetime(x["time"],utc=True)
m=tr.merge(x[["time","mfe_before_stop_r"]],left_on="candidate_time",right_on="time",how="left")
m["v32_4r"]=m["mfe_before_stop_r"]>=4
m["orig_win"]=m["outcome"].eq("WIN")
bad=m[m.v32_4r!=m.orig_win]
print("=== V32 PARITY AUDIT ===")
print("Total",len(m),"| Original wins",m.orig_win.sum(),"| V32 >=4R",m.v32_4r.sum())
print("Mismatches",len(bad))
print("V32 says 4R / original LOSS:",((m.v32_4r)&(~m.orig_win)).sum())
print("Original WIN / V32 says <4R:",((~m.v32_4r)&m.orig_win).sum())
print("\nMismatch sample:")
print(bad[["candidate_time","session","direction","entry","risk","outcome","mfe_before_stop_r"]].head(20).to_string(index=False))
