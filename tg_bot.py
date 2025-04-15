import os
from aiogram import Bot, Dispatcher, types, F
import asyncio
from decouple import config

TOKEN = config('TELEGRAM_BOT_TOKEN')

# Папка для сохранения видео (если не существует, создаётся)
VIDEO_STORAGE = "videos"
if not os.path.exists(VIDEO_STORAGE):
    os.makedirs(VIDEO_STORAGE)

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Декоратор с фильтром: обрабатываем только сообщения, где есть поле video
    @dp.message(F.video)
    async def handle_video(message: types.Message):
        video = message.video
        file_id = video.file_id

        # Получаем информацию о файле через API Telegram
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path

        # Определяем путь сохранения видео
        video_filename = os.path.join(VIDEO_STORAGE, f"{file_id}.mp4")

        # Скачиваем файл
        await bot.download_file(file_path, video_filename)

        # Отправляем пользователю подтверждение
        await message.reply("Ваше видео успешно сохранено!")

    # Запускаем поллинг бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())