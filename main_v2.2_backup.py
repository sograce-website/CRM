from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import sqlite3
import csv
import io

app = FastAPI()
DB = "crm.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS leads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT,
        email TEXT,
        website TEXT,
        category TEXT,
        status TEXT,
        note TEXT DEFAULT ''
    )
    """)
    try:
        c.execute("ALTER TABLE leads ADD COLUMN note TEXT DEFAULT ''")
    except:
        pass
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, company, email, website, category, status, note FROM leads ORDER BY id DESC")
    leads = c.fetchall()
    conn.close()

    rows = ""
    for lead in leads:
        rows += f"""
        <tr>
            <td>{lead[1]}</td>
            <td>{lead[2]}</td>
            <td>{lead[3]}</td>
            <td>{lead[4]}</td>
            <td>
                <form action="/status/{lead[0]}" method="post">
                    <select name="status">
                        <option>{lead[5]}</option>
                        <option>NEW</option>
                        <option>CONTACTED</option>
                        <option>REPLIED</option>
                        <option>QUOTED</option>
                        <option>SAMPLE</option>
                        <option>ORDERED</option>
                        <option>LOST</option>
                    </select>
                    <button>Update</button>
                </form>
            </td>
            <td>
                <form action="/note/{lead[0]}" method="post">
                    <input name="note" value="{lead[6] or ''}" placeholder="Note">
                    <button>Save</button>
                </form>
            </td>
            <td><a class="delete" href="/delete/{lead[0]}">Delete</a></td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>SOGRACE CRM V2.2</title>
<style>
body{{font-family:Arial;background:#07111f;color:white;margin:0}}
.header{{background:#0b1f3a;padding:20px;font-size:28px;font-weight:bold}}
.container{{padding:30px}}
.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select{{padding:10px;margin:6px;border-radius:6px;border:0}}
button{{padding:10px 16px;background:#1683ff;color:white;border:0;border-radius:6px}}
a{{color:white}}
.delete{{background:#d93333;padding:8px 12px;border-radius:6px;text-decoration:none}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:12px;border-bottom:1px solid #333;text-align:left}}
.export{{display:inline-block;background:#0bbf7a;padding:10px 18px;border-radius:6px;text-decoration:none;margin-bottom:15px}}
</style>
</head>
<body>
<div class="header">SOGRACE CRM V2.2</div>
<div class="container">

<div class="card">
<h2>Add Lead</h2>
<form action="/add" method="post">
<input name="company" placeholder="Company">
<input name="email" placeholder="Email">
<input name="website" placeholder="Website">
<select name="category">
<option>ELDERLY</option>
<option>PET</option>
<option>PLATFORM</option>
<option>DISTRIBUTOR</option>
</select>
<button type="submit">Add Lead</button>
</form>
</div>

<div class="card">
<h2>Lead List</h2>
<a class="export" href="/export">Export CSV</a>
<table>
<tr>
<th>Company</th><th>Email</th><th>Website</th><th>Category</th><th>Status</th><th>Note</th><th>Action</th>
</tr>
{rows}
</table>
</div>

</div>
</body>
</html>
"""

@app.post("/add")
def add_lead(
    company: str = Form(...),
    email: str = Form(...),
    website: str = Form(...),
    category: str = Form(...)
):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO leads (company,email,website,category,status,note) VALUES (?,?,?,?,?,?)",
        (company,email,website,category,"NEW","")
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/status/{lead_id}")
def update_status(lead_id: int, status: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/note/{lead_id}")
def update_note(lead_id: int, note: str = Form("")):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE leads SET note=? WHERE id=?", (note, lead_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete/{lead_id}")
def delete_lead(lead_id: int):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/export")
def export_csv():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT company,email,website,category,status,note FROM leads ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Company","Email","Website","Category","Status","Note"])
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sograce_crm_leads.csv"}
    )
