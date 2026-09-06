#!/bin/bash
cd /home/user/poly-perps
for p in $(pgrep -f "python3 src/live_capture_15m.py"); do kill $p 2>/dev/null; done
sleep 2; setsid nohup python3 src/live_capture_15m.py >> data/logs/live15.log 2>&1 < /dev/null &
sleep 20; tail -3 data/logs/live15.log; tail -c 400 data/live15/markets_$(date -u +%Y%m%d_%H).jsonl
