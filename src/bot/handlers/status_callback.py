# src/bot/handlers/status_callback.py
import httpx
from aiogram import types
from decouple import config

DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")


async def status_callback_handler(callback: types.CallbackQuery):
    """
    Обработка inline-кнопки «status:<video_id>».
    Показываем статус, расшифровку объектов и стараемся прислать само видео.
    """
    try:
        video_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные!", show_alert=True)
        return

    async with httpx.AsyncClient() as client:
        # -- сведения о ролике --
        video_resp = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}")
        if video_resp.status_code == 404:
            await callback.message.reply(f"Видео {video_id} не найдено.")
            await callback.answer()
            return
        video = video_resp.json()

        # -- если не обработано, просто сообщаем статус --
        if video.get("status") != "processed":
            await callback.message.reply(f"Статус видео {video_id}: {video.get('status')}.")
            await callback.answer()
            return

        # -- агрегированные объекты --
        obj_resp = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}/objects")
        objects = obj_resp.json() if obj_resp.status_code == 200 else []

    # -------- ответ пользователю --------
    if objects:
        text = f"Видео {video_id} (status=processed):\n"
        for o in objects:
            text += (
                f"- {o['label']}: {o['total_count']} шт., "
                f"avg_conf={o['avg_confidence']:.2f}, "
                f"best_conf={o['best_confidence']:.2f} (на {o['best_second']:.1f} с)\n"
            )
        await callback.message.reply(text)
    else:
        await callback.message.reply("В этом видео не обнаружено объектов.")

    # -------- пытаемся прислать сам файл --------
    sent = False
    try:
        if video.get("telegram_file_id"):
            await callback.message.answer_video(video["telegram_file_id"])
            sent = True
        elif video.get("s3_url"):
            await callback.message.answer_video(video["s3_url"])
            sent = True
    except Exception:
        pass

    if not sent:
        await callback.message.reply("⚠️ Видео недоступно для отправки.")

    await callback.answer()


def register_status_callback_handlers(dp):
    dp.callback_query.register(
        status_callback_handler, lambda c: c.data and c.data.startswith("status:")
    )
