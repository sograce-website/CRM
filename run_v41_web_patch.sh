#!/bin/bash
# V4.1 Web Patch Installer for SOGRACE CRM
# Assumes main_v41_web.py is in ~/crm/

CRM_DIR=~/crm
MAIN_FILE="$CRM_DIR/main.py"
WEB_FILE="$CRM_DIR/main_v41_web.py"
BACKUP_FILE="$CRM_DIR/main_backup.py"

echo "[*] Backing up current main.py to main_backup.py"
cp "$MAIN_FILE" "$BACKUP_FILE"

echo "[*] Reading web module from main_v41_web.py"
WEB_ROUTES=$(awk '/@app.get\(/, /return HTMLResponse/' "$WEB_FILE")

echo "[*] Appending Web routes to main.py"
echo -e "\n\n# ===== V4.1 Web Patch =====" >> "$MAIN_FILE"
echo "$WEB_ROUTES" >> "$MAIN_FILE"

echo "[*] Patch applied successfully. You can now restart the CRM service."
