import csv
import datetime
import re
import sqlite3
import sys

DB = "crm.db"
QUEUE_FILE = "email_queue_v33.csv"
LOG_FILE = "auto_outreach_v33.log"

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

BLOCK_DOMAINS = [
    ".gov", ".edu", ".ac.", ".org",
    "domain.com", "example.com", "test.com",
    "spb.gov.sg", "moh.gov.sg", "qandm.com.sg", "sata.com.sg",
]

BLOCK_WORDS = [
    "government", "ministry", "hospital", "clinic", "medical centre",
    "foundation", "charity", "school", "university", "college",
    "animal", "wildlife", "education", "learning", "course",
    "complaint", "complaints", "cme", "noreply", "no-reply",
    "admin@", "webmaster@", "user@", "hello@myselfexploration",
]

GPS_WORDS = [
    "gps", "tracker", "tracking", "telematics", "fleet", "iot",
    "vehicle tracker", "asset tracker", "personal tracker",
    "gps watch", "sos watch", "location", "security",
    "distributor", "dealer", "supplier", "wholesale", "wholesaler",
]

EMAIL_RE = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def domain_from_email(email):
    return email.split("@")[-1].lower().strip()

def is_blocked(email, company="", website="", note="", country=""):
    text = " ".join([email or "", company or "", website or "", note or "", country or ""]).lower()
    d = domain_from_email(email)

    if not re.match(EMAIL_RE, email or ""):
        return True, "invalid email"

    for b in BLOCK_DOMAINS:
        if b in d or b in text:
            return True, f"blocked domain/term: {b}"

    for w in BLOCK_WORDS:
        if w in text:
            return True, f"blocked word: {w}"

    return False, ""

def gps_score(company="", website="", note="", email="", country=""):
    text = " ".join([company or "", website or "", note or "", email or "", country or ""]).lower()
    score = 0

    for w in GPS_WORDS:
        if w in text:
            score += 20

    # 强相关加分
    if "gps" in text and ("tracker" in text or "tracking" in text):
        score += 40
    if "distributor" in text or "dealer" in text or "supplier" in text:
        score += 20
    if "telematics" in text or "fleet" in text:
        score += 40

    return score

def load_sent_emails(conn):
    sent = set()
    rows = conn.execute("SELECT history FROM leads WHERE history IS NOT NULL AND history!=''").fetchall()
    for (history,) in rows:
        for e in re.findall(r"To:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", history or ""):
            sent.add(e.lower().strip())
    return sent

def build_queue(limit=500, min_score=40):
    conn = sqlite3.connect(DB)
    sent = load_sent_emails(conn)

    rows = conn.execute("""
        SELECT id, company, email, website, country, note, history
        FROM leads
        WHERE email!=''
          AND email LIKE '%@%'
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    out = []
    seen = set()
    rejected = 0

    for lead_id, company, email, website, country, note, history in rows:
        email = (email or "").strip().lower()

        if email in seen or email in sent:
            rejected += 1
            continue

        blocked, reason = is_blocked(email, company, website, note, country)
        if blocked:
            log(f"REJECT: {email} | {reason}")
            rejected += 1
            continue

        score = gps_score(company, website, note, email, country)
        if score < min_score:
            log(f"REJECT LOW SCORE: {email} | score={score}")
            rejected += 1
            continue

        if history and ("Bulk Email Sent" in history or "Auto Outreach Sent" in history):
            rejected += 1
            continue

        seen.add(email)
        out.append({
            "lead_id": lead_id,
            "company": company or "",
            "email": email,
            "website": website or "",
            "country": country or "",
            "score": score,
            "subject": SUBJECT,
            "body": BODY,
            "status": "READY",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sent_at": "",
            "error": ""
        })

    conn.close()

    with open(QUEUE_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "lead_id","company","email","website","country","score",
            "subject","body","status","created_at","sent_at","error"
        ])
        writer.writeheader()
        writer.writerows(out)

    log(f"V3.3 QUEUE BUILT: ready={len(out)} rejected={rejected} file={QUEUE_FILE}")

def preview(n=30):
    try:
        rows = list(csv.DictReader(open(QUEUE_FILE, "r", encoding="utf-8-sig")))
    except FileNotFoundError:
        print("No queue file. Run: python auto_outreach_v33.py build")
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"

    if cmd == "build":
        build_queue()
    elif cmd == "preview":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        preview(n)
    else:
        print("Usage:")
        print("  python auto_outreach_v33.py build")
        print("  python auto_outreach_v33.py preview 30")
