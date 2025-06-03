# src/bot/handlers/text.py
from aiogram import types

async def handle_text(message: types.Message):
    text = message.text.lower()
    if text == "загрузить видео":
        await message.reply("Пожалуйста, отправьте видео.")
    elif text == "поиск":
        await message.reply("Введите запрос: «поиск <текст>».")
    elif text == "поиск по изображению":
        await message.reply("Пришлите фото объекта для поиска.")
    elif text.startswith("/status"):
        return  # обрабатывается отдельно
    else:
        await message.reply("Неизвестная команда. Используйте встроенную клавиатуру.")

