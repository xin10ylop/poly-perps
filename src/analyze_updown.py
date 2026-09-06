"""15m/4h BTC & ETH up/down binaries: calibration and mispricing vs a fair-value model using PM perps 1m closes as spot reference."""
import json, glob, pandas as pd, numpy as np
from scipy.stats import norm
# spot reference: PM perps klines (1m closes), BTC iid=6, ETH iid=7
def load_pm(iid):
    k=json.load(open(f'data/pm/klines1m_{iid}.json'))
    d=pd.DataFrame(k,columns=['ts','o','h','l','c','v','n']); d['t']=pd.to_datetime(d.ts.astype('int64'),unit='ms'); d=d.drop_duplicates('t').set_index('t').sort_index()
    return d.c.astype(float).resample('1min').last().ffill()
spot={'btc':load_pm(6),'eth':load_pm(7)}
# realized 1-min vol (rolling 24h) for the fair model
def rv(s): 
    r=np.log(s).diff(); return r.rolling(1440,min_periods=300).std()
vol={a:rv(s) for a,s in spot.items()}
rows=[]
for f in sorted(glob.glob('data/updown/*.json')):
    r=json.load(open(f)); e=r['event']; m=e['markets'][0]
    if not m.get('closed'): continue
    try: out=json.loads(m['outcomePrices']); up=1 if float(out[0])>0.5 else 0
    except: continue
    T0=r['t']; T1=T0+(900 if r['tf']=='15m' else 14400)
    h=pd.DataFrame(r['hist'])
    if h.empty: continue
    h['t']=pd.to_datetime(h.t,unit='s'); h=h[(h.t>=pd.Timestamp(T0,unit='s'))&(h.t<pd.Timestamp(T1,unit='s'))]
    s=spot[r['asset']]; v=vol[r['asset']]
    p0=s.asof(pd.Timestamp(T0,unit='s'))
    for _,x in h.iterrows():
        tm=x.t.floor('min'); 
        if tm not in s.index: continue
        st=s.loc[tm]; sig=v.loc[tm] if tm in v.index else np.nan
        rem=(T1-x.t.timestamp())/60.0
        if rem<=0 or np.isnan(sig) or p0 is None: continue
        z=np.log(st/p0)/(sig*np.sqrt(rem)); fair=norm.cdf(z)
        rows.append(dict(slug=r['slug'],asset=r['asset'],tf=r['tf'],T0=T0,t=x.t,rem_min=rem,price=x.p,fair=fair,move_bps=(st/p0-1)*1e4,up=up,vol=float(m.get('volumeNum') or 0)))
df=pd.DataFrame(rows); df.to_parquet('data/updown_panel.parquet')
print("obs",len(df),"markets",df.slug.nunique()); print(df.groupby(['asset','tf']).slug.nunique())
pd.set_option('display.width',220)
# 1) calibration of market price by bucket and by time remaining
df['pb']=pd.cut(df.price,[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]); df['rb']=pd.cut(df.rem_min,[0,1,2,5,10,15,60,240])
cal=df.groupby('pb',observed=True).agg(n=('up','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('up','mean'))
print("\nCalibration by market price bucket (all obs):"); print(cal.to_string(float_format=lambda x:f"{x:.3f}"))
cal2=df.groupby('rb',observed=True).agg(n=('up','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('up','mean'),mae_mkt=('price',lambda s: np.nan),)
df['err_mkt']=(df.price-df.up).abs(); df['err_fair']=(df.fair-df.up).abs(); df['brier_mkt']=(df.price-df.up)**2; df['brier_fair']=(df.fair-df.up)**2
print("\nBrier by remaining-time bucket: market vs fair model"); print(df.groupby('rb',observed=True).agg(n=('up','size'),brier_mkt=('brier_mkt','mean'),brier_fair=('brier_fair','mean'),mean_price=('price','mean'),realized=('up','mean')).to_string(float_format=lambda x:f"{x:.4f}"))
# 2) Systematic bias: at window start (rem >= tf-1min), is Up over/underpriced?
for tf,full in (('15m',15),('4h',240)):
    d=df[(df.tf==tf)&(df.rem_min>full-2)]
    print(f"\n{tf} near window start: n={len(d)} mean Up price={d.price.mean():.3f} realized Up={d.up.mean():.3f}")
# 3) Mispricing trade: mkt vs fair gap; taker with fee 0.07*p*(1-p); evaluate PnL per $1 of shares
df['gap']=df.price-df.fair
for thr in [0.1,0.15,0.2,0.3]:
    sel=df[(df.gap.abs()>thr)&(df.rem_min>0.5)]
    # buy Up if fair>price else buy Down at (1-price)
    buyup=sel.gap<0
    cost=np.where(buyup, sel.price, 1-sel.price); fee=0.07*sel.price*(1-sel.price)
    payoff=np.where(buyup, sel.up, 1-sel.up)
    pnl=(payoff-cost-fee); pnl_nofee=(payoff-cost)
    print(f"gap>{thr}: n={len(sel)} markets={sel.slug.nunique()} avg cost={cost.mean():.3f} PnL/share taker={pnl.mean():.4f} nofee={pnl_nofee.mean():.4f} ROI on cost={pnl.sum()/cost.sum():.3f}  by tf: {sel.groupby('tf').size().to_dict()}")
