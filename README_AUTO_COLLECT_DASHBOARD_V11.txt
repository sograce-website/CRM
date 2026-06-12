SOGRACE CRM Auto Collect Dashboard V1.1

上传到 GitHub：
install_auto_collect_dashboard_v11.py

服务器执行：
cd ~/crm
git fetch origin
git reset --hard origin/main
python3 install_auto_collect_new.py
python3 install_auto_collect_dashboard_v11.py
python3 -m py_compile main.py
pkill -f "uvicorn main:app" || true
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &

打开：
https://crm.sograce.cn

启动新采集：
https://crm.sograce.cn/auto_collect_new

日志：
https://crm.sograce.cn/auto_collect_new_log
