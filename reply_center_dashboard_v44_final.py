# reply_center_dashboard_v44_final.py
# SOGRACE CRM V4.4 P1 - Reply Center Dashboard Integrated
# 基于 main_current.py

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3, datetime
from pathlib import Path

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"
LOG_FILE = CRM_DIR / "reply_center.log"

app = FastAPI()

def get_leads(limit=50):
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("""
        SELECT company,email,status,last_contact
        FROM leads
        ORDER BY last_contact DESC
        LIMIT ?
    """,(limit,)).fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    data = {}
    for st in ["NEW","CONTACTED","REPLIED","QUOTED","SAMPLE","NEGOTIATION","ORDERED","LOST"]:
        data[st] = c.execute("SELECT COUNT(*) FROM leads WHERE status=?", (st,)).fetchone()[0]
    data["TOTAL"] = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    return data

@app.get("/reply_center", response_class=HTMLResponse)
def reply_center(request: Request):
    stats_data = get_stats()
    leads = get_leads(50)

    html = f"""
    <html><head><title>Reply Center - SOGRACE CRM V4.4</title>
    <style>
    body{{font-family:Arial;background:#07111f;color:white;margin:0;padding:20px}}
    .card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
    table{{width:100%;border-collapse:collapse}}
    th,td{{padding:10px;border-bottom:1px solid #333;text-align:left}}
    th{{background:#0b1f3a}}
    </style></head>
    <body>
    <h2>Reply Center (V4.4 Professional)</h2>

    <div class="card">
    <h3>Lead Status Summary</h3>
    <table>
    <tr><th>Status</th><th>Count</th></tr>
    """
    for k,v in stats_data.items():
        html += f"<tr><td>{k}</td><td>{v}</td></tr>"
    html += "</table></div>"

    html += """
    <div class="card">
    <h3>Recent Leads (Last 50)</h3>
    <table>
    <tr><th>Company</th><th>Email</th><th>Status</th><th>Last Contact</th></tr>
    """
    for l in leads:
        company,email_addr,status,last_contact = l
        last_contact = last_contact if last_contact else "-"
        html += f"<tr><td>{company}</td><td>{email_addr}</td><td>{status}</td><td>{last_contact}</td></tr>"
    html += "</table></div></body></html>"

    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
