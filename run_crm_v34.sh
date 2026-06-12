#!/bin/bash
cd ~/crm || exit 1

echo "[1/4] Stop V3.2/V3.3 auto sender if running..."
pkill -f auto_outreach_v32.py 2>/dev/null || true
pkill -f auto_outreach_v33.py 2>/dev/null || true

echo "[2/4] Build V3.4 GPS industry queue..."
./venv/bin/python auto_outreach_v34.py build

echo "[3/4] Preview first 30 GPS leads..."
./venv/bin/python auto_outreach_v34.py preview 30

echo "[4/4] Done."
echo "V3.4 only builds and previews queue. It does NOT send emails automatically."
echo "Queue file: email_queue_v34.csv"
