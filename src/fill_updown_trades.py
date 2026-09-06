import json, glob, os, time, requests
S=requests.Session()
def get(**p):
    for a in range(6):
        try:
            r=S.get("https://data-api.polymarket.com/trades",params=p,timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            r.raise_for_status(); return r.json()
        except Exception: time.sleep(1+a)
    return None
fs=sorted(glob.glob('data/updown/*.json')); n=0
for f in fs:
    slug=f.split('/')[-1][:-5]; ft=f"data/updown_trades/{slug}.json"
    if os.path.exists(ft): continue
    m=json.load(open(f))['event']['markets'][0]; cid=m['conditionId']; out=[]; off=0
    while True:
        j=get(market=cid,limit=500,offset=off)
        if not j: break
        out.extend(j)
        if len(j)<500 or off>=4500: break
        off+=500
    json.dump(out,open(ft,'w')); n+=1
    if n%100==0: print("filled",n,flush=True)
print("DONE",n)
