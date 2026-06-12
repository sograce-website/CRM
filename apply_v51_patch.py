#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import datetime
import shutil

CRM_DIR = Path(__file__).resolve().parent
MAIN = CRM_DIR / "main.py"
BACKUP = CRM_DIR / f"main_backup_before_v51_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"

if not MAIN.exists():
    raise SystemExit("ERROR: main.py not found. Put this file inside ~/crm and run: python3 apply_v51_patch.py")

txt = MAIN.read_text(encoding="utf-8", errors="ignore")

if "CRM V5.1 LIVE STATUS PATCH START" in txt:
    print("V5.1 patch already exists. No duplicate patch applied.")
    raise SystemExit(0)

shutil.copy2(MAIN, BACKUP)
print(f"Backup created: {BACKUP.name}")

txt = txt.replace("SOGRACE CRM V5.0 Professional Dashboard", "SOGRACE CRM V5.1 Professional Dashboard")
txt = txt.replace("V5.0 Professional", "V5.1 Professional")

txt = txt.replace(
    '<div class="card"><div class="label">Auto Collect</div><div class="num">Ready</div></div>',
    '<div class="card"><div class="label">Auto Collect</div><div class="num" id="v51_collect_status">Ready</div><div class="small" id="v51_collect_detail">Waiting</div></div>'
)
txt = txt.replace(
    '<div class="card"><div class="label">Auto Email</div><div class="num">Ready</div></div>',
    '<div class="card"><div class="label">Auto Email</div><div class="num" id="v51_email_status">Ready</div><div class="small" id="v51_email_detail">Waiting</div></div>'
)

txt = txt.replace('href="/auto_collect"', 'href="/auto_collect_v51"')
txt = txt.replace('href="/auto_send/50"', 'href="/auto_send_v51/50"')
txt = txt.replace('href="/auto_send/100"', 'href="/auto_send_v51/100"')

txt = txt.replace(
    '<a href="/lead_collect_log">📄 Collector Log</a>',
    '<a href="/lead_collect_log">📄 Collector Log</a>\n      <a href="/collector_log">📡 V5.1 Live Log</a>\n      <a href="/reply_center">💬 Reply Center</a>'
)
txt = txt.replace(
    '<a class="btn" href="/email_center">Email Center</a>',
    '<a class="btn" href="/email_center">Email Center</a>\n        <a class="btn" href="/v51_status">V5.1 Status</a>\n        <a class="btn" href="/reply_center">Reply Center</a>'
)

js = r"""
<script>
async function loadV51Status(){
  try{
    const r = await fetch('/api/v51/status?_=' + Date.now());
    const d = await r.json();
    const c = document.getElementById('v51_collect_status');
    const cd = document.getElementById('v51_collect_detail');
    const e = document.getElementById('v51_email_status');
    const ed = document.getElementById('v51_email_detail');
    if(c){ c.innerText = d.collect.status || 'Ready'; }
    if(cd){ cd.innerText = 'Found: ' + (d.collect.found || 0) + ' · Today: ' + (d.collect.today || 0); }
    if(e){ e.innerText = d.email.status || 'Ready'; }
    if(ed){ ed.innerText = 'Sent: ' + (d.email.sent || 0) + ' · Failed: ' + (d.email.failed || 0); }
  }catch(err){}
}
loadV51Status();
setInterval(loadV51Status, 3000);
</script>
"""
marker = "</body>\n</html>\n\"\"\""
idx = txt.find(marker)
if idx != -1:
    txt = txt[:idx] + js + "\n" + txt[idx:]
else:
    print("WARNING: dashboard html marker not found; status API still added.")

