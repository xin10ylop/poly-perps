"""Pull Hyperliquid data: metaAndAssetCtxs (main + xyz), predictedFundings, funding history and 1m candles for overlapping assets."""
import json, time, sys, requests
U="https://api.hyperliquid.xyz/info"; OUT="/home/user/poly-perps/data/hl"
def post(body):
    for a in range(6):
        try:
            r=requests.post(U,json=body,timeout=30)
            if r.status_code==429: time.sleep(3+3*a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",body,e,file=sys.stderr); time.sleep(1+a)
    return None
pm=json.load(open('/home/user/poly-perps/data/raw/instruments.json'))
bases=[i['base_asset'] for i in pm]
main=post({"type":"metaAndAssetCtxs"}); json.dump(main,open(f"{OUT}/main_ctx.json","w"))
mainnames=[u['name'] for u in main[0]['universe']]
dexes=post({"type":"perpDexs"}); json.dump(dexes,open(f"{OUT}/perpdexs.json","w"))
allctx={}
for d in dexes:
    if not d: continue
    n=d['name']; c=post({"type":"metaAndAssetCtxs","dex":n}); 
    if c: json.dump(c,open(f"{OUT}/ctx_{n}.json","w")); allctx[n]=c
    time.sleep(0.3)
pf=post({"type":"predictedFundings"}); json.dump(pf,open(f"{OUT}/predicted_fundings.json","w"))
# map PM base -> HL coin (main or dex-prefixed)
def find(base):
    if base in mainnames: return base
    for n,c in allctx.items():
        for u in c[0]['universe']:
            nm=u['name']; short=nm.split(':')[-1]
            if short.upper()==base.upper(): return nm
    return None
mp={b:find(b) for b in bases}
json.dump(mp,open(f"{OUT}/pm_to_hl_map.json","w"),indent=1); print("map:",mp,flush=True)
now=int(time.time()*1000); start=int(time.mktime(time.strptime("2026-07-20","%Y-%m-%d")))*1000
for b,coin in mp.items():
    if not coin: continue
    # funding history (paginated by time, 500 per call)
    fh=[]; s=start
    while True:
        j=post({"type":"fundingHistory","coin":coin,"startTime":s,"endTime":now})
        if not j: break
        fh.extend(j)
        if len(j)<500: break
        s=max(x['time'] for x in j)+1; time.sleep(0.25)
    json.dump(fh,open(f"{OUT}/funding_{b}.json","w")); 
    # 1m candles (max 5000 per call ~3.5 days)
    cs=[]; s=start
    while s<now:
        j=post({"type":"candleSnapshot","req":{"coin":coin,"interval":"1m","startTime":s,"endTime":now}})
        if not j: break
        cs.extend(j)
        if len(j)<5000: break
        s=max(x['t'] for x in j)+1; time.sleep(0.3)
    json.dump(cs,open(f"{OUT}/candles1m_{b}.json","w"))
    print(b,coin,"funding",len(fh),"candles",len(cs),flush=True); time.sleep(0.3)
print("DONE")
