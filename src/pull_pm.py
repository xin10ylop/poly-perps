"""Pull Polymarket Perps public history: funding, 1m klines, trades, for all instruments."""
import json, time, sys, os, requests
B="https://api.perpetuals.polymarket.com/v1/info"
OUT="/home/user/poly-perps/data/pm"
S=requests.Session()
def get(path, **params):
    for attempt in range(6):
        try:
            r=S.get(f"{B}/{path}", params=params, timeout=30)
            if r.status_code==429:
                time.sleep(2+attempt*2); continue
            r.raise_for_status(); return r.json()
        except Exception as e:
            print("ERR",path,params,e,file=sys.stderr); time.sleep(1+attempt)
    return None
def ts_of(item):
    for k in ('timestamp','time','ts','created_at','t'):
        if k in item: return int(item[k])
    raise KeyError(f"no ts in {item}")
def paginate(path, iid, start, end, label):
    """API returns newest-first pages of 100; walk backwards via end_timestamp."""
    allitems=[]; e=end; pages=0; seen=set()
    while True:
        j=get(path, instrument_id=iid, start_timestamp=start, end_timestamp=e)
        if j is None: break
        data=j.get('data',j) if isinstance(j,dict) else j
        if pages==0 and iid==1: print(f"[{label}] first resp keys:", list(j.keys()) if isinstance(j,dict) else type(j), "| sample:", json.dumps(data[:1])[:400], file=sys.stderr)
        if not data: break
        new=[x for x in data if json.dumps(x,sort_keys=True) not in seen]
        for x in new: seen.add(json.dumps(x,sort_keys=True))
        allitems.extend(new); pages+=1
        mn=min(ts_of(x) for x in data)
        more=j.get('more',False) if isinstance(j,dict) else False
        if not more and len(data)<100: break
        if mn<=start: break
        e=mn-1
        time.sleep(0.15)
        if pages>6000: print("page cap",label,iid,file=sys.stderr); break
    return allitems
def klines(iid, interval, start, end):
    out=[]; s=start; pages=0
    while True:
        j=get('klines', instrument_id=iid, interval=interval, start_timestamp=s, end_timestamp=end)
        if not j: break
        data=j.get('data',[])
        if not data: break
        out.extend(data); pages+=1
        if not j.get('more',False): break
        s=max(int(k[0]) for k in data)+1
        time.sleep(0.12)
        if pages>3000: break
    return out
if __name__=="__main__":
    ins=json.load(open('/home/user/poly-perps/data/raw/instruments.json'))
    now=int(time.time()*1000)
    start=int(time.mktime(time.strptime("2026-07-20","%Y-%m-%d")))*1000
    what=sys.argv[1] if len(sys.argv)>1 else "all"
    ids=[i['instrument_id'] for i in ins]
    for iid in ids:
        sym=[i['symbol'] for i in ins if i['instrument_id']==iid][0]
        if what in ("all","funding"):
            f=paginate('funding', iid, start, now, 'funding')
            json.dump(f, open(f"{OUT}/funding_{iid}.json","w")); print(sym,"funding",len(f),flush=True)
        if what in ("all","klines"):
            k=klines(iid,'1m',start,now)
            json.dump(k, open(f"{OUT}/klines1m_{iid}.json","w")); print(sym,"klines1m",len(k), "first", k[0][0] if k else None,flush=True)
        if what in ("all","trades"):
            t=paginate('trades', iid, start, now, 'trades')
            json.dump(t, open(f"{OUT}/trades_{iid}.json","w")); print(sym,"trades",len(t),flush=True)
    print("DONE",what)
