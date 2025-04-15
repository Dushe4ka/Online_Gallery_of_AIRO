import asyncio
import zipfile
import os
import json
import schedule
from aiogram import Bot, types
from config import BOT_TOKEN, ADMINS

# ✅ Список пользователей, которым отправляется бэкап
USER_IDS = ADMINS # Добавьте нужные ID

# ✅ Файл базы данных и имя архива
DB_FILE = "bot_data.db"
BACKUP_FILE = "bot_data_backup.zip"
MESSAGE_IDS_FILE = "backup_message_ids.json"  # Файл для хранения ID сообщений

# ✅ Инициализация бота
bot = Bot(token=BOT_TOKEN)

def create_backup():
    """Создает ZIP-архив с базой данных."""
    if os.path.exists(DB_FILE):
        with zipfile.ZipFile(BACKUP_FILE, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(DB_FILE)
        print(f"✅ Бэкап создан: {BACKUP_FILE}")
        return True
    else:
        print("❌ Файл базы данных не найден!")
        return False

def load_message_ids():
    """Загружает последние ID сообщений из файла."""
    if os.path.exists(MESSAGE_IDS_FILE):
        with open(MESSAGE_IDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_message_ids(message_ids):
    """Сохраняет последние ID сообщений в файл."""
    with open(MESSAGE_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(message_ids, f)

async def send_backup():
    """Отправляет архив с базой данных пользователям, удаляя старое сообщение."""
    if not create_backup():
        return

    document = types.FSInputFile(BACKUP_FILE)  # Используем FSInputFile
    message_ids = load_message_ids()

    for user_id in USER_IDS:
        try:
            # Удаляем предыдущее сообщение с бэкапом (если есть)
            if str(user_id) in message_ids:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=message_ids[str(user_id)])
                    print(f"♻️ Удалено предыдущее сообщение у {user_id}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить предыдущее сообщение у {user_id}: {e}")

            # Отправляем новый бэкап
            msg = await bot.send_document(chat_id=user_id, document=document, caption="📦 Еженедельный бэкап базы данных")

            # Сохраняем ID нового сообщения
            message_ids[str(user_id)] = msg.message_id
            print(f"✅ Бэкап отправлен пользователю {user_id}")

        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {user_id}: {e}")

    # Обновляем файл с ID сообщений
    save_message_ids(message_ids)

async def backup_service():
    """Асинхронный сервис для отправки бэкапа раз в неделю по понедельникам в 09:00."""
    schedule.every().monday.at("09:00").do(lambda: asyncio.create_task(send_backup()))

    print("⏳ Сервис бэкапа запущен. Ожидание времени отправки...")

    while True:
        schedule.run_pending()
        await asyncio.sleep(60)  # Проверять расписание каждую минуту

# ✅ Запуск службы бэкапа
if __name__ == "__main__":
    asyncio.run(backup_service())
