# auto_collect_v14_global.py
# SOGRACE CRM AUTO COLLECT V1.4 GLOBAL NO-CHINA
# Fixes V1.3 problem: many search/video/image/login links were saved as leads.
# V1.4 extracts real destination URLs from Bing/Yahoo/Ecosia result pages,
# filters search engine/internal/portal pages, deduplicates by domain,
# and saves cleaner company websites into crm.db.

import json
import re
import time
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

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
    # China / Chinese platforms
    ".cn", "china", "baidu.", "alibaba.", "made-in-china.", "1688.", "taobao.",
    "tmall.", "jd.com", "globalsources.cn",

    # Search engines / result pages / portals
    "bing.com", "yahoo.com", "search.yahoo.com", "r.search.yahoo.com",
    "ecosia.org", "google.", "duckduckgo.", "brave.com", "yandex.",
    "ask.com", "aol.com",

    # Social / media / marketplace / generic
    "facebook.", "instagram.", "youtube.", "youtu.be", "tiktok.", "linkedin.",
    "pinterest.", "reddit.", "quora.", "twitter.", "x.com",
    "amazon.", "ebay.", "aliexpress.", "temu.", "walmart.", "etsy.",
    "wikipedia.", "wiktionary.", "dictionary.",

    # Tech / CDN / captcha / file/static
    "w3.org", "cloudflare.", "turnstile", "doubleclick.", "googlesyndication.",
    "gstatic.", "googleapis.", "schema.org",

    # Gov/education/general non-buyers often polluted by search pages
    ".gov", ".edu", "gov.", "academy",

    # Unrelated junk seen in V1.3 DB
    "video.search", "images.search", "news.search", "login.yahoo", "help.yahoo",
]

BAD_PATH_WORDS = [
    "/search", "/images", "/image", "/video", "/news", "/login", "/signin",
    "/signup", "/account", "/privacy", "/terms", "/help", "/support/article",
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".rar"
]

