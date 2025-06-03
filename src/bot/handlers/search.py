# src/bot/handlers/search.py
import random
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from src.database.session import AsyncSessionLocal
from src.database.models import VideoObject, Video
from src.bot.states import SEARCH_STATE


async def start_search(message: types.Message):
    user_id = message.from_user.id
    SEARCH_STATE[user_id] = True
    await message.reply("Введите название объекта (пример: person, car, dog).")


async def handle_search_query(message: types.Message):
    # игнорируем не-текст
    if message.content_type != "text":
        return

    user_id = message.from_user.id
    if not SEARCH_STATE.get(user_id):
        return

    query_text = message.text.strip().lower()
    SEARCH_STATE[user_id] = False

    async with AsyncSessionLocal() as session:
        # 1. ищем подходящие объекты
        stmt = (
            select(VideoObject.video_id, VideoObject.best_second)
            .where(VideoObject.label.ilike(f"%{query_text}%"))
        )
        rows = (await session.execute(stmt)).all()
        if not rows:
            await message.reply("Ничего не найдено по запросу.")
            return

        random.shuffle(rows)
        rows = rows[:5]  # максимум 5 штук
        vids = [r[0] for r in rows]

        stmt_v = select(Video).where(Video.id.in_(vids))
        videos = (await session.execute(stmt_v)).scalars().all()

    best_sec = {r[0]: r[1] for r in rows}

    # -------- собираем inline-кнопки --------
    kb = InlineKeyboardBuilder()
    text = "Найдены видео:\n"
    for v in videos:
        sec = best_sec.get(v.id, 0)
        text += f"- ID {v.id}, статус={v.status}, max @ {sec:.1f} с.\n"
        kb.button(text=f"Видео #{v.id}", callback_data=f"status:{v.id}")
    kb.adjust(1)

    await message.reply(text, reply_markup=kb.as_markup())
