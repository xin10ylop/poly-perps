"""Poll Hyperliquid allMids (main + xyz dex) every ~1s; write JSONL with local time."""
import json, time, requests, threading
OUT="/home/user/poly-perps/data/hlmids"
S=requests.Session()
def loop(dex):
    body={"type":"allMids"} if dex is None else {"type":"allMids","dex":dex}
    name=dex or "main"; f=None; hr=None
    while True:
        t0=time.time()
        try:
            r=S.post("https://api.hyperliquid.xyz/info",json=body,timeout=5)
            if r.status_code==200:
                h=time.strftime('%Y%m%d_%H')
                if h!=hr:
                    if f: f.close()
                    f=open(f"{OUT}/{name}_{h}.jsonl","a"); hr=h
                f.write(json.dumps({"rt":t0,"rt2":time.time(),"m":r.json()})+"\n"); f.flush()
        except Exception as e: pass
        dt=time.time()-t0; time.sleep(max(0,1.0-dt))
for d in (None,"xyz"): threading.Thread(target=loop,args=(d,),daemon=True).start()
while True: time.sleep(60)
