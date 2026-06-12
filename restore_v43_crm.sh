#!/bin/bash
set -e

cd /home/admin/crm

echo "=== backup current main.py ==="
cp main.py main_broken_backup_$(date +%Y%m%d_%H%M).py

echo "=== restore main_v43_professional.py ==="
cp main_v43_professional.py main.py

echo "=== clear cache ==="
rm -rf __pycache__

echo "=== compile ==="
python3 -m py_compile main.py

echo "=== restart crm ==="
sudo systemctl restart crm
sleep 3

echo "=== service status ==="
sudo systemctl status crm --no-pager

echo "=== test login ==="
curl -s http://127.0.0.1:8000/login | head -20

echo "=== test home redirect ==="
curl -i http://127.0.0.1:8000/ | head -20

echo "=== done ==="
