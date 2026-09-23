import pandas as pd, numpy as np

print("=== ONE CAUSAL ENTER/WAIT RULE — FULL NATIVE 1M BACKTEST ===")
d=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
dc=next(c for c in ["direction","side","dir"] if c in d.columns)
mc=next((c for c in ["minute","delay_min","minutes_after","minute_after"] if c in d.columns),None)
if mc is not None: d=d[d[mc]==0].copy()
d=d.sort_values(tc).drop_duplicates([tc,dc]).reset_index(drop=True)

# Rule chosen from forensic result, before seeing this full-history performance:
# range_8_atr <= 2.1841. It was the strongest simple causal separator.
RULE=2.1841
sel=d[pd.to_numeric(d["range_8_atr"],errors="coerce")<=RULE].copy()
print("All native 1m extremes:",len(d))
print("ENTER signals:",len(sel))
print("Rule: range_8_atr <=",RULE)

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

# Candidate extreme/risk source from V106 if present; otherwise native candidate bar.
ec=next((c for c in ["extreme","candidate_extreme","extreme_price"] if c in sel.columns),None)

for rr in range(1,7):
    w=l=u=miss=0
    for _,x in sel.iterrows():
        i=idx.get(x[tc])
        if i is None or i+1>=len(one): miss+=1; continue
        # Pure native 1m: candidate candle is complete; enter next minute OPEN.
        j=i+1
        entry=float(one.iloc[j].open)
        extreme=float(x[ec]) if ec and pd.notna(x[ec]) else float(one.iloc[i].low if str(x[dc]).upper()=="LONG" else one.iloc[i].high)
        direction=str(x[dc]).upper()
        stop=extreme-.25 if direction=="LONG" else extreme+.25
        risk=entry-stop if direction=="LONG" else stop-entry
        if not np.isfinite(risk) or risk<=0: u+=1; continue
        target=entry+rr*risk if direction=="LONG" else entry-rr*risk
        out=0
        for _,b in one.iloc[j:min(j+241,len(one))].iterrows():
            if "ticker" in one.columns and b.ticker!=one.iloc[j].ticker: break
            if direction=="LONG":
                if b.low<=stop: out=-1; break
                if b.high>=target: out=1; break
            else:
                if b.high>=stop: out=-1; break
                if b.low<=target: out=1; break
        if out==1:w+=1
        elif out==-1:l+=1
        else:u+=1
    n=w+l
    print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | misses={miss}" if n else f"1:{rr} no resolved")

print("\nIMPORTANT: this is the independent test of the simple ENTER rule on all native 1m extremes.")
print("If performance is weak, we do NOT tune this same dataset repeatedly; next we build a chronological discovery/validation split using the frozen 766 as research labels.")
