import pandas as pd, numpy as np

print("=== ORIGINAL 1,911 SELECTION-GATE FORENSICS ===")
ref=pd.read_csv("data/original_1911_exact_live_future_rr_audit.csv")
ref["candidate_time"]=pd.to_datetime(ref["candidate_time"],utc=True,errors="coerce")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()
O,H,L,C=[one[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
prev=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev)))
ATR=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()

rows=[]
for _,r in ref.iterrows():
    i=idx.get(r.candidate_time)
    if i is None or i<20 or i+3>=len(one):continue
    s=1 if str(r.direction).upper()=="LONG" else -1
    a=ATR[i]
    if not np.isfinite(a) or a<=0:continue
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k];pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-C[i])/a*s
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if s==1 else 1-cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*s)>0).sum())
    ext=float(r.get("extreme",np.nan))
    if not np.isfinite(ext):
        stop=float(r.get("stop",np.nan));ext=stop+.25 if s==1 else stop-.25
    b0=one.iloc[i];rng=max(float(b0.high-b0.low),.25)
    wick=((min(b0.open,b0.close)-b0.low)/rng) if s==1 else ((b0.high-max(b0.open,b0.close))/rng)
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-ext)/a if s==1 else (ext-float(first2.iloc[-1].close))/a
    base=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
    preopt=base and reclaim<=.90 and vals["m2_close_pos"]<=.80 and wick<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4
    final=preopt and (reclaim<.576132 or reclaim*wick<.183258)
    rows.append({"future_dependent":bool(r.future_dependent),"base":base,"preopt":preopt,"final":final,"reclaim":reclaim,"wick":wick,**vals})
d=pd.DataFrame(rows)
print("Reference rows reconstructed:",len(d))
for col in ["base","preopt","final"]:
    print(col, int(d[col].sum()), "/",len(d), f"({100*d[col].mean():.2f}%)")
print("\nBY KNOWN 3M-BUG CLASS")
print(d.groupby("future_dependent")[["base","preopt","final"]].mean().mul(100).round(2))
print("\nIf final-filter coverage is far below 100%, the documented V7/Option2 chain is NOT the actual selection gate that produced all 1,911 references. We must trace the exact producer files instead of applying this chain blindly.")
