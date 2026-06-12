#!/bin/bash
cd ~/crm || exit 1

echo "[1/3] Stop V3.2 auto sender if running..."
pkill -f auto_outreach_v32.py 2>/dev/null || true

echo "[2/3] Build V3.3 precision queue..."
./venv/bin/python auto_outreach_v33.py build

echo "[3/3] Preview first 30 quality leads..."
./venv/bin/python auto_outreach_v33.py preview 30

echo "V3.3 only builds and previews queue. It does NOT send emails automatically."
echo "Queue file: email_queue_v33.csv"
