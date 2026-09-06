"""Coinbase Exchange 1m candles for BTC-USD, ETH-USD, SOL-USD from 2026-03-01."""
import json, time, sys, requests, datetime as dt
OUT="/home/user/poly-perps/data/cb"; S=requests.Session()
def get(prod, start, end):
    for a in range(8):
        try:
            r=S.get(f"https://api.exchange.coinbase.com/products/{prod}/candles", params=dict(granularity=60,start=dt.datetime.utcfromtimestamp(start).isoformat(),end=dt.datetime.utcfromtimestamp(end).isoformat()), timeout=30)
            if r.status_code==429: time.sleep(1+a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",prod,start,e,file=sys.stderr); time.sleep(1+a)
    return []
start=int(dt.datetime(2026,3,1,tzinfo=dt.timezone.utc).timestamp()); now=int(time.time())
for prod in ['BTC-USD','ETH-USD','SOL-USD']:
    allc={}; s=start
    while s<now:
        e=min(s+300*60,now); c=get(prod,s,e)
        for x in c: allc[int(x[0])]=x   # [time, low, high, open, close, volume]
        s=e; time.sleep(0.12)
    out=[allc[k] for k in sorted(allc)]
    json.dump(out,open(f"{OUT}/{prod}_1m.json","w")); print(prod,len(out),flush=True)
print("DONE")
