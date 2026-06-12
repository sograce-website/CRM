#!/usr/bin/env python3
from pathlib import Path
import datetime
import shutil
import py_compile

CRM = Path("/home/admin/crm")
MAIN = CRM / "main.py"

if not MAIN.exists():
    raise SystemExit("ERROR: /home/admin/crm/main.py not found")

backup = CRM / f"main_backup_dashboard_auto_collect_v11_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
shutil.copy2(MAIN, backup)

txt = MAIN.read_text(encoding="utf-8", errors="ignore")

if "NEW AUTO COLLECT ROUTES START" not in txt:
    raise SystemExit("ERROR: 请先执行 python3 install_auto_collect_new.py")

json_route = """
# ===== AUTO COLLECT DASHBOARD V1.1 STATUS API START =====
@app.get("/api/auto_collect_new_status")
def api_auto_collect_new_status(request: Request):
    if not is_login(request):
        return {"status": "Login Required", "message": "Please login first", "found": 0, "saved": 0, "skipped": 0, "failed": 0}
    from pathlib import Path
    import json
    p = Path("/home/admin/crm/auto_collect_status.json")
    if not p.exists():
        return {"status": "Ready", "message": "No run yet", "found": 0, "saved": 0, "skipped": 0, "failed": 0}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "Error", "message": str(e), "found": 0, "saved": 0, "skipped": 0, "failed": 0}
# ===== AUTO COLLECT DASHBOARD V1.1 STATUS API END =====
"""
if "AUTO COLLECT DASHBOARD V1.1 STATUS API START" not in txt:
    txt += "\\n" + json_route + "\\n"

download_route = """
# ===== AUTO COLLECT DASHBOARD V1.1 CSV DOWNLOAD START =====
@app.get("/download_auto_leads_new")
def download_auto_leads_new(request: Request):
    if not is_login(request):
        return RedirectResponse("/login", 303)
    from pathlib import Path
    from fastapi.responses import FileResponse, HTMLResponse
    p = Path("/home/admin/crm/auto_leads.csv")
    if not p.exists():
        return HTMLResponse("<h2>auto_leads.csv not found</h2><p><a href='/'>Back</a></p>")
    return FileResponse(str(p), filename="auto_leads.csv", media_type="text/csv")
# ===== AUTO COLLECT DASHBOARD V1.1 CSV DOWNLOAD END =====
"""
if "download_auto_leads_new" not in txt:
    txt += "\\n" + download_route + "\\n"

# 菜单入口切换到新模块
txt = txt.replace('href="/auto_collect">', 'href="/auto_collect_new">')
txt = txt.replace("href='/auto_collect'>", "href='/auto_collect_new'>")
txt = txt.replace('href="/lead_collect_log">', 'href="/auto_collect_new_log">')
txt = txt.replace("href='/lead_collect_log'>", "href='/auto_collect_new_log'>")

dashboard_script = """
<script>
async function refreshNewAutoCollectStatus(){
  try{
    const r = await fetch('/api/auto_collect_new_status', {cache:'no-store'});
    const s = await r.json();
    const status = s.status || 'Ready';
    const found = s.found || 0;
    const saved = s.saved || 0;
    const skipped = s.skipped || 0;
    const failed = s.failed || 0;
    const msg = s.message || '';
    const html = status + '<div style="font-size:13px;line-height:1.5;margin-top:8px;color:#b8c7dd">Found ' + found + ' / Saved ' + saved + ' / Skipped ' + skipped + ' / Failed ' + failed + '<br>' + msg + '</div><div style="font-size:13px;margin-top:8px"><a href="/auto_collect_new">Start</a> | <a href="/auto_collect_new_log">Log</a> | <a href="/auto_collect_new_status">Status</a> | <a href="/download_auto_leads_new">CSV</a></div>';
    const all = Array.from(document.querySelectorAll('div,section,article'));
    for(const el of all){
      if(el.innerText && el.innerText.includes('AUTO COLLECT') && !el.dataset.newAutoCollectPatched){
        const big = Array.from(el.querySelectorAll('*')).find(x => {
          const t = (x.innerText || '').trim();
          return t === 'Ready' || t === 'Running' || t === 'Finished';
        });
        if(big){
          big.innerHTML = html;
          el.dataset.newAutoCollectPatched = '1';
          break;
        }
      }
    }
  }catch(e){}
}
setTimeout(refreshNewAutoCollectStatus, 800);
setInterval(refreshNewAutoCollectStatus, 10000);
</script>
"""

if "refreshNewAutoCollectStatus" not in txt:
    if "</body>" in txt:
        txt = txt.replace("</body>", dashboard_script + "\\n</body>", 1)
    else:
        txt += "\\n" + dashboard_script + "\\n"

MAIN.write_text(txt, encoding="utf-8")
py_compile.compile(str(MAIN), doraise=True)

print("OK: Dashboard V1.1 installed")
print(f"Backup: {backup}")
print("Routes:")
print("  /auto_collect_new")
print("  /auto_collect_new_log")
print("  /auto_collect_new_status")
print("  /api/auto_collect_new_status")
print("  /download_auto_leads_new")
