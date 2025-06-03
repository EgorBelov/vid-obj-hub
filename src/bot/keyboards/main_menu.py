# src/bot/keyboards/main_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Загрузить видео")],
        [KeyboardButton(text="Поиск"), KeyboardButton(text="Поиск по изображению")]
    ],
    resize_keyboard=True
)
