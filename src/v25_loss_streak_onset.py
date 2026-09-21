import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int)
# Analyze 3+ loss runs: what happens immediately before the first loss?
streaks=[];i=0
while i<len(q):
 if q.loc[i,"win"]==0:
  j=i
  while j<len(q) and q.loc[j,"win"]==0:j+=1
  if j-i>=3: streaks.append((i,j-1))
  i=j
 else:i+=1
rows=[]
for a,b in streaks:
 first=q.loc[a]
 prev=q.loc[a-1] if a>0 else None
 rows.append({
  "start":first.candidate_time,"length":b-a+1,"session":first.get("session",""),
  "first_score":first.score,"first_reclaim":first.early_reclaim_atr,
  "first_reclaim_wick":first.reclaim_x_wick,"first_close_reclaim":first.close_x_reclaim,
  "first_quality_balance":first.quality_balance,
  "prev_was_loss": (prev.win==0) if prev is not None else False,
  "prev_score": prev.score if prev is not None else np.nan,
  "gap_min": (first.candidate_time-prev.candidate_time).total_seconds()/60 if prev is not None else np.nan})
s=pd.DataFrame(rows)
print("=== V25 LOSS-STREAK ONSET FORENSICS ===")
print(f"3+ loss runs: {len(s)} | losses inside runs: {sum(b-a+1 for a,b in streaks)}")
print("\nFIRST LOSS OF EACH BAD RUN")
for c in ["first_score","first_reclaim","first_reclaim_wick","first_close_reclaim","first_quality_balance","gap_min"]:
 print(f"{c:22s} median {s[c].median():.3f} | mean {s[c].mean():.3f}")
# Compare first losses in streaks to isolated/short-run losses.
bad_first=set(a for a,b in streaks)
other_loss=q[(q.win==0)&(~q.index.isin(bad_first))]
firsts=q.loc[list(bad_first)]
print("\nBAD-RUN FIRST LOSS vs OTHER LOSSES")
for c in ["score","early_reclaim_atr","reclaim_x_wick","close_x_reclaim","quality_balance","rejection_quality","impulse_to_reclaim","mins_into_session"]:
 sd=q[c].std();eff=(firsts[c].mean()-other_loss[c].mean())/sd if sd else 0
 print(f"{c:22s} other {other_loss[c].mean():.3f} | run-start {firsts[c].mean():.3f} | effect {eff:+.3f}")
s.to_csv("data/v25_loss_streak_onsets.csv",index=False)
