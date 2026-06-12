from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3

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
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def home():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM leads ORDER BY id DESC")
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
            <td>{lead[5]}</td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>SOGRACE CRM V2.1</title>

<style>
body{{font-family:Arial;background:#07111f;color:white;margin:0}}
.header{{background:#0b1f3a;padding:20px;font-size:26px;font-weight:bold}}
.container{{padding:30px}}
.card{{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}}
input,select{{padding:10px;margin:6px;border-radius:6px;border:0}}
button{{padding:10px 20px;background:#1683ff;color:white;border:0;border-radius:6px}}
table{{width:100%;border-collapse:collapse}}
td,th{{padding:10px;border-bottom:1px solid #333;text-align:left}}
</style>

</head>

<body>

<div class="header">
SOGRACE CRM V2.1
</div>

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

<button type="submit">
Add Lead
</button>

</form>

</div>

<div class="card">

<h2>Lead List</h2>

<table>

<tr>
<th>Company</th>
<th>Email</th>
<th>Website</th>
<th>Category</th>
<th>Status</th>
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
        """
        INSERT INTO leads
        (company,email,website,category,status)
        VALUES
        (?,?,?,?,?)
        """,
        (
            company,
            email,
            website,
            category,
            "NEW"
        )
    )

    conn.commit()
    conn.close()

    return RedirectResponse(url="/", status_code=303)
