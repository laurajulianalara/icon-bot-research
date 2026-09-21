import pandas as pd, numpy as np
q=pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# V12 interactions
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
q["close_x_reclaim"]=q.m2_close_pos*q.early_reclaim_atr
q["sweep_minus_reclaim"]=q.sweep_atr-q.early_reclaim_atr
q["impulse_minus_reclaim"]=q.reversal_impulse-q.early_reclaim_atr
q["quality_balance"]=q.rejection_quality*q.impulse_to_reclaim/(1+q.reclaim_to_sweep)
# V14 weighted causal quality score
parts=[]
for col,hi,w in [("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]:
 r=q[col].rank(pct=True); comp=r if hi else 1-r
 parts += [comp]*w
q["score"]=pd.concat(parts,axis=1).mean(axis=1)
# Lock V14 best frequency-quality row: drop bottom 7%, then hard max 6/day
thr=q.score.quantile(.07); z=q[q.score>=thr].copy()
z["date_et"]=z.candidate_time.dt.tz_convert("America/New_York").dt.date
z["trade_num_day"]=z.groupby("date_et").cumcount()+1
z=z[z.trade_num_day<=6].copy()
# Add sequential causal context
z["prior_losses_day"]=z.groupby("date_et").win.transform(lambda s:(1-s).cumsum().shift(fill_value=0))
z["prior_wins_day"]=z.groupby("date_et").win.transform(lambda s:s.cumsum().shift(fill_value=0))
z["prior_r_day"]=z.groupby("date_et").r.transform(lambda s:s.cumsum().shift(fill_value=0))
# same-session attempt
z["same_session_num"]=z.groupby(["date_et","session"]).cumcount()+1
# previous result streak (global chronological, causal)
loss_streak=[];cur=0
for w in z.win:
 loss_streak.append(cur);cur=0 if w else cur+1
z["prior_loss_streak"]=loss_streak
print("=== V15 OPTION 2 LOSS ROOT-CAUSE FORENSICS ===")
print(f"Population: {len(z)} | WR {100*z.win.mean():.2f}% | active/day {len(z)/z.date_et.nunique():.2f}")
for col in ["score","early_reclaim_atr","wick_percent","m2_close_pos","reversal_impulse","reclaim_x_wick","close_x_reclaim","sweep_minus_reclaim","impulse_minus_reclaim","quality_balance","trade_num_day","prior_losses_day","prior_wins_day","prior_r_day","same_session_num","prior_loss_streak"]:
 a=z[z.win==1][col];b=z[z.win==0][col];sd=z[col].std();effect=(b.mean()-a.mean())/sd if sd else 0
 print(f"{col:24s} WIN {a.mean():8.3f} LOSS {b.mean():8.3f} effect(loss-win) {effect:7.3f}")
print("\nWR by prior losses today:")
print(z.groupby("prior_losses_day").win.agg(["count","mean"]).assign(mean=lambda x:x["mean"]*100).round(2).to_string())
print("\nWR by trade number today:")
print(z.groupby("trade_num_day").win.agg(["count","mean"]).assign(mean=lambda x:x["mean"]*100).round(2).to_string())
print("\nWR by prior loss streak:")
print(z.groupby("prior_loss_streak").win.agg(["count","mean"]).assign(mean=lambda x:x["mean"]*100).round(2).to_string())
print("\nWR by session:")
print(z.groupby("session").win.agg(["count","mean"]).assign(mean=lambda x:x["mean"]*100).round(2).to_string())
z.to_csv("data/v15_option2_loss_forensics.csv",index=False)
print("\nSaved: data/v15_option2_loss_forensics.csv")
