"""Pull HL BTC/ETH/SOL 1m candles as far back as the API serves (target Jan 2026)."""
import json, time, sys, requests
U="https://api.hyperliquid.xyz/info"; OUT="/home/user/poly-perps/data/hl"
def post(body):
    for a in range(8):
        try:
            r=requests.post(U,json=body,timeout=30)
            if r.status_code==429: time.sleep(3+3*a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",e,file=sys.stderr); time.sleep(1+a)
now=int(time.time()*1000); start=int(time.mktime(time.strptime("2025-09-01","%Y-%m-%d")))*1000
W=4990*60*1000
for coin in ['BTC','ETH','SOL']:
    cs={}; s=start; empty=0
    while s<now:
        e=min(s+W,now); j=post({"type":"candleSnapshot","req":{"coin":coin,"interval":"1m","startTime":s,"endTime":e}})
        if j: 
            for x in j: cs[int(x['t'])]=x
        else: empty+=1
        s=e+1; time.sleep(0.3)
    out=[cs[k] for k in sorted(cs)]
    json.dump(out,open(f"{OUT}/deep1m_{coin}.json","w")); print(coin,len(out),"first",time.strftime('%Y-%m-%d',time.gmtime(out[0]['t']/1000)) if out else None,"empty windows",empty,flush=True)
print("DONE")
