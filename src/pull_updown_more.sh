#!/bin/bash
cd /home/user/poly-perps
# extend updown to 35 days (script skips nothing; re-fetches existing too, acceptable) then trades for all
python3 - <<'PY'
import re
s=open('src/pull_updown.py').read()
s=s.replace("t=(now//step)*step - step  # last completed period\n    t0=t-days*86400","t=(now//step)*step - step - 7*86400  # start where previous run ended\n    t0=t-days*86400")
s=s.replace("json.dump({'slug'","import os\n            if os.path.exists(f\"{OUT}/{slug}.json\"): t-=step; continue\n            json.dump({'slug'")
open('src/pull_updown_more.py','w').write(s)
PY
python3 src/pull_updown_more.py 28 > data/logs/pull_updown_more.log 2>&1
python3 src/pull_updown_trades.py > data/logs/pull_updown_trades2.log 2>&1
