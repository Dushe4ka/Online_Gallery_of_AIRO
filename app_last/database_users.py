# database_users.py
import logging
import aiosqlite

# Название новой базы данных
DATABASE_USERS = "users_data.db"


async def init_users_db():
    """
    Создаёт таблицу users, если её ещё нет.
    """
    async with aiosqlite.connect(DATABASE_USERS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()
        logging.info("Таблица users создана или уже существует.")


async def add_user(user_id: int):
    """
    Добавляет пользователя в таблицу users.
    Если user_id уже существует, запись не добавляется.
    """
    async with aiosqlite.connect(DATABASE_USERS) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
        logging.info(f"Пользователь {user_id} добавлен в таблицу users (если его ещё не было).")


async def remove_user(user_id: int):
    """
    Удаляет пользователя из таблицы users.
    """
    async with aiosqlite.connect(DATABASE_USERS) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
        logging.info(f"Пользователь {user_id} удалён из таблицы users.")


async def get_all_users():
    """
    Получает всех пользователей из таблицы users.
    """
    async with aiosqlite.connect(DATABASE_USERS) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
        return [user[0] for user in users]