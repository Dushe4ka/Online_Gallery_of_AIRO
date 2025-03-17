import sqlite3
from config import DB_PATH


def init_db():
    """Инициализация базы данных, создание таблиц, если их нет."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        # Таблица контента (фото/видео)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                media_type TEXT CHECK(media_type IN ('photo', 'video')) NOT NULL,
                media_url TEXT NOT NULL,
                description TEXT NOT NULL
            )
        """)

        # Таблица модераторов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY
            )
        """)

        conn.commit()


# ===================== Работа с пользователями =====================

def add_user(user_id):
    """Добавление пользователя в базу (если его нет)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()


def get_users():
    """Получение всех пользователей."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in cursor.fetchall()]


# ===================== Работа с контентом =====================

def add_content(section, media_type, media_url, description):
    """Добавление контента в базу (без title)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO content (section, media_type, media_url, description) 
            VALUES (?, ?, ?, ?)
        """, (section, media_type, media_url, description))
        conn.commit()


def get_content(section):
    """Получение контента по разделу (ID, media_type, media_url, description)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, media_type, media_url, description 
            FROM content 
            WHERE section = ?
        """, (section,))
        return cursor.fetchall()


def get_content_list(section):
    """Получает список контента для удаления (ID, description вместо title)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, description FROM content WHERE section = ?
        """, (section,))
        return cursor.fetchall()


def delete_content(content_id):
    """Удаление контента по ID."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM content WHERE id = ?", (content_id,))
        conn.commit()


# ===================== Работа с модераторами =====================

def add_moderator(user_id):
    """Добавление модератора."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO moderators (user_id) VALUES (?)", (user_id,))
        conn.commit()


def remove_moderator(user_id):
    """Удаление модератора."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM moderators WHERE user_id = ?", (user_id,))
        conn.commit()


async def get_moderators():
    """Получение списка модераторов."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM moderators")
        return [row[0] for row in cursor.fetchall()]


# ===================== Проверки =====================

def is_admin(user_id, ADMINS):
    """Проверка, является ли пользователь администратором."""
    return user_id in ADMINS


def is_moderator(user_id):
    """Проверка, является ли пользователь модератором."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM moderators WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
