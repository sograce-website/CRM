#!/bin/bash

# 进入 CRM 目录
cd ~/crm || exit 1

# 先确保 main.py 是最新版本
if [ -f main_fixed_final.py ]; then
    cp main_fixed_final.py main.py
    echo "[Replace] main.py replaced with main_fixed_final.py"
fi

# 编译 main.py
./venv/bin/python -m py_compile main.py
echo "[Compile] main.py compiled successfully"

# 重启 CRM 服务
sudo systemctl restart crm
sleep 2
sudo systemctl status crm --no-pager

# 检查 8000 端口是否被占用
PORT_PID=$(sudo lsof -ti:8000)
if [ -n "$PORT_PID" ]; then
    echo "[Port] Port 8000 is occupied by PID $PORT_PID. Killing process..."
    sudo kill -9 "$PORT_PID"
    echo "[Port] Port released"
fi

# 启动自动采集任务
echo "[AutoCollect] Starting Auto Lead Collector..."
./venv/bin/python lead_collector.py &
sleep 2

# 打开日志文件
echo "[Log] Tailing lead_collector.log..."
tail -f ~/crm/lead_collector.log
