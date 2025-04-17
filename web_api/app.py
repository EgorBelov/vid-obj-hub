from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx, io, hashlib, os
from decouple import config
from datetime import datetime
from recognition_service.celery_app import celery_app
from s3.s3_client import upload_fileobj

DB_URL = config("DB_SERVICE_URL", default="http://localhost:8000")
API_PORT = int(config("WEB_API_PORT", default=8080))

app = FastAPI(title="Vid‑Obj Hub — Web UI")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# ---------- helpers ---------------------------------------------------------
async def db_post(path: str, json: dict):
    async with httpx.AsyncClient(timeout=20) as c:
        return await c.post(f"{DB_URL}{path}", json=json)

async def db_put(path: str, json: dict):
    async with httpx.AsyncClient(timeout=20) as c:
        return await c.put(f"{DB_URL}{path}", json=json)

async def db_get(path: str, params=None):
    async with httpx.AsyncClient(timeout=20) as c:
        return await c.get(f"{DB_URL}{path}", params=params)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# ---------- HTML pages ------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload/file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    data = await file.read()
    sha = sha256_bytes(data)

    payload_init = {
        "telegram_file_id": None,          # вместо None
        "user_id": 0,
        "video_hash": sha,
        "status": "pending",
        "upload_time": datetime.utcnow().isoformat(),
        "s3_url": ""                     # тоже пустая строка
    }

    res = await db_post("/videos/", payload_init)
    if res.status_code not in (200, 201):
        raise HTTPException(res.status_code, res.text)
    j = res.json()
    vid = j["id"]
    if j.get("duplicate"):
        return RedirectResponse(url=f"/status/{vid}", status_code=303)

    # загрузка в S3
    s3_url = upload_fileobj(io.BytesIO(data), key=f"videos/{sha}.mp4")
    await db_put(f"/videos/{vid}", {"s3_url": s3_url})

    celery_app.send_task("process_video_task", args=[vid])
    return RedirectResponse(url=f"/status/{vid}", status_code=303)

@app.post("/upload/url")
async def upload_url(url: str = Form(...)):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
    if r.status_code != 200:
        raise HTTPException(400, "Cannot download URL")
    fake_file = UploadFile(filename="remote.mp4", file=io.BytesIO(r.content))
    return await upload_file(Request(scope={} ), fake_file)   # переиспользуем логику выше

@app.get("/status/{video_id}", response_class=HTMLResponse)
async def status_page(request: Request, video_id: int):
    v = await db_get(f"/videos/{video_id}")
    if v.status_code != 200:
        raise HTTPException(404, "video not found")
    video = v.json()

    objects = []
    if video["status"] == "processed":
        o = await db_get(f"/videos/{video_id}/objects")
        objects = o.json() if o.status_code == 200 else []

    return templates.TemplateResponse(
        "status.html",
        {"request": request, "video": video, "objects": objects}
    )

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = ""):
    results = []
    if q:
        r = await db_get("/search", params={"q": q})
        results = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse(
        "search.html",
        {"request": request, "query": q, "results": results}
    )

# ---------- launch with  `uvicorn web_api.app:app --reload --port 8080`
