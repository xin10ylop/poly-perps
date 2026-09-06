"""Pull 'what-price-will-X-hit' touch/barrier ladders: monthly, weekly, daily; BTC/ETH/SOL; with CLOB YES price history."""
import json, time, sys, requests, datetime as dt
def ts(x):
    return int(dt.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp())

G="https://gamma-api.polymarket.com/events"; C="https://clob.polymarket.com/prices-history"
OUT="/home/user/poly-perps/data/touch"; S=requests.Session()
def get(url, **p):
    for a in range(6):
        try:
            r=S.get(url, params=p, timeout=30)
            if r.status_code==429: time.sleep(2+2*a); continue
            if r.status_code in (404,400): return None
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",url,p,e,file=sys.stderr); time.sleep(1+a)
    return None
def save(slug,a,kind):
    ev=get(G, slug=slug)
    if not ev: return False
    e=ev[0]; rec={'slug':slug,'asset':a,'kind':kind,'event':e,'hist':{}}
    for m in e.get('markets',[]):
        try: toks=json.loads(m['clobTokenIds'])
        except: continue
        if not toks: continue
        st=ts(m.get('startDate') or e['startDate'])-3600; en=ts(m.get('endDate') or e['endDate'])+3600
        hist=[]; w=10*86400; a0=st
        while a0<en:
            b0=min(a0+w,en)
            hh=get(C, market=toks[0], startTs=a0, endTs=b0, fidelity=30 if kind=='monthly' else 10)
            if hh and hh.get('history'): hist.extend(hh['history'])
            a0=b0; time.sleep(0.1)
        h={'history':hist}
        rec['hist'][m['id']]=(h or {}).get('history',[]); time.sleep(0.15)
    json.dump(rec, open(f"{OUT}/{slug}.json","w")); print(slug,len(e.get('markets',[])),flush=True); return True
assets=['bitcoin','ethereum','solana']
months=[(y,m) for y in (2025,2026) for m in range(1,13) if (y,m)<=(2026,10)]
for a in assets:
    for y,m in months:
        save(f"{a}-price-on-{dt.date(y,m,1).strftime('%B').lower()}-{y}" if False else f"what-price-will-{a}-hit-in-{dt.date(y,m,1).strftime('%B').lower()}-{y}", a, 'monthly')
        time.sleep(0.2)
# weekly: 'what-price-will-bitcoin-hit-august-31-september-6-2026' -> Monday..Sunday
d=dt.date(2025,9,1)
while d<=dt.date(2026,9,7):
    if d.weekday()==0:
        e=d+dt.timedelta(days=6)
        for a in assets:
            if d.month==e.month: slug=f"what-price-will-{a}-hit-{d.strftime('%B').lower()}-{d.day}-{e.day}-{e.year}"
            else: slug=f"what-price-will-{a}-hit-{d.strftime('%B').lower()}-{d.day}-{e.strftime('%B').lower()}-{e.day}-{e.year}"
            save(slug,a,'weekly')
    d+=dt.timedelta(days=1)
# daily: 'what-price-will-bitcoin-hit-on-september-5-2026'
d=dt.date(2026,3,1)
while d<=dt.date(2026,9,7):
    for a in assets: save(f"what-price-will-{a}-hit-on-{d.strftime('%B').lower()}-{d.day}-{d.year}",a,'daily')
    d+=dt.timedelta(days=1)
print("DONE")
