# collect_leads.py
# SOGRACE CRM Auto Pipeline helper
# 功能：Auto Pipeline 调用 collect_ready_leads()
# 流程：运行 lead_collector.py，然后把 auto_leads.csv 合并进 email_queue.csv / email_queue_v34.csv

from pathlib import Path
import csv
import subprocess
import datetime

CRM_DIR = Path("/home/admin/crm")
LOG_FILE = CRM_DIR / "pipeline.log"

def _log(msg: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")

def _find_email(value: str) -> str:
    import re
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value or "")
    return m.group(0).lower() if m else ""

def _load_existing_emails(queue_file: Path):
    emails = set()
    if not queue_file.exists():
        return emails
    try:
        with queue_file.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                e = _find_email(r.get("email", ""))
                if e:
                    emails.add(e)
    except Exception as e:
        _log(f"QUEUE_READ_ERROR: {e}")
    return emails

def collect_ready_leads():
    _log("PIPELINE COLLECT START")

    # 1. 先运行现有采集器
    try:
        subprocess.run(
            ["./venv/bin/python", "lead_collector.py"],
            cwd=str(CRM_DIR),
            stdout=open(CRM_DIR / "lead_collector.log", "a"),
            stderr=open(CRM_DIR / "lead_collector.log", "a"),
            timeout=1800,
        )
        _log("LEAD_COLLECTOR FINISHED")
    except Exception as e:
        _log(f"LEAD_COLLECTOR_ERROR: {e}")

    # 2. 找采集结果文件
    source_files = [
        CRM_DIR / "auto_leads.csv",
        CRM_DIR / "auto_leads_v40.csv",
        CRM_DIR / "gps_watch_leads.csv",
    ]
    source_file = next((p for p in source_files if p.exists()), None)
    if not source_file:
        _log("NO_AUTO_LEADS_FILE_FOUND")
        return 0

    # 3. 写入队列文件，优先使用 email_queue_v34.csv
    queue_file = CRM_DIR / "email_queue_v34.csv"
    if not queue_file.exists():
        queue_file = CRM_DIR / "email_queue.csv"

    existing = _load_existing_emails(queue_file)

    fieldnames = ["lead_id", "company", "email", "website", "country", "score", "status"]
    rows_to_add = []

    try:
        with source_file.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for i, r in enumerate(reader, start=1):
                company = r.get("Company") or r.get("company") or r.get("Name") or r.get("name") or ""
                email = _find_email(r.get("Email") or r.get("email") or r.get("Emails") or r.get("emails") or "")
                website = r.get("Website") or r.get("website") or r.get("URL") or r.get("url") or ""
                country = r.get("Country") or r.get("country") or ""
                score = r.get("Score") or r.get("score") or "50"

                if not email or email in existing:
                    continue

                existing.add(email)
                rows_to_add.append({
                    "lead_id": "",
                    "company": company,
                    "email": email,
                    "website": website,
                    "country": country,
                    "score": score,
                    "status": "READY",
                })
    except Exception as e:
        _log(f"AUTO_LEADS_READ_ERROR: {e}")
        return 0

    if not rows_to_add:
        _log("NO_NEW_READY_LEADS")
        return 0

    write_header = not queue_file.exists() or queue_file.stat().st_size == 0
    try:
        with queue_file.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(rows_to_add)
        _log(f"QUEUE_BUILD_DONE added={len(rows_to_add)} file={queue_file.name}")
    except Exception as e:
        _log(f"QUEUE_WRITE_ERROR: {e}")
        return 0

    return len(rows_to_add)
