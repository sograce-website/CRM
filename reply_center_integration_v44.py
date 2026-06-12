# reply_center_integration_v44.py
# SOGRACE CRM V4.4 P1 - Reply Center Integrated
# 集成到 CRM 首页导航，显示最近 50 个 Lead 回复状态

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
from pathlib import Path
import datetime

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"

app = FastAPI()

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

@app.get("/reply_center", response_class=HTMLResponse)
def reply_center(request: Request):
    rows = get_reply_status(50)

    html = """
    <html>
    <head>
    <title>Reply Center - SOGRACE CRM V4.4</title>
    <style>
        table {border-collapse: collapse; width: 100%;}
        th, td {border: 1px solid #ddd; padding: 8px;}
        th {background-color: #f2f2f2;}
    </style>
    </head>
    <body>
    <h2>Reply Center (V4.4 Professional)</h2>
    <table>
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

    html += """
    </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
