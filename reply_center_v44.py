# reply_center_v44.py
# SOGRACE CRM V4.4 P1 - Reply Center
# 作用：读取 info@sograce.cn 收件箱，匹配 CRM leads 邮箱，自动把客户状态更新为 REPLIED，并写入日志。
# 运行：cd ~/crm && ./venv/bin/python reply_center_v44.py

import imaplib
import email
import sqlite3
import datetime
import re
from pathlib import Path
from email.header import decode_header, make_header

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"
LOG_FILE = CRM_DIR / "reply_center.log"

# 阿里云企业邮箱 IMAP
IMAP_HOST = "imap.qiye.aliyun.com"
IMAP_PORT = 993

# 直接从 main.py 读取邮箱配置，避免重复写密码
def load_mail_config():
    ns = {}
    main_py = CRM_DIR / "main.py"
    text = main_py.read_text(encoding="utf-8", errors="ignore")

    for key in ["SMTP_USER", "SMTP_PASSWORD"]:
        m = re.search(rf'^{key}\s*=\s*[\'"](.+?)[\'"]', text, re.M)
        ns[key] = m.group(1) if m else ""

    user = ns.get("SMTP_USER") or "info@sograce.cn"
    password = ns.get("SMTP_PASSWORD") or ""
    return user, password

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")

def decode_text(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value

def extract_email(addr):
    if not addr:
        return ""
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", addr)
    return m.group(0).lower() if m else ""

def get_body(msg):
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if ctype == "text/plain" and "attachment" not in disp.lower():
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="ignore")[:2000] if payload else ""
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="ignore")[:2000] if payload else ""
    except Exception as e:
        return f"[BODY_READ_ERROR] {e}"
    return ""

def ensure_replied_status_supported():
    # 不改表结构，只是后面把 leads.status 写成 REPLIED。
    # 当前 status 字段是 TEXT，可以直接写。
    pass

def update_lead_reply(sender_email, subject, reply_time, body):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 用 email 字段匹配 lead，兼容一个字段里多个邮箱的情况
    row = c.execute("""
        SELECT id, company, history, status
        FROM leads
        WHERE lower(email) LIKE ?
        ORDER BY id DESC
        LIMIT 1
    """, (f"%{sender_email.lower()}%",)).fetchone()

    if not row:
        conn.close()
        return False, None, None

    lead_id, company, history, old_status = row
    history = history or ""
    note = body.replace("\r", " ").replace("\n", " ")[:500]

    mark = f"Reply Received | From: {sender_email} | Subject: {subject}"
    if mark not in history:
        history += f"\n{reply_time} {mark}\nReply Preview: {note}"

    c.execute("""
        UPDATE leads
        SET status='REPLIED', history=?, last_contact=?
        WHERE id=?
    """, (history, reply_time, lead_id))

    conn.commit()
    conn.close()
    return True, lead_id, company

def fetch_replies(limit=50):
    user, password = load_mail_config()
    if not user or not password:
        log("ERROR missing SMTP_USER or SMTP_PASSWORD in main.py")
        return

    log(f"REPLY CHECK START user={user}")

    ensure_replied_status_supported()

    matched = 0
    unmatched = 0
    checked = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(user, password)
        mail.select("INBOX")

        # 只抓未读邮件，避免重复处理太多历史邮件
        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            log(f"IMAP SEARCH ERROR status={status}")
            mail.logout()
            return

        ids = data[0].split()
        ids = ids[-limit:] if ids else []

        for mid in ids:
            checked += 1
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK" or not msg_data:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender_raw = decode_text(msg.get("From", ""))
            sender_email = extract_email(sender_raw)
            subject = decode_text(msg.get("Subject", ""))
            date_raw = decode_text(msg.get("Date", ""))
            body = get_body(msg)

            reply_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            if not sender_email:
                unmatched += 1
                log(f"UNMATCHED no sender | subject={subject}")
                continue

            ok, lead_id, company = update_lead_reply(sender_email, subject, reply_time, body)
            if ok:
                matched += 1
                log(f"MATCHED lead_id={lead_id} company={company} from={sender_email} subject={subject}")
                # 标记已读，避免重复抓取
                mail.store(mid, "+FLAGS", "\\Seen")
            else:
                unmatched += 1
                log(f"UNMATCHED from={sender_email} subject={subject} date={date_raw}")

        mail.logout()
        log(f"REPLY CHECK FINISHED checked={checked} matched={matched} unmatched={unmatched}")

    except Exception as e:
        import traceback
        log("REPLY CHECK ERROR: " + str(e))
        log(traceback.format_exc())

if __name__ == "__main__":
    fetch_replies(limit=50)
