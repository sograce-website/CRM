import csv
import datetime
import re
import sqlite3
import smtplib
import sys
import time
from email.mime.text import MIMEText

DB = "crm.db"
QUEUE_FILE = "email_queue_v34.csv"
LOG_FILE = "auto_send_v40.log"

SMTP_HOST = "smtp.qiye.aliyun.com"
SMTP_PORT = 465
SMTP_USER = "info@sograce.cn"
SMTP_FROM = "info@sograce.cn"

SAFE_DOMAINS_BLOCK = [
    ".gov", ".edu", ".ac.", ".org",
    "domain.com", "example.com", "test.com",
    "zhihu.com", "splashlearn.com", "brighterly.com", "daum.net",
    "hospital", "clinic", "school", "university", "foundation", "charity"
]

SAFE_EMAIL_BLOCK = [
    "noreply", "no-reply", "admin@", "webmaster@", "abuse@", "privacy@",
    "user@", "test@", "example@", "hello@myselfexploration"
]

EMAIL_RE = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_smtp_password():
    try:
        text = open("main.py", "r", encoding="utf-8", errors="ignore").read()
        m = re.search(r'SMTP_PASSWORD\s*=\s*"([^"]+)"', text)
        return m.group(1) if m else ""
    except Exception:
        return ""

def safe_email(email, website="", company=""):
    email = (email or "").strip().lower()
    text = " ".join([email, website or "", company or ""]).lower()

    if not re.match(EMAIL_RE, email):
        return False, "invalid email"

    for b in SAFE_DOMAINS_BLOCK:
        if b in text:
            return False, f"blocked domain/term {b}"

    for b in SAFE_EMAIL_BLOCK:
        if b in email:
            return False, f"blocked email {b}"

    return True, ""

def update_crm_sent(lead_id, email, subject):
    conn = sqlite3.connect(DB)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    row = conn.execute("SELECT history FROM leads WHERE id=?", (lead_id,)).fetchone()
    history = row[0] if row and row[0] else ""
    history += f"\n{now} V4 Auto Email Sent | To: {email} | Subject: {subject}"

    conn.execute(
        "UPDATE leads SET history=?, status='CONTACTED', last_contact=? WHERE id=?",
        (history, now, lead_id)
    )
    conn.commit()
    conn.close()

def send_queue(max_send=1, delay_seconds=30):
    password = load_smtp_password()
    if not password:
        log("ERROR: SMTP_PASSWORD not found in main.py")
        return

    try:
        rows = list(csv.DictReader(open(QUEUE_FILE, "r", encoding="utf-8-sig")))
    except FileNotFoundError:
        log(f"ERROR: {QUEUE_FILE} not found. Run V4 collector first.")
        return

    sent = 0
    changed = False

    for r in rows:
        if sent >= max_send:
            break

        if r.get("status") != "READY":
            continue

        lead_id = r.get("lead_id", "")
        company = r.get("company", "")
        email = (r.get("email") or "").strip().lower()
        website = r.get("website", "")
        subject = r.get("subject", "GPS SOS Watch and GPS Tracking Devices Cooperation")
        body = r.get("body", "")

        ok, reason = safe_email(email, website, company)
        if not ok:
            r["status"] = "SKIPPED"
            r["error"] = reason
            changed = True
            log(f"SKIPPED: {email} | {reason}")
            continue

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = email

            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
            server.login(SMTP_USER, password)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
            server.quit()

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r["status"] = "SENT"
            r["sent_at"] = now
            r["error"] = ""
            update_crm_sent(lead_id, email, subject)

            sent += 1
            changed = True
            log(f"SENT: {email} | {company} | {website}")

            time.sleep(delay_seconds)

        except Exception as e:
            r["status"] = "FAILED"
            r["error"] = str(e)
            changed = True
            log(f"FAILED: {email} | {e}")

    if changed:
        with open(QUEUE_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    log(f"V4 SEND FINISHED: sent={sent}")

def preview(n=20):
    try:
        rows = list(csv.DictReader(open(QUEUE_FILE, "r", encoding="utf-8-sig")))
    except FileNotFoundError:
        print(f"{QUEUE_FILE} not found")
        return

    print("lead_id,company,email,website,country,score,status")
    for r in rows[:n]:
        print(",".join([
            r.get("lead_id",""),
            (r.get("company","") or "").replace(",", " "),
            r.get("email",""),
            r.get("website",""),
            r.get("country",""),
            r.get("score",""),
            r.get("status",""),
        ]))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"

    if cmd == "preview":
        preview(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "send":
        max_send = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        send_queue(max_send=max_send)
    else:
        print("Usage:")
        print("  python auto_send_v40.py preview 20")
        print("  python auto_send_v40.py send 1")
