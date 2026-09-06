"""Re-pull HL 1m candles with forward windows of <=5000 minutes (API returns most recent 5000 of a range)."""
import json, time, sys, requests
U="https://api.hyperliquid.xyz/info"; OUT="/home/user/poly-perps/data/hl"
def post(body):
    for a in range(8):
        try:
            r=requests.post(U,json=body,timeout=30)
            if r.status_code==429: time.sleep(3+3*a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",body,e,file=sys.stderr); time.sleep(1+a)
mp=json.load(open(f"{OUT}/pm_to_hl_map.json"))
now=int(time.time()*1000); start=int(time.mktime(time.strptime("2026-07-20","%Y-%m-%d")))*1000
W=4990*60*1000
for b,coin in mp.items():
    if not coin: continue
    cs={}; s=start
    while s<now:
        e=min(s+W,now)
        j=post({"type":"candleSnapshot","req":{"coin":coin,"interval":"1m","startTime":s,"endTime":e}})
        for x in (j or []): cs[int(x['t'])]=x
        s=e+1; time.sleep(0.25)
    out=[cs[k] for k in sorted(cs)]
    json.dump(out,open(f"{OUT}/candles1m_{b}.json","w")); print(b,coin,len(out),"first",out[0]['t'] if out else None,flush=True)
print("DONE")
