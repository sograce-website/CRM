from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
def home():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<title>SOGRACE CRM V2</title>
<style>
body{font-family:Arial;background:#07111f;color:white;margin:0}
.header{background:#0b1f3a;padding:20px;font-size:26px;font-weight:bold}
.container{padding:30px}
.card{background:#111d33;padding:20px;border-radius:12px;margin-bottom:20px}
input,select,button{padding:10px;margin:6px;border-radius:6px;border:0}
button{background:#1683ff;color:white;font-weight:bold}
table{width:100%;border-collapse:collapse;margin-top:20px}
td,th{border-bottom:1px solid #334;padding:10px;text-align:left}
</style>
</head>
<body>
<div class="header">SOGRACE CRM V2</div>
<div class="container">
<div class="card">
<h2>Dashboard</h2>
<p>Total Leads: 0</p>
<p>New Leads: 0</p>
<p>Sent Emails: 0</p>
<p>Replies: 0</p>
</div>

<div class="card">
<h2>Add Lead</h2>
<input placeholder="Company">
<input placeholder="Email">
<input placeholder="Website">
<select>
<option>ELDERLY</option>
<option>PET</option>
<option>PLATFORM</option>
</select>
<button>Add Lead</button>
</div>

<div class="card">
<h2>Lead List</h2>
<table>
<tr><th>Company</th><th>Email</th><th>Category</th><th>Status</th></tr>
<tr><td>Example Company</td><td>info@example.com</td><td>PLATFORM</td><td>NEW</td></tr>
</table>
</div>
</div>
</body>
</html>
""")
