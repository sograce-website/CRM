from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import sqlite3, csv, io, datetime

app = FastAPI()
DB = "crm.db"

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "sales": {"password": "sales123", "role": "sales"}
}

def is_login(request: Request):
    return request.cookies.get("crm_user") in USERS


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
<p>Admin: admin / admin123</p>
<p>Sales: sales / sales123</p>
</div>
</body></html>
"""

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user = USERS.get(username)
    if user and user["password"] == password:
        res = RedirectResponse("/",303)
        res.set_cookie("crm_user", username, max_age=86400)
        return res
    return RedirectResponse("/login",303)

@app.get("/logout")
def logout():
    res = RedirectResponse("/login",303)
    res.delete_cookie("crm_user")
    return res

@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = ""):
    if not is_login(request):
        return RedirectResponse("/login",303)
    conn = db()
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        leads = c.execute("""
        SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact
        FROM leads
        WHERE company LIKE ? OR email LIKE ? OR website LIKE ? OR country LIKE ? OR contact LIKE ? OR whatsapp LIKE ? OR source LIKE ?
        ORDER BY id DESC
        """,(like,like,like,like,like,like,like)).fetchall()
    else:
        leads = c.execute("""
        SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact
        FROM leads ORDER BY id DESC
        """).fetchall()
    conn.close()

    stats_data = stats()
    today_items, overdue_items = followup_alerts()

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
            <td><a href="/lead/{l[0]}">{l[1]}</a></td><td>{l[2]}</td><td>{l[3]}</td><td>{l[5]}</td>
            <td>{l[6]}</td><td>{l[7]}</td><td>{l[8]}</td><td>{l[14]}</td><td>{l[15]}</td><td>{l[16]}</td>
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
                    <input name="note" value="{l[10] or ''}" placeholder="Note">
                    <button>Save</button>
                </form>
            </td>
            <td><a class="delete" href="/delete/{l[0]}">Delete</a></td>
        </tr>
        """

    return f"""
<html><head><title>SOGRACE CRM V2.6 Professional P1</title>
<style>
body{{font-family:Arial;background:#07111f;color:white;margin:0}}
.header{{background:#0b1f3a;padding:20px;font-size:28px;font-weight:bold}}
.container{{padding:30px}}.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select,textarea{{padding:10px;margin:6px;border-radius:6px;border:0}}
button{{padding:10px 16px;background:#1683ff;color:white;border:0;border-radius:6px}}
a{{color:white}}.delete{{background:#d93333;padding:8px 12px;border-radius:6px;text-decoration:none}}
.export{{background:#0bbf7a;padding:10px 18px;border-radius:6px;text-decoration:none;margin:8px;display:inline-block}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}}
.stat{{background:#142848;padding:20px;border-radius:12px;font-size:24px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px;border-bottom:1px solid #333;text-align:left}}
</style></head><body>
<div class="header">SOGRACE CRM V2.6 Professional P1 <a style="float:right;font-size:16px" href="/logout">Logout</a></div>
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
</div>

<div class="card"><h2>Follow Up Reminder</h2>
<h3>Today Follow Up</h3>
{''.join([f'<p><a href="/lead/{x[0]}">{x[1]}</a> | Owner: {x[2]} | Date: {x[3]}</p>' for x in today_items]) or '<p>No follow up today.</p>'}
<h3 style="color:#ff5555">Overdue Follow Up</h3>
{''.join([f'<p style="color:#ff9999"><a href="/lead/{x[0]}">{x[1]}</a> | Owner: {x[2]} | Date: {x[3]}</p>' for x in overdue_items]) or '<p>No overdue follow up.</p>'}
</div>

<div class="card"><h2>Add Lead</h2>
<form action="/add" method="post">
<input name="company" placeholder="Company"><input name="contact" placeholder="Contact">
<input name="email" placeholder="Email"><input name="website" placeholder="Website">
<input name="country" placeholder="Country"><input name="whatsapp" placeholder="WhatsApp">
<input name="source" placeholder="Source">
<select name="category"><option>ELDERLY</option><option>PET</option><option>PLATFORM</option><option>DISTRIBUTOR</option></select>
<button>Add Lead</button></form></div>

<div class="card"><h2>Search / Import / Export</h2>
<form action="/" method="get"><input name="q" placeholder="Search" value="{q}">
<button>Search</button><a class="export" href="/">Reset</a><a class="export" href="/export">Export CSV</a></form>
<form action="/import" method="post" enctype="multipart/form-data"><input type="file" name="file" accept=".csv"><button>Import CSV</button></form>
</div>

<div class="card"><h2>Lead List</h2>
<table><tr><th>Company</th><th>Contact</th><th>Email</th><th>Country</th><th>WhatsApp</th><th>Category</th><th>Source</th><th>Product</th><th>Value</th><th>Last Contact</th><th>Quick Update</th><th>Action</th></tr>
{rows}</table></div>
</div></body></html>
"""


@app.post("/quick/{lead_id}")
def quick_update(lead_id:int, level:str=Form("C"), owner:str=Form(""), next_followup:str=Form(""), status:str=Form("NEW"), note:str=Form(""), product_interest:str=Form(""), customer_value:str=Form("★")):
    conn=db()
    old = conn.execute("SELECT status, history FROM leads WHERE id=?", (lead_id,)).fetchone()
    old_status = old[0] if old else ""
    old_history = old[1] if old and old[1] else ""
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if old_status != status:
        old_history += f"\\n{today} Status: {old_status} -> {status}"
    if note:
        old_history += f"\\n{today} Note: {note}"
    last_contact = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("UPDATE leads SET level=?, owner=?, next_followup=?, status=?, note=?, history=?, product_interest=?, customer_value=?, last_contact=? WHERE id=?", (level,owner,next_followup,status,note,old_history,product_interest,customer_value,last_contact,lead_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/",303)

@app.get("/lead/{lead_id}", response_class=HTMLResponse)
def lead_detail(lead_id:int):
    conn = db()
    l = conn.execute("SELECT id,company,contact,email,website,country,whatsapp,category,source,status,note,level,owner,next_followup,product_interest,customer_value,last_contact,history FROM leads WHERE id=?", (lead_id,)).fetchone()
    conn.close()
    if not l:
        return "Lead not found"
    return f"""
<html><head><title>{l[1]}</title><style>
body{{font-family:Arial;background:#07111f;color:white;padding:30px}}
.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select,textarea{{padding:10px;margin:6px;border-radius:6px;border:0;width:300px}}
button{{padding:10px 16px;background:#1683ff;color:white;border:0;border-radius:6px}}
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
<div class="card"><h2>History</h2><pre>{l[14] or ''}</pre></div>
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
