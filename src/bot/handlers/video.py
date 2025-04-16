# src/bot/handlers/video.py
import io
import os
from datetime import datetime
from aiogram import types
from sqlalchemy import select
from src.database.session import AsyncSessionLocal
from src.database.models import Video, VideoObject
from src.bot.keyboards.main_menu import main_menu_keyboard
from src.recognition import detect_objects_in_video
from decouple import config
from recognition_service.celery_app import celery_app
from recognition_service.detect import process_video_task  # наша Celery задача
from src.bot.keyboards.status import get_status_keyboard
from src.s3.s3_client import upload_fileobj

VIDEO_STORAGE = config('VIDEO_STORAGE')
if not os.path.exists(VIDEO_STORAGE):
    os.makedirs(VIDEO_STORAGE)

async def handle_video(message: types.Message):
    video = message.video
    file_id = video.file_id

    # # Получаем путь к файлу Telegram
    # file_info = await message.bot.get_file(file_id)
    # remote_file_path = file_info.file_path

    # # Формируем локальный путь
    # local_file_path = os.path.join(VIDEO_STORAGE, f"{file_id}.mp4")

    # # Скачиваем видео на диск
    # await message.bot.download_file(remote_file_path, local_file_path)
    
    # Получаем информацию о файле
    file_info = await message.bot.get_file(file_id)
    file_path = file_info.file_path
    
    # Скачиваем файл в память (BytesIO)
    byte_stream = io.BytesIO()
    await message.bot.download_file(file_path, byte_stream)
    byte_stream.seek(0)  # сбрасываем указатель в начало

    # Создаём ключ (S3-имя) для файла
    # например, "videos/{telegram_file_id}.mp4"
    key = f"videos/{file_id}.mp4"

    # Загружаем в S3
    s3_url = upload_fileobj(byte_stream, key=key)

    # Сохраняем информацию о видео в БД
    async with AsyncSessionLocal() as session:
        new_video = Video(
            telegram_file_id=file_id,
            # local_path=local_file_path,
            s3_url=s3_url,  # теперь мы храним ссылку на объект в S3
            user_id=message.from_user.id,
            upload_time=datetime.utcnow(),
            # status="pending"  # если нужно
        )
        session.add(new_video)
        await session.commit()
        video_id = new_video.id

    # # Информируем пользователя, что начинаем распознавание
    # await message.reply("Видео загружено! Начинаю распознавание (агрегированная статистика)...")

    # # Запускаем распознавание (синхронно, блокирует бота)
    # async with AsyncSessionLocal() as session:
    #     await detect_objects_in_video(session, video_id, local_file_path)

    # # По окончании чтём результаты из таблицы video_objects
    # async with AsyncSessionLocal() as session:
    #     query = (
    #         select(
    #             VideoObject.label,
    #             VideoObject.total_count,
    #             VideoObject.avg_confidence,
    #             VideoObject.best_confidence,
    #             VideoObject.best_second,
    #         )
    #         .where(VideoObject.video_id == video_id)
    #     )
    #     rows = (await session.execute(query)).all()

    # if not rows:
    #     await message.reply(
    #         "Объекты не найдены (или распознавание не сработало).",
    #         reply_markup=main_menu_keyboard
    #     )
    #     return

    # # Формируем итоговый текст
    # text_result = "Распознавание завершено! Найдены объекты:\n"
    # for label, total_count, avg_conf, best_conf, best_sec in rows:
    #     text_result += (
    #         f"- {label}: {total_count} шт., "
    #         f"средняя уверенность={avg_conf:.2f}, "
    #         f"максимальная={best_conf:.2f} (на {best_sec:.1f} c.)\n"
    #     )

    # await message.reply(text_result, reply_markup=main_menu_keyboard)

    # Отправляем задачу на обработку через RabbitMQ (Celery)
    celery_app.send_task("process_video_task", args=[video_id])
    # process_video_task.delay(video_id)

    # Отправляем пользователю сообщение с кодом видео и inline-клавиатурой для проверки статуса
    await message.reply(
        f"Ваше видео успешно загружено. Его код: {video_id}.\nНажмите кнопку 'Проверить статус', чтобы узнать статус обработки.",
        reply_markup=get_status_keyboard(video_id)
    )