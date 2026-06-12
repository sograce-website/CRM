# lead_collector.py
# SOGRACE CRM V5.2 Pro REAL Lead Collector
# No demo data. No example.com. Real search -> website -> email -> CRM database.

import csv
import datetime as dt
import html
import json
import random
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

DB = "/home/admin/crm/crm.db"
CRM_DIR = Path("/home/admin/crm")
LOG_FILE = CRM_DIR / "lead_collector.log"
CSV_FILE = CRM_DIR / "auto_leads.csv"
STATUS_FILE = CRM_DIR / "v52_status.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
}

KEYWORDS = [
    "gps watch distributor germany",
    "gps sos watch distributor germany",
    "elderly gps watch supplier europe",
    "senior gps tracker distributor",
    "gps tracker wholesaler europe",
    "personal gps tracker importer",
    "lone worker gps device distributor",
    "gps sos pendant supplier",
    "4g gps watch elderly supplier",
    "gps tracking solution distributor",
    "gps tracker distributor france",
    "gps tracker distributor italy",
    "gps tracker distributor spain",
    "gps tracker distributor netherlands",
    "gps tracker distributor poland",
    "gps tracker distributor sweden",
    "gps tracker distributor uk",
]

BAD_DOMAINS = [
    "google.", "youtube.", "facebook.", "instagram.", "linkedin.", "twitter.", "x.com",
    "amazon.", "ebay.", "aliexpress.", "temu.", "wikipedia.", "reddit.", "pinterest.",
    "bing.com", "duckduckgo.com", "yahoo.", "baidu.", "github.", "medium.com",
    "trustpilot.", "crunchbase.", "zoominfo.", "dnb.com", "glassdoor.", "indeed.",
    "dictionary.", "merriam-webster.", "cambridge.org"
]

GOOD_WORDS = [
    "gps", "tracker", "tracking", "sos", "elderly", "senior", "watch", "wearable",
    "telematics", "location", "lone worker", "panic button", "personal alarm",
    "distributor", "wholesale", "wholesaler", "importer", "supplier", "reseller", "dealer"
]

