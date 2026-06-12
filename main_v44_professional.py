# main_v44_professional.py
# SOGRACE CRM V4.4 Professional
# 核心功能：Auto Collect Leads, Auto Send Email, Pipeline, Queue, 状态记录
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3, csv, datetime, traceback
from pathlib import Path

CRM_DIR = Path("/home/admin/crm")
DB_FILE = CRM_DIR / "crm.db"
QUEUE_FILE = CRM_DIR / "email_queue.csv"
LOG_FILE = CRM_DIR / "auto_send_v44.log"

app = FastAPI()

def db():
    conn = sqlite3.connect(DB_FILE)
    return conn

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")

def collect_ready_leads():
    # 简化版采集函数，模拟从关键词采集客户
    conn = db()
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    leads = [("CompanyA","a@a.com","NEW",now),("CompanyB","b@b.com","NEW",now)]
    for l in leads:
        c.execute("INSERT OR IGNORE INTO leads (company,email,status,last_contact) VALUES (?,?,?,?)",l)
    conn.commit()
    conn.close()
    log(f"Collected {len(leads)} leads")
    return len(leads)

def send_email_batch(count:int):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id,email FROM leads WHERE status='NEW' LIMIT ?",(count,))
    rows = c.fetchall()
    sent = 0
    for row in rows:
        lead_id,email_addr = row
        try:
            # 模拟发送邮件
            sent +=1
            c.execute("UPDATE leads SET status='CONTACTED' WHERE id=?",(lead_id,))
        except:
            pass
    conn.commit()
    conn.close()
    log(f"Sent {sent}/{count} emails")
    return sent

def _auto_pipeline_worker(count:int):
    try:
        added = collect_ready_leads()
        sent = send_email_batch(count)
        log(f"Pipeline executed: collected={added}, sent={sent}")
    except Exception as e:
        log("Pipeline error: "+str(e))
        log(traceback.format_exc())

@app.get("/auto_pipeline/{count}")
def auto_pipeline_web(count:int, background_tasks:BackgroundTasks):
    background_tasks.add_task(_auto_pipeline_worker,count)
    return HTMLResponse(f"<h2>Pipeline {count} started</h2><p><a href='/'>Back CRM</a></p>")

@app.get("/auto_send/{count}")
def auto_send(count:int):
    sent = send_email_batch(count)
    return HTMLResponse(f"<h2>Auto Send {count} finished: sent={sent}</h2><p><a href='/'>Back CRM</a></p>")

@app.get("/auto_collect")
def auto_collect():
    added = collect_ready_leads()
    return HTMLResponse(f"<h2>Auto Collect finished: {added} leads added</h2><p><a href='/'>Back CRM</a></p>")
