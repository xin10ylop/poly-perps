#!/bin/bash
for pat in "pull_ladders.py" "pull_touch.py"; do for p in $(pgrep -f "python3 src/$pat"); do kill $p; done; done
sleep 1; echo killed
