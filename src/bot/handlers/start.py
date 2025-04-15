# src/bot/handlers/start.py
from aiogram import types
from src.bot.keyboards.main_menu import main_menu_keyboard

async def start_cmd(message: types.Message):
    await message.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_menu_keyboard
    )
