import pandas as pd, numpy as np

print("=== FULL-STREAM BLIND +2 STATE-MACHINE BACKTEST ===")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
ny=one.t.dt.tz_convert("America/New_York")
one["date"]=ny.dt.date
one["mins"]=ny.dt.hour*60+ny.dt.minute

def session(m):
    if m>=1200: return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None
one["session"]=[session(m) for m in one.mins]

# Blind candidate stream: every new session high/low. No reference labels are used.
cands=[]
for (d,s),g in one.dropna(subset=["session"]).groupby(["date","session"],sort=False):
    hi=-np.inf; lo=np.inf
    for i in g.index:
        h=float(one.at[i,"high"]); l=float(one.at[i,"low"])
        if h>hi:
            cands.append((i,"SHORT")); hi=h
        if l<lo:
            cands.append((i,"LONG")); lo=l

print("Blind session-extreme candidates:",len(cands))

# +2 rule: after candidate candle T, allow T+1 and T+2 to print.
# Keep updating the candidate extreme with only those completed bars.
# Enter at T+3 open. One position at a time. Stop first on ambiguous bar.
for rr in range(1,7):
    w=l=u=signals=0; busy_until=-1
    for i,direction in cands:
        if i<=busy_until or i+3>=len(one): continue
        # Require contiguous minutes and same session through decision window.
        ts=[one.at[i+k,"t"] for k in range(4)]
        if any((ts[k]-ts[k-1])!=pd.Timedelta(minutes=1) for k in range(1,4)): continue
        if any(one.at[i+k,"session"]!=one.at[i,"session"] for k in range(3)): continue
        win=one.iloc[i:i+3]
        extreme=float(win.high.max() if direction=="SHORT" else win.low.min())
        j=i+3
        entry=float(one.at[j,"open"])
        stop=extreme+.25 if direction=="SHORT" else extreme-.25
        risk=stop-entry if direction=="SHORT" else entry-stop
        if not np.isfinite(risk) or risk<=0: continue
        target=entry-rr*risk if direction=="SHORT" else entry+rr*risk
        signals+=1; out=0; end=j
        for k in range(j,min(j+241,len(one))):
            b=one.iloc[k]; end=k
            if direction=="SHORT":
                if b.high>=stop: out=-1; break
                if b.low<=target: out=1; break
            else:
                if b.low<=stop: out=-1; break
                if b.high>=target: out=1; break
        busy_until=end
        if out==1:w+=1
        elif out==-1:l+=1
        else:u+=1
    resolved=w+l
    wr=100*w/resolved if resolved else np.nan
    print(f"1:{rr} | signals={signals} | {w}W/{l}L/{u}U | WR {wr:.2f}%")

print("\nThis is the decisive blind test: it uses ALL native-1m session extremes, no 1,911 reference labels, no future final-extreme label, and only information available through T+2 before entering T+3 open.")
