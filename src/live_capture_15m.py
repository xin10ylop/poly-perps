"""Live capture for 15m/4h up-down binaries with exact timing:
 - Polymarket CLOB market WS (book + last_trade_price + price_change) for the current & next BTC/ETH 15m markets
 - PM perps BBO for BTC/ETH (already captured separately) + Coinbase ticker via REST every 2s (fallback reference)
Writes JSONL with local receive time."""
import json, time, threading, requests, websocket, sys, os
OUT="/home/user/poly-perps/data/live15"
G="https://gamma-api.polymarket.com/events"
lock=threading.Lock(); files={}
def fh(kind):
    hr=time.strftime('%Y%m%d_%H')
    if kind not in files or not files[kind].name.endswith(f"{hr}.jsonl"):
        if kind in files: files[kind].close()
        files[kind]=open(f"{OUT}/{kind}_{hr}.jsonl","a")
    return files[kind]
def write(kind,obj):
    with lock: f=fh(kind); f.write(json.dumps(obj)+"\n"); f.flush()
def current_markets():
    now=int(time.time()); out=[]
    for asset,step in (('btc',900),('eth',900),('btc',14400),('eth',14400),('btc',300),('eth',300),('sol',300),('xrp',300),('sol',900),('xrp',900)):
        tf={900:'15m',14400:'4h',300:'5m'}[step]
        for k in (0,1):
            t=(now//step)*step+k*step; slug=f"{asset}-updown-{tf}-{t}"
            try:
                ev=requests.get(G,params=dict(slug=slug),timeout=15).json()
                if ev:
                    m=ev[0]['markets'][0]; toks=json.loads(m['clobTokenIds'])
                    out.append(dict(slug=slug,asset=asset,tf=tf,t0=t,t1=t+step,cond=m['conditionId'],up=toks[0],down=toks[1]))
            except Exception as e: print("gamma err",slug,e,flush=True)
    return out
subscribed=set()
def clob_ws():
    while True:
        try:
            ws=websocket.create_connection("wss://ws-subscriptions-clob.polymarket.com/ws/market",timeout=30)
            def sub(mk):
                ws.send(json.dumps({"assets_ids":[mk['up'],mk['down']],"type":"market"}))
            mks=current_markets()
            for mk in mks:
                if mk['slug'] not in subscribed: sub(mk); subscribed.add(mk['slug']); write('markets',dict(rt=time.time(),**mk))
            last_refresh=time.time(); ws.settimeout(5)
            while True:
                try:
                    msg=ws.recv()
                    if msg: 
                        try: j=json.loads(msg)
                        except: j={"raw":msg}
                        write('clob',dict(rt=time.time(),m=j))
                except websocket.WebSocketTimeoutException: pass
                if time.time()-last_refresh>30:
                    last_refresh=time.time()
                    for mk in current_markets():
                        if mk['slug'] not in subscribed: sub(mk); subscribed.add(mk['slug']); write('markets',dict(rt=time.time(),**mk))
                    ws.send("PING")
        except Exception as e:
            print("clob ws err",e,flush=True); time.sleep(3)
def coinbase_poll():
    while True:
        for prod in ('BTC-USD','ETH-USD','SOL-USD','XRP-USD'):
            try:
                r=requests.get(f"https://api.exchange.coinbase.com/products/{prod}/ticker",timeout=5).json()
                write('cb',dict(rt=time.time(),prod=prod,bid=r.get('bid'),ask=r.get('ask'),price=r.get('price'),time=r.get('time')))
            except Exception as e: pass
        time.sleep(0.5)
def pm_bbo():
    while True:
        try:
            ws=websocket.create_connection("wss://ws.perpetuals.polymarket.com/v1/ws",timeout=30)
            ws.send(json.dumps({"req":"sub","chs":["bbo::6","bbo::7","trades::6","trades::7"]})); ws.settimeout(30)
            while True:
                msg=ws.recv(); j=json.loads(msg)
                if 'ch' in j: write('pmbbo',dict(rt=time.time(),m=j))
        except Exception as e: print("pm ws err",e,flush=True); time.sleep(3)
for f in (clob_ws,coinbase_poll,pm_bbo): threading.Thread(target=f,daemon=True).start()
while True: time.sleep(60)
