#!/bin/bash
# =============================================
# Safe Update Script for Sograce CRM main.py
# Auto-release port 8000 if occupied
# =============================================

# 1️⃣ 进入 CRM 根目录
cd ~/crm || { echo "CRM directory not found"; exit 1; }

# 2️⃣ 备份当前 main.py
if [ -f main.py ]; then
    cp main.py main.py.bak_$(date +"%Y%m%d_%H%M%S")
    echo "[Backup] main.py backed up"
fi

# 3️⃣ 复制新的 main_fixed_final.py 替换 main.py
cp ~/crm/main_fixed_final.py main.py
echo "[Replace] main.py replaced with main_fixed_final.py"

# 4️⃣ 使用虚拟环境编译 main.py
./venv/bin/python -m py_compile main.py
if [ $? -eq 0 ]; then
    echo "[Compile] main.py compiled successfully"
else
    echo "[Compile] Compilation failed"
    exit 1
fi

# 5️⃣ 检查端口 8000 是否被占用，并释放
PORT=8000
PID=$(sudo lsof -t -i:$PORT)
if [ ! -z "$PID" ]; then
    echo "[Port] Port $PORT is occupied by PID $PID. Killing process..."
    sudo kill -9 $PID
    sleep 1
    echo "[Port] Process killed, port $PORT released"
else
    echo "[Port] Port $PORT is free"
fi

# 6️⃣ 重启 CRM 服务
sudo systemctl restart crm
sleep 2

# 7️⃣ 检查 CRM 服务状态
sudo systemctl status crm --no-pager
if [ $? -eq 0 ]; then
    echo "[Service] CRM service is active"
else
    echo "[Service] CRM service failed to start"
fi

# 8️⃣ 可选：再次查看端口占用
sudo lsof -i :8000
