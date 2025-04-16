# src/main.py
import asyncio
import logging

from decouple import config

from aiogram import Bot, Dispatcher, F
from src.bot.handlers.search import handle_search_query, start_search
from src.bot.handlers.status_callback import register_status_callback_handlers
from src.database.session import init_db
from src.database.models import Base

from src.bot.handlers.start import start_cmd
from src.bot.handlers.video import handle_video
from src.bot.handlers.text import handle_text
from src.bot.handlers.status import status_cmd

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=config('TELEGRAM_BOT_TOKEN'))
    dp = Dispatcher()

    # Регистрируем хэндлеры
    dp.message.register(start_cmd, F.text == "/start")
    dp.message.register(handle_video, F.video)
    # dp.message.register(status_cmd, F.text.startswith("/status"))
    dp.message.register(start_search, F.text == "Поиск")  # если кнопка с текстом "Поиск"
    dp.message.register(handle_search_query)  # универсальный хэндлер текста
    dp.message.register(handle_text, F.text)
    
    register_status_callback_handlers(dp)
    
    # Инициализируем БД (создаём таблицы, если их нет)
    await init_db(Base)

    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
