"""Merge PM 1m klines with HL 1m candles per instrument into one parquet panel with session labels."""
import json, glob, pandas as pd, numpy as np
ins={i['instrument_id']:i for i in json.load(open('data/raw/instruments.json'))}
mp=json.load(open('data/hl/pm_to_hl_map.json'))
frames=[]
for iid,i in ins.items():
    b=i['base_asset']; sym=i['symbol']; cat=i['category']
    try: k=json.load(open(f'data/pm/klines1m_{iid}.json'))
    except FileNotFoundError: continue
    pm=pd.DataFrame(k,columns=['ts','o','h','l','c','v','n']).astype({'ts':'int64','o':float,'h':float,'l':float,'c':float,'v':float,'n':int})
    pm['t']=pd.to_datetime(pm.ts,unit='ms'); pm=pm.drop_duplicates('ts').set_index('t').sort_index()
    pm.columns=['pm_ts','pm_o','pm_h','pm_l','pm_c','pm_v','pm_n']
    hlc=None
    try:
        h=json.load(open(f'data/hl/candles1m_{b}.json'))
        if h:
            hl=pd.DataFrame(h); hl['t']=pd.to_datetime(hl.t.astype('int64'),unit='ms')
            hl=hl.drop_duplicates('t').set_index('t').sort_index()[['o','h','l','c','v','n']].astype(float)
            hl.columns=['hl_o','hl_h','hl_l','hl_c','hl_v','hl_n']; hlc=hl
    except FileNotFoundError: pass
    df=pm if hlc is None else pm.join(hlc,how='outer')
    df['iid']=iid; df['sym']=sym; df['cat']=cat; df['hl']=mp.get(b)
    frames.append(df.reset_index())
panel=pd.concat(frames,ignore_index=True)
# session labels (UTC). equity: regular Mon-Fri 13:30-20:00; weekend Fri20:00->Mon13:30; else overnight. cme (index/commodity): weekend Fri 21:00 -> Sun 22:00; else regular. crypto: 24/7.
t=panel.t; dow=t.dt.dayofweek; mins=t.dt.hour*60+t.dt.minute
eq_reg=(dow<5)&(mins>=13*60+30)&(mins<20*60)
eq_wknd=(dow==5)|(dow==6)|((dow==4)&(mins>=20*60))|((dow==0)&(mins<13*60+30))
cme_wknd=(dow==5)|((dow==4)&(mins>=21*60))|((dow==6)&(mins<22*60))
sess=np.where(panel.cat=='crypto','24x7',
     np.where(panel.cat=='equity', np.where(eq_reg,'regular',np.where(eq_wknd,'weekend','overnight')),
     np.where(cme_wknd,'weekend','regular')))
panel['sess']=sess
panel['dev_bps']=(panel.pm_c/panel.hl_c-1)*1e4
panel['wick_dn_bps']=(panel.pm_l/panel.hl_l-1)*1e4   # negative = PM low below HL low
panel['wick_up_bps']=(panel.pm_h/panel.hl_h-1)*1e4
panel.to_parquet('data/panel_1m.parquet'); print("panel rows",len(panel), "instruments", panel.iid.nunique(), "t range", panel.t.min(), panel.t.max())
both=panel.dropna(subset=['pm_c','hl_c'])
print("rows with both PM & HL:", len(both))
pd.set_option('display.width',250); pd.set_option('display.max_rows',300)
g=both.groupby(['cat','sess']).agg(n=('dev_bps','size'),med_abs_dev=('dev_bps',lambda s:s.abs().median()),p95_abs_dev=('dev_bps',lambda s:s.abs().quantile(.95)),p99_abs_dev=('dev_bps',lambda s:s.abs().quantile(.99)),mean_dev=('dev_bps','mean'),
    p1_wick_dn=('wick_dn_bps',lambda s:s.quantile(.01)),p99_wick_up=('wick_up_bps',lambda s:s.quantile(.99)),
    frac_wick_dn_gt50=('wick_dn_bps',lambda s:(s<-50).mean()),frac_wick_up_gt50=('wick_up_bps',lambda s:(s>50).mean()))
print(g.to_string(float_format=lambda x:f"{x:.2f}"))
print("\n=== per instrument (all sessions) ===")
g2=both.groupby('sym').agg(n=('dev_bps','size'),med_abs=('dev_bps',lambda s:s.abs().median()),p99_abs=('dev_bps',lambda s:s.abs().quantile(.99)),mean_dev=('dev_bps','mean'),
    p1_wick_dn=('wick_dn_bps',lambda s:s.quantile(.01)),p99_wick_up=('wick_up_bps',lambda s:s.quantile(.99)),n_wick_dn_gt100=('wick_dn_bps',lambda s:(s<-100).sum()),n_wick_up_gt100=('wick_up_bps',lambda s:(s>100).sum()),pm_vol_usd=('pm_v',lambda s: s.sum()))
g2['pm_vol_usd']=g2.pm_vol_usd*both.groupby('sym').pm_c.median()
print(g2.sort_values('p99_abs',ascending=False).to_string(float_format=lambda x:f"{x:,.1f}"))
