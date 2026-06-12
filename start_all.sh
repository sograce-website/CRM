#!/bin/bash
cd /home/admin/crm

pkill -f "uvicorn dashboard_v44:app"
pkill -f "lead_collector_v40.py"

sleep 2

nohup ./venv/bin/uvicorn dashboard_v44:app --host 0.0.0.0 --port 8012 > dashboard_v44.log 2>&1 &

nohup ./venv/bin/python lead_collector_v40.py > lead_collect.log 2>&1 &

sleep 3

echo "===== DASHBOARD ====="
ps -ef | grep dashboard_v44 | grep -v grep

echo "===== COLLECTOR ====="
ps -ef | grep lead_collector_v40.py | grep -v grep

echo "===== PORT ====="
ss -tlnp | grep 8012

echo "===== DASHBOARD TEST ====="
curl -I http://127.0.0.1:8012/dashboard

echo "===== COLLECT LOG ====="
tail -20 lead_collect.log
