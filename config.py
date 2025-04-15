# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов (список)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMINS = []
if ADMIN_IDS_STR:
    try:
        ADMINS = list(map(int, ADMIN_IDS_STR.split(",")))
    except ValueError:
        print("Ошибка: ADMIN_IDS в .env должен быть списком чисел, разделенных запятыми.")

# Путь к основной базе данных (контент, модераторы)
DB_PATH = "bot_data.db"
# Путь к базе данных пользователей
USERS_DB_PATH = "users_data.db" # <-- Добавлено

# Путь к файлу для ID сообщений бэкапа (из service.py)
BACKUP_MESSAGE_IDS_FILE = "backup_message_ids.json"
# Имя файла бэкапа
BACKUP_FILE_NAME = "bot_data_backup.zip"