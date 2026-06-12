
# lead_collector_v52.py
# V5.2 Auto Collect Core for SOGRACE CRM
# 基于V5.1环境升级的自动采集模块

import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import time

KEYWORDS = ["GPS Watch", "GPS SOS", "Elderly Tracker"]
MAX_RESULTS = 10
OUTPUT_FILE = "v52_collected_leads.xlsx"

def collect_leads():
    all_leads = []
    for kw in KEYWORDS:
        print(f"[{datetime.datetime.now()}] Collecting for keyword: {kw}")
        # 模拟采集
        for i in range(1, MAX_RESULTS+1):
            lead = {
                "Company": f"{kw} Company {i}",
                "Email": f"info{i}@example.com",
                "Country": "Germany",
                "CollectedAt": datetime.datetime.now()
            }
            all_leads.append(lead)
            print(f"  Collected: {lead['Company']} - {lead['Email']}")
            time.sleep(0.2)
    df = pd.DataFrame(all_leads)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"[{datetime.datetime.now()}] Collection complete. {len(all_leads)} leads saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    collect_leads()
