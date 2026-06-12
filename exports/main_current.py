from pathlib import Path
from pathlib import Path as FilePath
from fastapi import BackgroundTasks, Path as ApiPath, FastAPI, Form, UploadFile, File, Request
import re
import subprocess
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import sqlite3, csv, io, datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

app = FastAPI()
DB = "crm.db"

SMTP_HOST = "smtp.qiye.aliyun.com"
SMTP_PORT = 465
SMTP_USER = "info@sograce.cn"
SMTP_PASSWORD = "mtpfRVuYzZrz8Vnr"
SMTP_FROM = "info@sograce.cn"

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "sales": {"password": "sales123", "role": "sales"}
}

def get_user_role(username):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row[0] if row else None

def is_login(request: Request):
    username = request.cookies.get("crm_user")
    return get_user_role(username) is not None


def db():
    return sqlite3.connect(DB)

def init_db():
    conn = db()
    c = conn.cursor()
    for col, default in [
        ("note","''"),("country","''"),("contact","''"),("whatsapp","''"),("source","''"),
        ("level","'C'"),("owner","''"),("next_followup","''"),("history","''")
    ]:
        try:
            c.execute(f"ALTER TABLE leads ADD COLUMN {col} TEXT DEFAULT {default}")
        except:
            pass
    conn.commit()
    conn.close()

init_db()

def stats():
    conn = db()
    c = conn.cursor()
    data = {}
    for st in ["NEW","CONTACTED","QUOTED","SAMPLE","NEGOTIATION","ORDERED","LOST"]:
        data[st] = c.execute("SELECT COUNT(*) FROM leads WHERE status=?", (st,)).fetchone()[0]
    data["TOTAL"] = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    return data

