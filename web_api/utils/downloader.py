# web_api/utils/downloader.py
import asyncio, hashlib, os, shutil, shutil, tempfile, logging
from typing import Tuple
from shutil import which

import yt_dlp
from fastapi import HTTPException
log = logging.getLogger(__name__)

def _download_sync(url: str) -> Tuple[bytes, str]:
    tmp_dir  = tempfile.mkdtemp(prefix="ydl_")
    outtmpl  = os.path.join(tmp_dir, "%(id)s.%(ext)s")

    have_ffmpeg = which("ffmpeg") is not None
    # если ffmpeg нет – скачиваем только «цельный» поток
    if have_ffmpeg:
        ydl_format = ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                      "best[ext=mp4]/best")
        merge_to   = "mp4"
    else:
        ydl_format = "best[ext=mp4]/best"   # прогрессивный mp4
        merge_to   = None                   # не требуется

    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": ydl_format,
        "merge_output_format": merge_to,
        "concurrent_fragment_downloads": 4,
        "retries": 5,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            final = ydl.prepare_filename(info)
            if not final.lower().endswith(".mp4"):
                final = os.path.splitext(final)[0] + ".mp4"
        except Exception as exc:
            raise RuntimeError(exc) from exc

    data = open(final, "rb").read()
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return data, title


async def fetch_video_bytes(url: str) -> bytes:
    try:
        data, title = await asyncio.to_thread(_download_sync, url)
        if len(data) < 1_000_000:
            raise RuntimeError("Downloaded file is too small")
        log.info("Downloaded «%s», %d bytes", title, len(data))
        return data
    except Exception as exc:
        log.exception("yt‑dlp failed: %s", exc)
        raise HTTPException(400, "Не удалось получить mp4 из ссылки") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
