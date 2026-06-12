#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re

MAIN = Path("main.py")
if not MAIN.exists():
    raise SystemExit("ERROR: 当前目录没有 main.py，请先 cd 到 CRM 项目目录")

src = MAIN.read_text(encoding="utf-8")
bak = MAIN.with_name("main.py.bak_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
bak.write_text(src, encoding="utf-8")

if "import sqlite3" not in src:
    src = "import sqlite3\n" + src

if "from fastapi.responses import" in src:
    src = re.sub(
        r"from fastapi\.responses import ([^\n]+)",
        lambda m: m.group(0) if "HTMLResponse" in m.group(1) else "from fastapi.responses import " + m.group(1).strip() + ", HTMLResponse",
        src,
        count=1,
    )
else:
    src = "from fastapi.responses import HTMLResponse\n" + src

m = re.search(r"from fastapi import ([^\n]+)", src)
if m and "Request" not in m.group(1):
    src = re.sub(r"from fastapi import ([^\n]+)", lambda x: "from fastapi import " + x.group(1).strip() + ", Request", src, count=1)

dashboard = '\n# ===== SOGRACE CRM HOME DASHBOARD START =====\n@app.get("/", response_class=HTMLResponse)\ndef home_dashboard(request: Request):\n    try:\n        user = request.cookies.get("crm_user")\n        if not user:\n            return HTMLResponse(\'<script>location.href="/login"</script>\')\n    except Exception:\n        pass\n\n    total = new_count = contacted_count = quoted_count = sample_count = negotiation_count = ordered_count = lost_count = 0\n    pipeline_value = 0\n\n    try:\n        conn = sqlite3.connect(DB_FILE)\n        cur = conn.cursor()\n        cur.execute("SELECT COUNT(*) FROM leads")\n        total = cur.fetchone()[0] or 0\n\n        def count_status(s):\n            cur.execute("SELECT COUNT(*) FROM leads WHERE UPPER(COALESCE(status,\'\'))=?", (s,))\n            return cur.fetchone()[0] or 0\n\n        new_count = count_status("NEW")\n        contacted_count = count_status("CONTACTED")\n        quoted_count = count_status("QUOTED")\n        sample_count = count_status("SAMPLE")\n        negotiation_count = count_status("NEGOTIATION")\n        ordered_count = count_status("ORDERED")\n        lost_count = count_status("LOST")\n\n        for col in ["expected_amount", "value", "amount"]:\n            try:\n                cur.execute(f"SELECT COALESCE(SUM(CAST({col} AS REAL)),0) FROM leads")\n                pipeline_value = cur.fetchone()[0] or 0\n                break\n            except Exception:\n                pass\n        conn.close()\n    except Exception:\n        pass\n\n    quote_rate = round(quoted_count / total * 100, 1) if total else 0\n    order_rate = round(ordered_count / total * 100, 1) if total else 0\n\n    html = f"""\n<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>SOGRACE CRM</title>\n<style>\nbody{{margin:0;font-family:Arial;background:#f5f7fb;color:#111827}}\n.top{{background:#07111f;color:white;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}}\n.top a{{color:white;text-decoration:none;margin-left:15px;font-weight:600}}\n.wrap{{padding:24px}}\n.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px}}\n.card{{background:white;border-radius:14px;padding:18px;box-shadow:0 5px 18px rgba(0,0,0,.08)}}\n.label{{font-size:13px;color:#6b7280}}\n.num{{font-size:30px;font-weight:800;margin-top:8px}}\n.section{{margin-top:24px;background:white;border-radius:14px;padding:18px;box-shadow:0 5px 18px rgba(0,0,0,.08)}}\n.btn{{display:inline-block;padding:10px 14px;background:#2563eb;color:white;border-radius:8px;text-decoration:none;margin:6px 8px 0 0}}\n</style>\n</head>\n<body>\n<div class="top">\n  <div><b>SOGRACE CRM</b> · Dashboard</div>\n  <div>\n    <a href="/">Dashboard</a>\n    <a href="/leads">Leads</a>\n    <a href="/add">Add Lead</a>\n    <a href="/users">Users</a>\n    <a href="/logout">Logout</a>\n  </div>\n</div>\n<div class="wrap">\n  <div class="grid">\n    <div class="card"><div class="label">TOTAL LEADS</div><div class="num">{total}</div></div>\n    <div class="card"><div class="label">NEW</div><div class="num">{new_count}</div></div>\n    <div class="card"><div class="label">CONTACTED</div><div class="num">{contacted_count}</div></div>\n    <div class="card"><div class="label">QUOTED</div><div class="num">{quoted_count}</div></div>\n    <div class="card"><div class="label">SAMPLE</div><div class="num">{sample_count}</div></div>\n    <div class="card"><div class="label">NEGOTIATION</div><div class="num">{negotiation_count}</div></div>\n    <div class="card"><div class="label">ORDERED</div><div class="num">{ordered_count}</div></div>\n    <div class="card"><div class="label">LOST</div><div class="num">{lost_count}</div></div>\n    <div class="card"><div class="label">PIPELINE VALUE</div><div class="num">${pipeline_value:,.0f}</div></div>\n    <div class="card"><div class="label">QUOTE RATE</div><div class="num">{quote_rate}%</div></div>\n    <div class="card"><div class="label">ORDER RATE</div><div class="num">{order_rate}%</div></div>\n  </div>\n  <div class="section">\n    <h2>Quick Actions</h2>\n    <a class="btn" href="/add">Add Lead</a>\n    <a class="btn" href="/leads">Lead List</a>\n    <a class="btn" href="/today">Today Follow Up</a>\n    <a class="btn" href="/overdue">Overdue Follow Up</a>\n    <a class="btn" href="/import">Import</a>\n    <a class="btn" href="/export">Export</a>\n    <a class="btn" href="/bulk_send/10">Send 10</a>\n    <a class="btn" href="/bulk_send/50">Send 50</a>\n    <a class="btn" href="/bulk_send/100">Send 100</a>\n  </div>\n</div>\n</body>\n</html>\n"""\n    return HTMLResponse(html)\n\n\n@app.get("/dashboard", response_class=HTMLResponse)\ndef dashboard_alias(request: Request):\n    return home_dashboard(request)\n# ===== SOGRACE CRM HOME DASHBOARD END =====\n'

src = re.sub(r'\n@app\.get\(\s*["\']/["\'][\s\S]*?(?=\n@app\.|\nif __name__|\Z)', '\n', src, count=1)
src = re.sub(r'\n@app\.get\(\s*["\']/dashboard["\'][\s\S]*?(?=\n@app\.|\nif __name__|\Z)', '\n', src, count=1)
src = src.rstrip() + "\n\n" + dashboard + "\n"

MAIN.write_text(src, encoding="utf-8")
print("OK：已把仪表盘整合到 / 首页，并保留 /dashboard 入口")
print("备份文件：", bak.name)
print("下一步执行：")
print("python3 -m py_compile main.py")
print("pkill -f 'uvicorn main:app' || true")
print("nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &")
