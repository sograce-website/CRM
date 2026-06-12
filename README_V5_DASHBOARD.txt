SOGRACE CRM V5.0 Dashboard Edition

文件：
- main_v5_dashboard.py

上传 GitHub 方法：
1. 把 main_v5_dashboard.py 改名为 main.py
2. 上传覆盖 GitHub 仓库根目录里的 main.py
3. 阿里云服务器执行：

cd ~/crm
git pull origin main
python3 -m py_compile main.py
pkill -f "uvicorn main:app" || true
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &

访问：
http://8.219.139.140:8012/login
登录后进入新版 V5.0 Dashboard 风格首页。
