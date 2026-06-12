#!/bin/bash
set -e

cd /home/admin/crm

echo "===== 1. STOP OLD UVICORN ====="
pkill -f "uvicorn main:app" || true
sleep 2

echo "===== 2. CHECK main.py ====="
if python3 -m py_compile main.py; then
  echo "main.py OK"
else
  echo "main.py has error, restoring latest backup..."
  BACKUP=$(ls -t main_backup_before_new_auto_collect_*.py main_backup_auto_collect_v522_*.py main_backup_dashboard_auto_collect_v11_*.py 2>/dev/null | head -1)
  if [ -z "$BACKUP" ]; then
    echo "ERROR: no main backup found"
    exit 1
  fi
  echo "Restore: $BACKUP"
  cp "$BACKUP" main.py
  python3 -m py_compile main.py
fi

echo "===== 3. CHECK auto_collect_new.py ====="
python3 -m py_compile auto_collect_new.py

echo "===== 4. REINSTALL NEW AUTO COLLECT ROUTES ====="
python3 install_auto_collect_new.py
python3 -m py_compile main.py

echo "===== 5. START CRM ====="
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &
sleep 5

echo "===== 6. CHECK UVICORN ====="
ps -ef | grep "uvicorn main:app" | grep -v grep || {
  echo "ERROR: uvicorn not running"
  tail -n 80 crm.log
  exit 1
}

echo "===== 7. LOCAL TEST ====="
curl -I http://127.0.0.1:8000/ || true
curl -I http://127.0.0.1:8000/auto_collect_new || true

echo "===== 8. LAST CRM LOG ====="
tail -n 80 crm.log

echo "DONE: CRM should be back. Open https://crm.sograce.cn"
