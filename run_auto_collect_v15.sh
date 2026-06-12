#!/bin/bash
cd ~/crm
nohup ./venv/bin/python auto_collect_v15_global_pro.py > auto_collect_new.log 2>&1 &
echo "AUTO COLLECT V1.5 started"
echo "Status: https://crm.sograce.cn/auto_collect_new_status"
echo "Log: https://crm.sograce.cn/auto_collect_new_log"
