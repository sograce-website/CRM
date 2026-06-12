#!/bin/bash
# CRM V4.1 Full Pipeline: collect GPS leads -> build queue -> preview -> send limited emails

cd ~/crm || exit 1

SEND_LIMIT=${1:-5}

echo "========================================"
echo "CRM V4.1 Auto Lead + Safe Email Pipeline"
echo "Send limit: $SEND_LIMIT"
echo "========================================"

echo "[1/7] Stop old outreach tasks..."
pkill -f auto_outreach_v32.py 2>/dev/null || true
pkill -f auto_outreach_v33.py 2>/dev/null || true
pkill -f auto_outreach_v34.py 2>/dev/null || true
pkill -f auto_send_v40.py 2>/dev/null || true

echo "[2/7] Check required files..."
for f in lead_collector_v40.py auto_outreach_v34.py auto_send_v40.py; do
  if [ ! -f "$f" ]; then
    echo "ERROR: Missing $f"
    exit 1
  fi
done

echo "[3/7] Run V4 targeted GPS collector..."
./venv/bin/python lead_collector_v40.py

echo "[4/7] Build precision GPS email queue..."
./venv/bin/python auto_outreach_v34.py build

echo "[5/7] Preview first 30 qualified leads..."
./venv/bin/python auto_send_v40.py preview 30

echo "========================================"
echo "Safety check:"
echo "The script will send only $SEND_LIMIT emails."
echo "Press Ctrl+C within 8 seconds to cancel."
echo "========================================"
sleep 8

echo "[6/7] Send limited outreach emails..."
./venv/bin/python auto_send_v40.py send "$SEND_LIMIT"

echo "[7/7] Show recent send log..."
tail -n 50 auto_send_v40.log 2>/dev/null || echo "No auto_send_v40.log yet"

echo "========================================"
echo "DONE"
echo "Generated files:"
echo " - auto_leads_v40.csv"
echo " - email_queue_v34.csv"
echo " - auto_send_v40.log"
echo "========================================"
