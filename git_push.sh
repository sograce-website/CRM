#!/bin/bash#!/bin/bash
cd /home/admin/crm || exit echo "===== SOGRACE CRM AUTO PUSH =====" git add . git commit -m "CRM Auto Backup $(date '+%Y-%m-%d %H:%M:%S')" 2>/dev/null || echo "No changes" git 
push origin main echo "" echo "================================" echo "CRM Backup Finished" echo "GitHub:" echo "https://github.com/sograce-website/CRM" echo 
"================================" cd /home/admin/crm || exit echo "===== SOGRACE CRM AUTO PUSH =====" git add . git commit -m "CRM Auto Backup $(date '+%Y-%m-%d %H:%M:%S')" 
2>/dev/null || echo "No changes" git push origin main
echo "===== CRM Backup Finished ====="

