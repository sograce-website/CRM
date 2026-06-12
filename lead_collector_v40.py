import csv
import re
import time
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, urljoin, unquote, parse_qs

DB_FILE = "crm.db"
CSV_FILE = "auto_leads_v40.csv"
LOG_FILE = "lead_collector_v40.log"

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 18
MAX_SITES_PER_KEYWORD = 20

KEYWORDS = [
    '"gps tracker distributor" -gov -edu -hospital -clinic -school',
    '"gps tracking company" -gov -edu -hospital -clinic -school',
    '"telematics company" "contact" -gov -edu -hospital -clinic',
    '"fleet management company" "gps tracking" -gov -edu -school',
    '"vehicle tracker supplier" -gov -edu -hospital',
    '"asset tracking company" "gps" -gov -edu -school',
    '"personal gps tracker distributor" -gov -edu',
    '"gps watch distributor" -gov -edu -hospital',
    '"sos gps watch supplier" -gov -edu -hospital',
    '"iot tracking solution provider" gps -gov -edu',
    '"GPS tracking solutions" distributor contact',
    '"fleet tracking solutions" dealer contact',
]

BLOCK_DOMAINS = [
    "google.", "bing.", "yahoo.", "baidu.", "duckduckgo.",
    "facebook.", "instagram.", "youtube.", "tiktok.", "twitter.", "x.com",
    "linkedin.", "pinterest.", "reddit.", "quora.", "wikipedia.",
    "amazon.", "ebay.", "aliexpress.", "temu.",
    ".gov", ".edu", ".ac.", ".org",
    "hospital", "clinic", "school", "university", "college",
    "foundation", "charity", "animal", "wildlife",
    "zhihu.com", "splashlearn.com", "brighterly.com", "daum.net",
    "domain.com", "example.com", "test.com",
]

BLOCK_EMAIL_WORDS = [
    "noreply", "no-reply", "example.com", "domain.com", "test.com",
    "admin@", "webmaster@", "abuse@", "privacy@", "support-web",
    "frontend", "jquery", "bootstrap", "sentry", "wixpress",
    "wordpress", "cloudflare", "github", "npm"
]

GPS_TERMS = [
    "gps tracker", "gps tracking", "tracking device", "vehicle tracker",
    "asset tracking", "fleet tracking", "fleet management", "telematics",
    "personal tracker", "pet tracker", "gps watch", "sos watch",
    "location tracking", "iot tracking", "gps locator", "tracking solutions",
]

BUYER_TERMS = [
    "distributor", "dealer", "supplier", "wholesale", "wholesaler",
    "importer", "reseller", "solution provider", "systems integrator",
    "fleet", "telematics", "security company"
]

EMAIL_RE = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

def log(msg):
    line = str(msg)
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def clean_url(href):
    if not href:
        return None
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            href = unquote(qs["uddg"][0])
    if href.startswith("//"):
        href = "https:" + href
    if not href.startswith("http"):
        return None
    return href.split("#")[0].strip()

def domain(url):
    return urlparse(url).netloc.lower().replace("www.", "")

def ok_domain(url):
    d = domain(url)
    if not d:
        return False
    return not any(b in d for b in BLOCK_DOMAINS)

def clean_email(email):
    email = (email or "").lower().strip().strip(".,;:()[]<>")
    if not re.fullmatch(EMAIL_RE, email):
        return None
    if any(b in email for b in BLOCK_EMAIL_WORDS):
        return None
    d = email.split("@")[-1]
    if any(b in d for b in BLOCK_DOMAINS):
        return None
    if len(email) > 90:
        return None
    return email

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code >= 400:
            return ""
        return r.text
    except Exception:
        return ""

def score_site(company, site, text):
    t = " ".join([company or "", site or "", text or ""]).lower()
    d = domain(site)
    if any(b in t for b in BLOCK_DOMAINS):
        return 0

    gps_hits = [x for x in GPS_TERMS if x in t]
    buyer_hits = [x for x in BUYER_TERMS if x in t]

    score = len(gps_hits) * 50 + len(buyer_hits) * 20

    if "gps" in t and ("tracker" in t or "tracking" in t):
        score += 100
    if "telematics" in t:
        score += 80
    if "fleet" in t and ("tracking" in t or "management" in t):
        score += 80
    if any(x in d for x in ["gps", "track", "tracker", "tracking", "telematics", "fleet", "locator"]):
        score += 60

    return score

