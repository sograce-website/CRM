SOGRACE CRM 首页仪表盘补丁

上传到 GitHub 仓库根目录（和 main.py 同级）：
sograce_home_dashboard_patch.py

同步到阿里云服务器后执行：
cd ~/crm
python3 sograce_home_dashboard_patch.py
python3 -m py_compile main.py
pkill -f "uvicorn main:app" || true
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &

访问：
http://8.219.139.140:8012/login
登录后：
http://8.219.139.140:8012/
或：
http://8.219.139.140:8012/dashboard
