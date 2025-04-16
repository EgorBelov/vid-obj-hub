# src/bot/handlers/status_callback.py
import httpx
from aiogram import types
from decouple import config

DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")

async def status_callback_handler(callback: types.CallbackQuery):
    """
    Обработчик callback-запроса для проверки статуса видео.
    Ожидается, что callback.data имеет вид: "status:<video_id>"
    """
    try:
        video_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные!", show_alert=True)
        return

    async with httpx.AsyncClient() as client:
        # Получаем данные видео
        video_response = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}")
        if video_response.status_code == 404:
            await callback.message.reply(f"Видео с id={video_id} не найдено.")
            return
        video_data = video_response.json()

        # Если статус видео не "processed", сообщаем об этом
        if video_data.get("status") != "processed":
            await callback.message.reply(f"Статус видео {video_id}: {video_data.get('status')}.")
            return

        # Получаем агрегированные данные по объектам
        objects_response = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}/objects")
        if objects_response.status_code != 200:
            await callback.message.reply("Не удалось получить данные по объектам.")
            return
        objects = objects_response.json()

    if not objects:
        await callback.message.reply("В этом видео не обнаружено объектов.")
    else:
        text = f"Видео {video_id} (статус={video_data.get('status')}):\n"
        for obj in objects:
            label = obj.get("label")
            count = obj.get("total_count")
            avg_conf = obj.get("avg_confidence")
            best_conf = obj.get("best_confidence")
            best_sec = obj.get("best_second")
            text += (
                f"- {label}: {count} шт., "
                f"средняя уверенность {avg_conf:.2f}, "
                f"максимальная {best_conf:.2f} (на {best_sec:.1f} сек.)\n"
            )
        await callback.message.reply(text)

    await callback.answer()

def register_status_callback_handlers(dp):
    dp.callback_query.register(
        status_callback_handler, lambda c: c.data and c.data.startswith("status:")
    )
