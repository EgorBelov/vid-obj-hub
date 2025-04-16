# src/bot/handlers/video.py
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

    # Загружаем видео в S3 через модуль s3_client.upload_fileobj,
    # при этом формируем ключ, например, "videos/<telegram_file_id>.mp4"
    key = f"videos/{file_id}.mp4"
    from src.s3.s3_client import upload_fileobj  # если еще не импортировали
    s3_url = upload_fileobj(byte_stream, key=key)

    # Создаем запись о видео через API DB-сервиса:
    async with httpx.AsyncClient() as client:
        payload = {
            "telegram_file_id": file_id,
            "s3_url": s3_url,
            "user_id": message.from_user.id,
            "status": "pending",
            "upload_time": datetime.utcnow().isoformat()
        }
        response = await client.post(f"{DB_SERVICE_URL}/videos/", json=payload)
        response.raise_for_status()  # выбросит исключение при ошибке
        video_record = response.json()
        video_id = video_record["id"]

    # Отправляем задачу на обработку через RabbitMQ (Celery)
    celery_app.send_task("process_video_task", args=[video_id])
    
    # Отправляем пользователю сообщение, содержащее код видео и inline клавиатуру для проверки статуса
    await message.reply(
        f"Ваше видео успешно загружено в S3. Его код: {video_id}.\n"
        "Нажмите кнопку 'Проверить статус', чтобы узнать статус обработки.",
        reply_markup=get_status_keyboard(video_id)
    )
