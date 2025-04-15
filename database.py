# database.py
import logging
import aiosqlite
from config import DB_PATH

DATABASE = DB_PATH

CONTENT_SECTIONS = [
    "about_artist", "about_style", "catalog", "events",
    "guests", "cooperation", "contacts", "icons"
]

async def init_db():
    """Создаёт таблицы контента и модераторов, если их ещё нет"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("CREATE TABLE IF NOT EXISTS moderators (user_id INTEGER PRIMARY KEY)")
        logging.info("Table 'moderators' initialized.")
        for section in CONTENT_SECTIONS:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {section} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    published_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {section}_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id INTEGER NOT NULL,
                    media_type TEXT NOT NULL CHECK(media_type IN ('photo', 'video')),
                    file_id TEXT NOT NULL,
                    FOREIGN KEY (content_id) REFERENCES {section}(id) ON DELETE CASCADE
                )
            """)
            logging.info(f"Tables '{section}' and '{section}_media' initialized.")
        await db.commit()
        logging.info("Content and moderators database initialization complete.")

# --- Работа с контентом ---

async def add_content(section: str, title: str, description: str, media_files: list[dict]) -> int | None:
    """Добавляет контент с медиафайлами. Возвращает ID."""
    # (Код этой функции остается без изменений)
    if section not in CONTENT_SECTIONS:
        logging.error(f"Attempted to add content to non-existent section: {section}")
        return None
    async with aiosqlite.connect(DATABASE) as db:
        try:
            async with db.cursor() as cursor:
                await cursor.execute(f"INSERT INTO {section} (title, description) VALUES (?, ?)", (title, description))
                content_id = cursor.lastrowid
                if content_id and media_files:
                    unique_files_data = []
                    seen_file_ids = set()
                    for file in media_files:
                        if file["file_id"] not in seen_file_ids:
                            seen_file_ids.add(file["file_id"])
                            unique_files_data.append((content_id, file["type"], file["file_id"]))
                    if unique_files_data:
                        await cursor.executemany(f"INSERT INTO {section}_media (content_id, media_type, file_id) VALUES (?, ?, ?)", unique_files_data)
                        logging.info(f"Added {len(unique_files_data)} media files for content_id={content_id} in section '{section}'")
            await db.commit()
            logging.info(f"Content added successfully to section '{section}' with id={content_id}")
            return content_id
        except aiosqlite.Error as e:
            logging.error(f"Database error adding content to section '{section}': {e}")
            await db.rollback(); return None
        except Exception as e:
            logging.error(f"Unexpected error adding content to section '{section}': {e}")
            await db.rollback(); return None

async def get_content(section: str, content_id: int = None) -> list:
    """
    Получает контент с медиафайлами.
    СОРТИРОВКА ИЗМЕНЕНА НА ASC (старые первыми).
    """
    if section not in CONTENT_SECTIONS:
        logging.error(f"Attempted to get content from non-existent section: {section}")
        return []
    async with aiosqlite.connect(DATABASE) as db:
        try:
            base_query = f"""
                SELECT c.id, c.title, c.description, m.media_type, m.file_id
                FROM {section} c
                LEFT JOIN {section}_media m ON c.id = m.content_id
            """
            params = ()
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            # Сортируем по дате добавления (старые первыми) и ID медиа
            order_clause = "ORDER BY c.published_at ASC, m.id ASC"
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            if content_id:
                query = base_query + f" WHERE c.id = ? {order_clause}"
                params = (content_id,)
            else:
                query = base_query + f" {order_clause}"

            async with db.execute(query, params) as cursor:
                content = await cursor.fetchall()
                return content
        except aiosqlite.Error as e:
            logging.error(f"Database error getting content for section '{section}': {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error getting content for section '{section}': {e}")
            return []

async def get_post_details(section: str, content_id: int) -> dict | None:
    """Получает детали одного поста."""
    # (Код этой функции остается без изменений)
    rows = await get_content(section, content_id)
    if not rows:
        logging.warning(f"Post details not found for section='{section}', content_id={content_id}")
        return None
    post_details = {"id": rows[0][0], "title": rows[0][1], "description": rows[0][2], "media": []}
    for row in rows:
        if row[3] and row[4]:
            post_details["media"].append({"type": row[3], "file_id": row[4]})
    return post_details

async def delete_content(section: str, content_id: int) -> bool:
    """Удаляет определённый контент."""
    # (Код этой функции остается без изменений)
    if section not in CONTENT_SECTIONS: return False
    async with aiosqlite.connect(DATABASE) as db:
        try:
            cursor = await db.execute(f"DELETE FROM {section} WHERE id = ?", (content_id,))
            await db.commit()
            success = cursor.rowcount > 0
            if success: logging.info(f"Deleted content with id={content_id} from section '{section}'")
            else: logging.warning(f"Content id={content_id} not found in '{section}' for deletion.")
            return success
        except aiosqlite.Error as e: logging.error(f"DB error deleting id={content_id} from '{section}': {e}"); await db.rollback(); return False
        except Exception as e: logging.error(f"Unexpected error deleting id={content_id} from '{section}': {e}"); await db.rollback(); return False

async def delete_all_content(section: str) -> bool:
    """Очищает всю таблицу с контентом для раздела."""
    # (Код этой функции остается без изменений)
    if section not in CONTENT_SECTIONS: return False
    async with aiosqlite.connect(DATABASE) as db:
        try:
            await db.execute(f"DELETE FROM {section}")
            await db.commit()
            logging.info(f"Cleared all content from section '{section}'")
            return True
        except aiosqlite.Error as e: logging.error(f"DB error clearing section '{section}': {e}"); await db.rollback(); return False
        except Exception as e: logging.error(f"Unexpected error clearing section '{section}': {e}"); await db.rollback(); return False

# --- Работа с модераторами (остается без изменений) ---
async def add_moderator(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        try: await db.execute("INSERT OR IGNORE INTO moderators (user_id) VALUES (?)", (user_id,)); await db.commit(); logging.info(f"Added/ignored moderator {user_id}")
        except aiosqlite.Error as e: logging.error(f"DB error adding moderator {user_id}: {e}")
async def remove_moderator(user_id: int):
     async with aiosqlite.connect(DATABASE) as db:
        try: await db.execute("DELETE FROM moderators WHERE user_id = ?", (user_id,)); await db.commit(); logging.info(f"Removed moderator {user_id}")
        except aiosqlite.Error as e: logging.error(f"DB error removing moderator {user_id}: {e}"); await db.rollback()
async def get_moderators() -> list[int]:
    async with aiosqlite.connect(DATABASE) as db:
        try:
            async with db.execute("SELECT user_id FROM moderators") as cursor: return [row[0] for row in await cursor.fetchall()]
        except aiosqlite.Error as e: logging.error(f"DB error getting moderators: {e}"); return []
async def is_moderator(user_id: int) -> bool:
    mods = await get_moderators(); return user_id in mods