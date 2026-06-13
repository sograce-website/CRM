#!/bin/bash
set -e
cd ~/crm

cp auto_send_v40.py auto_send_v40_backup_$(date +%Y%m%d%H%M%S).py 2>/dev/null || true
cp crm_bulk_send.log crm_bulk_send_backup_$(date +%Y%m%d%H%M%S).log 2>/dev/null || true

chmod +x auto_send_v52_crm.py

echo "AUTO EMAIL V5.2 installed OK"
echo "Preview: ./venv/bin/python auto_send_v52_crm.py preview 20"
echo "Send:    ./venv/bin/python auto_send_v52_crm.py send 50"