POSITIVE_WORDS = [
    "gps", "tracker", "tracking", "watch", "sos", "medical", "alert",
    "elderly", "senior", "personal", "alarm", "safety", "lone", "worker",
    "distributor", "supplier", "wholesale", "manufacturer", "oem", "device"
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

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
        with open(STATUS, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    data.update(kw)
    data["updated"] = now()
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_url(url):
    if not url:
        return ""
    url = html_unescape(url.strip())

    # Yahoo redirect links: /RU=https%3a%2f%2fexample.com/RK=...
    if "r.search.yahoo.com" in url and "/RU=" in url:
        try:
            part = url.split("/RU=", 1)[1].split("/RK=", 1)[0]
            url = unquote(part)
        except Exception:
            pass

    # Common redirect params
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

    url = url.split("#")[0].strip()
    return url

def html_unescape(s):
    return (s.replace("&amp;", "&")
             .replace("&quot;", '"')
             .replace("&#39;", "'")
             .replace("&lt;", "<")
             .replace("&gt;", ">"))

def domain_of(url):
    try:
        d = urlparse(url).netloc.lower()
        if d.startswith("www."):
            d = d[4:]
        return d
    except Exception:
        return ""

def is_bad_url(url):
    if not url or not url.startswith(("http://", "https://")):
        return True

    u = url.lower()
    d = domain_of(u)
    if not d or "." not in d:
        return True

    if any(x in u for x in BLOCKED_DOMAINS):
        return True

    if any(x in u for x in BAD_PATH_WORDS):
        return True

    # reject obvious search-result links with encoded query only
    if "search?" in u or "/search/" in u:
        return True

    return False

def score_url(url, anchor_text=""):
    text = (url + " " + anchor_text).lower()
    score = 0
    for w in POSITIVE_WORDS:
        if w in text:
            score += 1
    return score

def extract_result_links(html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    # Prefer visible result anchors
    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href", ""))
        text = a.get_text(" ", strip=True)
        if is_bad_url(href):
            continue
        sc = score_url(href, text)
        # Keep even low score, but reject pure nav by requiring non-empty domain
        candidates.append((sc, href))

    # Sort higher-score links first and dedupe domain
    candidates.sort(reverse=True, key=lambda x: x[0])
    seen_domains = set()
    final = []
    for sc, url in candidates:
        d = domain_of(url)
        if d in seen_domains:
            continue
        seen_domains.add(d)
        final.append(url)
    return final

def existing_domain(cur, domain):
    row = cur.execute(
        "SELECT id FROM leads WHERE lower(website) LIKE ? LIMIT 1",
        (f"%{domain}%",)
    ).fetchone()
    return row is not None

def guess_country(keyword):
    for c in COUNTRIES:
        if f" {c}" in f" {keyword.lower()}":
            return c.upper()
    return ""

def fetch_email(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        txt = r.text[:200000]
        emails = EMAIL_RE.findall(txt)
        clean = []
        for e in emails:
            el = e.lower()
            if any(bad in el for bad in ["example.com", "domain.com", "sentry", "wixpress", "png", "jpg", "noreply"]):
                continue
            clean.append(e)
        return clean[0] if clean else ""
    except Exception:
        return ""

def save_lead(url, keyword):
    domain = domain_of(url)
    if not domain:
        return False, "no-domain"

    company = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
    country = guess_country(keyword)
    email = fetch_email(url)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    if existing_domain(cur, domain):
        conn.close()
        return False, "duplicate"

    try:
        cur.execute("""
            INSERT INTO leads(
                company, contact, email, website, country, whatsapp,
                source, category, status, level, owner, expected_amount
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            company, "", email, url, country, "",
            "AUTO COLLECT V1.4 / " + keyword,
            "ELDERLY", "NEW", "C", "admin", 0
        ))
        conn.commit()
        conn.close()
        return True, "saved"
    except Exception as e:
        conn.close()
        return False, "db-error:" + str(e)

def run():
    found = saved = skipped = failed = 0
    update_status(
        version="AUTO COLLECT V1.4 GLOBAL NO CHINA",
        status="running",
        message="Auto Collect V1.4 running",
        found=0, saved=0, skipped=0, failed=0,
        current_keyword="", current_site=""
    )
    write_log("===== AUTO COLLECT V1.4 GLOBAL NO-CHINA START =====")

    for country in COUNTRIES:
        for base_kw in KEYWORDS:
            keyword = f"{base_kw} {country}"
            update_status(current_keyword=keyword, message=f"Searching {keyword}",
                          found=found, saved=saved, skipped=skipped, failed=failed)

            for tpl in SEARCH_URLS:
                for page in [1, 11, 21, 31, 41]:
                    search_url = tpl.format(q=quote_plus(keyword), p=page)
                    try:
                        write_log("SEARCH " + search_url)
                        r = requests.get(search_url, headers=HEADERS, timeout=15)
                        links = extract_result_links(r.text)

                        for link in links:
                            found += 1
                            update_status(current_site=link, found=found, saved=saved,
                                          skipped=skipped, failed=failed)

                            ok, reason = save_lead(link, keyword)
                            if ok:
                                saved += 1
                                write_log("SAVED " + link)
                            else:
                                skipped += 1
                                # Only log useful skipped reasons, not every duplicate
                                if reason not in ("duplicate",):
                                    write_log("SKIP " + reason + " | " + link)

                        time.sleep(1)
                    except Exception as e:
                        failed += 1
                        write_log("FAILED " + str(e))
                        update_status(failed=failed)

    update_status(
        status="finished",
        message=f"Finished. Found {found}, saved {saved}, skipped {skipped}, failed {failed}",
        found=found, saved=saved, skipped=skipped, failed=failed,
        current_keyword="", current_site=""
    )
    write_log("===== AUTO COLLECT V1.4 DONE =====")

if __name__ == "__main__":
    run()
