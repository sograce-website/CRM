from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3, time
from pathlib import Path

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"
app = FastAPI()

def q(sql, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    r = c.execute(sql, params).fetchall()
    conn.close()
    return r

def leads_stats():
    data = {}
    for st in ["NEW","CONTACTED","REPLIED","QUOTED","SAMPLE","NEGOTIATION","ORDERED","LOST"]:
        data[st] = q("SELECT COUNT(*) FROM leads WHERE status=?", (st,))[0][0]
    data["TOTAL"] = q("SELECT COUNT(*) FROM leads")[0][0]
    return data

def email_status():
    p = CRM_DIR / "auto_send_v40.log"
    sent = failed = 0
    sending = False
    if p.exists():
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
        sent = sum("SENT" in x.upper() or "SUCCESS" in x.upper() for x in lines)
        failed = sum("FAILED" in x.upper() or "ERROR" in x.upper() for x in lines)
        sending = any("SEND" in x.upper() or "START" in x.upper() for x in lines[-20:])
    return {"sending": sending, "sent": sent, "failed": failed}

def collect_status():
    import subprocess
    logs = ["lead_collect.log","collector.log","auto_pipeline_v42.log","pipeline.log"]
    running = False
    last = ""

    try:
        out = subprocess.getoutput("ps -ef | grep -E 'lead_collector_v40.py|lead_collector.py|collect_leads.py|auto_collect.py' | grep -v grep")
        if out.strip():
            running = True
    except:
        pass

    for name in logs:
        p = CRM_DIR / name
        if p.exists():
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            if lines:
                last = lines[-1]

    return {"running": running, "last_log": last}

def pipeline_stats():
    total = q("SELECT COUNT(*) FROM leads")[0][0] or 1
    quoted = q("SELECT COUNT(*) FROM leads WHERE status='QUOTED'")[0][0]
    ordered = q("SELECT COUNT(*) FROM leads WHERE status='ORDERED'")[0][0]
    try:
        value = q("SELECT SUM(expected_amount) FROM leads")[0][0] or 0
    except:
        value = 0
    return {
        "pipeline_value": round(float(value),2),
        "quote_rate": round(quoted/total*100,1),
        "order_rate": round(ordered/total*100,1)
    }

def followups():
    today = time.strftime("%Y-%m-%d")
    try:
        today_rows = q("SELECT company, owner, follow_up_date FROM leads WHERE follow_up_date=? LIMIT 10", (today,))
        overdue_rows = q("SELECT company, owner, follow_up_date FROM leads WHERE follow_up_date<? AND follow_up_date!='' LIMIT 10", (today,))
    except:
        today_rows, overdue_rows = [], []
    return {"today": today_rows, "overdue": overdue_rows}

@app.get("/dashboard_status")
def dashboard_status():
    return JSONResponse({
        "leads": leads_stats(),
        "email": email_status(),
        "collect": collect_status(),
        "pipeline": pipeline_stats(),
        "followups": followups()
    })

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return HTMLResponse("""
<html>
<head>
<title>SOGRACE CRM Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
<style>
body{background:#07111f;color:white;font-family:Arial;margin:0;padding:25px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}
.card{background:#111d33;padding:20px;border-radius:14px;margin-bottom:18px}
.stat{font-size:28px;font-weight:bold;color:#36a3ff}
.good{color:#00d084;font-weight:bold}
.warn{color:#ffd166;font-weight:bold}
table{width:100%;border-collapse:collapse}
td,th{padding:9px;border-bottom:1px solid #24344f;text-align:left}
a{color:white}
</style>
</head>
<body>
<h1>📊 SOGRACE CRM Live Dashboard V4.4</h1>
<p><a href="/">Back CRM</a> | Auto refresh every 5 seconds</p>

<div class="grid">
<div class="card">Finding Customers<br><span id="collectRun" class="stat">-</span></div>
<div class="card">Email Sending<br><span id="emailRun" class="stat">-</span></div>
<div class="card">Sent Emails<br><span id="sentCount" class="stat">0</span></div>
<div class="card">Failed Emails<br><span id="failedCount" class="stat">0</span></div>
</div>

<div class="grid">
<div class="card">Total Leads<br><span id="totalLeads" class="stat">0</span></div>
<div class="card">Pipeline Value<br><span id="pipelineValue" class="stat">$0</span></div>
<div class="card">Quote Rate<br><span id="quoteRate" class="stat">0%</span></div>
<div class="card">Order Rate<br><span id="orderRate" class="stat">0%</span></div>
</div>

<div class="card"><div id="leadChart" style="height:320px"></div></div>

<div class="grid">
<div class="card"><h2>Today Follow Up</h2><table id="todayTable"></table></div>
<div class="card"><h2>Overdue Follow Up</h2><table id="overdueTable"></table></div>
</div>

<div class="card"><h2>Collector Last Log</h2><div id="collectLog">-</div></div>

<script>
var chart = echarts.init(document.getElementById('leadChart'));
function yn(v){return v ? "<span class='good'>RUNNING</span>" : "<span class='warn'>STOPPED</span>";}
function table(rows){
 if(!rows || rows.length===0) return "<tr><td>No data</td></tr>";
 let h="<tr><th>Company</th><th>Owner</th><th>Date</th></tr>";
 rows.forEach(r=>{h+=`<tr><td>${r[0]||''}</td><td>${r[1]||''}</td><td>${r[2]||''}</td></tr>`});
 return h;
}
function load(){
 fetch('/dashboard_status').then(r=>r.json()).then(d=>{
  collectRun.innerHTML=yn(d.collect.running);
  emailRun.innerHTML=yn(d.email.sending);
  sentCount.innerText=d.email.sent;
  failedCount.innerText=d.email.failed;
  totalLeads.innerText=d.leads.TOTAL;
  pipelineValue.innerText="$"+d.pipeline.pipeline_value;
  quoteRate.innerText=d.pipeline.quote_rate+"%";
  orderRate.innerText=d.pipeline.order_rate+"%";
  todayTable.innerHTML=table(d.followups.today);
  overdueTable.innerHTML=table(d.followups.overdue);
  collectLog.innerText=d.collect.last_log || "-";
  chart.setOption({
   title:{text:'Lead Status Overview',textStyle:{color:'#fff'}},
   tooltip:{},
   xAxis:{type:'category',data:Object.keys(d.leads),axisLabel:{color:'#fff',rotate:25}},
   yAxis:{type:'value',axisLabel:{color:'#fff'}},
   series:[{type:'bar',data:Object.values(d.leads)}]
  });
 });
}
load(); setInterval(load,5000);
</script>
</body>
</html>
""")
