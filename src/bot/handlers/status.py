# src/bot/handlers/status.py
import httpx
from aiogram import types
from decouple import config

DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")

async def status_cmd(message: types.Message):
    # Предположим, пользователь вводит "/status 10"
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Укажите ID видео, например: /status 10")
        return

    try:
        video_id = int(parts[1])
    except ValueError:
        await message.reply("Неверный формат ID.")
        return

    async with httpx.AsyncClient() as client:
        # Получаем информацию о видео
        response = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}")
        if response.status_code == 404:
            await message.reply(f"Видео с ID {video_id} не найдено.")
            return
        video_data = response.json()

        # Если статус не processed, сообщаем статус и выходим
        if video_data.get("status") != "processed":
            await message.reply(f"Статус видео {video_id}: {video_data.get('status')}.")
            return

        # Получаем агрегированные объекты видео
        response = await client.get(f"{DB_SERVICE_URL}/videos/{video_id}/objects")
        if response.status_code == 404:
            await message.reply("Для этого видео нет данных по распознанным объектам.")
            return
        objects = response.json()

    if not objects:
        await message.reply("В этом видео не обнаружено объектов.")
        return

    text = f"Видео {video_id} (статус={video_data.get('status')}):\n"
    for obj in objects:
        label = obj.get("label")
        count = obj.get("total_count")
        avg_conf = obj.get("avg_confidence")
        best_sec = obj.get("best_second")
        text += f"- {label}: {count} шт., средняя уверенность {avg_conf:.2f}, максимальная уверенность зафиксирована на {best_sec:.1f} сек.\n"

    await message.reply(text)
