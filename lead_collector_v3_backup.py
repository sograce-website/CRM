import re, time, csv, sqlite3, requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, urljoin, unquote, parse_qs

KEYWORDS = [
    "GPS watch distributor USA",
    "elderly GPS watch supplier Europe",
    "GPS SOS tracker distributor",
    "personal GPS tracker wholesaler",
    "pet GPS tracker distributor",
    "medical alert GPS watch distributor",
    "senior GPS tracker supplier",
]

MAX_SITES_PER_KEYWORD = 20
TIMEOUT = 20

BAD_DOMAINS = [
    "duckduckgo.", "google.", "bing.", "yahoo.", "facebook.", "instagram.", "w3.org", "schemas.live.com", "storage.live.com", "microsoft.", "live.com",
    "youtube.", "linkedin.", "amazon.", "ebay.", "aliexpress.", "temu.",
    "wikipedia.", "reddit.", "pinterest.", "tiktok.", "twitter.", "x.com", "importgenius.", "gob.ec", "nbd.ltd"
]

EMAIL_RE = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"

BAD_EMAIL_WORDS = [
    "noreply", "no-reply", "example.com", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".svg", "sentry", "wixpress", "cloudflare", "bootstrap", "jquery", "webflow", "slick-carousel", "swiper", "wordpress"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

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
    return href

def ok_domain(url):
    d = urlparse(url).netloc.lower().replace("www.", "")
    if not d:
        return False
    return not any(b in d for b in BAD_DOMAINS)

def clean_email(e):
    e = e.lower().strip().strip(".,;:()[]<>")
    if any(b in e for b in BAD_EMAIL_WORDS):
        return None
    if not re.fullmatch(EMAIL_RE, e):
        return None
    return e

def search_duckduckgo(keyword):
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
            print("SEARCH ERROR:", e)

    clean = []
    seen = set()
    for u in urls:
        domain = urlparse(u).netloc.lower().replace("www.", "")
        if domain not in seen:
            seen.add(domain)
            clean.append(u)
        if len(clean) >= MAX_SITES_PER_KEYWORD:
            break

    return clean

def extract_company(site):
    d = urlparse(site).netloc.replace("www.", "")
    return d.split(":")[0]

def extract_emails_from_site(site):
    company = extract_company(site)
    pages = [
        site,
        urljoin(site, "/contact"),
        urljoin(site, "/contact-us"),
        urljoin(site, "/about"),
        urljoin(site, "/about-us"),
    ]

    emails = set()

    for page in pages:
        try:
            r = requests.get(page, headers=HEADERS, timeout=TIMEOUT)
            text = r.text
            for e in re.findall(EMAIL_RE, text):
                ce = clean_email(e)
                if ce:
                    emails.add(ce)
        except Exception:
            pass
        time.sleep(0.8)

    return company, sorted(emails)

def save_csv(rows):
    with open("auto_leads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["company","email","website","source","keyword"])
        w.writeheader()
        w.writerows(rows)

def save_to_crm(rows):
    conn = sqlite3.connect("crm.db")
    c = conn.cursor()

    for r in rows:
        try:
            c.execute("""
            INSERT OR IGNORE INTO leads(company,email,website,source,status,note)
            VALUES(?,?,?,?,?,?)
            """, (
                r["company"],
                r["email"],
                r["website"],
                "Auto Collector",
                "NEW",
                "Auto collected keyword: " + r["keyword"]
            ))
        except Exception as e:
            print("DB SKIP:", r["email"], e)

    conn.commit()
    conn.close()

def main():
    all_rows = []
    seen_emails = set()

    for kw in KEYWORDS:
        print("SEARCH:", kw)
        sites = search_duckduckgo(kw)
        print("SITES:", len(sites))

        for site in sites:
            print("CHECK:", site)
            company, emails = extract_emails_from_site(site)

            for email in emails:
                if email not in seen_emails:
                    seen_emails.add(email)
                    row = {
                        "company": company,
                        "email": email,
                        "website": site,
                        "source": "DuckDuckGo",
                        "keyword": kw,
                    }
                    all_rows.append(row)
                    print("FOUND:", email)

            time.sleep(1)

    save_csv(all_rows)
    save_to_crm(all_rows)

    print("DONE:", len(all_rows), "leads saved")

if __name__ == "__main__":
    main()
