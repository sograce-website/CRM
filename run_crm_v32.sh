#!/bin/bash

cd ~/crm || exit 1

echo "[1/5] Build email queue..."
./venv/bin/python auto_outreach_v32.py build

echo "[2/5] Send first 10 emails..."
./venv/bin/python auto_outreach_v32.py send 10

echo "[3/5] Show queue summary..."
ls -lh email_queue.csv

echo "[4/5] Show recent outreach log..."
tail -n 30 auto_outreach.log

echo "[5/5] Done."
