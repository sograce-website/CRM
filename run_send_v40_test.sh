#!/bin/bash
cd ~/crm || exit 1

echo "[1/3] Preview current V4/V3.4 quality queue..."
./venv/bin/python auto_send_v40.py preview 20

echo "[2/3] Send ONLY 1 test email..."
./venv/bin/python auto_send_v40.py send 1

echo "[3/3] Show recent send log..."
tail -n 30 auto_send_v40.log

echo "Done. This script sends only 1 email for safety."
