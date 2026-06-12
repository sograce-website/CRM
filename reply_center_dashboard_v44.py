# reply_center_dashboard_v44.py
# SOGRACE CRM V4.4 P1 - Reply Center Web Integration
# 作用：读取 info@sograce.cn 收件箱，匹配 CRM leads 邮箱，并在网页显示最近回复状态

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import datetime
from pathlib import Path

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"
LOG_FILE = CRM_DIR / "reply_center.log"

app = FastAPI()

# 从数据库读取最近回复 Lead
def get_reply_status(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    rows = c.execute("""
        SELECT company, email, status, last_contact
        FROM leads
        ORDER BY last_contact DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

# 显示 Dashboard HTML
@app.get("/reply_center", response_class=HTMLResponse)
def reply_center_dashboard(request: Request):
    rows = get_reply_status(50)

    html = """
    <h2>Reply Center (V4.4 Professional)</h2>
    <table border="1" cellpadding="5" cellspacing="0">
    <tr>
        <th>Company</th>
        <th>Email</th>
        <th>Status</th>
        <th>Last Contact</th>
    </tr>
    """
    for r in rows:
        company, email_addr, status, last_contact = r
        last_contact = last_contact if last_contact else "-"
        html += f"<tr><td>{company}</td><td>{email_addr}</td><td>{status}</td><td>{last_contact}</td></tr>"
    html += "</table>"
    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
