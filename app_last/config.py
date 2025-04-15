import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администраторов (список)
ADMINS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Путь к базе данных
DB_PATH = os.getenv("DB_PATH")
