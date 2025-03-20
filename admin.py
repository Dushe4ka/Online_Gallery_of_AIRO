from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    add_content, delete_content, delete_all_content,
    add_moderator, remove_moderator, is_moderator, get_content
)
from config import ADMINS
from bot import dp, sections, bot

### --- СОСТОЯНИЯ ДЛЯ АДМИН-ПАНЕЛИ --- ###
class AddContentState(StatesGroup):
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
    await state.set_state(AddContentState.waiting_for_description)
    await callback.answer()


@dp.callback_query(F.data == "del_content")
async def delete_content_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Удалить контент'"""
    keyboard = await get_sections_keyboard("del_content")
    await callback.message.answer("🗑 Выберите раздел для удаления контента:", reply_markup=keyboard)
    await state.set_state(DeleteContentState.waiting_for_section)
    await callback.answer()


@dp.callback_query(F.data == "clear_section")
async def clear_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Очистить раздел'"""
    keyboard = await get_sections_keyboard("clear_section")
    await callback.message.answer("⚠ Выберите раздел для очистки:", reply_markup=keyboard)
    await state.set_state(ClearSectionState.waiting_for_section)
    await callback.answer()


@dp.callback_query(F.data == "add_moderator")
async def add_moderator_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить модератора'"""
    await callback.message.answer("👤 Введите ID пользователя, которого хотите сделать модератором:")
    await state.set_state(AddModeratorState.waiting_for_user_id)
    await callback.answer()


@dp.callback_query(F.data == "remove_moderator")
async def remove_moderator_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Удалить модератора'"""
    await callback.message.answer("🚫 Введите ID модератора, которого хотите удалить:")
    await state.set_state(RemoveModeratorState.waiting_for_user_id)
    await callback.answer()


@dp.callback_query(F.data.startswith("add_content_"), AddContentState.waiting_for_description)
async def add_content_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела для добавления контента"""
    section = callback.data.split("_", 2)[-1]  # Берем последний элемент после второго разделителя
    if section in sections:
        await state.update_data(section=section)
        await callback.message.answer(f"📝 Вы выбрали раздел '{sections[section]}'. Теперь введите описание:")
        await state.set_state(AddContentState.waiting_for_description)
    else:
        await callback.message.answer("⚠ Раздел не найден.")
    await callback.answer()


@dp.message(AddContentState.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    """Обработчик ввода описания"""
    description = message.text
    await state.update_data(description=description)
    await message.answer("📷 Теперь отправьте фотографии (если их нет, отправьте '-'):")
    await state.set_state(AddContentState.waiting_for_photos)


@dp.message(AddContentState.waiting_for_photos)
async def process_photos(message: types.Message, state: FSMContext):
    """Обработчик ввода фотографий"""
    user_data = await state.get_data()
    section = user_data["section"]
    description = user_data["description"]

    if message.text == "-":
        # Если пользователь отправил "-", сохраняем контент без фотографий
        await add_content(section, "Заголовок", description, [])
        await message.answer("✅ Контент успешно добавлен без фотографий.")
    elif message.photo:
        # Если пользователь отправил фотографии, сохраняем их
        photos = list(set([("photo", photo.file_id) for photo in message.photo]))  # Убираем дубликаты
        await add_content(section, "Заголовок", description, photos)
        await message.answer(f"✅ Контент успешно добавлен с {len(photos)} фотографиями.")
    else:
        await message.answer("⚠ Пожалуйста, отправьте фотографии или '-'.")

    await state.clear()


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

    # Создаем клавиатуру с постами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{row[1]}", callback_data=f"delete_post_{row[0]}")]
        for row in content
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


@dp.callback_query(F.data.startswith("clear_section_"), ClearSectionState.waiting_for_section)
async def clear_section_section_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела для очистки"""
    section = callback.data.split("_", 2)[-1]
    await delete_all_content(section)
    await callback.message.answer(f"✅ Раздел '{sections[section]}' успешно очищен.")
    await state.clear()
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


@dp.message(RemoveModeratorState.waiting_for_user_id)
async def process_remove_moderator(message: types.Message, state: FSMContext):
    """Обработчик ввода ID модератора для удаления"""
    user_id = message.text
    if not user_id.isdigit():
        await message.answer("⚠ ID модератора должен быть числом. Попробуйте снова.")
        return

    await remove_moderator(int(user_id))
    await message.answer(f"✅ Модератор с ID {user_id} успешно удалён.")
    await state.clear()