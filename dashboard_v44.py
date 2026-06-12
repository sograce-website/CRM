# dashboard_v44.py - Dashboard Status Fix Version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json, os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

STATIC_DIR = "static"
AUTO_COLLECT_FILE = os.path.expanduser("~/crm/auto_collect_status.json")
AUTO_EMAIL_FILE = os.path.expanduser("~/crm/auto_email_status.json")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def read_status(file_path):
    if not os.path.exists(file_path):
        return {"status": "ready", "found": 0, "saved": 0, "skipped": 0, "status_display":"READY"}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        status_map = {
            "running": "RUNNING",
            "finished": "FINISHED",
            "ready": "READY"
        }
        data["status_display"] = status_map.get(str(data.get("status","ready")).lower(), "READY")
        return data
    except Exception:
        return {"status": "ready", "found": 0, "saved": 0, "skipped": 0, "status_display":"READY"}

@app.get("/")
async def dashboard(request: Request):
    auto_collect_status = read_status(AUTO_COLLECT_FILE)
    auto_email_status = read_status(AUTO_EMAIL_FILE)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "auto_collect": auto_collect_status,
            "auto_email": auto_email_status
        }
    )

@app.get("/auto_collect_new_status")
async def auto_collect_status():
    return JSONResponse(content=read_status(AUTO_COLLECT_FILE))

@app.get("/auto_email_new_status")
async def auto_email_status():
    return JSONResponse(content=read_status(AUTO_EMAIL_FILE))
