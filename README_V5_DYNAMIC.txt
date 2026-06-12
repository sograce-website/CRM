SOGRACE CRM V5.0 Professional Dynamic Dashboard

这个版本：
1. 保留原来的登录、邮件中心、自动采集、用户管理、客户详情等功能。
2. 只替换首页版面。
3. 数据动态读取 /home/admin/crm/crm.db。
4. / 和 /dashboard 都可以进入新版 Dashboard。
5. Recent Leads 显示最近50个，避免900+客户导致首页卡顿。

上传：
把压缩包里的 main.py 上传 GitHub 覆盖旧 main.py。

服务器：
cd ~/crm
git pull origin main
python3 -m py_compile main.py
pkill -f "uvicorn main:app" || true
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &

访问：
http://crm.sograce.cn
或
http://8.219.139.140:8012