def followup_alerts():
    today = datetime.date.today().isoformat()
    conn = db()
    c = conn.cursor()
    today_items = c.execute("SELECT id,company,owner,next_followup FROM leads WHERE next_followup=?", (today,)).fetchall()
    overdue_items = c.execute("SELECT id,company,owner,next_followup FROM leads WHERE next_followup!='' AND next_followup<?", (today,)).fetchall()
    conn.close()
    return today_items, overdue_items


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
<html><head><title>SOGRACE CRM Login</title>
<style>
body{font-family:Arial;background:#07111f;color:white;display:flex;align-items:center;justify-content:center;height:100vh}
.box{background:#111d33;padding:40px;border-radius:12px;width:360px}
input{width:100%;padding:12px;margin:10px 0;border-radius:6px;border:0}
button{width:100%;padding:12px;background:#1683ff;color:white;border:0;border-radius:6px;font-size:16px}
</style></head><body>
<div class="box">
<h2>SOGRACE CRM Login</h2>
<form action="/login" method="post">
<input name="username" placeholder="Username">
<input name="password" type="password" placeholder="Password">
<button>Login</button>
</form>
<p></p>
<p></p>
</div>
</body></html>
"""

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = db()
    user = conn.execute(
        "SELECT username,password,role FROM users WHERE username=? AND password=?",
        (username,password)
    ).fetchone()
    conn.close()

    if user:
        res = RedirectResponse("/",303)
        res.set_cookie("crm_user", username, max_age=86400)
        return res


@app.get("/logout")
def logout():
    res = RedirectResponse("/login",303)
    res.delete_cookie("crm_user")
    return res

@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = ""):
    if not is_login(request):
        return RedirectResponse("/login",303)
    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    conn = db()
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        leads = c.execute("""
        SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact,expected_amount
        FROM leads
        WHERE (company LIKE ? OR email LIKE ? OR website LIKE ? OR country LIKE ? OR contact LIKE ? OR whatsapp LIKE ? OR source LIKE ?)
        AND (?='admin' OR owner=?)
        ORDER BY id DESC
        """,(like,like,like,like,like,like,like,role,username)).fetchall()
    else:
        leads = c.execute("""
        SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact,expected_amount
        FROM leads
        WHERE (?='admin' OR owner=?)
        ORDER BY id DESC
        """,(role,username)).fetchall()
    conn.close()

    stats_data = stats()
    today_items, overdue_items = followup_alerts()

    def money(v):
        try:
            return float(str(v or "0").replace("$","").replace(",",""))
        except:
            return 0

    pipeline_value = sum(money(x[17]) for x in leads)
    total_count = stats_data["TOTAL"] or 1
    quote_rate = round(stats_data["QUOTED"] * 100 / total_count, 1)
    order_rate = round(stats_data["ORDERED"] * 100 / total_count, 1)

    conn_rank = db()
    if role == "admin":
        sales_rows = conn_rank.execute("SELECT COALESCE(NULLIF(owner,''),'Unassigned') AS o, COUNT(*) FROM leads GROUP BY o ORDER BY COUNT(*) DESC").fetchall()
        money_rows = conn_rank.execute("SELECT COALESCE(NULLIF(owner,''),'Unassigned') AS o, SUM(CAST(expected_amount AS REAL)) FROM leads GROUP BY o ORDER BY SUM(CAST(expected_amount AS REAL)) DESC").fetchall()
    else:
        sales_rows = conn_rank.execute("SELECT owner, COUNT(*) FROM leads WHERE owner=? GROUP BY owner", (username,)).fetchall()
        money_rows = conn_rank.execute("SELECT owner, SUM(CAST(expected_amount AS REAL)) FROM leads WHERE owner=? GROUP BY owner", (username,)).fetchall()
    conn_rank.close()

    sales_ranking_html = "".join([f"<p>{r[0]}: {r[1]} Leads</p>" for r in sales_rows]) or "<p>No data</p>"
    money_ranking_html = "".join([f"<p>{r[0]}: ${float(r[1] or 0):,.0f}</p>" for r in money_rows]) or "<p>No data</p>"


    rows = ""
    today = datetime.date.today().isoformat()
    for l in leads:
        level_color = {"A":"#5c1f1f","B":"#5c3b1f","C":"#142848","D":"#333333"}.get(l[11] or "C", "#142848")
        if l[13] and l[13] < today:
            highlight = "style='background:#6b1f1f'"
        elif l[13] and l[13] == today:
            highlight = "style='background:#6b4a1f'"
        else:
            highlight = f"style='background:{level_color}'"
        rows += f"""
        <tr {highlight}>
            <td><a href="/lead/{l[0]}">{l[1]}</a></td>
            <td>{l[2]}</td>
            <td><a href="mailto:{l[3]}">{l[3]}</a></td>
            <td>{l[5]}</td>
            <td><a target="_blank" href="https://wa.me/{str(l[6]).replace('+','').replace(' ','').replace('-','')}">{l[6]}</a></td><td>{l[7]}</td><td>{l[8]}</td><td>{l[14]}</td><td>{l[15]}</td><td>{l[16]}</td><td>${l[17] or '0'}</td>
            <td>
                <form action="/quick/{l[0]}" method="post">
                    <select name="level">
                        <option>{l[11]}</option><option>A</option><option>B</option><option>C</option><option>D</option>
                    </select>
                    <input name="owner" value="{l[12] or ''}" placeholder="Owner">
                    <input name="next_followup" value="{l[13] or ''}" placeholder="Next Follow Up">
                    <select name="status">
                        <option>{l[9]}</option><option>NEW</option><option>CONTACTED</option><option>QUOTED</option><option>SAMPLE</option><option>NEGOTIATION</option><option>ORDERED</option><option>LOST</option>
                    </select>
                    <select name="product_interest">
                        <option>{l[14] or ''}</option><option>GPS Watch</option><option>GPS SOS Watch</option><option>GPS Tracker</option><option>Vehicle Tracker</option><option>Pet Tracker</option><option>OEM Project</option>
                    </select>
                    <select name="customer_value">
                        <option>{l[15] or '★'}</option><option>★</option><option>★★</option><option>★★★</option><option>★★★★</option><option>★★★★★</option>
                    </select>
                    <input name="expected_amount" value="{l[17] or '0'}" placeholder="Expected Amount">
                    <input name="note" value="{l[10] or ''}" placeholder="Note">
                    <button>Save</button>
                </form>
            </td>
            <td><a class="delete" href="/delete/{l[0]}">Delete</a></td>
        </tr>
        """

    return f"""
<html><head><title>SOGRACE CRM V4.1 Web Control Center</title>
<style>
body{{font-family:Arial;background:#07111f;color:white;margin:0}}
.header{{background:#0b1f3a;padding:20px;font-size:28px;font-weight:bold}}
.container{{padding:30px}}.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select,textarea{{padding:10px;margin:6px;border-radius:6px;border:0}}
button{{padding:10px 16px;background:#1683ff;color:white;border:0;border-radius:6px}}
.timeline-item{{background:#0b1f3a;margin:8px 0;padding:12px;border-left:4px solid #1683ff;border-radius:6px}}
a{{color:white}}.delete{{background:#d93333;padding:8px 12px;border-radius:6px;text-decoration:none}}
.export{{background:#0bbf7a;padding:10px 18px;border-radius:6px;text-decoration:none;margin:8px;display:inline-block}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}}
.stat{{background:#142848;padding:20px;border-radius:12px;font-size:24px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px;border-bottom:1px solid #333;text-align:left}}
</style></head><body>
<div class="header">SOGRACE CRM V4.1 Web Control Center <a style="float:right;font-size:16px" href="/logout">Logout</a></div>
<div class="container">

<div class="grid">
<div class="stat">TOTAL<br>{stats_data["TOTAL"]}</div>
<div class="stat">NEW<br>{stats_data["NEW"]}</div>
<div class="stat">CONTACTED<br>{stats_data["CONTACTED"]}</div>
<div class="stat">QUOTED<br>{stats_data["QUOTED"]}</div>
<div class="stat">SAMPLE<br>{stats_data["SAMPLE"]}</div>
<div class="stat">NEGOTIATION<br>{stats_data["NEGOTIATION"]}</div>
<div class="stat">ORDERED<br>{stats_data["ORDERED"]}</div>
<div class="stat">LOST<br>{stats_data["LOST"]}</div>
<div class="stat">PIPELINE VALUE<br>${pipeline_value:,.0f}</div>
<div class="stat">QUOTE RATE<br>{quote_rate}%</div>
<div class="stat">ORDER RATE<br>{order_rate}%</div>

<div class="card">
<h2>📊 Lead Count Ranking</h2>
{sales_ranking_html}
</div>

<div class="card">
<h2>🏆 Sales Amount Ranking</h2>
{money_ranking_html}
</div>
</div>

<div class="card"><h2>Follow Up Reminder</h2>
<h3>Today Follow Up</h3>
{''.join([f'<p><a href="/lead/{x[0]}">{x[1]}</a> | Owner: {x[2]} | Date: {x[3]}</p>' for x in today_items]) or '<p>No follow up today.</p>'}
<h3 style="color:#ff5555">Overdue Follow Up</h3>
{''.join([f'<p style="color:#ff9999"><a href="/lead/{x[0]}">{x[1]}</a> | Owner: {x[2]} | Date: {x[3]}</p>' for x in overdue_items]) or '<p>No overdue follow up.</p>'}
</div>

<div class="card"><h2>Sales Ranking</h2>
<h3>Lead Count</h3>
{sales_ranking_html}
<h3>Pipeline Value</h3>
{money_ranking_html}
</div>

<div class="card"><h2>Add Lead</h2>
<form action="/add" method="post">
<input name="company" placeholder="Company"><input name="contact" placeholder="Contact">
<input name="email" placeholder="Email"><input name="website" placeholder="Website">
<input name="country" placeholder="Country"><input name="whatsapp" placeholder="WhatsApp">
<input name="source" placeholder="Source">
<select name="category"><option>ELDERLY</option><option>PET</option><option>PLATFORM</option><option>DISTRIBUTOR</option></select>
<button>Add Lead</button></form></div>

<div class="card"><h2>Search / Import / Export / Automation</h2>
<form action="/" method="get" style="display:inline-block">
<input name="q" placeholder="Search" value="{q}">
<button>Search</button>
</form>
<a class="export" href="/">Reset</a>
<a class="export" href="/export">Export CSV</a>


<a class="export" href="/bulk_send/50">Send 50</a>
<a class="export" href="/bulk_send/100">Send 100</a>
<a class="export" href="/auto_collect">Auto Collect Leads</a>
<a class="export" href="/lead_collect_log">Collector Log</a>
<a class="export" href="/download_auto_leads">Download Leads</a>
<a class="export" href="/email_center">Email Center</a>
<a class="export" href="/auto_send/50">Auto Send 50</a>
<a class="export" href="/auto_send/100">Auto Send 100</a>
<form action="/import" method="post" enctype="multipart/form-data" style="margin-top:20px">
<input type="file" name="file" accept=".csv"><button>Import CSV</button>
</form>
</div>

<div class="card"><h2>Lead List</h2>
<table><tr><th>Company</th><th>Contact</th><th>Email</th><th>Country</th><th>WhatsApp</th><th>Category</th><th>Source</th><th>Product</th><th>Value</th><th>Last Contact</th><th>Expected Amount</th><th>Quick Update</th><th>Action</th></tr>
{rows}</table></div>
</div></body></html>
"""


@app.post("/quick/{lead_id}")
def quick_update(request: Request, lead_id:int, level:str=Form("C"), owner:str=Form(""), next_followup:str=Form(""), status:str=Form("NEW"), note:str=Form(""), product_interest:str=Form(""), customer_value:str=Form("★"), expected_amount:str=Form("0")):
    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    if role != "admin":
        owner = username
    conn=db()
    old = conn.execute("SELECT status, history FROM leads WHERE id=?", (lead_id,)).fetchone()
    old_status = old[0] if old else ""
    old_history = old[1] if old and old[1] else ""
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if old_status != status:
        old_history += f"\n{today} Status: {old_status} -> {status}"
    if note:
        old_history += f"\n{today} Note: {note}"
    last_contact = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("UPDATE leads SET level=?, owner=?, next_followup=?, status=?, note=?, history=?, product_interest=?, customer_value=?, last_contact=?, expected_amount=? WHERE id=?", (level,owner,next_followup,status,note,old_history,product_interest,customer_value,last_contact,expected_amount,lead_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/",303)

@app.get("/lead/{lead_id}", response_class=HTMLResponse)
def lead_detail(lead_id:int):
    conn = db()
    l = conn.execute("SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact,expected_amount,history FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    if not l:
        return "Lead not found"

    history_text = l[18] or ""
    timeline_items = ""
    for line in history_text.split("\n"):
        if line.strip():
            timeline_items += f"<div class='timeline-item'>📅 {line}</div>"
    if not timeline_items:
        timeline_items = "<p>No history yet.</p>"

    return f"""
<html><head><title>{l[1]}</title><style>
body{{font-family:Arial;background:#07111f;color:white;padding:30px}}
.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select,textarea{{padding:10px;margin:6px;border-radius:6px;border:0;width:300px}}
button{{padding:10px 16px;background:#1683ff;color:white;border:0;border-radius:6px}}
.timeline-item{{background:#0b1f3a;margin:8px 0;padding:12px;border-left:4px solid #1683ff;border-radius:6px}}
a{{color:white}}
</style></head><body>
<h1>{l[1]}</h1><a href="/">Back</a>
<div class="card">
<p>Contact: {l[2]}</p><p>Email: {l[3]}</p><p>Website: {l[4]}</p><p>Country: {l[5]}</p><p>WhatsApp: {l[6]}</p>
</div>
<div class="card"><h2>Update Follow Up</h2>
<form action="/followup/{l[0]}" method="post">
<select name="level"><option>{l[11]}</option><option>A</option><option>B</option><option>C</option><option>D</option></select>
<input name="owner" value="{l[12] or ''}" placeholder="Owner">
<input name="next_followup" value="{l[13] or ''}" placeholder="2026-06-15">
<textarea name="history" rows="4" placeholder="New follow up record"></textarea><br>
<button>Save Follow Up</button>
</form></div>

<div class="card"><h2>📧 Email Center</h2>
<form action="/send_email/{l[0]}" method="post">
<input name="subject" placeholder="Subject" value="GPS SOS Watch Introduction"><br>
<textarea name="message" rows="8" placeholder="Email message">Hello,

We are SOGRACE, a professional GPS SOS watch and GPS tracking solution supplier.

We provide GPS SOS watches, GPS tracker devices, and Globe GPS Tracker platform solutions.

Best regards,
SOGRACE</textarea><br>
<button>Send Email</button>
</form>
</div>

<div class="card"><h2>Timeline</h2>{timeline_items}</div>
</body></html>
"""

@app.post("/add")
def add_lead(company:str=Form(...),contact:str=Form(""),email:str=Form(...),website:str=Form(""),country:str=Form(""),whatsapp:str=Form(""),source:str=Form(""),category:str=Form(...)):
    conn=db()
    conn.execute("INSERT INTO leads (company,email,website,category,status,note,country,contact,whatsapp,source,level,owner,next_followup,history) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    (company,email,website,category,"NEW","",country,contact,whatsapp,source,"C","","",""))
    conn.commit(); conn.close()
    return RedirectResponse("/",303)

@app.post("/followup/{lead_id}")
def followup(lead_id:int, level:str=Form("C"), owner:str=Form(""), next_followup:str=Form(""), history:str=Form("")):
    conn=db()
    old = conn.execute("SELECT history FROM leads WHERE id=?", (lead_id,)).fetchone()
    old_history = old[0] if old and old[0] else ""
    if history:
        today = datetime.date.today().isoformat()
        old_history = old_history + f"\\n{today} {history}"
    conn.execute("UPDATE leads SET level=?, owner=?, next_followup=?, history=? WHERE id=?", (level,owner,next_followup,old_history,lead_id))
    conn.commit(); conn.close()
    return RedirectResponse(f"/lead/{lead_id}",303)

@app.post("/status/{lead_id}")
def update_status(lead_id:int,status:str=Form(...)):
    conn=db(); conn.execute("UPDATE leads SET status=? WHERE id=?", (status,lead_id)); conn.commit(); conn.close()
    return RedirectResponse("/",303)

@app.post("/note/{lead_id}")
def update_note(lead_id:int,note:str=Form("")):
    conn=db(); conn.execute("UPDATE leads SET note=? WHERE id=?", (note,lead_id)); conn.commit(); conn.close()
    return RedirectResponse("/",303)

@app.get("/delete/{lead_id}")
def delete_lead(lead_id:int):
    conn=db(); conn.execute("DELETE FROM leads WHERE id=?", (lead_id,)); conn.commit(); conn.close()
    return RedirectResponse("/",303)

@app.get("/export")
def export_csv():
    conn=db()
    rows=conn.execute("SELECT company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,history FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["Company","Contact","Email","Website","Country","WhatsApp","Category","Source","Status","Note","Level","Owner","NextFollowup","History"])
    writer.writerows(rows); output.seek(0)
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=sograce_crm_v24_leads.csv"})

@app.post("/import")
async def import_csv(file: UploadFile = File(...)):
    content=await file.read()
    reader=csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    conn=db()
    for r in reader:
        conn.execute("INSERT INTO leads (company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,history) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r.get("Company",""),r.get("Contact",""),r.get("Email",""),r.get("Website",""),r.get("Country",""),r.get("WhatsApp",""),r.get("Category","ELDERLY"),r.get("Source",""),r.get("Status","NEW"),r.get("Note",""),r.get("Level","C"),r.get("Owner",""),r.get("NextFollowup",""),r.get("History","")))
    conn.commit(); conn.close()
    return RedirectResponse("/",303)

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if not is_login(request):
        return RedirectResponse('/',303)

    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"

    if role != "admin":
        return HTMLResponse("<h2>Access Denied</h2>")

    conn = db()
    rows = conn.execute(
        "SELECT id,username,password,role FROM users ORDER BY id"
    ).fetchall()
    conn.close()

    html_rows = ""
    for r in rows:
        html_rows += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[3]}</td>
            <td><a href="/delete_user/{r[0]}">Delete</a></td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family:Arial">
    <h1>User Management</h1>

    <form action="/add_user" method="post">
        <input name="username" placeholder="Username">
        <input name="password" placeholder="Password">
        <select name="role">
            <option>sales</option>
            <option>admin</option>
        </select>
        <button>Add User</button>
    </form>

    <br>

    <table border="1" cellpadding="8">
        <tr>
            <th>ID</th>
            <th>Username</th>
            <th>Role</th>
            <th>Action</th>
        </tr>
        {html_rows}
    </table>

    <br>
    <a href="/">Back CRM</a>
    </body>
    </html>
    """

@app.post("/add_user")
def add_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    conn = db()
    conn.execute(
        "INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)",
        (username,password,role)
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/users",303)

@app.get("/delete_user/{user_id}")
def delete_user(user_id:int):
    conn = db()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/users",303)


@app.get("/assign", response_class=HTMLResponse)
def assign_page(request: Request):
    if not is_login(request):
        return RedirectResponse('/',303)

    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    if role != "admin":
        return HTMLResponse("<h2>Access Denied</h2>")

    conn = db()
    leads = conn.execute("SELECT id,company,owner FROM leads ORDER BY id DESC").fetchall()
    users = conn.execute("SELECT username FROM users ORDER BY username").fetchall()
    conn.close()

    lead_options = "".join([f'<option value="{l[0]}">{l[1]} | Owner: {l[2]}</option>' for l in leads])
    user_options = "".join([f'<option value="{u[0]}">{u[0]}</option>' for u in users])

    return f"""
    <html>
    <body style="font-family:Arial">
    <h1>Assign Customer</h1>
    <form action="/assign" method="post">
        <select name="lead_id">{lead_options}</select>
        <select name="owner">{user_options}</select>
        <button>Assign</button>
    </form>
    <br>
    <a href="/users">Back Users</a><br>
    <a href="/">Back CRM</a>
    </body>
    </html>
    """

@app.post("/assign")
def assign_customer(request: Request, lead_id:int=Form(...), owner:str=Form(...)):
    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    if role != "admin":
        return HTMLResponse("<h2>Access Denied</h2>")

    conn = db()
    conn.execute("UPDATE leads SET owner=? WHERE id=?", (owner,lead_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/assign",303)


@app.post("/send_email/{lead_id}")
def send_email_record(lead_id:int, subject:str=Form(...), message:str=Form("")):
    conn = db()
    lead = conn.execute("SELECT email,history FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return RedirectResponse("/",303)

    email = lead[0] or ""
    history = lead[1] or ""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        msg = MIMEText(message,"plain","utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = email

        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [email], msg.as_string())
        server.quit()

        history += f"\n{now} Email Sent | To: {email} | Subject: {subject}"

    except Exception as e:
        history += f"\n{now} Email Failed | {str(e)}"

    conn.execute("UPDATE leads SET history=? WHERE id=?", (history,lead_id))
    conn.commit()
    conn.close()

    return RedirectResponse(f"/lead/{lead_id}",303)

# BULK EMAIL TEST 5 START
@app.get("/bulk_test_5")
def bulk_test_5(request: Request):
    if not is_login(request):
        return RedirectResponse('/',303)

    subject = "GPS Tracking Devices for Your Market"
    message = """Dear Team,

I'm Chen from Sograce, a GPS tracking device manufacturer.

We provide elderly GPS watches, SOS GPS trackers, pet trackers, vehicle trackers, asset trackers, and GPS platform / APP solutions.

Would you be interested in receiving our latest catalog and OEM/ODM options?

Best regards,
Chen
Sograce
www.sograce.cn
"""

    conn = db()
    rows = conn.execute("""
        SELECT id,company,email,history
        FROM leads
        WHERE email!=''
          AND email!='Not found'
          AND email LIKE '%@%'
          AND (history IS NULL OR history NOT LIKE '%Bulk Email Sent%')
        ORDER BY id ASC
        LIMIT 20
    """).fetchall()

    sent = 0
    failed = 0
    skipped = 0
    batch_emails = set()
    report = ""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for lead_id, company, email, history in rows:
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email or "")
        emails = [e.strip().lower() for e in emails]

        if not emails:
            skipped += 1
            history = (history or "") + f"\\n{now} Invalid Email Skipped | Raw: {email}"
            conn.execute("UPDATE leads SET history=? WHERE id=?", (history, lead_id))
            report += f"<p style='color:#999'>SKIPPED invalid: {company} - {email}</p>"
            continue

        real_email = emails[0]

        if real_email in batch_emails:
            skipped += 1
            report += f"<p style='color:#999'>SKIPPED duplicate in batch: {company} - {real_email}</p>"
            continue

        already_sent = conn.execute("SELECT id FROM leads WHERE history LIKE ?", (f"%To: {real_email}%",)).fetchone()
        if already_sent:
            skipped += 1
            report += f"<p style='color:#999'>SKIPPED already sent: {company} - {real_email}</p>"
            continue

        batch_emails.add(real_email)

        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = real_email

            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [real_email], msg.as_string())
            server.quit()

            history = (history or "") + f"\\n{now} Bulk Email Sent | To: {real_email} | Subject: {subject}"
            conn.execute("UPDATE leads SET history=?, status='CONTACTED', last_contact=? WHERE id=?", (history, now, lead_id))
            sent += 1
            report += f"<p>OK: {company} - {real_email}</p>"
        except Exception as e:
            history = (history or "") + f"\\n{now} Bulk Email Failed | To: {real_email} | {str(e)}"
            conn.execute("UPDATE leads SET history=? WHERE id=?", (history, lead_id))
            failed += 1
            report += f"<p style='color:red'>FAILED: {company} - {real_email} - {str(e)}</p>"

    conn.commit()
    conn.close()

    return HTMLResponse(f"<h2>Bulk Email Test 5 Finished</h2><p>Sent: {sent}</p><p>Failed: {failed}</p><p>Skipped: {skipped}</p>{report}<p><a href='/'>Back to CRM</a></p>")
# BULK EMAIL TEST 5 END
# V3.0 BULK EMAIL MULTI SEND START


# V3.0 BULK EMAIL MULTI SEND START

@app.get("/bulk_send/{count}")
def bulk_send(request: Request, background_tasks: BackgroundTasks, count: int = ApiPath(..., ge=1, le=100)):
    if not is_login(request):
        return RedirectResponse("/login", status_code=303)
    background_tasks.add_task(_bulk_send_worker, count)
    return HTMLResponse(f"<h2>Bulk Email Task Started</h2><p>Sending {count} emails in background.</p><p><a href='/'>Back to CRM</a></p>")

def _bulk_send_worker(count: int):
    # background worker no request/login check here

    subject = "GPS Tracking Devices for Your Market"
    message = """Dear Team,

    I'm Chen from Sograce, a GPS tracking device manufacturer.

    We provide elderly GPS watches, SOS GPS trackers, pet trackers, vehicle trackers, asset trackers, and GPS platform / APP solutions.

    Would you be interested in receiving our latest catalog and OEM/ODM options?

    Best regards,
    Chen
    Sograce
    www.sograce.cn
    """
    # Background worker has no request object. Filters disabled for button-based bulk send.
    country_filter = None
    category_filter = None

    conn = db()
    sql = """
        SELECT id,company,email,history
        FROM leads
        WHERE email!='' AND email!='Not found' AND email LIKE '%@%'
          AND (history IS NULL OR history NOT LIKE '%Bulk Email Sent%')
    """
    params = []
    if country_filter:
        sql += " AND country=?"
        params.append(country_filter)
    if category_filter:
        sql += " AND category=?"
        params.append(category_filter)
    sql += " ORDER BY id ASC LIMIT ?"
    params.append(count)

    rows = conn.execute(sql, params).fetchall()

    sent = 0
    failed = 0
    skipped = 0
    batch_emails = set()
    report = ""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for lead_id, company, email, history in rows:
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email or "")
        emails = [e.strip().lower() for e in emails]
        if not emails:
            skipped += 1
            history = (history or "") + f"\n{now} Invalid Email Skipped | Raw: {email}"
            conn.execute("UPDATE leads SET history=? WHERE id=?", (history, lead_id))
            report += f"<p style='color:#999'>SKIPPED invalid: {company} - {email}</p>"
            continue

        real_email = emails[0]
        if real_email in batch_emails:
            skipped += 1
            report += f"<p style='color:#999'>SKIPPED duplicate in batch: {company} - {real_email}</p>"
            continue

        already_sent = conn.execute("SELECT id FROM leads WHERE history LIKE ?", (f'%To: {real_email}%',)).fetchone()
        if already_sent:
            skipped += 1
            report += f"<p style='color:#999'>SKIPPED already sent: {company} - {real_email}</p>"
            continue

        batch_emails.add(real_email)

        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = real_email

            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [real_email], msg.as_string())
            server.quit()

            history = (history or "") + f"\n{now} Bulk Email Sent | To: {real_email} | Subject: {subject}"
            conn.execute("UPDATE leads SET history=?, status='CONTACTED', last_contact=? WHERE id=?", (history, now, lead_id))
            sent += 1
            report += f"<p>OK: {company} - {real_email}</p>"
        except Exception as e:
            history = (history or "") + f"\n{now} Bulk Email Failed | To: {real_email} | {str(e)}"
            conn.execute("UPDATE leads SET history=? WHERE id=?", (history, lead_id))
            failed += 1
            report += f"<p style='color:red'>FAILED: {company} - {real_email} - {str(e)}</p>"

    conn.commit()
    conn.close()

    try:
        with open("/home/admin/crm/crm_bulk_send.log", "a", encoding="utf-8") as f:
            f.write(f"{now} Bulk Send Finished | count={count} | sent={sent} | failed={failed} | skipped={skipped}\n")
    except Exception:
        pass

    # V3.0 BULK EMAIL MULTI SEND END




# ===== AUTO LEAD COLLECTOR START =====
def _run_auto_collector():
    import subprocess
    subprocess.run(
        ["./venv/bin/python", "lead_collector.py"],
        cwd="/home/admin/crm",
        stdout=open("/home/admin/crm/lead_collector.log", "a"),
        stderr=open("/home/admin/crm/lead_collector.log", "a"),
        timeout=1800
    )

@app.get("/auto_collect", response_class=HTMLResponse)
def auto_collect(request: Request, background_tasks: BackgroundTasks):
    if not is_login(request):
        return RedirectResponse("/login", 303)

    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    if role != "admin":
        return HTMLResponse("<h2>Access Denied</h2>")

    background_tasks.add_task(_run_auto_collector)

    return HTMLResponse("""
    <h2>Auto Lead Collector Started</h2>
    <p>客户自动采集任务已经启动，后台正在搜索客户。</p>
    <p>完成后会写入 auto_leads.csv 和 CRM 数据库。</p>
    <p><a href="/">Back to CRM</a></p>
    <p><a href="/download_auto_leads">Download auto_leads.csv</a></p>
    """)



@app.get("/lead_collect_log", response_class=HTMLResponse)
def lead_collect_log(request: Request):
    if not is_login(request):
        return HTMLResponse("<h2>Please login first</h2><p><a href='/login'>Login</a></p>")

    try:
        log_path = FilePath("/home/admin/crm/lead_collector.log")
        if not log_path.exists():
            log_path.write_text("No log yet.", encoding="utf-8")

        text = log_path.read_text(encoding="utf-8", errors="ignore")[-12000:]
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return HTMLResponse(f"""
        <h2>Lead Collector Log</h2>
        <p><a href="/auto_collect">Start Auto Collect</a> | <a href="/">Back to CRM</a> | <a href="/download_auto_leads">Download CSV</a></p>
        <pre style="white-space:pre-wrap;background:#111;color:#0f0;padding:20px;border-radius:10px;">{text}</pre>
        """)
    except Exception as e:
        msg = str(e).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return HTMLResponse(f"<h2>Log Error</h2><pre>{msg}</pre><p><a href='/'>Back</a></p>")



@app.get("/download_auto_leads")
def download_auto_leads(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)

    file_path = FilePath("/home/admin/crm/auto_leads.csv")
    if not file_path.exists():
        return HTMLResponse("<h2>auto_leads.csv not found</h2>")

    return StreamingResponse(
        open(file_path, "rb"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auto_leads.csv"}
    )
# ===== AUTO LEAD COLLECTOR END =====



# ===== CRM V4.1 WEB PATCH REAL START =====
@app.get("/email_center", response_class=HTMLResponse)
def email_center(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)

    from pathlib import Path as _Path
    import csv as _csv
    import html as _html

    queue_files = [
        _Path("/home/admin/crm/email_queue_v34.csv"),
        _Path("/home/admin/crm/email_queue.csv"),
    ]
    queue_file = None
    for p in queue_files:
        if p.exists():
            queue_file = p
            break

    rows_html = ""
    total = ready = sent = failed = skipped = 0

    if queue_file:
        try:
            with queue_file.open("r", encoding="utf-8-sig", errors="ignore") as f:
                reader = _csv.DictReader(f)
                for r in list(reader)[:300]:
                    total += 1
                    status = (r.get("status") or "").upper()
                    if status == "READY":
                        ready += 1
                    elif status == "SENT":
                        sent += 1
                    elif status == "FAILED":
                        failed += 1
                    elif status == "SKIPPED":
                        skipped += 1

                    rows_html += f"""
                    <tr>
                        <td>{_html.escape(r.get('lead_id',''))}</td>
                        <td>{_html.escape(r.get('company',''))}</td>
                        <td>{_html.escape(r.get('email',''))}</td>
                        <td>{_html.escape(r.get('website',''))}</td>
                        <td>{_html.escape(r.get('country',''))}</td>
                        <td>{_html.escape(r.get('score',''))}</td>
                        <td>{_html.escape(status)}</td>
                    </tr>
                    """
        except Exception as e:
            rows_html = f"<tr><td colspan='7'>Queue read error: {_html.escape(str(e))}</td></tr>"
    else:
        rows_html = "<tr><td colspan='7'>No email_queue_v34.csv or email_queue.csv found.</td></tr>"

    log_text = ""
    for log_name in ["auto_send_v40.log", "crm_bulk_send.log"]:
        p = _Path("/home/admin/crm") / log_name
        if p.exists():
            log_text += f"===== {log_name} =====\\n"
            log_text += p.read_text(encoding="utf-8", errors="ignore")[-5000:] + "\\n"

    log_text = _html.escape(log_text or "No send log yet.")

    return HTMLResponse(f"""
    <html>
    <head>
    <title>SOGRACE CRM V4.1 Email Center</title>
    <style>
    body{{font-family:Arial;background:#07111f;color:white;margin:0;padding:30px}}
    .card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
    .grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:15px}}
    .stat{{background:#142848;padding:20px;border-radius:12px;font-size:22px}}
    a{{color:white}}
    .btn{{background:#0bbf7a;padding:10px 18px;border-radius:6px;text-decoration:none;margin:8px;display:inline-block}}
    table{{width:100%;border-collapse:collapse;font-size:14px}}
    th,td{{padding:10px;border-bottom:1px solid #333;text-align:left}}
    pre{{white-space:pre-wrap;background:#050b14;color:#0f0;padding:15px;border-radius:8px}}
    </style>
    </head>
    <body>
    <h1>📧 SOGRACE CRM V4.1 Email Center</h1>
    <p>
      <a class="btn" href="/">Back CRM</a>
      <a class="btn" href="/auto_collect">Auto Collect</a>
      <a class="btn" href="/lead_collect_log">Collector Log</a>
      <a class="btn" href="/auto_send/5">Send 5</a>
      <a class="btn" href="/auto_send/20">Send 20</a>
      <a class="btn" href="/bulk_send/10">Bulk Send 10</a>
    </p>

    <div class="grid">
      <div class="stat">TOTAL<br>{total}</div>
      <div class="stat">READY<br>{ready}</div>
      <div class="stat">SENT<br>{sent}</div>
      <div class="stat">FAILED<br>{failed}</div>
      <div class="stat">SKIPPED<br>{skipped}</div>
    </div>

    <div class="card">
    <h2>Email Queue</h2>
    <p>Source file: {queue_file if queue_file else "None"}</p>
    <table>
    <tr><th>ID</th><th>Company</th><th>Email</th><th>Website</th><th>Country</th><th>Score</th><th>Status</th></tr>
    {rows_html}
    </table>
    </div>

    <div class="card">
    <h2>Recent Send Log</h2>
    <pre>{log_text}</pre>
    </div>
    </body>
    </html>
    """)


def _auto_send_worker(count: int):
    import subprocess
    try:
        subprocess.run(
            ["./venv/bin/python", "auto_send_v40.py", "send", str(count)],
            cwd="/home/admin/crm",
            stdout=open("/home/admin/crm/auto_send_v40.log", "a"),
            stderr=open("/home/admin/crm/auto_send_v40.log", "a"),
            timeout=1800
        )
    except Exception as e:
        with open("/home/admin/crm/auto_send_v40.log", "a", encoding="utf-8") as f:
            f.write("AUTO_SEND_WORKER_ERROR: " + str(e) + "\\n")


@app.get("/auto_send/{count}", response_class=HTMLResponse)
def auto_send_web(request: Request, background_tasks: BackgroundTasks, count: int = ApiPath(..., ge=1, le=100)):
    if not is_login(request):
        return RedirectResponse("/login", 303)

    username = request.cookies.get("crm_user")
    role = get_user_role(username) or "sales"
    if role != "admin":
        return HTMLResponse("<h2>Access Denied</h2><p><a href='/'>Back</a></p>")

    background_tasks.add_task(_auto_send_worker, count)

    return HTMLResponse(f"""
    <h2>Auto Send Started</h2>
    <p>Sending up to {count} emails in background.</p>
    <p><a href="/email_center">Email Center</a></p>
    <p><a href="/">Back to CRM</a></p>
    """)
# ===== CRM V4.1 WEB PATCH REAL END =====

def _auto_pipeline_worker(count: int):
    from main import background_tasks, send_email_batch
    # Auto Collect Leads
    from collect_leads import collect_ready_leads
    collect_ready_leads()
    # Build Queue done inside collect_ready_leads
    send_email_batch(count)
    # 记录日志写入 pipeline.log
    with open("/home/admin/crm/pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"Auto Pipeline {{count}} executed\n")

@app.get("/auto_pipeline/{count}")
def auto_pipeline_web(request, count: int):
    background_tasks.add_task(_auto_pipeline_worker, count)
    return HTMLResponse(f"Pipeline {count} started")
