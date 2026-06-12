#!/usr/bin/env python3
# SOGRACE CRM V5.2.2 Auto Collect Hotfix
# 用法：cd ~/crm && python3 apply_auto_collect_v522_hotfix.py
from pathlib import Path
import datetime
import shutil
import re
import py_compile

CRM = Path("/home/admin/crm")
MAIN = CRM / "main.py"
COLLECTOR = CRM / "lead_collector.py"

if not MAIN.exists():
    raise SystemExit("ERROR: /home/admin/crm/main.py not found")
if not COLLECTOR.exists():
    raise SystemExit("ERROR: /home/admin/crm/lead_collector.py not found")

backup = CRM / f"main_backup_auto_collect_v522_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
shutil.copy2(MAIN, backup)

txt = MAIN.read_text(encoding="utf-8", errors="ignore")

# 1) 确保主程序只调用 lead_collector.py
txt = txt.replace("lead_collector_v40.py", "lead_collector.py")
txt = txt.replace("lead_collector_v52.py", "lead_collector.py")
txt = txt.replace("lead_collector_v40", "lead_collector")
txt = txt.replace("lead_collector_v52", "lead_collector")

# 2) 确保有 json/datetime 可用
if "import json" not in txt:
    txt = txt.replace("import sqlite3", "import sqlite3\nimport json", 1) if "import sqlite3" in txt else "import json\n" + txt
if "import datetime" not in txt and "from datetime" not in txt:
    txt = txt.replace("import sqlite3", "import sqlite3\nimport datetime", 1) if "import sqlite3" in txt else "import datetime\n" + txt

helper = '''
# ===== V5.2.2 AUTO COLLECT STATUS HELPER START =====
def _auto_collect_status(status="Ready", message="", found=0, saved=0, skipped=0, failed=0):
    try:
        from pathlib import Path as _Path
        import json as _json
        import datetime as _datetime
        status_file = _Path("/home/admin/crm/v52_status.json")
        old = {}
        if status_file.exists():
            try:
                old = _json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        old.update({
            "version": "V5.2.2 Auto Collect Hotfix",
            "status": status,
            "message": message,
            "found": old.get("found", found),
            "saved": old.get("saved", saved),
            "skipped": old.get("skipped", skipped),
            "failed": old.get("failed", failed),
            "updated": _datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        status_file.write_text(_json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
# ===== V5.2.2 AUTO COLLECT STATUS HELPER END =====
'''

if "V5.2.2 AUTO COLLECT STATUS HELPER START" not in txt:
    marker = "# ===== AUTO LEAD COLLECTOR START ====="
    if marker in txt:
        txt = txt.replace(marker, helper + "\n" + marker, 1)
    else:
        txt += "\n" + helper + "\n"

pattern = re.compile(r'def _run_auto_collector\(\):\n(?:    .*\n)+?\n(?=@app\.get\("/auto_collect")', re.M)
new_func = '''def _run_auto_collector():
    import subprocess
    try:
        _auto_collect_status("Running", "Auto Collect started")
        with open("/home/admin/crm/lead_collector.log", "a", encoding="utf-8") as f:
            f.write("\\n===== AUTO COLLECT STARTED FROM CRM V5.2.2 =====\\n")
        result = subprocess.run(
            ["./venv/bin/python", "lead_collector.py"],
            cwd="/home/admin/crm",
            stdout=open("/home/admin/crm/lead_collector.log", "a"),
            stderr=open("/home/admin/crm/lead_collector.log", "a"),
            timeout=1800
        )
        if result.returncode == 0:
            _auto_collect_status("Finished", "Auto Collect finished")
        else:
            _auto_collect_status("Error", f"Collector exit code {result.returncode}")
    except Exception as e:
        _auto_collect_status("Error", str(e))
        with open("/home/admin/crm/lead_collector.log", "a", encoding="utf-8") as f:
            f.write(f"\\nAUTO COLLECT ERROR: {e}\\n")

'''
if pattern.search(txt):
    txt = pattern.sub(new_func, txt, count=1)
else:
    txt = txt.replace('@app.get("/auto_collect"', new_func + '\n@app.get("/auto_collect"', 1)

if 'V5.2.2 route clicked' not in txt:
    txt = txt.replace(
        'background_tasks.add_task(_run_auto_collector)',
        '_auto_collect_status("Running", "V5.2.2 route clicked")\n    background_tasks.add_task(_run_auto_collector)',
        1
    )

MAIN.write_text(txt, encoding="utf-8")

collector_text = COLLECTOR.read_text(encoding="utf-8", errors="ignore")
bad = []
for word in ["duckduckgo", "example.com", "GPS Watch Company"]:
    if word.lower() in collector_text.lower():
        bad.append(word)
if bad:
    raise SystemExit("ERROR: lead_collector.py still contains: " + ", ".join(bad))

py_compile.compile(str(MAIN), doraise=True)
py_compile.compile(str(COLLECTOR), doraise=True)

print("OK: V5.2.2 Auto Collect Hotfix applied")
print(f"Backup: {backup}")
print("Next commands:")
print("cd ~/crm")
print('pkill -f "uvicorn main:app" || true')
print("nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &")
print("Then open CRM and click Auto Collect while logged in.")
