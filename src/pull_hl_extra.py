import json, time, sys, requests
U="https://api.hyperliquid.xyz/info"; OUT="/home/user/poly-perps/data/hl"
def post(body):
    for a in range(6):
        try:
            r=requests.post(U,json=body,timeout=30)
            if r.status_code==429: time.sleep(3+3*a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",body,e,file=sys.stderr); time.sleep(1+a)
extra={'WTIOIL':'xyz:CL','NAS100':'xyz:XYZ100','SKHYNIX':'xyz:SKHX','KPEPE':'kPEPE','KSHIB':'kSHIB','SAMSUNG':'xyz:SMSN'}
mp=json.load(open(f"{OUT}/pm_to_hl_map.json")); mp.update(extra); json.dump(mp,open(f"{OUT}/pm_to_hl_map.json","w"),indent=1)
now=int(time.time()*1000); start=int(time.mktime(time.strptime("2026-07-20","%Y-%m-%d")))*1000
for b,coin in extra.items():
    fh=[]; s=start
    while True:
        j=post({"type":"fundingHistory","coin":coin,"startTime":s,"endTime":now})
        if not j: break
        fh.extend(j)
        if len(j)<500: break
        s=max(x['time'] for x in j)+1; time.sleep(0.25)
    json.dump(fh,open(f"{OUT}/funding_{b}.json","w"))
    cs=[]; s=start
    while s<now:
        j=post({"type":"candleSnapshot","req":{"coin":coin,"interval":"1m","startTime":s,"endTime":now}})
        if not j: break
        cs.extend(j)
        if len(j)<5000: break
        s=max(x['t'] for x in j)+1; time.sleep(0.3)
    json.dump(cs,open(f"{OUT}/candles1m_{b}.json","w")); print(b,coin,len(fh),len(cs),flush=True)
print("DONE")
