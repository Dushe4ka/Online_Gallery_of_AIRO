import logging

import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN, ADMINS
from database import (
    init_db, get_content,
    add_content, delete_content, delete_all_content,
    add_moderator, remove_moderator, is_moderator, get_moderators, DATABASE
)
from database_users import add_user, get_all_users, init_users_db
from service import backup_service
import asyncio
# Добавляем импорт новой базы данных
from utils import send_new_post

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Список разделов
sections = {
    "about_artist": "🖌 О художнике",
    "about_style": "🎨 Life",
    "catalog": "🖼 Каталог картин",
    "events": "📅 Мероприятия",
    "guests": "👥 Наши гости",
    "cooperation": "🤝 Сотрудничество",
    "contacts": "📞 Контакты"
}


### --- СОСТОЯНИЯ ДЛЯ АДМИН-ПАНЕЛИ --- ###
class AddContentState(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_photos = State()


class DeleteContentState(StatesGroup):
    waiting_for_section = State()
    waiting_for_content_id = State()


class ClearSectionState(StatesGroup):
    waiting_for_section = State()


class AddModeratorState(StatesGroup):
    waiting_for_user_id = State()


class RemoveModeratorState(StatesGroup):
    waiting_for_user_id = State()
    confirmation = State()


from aiogram.types import InputMediaVideo


async def send_content(message: types.Message, section: str):
    """Отправляет контент пользователю с группировкой медиа"""
    content = await get_content(section)
    if not content:
        await message.answer(f"⚠ В разделе '{sections[section]}' пока нет контента.")
        return

    # Группируем по постам
    posts = {}
    for row in content:
        post_id = row[0]
        if post_id not in posts:
            posts[post_id] = {
                "title": row[1],
                "description": row[2],
                "photos": [],
                "videos": []
            }
        if row[3] == "photo":
            posts[post_id]["photos"].append(row[4])
        elif row[3] == "video":
            posts[post_id]["videos"].append(row[4])

    # Отправляем посты
    for post in posts.values():
        text = f"📌 <b>{post['title']}</b>\n\n{post['description']}"

        # Создаем медиагруппу
        media_group = []

        # Добавляем первое фото с текстом
        if post["photos"]:
            media_group.append(
                InputMediaPhoto(
                    media=post["photos"][0],
                    caption=text,
                    parse_mode="HTML"
                )
            )
            # Добавляем остальные фото
            for file_id in post["photos"][1:]:
                media_group.append(InputMediaPhoto(media=file_id))

        # Добавляем видео
        for video_id in post["videos"]:
            media_group.append(
                InputMediaVideo(
                    media=video_id
                )
            )

        # Отправляем медиагруппу
        if media_group:
            await message.answer_media_group(media_group)
        else:
            # Если нет медиафайлов, отправляем только текст
            await message.answer(text, parse_mode="HTML")


### --- ОБРАБОТЧИКИ КНОПОК --- ###
async def handle_section_button(message: types.Message):
    """Обрабатывает нажатие на кнопку раздела"""
    # Определяем, какой раздел был выбран
    for section, button_text in sections.items():
        if message.text == button_text:
            await send_content(message, section)
            break


### --- ФУНКЦИИ АДМИН-ПАНЕЛИ --- ###
async def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    return user_id in ADMINS


async def show_admin_panel(user_id: int):
    """Отображает меню админа / модератора"""
    if await is_admin(user_id):
        text = "🔧 *Админ-панель* 🔧\nВыберите действие:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить контент", callback_data="add_content")],
            [InlineKeyboardButton(text="🗑 Удалить контент", callback_data="del_content")],
            [InlineKeyboardButton(text="🔥 Очистить раздел", callback_data="clear_section")],
            [InlineKeyboardButton(text="➕ Добавить модератора", callback_data="add_moderator")],
            [InlineKeyboardButton(text="❌ Удалить модератора", callback_data="remove_moderator")]
        ])
    elif await is_moderator(user_id):
        text = "🔹 *Модераторская панель* 🔹\nВыберите действие:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить контент", callback_data="add_content")],
            [InlineKeyboardButton(text="🗑 Удалить контент", callback_data="del_content")]
        ])
    else:
        return "⛔ У вас нет доступа."

    return text, keyboard


@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    """Обрабатывает команду /admin"""
    user_id = message.from_user.id
    response = await show_admin_panel(user_id)

    if isinstance(response, tuple):
        text, keyboard = response
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(response)


### --- ОБРАБОТЧИКИ CALLBACK-КНОПОК --- ###
async def get_sections_keyboard(action: str):
    """Возвращает клавиатуру с разделами для выбранного действия"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"{action}_{section}")]
        for section, name in sections.items()
    ])
    return keyboard


@dp.callback_query(F.data == "add_content")
async def add_content_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить контент'"""
    keyboard = await get_sections_keyboard("add_content")
    await callback.message.answer("📝 Выберите раздел для добавления контента:", reply_markup=keyboard)
    await state.set_state(AddContentState.waiting_for_title)
    await callback.answer()


