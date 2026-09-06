import json, time, sys, requests
B="https://api.perpetuals.polymarket.com/v1/info"; OUT="/home/user/poly-perps/data/pm"
S=requests.Session()
def get(path, **params):
    for attempt in range(8):
        try:
            r=S.get(f"{B}/{path}", params=params, timeout=30)
            if r.status_code==429: time.sleep(3+attempt*3); continue
            r.raise_for_status(); return r.json()
        except Exception as e: print("ERR",path,params,e,file=sys.stderr); time.sleep(1+attempt)
    return None
ins=json.load(open('/home/user/poly-perps/data/raw/instruments.json'))
now=int(time.time()*1000); start=int(time.mktime(time.strptime("2026-07-20","%Y-%m-%d")))*1000
for i in ins:
    iid=i['instrument_id']; out=[]; s=start; pages=0
    while True:
        j=get('mark-history', instrument_id=iid, interval='1m', start_timestamp=s, end_timestamp=now)
        if not j: break
        data=j.get('data',[])
        if pages==0 and iid==1: print("sample:", json.dumps(data[:2]), file=sys.stderr)
        if not data: break
        out.extend(data); pages+=1
        if not j.get('more',False): break
        def ts(x): return int(x[0]) if isinstance(x,list) else int(x.get('timestamp') or x.get('t'))
        s=max(ts(x) for x in data)+1; time.sleep(0.25)
        if pages>4000: break
    json.dump(out,open(f"{OUT}/mark1m_{iid}.json","w")); print(i['symbol'],"mark1m",len(out),flush=True)
print("DONE")
