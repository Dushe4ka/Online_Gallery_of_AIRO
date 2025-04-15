import logging

import aiosqlite

DATABASE = "bot_data.db"

async def init_db():
    """Создаёт таблицы, если их ещё нет"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Таблица пользователей для рассылки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        # Таблица модераторов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY
            )
        """)

        # Создание таблиц для контента и медиафайлов
        sections = [
            "about_artist", "about_style", "catalog", "events",
            "guests", "cooperation", "contacts"
        ]
        for section in sections:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {section} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    published_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {section}_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id INTEGER,
                    media_type TEXT CHECK(media_type IN ('photo', 'video')),
                    file_id TEXT,
                    FOREIGN KEY (content_id) REFERENCES {section}(id) ON DELETE CASCADE
                )
            """)

        await db.commit()


# Добавление контента
async def add_content(section: str, title: str, description: str, media_files: list[dict]):
    """
    Добавляет контент с медиафайлами в указанный раздел.
    Возвращает ID добавленного контента.
    """
    async with aiosqlite.connect(DATABASE) as db:
        try:
            # 1. Добавляем основной контент (текст)
            cursor = await db.execute(
                f"""
                INSERT INTO {section} (title, description)
                VALUES (?, ?)
                """,
                (title, description)
            )
            content_id = cursor.lastrowid

            # 2. Добавляем медиафайлы, если они есть
            if media_files:
                # Убираем дубликаты
                unique_files = []
                seen = set()
                for file in media_files:
                    file_key = (file["type"], file["file_id"])
                    if file_key not in seen:
                        seen.add(file_key)
                        unique_files.append(file)

                # Логируем file_id
                logging.info(f"Добавляемые медиафайлы: {unique_files}")

                # Подготавливаем данные для вставки
                media_data = [
                    (content_id, file["type"], file["file_id"])
                    for file in unique_files
                ]

                # Вставляем все записи одним запросом
                await db.executemany(
                    f"""
                    INSERT INTO {section}_media (content_id, media_type, file_id)
                    VALUES (?, ?, ?)
                    """,
                    media_data
                )

            # Явно завершаем транзакцию
            await db.commit()
            return content_id  # Возвращаем ID добавленного контента

        except Exception as e:
            logging.error(f"Ошибка добавления контента: {e}")
            await db.rollback()
            return None


# Получение контента
async def get_content(section: str, content_id: int = None):
    """
    Получает контент с медиафайлами.

    :param section: Раздел, из которого нужно получить контент.
    :param content_id: ID конкретного контента (опционально).
    :return: Список контента.
    """
    async with aiosqlite.connect(DATABASE) as db:
        if content_id:
            # Получаем конкретный контент по ID
            cursor = await db.execute(f"""
                SELECT c.id, c.title, c.description, m.media_type, m.file_id
                FROM {section} c
                LEFT JOIN {section}_media m ON c.id = m.content_id
                WHERE c.id = ?
                ORDER BY c.published_at DESC
            """, (content_id,))
        else:
            # Получаем весь контент раздела
            cursor = await db.execute(f"""
                SELECT c.id, c.title, c.description, m.media_type, m.file_id
                FROM {section} c
                LEFT JOIN {section}_media m ON c.id = m.content_id
                ORDER BY c.published_at DESC
            """)
        content = await cursor.fetchall()
        logging.info(f"Извлеченный контент: {content}")
        return content


async def get_moderators():
    """Получает всех модераторов"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM moderators")
        return [row[0] for row in await cursor.fetchall()]


# Удаление конкретного контента по ID
async def delete_content(section, content_id):
    """Удаляет определённый контент (вместе с медиафайлами)"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(f"DELETE FROM {section} WHERE id = ?", (content_id,))
        await db.commit()

# Удаление всех записей из раздела
async def delete_all_content(section):
    """Очищает всю таблицу с контентом"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(f"DELETE FROM {section}")
        await db.commit()

# Добавление пользователя
async def add_user(user_id):
    """Добавляет пользователя в базу для рассылки"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

# Удаление пользователя
async def remove_user(user_id):
    """Удаляет пользователя из базы рассылки"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

# Получение всех пользователей
async def get_users():
    """Получает всех подписанных пользователей"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        return [row[0] for row in await cursor.fetchall()]

# Добавление модератора
async def add_moderator(user_id):
    """Добавляет модератора"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT OR IGNORE INTO moderators (user_id) VALUES (?)", (user_id,))
        await db.commit()

# Удаление модератора
async def remove_moderator(user_id):
    """Удаляет модератора"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM moderators WHERE user_id = ?", (user_id,))
        await db.commit()

# Проверка, является ли пользователь модератором
async def is_moderator(user_id):
    """Проверяет, является ли пользователь модератором"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT 1 FROM moderators WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

