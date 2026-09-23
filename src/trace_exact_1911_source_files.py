import pandas as pd, numpy as np
print("=== TRACE EXACT 1,911 PRODUCER CHAIN ===")
files=[("current","data/v27_option2a_trades.csv"),("prior","data/v56_icon_bot_funded_prior_year_trades.csv")]
for name,path in files:
 d=pd.read_csv(path)
 print("\n",name,path,"rows",len(d))
 print("columns:",", ".join(d.columns))
 for c in ["early_reclaim_atr","wick_percent","reclaim_x_wick","m2_close_pos","m2_move_atr","m2_dir_bars5"]:
  if c in d:
   x=pd.to_numeric(d[c],errors="coerce")
   print(c,"non-null",x.notna().sum(),"min",x.min(),"median",x.median(),"max",x.max())
 if "early_reclaim_atr" in d and "wick_percent" in d:
  rx=pd.to_numeric(d["early_reclaim_atr"],errors="coerce")*pd.to_numeric(d["wick_percent"],errors="coerce")
  pre=(pd.to_numeric(d.early_reclaim_atr,errors="coerce")<=.90)&(pd.to_numeric(d.m2_close_pos,errors="coerce")<=.80)&(pd.to_numeric(d.wick_percent,errors="coerce")<=.60)&(pd.to_numeric(d.m2_move_atr,errors="coerce")<=.15)&(pd.to_numeric(d.m2_dir_bars5,errors="coerce")<=4)
  final=pre&((pd.to_numeric(d.early_reclaim_atr,errors="coerce")<.576132)|(rx<.183258))
  print("preopt membership",int(pre.sum()),"/",len(d))
  print("final membership",int(final.sum()),"/",len(d))
print("\nThese source CSVs are the authoritative 953+958 populations. If they pass 100%, our previous audit reconstructed features against the wrong timestamp/extreme, not the wrong strategy chain.")
