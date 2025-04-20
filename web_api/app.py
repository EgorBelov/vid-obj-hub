import asyncio
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx, io, hashlib, os
from decouple import config
from datetime import datetime
from recognition_service.celery_app import celery_app
from s3.s3_client import upload_fileobj
import yt_dlp
import re, json
from web_api.utils.downloader import fetch_video_bytes


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


VK_TOKEN = config("access_user_token", default="")

VK_LINK_RE = re.compile(r"vk\\.com/video(?P<oid>-?\\d+)_(?P<vid>\\d+)")

async def fetch_vk_mp4(owner_id: str, video_id: str) -> str | None:
    """
    Возвращает прямую ссылку на mp4 через VK API или None.
    """
    if not VK_TOKEN:
        return None
    params = {
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": "5.199"
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://api.vk.com/method/video.get", params=params)
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        files = data["response"]["items"][0]["files"]
        # Берём самое качественное mp4, если есть
        for k in ("mp4_720", "mp4_480", "mp4_360", "external"):
            if k in files:
                return files[k]
    except Exception:
        return None
    return None

async def download_file(url: str, timeout: int = 60) -> bytes:
    """Кача­ет по прямой ссылке и возвращает bytes."""
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.get(url, follow_redirects=True)
    if r.status_code != 200:
        raise HTTPException(400, f"Cannot download {url} ({r.status_code})")
    return r.content


# async def fetch_video_bytes(url: str) -> bytes:
#     """
#     1) mp4 напрямую
#     2) yt‑dlp
#     3) VK API (если ссылка вида vk.com/video…)
#     """
#     if url.lower().endswith(".mp4"):
#         return await download_file(url)

#     # 1. yt‑dlp
#     try:
#         data = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(
#             {"quiet": True, "format": "best[ext=mp4]/best", "forcejson": True}
#         ).extract_info(url, download=False))
#         direct = data.get("url")
#         if direct and direct.endswith(".mp4"):
#             return await download_file(direct)
#     except Exception:
#         pass  # переходим к VK API

#     # 2. VK API
#     m = VK_LINK_RE.search(url)
#     if m:
#         mp4 = await fetch_vk_mp4(m["oid"], m["vid"])
#         if mp4:
#             return await download_file(mp4)

#     raise HTTPException(400, "Не удалось получить mp4 из ссылки")


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
async def upload_url(request: Request, url: str = Form(...)):
    """
    Получает ссылку (VK / Rutube / YouTube etc.), скачивает видео через yt‑dlp,
    заносит запись в БД‑сервис, заливает в S3 и ставит задачу Celery.
    """
    # 1) качаем
    data = await fetch_video_bytes(url)
    sha = sha256_bytes(data)

    # 2) черновик записи (без s3_url)
    payload = {
        "telegram_file_id": None,
        "user_id": 0,
        "video_hash": sha,
        "status": "pending",
        "upload_time": datetime.utcnow().isoformat(),
        "s3_url": "",
    }
    resp = await db_post("/videos/", payload)
    if resp.status_code not in (200, 201):
        raise HTTPException(resp.status_code, resp.text)

    video = resp.json()
    vid   = video["id"]

    # 3) если дубликат — редирект на статус
    if video.get("duplicate"):
        return RedirectResponse(f"/status/{vid}", status_code=303)

    # 4) загружаем в S3
    s3_url = upload_fileobj(io.BytesIO(data), key=f"videos/{sha}.mp4")
    await db_put(f"/videos/{vid}", {"s3_url": s3_url})

    # 5) Celery
    celery_app.send_task("process_video_task", args=[vid])

    return RedirectResponse(f"/status/{vid}", status_code=303)



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
