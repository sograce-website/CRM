SOGRACE CRM NEW AUTO COLLECT MODULE

上传到 GitHub 新增这两个文件：
1. auto_collect_new.py
2. install_auto_collect_new.py

服务器执行：
cd ~/crm
git fetch origin
git reset --hard origin/main
python3 install_auto_collect_new.py
python3 -m py_compile main.py
python3 -m py_compile auto_collect_new.py
pkill -f "uvicorn main:app" || true
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &

浏览器登录 CRM 后访问：
/auto_collect_new

日志：
/auto_collect_new_log

状态：
/auto_collect_new_status
