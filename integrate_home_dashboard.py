#!/usr/bin/env python3
from pathlib import Path
import re
from datetime import datetime

MAIN = Path("main.py")
if not MAIN.exists():
    raise SystemExit("ERROR: main.py not found. Run this in CRM project folder.")

src = MAIN.read_text(encoding="utf-8")
backup = MAIN.with_name("main.py.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.write_text(src, encoding="utf-8")

if "from fastapi.responses import" in src:
    src = re.sub(
        r"from fastapi\.responses import ([^\n]+)",
        lambda m: m.group(0) if "HTMLResponse" in m.group(1) else "from fastapi.responses import " + m.group(1).strip() + ", HTMLResponse",
        src,
        count=1,
    )
else:
    if "from fastapi import" in src:
        src = src.replace("from fastapi import", "from fastapi.responses import HTMLResponse\nfrom fastapi import", 1)
    else:
        src = "from fastapi.responses import HTMLResponse\n" + src

dashboard_code = '''
# ===== SOGRACE CRM HOME DASHBOARD START =====
@app.get("/", response_class=HTMLResponse)
def home_dashboard(request: Request):
    total = 0
    new_count = contacted_count = quoted_count = sample_count = negotiation_count = ordered_count = lost_count = 0
    pipeline_value = 0

    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads")
        total = cur.fetchone()[0] or 0

        def count_status(status):
            cur.execute("SELECT COUNT(*) FROM leads WHERE UPPER(COALESCE(status,''))=?", (status,))
            return cur.fetchone()[0] or 0

        new_count = count_status("NEW")
        contacted_count = count_status("CONTACTED")
        quoted_count = count_status("QUOTED")
        sample_count = count_status("SAMPLE")
        negotiation_count = count_status("NEGOTIATION")
        ordered_count = count_status("ORDERED")
        lost_count = count_status("LOST")

        try:
            cur.execute("SELECT COALESCE(SUM(CAST(expected_amount AS REAL)),0) FROM leads")
            pipeline_value = cur.fetchone()[0] or 0
        except Exception:
            pipeline_value = 0

        conn.close()
    except Exception:
        pass

    quote_rate = round((quoted_count / total * 100), 1) if total else 0
    order_rate = round((ordered_count / total * 100), 1) if total else 0

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>SOGRACE CRM Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f5f7fb; margin:0; color:#111827; }}
.top {{ background:#0f172a; color:white; padding:18px 26px; display:flex; justify-content:space-between; align-items:center; }}
.top a {{ color:white; text-decoration:none; margin-left:14px; font-weight:600; }}
.wrap {{ padding:24px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; }}
.card {{ background:white; border-radius:14px; padding:18px; box-shadow:0 4px 14px rgba(0,0,0,.06); }}
.label {{ font-size:13px; color:#6b7280; }}
.num {{ font-size:30px; font-weight:800; margin-top:8px; }}
.section {{ margin-top:24px; background:white; border-radius:14px; padding:18px; box-shadow:0 4px 14px rgba(0,0,0,.06); }}
.btn {{ display:inline-block; padding:10px 14px; background:#2563eb; color:white; border-radius:8px; text-decoration:none; margin-right:8px; margin-top:8px; }}
</style>
</head>
<body>
<div class="top">
  <div><b>SOGRACE CRM</b> · Home Dashboard</div>
  <div>
    <a href="/leads">Leads</a>
    <a href="/import">Import</a>
    <a href="/export">Export</a>
    <a href="/users">Users</a>
  </div>
</div>
<div class="wrap">
  <div class="grid">
    <div class="card"><div class="label">TOTAL LEADS</div><div class="num">{total}</div></div>
    <div class="card"><div class="label">NEW</div><div class="num">{new_count}</div></div>
    <div class="card"><div class="label">CONTACTED</div><div class="num">{contacted_count}</div></div>
    <div class="card"><div class="label">QUOTED</div><div class="num">{quoted_count}</div></div>
    <div class="card"><div class="label">SAMPLE</div><div class="num">{sample_count}</div></div>
    <div class="card"><div class="label">NEGOTIATION</div><div class="num">{negotiation_count}</div></div>
    <div class="card"><div class="label">ORDERED</div><div class="num">{ordered_count}</div></div>
    <div class="card"><div class="label">LOST</div><div class="num">{lost_count}</div></div>
    <div class="card"><div class="label">PIPELINE VALUE</div><div class="num">${pipeline_value:,.0f}</div></div>
    <div class="card"><div class="label">QUOTE RATE</div><div class="num">{quote_rate}%</div></div>
    <div class="card"><div class="label">ORDER RATE</div><div class="num">{order_rate}%</div></div>
  </div>
  <div class="section">
    <h2>Quick Actions</h2>
    <a class="btn" href="/add">Add Lead</a>
    <a class="btn" href="/leads">Lead List</a>
    <a class="btn" href="/today">Today Follow Up</a>
    <a class="btn" href="/overdue">Overdue Follow Up</a>
    <a class="btn" href="/bulk_send/10">Send 10</a>
    <a class="btn" href="/bulk_send/50">Send 50</a>
    <a class="btn" href="/bulk_send/100">Send 100</a>
  </div>
</div>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/dashboard_status")
def dashboard_status():
    return {"status": "ok", "service": "SOGRACE CRM", "page": "/"}
# ===== SOGRACE CRM HOME DASHBOARD END =====
'''

pattern = re.compile(
    r'\n@app\.get\(\s*["\']/["\'].*?\n(?:async\s+def|def)\s+\w+\([^)]*\):\n(?:    .*\n|\s*\n)*',
    re.S
)
src2, n = pattern.subn("\n" + dashboard_code + "\n", src, count=1)

if n == 0:
    src2 = src.rstrip() + "\n\n" + dashboard_code + "\n"

MAIN.write_text(src2, encoding="utf-8")
print("OK: main.py updated.")
print("Backup saved:", backup.name)
print("Next commands:")
print("python3 -m py_compile main.py")
print("pkill -f 'uvicorn main:app' || true")
print("nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &")
