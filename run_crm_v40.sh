#!/bin/bash
cd ~/crm || exit 1

echo "[1/4] Stop old auto tasks..."
pkill -f lead_collector.py 2>/dev/null || true
pkill -f auto_outreach_v32.py 2>/dev/null || true
pkill -f auto_outreach_v33.py 2>/dev/null || true
pkill -f auto_outreach_v34.py 2>/dev/null || true

echo "[2/4] Run V4 targeted GPS collector..."
./venv/bin/python lead_collector_v40.py

echo "[3/4] Build V3.4 GPS outreach queue from new CRM data..."
./venv/bin/python auto_outreach_v34.py build

echo "[4/4] Preview first 30..."
./venv/bin/python auto_outreach_v34.py preview 30

echo "Files:"
echo " - auto_leads_v40.csv"
echo " - email_queue_v34.csv"
echo "No emails sent automatically."
