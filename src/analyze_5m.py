"""5-minute up/down markets: taker economics, cheap-tail pocket, wallet consistency (BTC/ETH/SOL/XRP)."""
import json, glob, pandas as pd, numpy as np
rows=[]
for f in glob.glob('data/updown5m_trades/*.json'):
    slug=f.split('/')[-1][:-5]; asset=slug.split('-')[0]; T0=int(slug.split('-')[3]); T1=T0+300
    try: ev=json.load(open(f'data/updown5m/{slug}.json'))
    except: continue
    m=ev['event']['markets'][0]
    if not m.get('closed'): continue
    try: out=json.loads(m['outcomePrices']); up=1 if float(out[0])>0.5 else 0
    except: continue
    if float(out[0]) not in (0.0,1.0) and float(out[1]) not in (0.0,1.0): continue
    for x in json.load(open(f)):
        pu=x['price'] if x['outcome']=='Up' else 1-x['price']; lu=(x['side']=='BUY')==(x['outcome']=='Up')
        rows.append((slug,asset,T0,T1,x['timestamp'],pu,lu,x['size'],x['proxyWallet'],up))
df=pd.DataFrame(rows,columns=['slug','asset','T0','T1','ts','pu','long_up','size','wallet','up'])
df['fee']=0.07*df.pu*(1-df.pu); df['cost']=np.where(df.long_up,df.pu,1-df.pu); df['usd']=df['size']*df.cost; df['fee_usd']=df.fee*df['size']
df['pnl']=(np.where(df.long_up,df.up-df.pu,(1-df.up)-(1-df.pu))-df.fee)*df['size']; df['win']=np.where(df.long_up,df.up,1-df.up)
df['day']=pd.to_datetime(df.ts,unit='s').dt.date; df['rem_s']=df.T1-df.ts; df=df[(df.rem_s>=0)&(df.rem_s<=300)]
df.to_parquet('data/updown5m_trades_all.parquet')
pd.set_option('display.width',220)
print("5m: trades %d markets %d days %d wallets %d notional $%.1fM"%(len(df),df.slug.nunique(),df.day.nunique(),df.wallet.nunique(),df.usd.sum()/1e6))
print("taker pnl after fees $%.0f (%.2f%%), fees $%.0f (%.2f%% of notional), pre-fee $%.0f (%.2f%%)"%(df.pnl.sum(),100*df.pnl.sum()/df.usd.sum(),df.fee_usd.sum(),100*df.fee_usd.sum()/df.usd.sum(),df.pnl.sum()+df.fee_usd.sum(),100*(df.pnl.sum()+df.fee_usd.sum())/df.usd.sum()))
print("\nby asset:"); print(df.groupby('asset').agg(n=('pnl','size'),mkts=('slug','nunique'),usd=('usd','sum'),pnl=('pnl','sum'),fees=('fee_usd','sum')).assign(roi=lambda x:x.pnl/x.usd,prefee=lambda x:(x.pnl+x.fees)/x.usd).to_string(float_format=lambda x:f"{x:,.3f}"))
d=df.groupby('day').agg(usd=('usd','sum'),pnl=('pnl','sum'),fees=('fee_usd','sum')); print("\nper day: notional $%.0f, taker pnl $%.0f, fees $%.0f, maker gross $%.0f"%(d.usd.mean(),d.pnl.mean(),d.fees.mean(),-(d.pnl+d.fees).mean()))
df['rb']=pd.cut(df.rem_s,[0,15,30,60,90,120,180,240,300]); df['cb']=pd.cut(df.cost,[0,.05,.1,.2,.35,.5,.65,.8,.9,.95,1])
print("\nby seconds remaining:"); print(df.groupby('rb',observed=True).agg(n=('pnl','size'),usd=('usd','sum'),pnl=('pnl','sum')).assign(roi=lambda x:x.pnl/x.usd).to_string(float_format=lambda x:f"{x:,.3f}"))
print("\nby cost bucket (all times): n, cost, realized win, roi"); print(df.groupby('cb',observed=True).agg(n=('pnl','size'),cost=('cost','mean'),win=('win','mean'),usd=('usd','sum'),pnl=('pnl','sum')).assign(roi=lambda x:x.pnl/x.usd).to_string(float_format=lambda x:f"{x:,.3f}"))
late=df[df.rem_s<=60]; late=late.assign(cb=pd.cut(late.cost,[0,.02,.05,.1,.2,.5,.8,.9,.95,1]))
print("\nlast 60s by cost bucket:"); print(late.groupby('cb',observed=True).agg(n=('pnl','size'),cost=('cost','mean'),win=('win','mean'),usd=('usd','sum'),pnl=('pnl','sum')).assign(roi=lambda x:x.pnl/x.usd).to_string(float_format=lambda x:f"{x:,.3f}"))
l=df[(df.rem_s<=90)&(df.cost<=0.10)]; pm=l.groupby('slug').agg(usd=('usd','sum'),pnl=('pnl','sum'),won=('win','max'),cost=('cost','mean'))
rng=np.random.default_rng(0); rois=[(lambda s:s.pnl.sum()/s.usd.sum())(pm.sample(len(pm),replace=True)) for _ in range(2000)]
print("\ncheap-side (<=10c) last 90s: markets %d flips %d (%.3f) avg cost %.3f notional $%.0f pnl $%.0f (%.0f/day) ROI %.3f boot5-95 %.3f..%.3f"%(len(pm),pm.won.sum(),pm.won.mean(),pm.cost.mean(),pm.usd.sum(),pm.pnl.sum(),pm.pnl.sum()/df.day.nunique(),pm.pnl.sum()/pm.usd.sum(),np.percentile(rois,5),np.percentile(rois,95)))
h=df[(df.rem_s<=60)&(df.cost>=0.90)]; pm2=h.groupby('slug').agg(fav_won=('win','max'),cost=('cost','mean')); print("favourite >=90c in last 60s: markets %d lost %d (%.3f) implied %.3f"%(len(pm2),(pm2.fav_won==0).sum(),(pm2.fav_won==0).mean(),1-pm2.cost.mean()))
w=df.groupby('wallet').agg(n=('pnl','size'),usd=('usd','sum'),pnl=('pnl','sum'),days=('day','nunique'),mkts=('slug','nunique'))
for lo,hi in ((1,20),(20,200),(200,2000),(2000,10**9)):
    s=w[(w.n>=lo)&(w.n<hi)]; print(f"wallets {lo}-{hi} trades: {len(s)} | notional {s.usd.sum():,.0f} | pnl {s.pnl.sum():,.0f} ({100*s.pnl.sum()/max(s.usd.sum(),1):.2f}%)")
top=w[w.days>=4].sort_values('pnl',ascending=False).head(15); daily=df[df.wallet.isin(top.index)].groupby(['wallet','day']).agg(pnl=('pnl','sum'),usd=('usd','sum')).reset_index()
cons=daily.groupby('wallet').agg(days=('pnl','size'),pnl_total=('pnl','sum'),usd_day=('usd','mean'),pnl_day=('pnl','mean'),sd=('pnl','std'),frac_pos=('pnl',lambda s:(s>0).mean())); cons['sharpe']=cons.pnl_day/cons.sd; cons['roi_day_pct']=100*cons.pnl_day/cons.usd_day
print("\nTop wallets (>=4 active days) consistency:"); print(cons.sort_values('pnl_total',ascending=False).to_string(float_format=lambda x:f"{x:,.2f}"))
