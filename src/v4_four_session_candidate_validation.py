import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_four_session_candidate_validation.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

# Session-specific candidate families based on the broad robust neighborhoods found so far.
rules={
 "ASIA":   dict(cisd=.95,disp=1.20,sweep=.20),
 "NYAM":   dict(cisd=.95,disp=1.20,sweep=.20),
 "LONDON": dict(cisd=.96,disp=1.20,sweep=.20),
 "NYPM":   dict(cisd=.97,disp=1.10,sweep=None),
}

parts=[]
for s,r in rules.items():
    q=df[df.session==s].copy()
    q=q[(q.confirm_close_pos>=r["cisd"])&(q.disp_atr>=r["disp"])]
    if r["sweep"] is not None:q=q[q.sweep_atr>=r["sweep"]]
    parts.append(q)
z=pd.concat(parts).sort_values("fill_time").copy()

def stats(x,label):
    n=len(x)
    if not n:return dict(period=label,trades=0,wins=0,losses=0,wr=np.nan,expectancy_r=np.nan,max_dd_r=np.nan)
    wins=(x.outcome=="WIN").sum()
    eq=x.result_r.cumsum()
    return dict(period=label,trades=n,wins=wins,losses=n-wins,wr=wins/n*100,
                expectancy_r=x.result_r.mean(),max_dd_r=abs((eq-eq.cummax()).min()))

rows=[]
# Five chronological blocks for the combined four-session logic.
edges=np.linspace(0,len(z),6,dtype=int)
for i in range(5):
    rows.append(stats(z.iloc[edges[i]:edges[i+1]],f"chronological_20pct_{i+1}"))
for s,g in z.groupby("session"):
    rows.append(stats(g,f"session_{s}"))
rows.append(stats(z,"ALL"))
r=pd.DataFrame(rows)
r.to_csv(OUTFILE,index=False)

print("\n=== V4 FOUR-SESSION CANDIDATE VALIDATION — 4R ===")
for s,x in rules.items():
    print(f'{s}: CISD>={x["cisd"]} | DISP>={x["disp"]} | SWEEP>={x["sweep"]}')
print("\nChronological blocks:")
print(r[r.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSessions + combined:")
print(r[~r.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
