"""Daily 'X above K on date' ladders: calibration vs realized, by moneyness & horizon; strategy PnL (taker/maker) with optional perps delta hedge."""
import json, glob, pandas as pd, numpy as np, datetime as dt, sys
from scipy.stats import norm
def load_cb(prod):
    c=json.load(open(f'data/cb/{prod}_1m.json')); d=pd.DataFrame(c,columns=['t','l','h','o','c','v']); d['t']=pd.to_datetime(d.t.astype('int64'),unit='s'); return d.set_index('t').sort_index().c.astype(float)
spot={'bitcoin':load_cb('BTC-USD')}
for a,p in (('ethereum','ETH-USD'),('solana','SOL-USD')):
    try: spot[a]=load_cb(p)
    except Exception as e: print("no spot for",a)
def rvol(s):  # trailing 7-day realized vol per sqrt(minute)
    r=np.log(s).diff(); return r.rolling(7*1440,min_periods=1440).std()
vol={a:rvol(s) for a,s in spot.items()}
import re
rows=[]
for f in sorted(glob.glob('data/ladders/*.json')):
    r=json.load(open(f)); a=r['asset']
    if a not in spot: continue
    e=r['event']; s=spot[a]; v=vol[a]
    for m in e['markets']:
        if not m.get('closed'): continue
        mk=re.search(r'\$([\d,\.]+)',m['question']); 
        if not mk: continue
        K=float(mk.group(1).replace(',','')); 
        try: out=json.loads(m['outcomePrices']); y=1 if float(out[0])>0.5 else 0
        except: continue
        T=pd.Timestamp(m['endDate']).tz_convert(None) if pd.Timestamp(m['endDate']).tzinfo else pd.Timestamp(m['endDate'])
        # sanity: realized outcome vs spot at expiry (Coinbase proxy for Binance)
        sT=s.asof(T)
        h=r['hist'].get(m['id'],[])
        if not h: continue
        hd=pd.DataFrame(h); hd['t']=pd.to_datetime(hd.t,unit='s')
        for _,x in hd.iterrows():
            tau=(T-x.t).total_seconds()/60
            if tau<5: continue
            tm=x.t.floor('min')-pd.Timedelta(minutes=1)
            st=s.asof(tm); sg=v.asof(tm)
            if np.isnan(st) or np.isnan(sg) or sg==0: continue
            d2=np.log(st/K)/(sg*np.sqrt(tau)); fair=norm.cdf(d2)
            rows.append(dict(asset=a,date=r['date'],K=K,t=x.t,tau_h=tau/60,price=x.p,fair=fair,d2=d2,y=y,spot=st,sT=sT,vol=float(m.get('volumeNum') or 0)))
df=pd.DataFrame(rows); df.to_parquet('data/ladder_panel.parquet')
print("obs",len(df),"markets",df.groupby(['asset','date','K']).ngroups,"dates",df.date.nunique(), "assets", df.asset.unique())
# sanity check outcome vs coinbase spot at expiry
chk=df.groupby(['asset','date','K']).agg(y=('y','first'),sT=('sT','first')).reset_index(); chk['y_cb']=(chk.sT>chk.K).astype(int)
print("outcome agreement with Coinbase spot at expiry: %.3f"%(chk.y==chk.y_cb).mean())
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
df['hb']=pd.cut(df.tau_h,[0,1,3,6,12,24,48,96,200]); df['pb']=pd.cut(df.price,[0,.05,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,1.0])
print("\n=== Calibration by price bucket (all horizons) ==="); print(df.groupby('pb',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
print("\n=== Calibration by price bucket, horizon <= 24h ==="); d24=df[df.tau_h<=24]; print(d24.groupby('pb',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
print("\n=== Brier: market vs lognormal-realized-vol model by horizon ==="); df['bm']=(df.price-df.y)**2; df['bf']=(df.fair-df.y)**2
print(df.groupby('hb',observed=True).agg(n=('y','size'),brier_mkt=('bm','mean'),brier_fair=('bf','mean'),mean_gap=('price',lambda s: np.nan)).to_string(float_format=lambda x:f"{x:.4f}"))
df['gap']=df.price-df.fair; print("\nmean(price-fair) by horizon:"); print(df.groupby('hb',observed=True).gap.agg(['mean','std','size']).to_string(float_format=lambda x:f"{x:.4f}"))
print("\n=== By moneyness d2 bucket (horizon<=24h): market vs realized ==="); d24=df[df.tau_h<=24].copy(); d24['db']=pd.cut(d24.d2,[-9,-3,-2,-1.5,-1,-0.5,0,0.5,1,1.5,2,3,9])
print(d24.groupby('db',observed=True).agg(n=('y','size'),mkt=('price','mean'),fair=('fair','mean'),realized=('y','mean')).to_string(float_format=lambda x:f"{x:.3f}"))
