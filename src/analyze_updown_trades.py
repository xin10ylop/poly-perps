"""Trade-level analysis of 15m/4h up-down binaries: taker PnL, and maker-side backtest (post at fair +/- edge; filled if a print crosses)."""
import json, glob, pandas as pd, numpy as np, sys
from scipy.stats import norm
def load_cb(prod):
    c=json.load(open(f'data/cb/{prod}_1m.json')); d=pd.DataFrame(c,columns=['t','l','h','o','c','v']); d['t']=pd.to_datetime(d.t.astype('int64'),unit='s'); return d.set_index('t').sort_index().c.astype(float)
spot={'btc':load_cb('BTC-USD'),'eth':load_cb('ETH-USD')}
vol={a:np.log(s).diff().rolling(1440,min_periods=300).std() for a,s in spot.items()}
rows=[]
for f in sorted(glob.glob('data/updown_trades/*.json')):
    slug=f.split('/')[-1][:-5]; parts=slug.split('-'); asset=parts[0]; tf=parts[2]; T0=int(parts[3]); T1=T0+(900 if tf=='15m' else 14400)
    try: ev=json.load(open(f'data/updown/{slug}.json'))
    except: continue
    m=ev['event']['markets'][0]
    if not m.get('closed'): continue
    try: out=json.loads(m['outcomePrices']); up=1 if float(out[0])>0.5 else 0
    except: continue
    tr=json.load(open(f))
    if not tr: continue
    s=spot[asset]; v=vol[asset]; t0=pd.Timestamp(T0,unit='s'); p0=s.asof(t0-pd.Timedelta(minutes=1))
    for x in tr:
        ts=x['timestamp']
        if ts<T0 or ts>=T1: continue
        t=pd.Timestamp(ts,unit='s'); tm=t.floor('min')-pd.Timedelta(minutes=1); st=s.asof(tm); sg=v.asof(tm)
        if np.isnan(st) or np.isnan(sg): continue
        rem=(T1-ts)/60.0
        # price of the UP share for this trade
        pu=x['price'] if x['outcome']=='Up' else 1-x['price']
        # taker direction in terms of UP exposure: BUY Up or SELL Down => long Up
        long_up = (x['side']=='BUY')==(x['outcome']=='Up')
        fair=norm.cdf(np.log(st/p0)/(sg*np.sqrt(rem)))
        rows.append(dict(slug=slug,asset=asset,tf=tf,T0=T0,t=t,rem=rem,pu=pu,fair=fair,long_up=long_up,size=x['size'],usd=x['size']*x['price'],up=up,wallet=x['proxyWallet']))
df=pd.DataFrame(rows); df.to_parquet('data/updown_trades_panel.parquet')
print("trades in-window",len(df),"markets",df.slug.nunique(),"days",df.t.dt.date.nunique()); print(df.groupby('tf').size())
# taker PnL per share: long_up -> up - pu ; else (1-up) - (1-pu); fee 0.07*pu*(1-pu)
df['fee']=0.07*df.pu*(1-df.pu); df['taker_pnl']=np.where(df.long_up, df.up-df.pu, (1-df.up)-(1-df.pu))-df.fee
df['taker_pnl_usd']=df.taker_pnl*df.size
print("\nTaker aggregate PnL (USD, after fees): %.0f on %.0f USD notional (%.2f%%); n=%d"%(df.taker_pnl_usd.sum(),df.usd.sum(),df.taker_pnl_usd.sum()/df.usd.sum()*100,len(df)))
df['rb']=pd.cut(df.rem,[0,0.5,1,2,5,10,15,60,240]); 
print(df.groupby(['tf','rb'],observed=True).agg(n=('taker_pnl','size'),usd=('usd','sum'),taker_pnl_usd=('taker_pnl_usd','sum'),mean_pnl_share=('taker_pnl','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
# Maker backtest: I quote UP bid at fair-e and UP ask at fair+e (size 1 share each print); filled when a taker prints at <= my bid (they sold Up cheaper) or >= my ask
for e in (0.03,0.05,0.08,0.12):
    d=df[(df.rem>0.75)]
    buy=d[(~d.long_up)&(d.pu<=d.fair-e)]   # taker sold Up at/below my bid -> I buy Up at my bid price = fair-e (conservative: at pu)
    sell=d[(d.long_up)&(d.pu>=d.fair+e)]
    pnl_b=(buy.up-buy.pu); pnl_s=((1-sell.up)-(1-sell.pu))
    # one fill per market per side max
    b1=buy.groupby('slug').first(); s1=sell.groupby('slug').first(); pb=(b1.up-b1.pu); ps=((1-s1.up)-(1-s1.pu))
    allp=pd.concat([pb,ps])
    print(f"edge {e:.2f}: fills buyUp={len(buy)} sellUp={len(sell)} | per-market-first-fill: n={len(allp)} mean pnl/share={allp.mean():.4f} se={allp.std()/np.sqrt(len(allp)):.4f} win={ (allp>0).mean():.2f} | buy side {pb.mean():.3f} (n={len(pb)}) sell side {ps.mean():.3f} (n={len(ps)})")
# by day for edge 0.05
e=0.05; d=df[df.rem>0.75]; buy=d[(~d.long_up)&(d.pu<=d.fair-e)]; sell=d[(d.long_up)&(d.pu>=d.fair+e)]
b1=buy.groupby('slug').first(); s1=sell.groupby('slug').first(); b1['pnl']=b1.up-b1.pu; s1['pnl']=(1-s1.up)-(1-s1.pu)
allp=pd.concat([b1,s1]); allp['day']=allp.t.dt.date
print("\nedge 0.05 by day:"); print(allp.groupby('day').agg(n=('pnl','size'),pnl=('pnl','mean'),sum=('pnl','sum')).to_string(float_format=lambda x:f"{x:.3f}"))
print("\nedge 0.05 by tf:"); print(allp.groupby('tf').agg(n=('pnl','size'),pnl=('pnl','mean'),se=('pnl',lambda s:s.std()/np.sqrt(len(s)))).to_string(float_format=lambda x:f"{x:.4f}"))
print("\nedge 0.05 by remaining-time bucket:"); print(allp.groupby('rb',observed=True).agg(n=('pnl','size'),pnl=('pnl','mean'),se=('pnl',lambda s:s.std()/np.sqrt(len(s)))).to_string(float_format=lambda x:f"{x:.4f}"))