B2B_WORDS = ["distributor", "wholesale", "wholesaler", "importer", "reseller", "dealer", "supplier", "partner"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

COUNTRY_HINTS = {
    ".de": "Germany", ".fr": "France", ".it": "Italy", ".es": "Spain", ".nl": "Netherlands",
    ".be": "Belgium", ".pl": "Poland", ".se": "Sweden", ".no": "Norway", ".dk": "Denmark",
    ".fi": "Finland", ".co.uk": "United Kingdom", ".uk": "United Kingdom", ".ie": "Ireland",
    ".pt": "Portugal", ".ch": "Switzerland", ".at": "Austria", ".cz": "Czech Republic",
}

def log(msg):
    CRM_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def set_status(**kwargs):
    data = {
        "version": "V5.2 Pro Real",
        "status": "Running",
        "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "found": 0,
        "saved": 0,
        "skipped": 0,
        "failed": 0,
        "current_keyword": "",
        "current_site": "",
        "message": "",
    }
    if STATUS_FILE.exists():
        try:
            data.update(json.loads(STATUS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    data.update(kwargs)
    data["updated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def clean_domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def is_bad_url(url):
    u = url.lower()
    if not u.startswith("http"):
        return True
    return any(bad in u for bad in BAD_DOMAINS)

def guess_country(url, text=""):
    domain = clean_domain(url)
    for suffix, country in COUNTRY_HINTS.items():
        if domain.endswith(suffix):
            return country
    low = (domain + " " + text[:3000]).lower()
    for country in set(COUNTRY_HINTS.values()):
        if country.lower() in low:
            return country
    return ""

def score_site(url, title, body):
    low = f"{url} {title} {body[:6000]}".lower()
    score = 0
    for w in GOOD_WORDS:
        if w in low:
            score += 8
    for w in B2B_WORDS:
        if w in low:
            score += 18
    if any(x in low for x in ["contact us", "about us", "products", "solutions"]):
        score += 15
    if any(x in low for x in ["gps watch", "sos watch", "elderly gps", "personal gps", "gps tracker"]):
        score += 25
    if any(x in low for x in ["blog", "news", "review only", "dictionary"]):
        score -= 20
    return max(0, min(score, 100))

def customer_value(score):
    if score >= 80: return "★★★★★"
    if score >= 60: return "★★★★"
    if score >= 40: return "★★★"
    if score >= 20: return "★★"
    return "★"

def product_interest(text):
    low = text.lower()
    if "watch" in low or "elderly" in low or "senior" in low:
        return "GPS SOS Watch"
    if "vehicle" in low or "fleet" in low:
        return "Vehicle Tracker"
    if "pet" in low:
        return "Pet Tracker"
    if "platform" in low or "software" in low:
        return "GPS Platform"
    return "GPS Tracker"

def safe_get(url, retries=3, timeout=30):
    last = None
    for i in range(1, retries + 1):
        try:
            time.sleep(random.uniform(1.0, 2.5))
            return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        except Exception as e:
            last = e
            log(f"REQUEST RETRY {i}/{retries} {url}: {e}")
            time.sleep(i * 2)
    raise last

def search_web(query, max_results=8):
    urls, seen = [], set()
    search_urls = [
        f"https://www.bing.com/search?q={quote_plus(query)}",
        f"https://duckduckgo.com/html/?q={quote_plus(query)}",
    ]
    for surl in search_urls:
        try:
            r = safe_get(surl, retries=3, timeout=30)
            log(f"SEARCH {query} -> {r.status_code} {surl}")
            if r.status_code >= 400:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if href.startswith("/l/?") and "uddg=" in href:
                    qs = parse_qs(urlparse(href).query)
                    href = unquote(qs.get("uddg", [""])[0])
                if href.startswith("http") and not is_bad_url(href):
                    d = clean_domain(href)
                    if d and d not in seen:
                        seen.add(d)
                        urls.append(href)
                if len(urls) >= max_results:
                    return urls
        except Exception as e:
            log(f"SEARCH ERROR {query}: {e}")
            set_status(message=f"Search error: {e}")
    return urls

def fetch_page(url):
    try:
        r = safe_get(url, retries=2, timeout=25)
        ctype = r.headers.get("content-type", "")
        if r.status_code >= 400 or "text/html" not in ctype:
            return "", "", ""
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else clean_domain(url)
        body = soup.get_text(" ", strip=True)
        return title, body, r.url
    except Exception as e:
        log(f"FETCH ERROR {url}: {e}")
        return "", "", ""

def contact_pages(base_url, html_text):
    pages = [base_url]
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for a in soup.find_all("a", href=True):
            s = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
            if any(k in s for k in ["contact", "about", "impressum", "imprint", "support"]):
                full = urljoin(base_url, a["href"])
                if full.startswith("http") and clean_domain(full) == clean_domain(base_url):
                    pages.append(full)
    except Exception:
        pass
    return list(dict.fromkeys(pages))[:5]

def extract_lead(url):
    title, body, final_url = fetch_page(url)
    if not body:
        return None
    emails = set(EMAIL_RE.findall(body))
    for p in contact_pages(final_url or url, body)[1:]:
        _, b2, _ = fetch_page(p)
        if b2:
            body += " " + b2
            emails.update(EMAIL_RE.findall(b2))
    emails = [e.lower() for e in emails if not any(x in e.lower() for x in ["example.", "domain.", "png", "jpg", "sentry", "wixpress"])]
    score = score_site(final_url or url, title, body)
    domain = clean_domain(final_url or url)
    company = html.unescape((title.split("|")[0].split("-")[0].strip() or domain)[:120])
    return {
        "company": company,
        "email": emails[0] if emails else "",
        "website": final_url or url,
        "country": guess_country(final_url or url, body),
        "whatsapp": "",
        "source": "Auto Collect V5.2 Pro Real",
        "category": "DISTRIBUTOR" if any(w in body.lower() for w in B2B_WORDS) else "ELDERLY",
        "status": "NEW",
        "note": f"V5.2 score={score}; domain={domain}",
        "level": "A" if score >= 70 else "B" if score >= 45 else "C",
        "product_interest": product_interest(body),
        "customer_value": customer_value(score),
        "expected_amount": "5000" if score >= 70 else "2000" if score >= 45 else "0",
        "score": score,
    }

def ensure_columns():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for col, spec in [
        ("contact","TEXT DEFAULT ''"), ("country","TEXT DEFAULT ''"), ("whatsapp","TEXT DEFAULT ''"),
        ("source","TEXT DEFAULT ''"), ("level","TEXT DEFAULT 'C'"), ("owner","TEXT DEFAULT ''"),
        ("next_followup","TEXT DEFAULT ''"), ("history","TEXT DEFAULT ''"),
        ("product_interest","TEXT DEFAULT ''"), ("customer_value","TEXT DEFAULT '★'"),
        ("last_contact","TEXT DEFAULT ''"), ("expected_amount","TEXT DEFAULT '0'"),
    ]:
        try:
            c.execute(f"ALTER TABLE leads ADD COLUMN {col} {spec}")
        except Exception:
            pass
    conn.commit()
    conn.close()

def exists_lead(conn, email, website):
    if email:
        row = conn.execute("SELECT id FROM leads WHERE LOWER(email)=LOWER(?) LIMIT 1", (email,)).fetchone()
        if row: return True
    d = clean_domain(website)
    if d:
        row = conn.execute("SELECT id FROM leads WHERE website LIKE ? LIMIT 1", (f"%{d}%",)).fetchone()
        if row: return True
    return False

def append_csv(lead):
    exists = CSV_FILE.exists()
    with CSV_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        fields = ["company","email","website","country","category","level","product_interest","customer_value","expected_amount","score","source"]
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: lead.get(k, "") for k in fields})

def save_lead(lead):
    if not lead or lead.get("score", 0) < 25:
        return False
    conn = sqlite3.connect(DB)
    if exists_lead(conn, lead.get("email", ""), lead.get("website", "")):
        conn.close()
        return False
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    history = f"{now} Auto collected by V5.2 Pro Real | Score {lead['score']}"
    conn.execute("""
        INSERT INTO leads
        (company,email,website,category,status,note,country,contact,whatsapp,source,level,owner,next_followup,history,product_interest,customer_value,last_contact,expected_amount)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        lead["company"], lead["email"], lead["website"], lead["category"], "NEW", lead["note"],
        lead["country"], "", lead["whatsapp"], lead["source"], lead["level"], "", "", history,
        lead["product_interest"], lead["customer_value"], now, lead["expected_amount"]
    ))
    conn.commit()
    conn.close()
    append_csv(lead)
    return True

def main():
    ensure_columns()
    found = saved = skipped = failed = 0
    set_status(status="Running", found=0, saved=0, skipped=0, failed=0, message="V5.2 Pro Real started")
    log("===== SOGRACE CRM V5.2 PRO REAL COLLECTOR START =====")
    seen = set()
    for kw in KEYWORDS:
        set_status(current_keyword=kw, message=f"Searching {kw}")
        for url in search_web(kw, 8):
            domain = clean_domain(url)
            if not domain or domain in seen:
                skipped += 1
                continue
            seen.add(domain)
            set_status(current_site=domain, found=found, saved=saved, skipped=skipped, failed=failed, message=f"Checking {domain}")
            log(f"CHECK {url}")
            try:
                lead = extract_lead(url)
                found += 1
                if lead and save_lead(lead):
                    saved += 1
                    log(f"SAVED {lead['company']} | {lead['email']} | {lead['website']} | score={lead['score']}")
                else:
                    skipped += 1
                    log(f"SKIP {domain}")
            except Exception as e:
                failed += 1
                log(f"ERROR {url}: {e}")
            set_status(found=found, saved=saved, skipped=skipped, failed=failed)
    set_status(status="Finished", found=found, saved=saved, skipped=skipped, failed=failed, message="V5.2 Pro Real finished")
    log(f"===== FINISHED found={found} saved={saved} skipped={skipped} failed={failed} =====")

if __name__ == "__main__":
    main()
