#!/bin/bash
# SOGRACE CRM Auto Collect V1.1 + Auto Email starter
# 用法：cd ~/crm && chmod +x start_auto_collect_and_email_v11.sh && ./start_auto_collect_and_email_v11.sh

set -e
cd /home/admin/crm

echo "===== 1. START / RESTART CRM ====="
pkill -f "uvicorn main:app" || true
sleep 2
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &
sleep 5

echo "===== 2. CHECK CRM ====="
ps -ef | grep "uvicorn main:app" | grep -v grep || {
  echo "ERROR: CRM uvicorn not running"
  tail -n 80 crm.log
  exit 1
}

curl -s -I http://127.0.0.1:8000/ | head -5 || true

echo "===== 3. RUN AUTO COLLECT V1.1 ====="
> auto_collect_new.log
> auto_collect_debug_urls.txt
./venv/bin/python auto_collect_new.py

echo "===== 4. AUTO COLLECT STATUS ====="
cat auto_collect_status.json || true
echo
tail -n 80 auto_collect_new.log || true

SAVED=$(python3 - <<'PY'
import json
from pathlib import Path
p=Path("/home/admin/crm/auto_collect_status.json")
try:
    print(json.loads(p.read_text()).get("saved",0))
except Exception:
    print(0)
PY
)

echo "Saved leads: $SAVED"

if [ "$SAVED" = "0" ]; then
  echo "No new leads saved. Skip auto email."
  exit 0
fi

echo "===== 5. RUN AUTO EMAIL ====="
echo "Try CRM bulk_send/50 route first..."
curl -s http://127.0.0.1:8000/bulk_send/50 > auto_email_run_result.html || true

echo "===== 6. EMAIL RESULT ====="
if [ -f crm_bulk_send.log ]; then
  tail -n 80 crm_bulk_send.log
else
  echo "crm_bulk_send.log not found. Check auto_email_run_result.html:"
  tail -n 80 auto_email_run_result.html || true
fi

echo "===== DONE ====="
echo "CRM: https://crm.sograce.cn"
echo "New Auto Collect Log: https://crm.sograce.cn/auto_collect_new_log"
echo "New Auto Collect Status: https://crm.sograce.cn/auto_collect_new_status"
