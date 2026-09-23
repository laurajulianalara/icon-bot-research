import pandas as pd, numpy as np

print("=== CLEAN 3M LIVE-TIMING TEST — ORIGINAL ICON BOT ===")
ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
BASE="data/v7_base_trade_quality.parquet"
one=pd.read_parquet(ONE).copy(); cand=pd.read_parquet(CAND).copy(); q=pd.read_parquet(BASE).copy()
for d,c in [(one,"time_ny"),(cand,"time_ny"),(q,"candidate_time")]: d[c]=pd.to_datetime(d[c],utc=True)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}

# Exact saved original filters. Do NOT reconstruct features.
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
q=q[(q.early_reclaim_atr<=.90)&(q.m2_close_pos<=.80)&(q.wick_percent<=.60)&(q.m2_move_atr<=.15)&(q.m2_dir_bars5<=4)]
q=q[(q.early_reclaim_atr<.576132)|(q.reclaim_x_wick<.183258)].copy()
print("Original-filter setups before live timing:",len(q))

def test(delay):
    setups=[]
    for _,r in q.iterrows():
        c=cm.get((r.candidate_time,str(r.direction)))
        if c is None: continue
        i=idx.get(c.time_ny)
        if i is None: continue
        j=i+delay
        if j>=len(one) or one.iloc[j].ticker!=c.ticker: continue
        # A completed 3m candidate stamped T is knowable only at T+3.
        # delay=3 => enter first open after one completed candidate 3m candle.
        # delay=6 => wait one additional completed 3m candle.
        # Live invalidation: only use highs/lows that have actually printed by decision time.
        window=one.iloc[i:j]
        if len(window)==0: continue
        ext=float(window.low.min()) if c.direction=="LONG" else float(window.high.max())
        setups.append((j,str(c.direction),ext))
    print(f"\n--- {'1 completed 3m candle' if delay==3 else '2 completed 3m candles'} | entry T+{delay} open ---")
    for rr in range(1,7):
        w=l=u=0; busy=-1; sig=0
        for j,d,ext in setups:
            if j<=busy: continue
            entry=float(one.iloc[j].open); stop=ext-.25 if d=="LONG" else ext+.25
            risk=entry-stop if d=="LONG" else stop-entry
            if risk<=0: continue
            target=entry+rr*risk if d=="LONG" else entry-rr*risk
            sig+=1; out=0; end=j
            for k in range(j,min(j+241,len(one))):
                b=one.iloc[k]; end=k
                if d=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low>=target: pass
                    if b.low<=target: out=1; break
            busy=end
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        wr=100*w/(w+l) if w+l else np.nan
        print(f"1:{rr} | signals={sig} | WR={wr:.2f}% | {w}W/{l}L/{u}U")

test(3)
test(6)
print("\nNOTE: This preserves the saved original ATR/reclaim/wick/m1/m2 filter values and changes only when the 3m information is legally available. No future next-extreme invalidation is used.")
