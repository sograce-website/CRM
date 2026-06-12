#!/bin/bash

pkill -f "uvicorn dashboard_v44:app"

sleep 2

cd /home/admin/crm

nohup ./venv/bin/uvicorn dashboard_v44:app --host 0.0.0.0 --port 8012 > dashboard_v44.log 2>&1 &

sleep 3

echo "===== PROCESS ====="
ps -ef | grep dashboard_v44 | grep -v grep

echo "===== PORT ====="
ss -tlnp | grep 8012

echo "===== TEST ====="
curl -I http://127.0.0.1:8012/dashboard
