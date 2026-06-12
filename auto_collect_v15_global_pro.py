# auto_collect_v15_global_pro.py
# SOGRACE CRM AUTO COLLECT V1.5 GLOBAL PRO NO-CHINA
# Goal:
# 1) improve V1.4 save quality
# 2) reduce duplicate subdomains/pages
# 3) extract more valid company emails / WhatsApp
# 4) avoid review/support/activate/refill/forum/search/media junk pages

import json
import re
import time
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs, unquote, urljoin

DB = "crm.db"
STATUS = "auto_collect_status.json"
LOG = "auto_collect_new.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = [
    "gps sos watch distributor",
    "elderly gps watch distributor",
    "senior gps tracker watch supplier",
    "medical alert gps watch distributor",
    "personal alarm gps tracker distributor",
    "gps watch wholesaler",
    "elderly safety watch supplier",
    "lone worker gps device distributor",
    "4g gps sos watch supplier",
    "fall detection gps watch distributor",
    "senior safety device distributor",
    "personal emergency response system distributor",
    "gps tracker watch manufacturer",
    "gps watch importer",
    "medical alert device wholesaler",
    "PERS device distributor",
    "telecare gps watch supplier",
    "remote patient monitoring gps watch",
]

COUNTRIES = [
    "usa", "canada", "uk", "germany", "france", "italy", "spain",
    "netherlands", "sweden", "norway", "denmark", "finland",
    "australia", "new zealand", "ireland", "switzerland", "austria",
    "belgium", "poland", "czech", "portugal"
]

SEARCH_URLS = [
    "https://www.bing.com/search?q={q}&first={p}",
    "https://search.yahoo.com/search?p={q}&b={p}",
    "https://www.ecosia.org/search?q={q}&p={p}",
]

BLOCKED_DOMAINS = [
    ".cn", "china", "baidu.", "alibaba.", "made-in-china.", "1688.", "taobao.",
    "tmall.", "jd.com", "globalsources.cn",
    "bing.com", "yahoo.com", "search.yahoo.com", "r.search.yahoo.com",
    "ecosia.org", "google.", "duckduckgo.", "brave.com", "yandex.",
    "ask.com", "aol.com",
    "facebook.", "instagram.", "youtube.", "youtu.be", "tiktok.", "linkedin.",
    "pinterest.", "reddit.", "quora.", "twitter.", "x.com",
    "amazon.", "ebay.", "aliexpress.", "temu.", "walmart.", "etsy.",
    "wikipedia.", "wiktionary.", "dictionary.",
    "w3.org", "cloudflare.", "turnstile", "doubleclick.", "googlesyndication.",
    "gstatic.", "googleapis.", "schema.org",
    ".gov", ".edu", "gov.", "academy",
]

BAD_SUBDOMAIN_WORDS = [
    "support.", "help.", "login.", "accounts.", "account.", "activate.",
    "refill.", "reviews.", "review.", "forum.", "forums.", "video.",
    "images.", "news.", "blog.", "docs.", "status.", "cdn.", "static."
]

BAD_PATH_WORDS = [
    "/search", "/images", "/image", "/video", "/news", "/login", "/signin",
    "/signup", "/account", "/privacy", "/terms", "/help", "/support/article",
    "/forum", "/forums", "/reviews", "/review", "/activate", "/refill",
    "/cart", "/checkout", "/wp-json", "/tag/", "/author/",
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".rar"
]

POSITIVE_WORDS = [
    "gps", "tracker", "tracking", "watch", "sos", "medical", "alert",
    "elderly", "senior", "personal", "alarm", "safety", "lone", "worker",
    "distributor", "supplier", "wholesale", "manufacturer", "oem", "device",
    "telecare", "pers", "fall detection"
]

