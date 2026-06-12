#!/usr/bin/env python3
# SOGRACE CRM NEW AUTO COLLECT MODULE - Bing only
import csv, datetime as dt, html, json, random, re, sqlite3, time
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

CRM_DIR=Path("/home/admin/crm")
DB=CRM_DIR/"crm.db"
LOG_FILE=CRM_DIR/"auto_collect_new.log"
CSV_FILE=CRM_DIR/"auto_leads.csv"
STATUS_FILE=CRM_DIR/"auto_collect_status.json"
HEADERS={"User-Agent":"Mozilla/5.0 Chrome/124 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
KEYWORDS=["gps sos watch distributor germany","elderly gps watch distributor europe","senior gps tracker distributor","4g gps watch elderly supplier","gps tracker wholesaler europe","personal gps tracker importer europe","lone worker gps device distributor","gps sos pendant supplier","gps tracking solution distributor","gps tracker distributor france","gps tracker distributor italy","gps tracker distributor spain","gps tracker distributor netherlands","gps tracker distributor poland","gps tracker distributor sweden","gps tracker distributor uk"]
BAD_DOMAINS=["google.","youtube.","facebook.","instagram.","linkedin.","twitter.","x.com","amazon.","ebay.","aliexpress.","temu.","wikipedia.","reddit.","pinterest.","yahoo.","baidu.","github.","medium.com","trustpilot.","crunchbase.","zoominfo.","dnb.com","glassdoor.","indeed.","dictionary.","merriam-webster.","cambridge.org","bing.com/search"]
GOOD_WORDS=["gps","tracker","tracking","sos","elderly","senior","watch","wearable","telematics","location","lone worker","panic button","personal alarm","distributor","wholesale","wholesaler","importer","supplier","reseller","dealer"]
B2B_WORDS=["distributor","wholesale","wholesaler","importer","reseller","dealer","supplier","partner"]
EMAIL_RE=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
COUNTRY_HINTS={".de":"Germany",".fr":"France",".it":"Italy",".es":"Spain",".nl":"Netherlands",".be":"Belgium",".pl":"Poland",".se":"Sweden",".no":"Norway",".dk":"Denmark",".fi":"Finland",".co.uk":"United Kingdom",".uk":"United Kingdom",".ie":"Ireland",".pt":"Portugal",".ch":"Switzerland",".at":"Austria",".cz":"Czech Republic"}

def log(msg):
    CRM_DIR.mkdir(parents=True,exist_ok=True)
    line=f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line,flush=True)
    with LOG_FILE.open("a",encoding="utf-8") as f:f.write(line+"\n")

