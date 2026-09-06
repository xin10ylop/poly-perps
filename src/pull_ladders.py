"""Pull Polymarket daily 'X above on <date>' strike ladders (BTC/ETH/SOL) + CLOB price history of YES tokens."""
import json, time, sys, requests, datetime as dt
def ts(x):
    return int(dt.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp())

G="https://gamma-api.polymarket.com/events"; C="https://clob.polymarket.com/prices-history"
OUT="/home/user/poly-perps/data/ladders"; S=requests.Session()
def get(url, **p):
    for a in range(6):
        try:
            r=S.get(url, params=p, timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            if r.status_code==404: return None
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",url,p,e,file=sys.stderr); time.sleep(1+a)
    return None
assets=['bitcoin','ethereum','solana']
d0=dt.date(2026,3,1); d1=dt.date(2026,9,7)
d=d0; n_ev=0; n_mk=0
while d<=d1:
    for a in assets:
        slug=f"{a}-above-on-{d.strftime('%B').lower()}-{d.day}-{d.year}"
        ev=get(G, slug=slug)
        if not ev: continue
        e=ev[0]; rec={'slug':slug,'asset':a,'date':d.isoformat(),'event':e,'hist':{}}
        for m in e.get('markets',[]):
            try: toks=json.loads(m['clobTokenIds'])
            except: continue
            if not toks: continue
            st=ts(m.get('startDate') or e['startDate'])-3600; en=ts(m.get('endDate') or e['endDate'])+3600
            h=get(C, market=toks[0], startTs=st, endTs=en, fidelity=5)
            rec['hist'][m['id']]=(h or {}).get('history',[])
            n_mk+=1; time.sleep(0.15)
        json.dump(rec, open(f"{OUT}/{slug}.json","w")); n_ev+=1
        print(slug, len(e.get('markets',[])), "markets", flush=True)
        time.sleep(0.2)
    d+=dt.timedelta(days=1)
print("DONE events",n_ev,"markets",n_mk)
