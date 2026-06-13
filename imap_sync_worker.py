# imap_sync_worker.py
# SOGRACE CRM V5.2 P5.2 IMAP Reply Sync Worker
import time, imaplib, email, sqlite3, re, datetime
from email.header import decode_header

DB="/home/admin/crm/crm.db"
IMAP_HOST="imap.qiye.aliyun.com"
IMAP_PORT=993
IMAP_USER="info@sograce.cn"
IMAP_PASSWORD="mtpfRVuYzZrz8Vnr"

EMAIL_RE=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SYSTEM_SENDERS=["no-reply","noreply","postmaster","mailer-daemon","mailsupport","bounce"]
SYSTEM_SUBJECTS=["undeliverable","delivery status","delivery failed","mail delivery","returned mail","failure notice","退信","验证","verification","requires verification"]

def db(): return sqlite3.connect(DB)

def init():
    conn=db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS email_replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_uid TEXT UNIQUE,
        sender TEXT,
        sender_email TEXT,
        subject TEXT,
        received_time TEXT,
        body TEXT,
        status TEXT DEFAULT 'UNREAD',
        owner TEXT DEFAULT '',
        lead_id INTEGER DEFAULT 0,
        category TEXT DEFAULT 'CUSTOMER',
        created_at TEXT
    )
    """)
    cols=[x[1] for x in conn.execute("PRAGMA table_info(email_replies)").fetchall()]
    if "category" not in cols:
        conn.execute("ALTER TABLE email_replies ADD COLUMN category TEXT DEFAULT 'CUSTOMER'")
    conn.commit(); conn.close()

def dec(v):
    if not v: return ""
    try:
        out=""
        for t,e in decode_header(v):
            out += t.decode(e or "utf-8",errors="ignore") if isinstance(t,bytes) else t
        return out
    except Exception: return str(v)

def sender(raw):
    raw=dec(raw or "")
    m=EMAIL_RE.search(raw)
    em=m.group(0).lower() if m else ""
    name=raw.replace("<"+em+">","").strip().strip('"') if em else raw
    return name,em

def classify(em,sub,b=""):
    s=(em or "").lower(); sub=(sub or "").lower(); b=(b or "").lower()[:2000]
    if any(x in s for x in SYSTEM_SENDERS):
        if "postmaster" in s or "mailer-daemon" in s: return "BOUNCE"
        return "SYSTEM"
    if any(x in sub for x in SYSTEM_SUBJECTS) or "delivery status notification" in b:
        if any(x in sub for x in ["undeliverable","delivery failed","delivery status","returned mail","failure notice"]) or "delivery status notification" in b:
            return "BOUNCE"
        return "SYSTEM"
    return "CUSTOMER"

def body(msg):
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type()=="text/plain":
                    payload=part.get_payload(decode=True)
                    return (payload or b"").decode(part.get_content_charset() or "utf-8", errors="ignore")[:8000]
        payload=msg.get_payload(decode=True)
        return (payload or b"").decode(msg.get_content_charset() or "utf-8", errors="ignore")[:8000]
    except Exception: return ""

def match_lead(em):
    if not em: return 0,""
    conn=db()
    row=conn.execute("SELECT id,COALESCE(owner,'') FROM leads WHERE lower(email) LIKE ? ORDER BY id DESC LIMIT 1",(f"%{em.lower()}%",)).fetchone()
    conn.close()
    return (int(row[0]), row[1] or "") if row else (0,"")

def sync(limit=120):
    init()
    synced=failed=0
    mail=imaplib.IMAP4_SSL(IMAP_HOST,IMAP_PORT)
    mail.login(IMAP_USER,IMAP_PASSWORD)
    mail.select("INBOX")
    typ,data=mail.search(None,"ALL")
    ids=data[0].split()[-limit:] if typ=="OK" else []
    conn=db()
    for mid in ids:
        try:
            typ,msg_data=mail.fetch(mid,"(RFC822)")
            if typ!="OK":
                failed+=1; continue
            msg=email.message_from_bytes(msg_data[0][1])
            uid=mid.decode()
            sub=dec(msg.get("Subject",""))
            s,em=sender(msg.get("From",""))
            dt=msg.get("Date","") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            b=body(msg)
            cat=classify(em,sub,b)
            lead_id,owner=match_lead(em)
            conn.execute("""
            INSERT OR IGNORE INTO email_replies
            (message_uid,sender,sender_email,subject,received_time,body,status,owner,lead_id,category,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,(uid,s,em,sub,dt,b,"UNREAD",owner,lead_id,cat,datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            synced+=1
        except Exception:
            failed+=1
    conn.commit(); conn.close(); mail.logout()
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"synced",synced,"failed",failed,flush=True)

if __name__=="__main__":
    import sys
    mode=sys.argv[1] if len(sys.argv)>1 else "once"
    if mode=="loop":
        while True:
            try: sync()
            except Exception as e: print("ERROR",e,flush=True)
            time.sleep(300)
    else:
        sync()
