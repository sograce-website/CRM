#!/bin/bash
set -e
cd ~/crm

cp auto_collect_v14_global.py auto_collect_v14_global_backup_$(date +%Y%m%d%H%M%S).py 2>/dev/null || true
cp auto_collect_status.json auto_collect_status_backup_$(date +%Y%m%d%H%M%S).json 2>/dev/null || true

cat > auto_collect_status.json <<'JSON'
{
  "version": "AUTO COLLECT V1.5 GLOBAL PRO NO CHINA",
  "status": "ready",
  "message": "Auto Collect V1.5 ready",
  "found": 0,
  "saved": 0,
  "skipped": 0,
  "failed": 0,
  "email_found": 0,
  "current_keyword": "",
  "current_site": "",
  "updated": ""
}
JSON

chmod +x auto_collect_v15_global_pro.py run_auto_collect_v15.sh

echo "AUTO COLLECT V1.5 installed OK"
echo "Run: ./run_auto_collect_v15.sh"
