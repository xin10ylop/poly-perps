"""Delta-hedged backtest on daily strike ladders.
Decision at horizons H (hours before expiry). Model fair = lognormal with vol = market ATM implied vol at that time (smile-neutral),
fallback trailing realized vol. Trade if |mkt - fair| > thr: sell YES if rich, buy YES if cheap. Hedge delta with perps, rebalanced every 5 min
along Coinbase spot path; costs: binary taker fee 0.07*p(1-p) + 1c half-spread; perps taker 4bps on traded notional.
"""
import json, glob, re, sys, pandas as pd, numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
def load_cb(prod):
    c=json.load(open(f'data/cb/{prod}_1m.json')); d=pd.DataFrame(c,columns=['t','l','h','o','c','v']); d['t']=pd.to_datetime(d.t.astype('int64'),unit='s'); return d.set_index('t').sort_index().c.astype(float)
spot={'bitcoin':load_cb('BTC-USD')}
for a,p in (('ethereum','ETH-USD'),('solana','SOL-USD')):
    try: spot[a]=load_cb(p)
    except: pass
rvol={a:np.log(s).diff().rolling(7*1440,min_periods=1440).std() for a,s in spot.items()}
H=[float(x) for x in (sys.argv[1].split(',') if len(sys.argv)>1 else ['24','12','6','3','1'])]
THR=float(sys.argv[2]) if len(sys.argv)>2 else 0.05
MODEL=sys.argv[3] if len(sys.argv)>3 else 'iv'
def impvol(p,S,K,tau):
    # binary call price p = N(ln(S/K)/(sig sqrt tau)) -> sig
    if p<=0.02 or p>=0.98 or abs(np.log(S/K))<1e-6: return np.nan
    d=norm.ppf(p); 
    if d==0: return np.nan
    sig=np.log(S/K)/(d*np.sqrt(tau)); return sig if sig>0 else np.nan
events=[]
for f in sorted(glob.glob('data/ladders/*.json')):
    r=json.load(open(f)); a=r['asset']
    if a not in spot: continue
    e=r['event']; mkts=[]
    for m in e['markets']:
        if not m.get('closed'): continue
        mk=re.search(r'\$([\d,\.]+)',m['question']); 
        if not mk: continue
        K=float(mk.group(1).replace(',',''))
        try: out=json.loads(m['outcomePrices']); y=1 if float(out[0])>0.5 else 0
        except: continue
        h=r['hist'].get(m['id'],[])
        if not h: continue
        hd=pd.DataFrame(h); hd['t']=pd.to_datetime(hd.t,unit='s'); hd=hd.set_index('t').p.sort_index()
        T=pd.Timestamp(m['endDate']).tz_localize(None) if pd.Timestamp(m['endDate']).tzinfo is None else pd.Timestamp(m['endDate']).tz_convert(None)
        mkts.append((K,y,hd,T,m.get('orderPriceMinTickSize',0.01)))
    if mkts: events.append((a,r['date'],mkts))