CONTACT_PATHS = [
    "/", "/contact", "/contact-us", "/contacts", "/about", "/about-us",
    "/support/contact", "/sales", "/dealers", "/distributors"
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+|00)?[1-9][0-9\-\s().]{7,18}")

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_log(msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def update_status(**kw):
    data = {}
    try:
        data = json.load(open(STATUS, "r", encoding="utf-8"))
    except Exception:
        pass
    data.update(kw)
    data["updated"] = now()
    json.dump(data, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def html_unescape(s):
    return (s or "").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")

def normalize_url(url):
    url = html_unescape((url or "").strip())
    if not url:
        return ""

    if "r.search.yahoo.com" in url and "/RU=" in url:
        try:
            url = unquote(url.split("/RU=", 1)[1].split("/RK=", 1)[0])
        except Exception:
            pass

    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ["url", "u", "q", "r", "redirect", "target"]:
            if key in qs and qs[key]:
                candidate = qs[key][0]
                if candidate.startswith("http"):
                    url = unquote(candidate)
                    break
    except Exception:
        pass

    return url.split("#")[0].strip()

def domain_of(url):
    try:
        d = urlparse(url).netloc.lower()
        if d.startswith("www."):
            d = d[4:]
        return d
    except Exception:
        return ""

def root_domain(domain):
    parts = (domain or "").split(".")
    if len(parts) <= 2:
        return domain
    # handle common second-level TLDs
    if parts[-2] in ["co", "com", "net", "org"] and len(parts[-1]) == 2 and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])

def canonical_home(url):
    d = domain_of(url)
    if not d:
        return url
    rd = root_domain(d)
    scheme = urlparse(url).scheme or "https"
    return f"{scheme}://{rd}/"

def is_bad_url(url):
    if not url or not url.startswith(("http://", "https://")):
        return True
    u = url.lower()
    d = domain_of(u)
    if not d or "." not in d:
        return True
    if any(x in u for x in BLOCKED_DOMAINS):
        return True
    if any(d.startswith(x) or ("//" + x) in u for x in BAD_SUBDOMAIN_WORDS):
        return True
    if any(x in u for x in BAD_PATH_WORDS):
        return True
    if "search?" in u or "/search/" in u:
        return True
    return False

def score_url(url, anchor_text=""):
    text = (url + " " + anchor_text).lower()
    score = 0
    for w in POSITIVE_WORDS:
        if w in text:
            score += 2
    # prefer real company pages
    if any(x in text for x in ["contact", "about", "product", "solutions", "gps", "medical-alert", "sos"]):
        score += 2
    # penalize junk paths
    if any(x in text for x in ["support", "review", "forum", "activate", "refill", "login"]):
        score -= 8
    return score

