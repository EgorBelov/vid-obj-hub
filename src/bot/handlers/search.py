# src/bot/handlers/search.py
from aiogram import types
from aiogram.types import URLInputFile
import random
from sqlalchemy import select
from src.database.session import AsyncSessionLocal
from src.database.models import VideoObject, Video
from src.bot.states import SEARCH_STATE

async def start_search(message: types.Message):
    user_id = message.from_user.id
    SEARCH_STATE[user_id] = True  # устанавливаем флаг, что ждем ввода запроса
    await message.reply("Введите название объекта, который хотите найти (например: person, car, dog).")


async def handle_search_query(message: types.Message):
    user_id = message.from_user.id

    # Проверяем: действительно ли пользователь находится в режиме поиска
    if SEARCH_STATE.get(user_id) is True:
        query_text = message.text.strip().lower()
        SEARCH_STATE[user_id] = False  # выходим из режима поиска

        async with AsyncSessionLocal() as session:
            # 1) Находим все записи в VideoObject, где label удовлетворяет запросу
            # и извлекаем video_id + best_second
            stmt = (
                select(VideoObject.video_id, VideoObject.best_second)
                .where(VideoObject.label.ilike(f"%{query_text}%"))
            )
            result = (await session.execute(stmt)).all()  
            # result это список кортежей [(video_id, best_second), ...]

            if not result:
                await message.reply("Ничего не найдено по вашему запросу.")
                return

            # 2) Случайным образом выбираем 3 записи
            random.shuffle(result)
            top_entries = result[:3]

            # Выделяем список video_id, чтобы получить объекты Video
            top_ids = [row[0] for row in top_entries]

            # 3) Загружаем объекты Video
            stmt_v = select(Video).where(Video.id.in_(top_ids))
            videos = (await session.execute(stmt_v)).scalars().all()

        # Создаём словарь video_id -> best_second (чтобы вывести время)
        vid_to_second = {row[0]: row[1] for row in top_entries}

        if not videos:
            await message.reply("Ничего не найдено (нет объектов Video).")
            return

        # Выводим сводку в текстовом сообщении
        text = "Найдены видео (показаны до 3 случайных):\n"
        for vid in videos:
            # Для этого видео находим соответствующее best_second
            best_sec = vid_to_second.get(vid.id, 0)
            text += f"- ID {vid.id}, статус={vid.status}, наибольшая уверенность в {best_sec:.1f} c.\n"
        await message.reply(text)

        # Пример: отправляем само видео (если публичное S3)
        for vid in videos:
            # Проверяем, хранится ли s3_url (или другой способ получить файл)
            if not getattr(vid, "s3_url", None):
                continue

            file = URLInputFile(url=vid.s3_url)
            await message.answer_video(file, caption=f"Видео ID {vid.id}, best_second={vid_to_second[vid.id]:.1f} c.")

    else:
        # Пользователь не в режиме поиска
        await message.reply("Неизвестная команда. Нажмите «Поиск», чтобы начать поиск.")