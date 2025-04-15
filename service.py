# service.py
import asyncio
import zipfile
import os
import json
import logging
import schedule # Убедитесь, что установлен: pip install schedule
from aiogram import Bot, types
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
# Импортируем пути и админов из конфига
from config import ADMINS, DB_PATH, BACKUP_MESSAGE_IDS_FILE, BACKUP_FILE_NAME

# Логгер для этого модуля
logger = logging.getLogger(__name__)

# ✅ Список пользователей, которым отправляется бэкап (Админы)
USER_IDS = ADMINS

def create_backup():
    """Создает ZIP-архив с базой данных."""
    if os.path.exists(DB_PATH):
        try:
            with zipfile.ZipFile(BACKUP_FILE_NAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(DB_PATH, os.path.basename(DB_PATH)) # Добавляем файл с его именем внутри архива
            logger.info(f"Backup created: {BACKUP_FILE_NAME}")
            return True
        except Exception as e:
            logger.error(f"Error creating backup zip file: {e}")
            return False
    else:
        logger.error(f"Database file not found at {DB_PATH}")
        return False

def load_message_ids():
    """Загружает последние ID сообщений бэкапа из файла."""
    if os.path.exists(BACKUP_MESSAGE_IDS_FILE):
        try:
            with open(BACKUP_MESSAGE_IDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
             logger.error(f"Error decoding backup message IDs file: {e}")
             return {}
        except Exception as e:
             logger.error(f"Error loading backup message IDs file: {e}")
             return {}
    return {}

def save_message_ids(message_ids):
    """Сохраняет последние ID сообщений бэкапа в файл."""
    try:
        with open(BACKUP_MESSAGE_IDS_FILE, "w", encoding="utf-8") as f:
            json.dump(message_ids, f, indent=4) # Сохраняем с отступом для читаемости
    except Exception as e:
        logger.error(f"Error saving backup message IDs file: {e}")

# Эта функция теперь вызывается по расписанию и должна принимать bot
async def send_backup_task(bot: Bot):
    """Задача для создания и отправки бэкапа."""
    logger.info("Starting backup task...")
    if not create_backup():
        logger.error("Backup creation failed, task aborted.")
        return

    try:
        # Используем types.FSInputFile для отправки локального файла
        document = types.FSInputFile(BACKUP_FILE_NAME)
    except FileNotFoundError:
         logger.error(f"Backup file {BACKUP_FILE_NAME} not found after creation attempt.")
         return

    message_ids = load_message_ids()
    new_message_ids = message_ids.copy() # Работаем с копией

    for user_id in USER_IDS:
        user_id_str = str(user_id)
        try:
            # Удаляем предыдущее сообщение с бэкапом (если есть)
            if user_id_str in message_ids:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=message_ids[user_id_str])
                    logger.info(f"Deleted previous backup message for user {user_id}")
                except TelegramForbiddenError:
                     logger.warning(f"Can't delete message for user {user_id}, bot might be blocked.")
                     if user_id_str in new_message_ids: del new_message_ids[user_id_str]
                except TelegramAPIError as e:
                    if "message to delete not found" in str(e).lower():
                         logger.warning(f"Previous backup message for user {user_id} not found.")
                         if user_id_str in new_message_ids: del new_message_ids[user_id_str]
                    else:
                         logger.error(f"Failed to delete previous backup message for user {user_id}: {e}")

            # Отправляем новый бэкап
            msg = await bot.send_document(chat_id=user_id, document=document, caption="📦 Еженедельный бэкап базы данных")

            # Сохраняем ID нового сообщения
            new_message_ids[user_id_str] = msg.message_id
            logger.info(f"Backup sent to user {user_id}, message_id: {msg.message_id}")

        except TelegramForbiddenError:
            logger.warning(f"User {user_id} blocked the bot. Cannot send backup.")
            if user_id_str in new_message_ids: del new_message_ids[user_id_str]
        except TelegramAPIError as e:
            logger.error(f"Failed to send backup to user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending backup to user {user_id}: {e}")

    # Обновляем файл с ID сообщений
    save_message_ids(new_message_ids)

    # Удаляем локальный файл бэкапа после отправки
    try:
        if os.path.exists(BACKUP_FILE_NAME):
            os.remove(BACKUP_FILE_NAME)
            logger.info(f"Local backup file {BACKUP_FILE_NAME} removed.")
    except OSError as e:
        logger.error(f"Error removing local backup file: {e}")

# Эта функция запускается как asyncio Task из bot.py и должна принимать bot
async def backup_service(bot: Bot):
    """
    Асинхронный сервис для запуска отправки бэкапа по расписанию.
    Принимает экземпляр бота.
    """
    # Настраиваем расписание: каждый понедельник в 09:00
    schedule.every().monday.at("09:00").do(lambda: asyncio.create_task(send_backup_task(bot)))
    # Для теста:
    # schedule.every(5).minutes.do(lambda: asyncio.create_task(send_backup_task(bot))) # Каждые 5 минут

    logger.info("Backup service scheduler started. Waiting for scheduled time...")

    while True:
        try:
            # Запускаем запланированные задачи
            schedule.run_pending()
        except Exception as e:
             # Ловим ошибки выполнения самих задач schedule, если они возникнут
             logger.error(f"Error running scheduled task: {e}")
        # Пауза перед следующей проверкой расписания
        await asyncio.sleep(60) # Проверять раз в минуту
