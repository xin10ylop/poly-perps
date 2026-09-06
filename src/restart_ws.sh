#!/bin/bash
cd /home/user/poly-perps
for p in $(pgrep -f "python3 src/ws_capture.py"); do kill $p 2>/dev/null; done
sleep 2
setsid nohup python3 src/ws_capture.py > data/logs/ws.log 2>&1 < /dev/null &
sleep 12; cat data/logs/ws.log
