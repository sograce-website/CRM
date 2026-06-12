from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, time
from pathlib import Path

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def yn(v): return "<span class='good'>RUNNING</span>" if v else "<span class='warn'>STOPPED</span>"

def table(rows):
    if not rows or len(rows)==0: return "<tr><td>No data</td></tr>"
    h="<tr><th>Company</th><th>Owner</th><th>Date</th></tr>"
    for r in rows: h+= f"<tr><td>{r[0] or ''}</td><td>{r[1] or ''}</td><td>{r[2] or ''}</td></tr>"
    return h

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html = '''<html><head>
    <title>SOGRACE CRM Dashboard V4.5</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
    <style>
    body{{background:#07111f;color:white;font-family:Arial;margin:0;padding:25px}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}}
    .card{{background:#111d33;padding:20px;border-radius:14px;margin-bottom:18px}}
    .stat{{font-size:28px;font-weight:bold;color:#36a3ff}}
    .good{{color:#00d084;font-weight:bold}}
    .warn{{color:#ffd166;font-weight:bold}}
    table{{width:100%;border-collapse:collapse}}
    td,th{{padding:9px;border-bottom:1px solid #24344f;text-align:left}}
    a{{color:white}}
    </style>
    </head><body>
    <h1>📊 SOGRACE CRM Live Dashboard V4.5</h1>
    <p><a href="/">Back CRM</a> | Auto refresh every 5 seconds</p>
    <div id="dashboard"></div>
    <script>
    async function load(){{
        let d=await fetch('/dashboard_status').then(r=>r.json())
        document.getElementById('dashboard').innerHTML=JSON.stringify(d,null,2)
    }}
    load(); setInterval(load,5000)
    </script>
    </body></html>'''
    return HTMLResponse(content=html)

@app.get("/dashboard_status")
async def dashboard_status():
    # 模拟数据，可替换为真实 db 查询
    return {{
        "finding_customers": True,
        "email_sending": True,
        "sent_emails": 10,
        "failed_emails": 0,
        "total_leads": 946,
        "pipeline_value": 5000,
        "quote_rate": "0%",
        "order_rate": "0%",
        "today_leads": 36,
        "today_emails": 428,
        "today_replies": 12,
        "today_quotes": 4
    }}
