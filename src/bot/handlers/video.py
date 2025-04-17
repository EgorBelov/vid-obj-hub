# src/bot/handlers/video.py
import hashlib
import os
import io
from datetime import datetime
from aiogram import types
from decouple import config
import httpx
from recognition_service.celery_app import celery_app

from src.s3.s3_client import upload_fileobj
from src.bot.keyboards.status import get_status_keyboard

# URL DB-сервиса (например, http://localhost:8000)
DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")
VIDEO_STORAGE = config('VIDEO_STORAGE', default="videos")
if not os.path.exists(VIDEO_STORAGE):
    os.makedirs(VIDEO_STORAGE)

async def handle_video(message: types.Message):
    video = message.video
    file_id = video.file_id

    # Получаем путь к файлу в Telegram
    file_info = await message.bot.get_file(file_id)
    file_path = file_info.file_path

    # Скачиваем видео в память
    byte_stream = io.BytesIO()
    await message.bot.download_file(file_path, byte_stream)
    byte_stream.seek(0)

    video_bytes = byte_stream.getvalue()
    video_hash = hashlib.sha256(video_bytes).hexdigest()

    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        payload_init = {
            "telegram_file_id": file_id,
            "user_id": message.from_user.id,
            "video_hash": video_hash,
            "status": "pending",
            "upload_time": datetime.utcnow().isoformat(),
            "s3_url": None            # допускается, потому что Optional
        }
        init_resp = await client.post(f"{DB_SERVICE_URL}/videos/", json=payload_init, timeout=20)
        data = init_resp.json()
        video_id = data["id"]

        # 4. Дубликат? — сразу сообщаем и выходим
        if data.get("duplicate"):
            await message.reply(
                f"Это видео уже есть в системе (ID {video_id}). "
                "Нажмите кнопку «Проверить статус».",
                reply_markup=get_status_keyboard(video_id)
            )
            return
    
    # Загружаем видео в S3 через модуль s3_client.upload_fileobj,
    # при этом формируем ключ, например, "videos/<telegram_file_id>.mp4"
    key = f"videos/{file_id}.mp4"
    from src.s3.s3_client import upload_fileobj  # если еще не импортировали
    s3_url = upload_fileobj(byte_stream, key=key)

    # # Создаем запись о видео через API DB-сервиса:
    # async with httpx.AsyncClient() as client:
    #     payload = {
    #         "telegram_file_id": file_id,
    #         "s3_url": s3_url,
    #         "user_id": message.from_user.id,
    #         "status": "pending",
    #         "upload_time": datetime.utcnow().isoformat()
    #     }
    #     response = await client.post(f"{DB_SERVICE_URL}/videos/", json=payload)
    #     response.raise_for_status()  # выбросит исключение при ошибке
    #     video_record = response.json()
    #     video_id = video_record["id"]
    async with httpx.AsyncClient() as client:
        await client.put(
            f"{DB_SERVICE_URL}/videos/{video_id}",
            json={"s3_url": s3_url}
        )
    
    # Отправляем задачу на обработку через RabbitMQ (Celery)
    celery_app.send_task("process_video_task", args=[video_id])
    
    # Отправляем пользователю сообщение, содержащее код видео и inline клавиатуру для проверки статуса
    await message.reply(
        f"Ваше видео успешно загружено в S3. Его код: {video_id}.\n"
        "Нажмите кнопку 'Проверить статус', чтобы узнать статус обработки.",
        reply_markup=get_status_keyboard(video_id)
    )
