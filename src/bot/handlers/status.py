# src/bot/handlers/status.py
import asyncio
from aiogram import types
from src.database.session import AsyncSessionLocal
from src.database.models import Video, VideoObject

async def status_cmd(message: types.Message):
    # допустим пользователь пишет "/status 123"
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Укажите ID видео, например: /status 10")
        return

    video_id = int(parts[1])
    async with AsyncSessionLocal() as session:
        video = await session.get(Video, video_id)
        if not video:
            await message.reply(f"Видео с id={video_id} не найдено.")
            return

        if video.status != "processed":
            await message.reply(f"Статус видео {video_id}: {video.status}.")
            return

        # Если video.status == "processed", можно посмотреть в VideoObject
        from sqlalchemy import select
        stmt = (
            select(
                VideoObject.label, 
                VideoObject.total_count,
                VideoObject.avg_confidence
            )
            .where(VideoObject.video_id == video_id)
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        await message.reply("В этом видео не обнаружено объектов.")
        return

    text = f"Видео {video_id} (статус={video.status}):\n"
    for label, cnt, avg_conf in rows:
        text += f"- {label}: {cnt} шт. ср.увер={avg_conf:.2f}\n"

    await message.reply(text)