@dp.callback_query(F.data.startswith("add_content_"), AddContentState.waiting_for_title)
async def add_content_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела для добавления контента"""
    section = callback.data.split("_", 2)[-1]  # Берем последний элемент после второго разделителя
    if section in sections:
        await state.update_data(section=section)  # Сохраняем раздел в user_data
        await callback.message.answer(f"📝 Вы выбрали раздел '{sections[section]}'. Теперь введите название поста:")
        await state.set_state(AddContentState.waiting_for_title)
    else:
        await callback.message.answer("⚠ Раздел не найден.")
    await callback.answer()


@dp.message(AddContentState.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    """Обработчик ввода названия"""
    title = message.text
    await state.update_data(title=title)
    await message.answer("📝 Теперь введите описание поста:")
    await state.set_state(AddContentState.waiting_for_description)


@dp.message(AddContentState.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    """Обработчик ввода описания"""
    description = message.text
    await state.update_data(description=description)
    await message.answer("📷 Теперь отправьте фотографии (если их нет, отправьте '-'):")
    await state.set_state(AddContentState.waiting_for_photos)


@dp.message(AddContentState.waiting_for_photos)
async def process_photos(message: types.Message, state: FSMContext):
    """Обработчик ввода медиафайлов (фото или видео)"""
    user_data = await state.get_data()

    # Проверяем наличие ключа 'section'
    if "section" not in user_data:
        await message.answer("⚠ Ошибка: раздел не выбран. Начните заново.")
        await state.clear()
        return

    # Если пользователь отправляет "-", сохраняем пост без медиафайлов
    if message.text == "-":
        content_id = await add_content(
            user_data["section"],
            user_data["title"],
            user_data["description"],
            []
        )
        if content_id:
            await message.answer("✅ Контент добавлен без медиафайлов")
        else:
            await message.answer("⚠ Ошибка при сохранении контента.")
        await state.clear()
        return

    # Обработка фото
    if message.photo:
        new_media = {"type": "photo", "file_id": message.photo[-1].file_id}
    # Обработка видео
    elif message.video:
        new_media = {"type": "video", "file_id": message.video.file_id}
    else:
        await message.answer("⚠ Отправьте фото, видео или '-' для завершения.")
        return

    # Получаем текущий список медиафайлов
    current_media = user_data.get("media", [])

    # Проверяем дубликаты
    if new_media not in current_media:
        current_media.append(new_media)
        await state.update_data(media=current_media)
        logging.info(f"Добавлен новый медиафайл: {new_media}")
    else:
        logging.info(f"Медиафайл уже добавлен: {new_media}")

    # Кнопка завершения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить", callback_data="finish_media")]
    ])

    await message.answer(
        f"📷 Медиафайл добавлен. Всего: {len(current_media)}\n"
        "Можете отправить ещё или нажать кнопку ниже:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "finish_media")
async def finish_media(callback: CallbackQuery, state: FSMContext):
    """Финализация добавления контента"""
    user_data = await state.get_data()

    # Проверяем наличие ключа 'section'
    if "section" not in user_data:
        await callback.message.answer("⚠ Ошибка: раздел не выбран. Начните заново.")
        await state.clear()
        return

    # Добавляем контент в базу данных
    content_id = await add_content(
        user_data["section"],
        user_data["title"],
        user_data["description"],
        user_data.get("media", [])
    )

    if content_id:
        # Получаем всех пользователей для рассылки
        users = await get_all_users()

        # Рассылаем новый контент всем пользователям
        await send_new_post(bot, user_data["section"], content_id, users)

        await callback.message.answer("✅ Контент успешно сохранён и отправлен!")
    else:
        await callback.message.answer("⚠ Ошибка при сохранении контента.")

    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "finish_photos")
async def finish_photos(callback: CallbackQuery, state: FSMContext):
    """Финализация добавления контента"""
    user_data = await state.get_data()

    await add_content(
        user_data["section"],
        user_data["title"],
        user_data["description"],
        user_data.get("photos", [])
    )

    await callback.message.answer("✅ Контент успешно сохранён!")
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "del_content")
async def delete_content_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Удалить контент'"""
    keyboard = await get_sections_keyboard("del_content")
    await callback.message.answer("🗑 Выберите раздел для удаления контента:", reply_markup=keyboard)
    await state.set_state(DeleteContentState.waiting_for_section)
    await callback.answer()


@dp.callback_query(F.data.startswith("del_content_"), DeleteContentState.waiting_for_section)
async def delete_content_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела для удаления контента"""
    section = callback.data.split("_", 2)[-1]
    await state.update_data(section=section)

    # Получаем контент из раздела
    content = await get_content(section)
    if not content:
        await callback.message.answer("⚠ В этом разделе пока нет контента.")
        await state.clear()
        return

    # Группируем по постам
    posts = {}
    for row in content:
        post_id = row[0]
        if post_id not in posts:
            posts[post_id] = {
                "title": row[1],
                "description": row[2],
                "media": []
            }
        if row[3] == "photo":
            posts[post_id]["media"].append(row[4])

    # Создаем клавиатуру с постами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{post['title']}", callback_data=f"delete_post_{post_id}")]
        for post_id, post in posts.items()
    ])
    await callback.message.answer("🗑 Выберите пост для удаления:", reply_markup=keyboard)
    await state.set_state(DeleteContentState.waiting_for_content_id)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_post_"), DeleteContentState.waiting_for_content_id)
async def process_delete_post(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора поста для удаления"""
    content_id = callback.data.split("_")[-1]
    user_data = await state.get_data()
    section = user_data["section"]

    await delete_content(section, int(content_id))
    await callback.message.answer(f"✅ Пост с ID {content_id} успешно удалён из раздела '{sections[section]}'.")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "clear_section")
