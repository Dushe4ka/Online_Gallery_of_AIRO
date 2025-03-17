from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMINS
from database import (
    add_content, get_users, get_content_list, delete_content,
    add_moderator, remove_moderator, get_moderators
)

import logging

router = Router()

# Логирование
logger = logging.getLogger(__name__)


# Машина состояний
class UploadState(StatesGroup):
    section = State()
    media = State()
    description = State()


class ModeratorState(StatesGroup):
    add = State()
    remove = State()


# Проверка на админа/модератора
def is_admin(user_id):
    return user_id in ADMINS


async def is_moderator(user_id):
    return user_id in await get_moderators()


# Главное меню
@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id) and not await is_moderator(message.from_user.id):
        return await message.answer("⛔ У вас нет прав.")
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📷 Фото/🎥 Видео")],
            [types.KeyboardButton(text="🛠 Модератор")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)


# Фото/Видео меню
@router.message(lambda message: message.text == "📷 Фото/🎥 Видео")
async def media_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить")],
            [types.KeyboardButton(text="🗑 Удалить")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("📂 Выберите действие с фото/видео:", reply_markup=keyboard)


# Добавление контента - выбор категории
@router.message(lambda message: message.text == "➕ Добавить")
async def add_media(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="catalog")],
            [types.KeyboardButton(text="events")],
            [types.KeyboardButton(text="guests")],
            [types.KeyboardButton(text="cooperation")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await state.set_state(UploadState.section)
    await message.answer("📂 Выберите раздел для добавления контента:", reply_markup=keyboard)


@router.message(UploadState.section)
async def receive_media(message: types.Message, state: FSMContext):
    await state.update_data(section=message.text)
    await state.set_state(UploadState.media)
    await message.answer("📤 Отправьте фото или видео:")


@router.message(UploadState.media)
async def enter_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_url = None
    media_type = None

    if message.photo:
        media_url = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_url = message.video.file_id
        media_type = "video"

    if not media_url:
        return await message.answer("⛔ Отправьте фото или видео!")

    await state.update_data(media_url=media_url, media_type=media_type)
    await state.set_state(UploadState.description)
    await message.answer("✏ Введите описание:")


@router.message(UploadState.description)
async def save_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        add_content(data["section"], data["media_type"], data["media_url"], message.text)
        users = get_users()
        for user_id in users:
            try:
                if data["media_type"] == "photo":
                    await message.bot.send_photo(user_id, data["media_url"], caption=message.text)
                else:
                    await message.bot.send_video(user_id, data["media_url"], caption=message.text)
            except Exception as e:
                logger.error(f"Ошибка при отправке медиа пользователю {user_id}: {e}")
        await state.clear()
        await message.answer("✅ Контент загружен и разослан.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении контента: {e}")
        await message.answer("⛔ Произошла ошибка при загрузке контента.")


# Удаление контента
@router.message(lambda message: message.text == "🗑 Удалить")
async def delete_menu(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="catalog")],
            [types.KeyboardButton(text="events")],
            [types.KeyboardButton(text="guests")],
            [types.KeyboardButton(text="cooperation")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("📂 Выберите раздел для удаления контента:", reply_markup=keyboard)


@router.message(lambda message: message.text in ["catalog", "events", "guests", "cooperation"])
async def delete_content_list(message: types.Message):
    content = get_content_list(message.text)
    print(content)
    if not content:
        return await message.answer("❌ В этом разделе нет контента.")
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text=f"ID {id}", callback_data=f"del_{id}")] for id, description in content]
    )
    await message.answer("📋 Выберите контент для удаления:", reply_markup=keyboard)


@router.callback_query(lambda query: query.data.startswith("del_"))
async def confirm_delete_content(callback: types.CallbackQuery):
    content_id = int(callback.data.split("_")[1])
    delete_content(content_id)
    await callback.message.answer("✅ Контент удалён.")


# Модераторское меню
@router.message(lambda message: message.text == "🛠 Модератор")
async def moderator_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет прав.")

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить модератора")],
            [types.KeyboardButton(text="🗑 Удалить модератора")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("👨‍💼 Модераторская панель:", reply_markup=keyboard)


# Добавление модератора
@router.message(lambda message: message.text == "➕ Добавить модератора")
async def add_moderator_menu(message: types.Message, state: FSMContext):
    await state.set_state(ModeratorState.add)
    await message.answer("🆔 Введите ID пользователя для добавления модератором:")


@router.message(ModeratorState.add)
async def add_moderator_action(message: types.Message, state: FSMContext):
    user_id = message.text
    if not user_id.isdigit():
        return await message.answer("⛔ Введите правильный ID пользователя.")

    user_id = int(user_id)
    add_moderator(user_id)
    await state.clear()
    await message.answer(f"✅ Пользователь с ID {user_id} добавлен как модератор.")


# Удаление модератора
@router.message(lambda message: message.text == "🗑 Удалить модератора")
async def remove_moderator_menu(message: types.Message, state: FSMContext):
    await state.set_state(ModeratorState.remove)
    await message.answer("🆔 Введите ID пользователя для удаления из модераторов:")


@router.message(ModeratorState.remove)
async def remove_moderator_action(message: types.Message, state: FSMContext):
    user_id = message.text
    if not user_id.isdigit():
        return await message.answer("⛔ Введите правильный ID пользователя.")

    user_id = int(user_id)
    await remove_moderator(user_id)
    await state.clear()
    await message.answer(f"✅ Пользователь с ID {user_id} удалён из модераторов.")


@router.message(lambda message: message.text == "🔙 Назад")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id) and not await is_moderator(message.from_user.id):
        return await message.answer("⛔ У вас нет прав.")
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📷 Фото/🎥 Видео")],
            [types.KeyboardButton(text="🛠 Модератор")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)
