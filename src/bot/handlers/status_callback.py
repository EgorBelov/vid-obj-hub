# src/bot/handlers/status_callback.py
from aiogram import types
from src.database.session import AsyncSessionLocal
from src.database.models import Video, VideoObject
from sqlalchemy import select

async def status_callback_handler(callback: types.CallbackQuery):
    """
    Обработчик callback-запроса для проверки статуса видео.
    Ожидается, что callback.data имеет вид: "status:<video_id>"
    """
    try:
        # Извлекаем video_id из callback.data
        video_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        video = await session.get(Video, video_id)
        if not video:
            await callback.message.reply(f"Видео с id={video_id} не найдено.")
            return

        if video.status != "processed":
            await callback.message.reply(f"Статус видео {video_id}: {video.status}.")
            return

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
        await callback.message.reply("В этом видео не обнаружено объектов.")
    else:
        text = f"Видео {video_id} (статус={video.status}):\n"
        for label, cnt, avg_conf in rows:
            text += f"- {label}: {cnt} шт. ср.увер={avg_conf:.2f}\n"
        await callback.message.reply(text)

    await callback.answer()  # завершаем обработку callback

def register_status_callback_handlers(dp):
    dp.callback_query.register(status_callback_handler, lambda c: c.data and c.data.startswith("status:"))
