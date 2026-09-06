"""BBO-level cross-venue test: PM best bid/ask (WS) vs HL mid (allMids poll ~1Hz). For each HL sample, compute executable edge
(HL_mid - PM_ask) or (PM_bid - HL_mid) in bps using PM BBO as of that time (latest before). Then check persistence: PM BBO at +2s, +5s, +15s
and HL mid at +15s. Reports frequency of edges > 5/10/20 bps and how much survives 2s latency (retail bot)."""
import json, glob, pandas as pd, numpy as np, sys
ins={i['instrument_id']:i for i in json.load(open('data/raw/instruments.json'))}
mp=json.load(open('data/hl/pm_to_hl_map.json'))
# HL mids
hm=[]
for f in sorted(glob.glob('data/hlmids/*.jsonl')):
    for l in open(f):
        r=json.loads(l); t=(r['rt']+r['rt2'])/2
        for k,v in r['m'].items(): hm.append((t,k,float(v)))
hm=pd.DataFrame(hm,columns=['t','coin','mid']); print("HL mid samples",len(hm),"coins",hm.coin.nunique(),"time span (min) %.1f"%((hm.t.max()-hm.t.min())/60))
t_start=hm.t.min()
# PM bbo (recv time rt)
rows=[]
for f in sorted(glob.glob('data/ws/bbo_*.jsonl')):
    for l in open(f):
        r=json.loads(l)
        if r['rt']<t_start-60: continue
        d=r['m']['data']
        try: rows.append((r['rt'],int(d['iid']),float(d['bp']),float(d['ap']),float(d['bq']),float(d['aq'])))
        except: pass
bbo=pd.DataFrame(rows,columns=['t','iid','bp','ap','bq','aq']); print("PM bbo updates in window",len(bbo))
out=[]
for iid,i in ins.items():
    coin=mp.get(i['base_asset']); 
    if not coin: continue
    h=hm[hm.coin==coin].set_index('t').mid.sort_index(); b=bbo[bbo.iid==iid].set_index('t').sort_index()
    if len(h)<50 or len(b)<20: continue
    # align: for each HL sample time, latest PM bbo before it
    bb=b.reindex(b.index.union(h.index)).sort_index().ffill().reindex(h.index)
    df=pd.DataFrame({'hl':h,'bp':bb.bp,'ap':bb.ap,'bq':bb.bq,'aq':bb.aq}).dropna()
    df['edge_buy']=(df.hl/df.ap-1)*1e4     # HL above PM ask -> buy PM
    df['edge_sell']=(df.bp/df.hl-1)*1e4    # PM bid above HL -> sell PM
    df['edge']=np.maximum(df.edge_buy,df.edge_sell); df['side']=np.where(df.edge_buy>df.edge_sell,1,-1)
    # persistence: PM bbo 2s/5s/15s later, HL 15s later
    def later(s,dt): 
        idx=np.searchsorted(s.index.values, df.index.values+dt, side='right')-1; idx=np.clip(idx,0,len(s)-1); return s.values[idx]
    for dt in (2,5,15):
        bp2=later(b.bp,dt); ap2=later(b.ap,dt)
        # if we buy PM at ask now (side=1), value later = PM bid later; realized = (bid_later/ask_now -1); for sell: (bp_now/ap_later -1)
        df[f'real_pm_{dt}']=np.where(df.side==1,(bp2/df.ap-1)*1e4,(df.bp/ap2-1)*1e4)
        # if instead we could only act after dt latency: edge available then
        df[f'edge_at_{dt}']=np.where(df.side==1,(df.hl/ap2-1)*1e4,(bp2/df.hl-1)*1e4)
    hl15=later(h,15); df['hl_move_15']=np.where(df.side==1,(hl15/df.hl-1)*1e4,(df.hl/hl15-1)*1e4)  # + if HL moved further in our favour (HL was leading)
    spread=((df.ap-df.bp)/df.ap*1e4).median()
    rec=dict(sym=i['symbol'],cat=i['category'],n=len(df),spread_bps=spread,edge_p50=df.edge.median(),edge_p95=df.edge.quantile(.95),edge_max=df.edge.max())
    for X in (5,10,20):
        s=df[df.edge>X]
        rec[f'n_gt{X}']=len(s); rec[f'frac_gt{X}']=len(s)/len(df)
        if len(s):
            rec[f'edge_at2_gt{X}']=s['edge_at_2'].mean(); rec[f'real15_gt{X}']=s['real_pm_15'].mean(); rec[f'hlmove15_gt{X}']=s['hl_move_15'].mean()
    out.append(rec)
res=pd.DataFrame(out); pd.set_option('display.width',260); pd.set_option('display.max_rows',100)
cols=['sym','cat','n','spread_bps','edge_p50','edge_p95','edge_max','frac_gt5','frac_gt10','n_gt10','edge_at2_gt10','real15_gt10','hlmove15_gt10','n_gt20','edge_at2_gt20','real15_gt20','hlmove15_gt20']
print(res.sort_values('edge_p95',ascending=False)[[c for c in cols if c in res.columns]].to_string(index=False,float_format=lambda x:f"{x:.1f}"))
print("\nColumns: edge = HL mid outside PM BBO (bps, before fees 4bps PM + ~4.5bps HL hedge). edge_at2 = same edge available 2s later (retail latency).")
print("real15 = PnL if we took PM now and unwound at PM BBO 15s later (no HL leg). hlmove15 = HL moved further in our favour over 15s (>0 means HL led, PM lagged).")
