from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMINS
from database import add_content, get_users

router = Router()

# Машина состояний для загрузки контента
class UploadState(StatesGroup):
    section = State()
    media = State()
    description = State()


# Проверка на админа
def is_admin(user_id):
    return user_id in ADMINS


# Команда /admin
@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет прав администратора.")

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text="➕ Добавить фото"),
            types.KeyboardButton(text="➕ Добавить видео")
        ]], resize_keyboard=True
    )
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)


# Начало загрузки контента
@router.message(lambda message: message.text in ["➕ Добавить фото", "➕ Добавить видео"])
async def add_media(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет прав администратора.")

    media_type = "photo" if "фото" in message.text else "video"
    await state.update_data(media_type=media_type)
    await state.set_state(UploadState.section)
    await message.answer("📂 Введите раздел (catalog, events, guests, cooperation):")


# Ввод раздела
@router.message(UploadState.section)
async def enter_section(message: types.Message, state: FSMContext):
    await state.update_data(section=message.text)
    await state.set_state(UploadState.media)
    await message.answer("📤 Отправьте фото или видео:")


# Прием медиа
@router.message(UploadState.media)
async def receive_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_type = data["media_type"]
    media_url = message.photo[-1].file_id if media_type == "photo" else message.video.file_id
    await state.update_data(media_url=media_url)
    await state.set_state(UploadState.description)
    await message.answer("✏ Введите описание:")


# Ввод описания и сохранение
@router.message(UploadState.description)
async def enter_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    add_content(data["section"], data["media_type"], data["media_url"], message.text)

    # Рассылка пользователям
    users = get_users()
    for user_id in users:
        try:
            if data["media_type"] == "photo":
                await message.bot.send_photo(user_id, data["media_url"], caption=message.text)
            else:
                await message.bot.send_video(user_id, data["media_url"], caption=message.text)
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ Контент загружен и разослан пользователям.")
