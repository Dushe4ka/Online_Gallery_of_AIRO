# database_users.py
import logging
import aiosqlite
from config import USERS_DB_PATH # Используем путь из конфига

# Название новой базы данных
DATABASE = USERS_DB_PATH


async def init_users_db():
    """
    Создаёт таблицу users в отдельной базе, если её ещё нет.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            await db.commit()
        logging.info(f"Users table in '{DATABASE}' created or already exists.")
    except Exception as e:
         logging.error(f"Error initializing users database '{DATABASE}': {e}")


async def add_user(user_id: int):
    """
    Добавляет пользователя в таблицу users (в отдельной базе).
    Если user_id уже существует, запись не добавляется.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
        # logging.info(f"User {user_id} added to '{DATABASE}' (if not already present).") # Можно раскомментировать для отладки
    except Exception as e:
         logging.error(f"Error adding user {user_id} to '{DATABASE}': {e}")


async def remove_user(user_id: int):
    """
    Удаляет пользователя из таблицы users (в отдельной базе).
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()
        logging.info(f"User {user_id} removed from '{DATABASE}'.")
    except Exception as e:
         logging.error(f"Error removing user {user_id} from '{DATABASE}': {e}")


async def get_all_users() -> list[int]:
    """
    Получает всех пользователей из таблицы users (из отдельной базы).
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                users = await cursor.fetchall()
                return [user[0] for user in users]
    except Exception as e:
        logging.error(f"Error getting all users from '{DATABASE}': {e}")
        return []