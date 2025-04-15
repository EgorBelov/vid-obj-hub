# src/bot/handlers/text.py
from aiogram import types

async def handle_text(message: types.Message):
    text = message.text.lower()
    if text == "загрузить видео":
        await message.reply("Пожалуйста, отправьте видео, которое хотите загрузить.")
    elif text == "поиск":
        await message.reply("Функционал поиска пока не реализован. Попробуйте позже.")
    else:
        await message.reply("Неизвестная команда. Пожалуйста, используйте клавиатуру.")
