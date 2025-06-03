# src/bot/handlers/search_by_image.py
import io, random, pathlib
from PIL import Image
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ultralytics import YOLO
import httpx
from decouple import config
from src.bot.states import IMAGE_SEARCH_STATE

DB_SERVICE_URL = config("DB_SERVICE_URL", default="http://localhost:8000")

MODEL_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "yolo12n.pt"
yolo = YOLO(str(MODEL_PATH))


async def start_img_search(message: types.Message):
    IMAGE_SEARCH_STATE[message.from_user.id] = True
    await message.reply("Пришлите изображение объекта (фото или скрин).")


async def handle_photo_query(message: types.Message):
    uid = message.from_user.id
    if not IMAGE_SEARCH_STATE.pop(uid, False):
        return  # фото не ожидали

    # --- загружаем файл ---
    file = await message.bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await message.bot.download_file(file.file_path, buf)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    # --- YOLO детект ---
    result = yolo(img, conf=0.35, verbose=False)[0]
    labels = {yolo.names[int(c)] for c in result.boxes.cls.cpu().numpy()}
    if not labels:
        await message.reply("Не удалось распознать объекты.")
        return

    # --- запрос в db_service ---
    async with httpx.AsyncClient(base_url=DB_SERVICE_URL) as client:
        resp = await client.get(
            "/videos-by-labels",
            params={"labels": ",".join(labels)}
        )
    data = resp.json()
    if isinstance(data, dict):
        await message.reply(f"{data.get('detail', 'Ошибка сервиса.')}")
        return
    if not data:
        await message.reply("Совпадений не найдено.")
        return

    random.shuffle(data)
    videos = data[:5]

    # --- inline-кнопки ---
    kb = InlineKeyboardBuilder()
    text = f"Объекты: {', '.join(labels)}\nНайдены видео:\n"
    for v in videos:
        text += f"- ID {v['id']} (status={v['status']})\n"
        kb.button(text=f"Видео #{v['id']}", callback_data=f"status:{v['id']}")
    kb.adjust(1)

    await message.reply(text, reply_markup=kb.as_markup())
