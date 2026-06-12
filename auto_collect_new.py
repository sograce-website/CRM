#!/usr/bin/env python3
# SOGRACE CRM Auto Collect V1.1 Professional
# Bing only. Better URL extraction. Real website fetch. Email extraction. CRM DB save.

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

CRM_DIR = Path("/home/admin/crm")
DB = CRM_DIR / "crm.db"
LOG_FILE = CRM_DIR / "auto_collect_new.log"
CSV_FILE = CRM_DIR / "auto_leads.csv"
STATUS_FILE = CRM_DIR / "auto_collect_status.json"
DEBUG_URLS_FILE = CRM_DIR / "auto_collect_debug_urls.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = [
    "gps sos watch distributor germany",
    "elderly gps watch distributor europe",
    "senior gps tracker distributor",
    "4g gps watch elderly supplier",
    "gps tracker wholesaler europe",
    "personal gps tracker importer europe",
    "lone worker gps device distributor",
    "gps sos pendant supplier",
    "gps tracking solution distributor",
    "gps tracker distributor france",
    "gps tracker distributor italy",
    "gps tracker distributor spain",
    "gps tracker distributor netherlands",
    "gps tracker distributor poland",
    "gps tracker distributor sweden",
    "gps tracker distributor uk",
    "gps tracker reseller europe",
    "gps tracking device importer europe",
    "personal alarm gps distributor europe",
]

BAD_DOMAINS = [
    "google.", "youtube.", "facebook.", "instagram.", "linkedin.", "twitter.", "x.com",
    "amazon.", "ebay.", "aliexpress.", "temu.", "wikipedia.", "reddit.", "pinterest.",
    "yahoo.", "baidu.", "github.", "medium.com", "trustpilot.", "crunchbase.",
    "zoominfo.", "dnb.com", "glassdoor.", "indeed.", "dictionary.", "merriam-webster.",
    "cambridge.org", "bing.com", "microsoft.com", "office.com", "live.com",
]

