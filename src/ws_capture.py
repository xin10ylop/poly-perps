"""Capture Polymarket Perps public WS: bbo + trades for all instruments, book for top N. Writes JSONL per channel type with recv timestamp."""
import json, time, sys, threading, websocket, os
OUT="/home/user/poly-perps/data/ws"
ins=json.load(open('/home/user/poly-perps/data/raw/instruments.json'))
ids=[i['instrument_id'] for i in ins]
TOP=[int(x) for x in sys.argv[1].split(',')] if len(sys.argv)>1 else [6,7,8,10,1,2,19,21,4,5]
files={}
lock=threading.Lock()
def fh(kind):
    if kind not in files:
        files[kind]=open(f"{OUT}/{kind}_{time.strftime('%Y%m%d_%H')}.jsonl","a")
    return files[kind]
def run(chs, name):
    last_book={}
    def on_msg(ws,msg):
        t=time.time()
        try: j=json.loads(msg)
        except: return
        ch=j.get("ch"); kind=ch.split("::")[0] if isinstance(ch,str) else "ack"
        if kind=="book":
            if t-last_book.get(ch,0)<2.0: return
            last_book[ch]=t
            d=j.get("data",{}); d["a"]=d.get("a",[])[:10]; d["b"]=d.get("b",[])[:10]
        with lock:
            f=fh(kind); f.write(json.dumps({"rt":t,"m":j})+"\n")
    def on_open(ws):
        for i in range(0,len(chs),50):
            ws.send(json.dumps({"req":"sub","chs":chs[i:i+50],"id":i}))
        print(name,"subscribed",len(chs),flush=True)
    def on_err(ws,e): print(name,"err",e,flush=True)
    def on_close(ws,a,b): print(name,"closed",a,b,flush=True)
    while True:
        ws=websocket.WebSocketApp("wss://ws.perpetuals.polymarket.com/v1/ws",on_message=on_msg,on_open=on_open,on_error=on_err,on_close=on_close)
        ws.run_forever(ping_interval=20,ping_timeout=10)
        time.sleep(3)
def flusher():
    while True:
        time.sleep(5)
        with lock:
            for f in list(files.values()): f.flush()
            # hourly rotate
            hr=time.strftime('%Y%m%d_%H')
            for k,f in list(files.items()):
                if not f.name.endswith(f"{hr}.jsonl"): f.close(); del files[k]
threading.Thread(target=flusher,daemon=True).start()
conns=[]
conns.append(([f"bbo::{i}" for i in ids] + [f"funding::{i}" for i in ids[:30]],"c1"))
conns.append(([f"trades::{i}" for i in ids] + [f"funding::{i}" for i in ids[30:]],"c2"))
conns.append(([f"book::{i}" for i in ids],"c3"))
for chs,name in conns:
    threading.Thread(target=run,args=(chs,name),daemon=True).start()
while True: time.sleep(60)
