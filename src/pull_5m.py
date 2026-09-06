"""Pull 5-minute up/down markets (event JSON + all data-api trades) for given assets and days."""
import json, time, sys, os, requests
G="https://gamma-api.polymarket.com/events"; T="https://data-api.polymarket.com/trades"; S=requests.Session()
def get(url, **p):
    for a in range(6):
        try:
            r=S.get(url, params=p, timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            if r.status_code==404: return None
            r.raise_for_status(); return r.json()
        except Exception as e: time.sleep(1+a)
    return None
assets=sys.argv[1].split(','); days=float(sys.argv[2]); step=300
now=int(time.time()); t_end=(now//step)*step-2*step; t0=t_end-int(days*86400)
n=0
for asset in assets:
    t=t_end; found=0
    while t>=t0:
        slug=f"{asset}-updown-5m-{t}"; fe=f"data/updown5m/{slug}.json"; ft=f"data/updown5m_trades/{slug}.json"
        if not os.path.exists(fe):
            ev=get(G, slug=slug)
            if ev: json.dump({'slug':slug,'asset':asset,'tf':'5m','t':t,'event':ev[0]}, open(fe,'w')); found+=1
        if os.path.exists(fe) and not os.path.exists(ft):
            m=json.load(open(fe))['event']['markets'][0]; cid=m['conditionId']; out=[]; off=0
            while True:
                j=get(T, market=cid, limit=500, offset=off)
                if not j: break
                out.extend(j)
                if len(j)<500 or off>=4500: break
                off+=500
            json.dump(out, open(ft,'w'))
        t-=step; n+=1
        if n%200==0: print(asset, "processed", n, "found", found, flush=True); time.sleep(0.2)
    print(asset,"done found",found,flush=True)
print("DONE")