print("events",len(events))
rows=[]; ivrows=[]
for a,date,mkts in events:
    s=spot[a]; rv=rvol[a]; T=mkts[0][3]
    for hrs in H:
        t0=T-pd.Timedelta(hours=hrs); tm=t0.floor('min')-pd.Timedelta(minutes=1)
        S0=s.asof(tm); 
        if np.isnan(S0): continue
        tau0=hrs*60
        # ATM implied vol from the two strikes bracketing spot
        ivs=[]
        for K,y,hd,_,tick in mkts:
            p=hd.asof(t0)
            if p is None or np.isnan(p): continue
            iv=impvol(p,S0,K,tau0)
            if not np.isnan(iv) and 0.2<abs(np.log(S0/K))/(iv*np.sqrt(tau0))<2.0: ivs.append(iv)
        sig_iv=np.nanmedian(ivs) if ivs else np.nan
        sig_rv=rv.asof(tm)
        sig=sig_iv if (MODEL=='iv' and not np.isnan(sig_iv)) else sig_rv
        ivrows.append(dict(asset=a,date=date,H=hrs,sig_iv=sig_iv,sig_rv=sig_rv,S0=S0,T=T,tm=tm))
        if np.isnan(sig) or sig<=0: continue
        # spot path for hedging: 5-min grid from t0 to T
        path=s[(s.index>=tm)&(s.index<=T)].resample('5min').last().ffill()
        if len(path)<2: continue
        for K,y,hd,_,tick in mkts:
            p=hd.asof(t0)
            if p is None or np.isnan(p): continue
            d2=np.log(S0/K)/(sig*np.sqrt(tau0)); fair=norm.cdf(d2)
            fair_rv=norm.cdf(np.log(S0/K)/(sig_rv*np.sqrt(tau0))) if sig_rv>0 else np.nan
            gap=p-fair
            if abs(gap)<THR: continue
            side=-1 if gap>0 else 1   # -1 sell YES, +1 buy YES ; per 1 share ($1 payout)
            half_spread=max(tick,0.01)/2
            fee=0.07*p*(1-p)
            entry=p+side*half_spread   # buy at p+hs, sell at p-hs
            binary_pnl=side*(y-entry)-fee
            # delta hedge: position in underlying = -side*delta*(1/S) shares... delta wrt S of binary = phi(d2)/(S sig sqrt(tau))
            hedge_pnl=0.0; cost=0.0; prev_units=0.0
            times=path.index; vals=path.values
            for i in range(len(times)-1):
                tau=max((T-times[i]).total_seconds()/60,1e-6); St=vals[i]
                d2t=np.log(St/K)/(sig*np.sqrt(tau)); delta=norm.pdf(d2t)/(St*sig*np.sqrt(tau))  # $ payoff sensitivity per $1 of S
                units=-side*delta   # hedge units of underlying
                trade=units-prev_units; cost+=abs(trade)*St*0.0004; prev_units=units
                hedge_pnl+=units*(vals[i+1]-vals[i])
            cost+=abs(prev_units)*vals[-1]*0.0004  # unwind
            rows.append(dict(asset=a,date=date,K=K,H=hrs,S0=S0,p=p,fair=fair,fair_rv=fair_rv,sig=sig,sig_rv=sig_rv,d2=d2,gap=gap,side=side,cost_share=(p if side>0 else 1-p),y=y,binary_pnl=binary_pnl,hedge_pnl=hedge_pnl,hedge_cost=cost,total=binary_pnl+hedge_pnl-cost,unhedged=binary_pnl))
df=pd.DataFrame(rows); df.to_parquet('data/ladder_hedged_bt.parquet')
iv=pd.DataFrame(ivrows)
def fwd_rv(r):
    s=spot[r.asset]; seg=s[(s.index>=r['tm'])&(s.index<=r['T'])]; lr=np.log(seg).diff().dropna(); return lr.std() if len(lr)>10 else np.nan
iv['rv_fwd']=iv.apply(fwd_rv,axis=1); iv.to_parquet('data/ladder_iv.parquet')
print("\n=== ATM implied vol (per sqrt-min) vs trailing RV vs forward realized RV, by horizon ===")
print(iv.groupby('H').agg(n=('sig_iv','count'),iv=('sig_iv','median'),rv_trail=('sig_rv','median'),rv_fwd=('rv_fwd','median'),iv_over_fwd=('sig_iv',lambda x: np.nan)).to_string(float_format=lambda x:f"{x:.6f}"))
iv['ratio']=iv.sig_iv/iv.rv_fwd; print("IV/forward-RV ratio: median %.3f, mean %.3f, frac>1 %.2f, n=%d"%(iv.ratio.median(),iv.ratio.mean(),(iv.ratio>1).mean(),iv.ratio.notna().sum()))
print(iv.groupby('asset').ratio.describe().to_string())
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
print("trades",len(df),"dates",df.date.nunique(), "thr",THR)
def summ(g): 
    n=len(g); return pd.Series(dict(n=n,mean_total=g.total.mean(),se=g.total.std()/np.sqrt(n),t=g.total.mean()/(g.total.std()/np.sqrt(n)) if n>1 else np.nan,mean_unhedged=g.unhedged.mean(),win=(g.total>0).mean(),avg_cost_per_share=g.cost_share.mean()))
print("\nBy horizon:"); print(df.groupby('H').apply(summ).to_string(float_format=lambda x:f"{x:.4f}"))
print("\nBy side (sell YES=-1 / buy YES=+1):"); print(df.groupby('side').apply(summ).to_string(float_format=lambda x:f"{x:.4f}"))
print("\nBy asset:"); print(df.groupby('asset').apply(summ).to_string(float_format=lambda x:f"{x:.4f}"))
df['db']=pd.cut(df.d2,[-9,-2,-1,-0.5,0,0.5,1,2,9]); print("\nBy moneyness d2 (of spot vs K in vol units; positive = K below spot):"); print(df.groupby('db',observed=True).apply(summ).to_string(float_format=lambda x:f"{x:.4f}"))
print("\nBy date (total per date, sum over trades):"); print(df.groupby('date').agg(n=('total','size'),total=('total','sum'),unhedged=('unhedged','sum')).to_string(float_format=lambda x:f"{x:.3f}"))
