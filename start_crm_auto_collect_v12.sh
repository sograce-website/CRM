#!/bin/bash
# =========================================================
# SOGRACE CRM + V12 AUTO COLLECT + DASHBOARD STATUS STARTER
# =========================================================
# 用法：
# cd ~/crm
# chmod +x start_crm_auto_collect_v12.sh
# ./start_crm_auto_collect_v12.sh

set -e

CRM_DIR="/home/admin/crm"
VENV_PY="$CRM_DIR/venv/bin/python"
UVICORN="$CRM_DIR/venv/bin/uvicorn"

CRM_LOG="$CRM_DIR/crm.log"
AUTO_COLLECT_LOG="$CRM_DIR/auto_collect_new.log"
AUTO_COLLECT_STATUS="$CRM_DIR/auto_collect_status.json"
AUTO_EMAIL_STATUS="$CRM_DIR/auto_email_status.json"

cd "$CRM_DIR"

echo "===== 1. STOP OLD UVICORN ====="
pkill -f "uvicorn main:app" || true
sleep 2

echo "===== 2. CHECK FILES ====="
if [ ! -f "$CRM_DIR/main.py" ]; then
  echo "ERROR: main.py not found"
  exit 1
fi

if [ ! -f "$CRM_DIR/auto_collect_new.py" ]; then
  echo "ERROR: auto_collect_new.py not found"
  exit 1
fi

echo "===== 3. COMPILE CHECK ====="
python3 -m py_compile "$CRM_DIR/main.py"
python3 -m py_compile "$CRM_DIR/auto_collect_new.py"

echo "===== 4. WRITE DASHBOARD RUNNING STATUS ====="
cat > "$AUTO_COLLECT_STATUS" <<EOF
{
  "version": "AUTO COLLECT V1.2 GLOBAL NO CHINA",
  "status": "Running",
  "message": "CRM starter launched Auto Collect V12",
  "found": 0,
  "saved": 0,
  "skipped": 0,
  "failed": 0,
  "current_keyword": "",
  "current_site": "",
  "updated": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

cat > "$AUTO_EMAIL_STATUS" <<EOF
{
  "version": "AUTO EMAIL",
  "status": "Ready",
  "message": "Waiting for new collected leads",
  "sent": 0,
  "failed": 0,
  "skipped": 0,
  "updated": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

echo "===== 5. START CRM ====="
nohup "$UVICORN" main:app --host 0.0.0.0 --port 8000 > "$CRM_LOG" 2>&1 &
sleep 5

echo "===== 6. CHECK CRM PROCESS ====="
ps -ef | grep "uvicorn main:app" | grep -v grep || {
  echo "ERROR: uvicorn not running"
  tail -n 80 "$CRM_LOG"
  exit 1
}

echo "===== 7. LOCAL CRM TEST ====="
curl -s -I http://127.0.0.1:8000/ | head -5 || true
curl -s -I http://127.0.0.1:8000/auto_collect_new_status | head -5 || true

echo "===== 8. START AUTO COLLECT V12 BACKGROUND ====="
> "$AUTO_COLLECT_LOG"
> "$CRM_DIR/auto_collect_debug_urls.txt"

nohup "$VENV_PY" "$CRM_DIR/auto_collect_new.py" >> "$AUTO_COLLECT_LOG" 2>&1 &
AUTO_PID=$!

echo "Auto Collect PID: $AUTO_PID"
echo "$AUTO_PID" > "$CRM_DIR/auto_collect_new.pid"

sleep 3

echo "===== 9. DASHBOARD STATUS ====="
cat "$AUTO_COLLECT_STATUS" || true
echo
cat "$AUTO_EMAIL_STATUS" || true
echo

echo "===== 10. LOG PREVIEW ====="
tail -n 30 "$AUTO_COLLECT_LOG" || true

echo "===== DONE ====="
echo "CRM: https://crm.sograce.cn"
echo "Auto Collect Status: https://crm.sograce.cn/auto_collect_new_status"
echo "Auto Collect Log: https://crm.sograce.cn/auto_collect_new_log"
echo
echo "服务器查看状态："
echo "cat ~/crm/auto_collect_status.json"
echo "tail -f ~/crm/auto_collect_new.log"
