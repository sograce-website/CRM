#!/bin/bash
set -e
cd ~/crm

cp auto_collect_v13_global.py auto_collect_v13_global_backup_$(date +%Y%m%d%H%M%S).py 2>/dev/null || true
cp auto_collect_status.json auto_collect_status_backup_$(date +%Y%m%d%H%M%S).json 2>/dev/null || true

cat > auto_collect_status.json <<'JSON'
{
  "version": "AUTO COLLECT V1.4 GLOBAL NO CHINA",
  "status": "ready",
  "message": "Auto Collect V1.4 ready",
  "found": 0,
  "saved": 0,
  "skipped": 0,
  "failed": 0,
  "current_keyword": "",
  "current_site": "",
  "updated": ""
}
JSON

chmod +x auto_collect_v14_global.py run_auto_collect_v14.sh

echo "AUTO COLLECT V1.4 installed OK"
echo "Run: ./run_auto_collect_v14.sh"
