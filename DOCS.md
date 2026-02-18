# Техническая документация — Online Gallery of AIRO

Документация для разработчиков: как запускать проект, структура кода и окружение.

---

## 1. Описание проекта

Telegram-бот галереи: пользователи просматривают разделы (каталог, мероприятия, контакты и т.д.), админы и модераторы управляют контентом через админ-панель. После добавления поста выполняется рассылка подписчикам. Еженедельно админам отправляется бэкап основной БД.

**Стек:** Python 3.10+, aiogram 3.x, SQLite (aiosqlite), python-dotenv, schedule.

---

## 2. Требования

- **Python** 3.10+
- **Токен бота** от [@BotFather](https://t.me/BotFather)
- **Telegram ID администраторов** (например, через [@userinfobot](https://t.me/userinfobot))

---

## 3. Структура проекта

```
Online_Gallery_of_AIRO/
├── bot.py              # Точка входа, хендлеры, FSM, админ-панель
├── config.py           # BOT_TOKEN, ADMINS, пути к БД и бэкапу
├── database.py         # Контент и модераторы (bot_data.db)
├── database_users.py   # Подписчики (users_data.db)
├── service.py          # Еженедельный бэкап БД в Telegram
├── utils.py            # Рассылка нового поста (send_new_post)
├── requirements.txt
├── .env                # Секреты (не коммитить)
├── .env.sample         # Пример переменных
├── bot_data.db         # Создаётся при первом запуске
├── users_data.db       # Создаётся при первом запуске
├── DOCS.md             # Эта документация
└── app_last/           # Резервная копия старой версии (если есть)
```

---

## 4. Установка и настройка

### 4.1 Окружение и зависимости

```bash
cd Online_Gallery_of_AIRO
python3 -m venv myvenv
source myvenv/bin/activate   # macOS/Linux
# Windows: myvenv\Scripts\activate

pip install -r requirements.txt
```

### 4.2 Переменные окружения

Скопируйте пример и заполните:

```bash
cp .env.sample .env
```

Содержимое `.env`:

| Переменная   | Описание                    | Пример |
|-------------|-----------------------------|--------|
| `BOT_TOKEN` | Токен от BotFather          | `123456:ABC...` |
| `ADMIN_IDS` | ID админов через запятую    | `123456789,987654321` |
| `DB_PATH`   | Путь к БД контента (опц.)   | `bot_data.db` |

В `config.py` по умолчанию заданы: `DB_PATH = "bot_data.db"`, `USERS_DB_PATH = "users_data.db"`, а также файлы бэкапа. При необходимости их можно переопределить через `.env` (если конфиг будет читать эти переменные).

---

## 5. Запуск

### 5.1 Основной запуск

```bash
python bot.py
```

В логах ожидаются строки:
- инициализация БД;
- регистрация хендлеров разделов;
- запуск задачи бэкапа;
- старт polling.

### 5.2 Продакшн (PM2)

```bash
pm2 start bot.py --name airo_bot --interpreter python3
pm2 save
pm2 startup
```

Бэкап запускать отдельно не нужно — он работает как фоновая задача внутри бота.

---

## 6. Архитектура

### 6.1 Точка входа

`bot.py` → `main()`:

1. `init_db()` (контент + модераторы), `init_users_db()` (подписчики).
2. `register_section_handlers()` — кнопки разделов главного меню.
3. `asyncio.create_task(backup_service(bot))` — планировщик бэкапа.
4. `dp.start_polling(bot, allowed_updates=...)`.

### 6.2 Две базы данных

- **bot_data.db** (`config.DB_PATH`): контент по разделам, медиа, модераторы. Инициализация и работа в `database.py`.
- **users_data.db** (`config.USERS_DB_PATH`): подписчики (user_id). Инициализация и работа в `database_users.py`.

### 6.3 Разделы контента

В `bot.py` задан словарь `sections` (ключ — идентификатор, значение — текст кнопки). Список разделов в БД задаётся в `database.CONTENT_SECTIONS`. Они должны совпадать, иначе при старте пишется предупреждение в лог.

Текущие разделы: `about_artist`, `about_style`, `catalog`, `icons`, `events`, `guests`, `cooperation`, `contacts`.

Для части разделов включён режим «описание по кнопке» (`SECTIONS_WITH_DESCRIPTION_TOGGLE`): сначала показывается только заголовок, описание открывается по кнопке «ℹ️ ОПИСАНИЕ».

---

## 7. База данных

### 7.1 bot_data.db

- **moderators** — `user_id` (модераторы).
- Для каждого раздела из `CONTENT_SECTIONS`:
  - **{section}** — `id`, `title`, `description`, `published_at`;
  - **{section}_media** — `id`, `content_id`, `media_type` ('photo'|'video'), `file_id`, FK на `{section}(id)`.

Контент отдаётся в порядке `published_at ASC` (сначала старые).

### 7.2 users_data.db

- **users** — `user_id` (подписчики для рассылки).

### 7.3 Основные функции

**database.py:**  
`init_db`, `add_content`, `get_content`, `get_post_details`, `delete_content`, `delete_all_content`, `add_moderator`, `remove_moderator`, `is_moderator`, `get_moderators`.

**database_users.py:**  
`init_users_db`, `add_user`, `remove_user`, `get_all_users`.

---

## 8. Админ-панель

- Команда **/admin** (доступ: ID в `ADMINS` или в таблице модераторов).
- Callback-префикс кнопок: **admin:** (например, `admin:del_content`, `admin:add_select:catalog`).
- FSM: `AdminStates` в `bot.py` (выбор раздела, ввод заголовка/описания, загрузка медиа, удаление поста, очистка раздела, модераторы).

Удаление контента: постраничный список постов (по 8 на страницу), callback пагинации: `admin:del_page:{section}:{page}`.

---

## 9. Сервисы

### 9.1 Бэкап (service.py)

- По расписанию (понедельник 09:00) создаётся ZIP с `DB_PATH`, отправляется всем из `ADMINS`.
- Старое сообщение с бэкапом у админа удаляется, новое сохраняется в `backup_message_ids.json`.
- Бот передаётся в `backup_service(bot)` при запуске.

### 9.2 Рассылка нового поста (utils.py)

- `send_new_post(bot, section, content_id, users)` — отправляет один пост (медиагруппа или текст) списку `users`.
- Учитываются `TelegramForbiddenError`, `TelegramRetryAfter`, прочие ошибки API.
- Вызывается из бота после успешного добавления контента; список пользователей берётся из `get_all_users()`.

---

## 10. Конфигурация (config.py)

- **BOT_TOKEN** — из `.env`.
- **ADMINS** — список int из `ADMIN_IDS` (строка из `.env`, разбитая по запятой).
- **DB_PATH** — основная БД (по умолчанию `bot_data.db`).
- **USERS_DB_PATH** — БД пользователей (по умолчанию `users_data.db`).
- **BACKUP_MESSAGE_IDS_FILE**, **BACKUP_FILE_NAME** — файл для ID сообщений бэкапа и имя ZIP.

---

## 11. Быстрый старт (чеклист)

- [ ] Python 3.10+, venv создан и активирован  
- [ ] `pip install -r requirements.txt`  
- [ ] Файл `.env` с `BOT_TOKEN` и `ADMIN_IDS`  
- [ ] Запуск: `python bot.py`  
- [ ] В боте: `/start`, затем `/admin` (под учёткой с ID из ADMINS)

---

## 12. Важные замечания

- Не коммитить `.env` и файлы `*.db`, если в них есть боевые данные.
- При добавлении нового раздела нужно добавить его в `sections` в `bot.py` и в `CONTENT_SECTIONS` в `database.py`, а также при необходимости в `SECTIONS_WITH_DESCRIPTION_TOGGLE`.
- Лимиты Telegram: размер inline-клавиатуры, длина caption, flood control — в коде учтены (пагинация удаления, рассылка с retry и задержками).