GOOD_WORDS = [
    "gps", "tracker", "tracking", "sos", "elderly", "senior", "watch", "wearable",
    "telematics", "location", "lone worker", "panic button", "personal alarm",
    "distributor", "wholesale", "wholesaler", "importer", "supplier", "reseller", "dealer",
    "fleet", "asset tracking", "personal safety",
]
B2B_WORDS = ["distributor", "wholesale", "wholesaler", "importer", "reseller", "dealer", "supplier", "partner"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

COUNTRY_HINTS = {
    ".de": "Germany", ".fr": "France", ".it": "Italy", ".es": "Spain",
    ".nl": "Netherlands", ".be": "Belgium", ".pl": "Poland",
    ".se": "Sweden", ".no": "Norway", ".dk": "Denmark", ".fi": "Finland",
    ".co.uk": "United Kingdom", ".uk": "United Kingdom", ".ie": "Ireland",
    ".pt": "Portugal", ".ch": "Switzerland", ".at": "Austria", ".cz": "Czech Republic",
}

def log(msg: str) -> None:
    CRM_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def write_status(status="Running", message="", found=0, saved=0, skipped=0, failed=0, current_keyword="", current_site=""):
    STATUS_FILE.write_text(json.dumps({
        "version": "AUTO COLLECT V1.1 PRO",
        "status": status,
        "message": message,
        "found": found,
        "saved": saved,
        "skipped": skipped,
        "failed": failed,
        "current_keyword": current_keyword,
        "current_site": current_site,
        "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def normalize_url(href: str) -> str:
    if not href:
        return ""
    href = html.unescape(href.strip())

    # Bing sometimes uses redirect URLs.
    if "bing.com/ck/a" in href or "bing.com/aclick" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        for key in ("u", "url", "r"):
            if key in qs and qs[key]:
                val = qs[key][0]
                if val.startswith("a1"):
                    val = val[2:]
                href = unquote(val)
                break

    if href.startswith("//"):
        href = "https:" + href
    if not href.startswith("http"):
        return ""
    return href.split("#")[0]

def is_bad_url(url: str) -> bool:
    low = url.lower()
    if not low.startswith("http"):
        return True
    if any(x in low for x in BAD_DOMAINS):
        return True
    if any(x in low for x in [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip"]):
        return True
    return False

def safe_get(url: str, timeout=20):
    time.sleep(random.uniform(0.4, 1.1))
    return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)

def extract_bing_urls(search_html: str, max_results=10):
    soup = BeautifulSoup(search_html, "html.parser")
    candidates = []

    selectors = [
        "li.b_algo h2 a[href]",
        "h2 a[href]",
        "a[href]",
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = normalize_url(a.get("href", ""))
            if not href or is_bad_url(href):
                continue
            d = domain_of(href)
            if not d:
                continue
            title = a.get_text(" ", strip=True)
            candidates.append((href, d, title))

    # fallback regex from html
    for m in re.finditer(r'https?://[^\s"<>]+', search_html):
        href = normalize_url(m.group(0))
        if href and not is_bad_url(href):
            candidates.append((href, domain_of(href), ""))

    urls, seen = [], set()
    for href, d, title in candidates:
        if d in seen:
            continue
        seen.add(d)
        urls.append(href)
        if len(urls) >= max_results:
            break
    return urls

def bing_search(query: str, max_results=10):
    url = "https://www.bing.com/search?q=" + quote_plus(query)
    try:
        r = safe_get(url, timeout=20)
        log(f"BING SEARCH {query} -> {r.status_code}")
        if r.status_code >= 400:
            return []
        urls = extract_bing_urls(r.text, max_results=max_results)
        with DEBUG_URLS_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n### {dt.datetime.now()} | {query} | urls={len(urls)}\n")
            for u in urls:
                f.write(u + "\n")
        for u in urls:
            log(f"URL {u}")
        return urls
    except Exception as e:
        log(f"BING ERROR {query}: {e}")
        return []

def fetch_html(url: str):
    try:
        r = safe_get(url, timeout=20)
        ctype = r.headers.get("content-type", "")
        if r.status_code >= 400 or "text/html" not in ctype:
            return "", "", ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else domain_of(r.url)
        body = soup.get_text(" ", strip=True)
        return title, body, r.url
    except Exception as e:
        log(f"FETCH ERROR {url}: {e}")
        return "", "", ""

def contact_pages(base_url: str):
    pages = [base_url]
    try:
        r = safe_get(base_url, timeout=20)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
            return pages
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            t = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
            if any(k in t for k in ["contact", "about", "impressum", "imprint", "support", "kontakt"]):
                full = urljoin(base_url, a["href"])
                if full.startswith("http") and domain_of(full) == domain_of(base_url):
                    pages.append(full)
    except Exception:
        pass
    return list(dict.fromkeys(pages))[:5]

def guess_country(url: str, text: str = "") -> str:
    d = domain_of(url)
    for suffix, country in COUNTRY_HINTS.items():
        if d.endswith(suffix):
            return country
    low = (d + " " + text[:3000]).lower()
    for country in set(COUNTRY_HINTS.values()):
        if country.lower() in low:
            return country
    return ""

def score_site(url: str, title: str, body: str) -> int:
    low = f"{url} {title} {body[:7000]}".lower()
    score = 0
    for w in GOOD_WORDS:
        if w in low:
            score += 7
    for w in B2B_WORDS:
        if w in low:
            score += 15
    if any(x in low for x in ["gps watch", "sos watch", "elderly gps", "personal gps", "gps tracker", "tracking device"]):
        score += 25
    if any(x in low for x in ["contact us", "about us", "products", "solutions", "become a partner"]):
        score += 10
    if any(x in low for x in ["blog", "news", "review only", "dictionary"]):
        score -= 15
    return max(0, min(100, score))

def product_interest(text: str):
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

def customer_value(score: int):
    if score >= 80: return "★★★★★"
    if score >= 60: return "★★★★"
    if score >= 40: return "★★★"
    if score >= 20: return "★★"
    return "★"

def ensure_db_columns():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for col, spec in [
        ("contact", "TEXT DEFAULT ''"), ("country", "TEXT DEFAULT ''"), ("whatsapp", "TEXT DEFAULT ''"),
        ("source", "TEXT DEFAULT ''"), ("level", "TEXT DEFAULT 'C'"), ("owner", "TEXT DEFAULT ''"),
        ("next_followup", "TEXT DEFAULT ''"), ("history", "TEXT DEFAULT ''"), ("product_interest", "TEXT DEFAULT ''"),
        ("customer_value", "TEXT DEFAULT '★'"), ("last_contact", "TEXT DEFAULT ''"), ("expected_amount", "TEXT DEFAULT '0'"),
    ]:
        try:
            cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {spec}")
        except Exception:
            pass
    conn.commit()
    conn.close()

def exists_lead(conn, email: str, website: str):
    if email:
        row = conn.execute("SELECT id FROM leads WHERE LOWER(email)=LOWER(?) LIMIT 1", (email,)).fetchone()
        if row:
            return True
    d = domain_of(website)
    if d:
        row = conn.execute("SELECT id FROM leads WHERE website LIKE ? LIMIT 1", (f"%{d}%",)).fetchone()
        if row:
            return True
    return False

def append_csv(lead: dict):
    exists = CSV_FILE.exists()
    fields = ["company", "email", "website", "country", "category", "level", "product_interest", "customer_value", "expected_amount", "score", "source"]
    with CSV_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({k: lead.get(k, "") for k in fields})

def save_lead(lead: dict):
    if not lead or lead.get("score", 0) < 15:
        return False
    conn = sqlite3.connect(DB)
    if exists_lead(conn, lead.get("email", ""), lead.get("website", "")):
        conn.close()
        return False
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    history = f"{now} Auto Collect V1.1 Pro | Score {lead['score']}"
    conn.execute("""
        INSERT INTO leads
        (company,email,website,category,status,note,country,contact,whatsapp,source,level,owner,next_followup,history,product_interest,customer_value,last_contact,expected_amount)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        lead["company"], lead["email"], lead["website"], lead["category"], "NEW", lead["note"],
        lead["country"], "", "", lead["source"], lead["level"], "", "", history,
        lead["product_interest"], lead["customer_value"], now, lead["expected_amount"]
    ))
    conn.commit()
    conn.close()
    append_csv(lead)
    return True

def extract_lead(url: str):
    title, body, final_url = fetch_html(url)
    if not body:
        return None
    texts = [body]
    for p in contact_pages(final_url or url)[1:]:
        _, b, _ = fetch_html(p)
        if b:
            texts.append(b)
    text = " ".join(texts)
    emails = EMAIL_RE.findall(text)
    emails = [
        e.lower() for e in emails
        if not any(x in e.lower() for x in ["png", "jpg", "jpeg", "webp", "gif", "svg", "sentry", "wixpress", "noreply", "example"])
    ]
    sc = score_site(final_url or url, title, text)
    d = domain_of(final_url or url)
    company = html.unescape((title.split("|")[0].split("-")[0].strip() or d)[:120])
    return {
        "company": company,
        "email": emails[0] if emails else "",
        "website": final_url or url,
        "country": guess_country(final_url or url, text),
        "source": "Auto Collect V1.1 Pro Bing Only",
        "category": "DISTRIBUTOR" if any(w in text.lower() for w in B2B_WORDS) else "ELDERLY",
        "note": f"auto_collect_v11 score={sc}; domain={d}",
        "level": "A" if sc >= 70 else "B" if sc >= 45 else "C",
        "product_interest": product_interest(text),
        "customer_value": customer_value(sc),
        "expected_amount": "5000" if sc >= 70 else "2000" if sc >= 45 else "0",
        "score": sc,
    }

def main():
    CRM_DIR.mkdir(parents=True, exist_ok=True)
    ensure_db_columns()
    found = saved = skipped = failed = 0
    seen_domains = set()
    write_status("Running", "Auto Collect V1.1 started", found, saved, skipped, failed)
    log("===== AUTO COLLECT V1.1 PRO START =====")
    for kw in KEYWORDS:
        write_status("Running", f"Searching {kw}", found, saved, skipped, failed, kw, "")
        urls = bing_search(kw, 10)
        if not urls:
            log(f"NO URLS {kw}")
        for url in urls:
            d = domain_of(url)
            if not d or d in seen_domains:
                skipped += 1
                continue
            seen_domains.add(d)
            write_status("Running", f"Checking {d}", found, saved, skipped, failed, kw, d)
            log(f"CHECK {url}")
            try:
                lead = extract_lead(url)
                found += 1
                if lead:
                    log(f"LEAD {lead['company']} | email={lead['email']} | score={lead['score']} | {lead['website']}")
                if lead and save_lead(lead):
                    saved += 1
                    log(f"SAVED {lead['company']} | {lead['email']} | {lead['website']} | score={lead['score']}")
                else:
                    skipped += 1
                    log(f"SKIP {d}")
            except Exception as e:
                failed += 1
                log(f"ERROR {url}: {e}")
            write_status("Running", f"Progress found={found} saved={saved}", found, saved, skipped, failed, kw, d)
    write_status("Finished", "Auto Collect V1.1 finished", found, saved, skipped, failed)
    log(f"===== AUTO COLLECT V1.1 FINISHED found={found} saved={saved} skipped={skipped} failed={failed} =====")

if __name__ == "__main__":
    main()
