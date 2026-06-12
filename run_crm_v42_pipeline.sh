#!/bin/bash
cd ~/crm || exit 1

echo "[1/4] Collect leads..."
./venv/bin/python auto_leads_v42.py

echo "[2/4] Build outreach queue..."
echo "Queue build placeholder"

echo "[3/4] Send limited emails..."
./venv/bin/python auto_send_v42.py

echo "[4/4] Done."