def extract_result_links(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href", ""))
        text = a.get_text(" ", strip=True)
        if is_bad_url(href):
            continue
        sc = score_url(href, text)
        if sc < 1:
            continue
        # save canonical root domain, not deep review/support pages
        clean = canonical_home(href)
        if is_bad_url(clean):
            continue
        candidates.append((sc, clean, href))

    candidates.sort(reverse=True, key=lambda x: x[0])
    seen_roots = set()
    final = []
    for sc, clean, original in candidates:
        rd = root_domain(domain_of(clean))
        if rd in seen_roots:
            continue
        seen_roots.add(rd)
        final.append((clean, original, sc))
    return final

def safe_get(url, timeout=8):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except Exception:
        return None

def clean_email(email):
    e = (email or "").strip().strip(".,;:()[]<>").lower()
    bads = [
        "example.com", "domain.com", "test.com", "yourdomain", "sentry",
        "wixpress", "shopify", "wordpress", "png", "jpg", "jpeg",
        "noreply", "no-reply", "donotreply", "privacy@", "abuse@"
    ]
    if not e or any(b in e for b in bads):
        return ""
    if len(e) > 80:
        return ""
    return e

def pick_best_email(emails):
    cleaned = []
    for e in emails:
        ce = clean_email(e)
        if ce and ce not in cleaned:
            cleaned.append(ce)
    if not cleaned:
        return ""
    priority = ["sales@", "info@", "contact@", "hello@", "support@", "service@", "office@", "admin@"]
    for p in priority:
        for e in cleaned:
            if e.startswith(p):
                return e
    return cleaned[0]

def extract_contacts_from_html(html):
    soup = BeautifulSoup(html or "", "html.parser")
    emails = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            emails.append(href.split(":", 1)[1].split("?")[0])

    emails += EMAIL_RE.findall(html or "")

    text = soup.get_text(" ", strip=True)
    phones = []
    for p in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", p)
        if 8 <= len(digits) <= 16:
            phones.append(p.strip())

    return pick_best_email(emails), (phones[0] if phones else "")

def find_contact_links(base_url, html):
    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
        if any(k in text for k in ["contact", "about", "sales", "dealer", "distributor"]):
            href = urljoin(base_url, a["href"])
            if href.startswith(("http://", "https://")) and not is_bad_url(href):
                links.append(href)
    return list(dict.fromkeys(links))[:5]

def fetch_company_contacts(home_url):
    pages = [home_url]
    # try common paths
    for p in CONTACT_PATHS:
        pages.append(urljoin(home_url, p))

    email = ""
    phone = ""
    checked = set()

    # first homepage, then discovered contact links
    homepage = safe_get(home_url, 10)
    if homepage and homepage.text:
        e, p = extract_contacts_from_html(homepage.text)
        email = email or e
        phone = phone or p
        pages.extend(find_contact_links(home_url, homepage.text))

    for u in pages[:10]:
        if u in checked:
            continue
        checked.add(u)
        r = safe_get(u, 8)
        if not r or not r.text:
            continue
        e, p = extract_contacts_from_html(r.text)
        email = email or e
        phone = phone or p
        if email and phone:
            break

    return email, phone

def existing_root(cur, rd):
    row = cur.execute(
        "SELECT id FROM leads WHERE lower(website) LIKE ? LIMIT 1",
        (f"%{rd}%",)
    ).fetchone()
    return row is not None

def guess_country(keyword):
    k = " " + keyword.lower() + " "
    for c in COUNTRIES:
        if f" {c} " in k:
            return c.upper()
    return ""

def save_lead(home_url, original_url, keyword):
    d = domain_of(home_url)
    rd = root_domain(d)
    if not rd:
        return False, "no-domain"

    company = rd.split(".")[0].replace("-", " ").replace("_", " ").title()
    country = guess_country(keyword)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    if existing_root(cur, rd):
        conn.close()
        return False, "duplicate"

    email, phone = fetch_company_contacts(home_url)

    # quality gate: save company website even without email, but require meaningful source score already done
    try:
        cur.execute("""
            INSERT INTO leads(
                company, contact, email, website, country, whatsapp,
                source, category, status, level, owner, expected_amount
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            company, "", email, home_url, country, phone,
            "AUTO COLLECT V1.5 / " + keyword + " / " + original_url,
            "ELDERLY", "NEW", "C", "admin", 0
        ))
        conn.commit()
        conn.close()
        return True, "saved-email" if email else "saved-no-email"
    except Exception as e:
        conn.close()
        return False, "db-error:" + str(e)

def run():
    found = saved = skipped = failed = email_found = 0
    update_status(
        version="AUTO COLLECT V1.5 GLOBAL PRO NO CHINA",
        status="running",
        message="Auto Collect V1.5 running",
        found=0, saved=0, skipped=0, failed=0, email_found=0,
        current_keyword="", current_site=""
    )
    write_log("===== AUTO COLLECT V1.5 GLOBAL PRO NO-CHINA START =====")

    for country in COUNTRIES:
        for base_kw in KEYWORDS:
            keyword = f"{base_kw} {country}"
            update_status(current_keyword=keyword, message=f"Searching {keyword}",
                          found=found, saved=saved, skipped=skipped, failed=failed, email_found=email_found)

            for tpl in SEARCH_URLS:
                for page in [1, 11, 21, 31, 41]:
                    search_url = tpl.format(q=quote_plus(keyword), p=page)
                    try:
                        write_log("SEARCH " + search_url)
                        r = safe_get(search_url, 15)
                        if not r:
                            failed += 1
                            continue

                        links = extract_result_links(r.text)

                        for home_url, original_url, sc in links:
                            found += 1
                            update_status(current_site=home_url, found=found, saved=saved,
                                          skipped=skipped, failed=failed, email_found=email_found)

                            ok, reason = save_lead(home_url, original_url, keyword)
                            if ok:
                                saved += 1
                                if reason == "saved-email":
                                    email_found += 1
                                write_log(f"SAVED {home_url} | {reason} | score={sc}")
                            else:
                                skipped += 1
                                if reason not in ("duplicate",):
                                    write_log("SKIP " + reason + " | " + home_url)

                        time.sleep(1)
                    except Exception as e:
                        failed += 1
                        write_log("FAILED " + str(e))
                        update_status(failed=failed)

    update_status(
        status="finished",
        message=f"Finished. Found {found}, saved {saved}, skipped {skipped}, failed {failed}, email_found {email_found}",
        found=found, saved=saved, skipped=skipped, failed=failed, email_found=email_found,
        current_keyword="", current_site=""
    )
    write_log("===== AUTO COLLECT V1.5 DONE =====")

if __name__ == "__main__":
    run()