async def clear_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Очистить раздел'"""
    keyboard = await get_sections_keyboard("clear_section")
    await callback.message.answer("⚠ Выберите раздел для очистки:", reply_markup=keyboard)
    await state.set_state(ClearSectionState.waiting_for_section)
    await callback.answer()


@dp.callback_query(F.data.startswith("clear_section_"), ClearSectionState.waiting_for_section)
async def clear_section_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела для очистки"""
    section = callback.data.split("_", 2)[-1]
    await delete_all_content(section)
    await callback.message.answer(f"✅ Раздел '{sections[section]}' успешно очищен.")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "add_moderator")
async def add_moderator_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить модератора'"""
    await callback.message.answer("👤 Введите ID пользователя, которого хотите сделать модератором:")
    await state.set_state(AddModeratorState.waiting_for_user_id)
    await callback.answer()


@dp.message(AddModeratorState.waiting_for_user_id)
async def process_add_moderator(message: types.Message, state: FSMContext):
    """Обработчик ввода ID пользователя для добавления модератора"""
    user_id = message.text
    if not user_id.isdigit():
        await message.answer("⚠ ID пользователя должен быть числом. Попробуйте снова.")
        return

    await add_moderator(int(user_id))
    await message.answer(f"✅ Пользователь с ID {user_id} успешно добавлен в модераторы.")
    await state.clear()


@dp.callback_query(F.data == "remove_moderator")
async def remove_moderator_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Удалить модератора'"""
    moderators = await get_moderators()
    if not moderators:
        await callback.message.answer("⚠ Модераторов пока нет.")
        return

    # Создаем клавиатуру с модераторами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Модератор {moderator}", callback_data=f"remove_moderator_{moderator}")]
        for moderator in moderators
    ])
    await callback.message.answer("🚫 Выберите модератора для удаления:", reply_markup=keyboard)
    await callback.answer()


# class RemoveModeratorState(StatesGroup):
#     confirmation = State()


@dp.callback_query(F.data.startswith("remove_moderator_"))
async def confirm_remove_moderator(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления модератора"""
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(user_id=user_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_remove"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_remove")
        ]
    ])

    await callback.message.answer(
        f"⚠ Вы уверены, что хотите удалить модератора {user_id}?",
        reply_markup=keyboard
    )
    await state.set_state(RemoveModeratorState.confirmation)
    await callback.answer()


@dp.callback_query(F.data == "confirm_remove", RemoveModeratorState.confirmation)
async def process_remove(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения"""
    data = await state.get_data()
    await remove_moderator(data["user_id"])
    await callback.message.answer("✅ Модератор успешно удалён!")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "cancel_remove", RemoveModeratorState.confirmation)
async def cancel_remove(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    await state.clear()
    await callback.message.answer("❌ Удаление отменено")
    await callback.answer()


@dp.callback_query(F.data.startswith("remove_moderator_"))
async def process_remove_moderator(callback: CallbackQuery):
    """Обработчик выбора модератора для удаления"""
    user_id = callback.data.split("_")[-1]
    await remove_moderator(int(user_id))
    await callback.message.answer(f"✅ Модератор с ID {user_id} успешно удалён.")
    await callback.answer()


### --- РЕГИСТРАЦИЯ ХЭНДЛЕРОВ --- ###
def register_handlers():
    """Регистрируем обработчики"""
    dp.message.register(start_command, Command("start"))

    # Обработчики для кнопок разделов
    for text in sections.values():
        dp.message.register(handle_section_button, F.text == text)


### --- ГЛАВНЫЙ ЦИКЛ БОТА --- ###
async def start_command(message: types.Message):
    """Команда /start"""

    # Добавляем пользователя в новую базу данных
    await add_user(message.from_user.id)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖌 О художнике"), KeyboardButton(text="🎨 Life")],
            [KeyboardButton(text="🖼 Каталог картин"), KeyboardButton(text="📅 Мероприятия")],
            [KeyboardButton(text="👥 Наши гости"), KeyboardButton(text="🤝 Сотрудничество")],
            [KeyboardButton(text="📞 Контакты")]
        ], resize_keyboard=True
    )
    await message.answer("🎨 Добро пожаловать в ONLINE GALLERY OF AIRO!", reply_markup=keyboard)





async def main():
    await init_db()
    # Инициализация новой базы данных для пользователей
    await init_users_db()

    register_handlers()

    # Запускаем фоновый процесс для бэкапа
    asyncio.create_task(backup_service())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
