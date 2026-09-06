#!/bin/bash
cd /home/user/poly-perps
for p in $(pgrep -f "python3 src/pull_touch.py"); do kill $p 2>/dev/null; done
sleep 2; rm -f data/touch/*.json
setsid nohup python3 src/pull_touch.py > data/logs/pull_touch.log 2>&1 < /dev/null &
sleep 30; ls data/touch | wc -l; tail -2 data/logs/pull_touch.log | cut -c1-160
