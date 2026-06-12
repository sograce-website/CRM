import csv
import datetime
import re
import sqlite3
import smtplib
import time
from email.mime.text import MIMEText

DB = "crm.db"
QUEUE_FILE = "email_queue.csv"
LOG_FILE = "auto_outreach.log"

SMTP_HOST = "smtp.qiye.aliyun.com"
SMTP_PORT = 465
SMTP_USER = "info@sograce.cn"
SMTP_FROM = "info@sograce.cn"

# 为了安全，密码从本机 main.py 读取，不在这里重复写死
def load_smtp_password():
    try:
        text = open("main.py", "r", encoding="utf-8", errors="ignore").read()
        m = re.search(r'SMTP_PASSWORD\s*=\s*"([^"]+)"', text)
        return m.group(1) if m else ""
    except Exception:
        return ""

SMTP_PASSWORD = load_smtp_password()

SUBJECT = "GPS SOS Watch and GPS Tracking Devices Cooperation"

BODY = """Dear Team,

We are SOGRACE, a professional GPS tracking device manufacturer from China.

We provide:
- Elderly GPS SOS watches
- Personal GPS trackers
- Pet GPS trackers
- Vehicle GPS trackers
- Asset GPS tracking devices
- GPS platform and APP solutions

We support OEM / ODM customization, APP branding, platform integration, and bulk supply for distributors.

Would you be interested in receiving our latest catalog and cooperation options?

Best regards,
Chen
SOGRACE
www.sograce.cn
info@sograce.cn

If this message is not relevant, please reply "unsubscribe" and we will not contact you again.
"""

BAD_EMAIL_WORDS = [
    "noreply", "no-reply", "example.com", "test@", "admin@", "webmaster@",
    "support-web", "frontend", "jquery", "bootstrap", "sentry", "wixpress",
    "wordpress", "cloudflare", "github", "npm"
]

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def valid_email(email):
    email = (email or "").strip().lower()
    if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
        return False
    if any(x in email for x in BAD_EMAIL_WORDS):
        return False
    return True

def load_existing_history_emails(conn):
    rows = conn.execute("SELECT history FROM leads WHERE history IS NOT NULL AND history!=''").fetchall()
    sent = set()
    for (history,) in rows:
        for e in re.findall(r"To:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", history or ""):
            sent.add(e.strip().lower())
    return sent

def build_queue(limit=300):
    conn = sqlite3.connect(DB)
    sent_before = load_existing_history_emails(conn)

    rows = conn.execute("""
        SELECT id, company, email, website, country, note, history
        FROM leads
        WHERE email!=''
          AND email LIKE '%@%'
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    out = []
    seen = set()

    for lead_id, company, email, website, country, note, history in rows:
        email = (email or "").strip().lower()
        if not valid_email(email):
            continue
        if email in seen or email in sent_before:
            continue
        if history and ("Bulk Email Sent" in history or "Auto Outreach Sent" in history):
            continue

        seen.add(email)
        out.append({
            "lead_id": lead_id,
            "company": company or "",
            "email": email,
            "website": website or "",
            "country": country or "",
            "subject": SUBJECT,
            "body": BODY,
            "status": "READY",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sent_at": "",
            "error": ""
        })

    with open(QUEUE_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "lead_id", "company", "email", "website", "country",
            "subject", "body", "status", "created_at", "sent_at", "error"
        ])
        writer.writeheader()
        writer.writerows(out)

    log(f"QUEUE BUILT: {len(out)} emails ready in {QUEUE_FILE}")

def send_queue(max_send=10, delay_seconds=20):
    if not SMTP_PASSWORD:
        log("ERROR: SMTP_PASSWORD not found in main.py")
        return

    try:
        rows = list(csv.DictReader(open(QUEUE_FILE, "r", encoding="utf-8-sig")))
    except FileNotFoundError:
        log("ERROR: email_queue.csv not found. Run: python auto_outreach_v32.py build")
        return

    conn = sqlite3.connect(DB)
    sent_count = 0

    for r in rows:
        if sent_count >= max_send:
            break
        if r.get("status") != "READY":
            continue

        lead_id = r.get("lead_id")
        email = (r.get("email") or "").strip().lower()
        subject = r.get("subject") or SUBJECT
        body = r.get("body") or BODY

        if not valid_email(email):
            r["status"] = "SKIPPED"
            r["error"] = "invalid email"
            continue

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = email

            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
            server.quit()

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            old = conn.execute("SELECT history FROM leads WHERE id=?", (lead_id,)).fetchone()
            history = old[0] if old and old[0] else ""
            history += f"\n{now} Auto Outreach Sent | To: {email} | Subject: {subject}"
            conn.execute(
                "UPDATE leads SET history=?, status='CONTACTED', last_contact=? WHERE id=?",
                (history, now, lead_id)
            )
            conn.commit()

            r["status"] = "SENT"
            r["sent_at"] = now
            r["error"] = ""
            sent_count += 1
            log(f"SENT: {email}")

            time.sleep(delay_seconds)

        except Exception as e:
            r["status"] = "FAILED"
            r["error"] = str(e)
            log(f"FAILED: {email} | {e}")

    conn.close()

    with open(QUEUE_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "lead_id", "company", "email", "website", "country",
            "subject", "body", "status", "created_at", "sent_at", "error"
        ])
        writer.writeheader()
        writer.writerows(rows)

    log(f"SEND FINISHED: {sent_count} emails sent")

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"

    if cmd == "build":
        build_queue()
    elif cmd == "send":
        max_send = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        send_queue(max_send=max_send)
    elif cmd == "build_send":
        max_send = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        build_queue()
        send_queue(max_send=max_send)
    else:
        print("Usage:")
        print("  python auto_outreach_v32.py build")
        print("  python auto_outreach_v32.py send 10")
        print("  python auto_outreach_v32.py build_send 10")
