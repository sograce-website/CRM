import csv
import datetime
import re
import sqlite3
import sys

DB = "crm.db"
QUEUE_FILE = "email_queue_v34.csv"
LOG_FILE = "auto_outreach_v34.log"

SUBJECT = "GPS SOS Watch and GPS Tracking Devices Cooperation"

BODY = """Dear Team,

We are SOGRACE, a professional GPS tracking device manufacturer from China.

We provide elderly GPS SOS watches, personal GPS trackers, pet GPS trackers, vehicle GPS trackers, asset tracking devices, and GPS platform / APP solutions.

We support OEM / ODM customization, APP branding, platform integration, and bulk supply for distributors.

Would you be interested in receiving our latest catalog and cooperation options?

Best regards,
Chen
SOGRACE
www.sograce.cn
info@sograce.cn

If this message is not relevant, please reply "unsubscribe" and we will not contact you again.
"""

# 强黑名单：出现这些直接拒绝
BLOCK_DOMAINS = [
    ".gov", ".edu", ".ac.", ".org",
    "zhihu.com", "splashlearn.com", "brighterly.com", "daum.net",
    "baidu.", "wikipedia.", "facebook.", "instagram.", "youtube.",
    "domain.com", "example.com", "test.com",
    "spb.gov.sg", "moh.gov.sg", "qandm.com.sg", "sata.com.sg",
]

BLOCK_WORDS = [
    "government", "ministry", "hospital", "clinic", "medical centre",
    "foundation", "charity", "school", "university", "college",
    "animal", "wildlife", "education", "learning", "course",
    "complaint", "complaints", "cme", "noreply", "no-reply",
    "admin@", "webmaster@", "user@", "hello@myselfexploration",
    "zhihu", "splashlearn", "brighterly", "daum",
]

# GPS行业强关键词：必须命中
MUST_HAVE = [
    "gps tracker", "gps tracking", "gps watch", "sos watch",
    "tracking device", "vehicle tracker", "fleet tracking",
    "fleet management", "telematics", "asset tracking",
    "personal tracker", "pet tracker", "iot tracking",
    "location tracker", "gps locator", "tracker distributor",
    "tracking company", "tracking solution"
]

# 域名/公司名强相关词
DOMAIN_COMPANY_HINTS = [
    "gps", "tracker", "tracking", "fleet", "telematics",
    "locator", "location", "iot", "nav", "security", "sos"
]

BUYER_WORDS = [
    "distributor", "dealer", "supplier", "wholesale", "wholesaler",
    "importer", "reseller", "solution", "systems", "technology",
    "telematics", "tracking", "tracker", "gps"
]

EMAIL_RE = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def safe(v):
    return (v or "").strip()

def email_domain(email):
    return email.split("@")[-1].lower().strip()

def site_domain(website):
    w = (website or "").lower().replace("https://", "").replace("http://", "")
    return w.split("/")[0].replace("www.", "")

def valid_email(email):
    email = safe(email).lower()
    if not re.match(EMAIL_RE, email):
        return False, "invalid email format"
    d = email_domain(email)
    if any(b in d for b in BLOCK_DOMAINS):
        return False, "blocked email domain"
    if any(w in email for w in BLOCK_WORDS):
        return False, "blocked email word"
    return True, ""

def strict_gps_score(company="", website="", note="", email="", country=""):
    company = safe(company).lower()
    website = safe(website).lower()
    note = safe(note).lower()
    email = safe(email).lower()
    d = site_domain(website) or email_domain(email)

    text = " ".join([company, website, note, email, country or ""]).lower()

    if any(b in text for b in BLOCK_DOMAINS):
        return 0, "blocked domain in text"
    if any(w in text for w in BLOCK_WORDS):
        return 0, "blocked word in text"

    must_hits = [k for k in MUST_HAVE if k in text]
    domain_hits = [k for k in DOMAIN_COMPANY_HINTS if k in d or k in company]
    buyer_hits = [k for k in BUYER_WORDS if k in text]

    # 核心规则：必须有 GPS行业强关键词，同时域名/公司名要相关
    if not must_hits:
        return 0, "no GPS industry keyword"
    if not domain_hits and len(must_hits) < 2:
        return 0, "domain/company not GPS related"

    score = 0
    score += len(must_hits) * 40
    score += len(domain_hits) * 30
    score += len(buyer_hits) * 15

    # GPS + tracker/tracking 强组合
    if "gps" in text and ("tracker" in text or "tracking" in text):
        score += 80
    if "telematics" in text or "fleet management" in text:
        score += 60
    if "distributor" in text or "dealer" in text or "wholesale" in text:
        score += 40

    return score, "ok"

def load_sent_emails(conn):
    sent = set()
    rows = conn.execute("SELECT history FROM leads WHERE history IS NOT NULL AND history!=''").fetchall()
    for (history,) in rows:
        for e in re.findall(r"To:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", history or ""):
            sent.add(e.lower().strip())
    return sent

def build_queue(limit=800, min_score=100):
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
        email = safe(email).lower()

        if email in seen or email in sent:
            rejected += 1
            continue

        ok, reason = valid_email(email)
        if not ok:
            log(f"REJECT: {email} | {reason}")
            rejected += 1
            continue

        if history and ("Bulk Email Sent" in history or "Auto Outreach Sent" in history):
            rejected += 1
            continue

        score, reason = strict_gps_score(company, website, note, email, country)
        if score < min_score:
            log(f"REJECT: {email} | {reason} | score={score}")
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

    log(f"V3.4 GPS QUEUE BUILT: ready={len(out)} rejected={rejected} file={QUEUE_FILE}")

def preview(n=30):
    try:
        rows = list(csv.DictReader(open(QUEUE_FILE, "r", encoding="utf-8-sig")))
    except FileNotFoundError:
        print("No queue file. Run: python auto_outreach_v34.py build")
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
        print("  python auto_outreach_v34.py build")
        print("  python auto_outreach_v34.py preview 30")
