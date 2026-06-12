#!/bin/bash
set -e

cd /home/admin/crm

echo "=== 1. backup current main.py ==="
cp main.py main_backup_before_fix_nginx_$(date +%Y%m%d_%H%M).py

echo "=== 2. restore v43 ==="
cp main_v43_professional.py main.py

echo "=== 3. clear python cache ==="
rm -rf __pycache__

echo "=== 4. compile main.py ==="
python3 -m py_compile main.py

echo "=== 5. restart crm service ==="
sudo systemctl restart crm
sleep 3

echo "=== 6. test crm service ==="
sudo systemctl status crm --no-pager

echo "=== 7. test local backend ==="
curl -s http://127.0.0.1:8000/login | head -10

echo "=== 8. test nginx config ==="
sudo nginx -t

echo "=== 9. reload nginx ==="
sudo systemctl reload nginx

echo "=== 10. test https domain from server ==="
curl -k https://crm.sograce.cn/login | head -10

echo "=== DONE ==="
