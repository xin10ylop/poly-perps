"""Far-quote liquidity provision on PM perps: rest bid/ask at +-X bps from previous-minute mark (re-centered each minute).
Fill if a public trade prints at/beyond our price within that minute (conservative: fill size = min(our size, printed size beyond)).
Exit: at mark k minutes later (taker fee 4bps) . Entry maker fee 1.25bps. Exclude scheduled macro minutes optionally."""
import json, glob, sys, pandas as pd, numpy as np
ins={i['instrument_id']:i for i in json.load(open('data/raw/instruments.json'))}
X=float(sys.argv[1]) if len(sys.argv)>1 else 25; K=int(sys.argv[2]) if len(sys.argv)>2 else 15; SIZE=float(sys.argv[3]) if len(sys.argv)>3 else 10000
EXCL=set()  # (hour,minute) UTC scheduled
for h,mn in ((12,30),(12,31),(14,0),(14,1),(20,0),(20,1),(13,30),(13,31),(22,0),(22,1),(22,2),(18,0),(18,1)): EXCL.add((h,mn))
pd.set_option('display.width',250)
rows=[]
for f in sorted(glob.glob('data/pm/trades_*.json')):
    iid=int(f.split('_')[-1].split('.')[0]); sym=ins[iid]['symbol']
    tr=pd.DataFrame(json.load(open(f))); 
    if tr.empty: continue
    tr['t']=pd.to_datetime(tr.timestamp.astype('int64'),unit='ms'); tr['p']=tr.price.astype(float); tr['q']=tr.quantity.astype(float); tr['usd']=tr.p*tr.q
    m=json.load(open(f'data/pm/mark1m_{iid}.json')); mk=pd.DataFrame(m,columns=['ts','mark']); mk['t']=pd.to_datetime(mk.ts.astype('int64'),unit='ms'); mk['mark']=mk.mark.astype(float)
    mk=mk.drop_duplicates('t').set_index('t').mark.sort_index().resample('1min').last().ffill()
    tr['mn']=tr.t.dt.floor('min'); tr['ref']=mk.reindex(tr.mn-pd.Timedelta(minutes=1)).values
    tr=tr.dropna(subset=['ref']); tr['dev']=(tr.p/tr.ref-1)*1e4
    bid=tr.ref*(1-X/1e4); ask=tr.ref*(1+X/1e4)
    fb=tr[tr.p<=bid].copy(); fb['side']=+1; fb['fillp']=bid[tr.p<=bid]
    fa=tr[tr.p>=ask].copy(); fa['side']=-1; fa['fillp']=ask[tr.p>=ask]
    fills=pd.concat([fb,fa])
    if fills.empty: rows.append(dict(sym=sym,fills=0)); continue
    # one fill per minute per side, size = min(SIZE, sum usd printed beyond in that minute)
    g=fills.groupby(['mn','side']).agg(fillp=('fillp','first'),usd_beyond=('usd','sum'),ref=('ref','first')).reset_index()
    g['size_usd']=np.minimum(SIZE,g.usd_beyond)
    g['exit']=mk.reindex(g.mn+pd.Timedelta(minutes=K)).values
    g=g.dropna(subset=['exit'])
    g['gross_bps']=g.side*(g.exit/g.fillp-1)*1e4; g['net_bps']=g.gross_bps-1.25-4.0
    g['pnl_usd']=g.net_bps/1e4*g.size_usd
    g['excl']=[(t.hour,t.minute) in EXCL for t in g.mn]
    days=(tr.t.max()-tr.t.min()).total_seconds()/86400
    for lab,gg in (('all',g),('ex-macro',g[~g.excl])):
        rows.append(dict(sym=sym,set=lab,days=days,fills=len(gg),fills_per_day=len(gg)/days,avg_fill_usd=gg.size_usd.mean(),gross_bps=gg.gross_bps.mean(),net_bps=gg.net_bps.mean(),usdw_net_bps=np.average(gg.net_bps,weights=gg.size_usd) if len(gg) else np.nan,win=(gg.net_bps>0).mean(),pnl_usd_total=gg.pnl_usd.sum(),pnl_usd_day=gg.pnl_usd.sum()/days,worst=gg.pnl_usd.min(),std_bps=gg.net_bps.std()))
df=pd.DataFrame(rows); print(f"X={X}bps K={K}min SIZE={SIZE}"); print(df.to_string(index=False,float_format=lambda x:f"{x:,.1f}"))