def status(s="Running",m="",found=0,saved=0,skipped=0,failed=0,kw="",site=""):
    STATUS_FILE.write_text(json.dumps({"version":"NEW AUTO COLLECT MODULE","status":s,"message":m,"found":found,"saved":saved,"skipped":skipped,"failed":failed,"current_keyword":kw,"current_site":site,"updated":dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")},ensure_ascii=False,indent=2),encoding="utf-8")

def domain(url):
    try:return urlparse(url).netloc.lower().replace("www.","")
    except Exception:return ""

def bad(url):
    low=url.lower()
    return (not low.startswith("http")) or any(x in low for x in BAD_DOMAINS)

def get(url,timeout=20):
    time.sleep(random.uniform(0.5,1.2))
    return requests.get(url,headers=HEADERS,timeout=timeout,allow_redirects=True)

def bing(q,max_results=8):
    urls=[];seen=set();search="https://www.bing.com/search?q="+quote_plus(q)
    try:
        r=get(search);log(f"BING SEARCH {q} -> {r.status_code}")
        if r.status_code>=400:return urls
        soup=BeautifulSoup(r.text,"html.parser")
        for a in soup.select("li.b_algo h2 a[href], a[href]"):
            href=a.get("href","")
            if bad(href):continue
            d=domain(href)
            if not d or d in seen:continue
            seen.add(d);urls.append(href)
            if len(urls)>=max_results:break
    except Exception as e:log(f"BING ERROR {q}: {e}")
    return urls

def fetch(url):
    try:
        r=get(url)
        if r.status_code>=400 or "text/html" not in r.headers.get("content-type",""):return "","",""
        soup=BeautifulSoup(r.text,"html.parser")
        title=soup.title.get_text(" ",strip=True) if soup.title else domain(r.url)
        return title,soup.get_text(" ",strip=True),r.url
    except Exception as e:
        log(f"FETCH ERROR {url}: {e}");return "","",""

def contact_pages(base):
    pages=[base]
    try:
        r=get(base);soup=BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all("a",href=True):
            t=(a.get_text(" ",strip=True)+" "+a["href"]).lower()
            if any(k in t for k in ["contact","about","impressum","imprint","support"]):
                full=urljoin(base,a["href"])
                if domain(full)==domain(base):pages.append(full)
    except Exception:pass
    return list(dict.fromkeys(pages))[:4]

def country(url,text=""):
    d=domain(url)
    for suf,c in COUNTRY_HINTS.items():
        if d.endswith(suf):return c
    low=(d+" "+text[:2000]).lower()
    for c in set(COUNTRY_HINTS.values()):
        if c.lower() in low:return c
    return ""

def score(url,title,body):
    low=f"{url} {title} {body[:6000]}".lower();s=0
    for w in GOOD_WORDS:
        if w in low:s+=8
    for w in B2B_WORDS:
        if w in low:s+=15
    if any(x in low for x in ["gps watch","sos watch","elderly gps","personal gps","gps tracker"]):s+=25
    if any(x in low for x in ["contact us","about us","products","solutions"]):s+=10
    if any(x in low for x in ["blog","news","review only","dictionary"]):s-=15
    return max(0,min(100,s))

def product(text):
    low=text.lower()
    if "watch" in low or "elderly" in low or "senior" in low:return "GPS SOS Watch"
    if "vehicle" in low or "fleet" in low:return "Vehicle Tracker"
    if "pet" in low:return "Pet Tracker"
    if "platform" in low or "software" in low:return "GPS Platform"
    return "GPS Tracker"

def value(s):return "★★★★★" if s>=80 else "★★★★" if s>=60 else "★★★" if s>=40 else "★★" if s>=20 else "★"

def ensure_db():
    conn=sqlite3.connect(DB);cur=conn.cursor()
    for col,spec in [("contact","TEXT DEFAULT ''"),("country","TEXT DEFAULT ''"),("whatsapp","TEXT DEFAULT ''"),("source","TEXT DEFAULT ''"),("level","TEXT DEFAULT 'C'"),("owner","TEXT DEFAULT ''"),("next_followup","TEXT DEFAULT ''"),("history","TEXT DEFAULT ''"),("product_interest","TEXT DEFAULT ''"),("customer_value","TEXT DEFAULT '★'"),("last_contact","TEXT DEFAULT ''"),("expected_amount","TEXT DEFAULT '0'")]:
        try:cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {spec}")
        except Exception:pass
    conn.commit();conn.close()

def exists(conn,email,web):
    if email and conn.execute("SELECT id FROM leads WHERE LOWER(email)=LOWER(?) LIMIT 1",(email,)).fetchone():return True
    d=domain(web)
    if d and conn.execute("SELECT id FROM leads WHERE website LIKE ? LIMIT 1",(f"%{d}%",)).fetchone():return True
    return False

def append_csv(lead):
    ex=CSV_FILE.exists();fields=["company","email","website","country","category","level","product_interest","customer_value","expected_amount","score","source"]
    with CSV_FILE.open("a",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        if not ex:w.writeheader()
        w.writerow({k:lead.get(k,"") for k in fields})

def save(lead):
    if not lead or lead.get("score",0)<25:return False
    conn=sqlite3.connect(DB)
    if exists(conn,lead.get("email",""),lead.get("website","")):conn.close();return False
    now=dt.datetime.now().strftime("%Y-%m-%d %H:%M");hist=f"{now} New auto collect module | Score {lead['score']}"
    conn.execute("INSERT INTO leads (company,email,website,category,status,note,country,contact,whatsapp,source,level,owner,next_followup,history,product_interest,customer_value,last_contact,expected_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(lead["company"],lead["email"],lead["website"],lead["category"],"NEW",lead["note"],lead["country"],"","",lead["source"],lead["level"],"","",hist,lead["product_interest"],lead["customer_value"],now,lead["expected_amount"]))
    conn.commit();conn.close();append_csv(lead);return True

def extract(url):
    title,body,final=fetch(url)
    if not body:return None
    texts=[body]
    for p in contact_pages(final or url)[1:]:
        _,b,_=fetch(p)
        if b:texts.append(b)
    text=" ".join(texts)
    emails=[e.lower() for e in EMAIL_RE.findall(text) if not any(x in e.lower() for x in ["png","jpg","jpeg","webp","gif","svg","sentry","wixpress","noreply"])]
    sc=score(final or url,title,text);d=domain(final or url)
    comp=html.unescape((title.split("|")[0].split("-")[0].strip() or d)[:120])
    return {"company":comp,"email":emails[0] if emails else "","website":final or url,"country":country(final or url,text),"source":"New Auto Collect Module Bing Only","category":"DISTRIBUTOR" if any(w in text.lower() for w in B2B_WORDS) else "ELDERLY","note":f"new_auto_collect score={sc}; domain={d}","level":"A" if sc>=70 else "B" if sc>=45 else "C","product_interest":product(text),"customer_value":value(sc),"expected_amount":"5000" if sc>=70 else "2000" if sc>=45 else "0","score":sc}

def main():
    CRM_DIR.mkdir(parents=True,exist_ok=True);ensure_db()
    found=saved=skipped=failed=0;seen=set()
    status("Running","New auto collect started");log("===== NEW AUTO COLLECT MODULE START =====")
    for kw in KEYWORDS:
        status("Running",f"Searching {kw}",found,saved,skipped,failed,kw,"")
        for url in bing(kw,8):
            d=domain(url)
            if not d or d in seen:skipped+=1;continue
            seen.add(d);status("Running",f"Checking {d}",found,saved,skipped,failed,kw,d);log(f"CHECK {url}")
            try:
                lead=extract(url);found+=1
                if lead and save(lead):saved+=1;log(f"SAVED {lead['company']} | {lead['email']} | {lead['website']} | score={lead['score']}")
                else:skipped+=1;log(f"SKIP {d}")
            except Exception as e:failed+=1;log(f"ERROR {url}: {e}")
            status("Running",f"Progress found={found} saved={saved}",found,saved,skipped,failed,kw,d)
    status("Finished","New auto collect finished",found,saved,skipped,failed)
    log(f"===== NEW AUTO COLLECT FINISHED found={found} saved={saved} skipped={skipped} failed={failed} =====")

if __name__=="__main__":main()
