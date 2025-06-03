# src/bot/states.py

# Словарь user_id -> bool (True, если пользователь сейчас вводит поисковый запрос)
SEARCH_STATE = {}

# Словарь user_id -> True, когда ждём фотографию для поиска
IMAGE_SEARCH_STATE = {}