v51_code = r"""
# ===== CRM V5.1 LIVE STATUS PATCH START =====
import json as _v51_json
from pathlib import Path as _V51Path

V51_DIR = _V51Path("/home/admin/crm")
V51_STATUS_FILE = V51_DIR / "v51_status.json"
V51_COLLECT_LOG = V51_DIR / "collector_v51.log"
V51_EMAIL_LOG = V51_DIR / "email_v51.log"

def _v51_now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _v51_default_status():
    return {
        "collect": {"status": "Ready", "found": 0, "today": 0, "message": "Waiting", "updated": _v51_now()},
        "email": {"status": "Ready", "sent": 0, "failed": 0, "message": "Waiting", "updated": _v51_now()}
    }

def _v51_read_status():
    try:
        if V51_STATUS_FILE.exists():
            return _v51_json.loads(V51_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return _v51_default_status()

def _v51_write_status(data):
    V51_STATUS_FILE.write_text(_v51_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _v51_set(section, **kwargs):
    data = _v51_read_status()
    data.setdefault(section, {})
    data[section].update(kwargs)
    data[section]["updated"] = _v51_now()
    _v51_write_status(data)

def _v51_log(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{_v51_now()}] {text}\\n")

def _v51_today_leads_count():
    try:
        conn = db()
        c = conn.cursor()
        today = datetime.date.today().isoformat()
        try:
            n = c.execute("SELECT COUNT(*) FROM leads WHERE created_at LIKE ?", (today + "%",)).fetchone()[0]
        except Exception:
            n = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()
        return int(n or 0)
    except Exception:
        return 0

def _v51_total_leads_count():
    try:
        conn = db()
        n = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()
        return int(n or 0)
    except Exception:
        return 0

def _v51_run_collect_worker():
    before = _v51_total_leads_count()
    _v51_set("collect", status="Running", found=0, today=_v51_today_leads_count(), message="Auto collect started")
    _v51_log(V51_COLLECT_LOG, "Auto collect started")
    try:
        candidates = [V51_DIR / "collect_leads.py", V51_DIR / "auto_collect.py", V51_DIR / "lead_collector.py"]
        script = next((p for p in candidates if p.exists()), None)
        if script:
            import subprocess
            _v51_log(V51_COLLECT_LOG, f"Running {script.name}")
            p = subprocess.run(["./venv/bin/python", str(script.name)], cwd=str(V51_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800)
            with open(V51_COLLECT_LOG, "a", encoding="utf-8") as f:
                f.write((p.stdout or "")[-12000:] + "\\n")
        else:
            _v51_log(V51_COLLECT_LOG, "No collector script found. Expected collect_leads.py / auto_collect.py / lead_collector.py")
        after = _v51_total_leads_count()
        found = max(0, after - before)
        _v51_set("collect", status="Ready", found=found, today=_v51_today_leads_count(), message=f"Finished. New leads: {found}")
        _v51_log(V51_COLLECT_LOG, f"Auto collect finished. New leads: {found}")
    except Exception as e:
        _v51_set("collect", status="Error", message=str(e))
        _v51_log(V51_COLLECT_LOG, "ERROR: " + str(e))

@app.get("/auto_collect_v51", response_class=HTMLResponse)
def auto_collect_v51(request: Request, background_tasks: BackgroundTasks):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    background_tasks.add_task(_v51_run_collect_worker)
    return HTMLResponse("<html><body style='font-family:Arial;background:#07111f;color:white;padding:30px'><h2>Auto Collect Started - V5.1</h2><p>Dashboard status will update automatically.</p><p><a style='color:white' href='/'>Back Dashboard</a> | <a style='color:white' href='/collector_log'>Live Log</a></p></body></html>")

def _v51_run_email_worker(count):
    _v51_set("email", status="Running", sent=0, failed=0, message=f"Sending {count} emails")
    _v51_log(V51_EMAIL_LOG, f"Auto email started, count={count}")
    try:
        import subprocess
        script = V51_DIR / "auto_send_v40.py"
        sent = 0
        failed = 0
        if script.exists():
            p = subprocess.run(["./venv/bin/python", "auto_send_v40.py", "send", str(count)], cwd=str(V51_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800)
            output = p.stdout or ""
            with open(V51_EMAIL_LOG, "a", encoding="utf-8") as f:
                f.write(output[-12000:] + "\\n")
            sent = output.lower().count("sent") or output.lower().count("success")
            failed = output.lower().count("failed") or output.lower().count("error")
        else:
            _v51_log(V51_EMAIL_LOG, "auto_send_v40.py not found")
            failed = 1
        _v51_set("email", status="Ready", sent=sent, failed=failed, message="Finished")
        _v51_log(V51_EMAIL_LOG, f"Auto email finished. sent={sent}, failed={failed}")
    except Exception as e:
        _v51_set("email", status="Error", message=str(e))
        _v51_log(V51_EMAIL_LOG, "ERROR: " + str(e))

@app.get("/auto_send_v51/{count}", response_class=HTMLResponse)
def auto_send_v51(request: Request, background_tasks: BackgroundTasks, count: int = ApiPath(..., ge=1, le=100)):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    background_tasks.add_task(_v51_run_email_worker, count)
    return HTMLResponse(f"<html><body style='font-family:Arial;background:#07111f;color:white;padding:30px'><h2>Auto Send Started - V5.1</h2><p>Sending up to {count} emails in background.</p><p><a style='color:white' href='/'>Back Dashboard</a> | <a style='color:white' href='/v51_status'>V5.1 Status</a></p></body></html>")

@app.get("/api/v51/status")
def api_v51_status(request: Request):
    data = _v51_read_status()
    data["collect"]["today"] = _v51_today_leads_count()
    return data

@app.get("/v51_status", response_class=HTMLResponse)
def v51_status_page(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    return HTMLResponse("""
    <html><head><title>SOGRACE CRM V5.1 Status</title>
    <style>body{font-family:Arial;background:#07111f;color:white;padding:25px}.card{background:#111d33;padding:20px;border-radius:12px;margin:14px 0}a{color:white}.num{font-size:28px;font-weight:900}</style></head><body>
    <h1>SOGRACE CRM V5.1 Live Status</h1>
    <p><a href="/">Back Dashboard</a> | <a href="/collector_log">Collector Log</a> | <a href="/reply_center">Reply Center</a></p>
    <div class="card"><h2>Auto Collect</h2><div class="num" id="cst">Loading</div><p id="cdt"></p></div>
    <div class="card"><h2>Auto Email</h2><div class="num" id="est">Loading</div><p id="edt"></p></div>
    <script>
    async function load(){let d=await fetch('/api/v51/status?_='+Date.now()).then(r=>r.json());cst.innerText=d.collect.status;cdt.innerText='Found: '+d.collect.found+' | Today: '+d.collect.today+' | '+d.collect.message+' | '+d.collect.updated;est.innerText=d.email.status;edt.innerText='Sent: '+d.email.sent+' | Failed: '+d.email.failed+' | '+d.email.message+' | '+d.email.updated;}
    load(); setInterval(load,3000);
    </script></body></html>
    """)

@app.get("/collector_log", response_class=HTMLResponse)
def collector_log_v51(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    log = ""
    for p in [V51_COLLECT_LOG, V51_EMAIL_LOG, V51_DIR / "crm.log", V51_DIR / "auto_send_v40.log"]:
        if p.exists():
            try:
                log += f"\\n\\n===== {p.name} =====\\n" + p.read_text(encoding="utf-8", errors="ignore")[-8000:]
            except Exception:
                pass
    log = log.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return HTMLResponse(f"<html><head><title>Collector Log V5.1</title><meta http-equiv='refresh' content='5'><style>body{{font-family:Arial;background:#07111f;color:white;padding:25px}}pre{{background:#020617;padding:18px;border-radius:12px;white-space:pre-wrap}}a{{color:white}}</style></head><body><h1>Collector / Email Live Log V5.1</h1><p><a href='/'>Back Dashboard</a></p><pre>{log or 'No log yet.'}</pre></body></html>")

@app.get("/reply_center", response_class=HTMLResponse)
def reply_center_v51(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    conn = db()
    try:
        rows = conn.execute("SELECT id, company, email, status, last_contact, note FROM leads WHERE UPPER(COALESCE(status,'')) IN ('REPLIED','CONTACTED','QUOTED','SAMPLE','NEGOTIATION','ORDERED') OR COALESCE(note,'')!='' ORDER BY COALESCE(last_contact,'') DESC, id DESC LIMIT 80").fetchall()
    except Exception:
        rows = []
    conn.close()
    html_rows = ""
    for r in rows:
        html_rows += f"<tr><td><a href='/lead/{r[0]}'>{r[1] or ''}</a></td><td>{r[2] or ''}</td><td>{r[3] or ''}</td><td>{r[4] or ''}</td><td>{r[5] or ''}</td></tr>"
    return HTMLResponse(f"<html><head><title>Reply Center V5.1</title><style>body{{font-family:Arial;background:#07111f;color:white;padding:25px}}table{{width:100%;border-collapse:collapse;background:#111d33;border-radius:12px;overflow:hidden}}th,td{{padding:10px;border-bottom:1px solid rgba(255,255,255,.1);text-align:left}}th{{background:#0b1f3a}}a{{color:white}}</style></head><body><h1>Reply Center V5.1</h1><p><a href='/'>Back Dashboard</a></p><table><tr><th>Company</th><th>Email</th><th>Status</th><th>Last Contact</th><th>Note</th></tr>{html_rows or '<tr><td colspan=5>No reply data yet.</td></tr>'}</table></body></html>")

try:
    if not V51_STATUS_FILE.exists():
        _v51_write_status(_v51_default_status())
except Exception:
    pass
# ===== CRM V5.1 LIVE STATUS PATCH END =====
"""
txt += v51_code
MAIN.write_text(txt, encoding="utf-8")
print("SOGRACE CRM V5.1 patch applied to main.py")
print("Next:")
print("  python3 -m py_compile main.py")
print("  pkill -f 'uvicorn main:app' || true")
print("  nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8012 > crm.log 2>&1 &")
