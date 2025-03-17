import sqlite3
from config import DB_PATH

def init_db():
    """Инициализация базы данных."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)

    # Таблица контента
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            media_type TEXT NOT NULL CHECK(media_type IN ('photo', 'video')),
            media_url TEXT NOT NULL,
            description TEXT
        )
    """)

    conn.commit()
    conn.close()

def add_user(user_id):
    """Добавление пользователя в базу (если его нет)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_users():
    """Получение всех пользователей."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def add_content(section, media_type, media_url, description):
    """Добавление контента в базу."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO content (section, media_type, media_url, description)
        VALUES (?, ?, ?, ?)
    """, (section, media_type, media_url, description))
    conn.commit()
    conn.close()

def get_content(section):
    """Получение контента по разделу."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT media_type, media_url, description FROM content WHERE section = ?", (section,))
    content = cursor.fetchall()
    conn.close()
    return content

