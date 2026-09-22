import pandas as pd, numpy as np

print("=== V101 1M ICON BOT FORENSIC REBUILD ===")
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
ref=pd.concat([pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv"),pd.read_csv("data/v27_option2a_trades.csv")],ignore_index=True)
tc="time_ny" if "time_ny" in m.columns else next(c for c in m if "time" in c.lower())
m["_t"]=pd.to_datetime(m[tc],utc=True,errors="coerce"); m=m.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
# Locate usable reference time/direction columns without assuming old naming.
rt=next((c for c in ref if any(k in c.lower() for k in ["candidate_time","signal_time","entry_time","time_ny"]) ),None)
rd=next((c for c in ref if c.lower() in ["direction","side","dir"]),None)
if rt is None: raise ValueError("No reference timestamp column found: "+str(list(ref.columns)))
ref["_rt"]=pd.to_datetime(ref[rt],utc=True,errors="coerce")
print("Native 1m bars:",len(m),"Reference rows:",len(ref),"reference time:",rt,"direction:",rd)
# Pure 1m session candidate stream. No resampled 3m bars are used.
ny=m["_t"].dt.tz_convert("America/New_York"); mins=ny.dt.hour*60+ny.dt.minute
sess=np.select([
 (mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)
],["Asia","London","NYAM","NYPM"],default="")
m["session"]=sess
day=ny.dt.strftime("%Y-%m-%d")
# Asia belongs to session date beginning at 20:00.
asia=(m["session"]=="Asia")&(mins<1); sday=day.copy()
sday.loc[asia]=(ny.loc[asia]-pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
m["_sid"]=m["session"]+"_"+sday
rows=[]
for sid,g in m[m["session"]!=""].groupby("_sid",sort=False):
 hi=-np.inf; lo=np.inf
 for i,r in g.iterrows():
  nh=float(r.high)>hi; nl=float(r.low)<lo
  if nh:
   rows.append({"candidate_time":r["_t"],"session":r["session"],"direction":"SHORT","extreme":float(r.high),"bar_index":i})
   hi=float(r.high)
  if nl:
   rows.append({"candidate_time":r["_t"],"session":r["session"],"direction":"LONG","extreme":float(r.low),"bar_index":i})
   lo=float(r.low)
cand=pd.DataFrame(rows).sort_values("candidate_time").reset_index(drop=True)
print("Pure 1m session-extreme candidates:",len(cand))
# Match reference timestamps within a small window only for forensic labels; never becomes a predictor.
matches=[]
for _,r in ref.dropna(subset=["_rt"]).iterrows():
 q=cand[(cand.candidate_time>=r["_rt"]-pd.Timedelta(minutes=6))&(cand.candidate_time<=r["_rt"]+pd.Timedelta(minutes=6))]
 if rd and str(r[rd]).upper() in ["LONG","SHORT"]: q=q[q.direction==str(r[rd]).upper()]
 if len(q):
  j=(q.candidate_time-r["_rt"]).abs().idxmin(); matches.append(j)
cand["is_reference"]=False; cand.loc[list(set(matches)),"is_reference"]=True
print("Reference trades mapped to native 1m candidates:",cand.is_reference.sum(),"/",len(ref))
cand.to_parquet("data/v101_1m_candidate_reference_map.parquet",index=False)
print("Saved data/v101_1m_candidate_reference_map.parquet")
print("IMPORTANT: is_reference is FORENSIC LABEL ONLY and must never be used as a live feature.")
print("NEXT: V102 builds timestamp-locked 1m CISD + CHoCH + buyside/sellside sweep features for reference-vs-rejected analysis.")
