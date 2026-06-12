import re, time, csv, sqlite3, requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, urljoin, unquote, parse_qs

KEYWORDS = [
    "GPS tracker distributor USA",
    "GPS tracking company USA",
    "GPS watch distributor USA",
    "elderly GPS watch supplier Europe",
    "SOS GPS tracker distributor",
    "personal GPS tracker wholesaler",
    "vehicle GPS tracking distributor",
    "asset GPS tracking supplier",
    "fleet GPS tracking company",
    "medical alert GPS watch distributor",
]

MAX_SITES_PER_KEYWORD = 15
TIMEOUT = 18
CSV_FILE = "auto_leads.csv"
DB_FILE = "crm.db"

HEADERS = {"User-Agent": "Mozilla/5.0"}

BAD_DOMAINS = [
    "google.", "bing.", "yahoo.", "baidu.", "duckduckgo.",
    "facebook.", "instagram.", "youtube.", "tiktok.", "twitter.", "x.com",
    "linkedin.", "pinterest.", "reddit.", "quora.",
    "amazon.", "ebay.", "aliexpress.", "temu.",
    "wikipedia.", "w3.org", "microsoft.", "live.com",
    ".gov", ".edu", "school.", "university.",
    "foundation.", "charity.", "animal.", "wildlife.",
    "brilliant.org", "splashlearn.com", "baidu.com",
]

BAD_EMAIL_WORDS = [
    "noreply", "no-reply", "example.com", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".svg", "sentry", "wixpress", "bootstrap",
    "jquery", "webflow", "wordpress", "swiper", "slick-carousel",
    "calendar-web", "frontend", "support-web", "taglib",
]

GOOD_KEYWORDS = [
    "gps tracker", "gps tracking", "gps watch", "sos tracker",
    "sos watch", "personal tracker", "vehicle tracking",
    "fleet tracking", "asset tracking", "iot tracking",
    "elderly gps", "medical alert", "location tracking",
    "telematics", "tracking device", "gps device"
]

EMAIL_RE = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"

def log(msg):
    print(msg, flush=True)

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
    return href.split("#")[0]

def domain(url):
    return urlparse(url).netloc.lower().replace("www.", "")

def ok_domain(url):
    d = domain(url)
    if not d:
        return False
    return not any(b in d for b in BAD_DOMAINS)

def clean_email(e):
    e = e.lower().strip().strip(".,;:()[]<>")
    if any(b in e for b in BAD_EMAIL_WORDS):
        return None
    if not re.fullmatch(EMAIL_RE, e):
        return None
    if len(e) > 80:
        return None
    return e

def gps_score(text):
    t = text.lower()
    score = 0
    for k in GOOD_KEYWORDS:
        if k in t:
            score += 20
    return score

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
    if d.endswith(".com"):
        return "USA"
    return ""

def search_sites(keyword):
    urls = []
    search_urls = [
        "https://www.bing.com/search?q=" + quote_plus(keyword),
        "https://duckduckgo.com/html/?q=" + quote_plus(keyword),
    ]

    for search_url in search_urls:
        try:
            r = requests.get(search_url, headers=HEADERS, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a"):
                href = clean_url(a.get("href"))
                if href and ok_domain(href):
                    urls.append(href)

            for u in re.findall(r'https?://[^\s\\"<>]+', r.text):
                u = clean_url(u)
                if u and ok_domain(u):
                    urls.append(u)

        except Exception as e:
            log("SEARCH ERROR: " + str(e))

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

def fetch_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return r.text
    except Exception:
        return ""

def extract_company(site, html):
    d = domain(site)
    try:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        if title:
            title = re.sub(r"[\|\-–—].*", "", title).strip()
            if 2 <= len(title) <= 60:
                return title
    except Exception:
        pass
    return d

def extract_emails_from_site(site):
    pages = [
        site,
        urljoin(site, "/contact"),
        urljoin(site, "/contact-us"),
        urljoin(site, "/about"),
        urljoin(site, "/about-us"),
    ]

    all_text = ""
    emails = set()

    for page in pages:
        html = fetch_text(page)
        all_text += " " + html[:200000]
        for e in re.findall(EMAIL_RE, html):
            ce = clean_email(e)
            if ce:
                emails.add(ce)
        time.sleep(0.7)

    score = gps_score(all_text)
    company = extract_company(site, all_text)

    return company, sorted(emails), score

def save_csv(rows):
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["company","email","website","country","score","source","keyword"])
        w.writeheader()
        w.writerows(rows)

def save_to_crm(rows):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for r in rows:
        try:
            c.execute("""
            INSERT INTO leads(company,email,website,country,source,status,note,category)
            VALUES(?,?,?,?,?,?,?,?)
            """, (
                r["company"],
                r["email"],
                r["website"],
                r["country"],
                "Auto Collector",
                "NEW",
                f"Auto collected | keyword={r['keyword']} | score={r['score']}",
                "DISTRIBUTOR"
            ))
        except Exception as e:
            log("DB SKIP: " + r["email"] + " " + str(e))

    conn.commit()
    conn.close()

def main():
    all_rows = []
    seen_emails = set()
    seen_domains = set()

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
            company, emails, score = extract_emails_from_site(site)

            if score < 20:
                log("SKIP LOW SCORE: " + d + " SCORE=" + str(score))
                continue

            if not emails:
                log("SKIP NO EMAIL: " + d + " SCORE=" + str(score))
                continue

            country = guess_country(site)

            for email in emails:
                if email not in seen_emails:
                    seen_emails.add(email)
                    row = {
                        "company": company,
                        "email": email,
                        "website": site,
                        "country": country,
                        "score": score,
                        "source": "Search Engine",
                        "keyword": kw
                    }
                    all_rows.append(row)
                    log("FOUND: " + email + " | " + company + " | SCORE=" + str(score))

            time.sleep(1)

    save_csv(all_rows)
    save_to_crm(all_rows)
    log("DONE: " + str(len(all_rows)) + " quality leads saved")

if __name__ == "__main__":
    main()
