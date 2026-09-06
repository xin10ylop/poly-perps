"""Touch (barrier) markets 'Will X hit $K in <period>': calibration of market price vs realized, and vs reflection-principle fair using Coinbase path."""
import json, glob, re, pandas as pd, numpy as np
from scipy.stats import norm
def load_cb(prod):
    c=json.load(open(f'data/cb/{prod}_1m.json')); d=pd.DataFrame(c,columns=['t','l','h','o','c','v']); d['t']=pd.to_datetime(d.t.astype('int64'),unit='s'); return d.set_index('t').sort_index()[['l','h','c']].astype(float)
spot={'bitcoin':load_cb('BTC-USD'),'ethereum':load_cb('ETH-USD'),'solana':load_cb('SOL-USD')}
rv={a:np.log(s.c).diff().rolling(7*1440,min_periods=1440).std() for a,s in spot.items()}
rows=[]
for f in sorted(glob.glob('data/touch/*.json')):
    r=json.load(open(f)); a=r['asset']; e=r['event']
    if a not in spot: continue
    s=spot[a]
    for m in e['markets']:
        if not m.get('closed'): continue
        q=m['question']; mk=re.search(r'\$([\d,\.]+)',q)
        if not mk: continue
        K=float(mk.group(1).replace(',','')); 
        try: out=json.loads(m['outcomePrices']); y=1 if float(out[0])>0.5 else 0
        except: continue
        h=r['hist'].get(m['id'],[])
        if not h: continue
        T=pd.Timestamp(m['endDate']); T=T.tz_convert(None) if T.tzinfo else T
        T0=pd.Timestamp(m['startDate']); T0=T0.tz_convert(None) if T0.tzinfo else T0
        # direction: 'reach'/'hit' above or below current? infer from spot at start: K> S0 -> up-touch else down-touch (both possible in these ladders; 'dip to' markets are down)
        hd=pd.DataFrame(h); hd['t']=pd.to_datetime(hd.t,unit='s')
        seg=s[(s.index>=T0)&(s.index<=T)]
        if seg.empty: continue
        S0=seg.c.iloc[0]; up=K>S0
        touched=(seg.h.max()>=K) if up else (seg.l.min()<=K)
        for _,x in hd.iloc[::max(1,len(hd)//60)].iterrows():   # ~60 points per market
            tau=(T-x.t).total_seconds()/60
            if tau<60: continue
            tm=x.t.floor('min'); St=s.c.asof(tm); sg=rv[a].asof(tm)
            if np.isnan(St) or np.isnan(sg): continue
            # already touched by time t?
            past=s[(s.index>=T0)&(s.index<=tm)]
            already=(past.h.max()>=K) if up else (past.l.min()<=K)
            if already: fair=1.0
            else:
                d=abs(np.log(K/St))/(sg*np.sqrt(tau)); fair=2*(1-norm.cdf(d))   # reflection principle, driftless
            rows.append(dict(asset=a,kind=r['kind'],slug=r['slug'],K=K,up=up,t=x.t,tau_d=tau/1440,price=x.p,fair=fair,already=already,y=y,touched_cb=int(touched),dist_sig=abs(np.log(K/St))/(sg*np.sqrt(tau)) if not already else 0))
df=pd.DataFrame(rows); df.to_parquet('data/touch_panel.parquet')
print("obs",len(df),"markets",df.slug.nunique(),"kinds",df.kind.value_counts().to_dict())
chk=df.groupby('slug').agg(y=('y','first'),t=('touched_cb','first')); print("outcome agreement with Coinbase path: %.3f (n=%d)"%((chk.y==chk.t).mean(),len(chk)))
pd.set_option('display.width',250); pd.set_option('display.max_rows',100)
d=df[~df.already]
d['pb']=pd.cut(d.price,[0,.05,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,1.0])
print("\n=== Not-yet-touched: calibration by market price bucket ==="); print(d.groupby('pb',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
d['db']=pd.cut(d.dist_sig,[0,0.5,1,1.5,2,3,5,20])
print("\n=== by distance (in vol units) ==="); print(d.groupby('db',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
d['tb']=pd.cut(d.tau_d,[0,1,3,7,14,31,60])
print("\n=== by days to expiry ==="); print(d.groupby('tb',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
print("\n=== by kind & up/down ==="); print(d.groupby(['kind','up']).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
d['bm']=(d.price-d.y)**2; d['bf']=(d.fair-d.y)**2; print("\nBrier market %.4f vs reflection-model %.4f"%(d.bm.mean(),d.bf.mean()))
# simple strategy: buy YES when price < fair - 0.1 and price<0.5 ; sell YES when price > fair + 0.1. per-market one trade (first signal), hold to expiry, taker fee 0.07 p(1-p) + 1c
sig=d[(d.fair-d.price>0.10)]; s1=sig.groupby('slug').first(); pnl_b=s1.y-(s1.price+0.01)-0.07*s1.price*(1-s1.price)
sig2=d[(d.price-d.fair>0.10)]; s2=sig2.groupby('slug').first(); pnl_s=(1-s2.y)-((1-s2.price)+0.01)-0.07*s2.price*(1-s2.price)
print(f"\nBUY cheap touches (fair-mkt>0.10): n={len(s1)} mean pnl/share={pnl_b.mean():.3f} se={pnl_b.std()/np.sqrt(max(len(s1),1)):.3f} avg price {s1.price.mean():.3f} win {(pnl_b>0).mean():.2f}")
print(f"SELL rich touches (mkt-fair>0.10): n={len(s2)} mean pnl/share={pnl_s.mean():.3f} se={pnl_s.std()/np.sqrt(max(len(s2),1)):.3f} avg price {s2.price.mean():.3f} win {(pnl_s>0).mean():.2f}")
