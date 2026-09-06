"""Pull all public trades (data-api) for the up/down markets already collected."""
import json, glob, time, sys, requests
OUT="/home/user/poly-perps/data/updown_trades"; S=requests.Session()
def get(**p):
    for a in range(6):
        try:
            r=S.get("https://data-api.polymarket.com/trades",params=p,timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",p,e,file=sys.stderr); time.sleep(1+a)
    return None
fs=sorted(glob.glob('data/updown/*.json'))
for f in fs:
    r=json.load(open(f)); m=r['event']['markets'][0]; cid=m['conditionId']; slug=r['slug']
    out=[]; off=0
    while True:
        j=get(market=cid,limit=500,offset=off)
        if not j: break
        out.extend(j)
        if len(j)<500 or off>=3000: break
        off+=500; time.sleep(0.1)
    json.dump(out,open(f"{OUT}/{slug}.json","w")); time.sleep(0.1)
print("DONE",len(fs))
