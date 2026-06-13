# auto_send_v52_crm.py
# SOGRACE CRM AUTO EMAIL V5.2 P4
# Directly reads crm.db leads table.
# Sends distinct emails only, skips already-sent emails globally.

import sys
import re
import sqlite3
import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

DB = "/home/admin/crm/crm.db"
LOG = "/home/admin/crm/crm_bulk_send.log"

SMTP_HOST = "smtp.qiye.aliyun.com"
SMTP_PORT = 465
SMTP_USER = "info@sograce.cn"
SMTP_PASSWORD = "mtpfRVuYzZrz8Vnr"
SMTP_FROM = "info@sograce.cn"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL_WORDS = ["example.com","domain.com","test.com","yourdomain","noreply","no-reply","donotreply","privacy@","abuse@",".png",".jpg",".jpeg",".webp",".gif"]

SUBJECT = "GPS SOS Watch and Medical Alert Device Supplier"

BODY = """Dear Team,

This is Chen from SOGRACE.

We are a professional supplier of GPS SOS watches, elderly safety watches, medical alert GPS devices, and GPS tracking platform solutions.

Our products are suitable for:
- Elderly care
- Medical alert service providers
- GPS tracking distributors
- Personal safety and lone worker solutions
- OEM / ODM projects

If you are interested, I can send you our latest catalog and product details.

Best regards,
Chen
SOGRACE
www.sograce.cn
info@sograce.cn
"""

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(line):
    msg = f"{now()} {line}"
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def clean_email(raw):
    raw = raw or ""
    emails = EMAIL_RE.findall(raw)
    for e in emails:
        e = e.strip().lower()
        if any(b in e for b in BAD_EMAIL_WORDS):
            continue
        return e
    return ""

def get_sent_email_set(conn):
    rows = conn.execute("SELECT history FROM leads WHERE history LIKE '%To:%'").fetchall()
    sent = set()
    for (h,) in rows:
        for e in EMAIL_RE.findall(h or ""):
            sent.add(e.lower())
    return sent

def get_candidates(limit):
    conn = sqlite3.connect(DB)
    sent_global = get_sent_email_set(conn)
    rows = conn.execute("""
        SELECT id, company, email, website, country, source, history
        FROM leads
        WHERE email IS NOT NULL
          AND email <> ''
          AND email LIKE '%@%'
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    result = []
    seen = set()

    for lead_id, company, email_raw, website, country, source, history in rows:
        email = clean_email(email_raw)
        if not email:
            continue
        if email in seen:
            continue
        if email in sent_global:
            continue
        seen.add(email)
        result.append((lead_id, company or "", email, website or "", country or "", source or "", history or ""))
        if len(result) >= limit:
            break

    return result

def send_one(to_email):
    msg = MIMEText(BODY, "plain", "utf-8")
    msg["Subject"] = Header(SUBJECT, "utf-8")
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(SMTP_FROM, [to_email], msg.as_string())
    server.quit()

def update_history(lead_id, old_history, line, status=None):
    conn = sqlite3.connect(DB)
    history = (old_history or "") + "\n" + line
    if status:
        conn.execute("UPDATE leads SET history=?, status=?, last_contact=? WHERE id=?", (history, status, now(), lead_id))
    else:
        conn.execute("UPDATE leads SET history=?, last_contact=? WHERE id=?", (history, now(), lead_id))
    conn.commit()
    conn.close()

def preview(limit):
    rows = get_candidates(limit)
    print(f"PREVIEW {len(rows)} unique candidates")
    for r in rows:
        lead_id, company, email, website, country, source, history = r
        print(f"{lead_id} | {company} | {email} | {country} | {website}")

def send(limit):
    rows = get_candidates(limit)
    sent = failed = skipped = 0
    log(f"V5.2 P4 SEND START target={limit} candidates={len(rows)}")

    for lead_id, company, email, website, country, source, history in rows:
        try:
            send_one(email)
            line = f"{now()} Auto Email Sent | To: {email} | Subject: {SUBJECT}"
            update_history(lead_id, history, line, status="CONTACTED")
            sent += 1
            log(f"SENT: {email} | {company} | {website}")
        except Exception as e:
            line = f"{now()} Auto Email Failed | To: {email} | {str(e)}"
            update_history(lead_id, history, line)
            failed += 1
            log(f"FAILED: {email} | {company} | {str(e)}")

    log(f"V5.2 P4 SEND FINISHED: sent={sent} failed={failed} skipped={skipped}")

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python auto_send_v52_crm.py preview 20")
        print("  python auto_send_v52_crm.py send 50")
        return
    mode = sys.argv[1].lower()
    try:
        limit = int(sys.argv[2])
    except Exception:
        limit = 20
    limit = max(1, min(limit, 500))
    if mode == "preview":
        preview(limit)
    elif mode == "send":
        send(limit)
    else:
        print("Unknown mode:", mode)

if __name__ == "__main__":
    main()
