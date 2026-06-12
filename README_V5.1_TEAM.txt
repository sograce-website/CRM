SOGRACE CRM V5.1 Professional Team Edition

包含完整升级功能：
- Recent Leads（首页最近50条客户）
- Activity Timeline（客户跟进时间轴）
- Sales / Pipeline Ranking（销售与管道排行榜）
- Auto Collect / Auto Email 实时状态
- 用户管理增强（网页新增/删除/修改/禁用/权限管理）
- 保留原有 V5.0 风格和左侧菜单

部署方法：
1. 上传 main.py 到 GitHub 覆盖原来的 main.py
2. 在服务器执行部署脚本 deploy_crm.sh
   或手动执行命令：
   cd ~/crm
   git pull origin main
   python3 -m py_compile main.py
   pkill -f "uvicorn main:app" || true
   nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &

访问：http://crm.sograce.cn
