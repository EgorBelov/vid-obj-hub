# src/bot/keyboards/status.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_status_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Проверить статус", callback_data=f"status:{video_id}")]
        ]
    )
