#!/bin/bash

# 停止旧的 Dashboard 和采集任务
pkill -f 'uvicorn dashboard_v44:app'
pkill -f 'python3 auto_collect.py'

# 等待 2 秒
sleep 2

# 进入 CRM 目录
cd /home/admin/crm

# 启动 Dashboard (后台运行)
nohup ./venv/bin/uvicorn dashboard_v44:app --host 0.0.0.0 --port 8012 > dashboard_v44.log 2>&1 &

# 启动自动采集任务 (后台运行)
nohup ./venv/bin/python3 auto_collect.py > lead_collect_log 2>&1 &

# 等待 3 秒
sleep 3

# 显示进程状态
echo "===== PROCESS ====="
ps -ef | grep dashboard_v44 | grep -v grep
ps -ef | grep auto_collect.py | grep -v grep

# 显示端口监听状态
echo "===== PORT ====="
ss -tlnp | grep 8012

echo "Dashboard & Auto Collect started successfully."
