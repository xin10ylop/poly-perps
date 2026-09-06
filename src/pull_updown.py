"""Pull Polymarket 15m and 4h BTC/ETH up-or-down markets for last N days, with 1-min CLOB price history."""
import json, time, sys, requests
G="https://gamma-api.polymarket.com/events"; C="https://clob.polymarket.com/prices-history"
OUT="/home/user/poly-perps/data/updown"; S=requests.Session()
def get(url, **p):
    for a in range(6):
        try:
            r=S.get(url, params=p, timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            if r.status_code==404: return None
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",url,p,e,file=sys.stderr); time.sleep(1+a)
    return None
days=int(sys.argv[1]) if len(sys.argv)>1 else 10
now=int(time.time()); 
specs=[('btc','15m',900),('eth','15m',900),('btc','4h',14400),('eth','4h',14400)]
for asset,tf,step in specs:
    t=(now//step)*step - step  # last completed period
    t0=t-days*86400; found=0; miss=0
    while t>=t0:
        slug=f"{asset}-updown-{tf}-{t}"
        ev=get(G, slug=slug)
        if ev:
            e=ev[0]; m=e['markets'][0]
            toks=json.loads(m['clobTokenIds']) if m.get('clobTokenIds') else []
            h=get(C, market=toks[0], interval='max', fidelity=1) if toks else None
            json.dump({'slug':slug,'asset':asset,'tf':tf,'t':t,'event':e,'hist':(h or {}).get('history',[])}, open(f"{OUT}/{slug}.json","w"))
            found+=1
        else: miss+=1
        t-=step; time.sleep(0.12)
    print(asset,tf,"found",found,"miss",miss,flush=True)
print("DONE")