def search_sites(keyword):
    urls = []
    search_urls = [
        "https://www.bing.com/search?q=" + quote_plus(keyword),
        "https://duckduckgo.com/html/?q=" + quote_plus(keyword),
    ]

    for search_url in search_urls:
        log("SEARCH_URL: " + search_url)
        html = fetch(search_url)
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a"):
            u = clean_url(a.get("href"))
            if u and ok_domain(u):
                urls.append(u)

        for u in re.findall(r'https?://[^\s\\"<>]+', html):
            u = clean_url(u)
            if u and ok_domain(u):
                urls.append(u)

        time.sleep(1)

    clean = []
    seen = set()
    for u in urls:
        d = domain(u)
        if d not in seen and ok_domain(u):
            seen.add(d)
            clean.append(u)
        if len(clean) >= MAX_SITES_PER_KEYWORD:
            break
    return clean

def extract_company(site, html):
    try:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            title = re.sub(r"[\|\-–—].*", "", title).strip()
            if 2 <= len(title) <= 70:
                return title
    except Exception:
        pass
    return domain(site)

def extract_site(site):
    pages = [
        site,
        urljoin(site, "/contact"),
        urljoin(site, "/contact-us"),
        urljoin(site, "/about"),
        urljoin(site, "/about-us"),
        urljoin(site, "/solutions"),
        urljoin(site, "/products"),
    ]

    combined = ""
    emails = set()
    first_html = ""

    for page in pages:
        html = fetch(page)
        if not first_html and html:
            first_html = html
        combined += " " + html[:250000]
        for e in re.findall(EMAIL_RE, html):
            ce = clean_email(e)
            if ce:
                emails.add(ce)
        time.sleep(0.6)

    company = extract_company(site, first_html or combined)
    score = score_site(company, site, combined)
    return company, sorted(emails), score, combined[:5000]

def guess_country(site):
    d = domain(site)
    if d.endswith(".co.uk") or d.endswith(".uk"):
        return "UK"
    if d.endswith(".de"):
        return "Germany"
    if d.endswith(".fr"):
        return "France"
    if d.endswith(".it"):
        return "Italy"
    if d.endswith(".es"):
        return "Spain"
    if d.endswith(".nl"):
        return "Netherlands"
    if d.endswith(".pl"):
        return "Poland"
    if d.endswith(".sg"):
        return "Singapore"
    if d.endswith(".au"):
        return "Australia"
    if d.endswith(".ca"):
        return "Canada"
    if d.endswith(".com"):
        return "USA"
    return ""

def save_csv(rows):
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "company", "email", "website", "country", "score", "source", "keyword"
        ])
        w.writeheader()
        w.writerows(rows)

def save_db(rows):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    for r in rows:
        try:
            old = c.execute("SELECT id FROM leads WHERE email=?", (r["email"],)).fetchone()
            if old:
                continue
            c.execute("""
                INSERT INTO leads(company,email,website,country,source,status,note,category)
                VALUES(?,?,?,?,?,?,?,?)
            """, (
                r["company"], r["email"], r["website"], r["country"],
                "V4 GPS Collector", "NEW",
                f"V4 targeted GPS lead | keyword={r['keyword']} | score={r['score']}",
                "GPS"
            ))
        except Exception as e:
            log("DB_SKIP: " + r["email"] + " | " + str(e))

    conn.commit()
    conn.close()

def main():
    all_rows = []
    seen_domains = set()
    seen_emails = set()

    for kw in KEYWORDS:
        log("SEARCH: " + kw)
        sites = search_sites(kw)
        log("SITES: " + str(len(sites)))

        for site in sites:
            d = domain(site)
            if d in seen_domains:
                continue
            seen_domains.add(d)

            log("CHECK: " + site)
            company, emails, score, text_sample = extract_site(site)

            if score < 120:
                log(f"SKIP_LOW_SCORE: {d} score={score}")
                continue
            if not emails:
                log(f"SKIP_NO_EMAIL: {d} score={score}")
                continue

            for email in emails:
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                row = {
                    "company": company,
                    "email": email,
                    "website": site,
                    "country": guess_country(site),
                    "score": score,
                    "source": "V4 GPS Collector",
                    "keyword": kw,
                }
                all_rows.append(row)
                log(f"FOUND: {email} | {company} | score={score}")

            time.sleep(1)

    save_csv(all_rows)
    save_db(all_rows)
    log(f"DONE: {len(all_rows)} GPS leads saved to {CSV_FILE} and crm.db")

if __name__ == "__main__":
    main()
